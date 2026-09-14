"""A QLabel that shrinks instead of forcing its container wider.

A plain QLabel reports the full width of its text as its size hint.  Inside a
narrow docked panel that pushes the whole card past the viewport edge, which
clips the buttons on the far side.  This label reports a small minimum width and
elides its text to whatever room it is actually given.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    def __init__(
        self,
        text: str = "",
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._full_text = text
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(0)
        super().setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self._full_text = text or ""
        self._relayout()

    def full_text(self) -> str:
        return self._full_text

    def minimumSizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        # Anything narrower than an ellipsis is pointless; anything wider lets
        # the label dictate the panel's width, which is what we are avoiding.
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance("…"), fm.height())

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        fm = QFontMetrics(self.font())
        return QSize(min(fm.horizontalAdvance(self._full_text), 400), fm.height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt naming)
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        fm = QFontMetrics(self.font())
        width = max(0, self.width() - 2)
        super().setText(fm.elidedText(self._full_text, self._mode, width) if width else self._full_text)


class WrapLabel(QLabel):
    """A word-wrapping label that never forces its container wider."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(0)

    def minimumSizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance("…"), fm.height())
