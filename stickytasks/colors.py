"""Mapping a due date onto a background colour.

The rule is a list of bands, each with an upper bound in days-until-due.  A task
falls into the first band whose ``max_days`` it does not exceed; the final band
has ``max_days = None`` and catches everything further out.  With the defaults
that means overdue tasks are deep red and tasks more than two weeks out are
green, with a ramp in between.

Bands are data, not code, so the settings screen can edit them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence


def normalize_hex(value: str) -> str:
    """Return ``value`` as ``#rrggbb``, falling back to grey if unparseable."""
    v = (value or "").strip()
    if not v.startswith("#"):
        v = "#" + v
    body = v[1:]
    if len(body) == 3 and all(c in "0123456789abcdefABCDEF" for c in body):
        body = "".join(c * 2 for c in body)
    if len(body) != 6 or not all(c in "0123456789abcdefABCDEF" for c in body):
        return "#9E9E9E".lower()
    return "#" + body.lower()


@dataclass
class Band:
    """One colour band.

    ``max_days`` is the largest number of days-until-due that still lands in
    this band.  ``None`` means "no upper bound" and must be the last band.
    """

    label: str
    max_days: Optional[int]
    color: str

    def __post_init__(self) -> None:
        self.color = normalize_hex(self.color)

    def to_dict(self) -> dict:
        return {"label": self.label, "max_days": self.max_days, "color": self.color}

    @classmethod
    def from_dict(cls, data: dict) -> "Band":
        raw = data.get("max_days")
        return cls(
            label=str(data.get("label", "")),
            max_days=None if raw is None else int(raw),
            color=normalize_hex(str(data.get("color", "#9E9E9E"))),
        )


DEFAULT_BANDS: list[Band] = [
    Band("Overdue", -1, "#B71C1C"),
    Band("Due today", 0, "#E53935"),
    Band("Next 3 days", 3, "#FB8C00"),
    Band("This week", 7, "#FDD835"),
    Band("Next 2 weeks", 14, "#C0CA33"),
    Band("Later", None, "#43A047"),
]

DEFAULT_NO_DUE_COLOR = "#78909C"
DEFAULT_DONE_COLOR = "#546E7A"


def default_bands() -> list[Band]:
    return [Band(b.label, b.max_days, b.color) for b in DEFAULT_BANDS]


def days_until_due(due: Optional[date], today: Optional[date] = None) -> Optional[int]:
    """Whole days from ``today`` to ``due``.  Negative means overdue."""
    if due is None:
        return None
    return (due - (today or date.today())).days


def band_for(
    due: Optional[date],
    bands: Sequence[Band],
    today: Optional[date] = None,
) -> Optional[Band]:
    """Return the band a due date falls into, or ``None`` when there is no date."""
    days = days_until_due(due, today)
    if days is None:
        return None
    ordered = sort_bands(bands)
    for b in ordered:
        if b.max_days is None or days <= b.max_days:
            return b
    return ordered[-1] if ordered else None


def sort_bands(bands: Sequence[Band]) -> list[Band]:
    """Order bands by upper bound, with the open-ended band last.

    The settings editor lets rows be entered in any order; sorting here means a
    mis-ordered list still produces sensible colours instead of silently
    swallowing every task into whichever band happens to be first.
    """
    bounded = sorted((b for b in bands if b.max_days is not None), key=lambda b: b.max_days)
    unbounded = [b for b in bands if b.max_days is None]
    if not unbounded:
        return bounded
    # Only one open-ended band is meaningful; keep the first and drop the rest.
    return bounded + unbounded[:1]


def color_for(
    due: Optional[date],
    bands: Sequence[Band],
    today: Optional[date] = None,
    no_due_color: str = DEFAULT_NO_DUE_COLOR,
) -> str:
    b = band_for(due, bands, today)
    return b.color if b else normalize_hex(no_due_color)


def label_for(
    due: Optional[date],
    bands: Sequence[Band],
    today: Optional[date] = None,
) -> str:
    b = band_for(due, bands, today)
    return b.label if b else "No due date"


def rgb(color: str) -> tuple[int, int, int]:
    c = normalize_hex(color)
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def relative_luminance(color: str) -> float:
    """WCAG relative luminance, used to choose readable text over a swatch."""

    def channel(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def text_color_for(background: str) -> str:
    """Black or white text, whichever contrasts better with ``background``."""
    return "#000000" if relative_luminance(background) > 0.45 else "#ffffff"


def mix(color: str, other: str, amount: float) -> str:
    """Blend ``amount`` (0..1) of ``other`` into ``color``."""
    amount = max(0.0, min(1.0, amount))
    r1, g1, b1 = rgb(color)
    r2, g2, b2 = rgb(other)
    r = round(r1 + (r2 - r1) * amount)
    g = round(g1 + (g2 - g1) * amount)
    b = round(b1 + (b2 - b1) * amount)
    return "#%02x%02x%02x" % (r, g, b)
