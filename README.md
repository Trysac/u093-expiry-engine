# expiry-engine

[![PyPI version](https://img.shields.io/pypi/v/trysac-expiry-engine)](https://pypi.org/project/trysac-expiry-engine/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-expiry-engine)](LICENSE)
[![CI](https://github.com/Trysac/u093-expiry-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u093-expiry-engine/actions/workflows/ci.yml)

Track expirations by date, usage count or time after first use, generate reminders from rules and export them as RFC 5545 iCalendar.

## Problem

Teams track expiring items such as certifications, licences, warranties or consumables in spreadsheets, and reminders are missed because expiry can depend on a date, a usage count or time after first use. Calendar libraries write `.ics` files but know nothing about expiry rules. This small deterministic engine computes state and reminders and exports a calendar that follows RFC 5545.

## Install

```sh
pip install trysac-expiry-engine
# or
uv add trysac-expiry-engine
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
from datetime import date, datetime, timezone
from expiry_engine import Item, Rule, to_ical, upcoming_reminders

item = Item(id="cert", name="Certificate", expires_on=date(2026, 3, 10))
reminders = upcoming_reminders([item], [Rule(id="r")], today=date(2026, 2, 1), horizon_days=60)
stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
print(to_ical(reminders, calendar_name="Expiry", dtstamp=stamp))
```

## Public API

- `Item(id, name, expires_on=None, usage_limit=None, used=0, valid_days_after_first_use=None, first_used_on=None, tags=frozenset())`: frozen dataclass validated on creation; `expires_on` is the last valid day. At least one of `expires_on`, `usage_limit` or `valid_days_after_first_use` is required. Property `effective_expiry` returns the earlier of `expires_on` and first use plus the validity period.
- `Rule(id, warn_days=(30, 7, 1), warn_remaining_uses=(), tags=None)`: `tags=None` applies to every item, otherwise to items sharing at least one tag.
- `evaluate(items, rules, *, today) -> list[Status]`: `Status` has `item_id`, `state` (`ok`, `warning`, `expired`, `exhausted`), `days_left`, `uses_left` and `reasons`. `exhausted` wins over `expired`.
- `upcoming_reminders(items, rules, *, today, horizon_days) -> list[Reminder]`: `Reminder` has `item_id`, `on`, `kind` (`date` or `usage`) and `message`. Results are unique by `(item_id, on, kind)` and sorted by `(on, item_id, kind)`.
- `record_use(item, *, on, count=1) -> Item`: returns a new item; the input is never changed.
- `to_ical(reminders, *, calendar_name, dtstamp, alarm_minutes=None) -> str`: RFC 5545 text with CRLF line endings. `dtstamp` must be timezone-aware.
- `ExpiryError` with a `code`: `invalid_item`, `invalid_rule`, `exhausted`, `expired` or `limit`. Messages are clipped to 200 characters.

Limits: at most 100,000 items, 1,000 rules and 100,000 reminders; horizon 0 to 3660 days; at most 10 offsets per rule, each 0 to 3660 days; text fields have fixed maximum lengths; iCalendar alarms up to 525,600 minutes. Dates only: there is no time-zone handling beyond the UTC `dtstamp`.

Output is deterministic: `today` and `dtstamp` are injected and UIDs are derived with UUID version 5.

## Why not icalendar?

The `icalendar` package writes and parses `.ics` files but has no notion of expiry rules, usage counts or reminder generation. This library adds those rules and a deterministic export on top of a minimal iCalendar writer.

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for the threat model and limits.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
