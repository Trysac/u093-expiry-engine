# Usage and semantics

`expiry_engine` tracks expirations by date, usage count or time after first use, generates
reminders from rules and exports them as RFC 5545 iCalendar. It has no runtime dependencies
and no I/O; clocks are injected (`today`, `dtstamp`), so every function is deterministic.

## Public API

| Name | Purpose |
|---|---|
| `Item` | Frozen, validated item. `effective_expiry` is the earlier of `expires_on` and `first_used_on + valid_days_after_first_use`. |
| `Rule` | Frozen reminder rule: `warn_days`, `warn_remaining_uses`, optional `tags` filter. |
| `evaluate(items, rules, *, today)` | One `Status` per item. |
| `upcoming_reminders(items, rules, *, today, horizon_days)` | Sorted, de-duplicated `Reminder` list. |
| `record_use(item, *, on, count=1)` | New `Item` with the use recorded; the input is never changed. |
| `to_ical(reminders, *, calendar_name, dtstamp, alarm_minutes=None)` | Deterministic RFC 5545 text. |
| `ExpiryError` | Base error with `code`: `invalid_item`, `invalid_rule`, `exhausted`, `expired`, `limit`. |

## Semantics

- `expires_on` is the last valid day; `days_left = (effective_expiry - today).days`.
- State is `exhausted` when no uses are left (wins over `expired`), `expired` when `days_left`
  is negative, `warning` when `days_left` is at or below the largest matching `warn_days` or the
  remaining uses are at or below the largest matching `warn_remaining_uses`, otherwise `ok`.
- A rule with `tags=None` applies to every item; otherwise it applies to items sharing at least
  one tag (an empty tag set matches nothing).
- Date reminders fall on `effective_expiry - offset`, are kept only within
  `today .. today + horizon_days` and are unique by `(item_id, on, kind)`. Items that are already
  exhausted still receive date reminders inside the window.
- Usage reminders fall on `today` when the remaining uses are at or below a matching threshold
  (including zero remaining uses).
- `record_use` checks, in order: `count >= 1` (`invalid_item`), exhausted, expired (`on` after the
  effective expiry), then `used + count > usage_limit` (`limit`). `exhausted` and `expired` are
  terminal. The first use sets `first_used_on`.

## Limits

| Limit | Value | Error code |
|---|---|---|
| Items per call | 100,000 | `limit` |
| Rules per call | 1,000 | `limit` |
| Reminders per call or export | 100,000 | `limit` |
| `horizon_days` | 0 to 3660 | `limit` |
| Offsets per rule, each offset | at most 10, each 0 to 3660 | `invalid_rule` |
| Identifier / name / tag length | 200 / 500 / 100 characters; at most 100 tags | `invalid_item`, `invalid_rule` |
| Reminder message / calendar name | 2,000 / 500 characters | `invalid_rule` |
| `alarm_minutes` | 0 to 525,600 | `invalid_rule` |

Invalid call arguments (non-date `today`, naive `dtstamp`, malformed reminders) also use
`invalid_rule`. Error messages never exceed 200 characters and never echo untrusted input.

## iCalendar output

- CRLF line endings; content lines longer than 75 octets are folded with CRLF plus one space
  without splitting a UTF-8 sequence (RFC 5545 section 3.1).
- TEXT values escape backslash, semicolon, comma and newline (section 3.3.11). CR and other
  control characters (except tab) are removed so a value can never inject a content line.
- Property order is fixed. Calendar: `BEGIN:VCALENDAR`, `VERSION:2.0`,
  `PRODID:-//trysac//expiry-engine//EN`, `NAME`, `X-WR-CALNAME`, events, `END:VCALENDAR`.
  Event: `BEGIN:VEVENT`, `UID`, `DTSTAMP`, `DTSTART;VALUE=DATE`, `DTEND;VALUE=DATE` (next day,
  exclusive), `SUMMARY`, `TRANSP:TRANSPARENT`, optional `VALARM` (`ACTION:DISPLAY`,
  `DESCRIPTION`, `TRIGGER:-PTnM`), `END:VEVENT`.
- `UID` is `str(uuid.uuid5(NAMESPACE, f"{item_id}|{on.isoformat()}|{kind}"))` where
  `NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "expiry-engine.invalid")`; no host name is embedded
  (RFC 7986 section 5.3).
- `dtstamp` must be timezone-aware and is written in UTC (`YYYYMMDDTHHMMSSZ`). Events keep the
  order of the input reminders.

## Out of scope

Persistence, notifications, recurrence rules, time zones (dates only) and parsing `.ics` files.
Compared with the `ics` and `icalendar` packages, this library adds expiry rules and a
deterministic export.
