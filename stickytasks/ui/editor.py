"""The task editor dialog: fields on top, rich-text note below."""

from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .. import colors as colormod
from ..humanize import due_phrase, stamp
from ..imagestore import ImageStore
from ..models import STATUSES, Task
from .elidedlabel import ElidedLabel
from .richtext import NoteEditor
from .theme import panel_stylesheet


class TaskEditor(QDialog):
    def __init__(
        self,
        task: Task,
        projects: Sequence[str],
        store: ImageStore,
        bands: Sequence[colormod.Band],
        no_due_color: str,
        font_size: int = 10,
        history: Optional[Sequence] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._task = task
        self._bands = list(bands)
        self._no_due_color = no_due_color

        self.setWindowTitle("New task" if task.id is None else "Edit task")
        self.setModal(True)
        self.resize(580, 640)
        self.setStyleSheet(panel_stylesheet(font_size))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.ed_title = QLineEdit(task.title, self)
        self.ed_title.setPlaceholderText("What needs doing?")
        form.addRow("Title", self.ed_title)

        self.cmb_project = QComboBox(self)
        self.cmb_project.setEditable(True)
        self.cmb_project.addItem("")
        self.cmb_project.addItems([p for p in projects if p])
        self.cmb_project.setCurrentText(task.project)
        self.cmb_project.lineEdit().setPlaceholderText("Project or category (optional)")
        completer = QCompleter([p for p in projects if p], self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.cmb_project.setCompleter(completer)
        form.addRow("Project", self.cmb_project)

        due_row = QHBoxLayout()
        due_row.setSpacing(8)
        self.dt_due = QDateEdit(self)
        self.dt_due.setCalendarPopup(True)
        self.dt_due.setDisplayFormat("yyyy-MM-dd")
        self.dt_due.setDate(QDate(task.due_date) if task.due_date else QDate.currentDate())
        self.dt_due.dateChanged.connect(self._update_due_hint)
        self.dt_due.setFixedWidth(130)
        due_row.addWidget(self.dt_due, 0)

        self.chk_no_due = QCheckBox("No due date", self)
        self.chk_no_due.setChecked(task.due_date is None)
        self.chk_no_due.toggled.connect(self._on_no_due_toggled)
        due_row.addWidget(self.chk_no_due, 0)

        self.lbl_due_hint = ElidedLabel("", parent=self)
        self.lbl_due_hint.setObjectName("FooterLabel")
        due_row.addWidget(self.lbl_due_hint, 1)
        form.addRow("Due", due_row)

        self.cmb_status = QComboBox(self)
        self.cmb_status.addItems(list(STATUSES))
        self.cmb_status.setCurrentText(task.status if task.status in STATUSES else STATUSES[0])
        self.cmb_status.currentTextChanged.connect(self._update_due_hint)
        form.addRow("Status", self.cmb_status)
        root.addLayout(form)

        self.note = NoteEditor(store, self)
        self.note.set_html(task.note_html)
        root.addWidget(self.note, 1)

        if history:
            root.addWidget(self._history_strip(history))

        buttons = QDialogButtonBox(self)
        self.btn_save = buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_save.setDefault(True)
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._accept)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self._accept)

        self._on_no_due_toggled(self.chk_no_due.isChecked())
        self.ed_title.setFocus()
        self.ed_title.selectAll()

    # -- helpers --------------------------------------------------------
    def _history_strip(self, history: Sequence) -> QWidget:
        box = QFrame(self)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        head = QLabel("History", box)
        head.setObjectName("FooterLabel")
        layout.addWidget(head)
        for ev in list(history)[-4:]:
            arrow = (
                f"{ev.from_status} → {ev.to_status}" if ev.from_status
                else f"created as {ev.to_status}"
            )
            line = QLabel(f"{stamp(ev.changed_at)}   {arrow}", box)
            line.setObjectName("FooterLabel")
            layout.addWidget(line)
        return box

    def _on_no_due_toggled(self, no_due: bool) -> None:
        self.dt_due.setEnabled(not no_due)
        self._update_due_hint()

    def _update_due_hint(self, *_args) -> None:
        if self.chk_no_due.isChecked():
            self.lbl_due_hint.setText("")
            self.lbl_due_hint.setStyleSheet("")
            return
        due = self.dt_due.date().toPython()
        color = colormod.color_for(due, self._bands, None, self._no_due_color)
        label = colormod.label_for(due, self._bands)
        self.lbl_due_hint.setText(f"{due_phrase(due)}  ·  {label}")
        self.lbl_due_hint.setStyleSheet(f"color: {color}; font-weight: 600;")

    # -- result ---------------------------------------------------------
    def _accept(self) -> None:
        if not self.ed_title.text().strip():
            QMessageBox.information(self, "Title required", "Give the task a title first.")
            self.ed_title.setFocus()
            return
        self.accept()

    def result_task(self) -> Task:
        """The edited task.  Only called after the dialog is accepted."""
        t = self._task
        t.title = self.ed_title.text().strip()
        t.project = self.cmb_project.currentText().strip()
        t.due_date = None if self.chk_no_due.isChecked() else self.dt_due.date().toPython()
        t.status = self.cmb_status.currentText()
        if self.note.is_empty():
            t.note_html = ""
            t.note_plain = ""
        else:
            t.note_html = self.note.html()
            t.note_plain = self.note.plain_text()
        return t
