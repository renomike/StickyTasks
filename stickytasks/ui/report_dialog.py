"""Build a review-season report from a date range and save or copy it."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import report as reportmod
from ..db import Database
from ..paths import exports_dir
from .theme import panel_stylesheet


class ReportDialog(QDialog):
    def __init__(self, db: Database, font_size: int = 10, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._db = db
        self.setWindowTitle("Task report")
        self.resize(860, 700)
        self.setStyleSheet(panel_stylesheet(font_size))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)
        root.addWidget(self._controls())

        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        mono = QFont("Consolas" if _has_consolas() else "monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        mono.setPointSize(max(8, font_size - 1))
        self.preview.setFont(mono)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        root.addWidget(self.preview, 1)

        row = QHBoxLayout()
        self.lbl_status = QLabel("", self)
        self.lbl_status.setObjectName("FooterLabel")
        row.addWidget(self.lbl_status, 1)

        btn_copy = QPushButton("Copy to clipboard", self)
        btn_copy.clicked.connect(self._copy)
        row.addWidget(btn_copy)

        btn_save = QPushButton("Save to file…", self)
        btn_save.clicked.connect(self._save)
        row.addWidget(btn_save)

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.reject)
        row.addWidget(btn_close)
        root.addLayout(row)

        self._apply_preset(0)
        self.refresh()

    # -- controls -------------------------------------------------------
    def _controls(self) -> QWidget:
        box = QGroupBox("Period and contents", self)
        outer = QHBoxLayout(box)
        outer.setSpacing(18)

        left = QFormLayout()
        left.setSpacing(7)

        self.cmb_preset = QComboBox(box)
        self._presets = reportmod.preset_ranges()
        for name, _s, _e in self._presets:
            self.cmb_preset.addItem(name)
        self.cmb_preset.addItem("Custom")
        self.cmb_preset.currentIndexChanged.connect(self._apply_preset)
        left.addRow("Preset", self.cmb_preset)

        self.dt_from = QDateEdit(box)
        self.dt_from.setCalendarPopup(True)
        self.dt_from.setDisplayFormat("yyyy-MM-dd")
        self.dt_from.dateChanged.connect(self._on_date_edited)
        left.addRow("From", self.dt_from)

        self.dt_to = QDateEdit(box)
        self.dt_to.setCalendarPopup(True)
        self.dt_to.setDisplayFormat("yyyy-MM-dd")
        self.dt_to.dateChanged.connect(self._on_date_edited)
        left.addRow("To", self.dt_to)

        self.ed_title = QLineEdit("Task Report", box)
        left.addRow("Report title", self.ed_title)
        outer.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(5)

        self.rb_completed = QRadioButton("Only tasks completed in the period", box)
        self.rb_completed.setChecked(True)
        self.rb_activity = QRadioButton("Everything I touched in the period", box)
        right.addWidget(self.rb_completed)
        right.addWidget(self.rb_activity)

        right.addSpacing(6)
        self.rb_markdown = QRadioButton("Markdown", box)
        self.rb_markdown.setChecked(True)
        self.rb_text = QRadioButton("Plain text", box)
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:", box))
        fmt_row.addWidget(self.rb_markdown)
        fmt_row.addWidget(self.rb_text)
        fmt_row.addStretch(1)
        right.addLayout(fmt_row)

        self.chk_notes = QCheckBox("Include note text", box)
        self.chk_notes.setChecked(True)
        self.chk_history = QCheckBox("Include status history", box)
        self.chk_group = QCheckBox("Group by project", box)
        self.chk_group.setChecked(True)
        for w in (self.chk_notes, self.chk_history, self.chk_group):
            right.addWidget(w)

        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel("Trim notes to", box))
        self.spn_limit = QSpinBox(box)
        self.spn_limit.setRange(0, 20000)
        self.spn_limit.setSingleStep(100)
        self.spn_limit.setValue(0)
        self.spn_limit.setSpecialValueText("no limit")
        self.spn_limit.setSuffix(" chars")
        limit_row.addWidget(self.spn_limit)
        limit_row.addStretch(1)
        right.addLayout(limit_row)
        right.addStretch(1)
        outer.addLayout(right, 1)

        for w in (
            self.rb_completed, self.rb_activity, self.rb_markdown, self.rb_text,
            self.chk_notes, self.chk_history, self.chk_group,
        ):
            w.toggled.connect(self.refresh)
        self.spn_limit.valueChanged.connect(self.refresh)
        self.ed_title.textChanged.connect(self.refresh)
        return box

    # -- behaviour ------------------------------------------------------
    def _apply_preset(self, index: int) -> None:
        if index < 0 or index >= len(self._presets):
            return  # "Custom" — leave the dates alone
        _name, start, end = self._presets[index]
        for widget, value in ((self.dt_from, start), (self.dt_to, end)):
            widget.blockSignals(True)
            widget.setDate(QDate(value))
            widget.blockSignals(False)
        self.refresh()

    def _on_date_edited(self) -> None:
        if self.cmb_preset.currentIndex() < len(self._presets):
            self.cmb_preset.blockSignals(True)
            self.cmb_preset.setCurrentIndex(self.cmb_preset.count() - 1)  # Custom
            self.cmb_preset.blockSignals(False)
        self.refresh()

    def options(self) -> reportmod.ReportOptions:
        start: date = self.dt_from.date().toPython()
        end: date = self.dt_to.date().toPython()
        if end < start:
            start, end = end, start
        return reportmod.ReportOptions(
            start=start,
            end=end,
            scope=reportmod.SCOPE_ACTIVITY if self.rb_activity.isChecked() else reportmod.SCOPE_COMPLETED,
            fmt=reportmod.FORMAT_TEXT if self.rb_text.isChecked() else reportmod.FORMAT_MARKDOWN,
            include_notes=self.chk_notes.isChecked(),
            include_history=self.chk_history.isChecked(),
            group_by_project=self.chk_group.isChecked(),
            title=self.ed_title.text().strip() or "Task Report",
            note_char_limit=self.spn_limit.value(),
        )

    def refresh(self) -> None:
        opts = self.options()
        try:
            text = reportmod.generate(self._db, opts)
        except Exception as exc:  # keep the dialog usable if a query fails
            self.preview.setPlainText(f"Could not build the report:\n{exc}")
            self.lbl_status.setText("Error")
            return
        self.preview.setPlainText(text)
        count = len(reportmod.collect(self._db, opts))
        self.lbl_status.setText(
            f"{count} task(s) · {opts.start.isoformat()} to {opts.end.isoformat()}"
        )

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.preview.toPlainText())
        self.lbl_status.setText("Copied to clipboard.")

    def _save(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        opts = self.options()
        ext = "md" if opts.fmt == reportmod.FORMAT_MARKDOWN else "txt"
        default = exports_dir() / f"task-report-{opts.start}-to-{opts.end}.{ext}"
        filters = (
            "Markdown (*.md);;Text (*.txt)"
            if ext == "md"
            else "Text (*.txt);;Markdown (*.md)"
        )
        path, _ = QFileDialog.getSaveFileName(self, "Save report", str(default), filters)
        if not path:
            return
        try:
            Path(path).write_text(self.preview.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self.lbl_status.setText(f"Saved to {path}")


def _has_consolas() -> bool:
    from PySide6.QtGui import QFontDatabase

    return "Consolas" in QFontDatabase.families()
