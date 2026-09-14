"""Filesystem locations for application data.

Everything the app owns lives under one directory so the whole thing can be
backed up or moved by copying a single folder.  The location can be overridden
with the STICKYTASKS_HOME environment variable, which is what the tests use.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def app_home() -> Path:
    """Return the directory holding the database, settings and images."""
    override = os.environ.get("STICKYTASKS_HOME")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / "StickyTasks"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "StickyTasks"
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return Path(base) / "stickytasks"


def ensure_home() -> Path:
    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    (home / "images").mkdir(exist_ok=True)
    return home


def db_path() -> Path:
    return ensure_home() / "stickytasks.db"


def settings_path() -> Path:
    return ensure_home() / "settings.json"


def images_dir() -> Path:
    return ensure_home() / "images"


def exports_dir() -> Path:
    d = ensure_home() / "exports"
    d.mkdir(exist_ok=True)
    return d
