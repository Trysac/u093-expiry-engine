"""Typed errors raised by the expiry engine."""

from __future__ import annotations

from typing import Literal

__all__ = ["ErrorCode", "ExpiryError"]

ErrorCode = Literal["invalid_item", "invalid_rule", "exhausted", "expired", "limit"]

MAX_MESSAGE_LENGTH = 200


class ExpiryError(Exception):
    """Base error of the library, carrying a stable machine-readable ``code``.

    Messages never contain secrets and are clipped to 200 characters.
    """

    def __init__(self, code: ErrorCode, message: str) -> None:
        clipped = message[:MAX_MESSAGE_LENGTH]
        super().__init__(clipped)
        self.code: ErrorCode = code
        self.message = clipped
