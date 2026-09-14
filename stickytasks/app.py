"""Application entry point."""

from __future__ import annotations

import sys
from typing import Optional

from .config import Settings
from .db import Database
from .imagestore import ImageStore
from .paths import db_path, ensure_home, images_dir


def build(argv: Optional[list[str]] = None):
    """Create the application and panel without entering the event loop.

    Split out from :func:`run` so tests can drive a fully wired app.
    """
    from PySide6.QtWidgets import QApplication

    from .ui.icons import app_icon
    from .ui.panel import StickyPanel

    ensure_home()
    # Reuse an existing instance if there is one; Qt allows only one per process.
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("StickyTasks")
    app.setOrganizationName("StickyTasks")
    app.setWindowIcon(app_icon())
    # The panel hides to the tray, so an empty screen must not end the process.
    app.setQuitOnLastWindowClosed(False)

    settings = Settings.load()
    db = Database(db_path())
    store = ImageStore(images_dir())

    # Drop images no note references any more (e.g. pastes that were undone).
    try:
        store.purge_unreferenced(db.referenced_image_names())
    except OSError:
        pass

    panel = StickyPanel(db, settings, store)
    if settings.start_hidden and panel.tray is not None:
        panel.hide()
    else:
        panel.show_panel()
    return app, panel, db


def run(argv: Optional[list[str]] = None) -> int:
    app, _panel, db = build(argv)
    try:
        return app.exec()
    finally:
        db.close()


def main() -> None:
    raise SystemExit(run())
