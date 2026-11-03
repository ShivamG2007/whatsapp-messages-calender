from datetime import date, datetime, time

import pytest

from brain.dates import parse_time_range, resolve_date, resolve_when
from tests.conftest import IST

WED = datetime(2026, 11, 4, 0, 44, tzinfo=IST)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("tomorrow", date(2026, 11, 5)),
        ("kal", date(2026, 11, 5)),
        ("tmrw", date(2026, 11, 5)),
        ("today", date(2026, 11, 4)),
        ("aaj", date(2026, 11, 4)),
        ("tonight", date(2026, 11, 4)),
        ("parso", date(2026, 11, 6)),
        ("day after tomorrow", date(2026, 11, 6)),
        ("friday", date(2026, 11, 6)),
        ("next friday", date(2026, 11, 6)),
        ("this saturday", date(2026, 11, 7)),
        ("on sat", date(2026, 11, 7)),
        ("wednesday", date(2026, 11, 4)),
        ("monday", date(2026, 11, 9)),
        ("5 nov", date(2026, 11, 5)),
        ("20th november", date(2026, 11, 20)),
        ("12/11", date(2026, 11, 12)),
    ],
)
def test_resolve_date(text, expected):
    assert resolve_date(text, WED) == expected


def test_resolve_date_gibberish():
    assert resolve_date("whenever", WED) is None


@pytest.mark.parametrize(
    "text, start, end",
    [
        ("7pm", time(19, 0), None),
        ("7 PM", time(19, 0), None),
        ("7:30 pm", time(19, 30), None),
        ("7.30pm", time(19, 30), None),
        ("19:00", time(19, 0), None),
        ("7", time(19, 0), None),
        ("7 baje", time(19, 0), None),
        ("9", time(9, 0), None),
        ("9am", time(9, 0), None),
        ("12 am", time(0, 0), None),
        ("shaam 6", time(18, 0), None),
        ("subah 6", time(6, 0), None),
        ("noon", time(12, 0), None),
        ("6-8pm", time(18, 0), time(20, 0)),
        ("11am - 1pm", time(11, 0), time(13, 0)),
        ("5:30 to 7", time(17, 30), time(19, 0)),
        ("after the game", None, None),
    ],
)
def test_parse_time_range(text, start, end):
    assert parse_time_range(text) == (start, end)


def test_when_with_date_and_time():
    when = resolve_when("tomorrow", "7pm", "", WED, 60)
    assert when.start == datetime(2026, 11, 5, 19, 0, tzinfo=IST)
    assert when.end == datetime(2026, 11, 5, 20, 0, tzinfo=IST)
    assert not when.all_day and not when.explicit_end


def test_when_time_only_already_passed_moves_to_next_day():
    evening = datetime(2026, 11, 4, 20, 0, tzinfo=IST)
    when = resolve_when("", "7pm", "", evening, 60)
    assert when.start == datetime(2026, 11, 5, 19, 0, tzinfo=IST)


def test_when_date_only_is_all_day():
    when = resolve_when("friday", "", "", WED, 60)
    assert when.all_day
    assert when.start == datetime(2026, 11, 6, 0, 0, tzinfo=IST)


def test_when_keeps_old_date_when_only_time_changes():
    old = datetime(2026, 11, 7, 17, 0, tzinfo=IST)
    when = resolve_when("", "7", "", WED, 60, keep_from=old)
    assert when.start == datetime(2026, 11, 7, 19, 0, tzinfo=IST)


def test_when_keeps_old_time_when_only_date_changes():
    old = datetime(2026, 11, 5, 18, 0, tzinfo=IST)
    when = resolve_when("saturday", "", "", WED, 60, keep_from=old)
    assert when.start == datetime(2026, 11, 7, 18, 0, tzinfo=IST)


def test_when_nothing():
    assert resolve_when("", "", "", WED, 60) is None
