"""End-to-end checks: the app starts, saves, and reloads its own data."""

import os
from datetime import date

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtGui import QColor, QImage  # noqa: E402

from stickytasks import app as appmod  # noqa: E402
from stickytasks.models import STATUS_COMPLETE  # noqa: E402


@pytest.fixture
def started(home):
    """A fully wired app rooted at an isolated STICKYTASKS_HOME."""
    application, panel, db = appmod.build([])
    yield application, panel, db
    panel._tick.stop()
    panel.hide()
    db.close()


def test_app_starts_with_an_empty_database(started, home):
    _app, panel, db = started
    assert panel._cards == []
    assert (home / "stickytasks.db").exists()
    assert (home / "images").is_dir()


def test_task_survives_a_restart(started, home):
    _app, panel, db = started
    db.add_task("Persisted task", project="Ops", due_date=date(2026, 12, 1))
    panel.reload()
    assert len(panel._cards) == 1
    panel._tick.stop()
    panel.hide()
    db.close()

    _app2, panel2, db2 = appmod.build([])
    try:
        assert [c.task.title for c in panel2._cards] == ["Persisted task"]
        assert panel2._cards[0].task.project == "Ops"
    finally:
        panel2._tick.stop()
        panel2.hide()
        db2.close()


def test_note_image_survives_a_restart(started, home):
    """The whole point of storing images on disk instead of in the document."""
    _app, panel, db = started
    from stickytasks.ui.richtext import NoteEditor

    editor = NoteEditor(panel.store)
    img = QImage(60, 40, QImage.Format.Format_RGB32)
    img.fill(QColor("#aa3366"))
    editor.edit.insert_image(img)
    db.add_task("With screenshot", note_html=editor.html(), note_plain=editor.plain_text())

    panel._tick.stop()
    panel.hide()
    db.close()

    # Restart: startup purges orphaned images, so the referenced one must stay.
    _app2, panel2, db2 = appmod.build([])
    try:
        task = panel2.db.list_tasks()[0]
        name = task.note_html.split('src="')[1].split('"')[0]
        assert panel2.store.exists(name), "startup purge deleted a referenced image"

        reopened = NoteEditor(panel2.store)
        reopened.set_html(task.note_html)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QTextDocument

        resolved = reopened.edit.loadResource(
            QTextDocument.ResourceType.ImageResource.value, QUrl(name)
        )
        assert isinstance(resolved, QImage) and not resolved.isNull()
    finally:
        panel2._tick.stop()
        panel2.hide()
        db2.close()


def test_startup_purges_orphaned_images(started, home):
    _app, panel, db = started
    orphan = panel.store.save_bytes(b"\x89PNG\r\n\x1a\nnot referenced anywhere")
    assert panel.store.exists(orphan)

    panel._tick.stop()
    panel.hide()
    db.close()

    _app2, panel2, db2 = appmod.build([])
    try:
        assert not panel2.store.exists(orphan)
    finally:
        panel2._tick.stop()
        panel2.hide()
        db2.close()


def test_settings_changes_persist_across_restarts(started, home):
    _app, panel, db = started
    panel.settings.panel_width = 512
    panel.settings.compact_cards = True
    panel.settings.save()

    panel._tick.stop()
    panel.hide()
    db.close()

    _app2, panel2, db2 = appmod.build([])
    try:
        assert panel2.settings.panel_width == 512
        assert panel2.settings.compact_cards is True
    finally:
        panel2._tick.stop()
        panel2.hide()
        db2.close()


def test_completed_tasks_reach_the_report_after_a_restart(started, home):
    _app, panel, db = started
    t = db.add_task("Delivered the thing", project="Platform", note_plain="Went out on time.")
    db.set_status(t.id, STATUS_COMPLETE)

    panel._tick.stop()
    panel.hide()
    db.close()

    _app2, panel2, db2 = appmod.build([])
    try:
        from stickytasks import report as reportmod

        today = date.today()
        text = reportmod.generate(
            db2,
            reportmod.ReportOptions(start=date(today.year, 1, 1), end=today),
        )
        assert "Delivered the thing" in text
        assert "Went out on time." in text
    finally:
        panel2._tick.stop()
        panel2.hide()
        db2.close()
