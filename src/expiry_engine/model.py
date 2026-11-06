"""Expiry items, rules, evaluation, reminders and usage recording."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from itertools import islice
from typing import Literal, TypeGuard

from .errors import ErrorCode, ExpiryError

logger = logging.getLogger(__name__)

State = Literal["ok", "warning", "expired", "exhausted"]
ReminderKind = Literal["date", "usage"]

MAX_ITEMS = 100_000
MAX_RULES = 1_000
MAX_REMINDERS = 100_000
MAX_HORIZON_DAYS = 3660
MAX_OFFSETS = 10
MAX_OFFSET_DAYS = 3660
MAX_ID_LENGTH = 200
MAX_NAME_LENGTH = 500
MAX_TAGS = 100
MAX_TAG_LENGTH = 100
MAX_VALID_DAYS = 36_500
MAX_USED = 1_000_000_000


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_date(value: object) -> TypeGuard[date]:
    return isinstance(value, date) and not isinstance(value, datetime)


def _check_text(value: object, name: str, limit: int, code: ErrorCode) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ExpiryError(code, f"{name} must be non-empty text of at most {limit} chars")


def _check_optional_date(value: object, name: str) -> None:
    if value is not None and not _is_date(value):
        raise ExpiryError("invalid_item", f"{name} must be a date")


def _check_optional_int(value: object, name: str, low: int, high: int) -> None:
    if value is None:
        return
    if not _is_int(value) or not low <= value <= high:
        raise ExpiryError("invalid_item", f"{name} must be an integer from {low} to {high}")


def _check_tags(tags: object, code: ErrorCode) -> None:
    if (
        not isinstance(tags, frozenset)
        or len(tags) > MAX_TAGS
        or any(not isinstance(tag, str) or not tag or len(tag) > MAX_TAG_LENGTH for tag in tags)
    ):
        raise ExpiryError(code, f"tags must be at most {MAX_TAGS} short non-empty strings")


def _check_offsets(values: object, name: str) -> None:
    if (
        not isinstance(values, tuple)
        or len(values) > MAX_OFFSETS
        or any(not _is_int(v) or not 0 <= v <= MAX_OFFSET_DAYS for v in values)
    ):
        raise ExpiryError("invalid_rule", f"{name} must be a tuple of valid day offsets")


@dataclass(frozen=True)
class Item:
    """A tracked item that can expire by date, usage count or time after first use.

    ``expires_on`` is the last valid day. Validation happens in ``__post_init__`` and raises
    :class:`ExpiryError` with code ``invalid_item``.
    """

    id: str
    name: str
    expires_on: date | None = None
    usage_limit: int | None = None
    used: int = 0
    valid_days_after_first_use: int | None = None
    first_used_on: date | None = None
    tags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _check_text(self.id, "id", MAX_ID_LENGTH, "invalid_item")
        _check_text(self.name, "name", MAX_NAME_LENGTH, "invalid_item")
        _check_optional_date(self.expires_on, "expires_on")
        _check_optional_date(self.first_used_on, "first_used_on")
        _check_optional_int(self.usage_limit, "usage_limit", 1, MAX_USED)
        _check_optional_int(
            self.valid_days_after_first_use,
            "valid_days_after_first_use",
            1,
            MAX_VALID_DAYS,
        )
        if not _is_int(self.used) or not 0 <= self.used <= MAX_USED:
            raise ExpiryError("invalid_item", f"used must be an integer from 0 to {MAX_USED}")
        if self.usage_limit is not None and self.used > self.usage_limit:
            raise ExpiryError("invalid_item", "used must not exceed usage_limit")
        _check_tags(self.tags, "invalid_item")
        criteria = (self.expires_on, self.usage_limit, self.valid_days_after_first_use)
        if all(criterion is None for criterion in criteria):
            raise ExpiryError("invalid_item", "item needs a date, usage or validity criterion")

    @property
    def effective_expiry(self) -> date | None:
        """The earlier of ``expires_on`` and first use plus the validity period, if any."""
        candidates: list[date] = []
        if self.expires_on is not None:
            candidates.append(self.expires_on)
        first, days = self.first_used_on, self.valid_days_after_first_use
        if first is not None and days is not None:
            with suppress(OverflowError):
                candidates.append(first + timedelta(days=days))
        return min(candidates) if candidates else None


@dataclass(frozen=True)
class Rule:
    """A reminder rule.

    ``warn_days`` are day offsets before expiry, ``warn_remaining_uses`` are remaining-use
    thresholds. ``tags=None`` applies the rule to every item, otherwise to items sharing at
    least one tag. Violations raise :class:`ExpiryError` with code ``invalid_rule``.
    """

    id: str
    warn_days: tuple[int, ...] = (30, 7, 1)
    warn_remaining_uses: tuple[int, ...] = ()
    tags: frozenset[str] | None = None

    def __post_init__(self) -> None:
        _check_text(self.id, "id", MAX_ID_LENGTH, "invalid_rule")
        _check_offsets(self.warn_days, "warn_days")
        _check_offsets(self.warn_remaining_uses, "warn_remaining_uses")
        if self.tags is not None:
            _check_tags(self.tags, "invalid_rule")


@dataclass(frozen=True)
class Status:
    """The evaluated state of one item."""

    item_id: str
    state: State
    days_left: int | None
    uses_left: int | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Reminder:
    """A reminder that falls on a calendar day."""

    item_id: str
    on: date
    kind: ReminderKind
    message: str


def _load_items(items: Iterable[Item]) -> list[Item]:
    loaded = list(islice(items, MAX_ITEMS + 1))
    if len(loaded) > MAX_ITEMS:
        raise ExpiryError("limit", f"at most {MAX_ITEMS} items are accepted")
    if not all(isinstance(item, Item) for item in loaded):
        raise ExpiryError("invalid_item", "items must be Item instances")
    return loaded


def _load_rules(rules: Iterable[Rule]) -> tuple[Rule, ...]:
    loaded = tuple(islice(rules, MAX_RULES + 1))
    if len(loaded) > MAX_RULES:
        raise ExpiryError("limit", f"at most {MAX_RULES} rules are accepted")
    if not all(isinstance(rule, Rule) for rule in loaded):
        raise ExpiryError("invalid_rule", "rules must be Rule instances")
    return loaded


def _check_today(today: object) -> None:
    if not _is_date(today):
        raise ExpiryError("invalid_rule", "today must be a date")


def _applies(rule: Rule, item: Item) -> bool:
    return rule.tags is None or bool(rule.tags & item.tags)


def _status(item: Item, rules: tuple[Rule, ...], today: date) -> Status:
    matching = [rule for rule in rules if _applies(rule, item)]
    expiry = item.effective_expiry
    days_left = (expiry - today).days if expiry is not None else None
    uses_left = item.usage_limit - item.used if item.usage_limit is not None else None
    day_limit = max((d for rule in matching for d in rule.warn_days), default=None)
    use_limit = max((n for rule in matching for n in rule.warn_remaining_uses), default=None)
    reasons: list[str] = []
    exhausted = uses_left is not None and uses_left <= 0
    if exhausted:
        reasons.append("usage limit reached")
    if days_left is not None and days_left < 0:
        reasons.append(f"expired {-days_left} day(s) ago")
    state: State
    if reasons:
        state = "exhausted" if exhausted else "expired"
    else:
        if days_left is not None and day_limit is not None and days_left <= day_limit:
            reasons.append(f"expires in {days_left} day(s)")
        if uses_left is not None and use_limit is not None and uses_left <= use_limit:
            reasons.append(f"{uses_left} use(s) left")
        state = "warning" if reasons else "ok"
    return Status(item.id, state, days_left, uses_left, tuple(reasons))


def evaluate(items: Iterable[Item], rules: Iterable[Rule], *, today: date) -> list[Status]:
    """Evaluate every item against the rules and return one :class:`Status` per item.

    ``days_left`` is ``(effective_expiry - today).days``. The state is ``exhausted`` when no
    uses are left (this wins over ``expired``), ``expired`` when ``days_left`` is negative,
    ``warning`` when ``days_left`` is at or below the largest matching ``warn_days`` or the
    remaining uses are at or below the largest matching ``warn_remaining_uses``, else ``ok``.

    Raises:
        ExpiryError: ``limit`` for more than 100_000 items, ``invalid_item`` or
            ``invalid_rule`` for malformed input.
    """
    _check_today(today)
    loaded_items = _load_items(items)
    loaded_rules = _load_rules(rules)
    statuses = [_status(item, loaded_rules, today) for item in loaded_items]
    logger.debug("evaluated %d items", len(statuses))
    return statuses


def _date_message(name: str, offset: int) -> str:
    if offset == 0:
        return f"{name} expires today"
    if offset == 1:
        return f"{name} expires tomorrow"
    return f"{name} expires in {offset} days"


def _usage_message(name: str, uses_left: int) -> str:
    if uses_left <= 0:
        return f"{name} has no uses left"
    return f"{name} has {uses_left} use(s) left"


def _add_date_reminders(
    found: dict[tuple[str, date, str], Reminder],
    item: Item,
    matching: list[Rule],
    today: date,
    last: date,
) -> None:
    expiry = item.effective_expiry
    if expiry is None:
        return
    offsets = {offset for rule in matching for offset in rule.warn_days}
    for offset in sorted(offsets):
        try:
            on = expiry - timedelta(days=offset)
        except OverflowError:
            continue
        key = (item.id, on, "date")
        if today <= on <= last and key not in found:
            message = _date_message(item.name, offset)
            found[key] = Reminder(item.id, on, "date", message)


def _add_usage_reminder(
    found: dict[tuple[str, date, str], Reminder],
    item: Item,
    matching: list[Rule],
    today: date,
) -> None:
    if item.usage_limit is None:
        return
    threshold = max((n for rule in matching for n in rule.warn_remaining_uses), default=None)
    uses_left = item.usage_limit - item.used
    if threshold is None or uses_left > threshold:
        return
    key = (item.id, today, "usage")
    if key not in found:
        found[key] = Reminder(item.id, today, "usage", _usage_message(item.name, uses_left))


def upcoming_reminders(
    items: Iterable[Item],
    rules: Iterable[Rule],
    *,
    today: date,
    horizon_days: int,
) -> list[Reminder]:
    """Generate reminders from ``today`` up to ``today + horizon_days``.

    Date reminders fall on ``effective_expiry - offset`` for each matching ``warn_days``
    offset and are kept only inside the window. Usage reminders fall on ``today`` when the
    remaining uses are at or below a matching ``warn_remaining_uses`` threshold. Reminders
    are unique by ``(item_id, on, kind)`` and sorted by ``(on, item_id, kind)``.

    Raises:
        ExpiryError: ``limit`` when ``horizon_days`` is outside 0..3660, for more than
            100_000 items or more than 100_000 reminders.
    """
    _check_today(today)
    if not _is_int(horizon_days) or not 0 <= horizon_days <= MAX_HORIZON_DAYS:
        raise ExpiryError("limit", f"horizon_days must be between 0 and {MAX_HORIZON_DAYS}")
    loaded_items = _load_items(items)
    loaded_rules = _load_rules(rules)
    try:
        last = today + timedelta(days=horizon_days)
    except OverflowError:
        last = date.max
    found: dict[tuple[str, date, str], Reminder] = {}
    for item in loaded_items:
        matching = [rule for rule in loaded_rules if _applies(rule, item)]
        _add_date_reminders(found, item, matching, today, last)
        _add_usage_reminder(found, item, matching, today)
        if len(found) > MAX_REMINDERS:
            raise ExpiryError("limit", f"more than {MAX_REMINDERS} reminders")
    logger.debug("generated %d reminders", len(found))
    return sorted(found.values(), key=lambda r: (r.on, r.item_id, r.kind))


def record_use(item: Item, *, on: date, count: int = 1) -> Item:
    """Return a new item with ``count`` more uses recorded on day ``on``.

    The input item is never changed. Checks run in this order: ``count >= 1``
    (``invalid_item``), exhausted (``exhausted``), expired because ``on`` is after the
    effective expiry (``expired``), and ``used + count`` above the usage limit (``limit``).
    The first use sets ``first_used_on``.
    """
    if not isinstance(item, Item):
        raise ExpiryError("invalid_item", "item must be an Item")
    if not _is_int(count) or count < 1:
        raise ExpiryError("invalid_item", "count must be an integer >= 1")
    if not _is_date(on):
        raise ExpiryError("invalid_item", "on must be a date")
    if item.usage_limit is not None and item.used >= item.usage_limit:
        raise ExpiryError("exhausted", "item has no uses left")
    expiry = item.effective_expiry
    if expiry is not None and on > expiry:
        raise ExpiryError("expired", "item expired before the use date")
    new_used = item.used + count
    limit = item.usage_limit if item.usage_limit is not None else MAX_USED
    if new_used > limit:
        raise ExpiryError("limit", "use count exceeds the usage limit")
    first = item.first_used_on if item.first_used_on is not None else on
    return replace(item, used=new_used, first_used_on=first)
