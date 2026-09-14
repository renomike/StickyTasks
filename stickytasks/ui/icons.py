"""Icons drawn at runtime.

Everything the UI needs is painted with QPainter rather than loaded from disk,
so the app ships as pure Python with no binary assets to lose or mis-path.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap


def app_pixmap(size: int = 64) -> QPixmap:
    """The StickyTasks mark: a rounded note with a red/amber/green edge."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    body = QRectF(size * 0.08, size * 0.08, size * 0.84, size * 0.84)
    path = QPainterPath()
    path.addRoundedRect(body, size * 0.14, size * 0.14)
    p.fillPath(path, QBrush(QColor("#2b2f36")))

    stripe_w = size * 0.16
    stripes = ["#e53935", "#fb8c00", "#43a047"]
    p.setClipPath(path)
    for i, color in enumerate(stripes):
        top = body.top() + body.height() * (i / len(stripes))
        p.fillRect(
            QRectF(body.left(), top, stripe_w, body.height() / len(stripes)),
            QColor(color),
        )
    # A couple of "text" rules to read as a note at small sizes.
    p.setBrush(QColor("#9aa4b2"))
    p.setPen(Qt.PenStyle.NoPen)
    line_x = body.left() + stripe_w + size * 0.08
    for i in range(3):
        y = body.top() + size * 0.22 + i * size * 0.18
        w = body.right() - line_x - size * (0.08 if i < 2 else 0.28)
        p.drawRoundedRect(QRectF(line_x, y, w, size * 0.075), size * 0.03, size * 0.03)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(s))
    return icon


def glyph_icon(character: str, color: str = "#e6e6e6", size: int = 20) -> QIcon:
    """Render a single character as an icon, centred and crisp."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont()
    font.setPixelSize(int(size * 0.72))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, character)
    p.end()
    return QIcon(pm)


def swatch_icon(color: str, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor("#00000055"))
    p.setBrush(QColor(color))
    p.drawRoundedRect(1, 1, size - 2, size - 2, 3, 3)
    p.end()
    return QIcon(pm)


def highlight_icon(size: int = 20, color: str = "#e6e6e6") -> QIcon:
    """A marker stroke over a bar, for the highlight button."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#f7d94c"))
    p.drawRoundedRect(QRectF(size * 0.15, size * 0.62, size * 0.7, size * 0.2), 2, 2)
    font = QFont()
    font.setPixelSize(int(size * 0.62))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(
        QRectF(0, -size * 0.12, size, size),
        Qt.AlignmentFlag.AlignCenter,
        "A",
    )
    p.end()
    return QIcon(pm)


def image_icon(size: int = 20, color: str = "#e6e6e6") -> QIcon:
    """A picture frame with a hill and a sun."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    frame = QRectF(size * 0.14, size * 0.2, size * 0.72, size * 0.6)
    pen = p.pen()
    pen.setColor(QColor(color))
    pen.setWidthF(max(1.0, size * 0.08))
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(frame, 2, 2)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(size * 0.24, size * 0.3, size * 0.14, size * 0.14))
    hill = QPainterPath()
    hill.moveTo(frame.left() + size * 0.04, frame.bottom() - size * 0.05)
    hill.lineTo(frame.center().x(), frame.top() + size * 0.22)
    hill.lineTo(frame.right() - size * 0.04, frame.bottom() - size * 0.05)
    hill.closeSubpath()
    p.fillPath(hill, QBrush(QColor(color)))
    p.end()
    return QIcon(pm)


def clear_format_icon(size: int = 20, color: str = "#e6e6e6") -> QIcon:
    """An 'A' struck through, for clearing character formatting."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont()
    font.setPixelSize(int(size * 0.72))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "A")

    pen = p.pen()
    pen.setColor(QColor("#ef5350"))
    pen.setWidthF(max(1.2, size * 0.1))
    p.setPen(pen)
    p.drawLine(int(size * 0.16), int(size * 0.82), int(size * 0.84), int(size * 0.2))
    p.end()
    return QIcon(pm)
