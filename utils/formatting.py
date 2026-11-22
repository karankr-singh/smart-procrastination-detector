"""Formatting helpers used across the UI and reports."""
from __future__ import annotations

import html
from datetime import datetime


def fmt_minutes(minutes) -> str:
    """90 -> '1h 30m', 0.5 -> '30s', None -> '–'."""
    if minutes is None or minutes != minutes:
        return "–"
    total_seconds = int(round(float(minutes) * 60))
    if total_seconds < 60:
        return f"{total_seconds}s"
    mins = total_seconds // 60
    hours, rem = divmod(mins, 60)
    if hours and rem:
        return f"{hours}h {rem}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def fmt_clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def fmt_pct(value, digits: int = 0) -> str:
    if value is None or value != value:
        return "–"
    return f"{value * 100:.{digits}f}%"


def fmt_dt(value, pattern: str = "%d %b, %H:%M") -> str:
    if value is None or value != value:
        return "–"
    if isinstance(value, datetime):
        return value.strftime(pattern)
    return str(value)


def esc(text) -> str:
    """HTML-escape user-provided text before placing it in unsafe_allow_html blocks."""
    return html.escape("" if text is None else str(text))
