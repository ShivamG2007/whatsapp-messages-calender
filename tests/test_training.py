import json
from datetime import datetime, timedelta

from brain.training import evaluate, export_label_studio, export_llamafactory, import_label_studio
from tests.conftest import IST, FakeExtractor, make_msg

WED = datetime(2026, 11, 4, 10, 0, tzinfo=IST)


def _fill(processor, extractor, n=10):
    for i in range(n):
        extractor.queue(action="add", event="Practice", date_text="tomorrow", time_text=f"{i % 5 + 3}pm")
        processor.handle(make_msg(f"practice tomorrow {i % 5 + 3}pm #{i}", WED + timedelta(minutes=i), f"msg{i}"))


def _ls_export(tasks, overrides):
    exported = []
    for task in tasks:
        result = task["predictions"][0]["result"]
        rid = task["data"]["record_id"]
        if rid in overrides:
            result = [r for r in result if r["from_name"] != "action"]
            result.append(
                {"from_name": "action", "to_name": "message", "type": "choices", "value": {"choices": [overrides[rid]]}}
            )
        exported.append({"data": task["data"], "annotations": [{"result": result, "was_cancelled": False}]})
    return exported


def test_label_studio_roundtrip_and_llamafactory_export(processor, extractor, tmp_path):
    _fill(processor, extractor)
    tasks_file = tmp_path / "tasks.json"
    assert export_label_studio(processor.dataset, tasks_file) == 10
    tasks = json.loads(tasks_file.read_text())
    assert tasks[0]["data"]["message"].startswith("practice tomorrow")
    assert tasks[0]["predictions"][0]["result"][0]["value"] == {"choices": ["add"]}

    export_file = tmp_path / "export.json"
    export_file.write_text(json.dumps(_ls_export(tasks, {tasks[0]["data"]["record_id"]: "none"})))
    counts = import_label_studio(processor.dataset, export_file)
    assert counts == {"correct": 9, "corrected": 1}
    assert export_label_studio(processor.dataset, tasks_file) == 0

    out = tmp_path / "lf"
    counts = export_llamafactory(processor.dataset, out)
    assert counts["train"] + counts["test"] == 10
    info = json.loads((out / "dataset_info.json").read_text())
    assert info["calbot_train"]["columns"]["response"] == "output"
    rows = json.loads((out / "calbot_train.json").read_text()) + json.loads((out / "calbot_test.json").read_text())
    first = json.loads(rows[0]["output"])
    assert list(first) == ["action", "event", "date_text", "time_text", "end_time_text", "place", "target", "confidence"]
    assert rows[0]["system"].startswith("You read WhatsApp messages")


def test_evaluate_scores_fields(processor, extractor, tmp_path):
    _fill(processor, extractor, 20)
    tasks_file = tmp_path / "t.json"
    export_label_studio(processor.dataset, tasks_file)
    tasks = json.loads(tasks_file.read_text())
    (tmp_path / "e.json").write_text(json.dumps(_ls_export(tasks, {})))
    import_label_studio(processor.dataset, tmp_path / "e.json")

    model = FakeExtractor()
    test_records = processor.dataset.records(labeled_only=True, split="test")
    for rec in test_records:
        model.queue(**rec["label"])
    report = evaluate(processor.dataset, model, "test")
    assert report["examples"] == len(test_records)
    if test_records:
        assert report["all_fields_correct"] == 1.0
