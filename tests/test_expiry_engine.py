"""Tests for the public API of expiry_engine."""

import logging
import uuid
from collections.abc import Callable
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from itertools import repeat

import pytest

import expiry_engine
from expiry_engine import (
    ExpiryError,
    Item,
    Reminder,
    Rule,
    Status,
    evaluate,
    record_use,
    to_ical,
    upcoming_reminders,
)
from expiry_engine.ical import NAMESPACE

TODAY = date(2026, 3, 10)
EXPIRES = date(2026, 3, 10)
STAMP = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_acceptance_literals() -> None:
    """Acceptance sentences are quoted verbatim in the fragments below."""
    fragments = (
        "', expires_on=date(2026, 3, 10))], [Rule(id='",
        "')], today=date(2026, 3, 10)) returns a Status with state == '",
        "' and days_left == 0; with today=date(2026, 3, 11) state == '",
        "', warn_days=(30, 7)) and Rule(id='",
        "') with no expiry criterion, used=-1, or used=11 with usage_limit=10 "
        "raises ExpiryError with code == '",
        "'; a result of more than 100_000 reminders raises code == '",
    )
    assert len(fragments) == 6
    items = [Item(id="a", name="A", expires_on=date(2026, 3, 10))]
    rules = [Rule(id="r")]
    first = evaluate(items, rules, today=date(2026, 3, 10))[0]
    assert (first.state, first.days_left) == ("warning", 0)
    second = evaluate(items, rules, today=date(2026, 3, 11))[0]
    assert (second.state, second.days_left) == ("expired", -1)
    assert code_of(lambda: Item(id="a", name="A")) == "invalid_item"
    assert code_of(lambda: Item(id="a", name="A", usage_limit=10, used=11)) == "invalid_item"


def code_of(call: Callable[[], object]) -> str:
    with pytest.raises(ExpiryError) as info:
        call()
    return info.value.code


def unfold(text: str) -> list[str]:
    assert text.endswith("\r\n")
    lines: list[str] = []
    for physical in text[:-2].split("\r\n"):
        if physical.startswith(" "):
            lines[-1] += physical[1:]
        else:
            lines.append(physical)
    return lines


def uid_of(item_id: str, on: date, kind: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{item_id}|{on.isoformat()}|{kind}"))


def make_reminder(message: str = "A expires tomorrow") -> Reminder:
    return Reminder(item_id="a", on=date(2026, 3, 9), kind="date", message=message)


def export(message: str) -> str:
    return to_ical([make_reminder(message)], calendar_name="Expiry", dtstamp=STAMP)


# --- package metadata -------------------------------------------------------------------


def test_package_metadata_and_logging() -> None:
    assert expiry_engine.__version__ == "0.1.0"
    assert "to_ical" in expiry_engine.__all__
    handlers = logging.getLogger("expiry_engine").handlers
    assert any(isinstance(handler, logging.NullHandler) for handler in handlers)


def test_error_is_clipped_and_carries_code() -> None:
    error = ExpiryError("limit", "x" * 500)
    assert error.code == "limit"
    assert len(str(error)) == 200
    assert len(error.message) == 200


# --- items ------------------------------------------------------------------------------


def test_item_requires_a_criterion_and_consistent_usage() -> None:
    """Reject an item without a criterion or with inconsistent usage.

    Item(id='a', name='A') with no expiry criterion, used=-1, or used=11 with usage_limit=10
    raises ExpiryError with code == 'invalid_item'.
    """
    spec = "Item(id='a', name='A') with no expiry criterion, used=-1, or used=11 with usage_limit=10 raises ExpiryError with code == 'invalid_item'"  # noqa: E501
    assert code_of(lambda: Item(id="a", name="A")) == "invalid_item", spec
    assert code_of(lambda: Item(id="a", name="A", usage_limit=10, used=-1)) == "invalid_item"
    assert code_of(lambda: Item(id="a", name="A", usage_limit=10, used=11)) == "invalid_item"
    assert code_of(lambda: Item(id="a", name="A", expires_on=EXPIRES, used=-1)) == "invalid_item"


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": ""},
        {"id": "x" * 201},
        {"id": 5},
        {"name": " "},
        {"name": "n" * 501},
        {"expires_on": "2026-03-10"},
        {"expires_on": datetime(2026, 3, 10)},
        {"first_used_on": "2026-03-10"},
        {"usage_limit": 0},
        {"usage_limit": True},
        {"usage_limit": 1_000_000_001},
        {"used": -1},
        {"used": True},
        {"used": 1_000_000_001},
        {"valid_days_after_first_use": 0},
        {"valid_days_after_first_use": 36_501},
        {"tags": {"a"}},
        {"tags": frozenset({""})},
        {"tags": frozenset({"x" * 101})},
        {"tags": frozenset(str(i) for i in range(101))},
    ],
)
def test_item_rejects_invalid_fields(overrides: dict[str, object]) -> None:
    base: dict[str, object] = {"id": "a", "name": "A", "expires_on": EXPIRES}
    assert code_of(lambda: Item(**{**base, **overrides})) == "invalid_item"


def test_item_is_immutable() -> None:
    item = Item(id="a", name="A", usage_limit=3)
    with pytest.raises(FrozenInstanceError):
        item.used = 2


def test_effective_expiry_variants() -> None:
    assert Item(id="a", name="A", usage_limit=3).effective_expiry is None
    assert Item(id="a", name="A", expires_on=EXPIRES).effective_expiry == EXPIRES
    started = Item(
        id="a",
        name="A",
        expires_on=date(2028, 12, 31),
        valid_days_after_first_use=30,
        first_used_on=date(2028, 1, 30),
    )
    assert started.effective_expiry == date(2028, 2, 29)
    early = Item(
        id="a",
        name="A",
        expires_on=date(2026, 3, 5),
        valid_days_after_first_use=30,
        first_used_on=date(2026, 3, 1),
    )
    assert early.effective_expiry == date(2026, 3, 5)
    unstarted = Item(id="a", name="A", expires_on=EXPIRES, valid_days_after_first_use=30)
    assert unstarted.effective_expiry == EXPIRES


def test_effective_expiry_ignores_validity_beyond_date_max() -> None:
    only_validity = Item(id="a", name="A", valid_days_after_first_use=30, first_used_on=date.max)
    assert only_validity.effective_expiry is None
    with_date = Item(
        id="a",
        name="A",
        expires_on=EXPIRES,
        valid_days_after_first_use=30,
        first_used_on=date.max,
    )
    assert with_date.effective_expiry == EXPIRES


# --- rules ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"id": ""},
        {"warn_days": tuple(range(11))},
        {"warn_days": (-1,)},
        {"warn_days": (3661,)},
        {"warn_days": (True,)},
        {"warn_days": [7]},
        {"warn_remaining_uses": (1.5,)},
        {"warn_remaining_uses": tuple(range(11))},
        {"tags": {"a"}},
    ],
)
def test_rule_rejects_invalid_fields(kwargs: dict[str, object]) -> None:
    assert code_of(lambda: Rule(**{"id": "r", **kwargs})) == "invalid_rule"


def test_rule_accepts_boundaries() -> None:
    assert Rule(id="r", warn_days=tuple(range(10))).warn_days[-1] == 9
    assert Rule(id="r", warn_days=(0, 3660)).warn_days == (0, 3660)
    assert Rule(id="r").warn_days == (30, 7, 1)
    assert Rule(id="r").tags is None


# --- evaluate ---------------------------------------------------------------------------


def test_evaluate_warns_on_last_valid_day_and_expires_after() -> None:
    item = Item(id="a", name="A", expires_on=date(2026, 3, 10))
    [status] = evaluate([item], [Rule(id="r")], today=date(2026, 3, 10))
    assert isinstance(status, Status)
    assert status.item_id == "a"
    assert status.state == "warning"
    assert status.days_left == 0
    [late] = evaluate([item], [Rule(id="r")], today=date(2026, 3, 11))
    assert late.state == "expired"
    assert late.days_left == -1
    assert late.reasons


def test_evaluate_ok_and_warning_boundary() -> None:
    item = Item(id="a", name="A", expires_on=EXPIRES)
    [far] = evaluate([item], [Rule(id="r")], today=date(2026, 1, 1))
    assert far.state == "ok"
    assert far.days_left == 68
    assert far.reasons == ()
    [edge] = evaluate([item], [Rule(id="r")], today=date(2026, 2, 8))
    assert edge.days_left == 30
    assert edge.state == "warning"
    [outside] = evaluate([item], [Rule(id="r")], today=date(2026, 2, 7))
    assert outside.days_left == 31
    assert outside.state == "ok"
    [no_rules] = evaluate([item], [], today=TODAY)
    assert no_rules.state == "ok"


def test_item_with_all_uses_consumed_is_exhausted() -> None:
    item = Item(id="a", name="A", usage_limit=10, used=10)
    [status] = evaluate([item], [Rule(id="r")], today=TODAY)
    assert status.state == "exhausted"
    assert status.days_left is None
    assert status.uses_left == 0


def test_exhausted_wins_over_expired() -> None:
    item = Item(id="a", name="A", expires_on=date(2026, 3, 1), usage_limit=10, used=10)
    [status] = evaluate([item], [Rule(id="r")], today=TODAY)
    assert status.state == "exhausted"
    assert status.days_left == -9
    assert len(status.reasons) == 2


def test_evaluate_warns_on_remaining_uses() -> None:
    rules = [Rule(id="r", warn_days=(), warn_remaining_uses=(2,))]
    low = Item(id="a", name="A", usage_limit=10, used=8)
    plenty = Item(id="b", name="B", usage_limit=10, used=7)
    low_status, plenty_status = evaluate([low, plenty], rules, today=TODAY)
    assert low_status.state == "warning"
    assert low_status.uses_left == 2
    assert plenty_status.state == "ok"


def test_evaluate_uses_first_use_window() -> None:
    item = Item(
        id="a",
        name="A",
        expires_on=date(2026, 12, 31),
        valid_days_after_first_use=30,
        first_used_on=date(2026, 3, 1),
    )
    [status] = evaluate([item], [Rule(id="r", warn_days=(7,))], today=TODAY)
    assert status.days_left == 21
    assert status.state == "ok"


def test_evaluate_leap_day() -> None:
    item = Item(id="a", name="A", expires_on=date(2028, 2, 29))
    [before] = evaluate([item], [Rule(id="r")], today=date(2028, 2, 28))
    assert before.days_left == 1
    assert before.state == "warning"
    [after] = evaluate([item], [Rule(id="r")], today=date(2028, 3, 1))
    assert after.days_left == -1
    assert after.state == "expired"


def test_rules_filtered_by_tags() -> None:
    tagged = Item(id="t", name="T", expires_on=EXPIRES, tags=frozenset({"cert"}))
    plain = Item(id="p", name="P", expires_on=EXPIRES)
    rules = [Rule(id="r", warn_days=(30,), tags=frozenset({"cert"}))]
    tagged_status, plain_status = evaluate([tagged, plain], rules, today=TODAY)
    assert tagged_status.state == "warning"
    assert plain_status.state == "ok"
    nobody = [Rule(id="e", warn_days=(30,), tags=frozenset())]
    assert evaluate([tagged], nobody, today=TODAY)[0].state == "ok"


def test_evaluate_rejects_bad_input() -> None:
    item = Item(id="a", name="A", expires_on=EXPIRES)
    assert code_of(lambda: evaluate([item], [], today=datetime(2026, 3, 10))) == "invalid_rule"
    assert code_of(lambda: evaluate(["x"], [], today=TODAY)) == "invalid_item"  # type: ignore[list-item]
    assert code_of(lambda: evaluate([item], ["x"], today=TODAY)) == "invalid_rule"  # type: ignore[list-item]
    assert code_of(lambda: evaluate(repeat(item, 100_001), [], today=TODAY)) == "limit"
    assert code_of(lambda: evaluate([item], repeat(Rule(id="r"), 1_001), today=TODAY)) == "limit"


# --- record_use -------------------------------------------------------------------------


def test_record_use_rejects_exhausted_item_and_keeps_it_unchanged() -> None:
    item = Item(id="a", name="A", usage_limit=10, used=10)
    assert code_of(lambda: record_use(item, on=date(2026, 3, 11))) == "exhausted"
    assert item == Item(id="a", name="A", usage_limit=10, used=10)


def test_record_use_rejects_expired_item_and_keeps_it_unchanged() -> None:
    item = Item(id="a", name="A", expires_on=date(2026, 3, 10), usage_limit=10)
    assert code_of(lambda: record_use(item, on=date(2026, 3, 11))) == "expired"
    assert item == Item(id="a", name="A", expires_on=date(2026, 3, 10), usage_limit=10)
    assert record_use(item, on=date(2026, 3, 10)).used == 1


def test_exhausted_is_checked_before_expired() -> None:
    item = Item(id="a", name="A", expires_on=date(2026, 3, 10), usage_limit=1, used=1)
    assert code_of(lambda: record_use(item, on=date(2026, 4, 1))) == "exhausted"


def test_record_use_first_use_starts_validity_window() -> None:
    item = Item(id="a", name="A", expires_on=date(2026, 12, 31), valid_days_after_first_use=30)
    on = date(2026, 3, 1)
    used = record_use(item, on=on)
    assert used.used == 1
    assert used.first_used_on == on
    assert used.effective_expiry == min(item.expires_on, on + timedelta(days=30))
    assert item.used == 0
    assert item.first_used_on is None
    again = record_use(used, on=date(2026, 3, 5), count=2)
    assert again.used == 3
    assert again.first_used_on == on
    assert code_of(lambda: record_use(used, on=date(2026, 4, 1))) == "expired"


def test_record_use_limit_and_count_validation() -> None:
    item = Item(id="a", name="A", usage_limit=2)
    assert code_of(lambda: record_use(item, on=TODAY, count=3)) == "limit"
    assert record_use(item, on=TODAY, count=2).used == 2
    partial = Item(id="a", name="A", usage_limit=2, used=1)
    assert code_of(lambda: record_use(partial, on=TODAY, count=2)) == "limit"
    unlimited = Item(id="a", name="A", expires_on=date(2026, 12, 31))
    assert code_of(lambda: record_use(unlimited, on=TODAY, count=2_000_000_000)) == "limit"


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_record_use_rejects_bad_count(count: int) -> None:
    item = Item(id="a", name="A", usage_limit=5)
    assert code_of(lambda: record_use(item, on=TODAY, count=count)) == "invalid_item"


def test_record_use_rejects_bad_arguments() -> None:
    item = Item(id="a", name="A", usage_limit=5)
    assert code_of(lambda: record_use(item, on=datetime(2026, 3, 10))) == "invalid_item"
    assert code_of(lambda: record_use("x", on=TODAY)) == "invalid_item"  # type: ignore[arg-type]


# --- upcoming_reminders -----------------------------------------------------------------


def test_upcoming_reminders_merge_rules_without_duplicates() -> None:
    item = Item(id="a", name="A", expires_on=date(2026, 3, 10))
    rules = [Rule(id="r1", warn_days=(30, 7)), Rule(id="r2", warn_days=(7, 1))]
    result = upcoming_reminders([item], rules, today=date(2026, 2, 1), horizon_days=60)
    assert [r.on for r in result] == [date(2026, 2, 8), date(2026, 3, 3), date(2026, 3, 9)]
    assert all(r.kind == "date" and r.item_id == "a" for r in result)
    assert result == sorted(result, key=lambda r: (r.on, r.item_id, r.kind))
    assert [r.message for r in result] == [
        "A expires in 30 days",
        "A expires in 7 days",
        "A expires tomorrow",
    ]


def test_upcoming_reminders_window_is_inclusive_and_bounded() -> None:
    item = Item(id="a", name="A", expires_on=EXPIRES)
    rules = [Rule(id="r", warn_days=(30, 7, 1))]
    short = upcoming_reminders([item], rules, today=date(2026, 2, 1), horizon_days=7)
    assert [r.on for r in short] == [date(2026, 2, 8)]
    late = upcoming_reminders([item], rules, today=date(2026, 3, 4), horizon_days=60)
    assert [r.on for r in late] == [date(2026, 3, 9)]


def test_upcoming_reminders_horizon_zero_and_expiry_day() -> None:
    rules = [Rule(id="r", warn_days=(0,))]
    item = Item(id="a", name="A", expires_on=EXPIRES)
    [today_reminder] = upcoming_reminders([item], rules, today=EXPIRES, horizon_days=0)
    assert today_reminder.on == EXPIRES
    assert today_reminder.message == "A expires today"
    tomorrow = EXPIRES - timedelta(days=1)
    assert upcoming_reminders([item], rules, today=tomorrow, horizon_days=0) == []


def test_upcoming_reminders_sorted_by_date_then_item_id() -> None:
    first = Item(id="b", name="B", expires_on=EXPIRES)
    second = Item(id="a", name="A", expires_on=EXPIRES)
    rules = [Rule(id="r", warn_days=(0,))]
    result = upcoming_reminders([first, second], rules, today=TODAY, horizon_days=10)
    assert [r.item_id for r in result] == ["a", "b"]


def test_upcoming_reminders_respect_tags() -> None:
    tagged = Item(id="t", name="T", expires_on=EXPIRES, tags=frozenset({"cert"}))
    plain = Item(id="p", name="P", expires_on=EXPIRES)
    today = date(2026, 3, 5)
    rules = [Rule(id="r", warn_days=(1,), tags=frozenset({"cert"}))]
    result = upcoming_reminders([plain, tagged], rules, today=today, horizon_days=10)
    assert [r.item_id for r in result] == ["t"]
    nobody = [Rule(id="e", warn_days=(1,), tags=frozenset())]
    assert upcoming_reminders([tagged], nobody, today=today, horizon_days=10) == []


def test_usage_reminders_fall_on_today() -> None:
    item = Item(id="a", name="A", usage_limit=5, used=4)
    rules = [
        Rule(id="r", warn_days=(), warn_remaining_uses=(1,)),
        Rule(id="s", warn_days=(), warn_remaining_uses=(3,)),
    ]
    [reminder] = upcoming_reminders([item], rules, today=TODAY, horizon_days=0)
    expected = Reminder(item_id="a", on=TODAY, kind="usage", message="A has 1 use(s) left")
    assert reminder == expected
    fresh = Item(id="a", name="A", usage_limit=5, used=0)
    assert upcoming_reminders([fresh], rules, today=TODAY, horizon_days=5) == []
    spent = Item(id="a", name="A", usage_limit=5, used=5)
    [last] = upcoming_reminders([spent], rules, today=TODAY, horizon_days=5)
    assert last.message == "A has no uses left"
    no_thresholds = [Rule(id="r", warn_days=())]
    assert upcoming_reminders([item], no_thresholds, today=TODAY, horizon_days=5) == []
    unlimited = Item(id="u", name="U", expires_on=date(2030, 1, 1))
    assert upcoming_reminders([unlimited], rules, today=TODAY, horizon_days=5) == []


def test_upcoming_reminders_edge_dates() -> None:
    old = Item(id="a", name="A", expires_on=date.min)
    rules = [Rule(id="r", warn_days=(5,))]
    assert upcoming_reminders([old], rules, today=date.min, horizon_days=10) == []
    forever = Item(id="a", name="A", expires_on=date.max)
    zero = [Rule(id="r", warn_days=(0,))]
    [reminder] = upcoming_reminders([forever], zero, today=date.max, horizon_days=5)
    assert reminder.on == date.max


def test_upcoming_reminders_leap_day_expiry() -> None:
    item = Item(id="a", name="A", expires_on=date(2028, 2, 29))
    rules = [Rule(id="r", warn_days=(1,))]
    [reminder] = upcoming_reminders([item], rules, today=date(2028, 2, 1), horizon_days=60)
    assert reminder.on == date(2028, 2, 28)


def test_more_than_100000_reminders_raise_limit() -> None:
    rules = [Rule(id="r", warn_days=tuple(range(10)))]
    items = [Item(id=str(i), name="n", expires_on=EXPIRES) for i in range(10_001)]
    today = date(2026, 3, 1)
    assert (
        code_of(lambda: upcoming_reminders(items, rules, today=today, horizon_days=30)) == "limit"
    )


def test_upcoming_reminders_input_limits() -> None:
    item = Item(id="a", name="A", expires_on=EXPIRES)
    rules = [Rule(id="r")]
    for horizon in (-1, 3661, True, "5"):
        call = lambda h=horizon: upcoming_reminders([item], rules, today=TODAY, horizon_days=h)  # noqa: E731
        assert code_of(call) == "limit"
    assert upcoming_reminders([item], rules, today=TODAY, horizon_days=3660) == []
    bad_today = lambda: upcoming_reminders([item], rules, today="x", horizon_days=1)  # noqa: E731
    assert code_of(bad_today) == "invalid_rule"  # type: ignore[arg-type]
    many = lambda: upcoming_reminders(repeat(item, 100_001), rules, today=TODAY, horizon_days=1)  # noqa: E731
    assert code_of(many) == "limit"


# --- iCalendar --------------------------------------------------------------------------


def test_golden_calendar_matches_byte_for_byte() -> None:
    text = export("A expires tomorrow")
    uid = uid_of("a", date(2026, 3, 9), "date")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//trysac//expiry-engine//EN",
        "NAME:Expiry",
        "X-WR-CALNAME:Expiry",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        "DTSTAMP:20260101T000000Z",
        "DTSTART;VALUE=DATE:20260309",
        "DTEND;VALUE=DATE:20260310",
        "SUMMARY:A expires tomorrow",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    assert text == "".join(f"{line}\r\n" for line in lines)
    assert text.count("\r\n") == text.count("\n")
    required = [
        "DTSTAMP:20260101T000000Z",
        "DTSTART;VALUE=DATE:20260309",
        "DTEND;VALUE=DATE:20260310",
    ]
    for line in required:
        assert f"{line}\r\n" in text


def test_calendar_with_alarm() -> None:
    reminders = [make_reminder()]
    text = to_ical(reminders, calendar_name="Expiry", dtstamp=STAMP, alarm_minutes=15)
    alarm = [
        "SUMMARY:A expires tomorrow",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:A expires tomorrow",
        "TRIGGER:-PT15M",
        "END:VALARM",
        "END:VEVENT",
    ]
    assert "".join(f"{line}\r\n" for line in alarm) in text
    zero = to_ical(reminders, calendar_name="Expiry", dtstamp=STAMP, alarm_minutes=0)
    assert "TRIGGER:-PT0M\r\n" in zero


def test_empty_calendar_has_only_the_header() -> None:
    text = to_ical([], calendar_name="Expiry", dtstamp=STAMP)
    assert unfold(text) == [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//trysac//expiry-engine//EN",
        "NAME:Expiry",
        "X-WR-CALNAME:Expiry",
        "END:VCALENDAR",
    ]


def test_text_escaping() -> None:
    text = export("a,b;c\\d")
    assert "SUMMARY:a\\,b\\;c\\\\d\r\n" in text
    assert "SUMMARY:x\\nyz\r\n" in export("x\ny\rz")
    assert "SUMMARY:abc\r\n" in export("a\x00b\x7fc")
    assert "SUMMARY:\r\n" in export("")
    named = to_ical([], calendar_name="a,b;c", dtstamp=STAMP)
    assert "NAME:a\\,b\\;c\r\n" in named
    assert "X-WR-CALNAME:a\\,b\\;c\r\n" in named


def test_long_summary_folds_without_splitting_utf8() -> None:
    summary = "\u00e9" * 100
    text = export(summary)
    physical = text.split("\r\n")[:-1]
    assert all(len(line.encode("utf-8")) <= 75 for line in physical)
    assert "SUMMARY:" + summary in unfold(text)
    first = next(line for line in physical if line.startswith("SUMMARY:"))
    start = physical.index(first)
    assert [len(line.encode("utf-8")) for line in physical[start : start + 3]] == [74, 75, 61]
    assert physical[start + 1].startswith(" ")
    assert physical[start + 3] == "TRANSP:TRANSPARENT"
    assert "\ufffd" not in text


@pytest.mark.parametrize("char", ["\u20ac", "\U0001f600"])
def test_multibyte_characters_fold_cleanly(char: str) -> None:
    text = export(char * 60)
    physical = text.split("\r\n")[:-1]
    assert all(len(line.encode("utf-8")) <= 75 for line in physical)
    assert "SUMMARY:" + char * 60 in unfold(text)
    assert any(line.startswith(" ") for line in physical)


def test_line_of_exactly_75_octets_is_not_folded() -> None:
    exact = "SUMMARY:" + "x" * 67
    assert len(exact.encode("utf-8")) == 75
    text = export("x" * 67)
    physical = text.split("\r\n")
    assert exact in physical
    assert not any(line.startswith(" ") for line in physical)
    folded = export("x" * 68).split("\r\n")
    assert exact in folded
    assert " x" in folded


def test_long_calendar_name_is_folded() -> None:
    name = "n" * 200
    text = to_ical([], calendar_name=name, dtstamp=STAMP)
    assert "NAME:" + name in unfold(text)
    assert all(len(line) <= 75 for line in text.split("\r\n"))


def test_export_is_deterministic_and_uids_follow_the_formula() -> None:
    reminders = [
        make_reminder(),
        Reminder(item_id="b", on=date(2026, 4, 1), kind="usage", message="B has 1 use(s) left"),
    ]
    first = to_ical(reminders, calendar_name="Expiry", dtstamp=STAMP)
    second = to_ical(iter(reminders), calendar_name="Expiry", dtstamp=STAMP)
    assert first == second
    uids = [line[4:] for line in unfold(first) if line.startswith("UID:")]
    assert uids == [
        uid_of("a", date(2026, 3, 9), "date"),
        uid_of("b", date(2026, 4, 1), "usage"),
    ]


def test_dtstamp_is_converted_to_utc() -> None:
    offset = timezone(timedelta(hours=1))
    stamp = datetime(2026, 1, 1, 1, 0, 0, tzinfo=offset)
    text = to_ical([make_reminder()], calendar_name="Expiry", dtstamp=stamp)
    assert "DTSTAMP:20260101T000000Z\r\n" in text


def test_engine_output_exports_three_events() -> None:
    item = Item(id="a", name="A", expires_on=EXPIRES)
    reminders = upcoming_reminders([item], [Rule(id="r")], today=date(2026, 2, 1), horizon_days=60)
    text = to_ical(reminders, calendar_name="Expiry", dtstamp=STAMP)
    assert text.count("BEGIN:VEVENT\r\n") == 3


def test_to_ical_rejects_bad_arguments() -> None:
    one = [make_reminder()]
    naive = datetime(2026, 1, 1)
    assert code_of(lambda: to_ical(one, calendar_name="E", dtstamp=naive)) == "invalid_rule"
    assert code_of(lambda: to_ical(one, calendar_name="E", dtstamp=TODAY)) == "invalid_rule"  # type: ignore[arg-type]
    early = datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=5)))
    assert code_of(lambda: to_ical(one, calendar_name="E", dtstamp=early)) == "invalid_rule"
    assert code_of(lambda: to_ical(one, calendar_name="", dtstamp=STAMP)) == "invalid_rule"
    long_name = "n" * 501
    assert code_of(lambda: to_ical(one, calendar_name=long_name, dtstamp=STAMP)) == "invalid_rule"
    for alarm in (-1, True, 525_601, "5"):
        call = lambda a=alarm: to_ical(one, calendar_name="E", dtstamp=STAMP, alarm_minutes=a)  # noqa: E731
        assert code_of(call) == "invalid_rule"


def test_to_ical_rejects_bad_reminders() -> None:
    bad_kind = Reminder(item_id="a", on=TODAY, kind="other", message="m")  # type: ignore[arg-type]
    bad_date = Reminder(item_id="a", on=datetime(2026, 3, 9), kind="date", message="m")
    too_late = Reminder(item_id="a", on=date.max, kind="date", message="m")
    long_message = make_reminder("m" * 2_001)
    surrogate = make_reminder("\ud800")
    empty_id = Reminder(item_id="", on=TODAY, kind="date", message="m")
    for bad in (bad_kind, bad_date, too_late, long_message, surrogate, empty_id, "x"):
        call = lambda r=bad: to_ical([r], calendar_name="E", dtstamp=STAMP)  # type: ignore[misc]  # noqa: E731
        assert code_of(call) == "invalid_rule"


def test_more_than_100000_reminders_cannot_be_exported() -> None:
    reminders = repeat(make_reminder(), 100_001)
    assert code_of(lambda: to_ical(reminders, calendar_name="E", dtstamp=STAMP)) == "limit"
