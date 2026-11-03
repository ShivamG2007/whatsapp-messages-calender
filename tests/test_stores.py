from datetime import datetime, timedelta

from brain.calendars import format_description, parse_description
from brain.dataset import Dataset, split_for
from brain.extractor import parse_output
from brain.memory import ShortTermMemory
from brain.prefilter import might_be_schedule
from tests.conftest import IST, make_msg

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=IST)


def test_memory_keeps_two_days_only(tmp_path):
    mem = ShortTermMemory(tmp_path / "m.db", keep_days=2)
    mem.add(make_msg("old one", NOW - timedelta(days=3), "old"))
    mem.add(make_msg("yesterday", NOW - timedelta(days=1), "mid"))
    mem.add(make_msg("now", NOW, "new"))
    assert mem.prune(now=NOW) == 1
    assert [r["body"] for r in mem.recent("Dance group@g.us", int(NOW.timestamp()) + 1, 10)] == ["yesterday", "now"]


def test_memory_and_dataset_are_separate_files(settings):
    assert settings.memory_db != settings.dataset_db


def test_dataset_split_is_stable():
    assert split_for("abc") == split_for("abc")
    splits = [split_for(str(i)) for i in range(1000)]
    assert 150 < splits.count("test") < 250


def test_dataset_label_roundtrip(tmp_path):
    ds = Dataset(tmp_path / "d.db")
    rid = ds.add(message_id="x", message="hi", sent_at=NOW.isoformat(), decision={"action": "none"})
    assert ds.add(message_id="x", message="hi", sent_at=NOW.isoformat()) is None
    ds.set_label(rid, {"action": "add"}, "corrected")
    rec = ds.get(rid)
    assert rec["label"] == {"action": "add"} and rec["label_status"] == "corrected"
    assert ds.stats()["by_label_status"] == {"corrected": 1}


def test_description_roundtrip():
    text = format_description("CalBot", "123@g.us", "Dance group", "m1", "practice\n tomorrow 6pm", NOW, ["a", "b"])
    info = parse_description(text)
    assert text.startswith("[CalBot]")
    assert info["chat"] == "Dance group"
    assert info["chat_id"] == "123@g.us"
    assert info["source_message"] == "practice tomorrow 6pm"
    assert info["history"] == ["a", "b"]


def test_parse_output_handles_junk():
    assert parse_output('{"action":"add","event":"X","target":"2","confidence":"0.8"}').target == 2
    assert parse_output('<think>hmm</think>\n{"action":"cancel"}').action == "cancel"
    assert parse_output('{"action":"explode"}').action == "none"
    assert parse_output("not json").action == "none"


def test_prefilter():
    assert might_be_schedule("practice kal 6 baje")
    assert might_be_schedule("meeting shifted to 7:30")
    assert might_be_schedule("submission due 12 nov")
    assert not might_be_schedule("hahaha")
    assert not might_be_schedule("ok")


def test_ollama_host_from_system_env_is_usable(monkeypatch):
    from brain.config import _ollama_host

    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    assert _ollama_host() == "http://127.0.0.1:11434"
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    assert _ollama_host() == "http://127.0.0.1:11434"
