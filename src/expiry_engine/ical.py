"""RFC 5545 iCalendar export of reminders."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from itertools import islice

from .errors import ExpiryError
from .model import MAX_ID_LENGTH, MAX_REMINDERS, Reminder

logger = logging.getLogger(__name__)

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "expiry-engine.invalid")
PRODID = "-//trysac//expiry-engine//EN"
MAX_LINE_OCTETS = 75
MAX_MESSAGE_LENGTH = 2_000
MAX_CALENDAR_NAME_LENGTH = 500
MAX_ALARM_MINUTES = 525_600

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_ESCAPES = {ord("\\"): "\\\\", ord(";"): "\\;", ord(","): "\\,", ord("\n"): "\\n"}


def _text(value: object, name: str, limit: int, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (not value and not allow_empty):
        raise ExpiryError("invalid_rule", f"{name} must be text of at most {limit} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ExpiryError("invalid_rule", f"{name} is not valid unicode text") from exc
    return value


def _escape_text(value: str) -> str:
    """Escape a TEXT value (RFC 5545 3.3.11); control characters including CR are removed."""
    return _CONTROL.sub("", value).translate(_ESCAPES)


def _fold(line: str) -> str:
    """Fold a content line at 75 octets without splitting a UTF-8 sequence (RFC 5545 3.1)."""
    parts: list[str] = []
    current: list[str] = []
    size = 0
    budget = MAX_LINE_OCTETS
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > budget:
            parts.append("".join(current))
            current = []
            size = 0
            budget = MAX_LINE_OCTETS - 1
        current.append(char)
        size += width
    parts.append("".join(current))
    return "\r\n ".join(parts)


def _date_value(value: date) -> str:
    return f"{value.year:04d}{value.month:02d}{value.day:02d}"


def _format_stamp(dtstamp: datetime) -> str:
    if not isinstance(dtstamp, datetime) or dtstamp.tzinfo is None or dtstamp.utcoffset() is None:
        raise ExpiryError("invalid_rule", "dtstamp must be a timezone-aware datetime")
    try:
        utc = dtstamp.astimezone(timezone.utc)
    except OverflowError as exc:
        raise ExpiryError("invalid_rule", "dtstamp is out of range") from exc
    day = _date_value(utc.date())
    return f"{day}T{utc.hour:02d}{utc.minute:02d}{utc.second:02d}Z"


def _check_alarm(alarm_minutes: int | None) -> None:
    if alarm_minutes is None:
        return
    if (
        isinstance(alarm_minutes, bool)
        or not isinstance(alarm_minutes, int)
        or not 0 <= alarm_minutes <= MAX_ALARM_MINUTES
    ):
        raise ExpiryError("invalid_rule", f"alarm_minutes must be 0..{MAX_ALARM_MINUTES}")


def _event_lines(reminder: Reminder, stamp: str, alarm_minutes: int | None) -> list[str]:
    if not isinstance(reminder, Reminder) or reminder.kind not in ("date", "usage"):
        raise ExpiryError("invalid_rule", "reminders must be valid Reminder instances")
    on = reminder.on
    if not isinstance(on, date) or isinstance(on, datetime):
        raise ExpiryError("invalid_rule", "reminder date must be a date")
    item_id = _text(reminder.item_id, "item_id", MAX_ID_LENGTH)
    message = _text(reminder.message, "message", MAX_MESSAGE_LENGTH, allow_empty=True)
    try:
        end = on + timedelta(days=1)
    except OverflowError as exc:
        raise ExpiryError("invalid_rule", "reminder date is out of range") from exc
    summary = _escape_text(message)
    uid = str(uuid.uuid5(NAMESPACE, f"{item_id}|{on.isoformat()}|{reminder.kind}"))
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{_date_value(on)}",
        f"DTEND;VALUE=DATE:{_date_value(end)}",
        f"SUMMARY:{summary}",
        "TRANSP:TRANSPARENT",
    ]
    if alarm_minutes is not None:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{summary}",
            f"TRIGGER:-PT{alarm_minutes}M",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def to_ical(
    reminders: Iterable[Reminder],
    *,
    calendar_name: str,
    dtstamp: datetime,
    alarm_minutes: int | None = None,
) -> str:
    """Export reminders as an RFC 5545 iCalendar document.

    Output uses CRLF line endings, folds lines longer than 75 octets and escapes TEXT values.
    Events keep the input order, UIDs are derived deterministically (UUID version 5) and
    ``dtstamp`` is injected, so the same input always yields the same text.

    Raises:
        ExpiryError: ``invalid_rule`` for a naive ``dtstamp``, bad names, alarms or reminders;
            ``limit`` for more than 100_000 reminders.
    """
    stamp = _format_stamp(dtstamp)
    name = _escape_text(_text(calendar_name, "calendar_name", MAX_CALENDAR_NAME_LENGTH))
    _check_alarm(alarm_minutes)
    events = list(islice(reminders, MAX_REMINDERS + 1))
    if len(events) > MAX_REMINDERS:
        raise ExpiryError("limit", f"at most {MAX_REMINDERS} reminders can be exported")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        f"NAME:{name}",
        f"X-WR-CALNAME:{name}",
    ]
    for reminder in events:
        lines.extend(_event_lines(reminder, stamp, alarm_minutes))
    lines.append("END:VCALENDAR")
    logger.debug("exported %d reminders", len(events))
    return "".join(_fold(line) + "\r\n" for line in lines)
