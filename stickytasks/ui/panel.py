"""The docked panel: a colour-ranked column of tasks down one screen edge."""

from __future__ import annotations

from datetime import date
from typing import Optional

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QGuiApplication,
    QKeySequence,
    QMouseEvent,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import winautostart
from ..config import DOCK_LEFT, Settings
from ..db import Database
from ..humanize import plural
from ..imagestore import ImageStore
from ..models import (
    ACTIVE_STATUSES,
    STATUS_COMPLETE,
    STATUS_IN_WORK,
    STATUS_TODO,
    Task,
)
from .editor import TaskEditor
from .icons import app_icon
from .report_dialog import ReportDialog
from .settings_dialog import SettingsDialog
from .taskcard import TaskCard
from .theme import BORDER, panel_stylesheet
from .winappbar import AppBar, is_available as appbar_available

GRIP_WIDTH = 6
MIN_WIDTH = 220
MAX_WIDTH = 1200

VIEW_OPEN = "Open"
VIEW_TODO = "To Do"
VIEW_IN_WORK = "In Work"
VIEW_ARCHIVED = "Completed"
VIEW_ALL = "All"

SORT_DUE = "Due date"
SORT_PROJECT = "Project"
SORT_NEWEST = "Newest"


def dock_x(screen_rect, work_rect, edge: str, width: int, reserving: bool) -> int:
    """Left edge for a panel of `width` docked to `edge` of a screen.

    When the panel reserves screen space, the work area has already had the
    panel's own strip taken out of it, so that is the one rectangle it must not
    measure from: doing so walks the panel inwards by its own width every time
    the geometry is reapplied.  Reserving docks against the physical screen
    instead and lets the shell hand back what it grants; floating docks against
    the work area so it sits beside the taskbar rather than under it.
    """
    rect = screen_rect if reserving else work_rect
    return rect.left() if edge == DOCK_LEFT else rect.right() - width + 1


def undock_area(work_rect, edge: str, released_width: int):
    """`work_rect` with a strip the panel just stopped reserving added back.

    The shell only widens the work area once it has broadcast the change, so
    immediately after handing a reservation back the rectangle Qt reports is
    still a strip short.  Nobody else can tell us it is stale, but we know: we
    are the ones who just released it.
    """
    if not released_width:
        return work_rect
    if edge == DOCK_LEFT:
        return work_rect.adjusted(-released_width, 0, 0, 0)
    return work_rect.adjusted(0, 0, released_width, 0)


class StickyPanel(QWidget):
    quit_requested = Signal()

    def __init__(self, db: Database, settings: Settings, store: ImageStore):
        super().__init__()
        self.db = db
        self.settings = settings
        self.store = store
        self._cards: list[TaskCard] = []
        self._today = date.today()
        self._appbar: Optional[AppBar] = None
        self._reserved_width = 0
        self._quitting = False
        self._drag_origin: Optional[QPoint] = None
        self._resize_origin: Optional[tuple[int, int]] = None

        self.setObjectName("StickyPanel")
        self.setWindowTitle("StickyTasks")
        self.setWindowIcon(app_icon())
        self._apply_window_flags()

        self._build()
        self._install_shortcuts()
        self._build_tray()
        self.apply_settings(settings, reload=False)
        self.reload()

        # Colours are relative to today, so the panel has to notice midnight.
        self._tick = QTimer(self)
        self._tick.setInterval(60_000)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.grip = QFrame(self)
        self.grip.setFixedWidth(GRIP_WIDTH)
        self.grip.setCursor(Qt.CursorShape.SizeHorCursor)
        self.grip.setStyleSheet(f"background: {BORDER};")
        self.grip.setToolTip("Drag to resize the panel")
        self.grip.installEventFilter(self)

        self.content = QWidget(self)
        column = QVBoxLayout(self.content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addWidget(self._header())
        column.addWidget(self._filters())
        column.addWidget(self._scroll(), 1)
        column.addWidget(self._footer())

        outer.addWidget(self.grip)
        outer.addWidget(self.content, 1)
        self._place_grip()

    def _header(self) -> QWidget:
        head = QWidget(self)
        head.setObjectName("PanelHeader")
        head.setFixedHeight(38)
        head.installEventFilter(self)
        row = QHBoxLayout(head)
        row.setContentsMargins(10, 4, 6, 4)
        row.setSpacing(4)

        self.lbl_title = QLabel("StickyTasks", head)
        self.lbl_title.setObjectName("PanelTitle")
        self.lbl_title.setToolTip("Drag to move the panel to another screen edge")
        row.addWidget(self.lbl_title, 1)

        self.btn_new = self._tool(head, "＋", "New task (Ctrl+N)", self.new_task)
        self.btn_report = self._tool(head, "▤", "Report (Ctrl+R)", self.open_report)
        self.btn_settings = self._tool(head, "⚙", "Settings", self.open_settings)
        self.btn_hide = self._tool(head, "✕", "Hide to tray (Esc)", self.hide_panel)
        for b in (self.btn_new, self.btn_report, self.btn_settings, self.btn_hide):
            row.addWidget(b)
        return head

    def _tool(self, parent: QWidget, text: str, tip: str, slot) -> QToolButton:
        b = QToolButton(parent)
        b.setText(text)
        b.setToolTip(tip)
        b.setFixedSize(QSize(26, 26))
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _filters(self) -> QWidget:
        bar = QWidget(self)
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(5)

        self.ed_search = QLineEdit(bar)
        self.ed_search.setPlaceholderText("Search titles, projects and notes…")
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.textChanged.connect(self.reload)
        layout.addWidget(self.ed_search)

        row = QHBoxLayout()
        row.setSpacing(5)
        self.cmb_view = QComboBox(bar)
        self.cmb_view.addItems([VIEW_OPEN, VIEW_TODO, VIEW_IN_WORK, VIEW_ARCHIVED, VIEW_ALL])
        self.cmb_view.setToolTip("Which tasks to show")
        self.cmb_view.currentTextChanged.connect(self.reload)
        row.addWidget(self.cmb_view, 1)

        self.cmb_sort = QComboBox(bar)
        self.cmb_sort.addItems([SORT_DUE, SORT_PROJECT, SORT_NEWEST])
        self.cmb_sort.setToolTip("Sort order")
        self.cmb_sort.currentTextChanged.connect(self.reload)
        row.addWidget(self.cmb_sort, 1)
        layout.addLayout(row)
        return bar

    def _scroll(self) -> QWidget:
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("TaskScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # The viewport is a separate widget from the scroll area and does not
        # inherit its background, which leaves an empty list showing the
        # platform's default light grey.
        self.scroll.viewport().setObjectName("TaskScrollViewport")

        self.list_host = QWidget(self.scroll)
        self.list_host.setObjectName("TaskList")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(8, 4, 8, 8)
        self.list_layout.setSpacing(7)
        self.list_layout.addStretch(1)

        self.lbl_empty = QLabel("", self.list_host)
        self.lbl_empty.setObjectName("FooterLabel")
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.list_layout.insertWidget(0, self.lbl_empty)

        self.scroll.setWidget(self.list_host)
        return self.scroll

    def _footer(self) -> QWidget:
        foot = QWidget(self)
        foot.setObjectName("PanelFooter")
        foot.setFixedHeight(28)
        row = QHBoxLayout(foot)
        row.setContentsMargins(10, 2, 8, 2)
        self.lbl_counts = QLabel("", foot)
        self.lbl_counts.setObjectName("FooterLabel")
        row.addWidget(self.lbl_counts, 1)
        return foot

    def _install_shortcuts(self) -> None:
        for seq, slot in (
            ("Ctrl+N", self.new_task),
            ("Ctrl+F", lambda: (self.ed_search.setFocus(), self.ed_search.selectAll())),
            ("Ctrl+R", self.open_report),
            ("F5", self.reload),
            ("Esc", self._on_escape),
        ):
            QShortcut(QKeySequence(seq), self, activated=slot)

    def _build_tray(self) -> None:
        self.tray: Optional[QSystemTrayIcon] = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("StickyTasks")

        menu = QMenu()
        for text, slot in (
            ("Show panel", self.show_panel),
            ("Hide panel", self.hide_panel),
            (None, None),
            ("New task…", self.new_task),
            ("Report…", self.open_report),
            ("Settings…", self.open_settings),
            (None, None),
            ("Quit StickyTasks", self._quit),
        ):
            if text is None:
                menu.addSeparator()
                continue
            action = QAction(text, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        self._tray_menu = menu  # keep a reference; Qt does not own it
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_panel() if not self.isVisible() else self.hide_panel()

    # ------------------------------------------------------------------
    # geometry
    # ------------------------------------------------------------------
    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        if self.settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def _place_grip(self) -> None:
        """Keep the resize grip on the inward-facing side of the panel."""
        layout: QHBoxLayout = self.layout()  # type: ignore[assignment]
        layout.removeWidget(self.grip)
        layout.removeWidget(self.content)
        if self.settings.dock_edge == DOCK_LEFT:
            layout.addWidget(self.content, 1)
            layout.addWidget(self.grip)
        else:
            layout.addWidget(self.grip)
            layout.addWidget(self.content, 1)

    def target_screen(self):
        screens = QGuiApplication.screens()
        if not screens:
            return None
        index = min(max(0, self.settings.monitor_index), len(screens) - 1)
        return screens[index]

    def apply_geometry(self) -> None:
        screen = self.target_screen()
        if screen is None:
            return
        reserving = self._wants_appbar()
        # Release before measuring, then measure as if the strip were already
        # back: docking against a work area with our own band still cut out of
        # it is what used to walk the panel inwards a width at a time.
        given_back = 0 if reserving else self._release_appbar()
        area = undock_area(screen.availableGeometry(), self.settings.dock_edge, given_back)
        width = max(MIN_WIDTH, min(MAX_WIDTH, self.settings.panel_width))
        x = dock_x(screen.geometry(), area, self.settings.dock_edge, width, reserving)
        self.setGeometry(x, area.top(), width, area.height())
        self._sync_appbar(area, width, x)

    def _wants_appbar(self) -> bool:
        return bool(self.settings.reserve_screen_space) and appbar_available()

    def _release_appbar(self) -> int:
        """Hand the reserved strip back to the desktop; returns its width."""
        if self._appbar is None:
            return 0
        self._appbar.unregister()
        self._appbar = None
        width, self._reserved_width = self._reserved_width, 0
        return width

    def _sync_appbar(self, area, width: int, x: int) -> None:
        """Register, update or drop the Windows AppBar reservation."""
        if not self._wants_appbar():
            self._release_appbar()
            return
        if self._appbar is None:
            self._appbar = AppBar(int(self.winId()))
            if not self._appbar.register():
                self._appbar = None
                return
        granted = self._appbar.reserve(
            self.settings.dock_edge, x, area.top(), x + width, area.top() + area.height()
        )
        if granted:
            left, top, right, bottom = granted
            width = max(MIN_WIDTH, right - left)
            self.setGeometry(left, top, width, max(100, bottom - top))
        self._reserved_width = width

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt naming)
        if watched is self.grip:
            if event.type() == QEvent.Type.MouseButtonPress:
                self._resize_origin = (event.globalPosition().toPoint().x(), self.width())
                return True
            if event.type() == QEvent.Type.MouseMove and self._resize_origin:
                start_x, start_w = self._resize_origin
                delta = event.globalPosition().toPoint().x() - start_x
                # Dragging the grip inward widens the panel on a right dock.
                new_w = start_w - delta if self.settings.dock_edge != DOCK_LEFT else start_w + delta
                self.settings.panel_width = max(MIN_WIDTH, min(MAX_WIDTH, int(new_w)))
                self.apply_geometry()
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and self._resize_origin:
                self._resize_origin = None
                self.settings.save()
                return True

        if watched is not None and event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(event, QMouseEvent) and watched.objectName() == "PanelHeader":
                self._drag_origin = event.globalPosition().toPoint()
        elif watched is not None and event.type() == QEvent.Type.MouseButtonRelease:
            if self._drag_origin is not None and watched.objectName() == "PanelHeader":
                self._drag_origin = None
                self._redock_to_cursor(event.globalPosition().toPoint())
                return True
        return super().eventFilter(watched, event)

    def _redock_to_cursor(self, global_pos) -> None:
        """Snap to whichever screen edge the header was released nearest."""
        screens = QGuiApplication.screens()
        for i, screen in enumerate(screens):
            area = screen.availableGeometry()
            if not area.contains(global_pos):
                continue
            midpoint = area.left() + area.width() // 2
            edge = DOCK_LEFT if global_pos.x() < midpoint else "right"
            if i == self.settings.monitor_index and edge == self.settings.dock_edge:
                return
            self.settings.monitor_index = i
            self.settings.dock_edge = edge
            self.settings.save()
            self._place_grip()
            self.apply_geometry()
            return

    # ------------------------------------------------------------------
    # data
    # ------------------------------------------------------------------
    def _query(self) -> list[Task]:
        view = self.cmb_view.currentText()
        sort_map = {SORT_DUE: "due", SORT_PROJECT: "project", SORT_NEWEST: "created"}
        order = sort_map.get(self.cmb_sort.currentText(), "due")
        search = self.ed_search.text().strip() or None

        if view == VIEW_ARCHIVED:
            return self.db.list_tasks(
                include_archived=True, statuses=[STATUS_COMPLETE], search=search, order=order
            )
        if view == VIEW_ALL:
            return self.db.list_tasks(include_archived=True, search=search, order=order)
        if view == VIEW_TODO:
            return self.db.list_tasks(statuses=[STATUS_TODO], search=search, order=order)
        if view == VIEW_IN_WORK:
            return self.db.list_tasks(statuses=[STATUS_IN_WORK], search=search, order=order)
        return self.db.list_tasks(statuses=list(ACTIVE_STATUSES), search=search, order=order)

    def reload(self) -> None:
        tasks = self._query()
        self._today = date.today()

        for card in self._cards:
            self.list_layout.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        for i, task in enumerate(tasks):
            card = TaskCard(
                task,
                self.settings.bands,
                self.settings.no_due_color,
                self.settings.done_color,
                compact=self.settings.compact_cards,
                font_size=self.settings.font_size,
                today=self._today,
                parent=self.list_host,
            )
            card.edit_requested.connect(self.edit_task)
            card.status_changed.connect(self.change_status)
            card.delete_requested.connect(self.delete_task)
            card.archive_requested.connect(self.toggle_archived)
            card.duplicate_requested.connect(self.duplicate_task)
            self.list_layout.insertWidget(i + 1, card)  # +1: the empty-state label is at 0
            self._cards.append(card)

        self._update_empty_state(len(tasks))
        self._update_footer()

    def _update_empty_state(self, count: int) -> None:
        if count:
            self.lbl_empty.setVisible(False)
            return
        if self.ed_search.text().strip():
            msg = "Nothing matches that search."
        elif self.cmb_view.currentText() == VIEW_ARCHIVED:
            msg = "No completed tasks yet.\nFinished tasks are archived here, not deleted."
        else:
            msg = "No open tasks.\nPress Ctrl+N or the ＋ button to add one."
        self.lbl_empty.setText("\n\n" + msg)
        self.lbl_empty.setVisible(True)

    def _update_footer(self) -> None:
        counts = self.db.counts()
        open_total = counts[STATUS_TODO] + counts[STATUS_IN_WORK]
        self.lbl_counts.setText(
            f"{plural(open_total, 'open task')}  ·  "
            f"{counts[STATUS_IN_WORK]} in work  ·  {counts['Archived']} archived"
        )

    def _on_tick(self) -> None:
        """Re-colour when the date rolls over; colours are relative to today."""
        if date.today() != self._today:
            self.reload()

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def new_task(self) -> None:
        task = Task(status=self.settings.default_status)
        dialog = TaskEditor(
            task, self.db.projects(), self.store, self.settings.bands,
            self.settings.no_due_color, self.settings.font_size, parent=self,
        )
        self._centre_on_panel_screen(dialog)
        if dialog.exec() != TaskEditor.DialogCode.Accepted:
            return
        edited = dialog.result_task()
        self.db.add_task(
            title=edited.title, project=edited.project, due_date=edited.due_date,
            status=edited.status, note_html=edited.note_html, note_plain=edited.note_plain,
        )
        self.reload()

    def edit_task(self, task_id: int) -> None:
        task = self.db.get_task(task_id)
        if task is None:
            self.reload()
            return
        dialog = TaskEditor(
            task, self.db.projects(), self.store, self.settings.bands,
            self.settings.no_due_color, self.settings.font_size,
            history=self.db.status_events(task_id), parent=self,
        )
        self._centre_on_panel_screen(dialog)
        if dialog.exec() != TaskEditor.DialogCode.Accepted:
            return
        self.db.update_task(dialog.result_task())
        self.reload()

    def change_status(self, task_id: int, status: str) -> None:
        self.db.set_status(task_id, status)
        self.reload()

    def toggle_archived(self, task_id: int) -> None:
        task = self.db.get_task(task_id)
        if task is None:
            return
        self.db.set_archived(task_id, not task.archived)
        self.reload()

    def duplicate_task(self, task_id: int) -> None:
        task = self.db.get_task(task_id)
        if task is None:
            return
        self.db.add_task(
            title=f"{task.title} (copy)", project=task.project, due_date=task.due_date,
            status=STATUS_TODO, note_html=task.note_html, note_plain=task.note_plain,
        )
        self.reload()

    def delete_task(self, task_id: int) -> None:
        task = self.db.get_task(task_id)
        if task is None:
            return
        if self.settings.confirm_delete:
            answer = QMessageBox.question(
                self,
                "Delete permanently?",
                f"Delete “{task.title or '(untitled)'}” and its notes for good?\n\n"
                "This cannot be undone. To keep it out of the panel without "
                "losing it, mark it Complete instead — completed tasks are "
                "archived and still appear in reports.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.db.delete_task(task_id)
        self.reload()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, parent=self)
        self._centre_on_panel_screen(dialog)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        updated = dialog.result_settings()
        updated.save()
        self._apply_autostart(dialog.autostart_wanted())
        self.apply_settings(updated)

    def _apply_autostart(self, wanted: Optional[bool]) -> None:
        """Write the sign-in registration, which lives outside settings.json."""
        if wanted is None or winautostart.set_enabled(wanted):
            return
        refused = (
            "Windows would not let StickyTasks change its own sign-in entry, "
            "which usually means a policy on a managed machine."
        )
        by_hand = (
            "You can still set it up by hand: press Win+R, run shell:startup, "
            "and put a shortcut to StickyTasks.bat in the folder that opens."
        )
        QMessageBox.warning(self, "StickyTasks", refused + "\n\n" + by_hand)

    def open_report(self) -> None:
        dialog = ReportDialog(self.db, self.settings.font_size, parent=self)
        self._centre_on_panel_screen(dialog)
        dialog.exec()

    def apply_settings(self, settings: Settings, reload: bool = True) -> None:
        was_on_top = bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        self.settings = settings
        self.setStyleSheet(panel_stylesheet(settings.font_size))
        self.setWindowOpacity(settings.opacity)
        if was_on_top != settings.always_on_top:
            visible = self.isVisible()
            self._apply_window_flags()
            if visible:
                self.show()  # re-applying flags hides the window
        self._place_grip()
        self.apply_geometry()
        if reload:
            self.reload()

    def _centre_on_panel_screen(self, dialog) -> None:
        """Open dialogs on the panel's screen, not under the panel itself."""
        screen = self.target_screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        size = dialog.sizeHint().expandedTo(dialog.size())
        dialog.move(
            area.center().x() - size.width() // 2,
            max(area.top() + 20, area.center().y() - size.height() // 2),
        )

    # ------------------------------------------------------------------
    # visibility
    # ------------------------------------------------------------------
    def show_panel(self) -> None:
        self.apply_geometry()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_panel(self) -> None:
        # Hidden means gone: keeping the reservation would fence maximised
        # windows out of a strip nothing is drawing in.
        self._release_appbar()
        self.hide()

    def _on_escape(self) -> None:
        if self.ed_search.text():
            self.ed_search.clear()
            return
        self.hide_panel()

    def _quit(self) -> None:
        self._quitting = True
        self._release_appbar()
        if self.tray is not None:
            self.tray.hide()
        self.quit_requested.emit()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt naming)
        if self._quitting or self.tray is None:
            self._release_appbar()
            event.accept()
            return
        # With a tray icon present, closing hides rather than exits — otherwise
        # a stray Alt+F4 would silently take the panel away for the session.
        event.ignore()
        self.hide_panel()
