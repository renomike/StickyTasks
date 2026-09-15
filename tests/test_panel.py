"""Integration tests for the panel, driven headlessly through Qt's offscreen platform.

These exercise the wiring between the widgets and the database: clicking a
card's status control really does archive the task, filters really do change
the query, and so on.
"""

import os
from datetime import date, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from stickytasks.config import DOCK_LEFT, DOCK_RIGHT, Settings  # noqa: E402
from stickytasks.db import Database  # noqa: E402
from stickytasks.imagestore import ImageStore  # noqa: E402
from stickytasks.models import STATUS_COMPLETE, STATUS_IN_WORK, STATUS_TODO  # noqa: E402
from stickytasks.ui.panel import (  # noqa: E402
    MAX_WIDTH,
    MIN_WIDTH,
    VIEW_ALL,
    VIEW_ARCHIVED,
    VIEW_IN_WORK,
    VIEW_OPEN,
    StickyPanel,
    dock_x,
    undock_area,
)
from stickytasks.ui.winappbar import is_available as appbar_available  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def panel(qapp, tmp_path):
    db = Database(tmp_path / "panel.db")
    settings = Settings()
    p = StickyPanel(db, settings, ImageStore(tmp_path / "images"))
    yield p
    p._tick.stop()
    p._release_appbar()  # a test must never leave a strip of desktop reserved
    db.close()


class FakeAppBar:
    """Stands in for the Windows AppBar so the release paths run anywhere."""

    def __init__(self):
        self.unregistered = False

    def unregister(self):
        self.unregistered = True
        return True


def seed(panel, n=3):
    today = date.today()
    for i in range(n):
        panel.db.add_task(
            f"Task {i}", project="Proj" if i % 2 else "Other",
            due_date=today + timedelta(days=i),
        )
    panel.reload()


def test_cards_reflect_tasks(panel):
    seed(panel, 3)
    assert len(panel._cards) == 3
    assert [c.task.title for c in panel._cards] == ["Task 0", "Task 1", "Task 2"]


def test_cards_are_ordered_soonest_due_first(panel):
    today = date.today()
    panel.db.add_task("later", due_date=today + timedelta(days=30))
    panel.db.add_task("sooner", due_date=today + timedelta(days=1))
    panel.db.add_task("undated")
    panel.reload()
    assert [c.task.title for c in panel._cards] == ["sooner", "later", "undated"]


def test_card_colour_matches_the_band(panel):
    today = date.today()
    panel.db.add_task("overdue", due_date=today - timedelta(days=5))
    panel.db.add_task("far off", due_date=today + timedelta(days=90))
    panel.reload()
    by_title = {c.task.title: c.background_color() for c in panel._cards}
    assert by_title["overdue"] == "#b71c1c"
    assert by_title["far off"] == "#43a047"


def test_completing_from_a_card_archives_and_removes_it(panel):
    seed(panel, 1)
    card = panel._cards[0]
    card.btn_done.click()

    assert panel._cards == []  # gone from the Open view
    stored = panel.db.get_task(card.task.id)
    assert stored.status == STATUS_COMPLETE
    assert stored.archived is True


def test_completed_view_shows_archived_tasks(panel):
    seed(panel, 1)
    panel._cards[0].btn_done.click()
    panel.cmb_view.setCurrentText(VIEW_ARCHIVED)
    assert [c.task.title for c in panel._cards] == ["Task 0"]


def test_status_combo_moves_a_task_to_in_work(panel):
    seed(panel, 1)
    panel._cards[0].cmb_status.setCurrentText(STATUS_IN_WORK)
    assert panel.db.get_task(1).status == STATUS_IN_WORK
    panel.cmb_view.setCurrentText(VIEW_IN_WORK)
    assert len(panel._cards) == 1


def test_view_filters(panel):
    a = panel.db.add_task("todo one")
    b = panel.db.add_task("working")
    panel.db.set_status(b.id, STATUS_IN_WORK)
    c = panel.db.add_task("finished")
    panel.db.set_status(c.id, STATUS_COMPLETE)
    panel.reload()

    panel.cmb_view.setCurrentText(VIEW_OPEN)
    assert {x.task.title for x in panel._cards} == {"todo one", "working"}

    panel.cmb_view.setCurrentText(VIEW_ALL)
    assert len(panel._cards) == 3
    assert a.id and c.id


def test_search_filters_cards(panel):
    panel.db.add_task("Quarterly filing", project="Compliance")
    panel.db.add_task("Fix the parser", project="Platform")
    panel.reload()

    panel.ed_search.setText("parser")
    assert [c.task.title for c in panel._cards] == ["Fix the parser"]

    panel.ed_search.setText("compliance")
    assert [c.task.title for c in panel._cards] == ["Quarterly filing"]

    panel.ed_search.setText("")
    assert len(panel._cards) == 2


def test_empty_state_message_depends_on_context(panel):
    assert not panel.lbl_empty.isHidden()
    assert "No open tasks" in panel.lbl_empty.text()

    panel.ed_search.setText("zzz")
    assert "Nothing matches" in panel.lbl_empty.text()

    panel.ed_search.setText("")
    panel.cmb_view.setCurrentText(VIEW_ARCHIVED)
    assert "archived here, not deleted" in panel.lbl_empty.text()


def test_footer_counts(panel):
    panel.db.add_task("a")
    b = panel.db.add_task("b")
    panel.db.set_status(b.id, STATUS_IN_WORK)
    c = panel.db.add_task("c")
    panel.db.set_status(c.id, STATUS_COMPLETE)
    panel.reload()
    assert panel.lbl_counts.text() == "2 open tasks  ·  1 in work  ·  1 archived"


def test_delete_without_confirmation_removes_the_task(panel):
    seed(panel, 1)
    panel.settings.confirm_delete = False
    panel.delete_task(1)
    assert panel.db.get_task(1) is None
    assert panel._cards == []


def test_duplicate_creates_an_open_copy(panel):
    t = panel.db.add_task("Weekly report", project="Ops", note_plain="the usual")
    panel.db.set_status(t.id, STATUS_COMPLETE)
    panel.duplicate_task(t.id)

    copy = [x for x in panel.db.list_tasks(include_archived=True) if x.id != t.id][0]
    assert copy.title == "Weekly report (copy)"
    assert copy.project == "Ops"
    assert copy.status == STATUS_TODO
    assert copy.archived is False


def test_toggle_archived_hides_without_changing_status(panel):
    seed(panel, 1)
    panel.toggle_archived(1)
    stored = panel.db.get_task(1)
    assert stored.archived is True
    assert stored.status == STATUS_TODO  # still open, just hidden
    assert panel._cards == []


def test_geometry_hugs_the_chosen_edge(panel):
    screen = panel.target_screen()
    area = screen.availableGeometry()

    panel.settings.dock_edge = DOCK_RIGHT
    panel.settings.panel_width = 350
    panel.apply_geometry()
    g = panel.geometry()
    assert g.width() == 350
    assert g.right() == area.right()
    assert g.top() == area.top()
    assert g.height() == area.height()

    panel.settings.dock_edge = DOCK_LEFT
    panel.apply_geometry()
    assert panel.geometry().left() == area.left()


def test_reserving_docks_against_the_screen_not_its_own_reserved_strip():
    """Regression: the panel used to walk inwards by its own width.

    Once the AppBar reservation is live the work area no longer includes the
    strip the panel sits in, so measuring from it moved the panel inwards every
    time the geometry was reapplied — 1540, then 1160, then 780.
    """
    screen = QRect(0, 0, 1920, 1080)
    reserved = QRect(0, 0, 1540, 1032)  # our own 380px strip already taken out

    x = dock_x(screen, reserved, DOCK_RIGHT, 380, reserving=True)
    assert x == 1540
    # Reapplying with the same shrunken work area must not move it again.
    assert dock_x(screen, reserved, DOCK_RIGHT, 380, reserving=True) == x
    assert dock_x(screen, reserved, DOCK_LEFT, 380, reserving=True) == 0


def test_floating_docks_inside_the_work_area():
    """Without a reservation the panel sits beside the taskbar, not under it."""
    screen = QRect(0, 0, 1920, 1080)
    work = QRect(0, 0, 1870, 1080)  # taskbar down the right-hand edge

    assert dock_x(screen, work, DOCK_RIGHT, 380, reserving=False) == 1490


def test_giving_the_reservation_back_measures_as_if_the_strip_were_already_back():
    """Regression: turning the setting off moved the panel inwards by a width.

    The shell widens the work area asynchronously, so the rectangle Qt reports
    the instant the reservation is released is still a strip short.
    """
    screen = QRect(0, 0, 1920, 1080)
    stale = QRect(0, 0, 1540, 1032)  # our own 380px band not back yet

    area = undock_area(stale, DOCK_RIGHT, 380)
    assert area.right() == screen.right()
    assert dock_x(screen, area, DOCK_RIGHT, 380, reserving=False) == 1540

    assert undock_area(QRect(380, 0, 1540, 1032), DOCK_LEFT, 380).left() == 0
    assert undock_area(stale, DOCK_RIGHT, 0) == stale  # released nothing, add nothing


def test_panel_width_is_clamped(panel):
    panel.settings.panel_width = 50
    panel.apply_geometry()
    assert panel.geometry().width() == MIN_WIDTH

    panel.settings.panel_width = 99999
    panel.apply_geometry()
    assert panel.geometry().width() == MAX_WIDTH


def test_monitor_index_beyond_available_screens_falls_back(panel):
    panel.settings.monitor_index = 99
    assert panel.target_screen() is not None
    panel.apply_geometry()  # must not raise


def test_applying_settings_repaints_cards(panel):
    seed(panel, 1)
    settings = panel.settings
    settings.bands[0].color = "#123456"  # recolour the overdue band
    panel.db.conn.execute(
        "UPDATE tasks SET due_date=? WHERE id=1", ((date.today() - timedelta(days=9)).isoformat(),)
    )
    panel.db.conn.commit()
    panel.apply_settings(settings)
    assert panel._cards[0].background_color() == "#123456"


def test_compact_mode_hides_the_preview_line(panel):
    panel.db.add_task("With note", note_plain="some detail")
    panel.settings.compact_cards = True
    panel.apply_settings(panel.settings)
    assert panel._cards[0].lbl_preview.isHidden()


def test_midnight_rollover_triggers_a_reload(panel, monkeypatch):
    seed(panel, 1)
    panel._today = date.today() - timedelta(days=1)  # pretend the day changed
    calls = []
    monkeypatch.setattr(panel, "reload", lambda: calls.append(1))
    panel._on_tick()
    assert calls == [1]


def test_no_appbar_is_registered_where_the_platform_has_none(panel):
    panel.settings.reserve_screen_space = True
    panel.apply_geometry()
    # AppBar is a Windows extra: everywhere else the setting degrades quietly.
    assert panel._appbar is None or appbar_available()


def test_hiding_to_the_tray_gives_the_reserved_strip_back(panel):
    """A hidden panel must not fence maximised windows out of the strip."""
    bar = FakeAppBar()
    panel._appbar = bar
    panel._reserved_width = 380
    panel.hide_panel()

    assert bar.unregistered
    assert panel._appbar is None
    assert panel._reserved_width == 0


def test_releasing_reports_the_width_it_handed_back(panel):
    panel._appbar = FakeAppBar()
    panel._reserved_width = 380

    assert panel._release_appbar() == 380
    assert panel._release_appbar() == 0  # nothing left to give back


def test_empty_list_area_uses_the_dark_theme(panel):
    """An empty list must not show the platform's default light background.

    The scroll viewport is a separate widget from the QScrollArea and does not
    inherit its background, so it needs targeting by name in the stylesheet.
    This only shows up when no cards cover it.
    """
    from PySide6.QtGui import QColor

    from stickytasks.ui.theme import BG

    assert panel._cards == []
    assert panel.scroll.viewport().objectName() == "TaskScrollViewport"
    assert panel.list_host.objectName() == "TaskList"

    sheet = panel.styleSheet()
    assert "QWidget#TaskScrollViewport" in sheet
    assert "QWidget#TaskList" in sheet

    panel.show()
    panel.resize(380, 400)
    shot = panel.grab().toImage()
    # Sample well inside the list area, below the header and filter rows.
    sampled = QColor(shot.pixel(shot.width() // 2, int(shot.height() * 0.7)))
    expected = QColor(BG)
    assert sampled.lightness() < 100, f"list area is light ({sampled.name()}), expected {BG}"
    for got, want in zip(
        (sampled.red(), sampled.green(), sampled.blue()),
        (expected.red(), expected.green(), expected.blue()),
    ):
        assert abs(got - want) <= 8, f"list background {sampled.name()} != {BG}"
    panel.hide()
