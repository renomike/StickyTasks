"""One task, rendered as a colour-coded card in the panel."""

from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QFont, QMouseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import colors as colormod
from ..humanize import due_phrase, short_date
from ..models import STATUS_COMPLETE, STATUSES, Task
from ..report import html_to_text
from .elidedlabel import ElidedLabel, WrapLabel


class TaskCard(QFrame):
    """Emits intent; it never touches the database itself."""

    edit_requested = Signal(int)
    status_changed = Signal(int, str)
    delete_requested = Signal(int)
    archive_requested = Signal(int)
    duplicate_requested = Signal(int)

    def __init__(
        self,
        task: Task,
        bands: Sequence[colormod.Band],
        no_due_color: str,
        done_color: str,
        compact: bool = False,
        font_size: int = 10,
        today: Optional[date] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.task = task
        self._bands = list(bands)
        self._no_due_color = no_due_color
        self._done_color = done_color
        self._compact = compact
        self._font_size = font_size
        self._today = today or date.today()
        self._suppress_status_signal = False

        self.setObjectName("TaskCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

        self._build()
        self.refresh(task)

    # -- construction ---------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        margin = 7 if self._compact else 9
        outer.setContentsMargins(10, margin, 8, margin)
        outer.setSpacing(3 if self._compact else 5)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.lbl_title = WrapLabel("", self)
        title_font = QFont()
        title_font.setPointSize(self._font_size + 1)
        title_font.setBold(True)
        self.lbl_title.setFont(title_font)
        top.addWidget(self.lbl_title, 1)

        self.btn_done = QToolButton(self)
        self.btn_done.setText("✓")
        self.btn_done.setToolTip("Mark complete (archives it)")
        self.btn_done.setFixedSize(QSize(22, 22))
        self.btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_done.clicked.connect(
            lambda: self.status_changed.emit(self.task.id, STATUS_COMPLETE)
        )
        top.addWidget(self.btn_done, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(top)

        self.lbl_meta = ElidedLabel("", parent=self)
        meta_font = QFont()
        meta_font.setPointSize(max(7, self._font_size - 1))
        self.lbl_meta.setFont(meta_font)
        outer.addWidget(self.lbl_meta)

        self.lbl_preview = ElidedLabel("", parent=self)
        preview_font = QFont()
        preview_font.setPointSize(max(7, self._font_size - 1))
        preview_font.setItalic(True)
        self.lbl_preview.setFont(preview_font)
        outer.addWidget(self.lbl_preview)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        self.cmb_status = QComboBox(self)
        self.cmb_status.addItems(list(STATUSES))
        self.cmb_status.setFixedHeight(22)
        self.cmb_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cmb_status.currentTextChanged.connect(self._on_status_changed)
        bottom.addWidget(self.cmb_status, 0)
        bottom.addStretch(1)

        self.btn_menu = QToolButton(self)
        self.btn_menu.setText("⋯")
        self.btn_menu.setToolTip("More actions")
        self.btn_menu.setFixedSize(QSize(22, 22))
        self.btn_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_menu.clicked.connect(
            lambda: self._show_menu(self.btn_menu.geometry().bottomLeft())
        )
        bottom.addWidget(self.btn_menu, 0)
        outer.addLayout(bottom)

    # -- state ----------------------------------------------------------
    def refresh(self, task: Task, today: Optional[date] = None) -> None:
        self.task = task
        if today:
            self._today = today

        self.lbl_title.setText(task.title or "(untitled)")

        bits = []
        if task.project:
            bits.append(task.project)
        if task.due_date:
            bits.append(f"{short_date(task.due_date)} · {due_phrase(task.due_date, self._today)}")
        else:
            bits.append("no due date")
        self.lbl_meta.setText("  ·  ".join(bits))

        preview = self._preview_text(task)
        self.lbl_preview.setText(preview)
        self.lbl_preview.setVisible(bool(preview) and not self._compact)

        self._suppress_status_signal = True
        self.cmb_status.setCurrentText(
            task.status if task.status in STATUSES else STATUSES[0]
        )
        self._suppress_status_signal = False

        self.btn_done.setVisible(not task.is_complete)
        self._apply_colors()
        tip = [task.title or "(untitled)"]
        if task.project:
            tip.append(f"Project: {task.project}")
        tip.append(f"Status: {task.status}")
        if task.due_date:
            tip.append(f"Due: {task.due_date.isoformat()} ({due_phrase(task.due_date, self._today)})")
        tip.append("Double-click to open")
        self.setToolTip("\n".join(tip))

    @staticmethod
    def _preview_text(task: Task) -> str:
        body = (task.note_plain or html_to_text(task.note_html)).strip()
        if not body:
            return ""
        first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
        return first[:90] + ("…" if len(first) > 90 else "")

    def background_color(self) -> str:
        if self.task.is_complete:
            return colormod.normalize_hex(self._done_color)
        return colormod.color_for(
            self.task.due_date, self._bands, self._today, self._no_due_color
        )

    def _apply_colors(self) -> None:
        bg = self.background_color()
        fg = colormod.text_color_for(bg)
        dim = colormod.mix(fg, bg, 0.35)
        hover = colormod.mix(bg, fg, 0.10)
        border = colormod.mix(bg, "#000000", 0.22)
        control_bg = colormod.mix(bg, fg, 0.14)

        self.setStyleSheet(
            f"""
            QFrame#TaskCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 7px;
            }}
            QFrame#TaskCard:hover {{ background: {hover}; }}
            QFrame#TaskCard QLabel {{ color: {fg}; background: transparent; }}
            QFrame#TaskCard QToolButton {{
                color: {fg}; background: transparent;
                border: 1px solid {border}; border-radius: 4px;
            }}
            QFrame#TaskCard QToolButton:hover {{ background: {control_bg}; }}
            QFrame#TaskCard QComboBox {{
                color: {fg}; background: {control_bg};
                border: 1px solid {border}; border-radius: 4px;
                padding: 1px 4px;
            }}
            QFrame#TaskCard QComboBox::drop-down {{ border: none; width: 14px; }}
            """
        )
        self.lbl_preview.setStyleSheet(f"color: {dim}; background: transparent;")
        self.lbl_meta.setStyleSheet(f"color: {dim}; background: transparent;")

    # -- interaction ----------------------------------------------------
    def _on_status_changed(self, text: str) -> None:
        if self._suppress_status_signal or self.task.id is None:
            return
        if text != self.task.status:
            self.status_changed.emit(self.task.id, text)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.task.id is not None:
            self.edit_requested.emit(self.task.id)
        super().mouseDoubleClickEvent(event)

    def _show_menu(self, pos) -> None:
        if self.task.id is None:
            return
        menu = QMenu(self)
        act_edit = QAction("Open / edit", menu)
        act_edit.triggered.connect(lambda: self.edit_requested.emit(self.task.id))
        menu.addAction(act_edit)

        menu.addSeparator()
        for status in STATUSES:
            act = QAction(f"Set status: {status}", menu)
            act.setEnabled(status != self.task.status)
            act.triggered.connect(
                lambda _checked=False, s=status: self.status_changed.emit(self.task.id, s)
            )
            menu.addAction(act)

        menu.addSeparator()
        act_dup = QAction("Duplicate", menu)
        act_dup.triggered.connect(lambda: self.duplicate_requested.emit(self.task.id))
        menu.addAction(act_dup)

        act_archive = QAction(
            "Restore to panel" if self.task.archived else "Hide from panel (keep)", menu
        )
        act_archive.triggered.connect(lambda: self.archive_requested.emit(self.task.id))
        menu.addAction(act_archive)

        menu.addSeparator()
        act_del = QAction("Delete permanently…", menu)
        act_del.triggered.connect(lambda: self.delete_requested.emit(self.task.id))
        menu.addAction(act_del)

        menu.exec(self.mapToGlobal(pos))
