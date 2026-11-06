# Architecture

## Purpose

`trysac-expiry-engine` is a small, dependency-free Python library (import name `expiry_engine`) that tracks expirations by date, usage count or time after first use, generates reminders from rules and exports them as RFC 5545 iCalendar.

## Shape

```text
caller code --> expiry_engine (public API in __init__.py)
                    |
                    +-- errors.py   ExpiryError with stable codes
                    +-- model.py    Item, Rule, Status, Reminder, evaluate,
                    |               upcoming_reminders, record_use
                    +-- ical.py     to_ical (RFC 5545 export)
```

- **Public API**: the six names listed in `__all__` of `src/expiry_engine/__init__.py`, plus `ExpiryError`, `Item`, `Reminder`, `Rule`, `Status`, `__version__`. Other names are internal.
- **Errors**: invalid input raises `ExpiryError` with a `code`; the library does not print or exit.
- **Side effects**: none beyond a `logging` debug message through a `NullHandler` logger.
- **Pure functions**: all operations take their clock (`today`, `dtstamp`) as arguments.

## Decisions

No ADR directory exists in the repository at this time.
