"""Track expirations by date, usage count or time after first use.

Generate reminders from rules and export them as RFC 5545 iCalendar.
"""

from __future__ import annotations

import logging

from .errors import ExpiryError
from .ical import to_ical
from .model import (
    Item,
    Reminder,
    Rule,
    Status,
    evaluate,
    record_use,
    upcoming_reminders,
)

__all__ = [
    "ExpiryError",
    "Item",
    "Reminder",
    "Rule",
    "Status",
    "__version__",
    "evaluate",
    "record_use",
    "to_ical",
    "upcoming_reminders",
]

__version__ = "0.1.0"

logging.getLogger(__name__).addHandler(logging.NullHandler())
