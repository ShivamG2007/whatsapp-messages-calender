from datetime import datetime, timedelta

from tests.conftest import IST, make_msg

WED = datetime(2026, 11, 4, 10, 0, tzinfo=IST)


def events(processor):
    return processor.calendar.list_events(WED - timedelta(days=2), WED + timedelta(days=30))


def test_add_then_reschedule_then_cancel(processor, extractor):
    extractor.queue(action="add", event="dance practice", date_text="tomorrow", time_text="6pm", place="OAT")
    out = processor.handle(make_msg("dance practice tomorrow 6pm at OAT", WED, "m1"))
    assert out.status == "created"
    [event] = events(processor)
    assert event.title == "Dance practice"
    assert event.start == datetime(2026, 11, 5, 18, 0, tzinfo=IST)
    assert event.place == "OAT"
    assert event.chat_name == "Dance group"
    assert "[CalBot]" in event.description

    extractor.queue(action="reschedule", event="dance practice", time_text="7pm", target=1)
    out = processor.handle(make_msg("practice shifted to 7pm", WED + timedelta(hours=1), "m2"))
    assert out.status == "updated"
    [event] = events(processor)
    assert event.start == datetime(2026, 11, 5, 19, 0, tzinfo=IST)
    assert event.end == datetime(2026, 11, 5, 20, 0, tzinfo=IST)
    assert len(event.history) == 2
    assert "dance practice tomorrow 6pm" in event.description

    extractor.queue(action="cancel", event="dance practice", target=1)
    out = processor.handle(make_msg("practice cancelled guys", WED + timedelta(hours=2), "m3"))
    assert out.status == "deleted"
    assert events(processor) == []


def test_model_sees_context_and_calendar(processor, extractor):
    extractor.queue(action="add", event="Practice", date_text="friday", time_text="5pm")
    processor.handle(make_msg("practice friday 5pm", WED, "a"))
    processor.handle(make_msg("ok", WED + timedelta(minutes=1), "b"))
    extractor.queue(action="none")
    processor.handle(make_msg("is practice still on friday?", WED + timedelta(minutes=2), "c"))
    prompt = extractor.prompts[-1]
    assert "practice friday 5pm" in prompt
    assert "1. Practice | Fri 2026-11-06 17:00" in prompt


def test_chitchat_never_reaches_model(processor, extractor):
    out = processor.handle(make_msg("hahaha", WED, "x"))
    assert out.status == "filtered"
    assert extractor.prompts == []


def test_duplicate_message_ignored(processor, extractor):
    extractor.queue(action="add", event="Match", date_text="sat", time_text="4pm")
    processor.handle(make_msg("match sat 4pm", WED, "same"))
    assert processor.handle(make_msg("match sat 4pm", WED, "same")).status == "duplicate"
    assert len(events(processor)) == 1


def test_same_event_announced_twice_is_not_added_twice(processor, extractor):
    extractor.queue(action="add", event="Match", date_text="sat", time_text="4pm")
    extractor.queue(action="add", event="match", date_text="saturday", time_text="4 pm")
    processor.handle(make_msg("match sat 4pm", WED, "one"))
    out = processor.handle(make_msg("reminder: match saturday 4 pm", WED + timedelta(hours=3), "two"))
    assert out.status == "skipped" and out.reason == "duplicate"
    assert len(events(processor)) == 1


def test_low_confidence_skipped(processor, extractor):
    extractor.queue(action="add", event="Meet", date_text="tomorrow", time_text="5", confidence=0.3)
    out = processor.handle(make_msg("maybe meet tomorrow 5?", WED, "lc"))
    assert out.status == "skipped"
    assert events(processor) == []


def test_cancel_without_event_is_skipped(processor, extractor):
    extractor.queue(action="cancel", event="practice")
    out = processor.handle(make_msg("practice cancelled", WED, "c1"))
    assert out.reason == "no_matching_event_to_cancel"


def test_reschedule_without_existing_event_adds_it(processor, extractor):
    extractor.queue(action="reschedule", event="dance practice", date_text="tomorrow", time_text="7pm", place="OAT")
    out = processor.handle(make_msg("guys dance practice shifted to tomorrow 7pm at OAT", WED, "r1"))
    assert out.status == "created"
    assert events(processor)[0].start == datetime(2026, 11, 5, 19, 0, tzinfo=IST)


def test_past_event_not_added(processor, extractor):
    evening = WED.replace(hour=21)
    extractor.queue(action="add", event="Meeting", date_text="today", time_text="5pm")
    out = processor.handle(make_msg("meeting today 5pm was great", evening, "p1"))
    assert out.reason == "event_already_over"


def test_cancel_only_touches_same_chat(processor, extractor):
    extractor.queue(action="add", event="Practice", date_text="friday", time_text="5pm")
    processor.handle(make_msg("practice friday 5pm", WED, "d1", chat="Football"))
    extractor.queue(action="cancel", event="")
    out = processor.handle(make_msg("practice cancelled", WED, "d2", chat="Dance group"))
    assert out.status == "skipped"
    assert len(events(processor)) == 1


def test_everything_is_recorded_in_dataset(processor, extractor):
    extractor.queue(action="add", event="Practice", date_text="tomorrow", time_text="6pm")
    processor.handle(make_msg("practice tomorrow 6pm", WED, "ds1"))
    [rec] = processor.dataset.records()
    assert rec["message"] == "practice tomorrow 6pm"
    assert rec["decision"]["action"] == "add"
    assert rec["result"]["status"] == "created"
    assert rec["label_status"] == "unlabeled"
    assert rec["split"] in {"train", "test"}
    assert "New message from Riya" in rec["user_prompt"]


def test_model_cannot_cancel_another_groups_event(processor, extractor):
    extractor.queue(action="add", event="Match", date_text="friday", time_text="5pm")
    processor.handle(make_msg("match friday 5pm", WED, "f1", chat="Football"))
    extractor.queue(action="cancel", event="Match", target=1)
    out = processor.handle(make_msg("match cancelled", WED, "f2", chat="Dance group"))
    assert out.status == "skipped"
    assert len(events(processor)) == 1
