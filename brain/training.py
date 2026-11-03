import json
from collections import Counter
from pathlib import Path

from .dataset import Dataset
from .prompts import OUTPUT_SCHEMA, SYSTEM_PROMPT

TEXT_FIELDS = ("event", "date_text", "time_text", "end_time_text", "place")
LABEL_FIELDS = ("action",) + TEXT_FIELDS + ("target",)
TRAINING_CONFIDENCE = 0.9


def _norm(value) -> str:
    return " ".join(str(value or "").lower().split())


def _prediction_result(decision: dict) -> list[dict]:
    result = [
        {"from_name": "action", "to_name": "message", "type": "choices", "value": {"choices": [decision.get("action", "none")]}}
    ]
    for name in TEXT_FIELDS:
        if decision.get(name):
            result.append({"from_name": name, "to_name": "message", "type": "textarea", "value": {"text": [decision[name]]}})
    result.append(
        {"from_name": "target", "to_name": "message", "type": "number", "value": {"number": int(decision.get("target") or 0)}}
    )
    return result


def export_label_studio(dataset: Dataset, out_path: Path, include_labeled: bool = False) -> int:
    """Write Label Studio tasks, pre-filled with what the model said, so labeling is mostly clicking 'Submit'."""
    tasks = []
    for rec in dataset.records():
        if rec["label_status"] != "unlabeled" and not include_labeled:
            continue
        decision = rec.get("decision") or {}
        prefill = rec.get("label") or decision
        tasks.append(
            {
                "data": {
                    "record_id": rec["id"],
                    "chat_name": rec["chat_name"] or "",
                    "sender": rec["sender"] or "",
                    "sent_at": rec["sent_at"],
                    "message": rec["message"],
                    "context": rec["context_text"] or "",
                    "candidates": rec["candidates_text"] or "",
                    "model_output": json.dumps(decision, ensure_ascii=False),
                    "bot_result": json.dumps(rec.get("result") or {}, ensure_ascii=False),
                },
                "predictions": [{"model_version": rec["model"] or "unknown", "result": _prediction_result(prefill)}],
            }
        )
    out_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(tasks)


def _label_from_annotation(result: list[dict]) -> dict:
    label = {"action": "none", **{name: "" for name in TEXT_FIELDS}, "target": 0}
    for item in result:
        name, value = item.get("from_name"), item.get("value", {})
        if name == "action" and value.get("choices"):
            label["action"] = value["choices"][0]
        elif name in TEXT_FIELDS and value.get("text"):
            label[name] = str(value["text"][0]).strip()
        elif name == "target" and value.get("number") is not None:
            label["target"] = int(value["number"])
    return label


def import_label_studio(dataset: Dataset, export_path: Path) -> Counter:
    """Read a Label Studio JSON export and store your answers next to the model's answers."""
    tasks = json.loads(export_path.read_text(encoding="utf-8"))
    counts: Counter = Counter()
    for task in tasks:
        record_id = task.get("data", {}).get("record_id")
        annotations = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
        if record_id is None or not annotations:
            counts["skipped"] += 1
            continue
        record = dataset.get(int(record_id))
        if record is None:
            counts["unknown_record"] += 1
            continue
        label = _label_from_annotation(annotations[-1]["result"])
        model = record.get("decision") or {}
        same = all(_norm(label[f]) == _norm(model.get(f, "" if f != "target" else 0)) for f in LABEL_FIELDS)
        status = "correct" if same else "corrected"
        dataset.set_label(int(record_id), label, status)
        counts[status] += 1
    return counts


def training_output(label: dict) -> str:
    ordered = {key: label.get(key, 0 if key == "target" else "") for key in OUTPUT_SCHEMA["properties"] if key != "confidence"}
    ordered["confidence"] = TRAINING_CONFIDENCE
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


def export_llamafactory(dataset: Dataset, out_dir: Path) -> dict:
    """Write train/test files in LLaMA-Factory's alpaca format plus the dataset_info.json it needs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split in ("train", "test"):
        rows = [
            {"instruction": rec["user_prompt"], "input": "", "output": training_output(rec["label"]), "system": SYSTEM_PROMPT}
            for rec in dataset.records(labeled_only=True, split=split)
            if rec.get("user_prompt") and rec.get("label")
        ]
        (out_dir / f"calbot_{split}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        counts[split] = len(rows)
    columns = {"prompt": "instruction", "query": "input", "response": "output", "system": "system"}
    info = {f"calbot_{split}": {"file_name": f"calbot_{split}.json", "columns": columns} for split in ("train", "test")}
    (out_dir / "dataset_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return counts


def evaluate(dataset: Dataset, extractor, split: str = "test", limit: int | None = None) -> dict:
    """Run the model on labeled examples it was not trained on and score it field by field."""
    records = [r for r in dataset.records(labeled_only=True, split=split) if r.get("user_prompt")]
    if limit:
        records = records[:limit]
    field_hits: Counter = Counter()
    all_correct = 0
    mistakes = []
    for rec in records:
        predicted, _ = extractor.extract(rec["user_prompt"])
        pred = predicted.to_dict()
        label = rec["label"]
        ok_fields = [f for f in LABEL_FIELDS if _norm(pred.get(f)) == _norm(label.get(f, "" if f != "target" else 0))]
        field_hits.update(ok_fields)
        if len(ok_fields) == len(LABEL_FIELDS):
            all_correct += 1
        elif len(mistakes) < 10:
            mistakes.append({"id": rec["id"], "message": rec["message"][:80], "expected": label, "got": pred})
    total = len(records)
    return {
        "examples": total,
        "all_fields_correct": round(all_correct / total, 3) if total else None,
        "per_field": {f: round(field_hits[f] / total, 3) if total else None for f in LABEL_FIELDS},
        "sample_mistakes": mistakes,
    }
