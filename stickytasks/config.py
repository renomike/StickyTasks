"""User settings, stored as JSON next to the database.

Unknown keys in the file are preserved on save so a settings file written by a
newer build is not silently truncated by an older one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from . import colors as colormod
from .colors import Band
from .paths import settings_path

DOCK_RIGHT = "right"
DOCK_LEFT = "left"


@dataclass
class Settings:
    # --- placement -------------------------------------------------------
    monitor_index: int = 0
    dock_edge: str = DOCK_RIGHT
    panel_width: int = 380
    always_on_top: bool = True
    reserve_screen_space: bool = False  # Windows AppBar; off by default
    start_hidden: bool = False
    opacity: float = 1.0

    # --- appearance ------------------------------------------------------
    bands: list[Band] = field(default_factory=colormod.default_bands)
    no_due_color: str = colormod.DEFAULT_NO_DUE_COLOR
    done_color: str = colormod.DEFAULT_DONE_COLOR
    font_size: int = 10
    compact_cards: bool = False

    # --- behaviour -------------------------------------------------------
    show_completed: bool = False
    default_status: str = "To Do"
    confirm_delete: bool = True

    # Anything this build does not know about, round-tripped verbatim.
    _extra: dict[str, Any] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        data = dict(self._extra)
        data.update(
            {
                "monitor_index": self.monitor_index,
                "dock_edge": self.dock_edge,
                "panel_width": self.panel_width,
                "always_on_top": self.always_on_top,
                "reserve_screen_space": self.reserve_screen_space,
                "start_hidden": self.start_hidden,
                "opacity": self.opacity,
                "bands": [b.to_dict() for b in self.bands],
                "no_due_color": self.no_due_color,
                "done_color": self.done_color,
                "font_size": self.font_size,
                "compact_cards": self.compact_cards,
                "show_completed": self.show_completed,
                "default_status": self.default_status,
                "confirm_delete": self.confirm_delete,
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {
            "monitor_index", "dock_edge", "panel_width", "always_on_top",
            "reserve_screen_space", "start_hidden", "opacity", "bands",
            "no_due_color", "done_color", "font_size", "compact_cards",
            "show_completed", "default_status", "confirm_delete",
        }
        s = cls()
        s._extra = {k: v for k, v in data.items() if k not in known}

        s.monitor_index = max(0, _as_int(data.get("monitor_index"), s.monitor_index))
        edge = str(data.get("dock_edge", s.dock_edge)).lower()
        s.dock_edge = edge if edge in (DOCK_LEFT, DOCK_RIGHT) else DOCK_RIGHT
        s.panel_width = _clamp(_as_int(data.get("panel_width"), s.panel_width), 220, 1200)
        s.always_on_top = bool(data.get("always_on_top", s.always_on_top))
        s.reserve_screen_space = bool(data.get("reserve_screen_space", s.reserve_screen_space))
        s.start_hidden = bool(data.get("start_hidden", s.start_hidden))
        s.opacity = min(1.0, max(0.4, _as_float(data.get("opacity"), s.opacity)))

        raw_bands = data.get("bands")
        if isinstance(raw_bands, list) and raw_bands:
            parsed = []
            for item in raw_bands:
                if isinstance(item, dict):
                    try:
                        parsed.append(Band.from_dict(item))
                    except (TypeError, ValueError):
                        continue
            s.bands = colormod.sort_bands(parsed) if parsed else colormod.default_bands()
            if not any(b.max_days is None for b in s.bands):
                # Guarantee a catch-all so distant tasks always get a colour.
                s.bands.append(Band("Later", None, colormod.DEFAULT_BANDS[-1].color))

        s.no_due_color = colormod.normalize_hex(str(data.get("no_due_color", s.no_due_color)))
        s.done_color = colormod.normalize_hex(str(data.get("done_color", s.done_color)))
        s.font_size = _clamp(_as_int(data.get("font_size"), s.font_size), 7, 24)
        s.compact_cards = bool(data.get("compact_cards", s.compact_cards))
        s.show_completed = bool(data.get("show_completed", s.show_completed))
        s.default_status = str(data.get("default_status", s.default_status))
        s.confirm_delete = bool(data.get("confirm_delete", s.confirm_delete))
        return s

    # ------------------------------------------------------------------
    def save(self, path=None) -> None:
        target = path or settings_path()
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(target)  # atomic on the same filesystem

    @classmethod
    def load(cls, path=None) -> "Settings":
        target = path or settings_path()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        return cls.from_dict(data)


def _as_int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))
