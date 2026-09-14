"""Human-readable phrasing for dates and counts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def due_phrase(due: Optional[date], today: Optional[date] = None) -> str:
    """A short phrase for how far away a due date is.

    Examples: ``"overdue by 3 days"``, ``"due today"``, ``"due tomorrow"``,
    ``"in 5 days"``, ``"in 3 weeks"``.
    """
    if due is None:
        return "no due date"
    days = (due - (today or date.today())).days
    if days < 0:
        n = -days
        if n == 1:
            return "overdue by 1 day"
        if n < 14:
            return f"overdue by {n} days"
        if n < 60:
            return f"overdue by {round(n / 7)} weeks"
        return f"overdue by {round(n / 30)} months"
    if days == 0:
        return "due today"
    if days == 1:
        return "due tomorrow"
    if days < 14:
        return f"in {days} days"
    if days < 60:
        return f"in {round(days / 7)} weeks"
    return f"in {round(days / 30)} months"


def short_date(value: Optional[date]) -> str:
    """``Sep 20`` for dates this year, ``Sep 20 2027`` otherwise."""
    if value is None:
        return ""
    if value.year == date.today().year:
        return value.strftime("%b %-d") if _supports_dash() else value.strftime("%b %d").replace(" 0", " ")
    return value.strftime("%b %d %Y").replace(" 0", " ")


def _supports_dash() -> bool:
    """glibc supports ``%-d``; Windows' CRT does not."""
    try:
        date(2020, 1, 5).strftime("%-d")
        return True
    except ValueError:
        return False


def stamp(value: Optional[datetime]) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def plural(count: int, singular: str, plural_form: Optional[str] = None) -> str:
    word = singular if count == 1 else (plural_form or singular + "s")
    return f"{count} {word}"
