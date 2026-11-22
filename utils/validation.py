"""Input validation. Every write path validates before touching the database."""
from __future__ import annotations

import re
from datetime import datetime

from config import PRIORITIES, TASK_STATUSES


class ValidationError(ValueError):
    """Raised when user input is invalid. The message is safe to show in the UI."""


_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def clean_text(value, field: str, *, min_len: int = 1, max_len: int = 120, required: bool = True) -> str:
    text = (value or "").strip() if isinstance(value, str) or value is None else str(value).strip()
    if not text and not required:
        return ""
    if len(text) < min_len:
        raise ValidationError(f"{field} can't be empty.")
    if len(text) > max_len:
        raise ValidationError(f"{field} must be {max_len} characters or fewer.")
    return text


def validate_minutes(value, field: str, *, minimum: float = 0, maximum: float = 1440, allow_none: bool = False):
    if value is None or value == "":
        if allow_none:
            return None
        raise ValidationError(f"{field} is required.")
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number.") from None
    if num != num or num in (float("inf"), float("-inf")):
        raise ValidationError(f"{field} must be a finite number.")
    if num < minimum or num > maximum:
        raise ValidationError(f"{field} must be between {minimum:g} and {maximum:g} minutes.")
    return num


def validate_color(value: str) -> str:
    if not isinstance(value, str) or not _HEX.match(value):
        raise ValidationError("Colour must be a hex value like #8B7CFF.")
    return value.upper()


def validate_hhmm(value: str, field: str) -> str:
    if not isinstance(value, str) or not _HHMM.match(value):
        raise ValidationError(f"{field} must be in HH:MM format.")
    return value


def validate_priority(value: str) -> str:
    if value not in PRIORITIES:
        raise ValidationError(f"Priority must be one of: {', '.join(PRIORITIES)}.")
    return value


def validate_status(value: str) -> str:
    if value not in TASK_STATUSES:
        raise ValidationError(f"Status must be one of: {', '.join(TASK_STATUSES)}.")
    return value


def validate_deadline(value, *, allow_none: bool = True):
    if value is None:
        if allow_none:
            return None
        raise ValidationError("Deadline is required.")
    if not isinstance(value, datetime):
        raise ValidationError("Deadline must be a valid date and time.")
    if value.year < 2000 or value.year > 2100:
        raise ValidationError("Deadline must be between the years 2000 and 2100.")
    return value
