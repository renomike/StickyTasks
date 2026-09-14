"""Settings: where the panel sits, how it looks, and the due-date colour bands."""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import colors as colormod
from ..colors import Band
from ..config import DOCK_LEFT, DOCK_RIGHT, Settings
from .icons import swatch_icon
from .theme import panel_stylesheet

COL_LABEL, COL_DAYS, COL_NOLIMIT, COL_COLOR = range(4)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._settings = settings
        self.setWindowTitle("StickyTasks settings")
        self.setModal(True)
        self.resize(620, 620)
        self.setStyleSheet(panel_stylesheet(settings.font_size))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        tabs = QTabWidget(self)
        tabs.addTab(self._placement_tab(), "Placement")
        tabs.addTab(self._appearance_tab(), "Appearance")
        tabs.addTab(self._colors_tab(), "Due-date colours")
        root.addWidget(tabs, 1)

        buttons = QDialogButtonBox(self)
        ok = buttons.addButton("Save", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setDefault(True)
        buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # -- placement ------------------------------------------------------
    def _placement_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        form = QFormLayout()
        form.setSpacing(8)

        self.cmb_monitor = QComboBox(page)
        for i, screen in enumerate(QGuiApplication.screens()):
            g = screen.geometry()
            primary = " (primary)" if screen is QGuiApplication.primaryScreen() else ""
            self.cmb_monitor.addItem(
                f"{i + 1}. {screen.name()} — {g.width()}×{g.height()}{primary}", i
            )
        if self._settings.monitor_index < self.cmb_monitor.count():
            self.cmb_monitor.setCurrentIndex(self._settings.monitor_index)
        form.addRow("Monitor", self.cmb_monitor)

        self.cmb_edge = QComboBox(page)
        self.cmb_edge.addItem("Right edge", DOCK_RIGHT)
        self.cmb_edge.addItem("Left edge", DOCK_LEFT)
        self.cmb_edge.setCurrentIndex(0 if self._settings.dock_edge == DOCK_RIGHT else 1)
        form.addRow("Dock to", self.cmb_edge)

        self.spn_width = QSpinBox(page)
        self.spn_width.setRange(220, 1200)
        self.spn_width.setSingleStep(10)
        self.spn_width.setSuffix(" px")
        self.spn_width.setValue(self._settings.panel_width)
        form.addRow("Panel width", self.spn_width)

        self.sld_opacity = QSlider(Qt.Orientation.Horizontal, page)
        self.sld_opacity.setRange(40, 100)
        self.sld_opacity.setValue(int(self._settings.opacity * 100))
        self.lbl_opacity = QLabel(f"{self.sld_opacity.value()}%", page)
        self.sld_opacity.valueChanged.connect(lambda v: self.lbl_opacity.setText(f"{v}%"))
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.sld_opacity, 1)
        opacity_row.addWidget(self.lbl_opacity, 0)
        form.addRow("Opacity", opacity_row)
        layout.addLayout(form)

        box = QGroupBox("Window behaviour", page)
        box_layout = QVBoxLayout(box)
        self.chk_on_top = QCheckBox("Keep on top of other windows", box)
        self.chk_on_top.setChecked(self._settings.always_on_top)
        box_layout.addWidget(self.chk_on_top)

        self.chk_reserve = QCheckBox("Reserve screen space (maximised windows stop at the panel)", box)
        self.chk_reserve.setChecked(self._settings.reserve_screen_space)
        box_layout.addWidget(self.chk_reserve)

        note = QLabel(
            "Reserving space uses the Windows AppBar API and works on Windows only. "
            "Left off, the panel simply floats above other windows and a maximised "
            "window slides underneath it.",
            box,
        )
        note.setObjectName("FooterLabel")
        note.setWordWrap(True)
        box_layout.addWidget(note)
        if sys.platform != "win32":
            self.chk_reserve.setEnabled(False)
            self.chk_reserve.setChecked(False)
            note.setText(note.text() + f"\n\nDisabled here: this is {sys.platform}, not Windows.")

        self.chk_start_hidden = QCheckBox("Start minimised to the system tray", box)
        self.chk_start_hidden.setChecked(self._settings.start_hidden)
        box_layout.addWidget(self.chk_start_hidden)
        layout.addWidget(box)
        layout.addStretch(1)
        return page

    # -- appearance -----------------------------------------------------
    def _appearance_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        form = QFormLayout()
        form.setSpacing(8)

        self.spn_font = QSpinBox(page)
        self.spn_font.setRange(7, 24)
        self.spn_font.setSuffix(" pt")
        self.spn_font.setValue(self._settings.font_size)
        form.addRow("Base font size", self.spn_font)

        self.chk_compact = QCheckBox("Compact cards (hide the note preview line)", page)
        self.chk_compact.setChecked(self._settings.compact_cards)
        form.addRow("", self.chk_compact)

        self.btn_no_due = self._color_button(self._settings.no_due_color)
        form.addRow("Colour for tasks with no due date", self.btn_no_due)

        self.btn_done_color = self._color_button(self._settings.done_color)
        form.addRow("Colour for completed tasks", self.btn_done_color)

        self.chk_confirm_delete = QCheckBox("Ask before deleting a task permanently", page)
        self.chk_confirm_delete.setChecked(self._settings.confirm_delete)
        form.addRow("", self.chk_confirm_delete)

        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _color_button(self, color: str) -> QPushButton:
        btn = QPushButton(colormod.normalize_hex(color), self)
        btn.setIcon(swatch_icon(color))
        btn.setProperty("color", colormod.normalize_hex(color))
        btn.clicked.connect(lambda: self._pick_color(btn))
        return btn

    def _pick_color(self, button: QPushButton) -> None:
        from PySide6.QtGui import QColor

        current = QColor(str(button.property("color")))
        chosen = QColorDialog.getColor(current, self, "Pick a colour")
        if chosen.isValid():
            value = chosen.name()
            button.setProperty("color", value)
            button.setText(value)
            button.setIcon(swatch_icon(value))

    # -- colour bands ---------------------------------------------------
    def _colors_tab(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)

        blurb = QLabel(
            "A task takes the colour of the first band its due date fits into, "
            "counting days from today. Negative numbers are overdue: a band with "
            "“Days ≤ -1” catches everything already past due. Exactly one band "
            "must be marked “no limit” — it catches everything further out.",
            page,
        )
        blurb.setWordWrap(True)
        blurb.setObjectName("FooterLabel")
        layout.addWidget(blurb)

        self.tbl_bands = QTableWidget(0, 4, page)
        self.tbl_bands.setHorizontalHeaderLabels(["Label", "Days ≤", "No limit", "Colour"])
        self.tbl_bands.verticalHeader().setVisible(False)
        header = self.tbl_bands.horizontalHeader()
        header.setSectionResizeMode(COL_LABEL, QHeaderView.ResizeMode.Stretch)
        for col in (COL_DAYS, COL_NOLIMIT, COL_COLOR):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tbl_bands, 1)

        for band in colormod.sort_bands(self._settings.bands):
            self._add_band_row(band)

        row = QHBoxLayout()
        btn_add = QPushButton("Add band", page)
        btn_add.clicked.connect(lambda: self._add_band_row(Band("New band", 30, "#8bc34a")))
        row.addWidget(btn_add)

        btn_remove = QPushButton("Remove selected", page)
        btn_remove.clicked.connect(self._remove_selected_band)
        row.addWidget(btn_remove)

        btn_reset = QPushButton("Reset to defaults", page)
        btn_reset.clicked.connect(self._reset_bands)
        row.addWidget(btn_reset)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    def _add_band_row(self, band: Band) -> None:
        r = self.tbl_bands.rowCount()
        self.tbl_bands.insertRow(r)
        self.tbl_bands.setItem(r, COL_LABEL, QTableWidgetItem(band.label))

        spin = QSpinBox(self.tbl_bands)
        spin.setRange(-3650, 3650)
        spin.setValue(band.max_days if band.max_days is not None else 0)
        spin.setEnabled(band.max_days is not None)
        self.tbl_bands.setCellWidget(r, COL_DAYS, spin)

        holder = QWidget(self.tbl_bands)
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk = QCheckBox(holder)
        chk.setChecked(band.max_days is None)
        chk.toggled.connect(lambda checked, s=spin: s.setEnabled(not checked))
        holder_layout.addWidget(chk)
        self.tbl_bands.setCellWidget(r, COL_NOLIMIT, holder)

        self.tbl_bands.setCellWidget(r, COL_COLOR, self._color_button(band.color))

    def _remove_selected_band(self) -> None:
        rows = sorted({i.row() for i in self.tbl_bands.selectedIndexes()}, reverse=True)
        if not rows:
            return
        if self.tbl_bands.rowCount() - len(rows) < 1:
            QMessageBox.information(self, "Colour bands", "Keep at least one band.")
            return
        for r in rows:
            self.tbl_bands.removeRow(r)

    def _reset_bands(self) -> None:
        self.tbl_bands.setRowCount(0)
        for band in colormod.default_bands():
            self._add_band_row(band)

    def _bands_from_table(self) -> list[Band]:
        bands: list[Band] = []
        for r in range(self.tbl_bands.rowCount()):
            item = self.tbl_bands.item(r, COL_LABEL)
            label = item.text().strip() if item else ""
            spin: QSpinBox = self.tbl_bands.cellWidget(r, COL_DAYS)  # type: ignore[assignment]
            holder = self.tbl_bands.cellWidget(r, COL_NOLIMIT)
            chk: QCheckBox = holder.findChild(QCheckBox)  # type: ignore[assignment]
            btn: QPushButton = self.tbl_bands.cellWidget(r, COL_COLOR)  # type: ignore[assignment]
            no_limit = bool(chk and chk.isChecked())
            bands.append(
                Band(
                    label=label or ("Later" if no_limit else f"Band {r + 1}"),
                    max_days=None if no_limit else spin.value(),
                    color=str(btn.property("color")),
                )
            )

        bands = colormod.sort_bands(bands)  # drops surplus no-limit rows
        if not any(b.max_days is None for b in bands):
            bands.append(Band("Later", None, colormod.DEFAULT_BANDS[-1].color))
        return bands

    # -- result ---------------------------------------------------------
    def result_settings(self) -> Settings:
        s = self._settings
        s.monitor_index = max(0, self.cmb_monitor.currentData() or 0)
        s.dock_edge = self.cmb_edge.currentData()
        s.panel_width = self.spn_width.value()
        s.opacity = self.sld_opacity.value() / 100.0
        s.always_on_top = self.chk_on_top.isChecked()
        s.reserve_screen_space = self.chk_reserve.isChecked() and sys.platform == "win32"
        s.start_hidden = self.chk_start_hidden.isChecked()

        s.font_size = self.spn_font.value()
        s.compact_cards = self.chk_compact.isChecked()
        s.no_due_color = str(self.btn_no_due.property("color"))
        s.done_color = str(self.btn_done_color.property("color"))
        s.confirm_delete = self.chk_confirm_delete.isChecked()

        s.bands = self._bands_from_table()
        return s
