"""Rich-text note editor with clipboard image support.

Qt's QTextEdit already handles rich text and will happily display a pasted
image, but by default that image lives only inside the in-memory document and
is lost on save.  :class:`NoteEdit` intercepts the paste, writes the bytes to
the :class:`~stickytasks.imagestore.ImageStore`, and inserts a reference by
filename.  :meth:`NoteEdit.loadResource` resolves those filenames back to disk
when a note is reopened, which is what makes images survive a restart.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QImage,
    QKeySequence,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..imagestore import ImageStore
from .icons import clear_format_icon, highlight_icon, image_icon

# Pasted screenshots are routinely 2000+ px wide.  Displaying them at native
# size makes the note unusable, so the *displayed* width is capped while the
# stored file keeps its full resolution.
MAX_DISPLAY_WIDTH = 560


class NoteEdit(QTextEdit):
    def __init__(self, store: ImageStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._store = store
        self.setAcceptRichText(True)
        self.setTabChangesFocus(False)
        self.setPlaceholderText("Notes — paste screenshots directly, Ctrl+V")
        self.document().setDocumentMargin(8)

    # -- clipboard ------------------------------------------------------
    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802 (Qt naming)
        if source.hasImage() or self._image_urls(source):
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802 (Qt naming)
        if source.hasImage():
            image = QImage(source.imageData())
            if not image.isNull():
                self.insert_image(image)
                return

        urls = self._image_urls(source)
        if urls:
            inserted = False
            for path in urls:
                image = QImage(str(path))
                if not image.isNull():
                    self.insert_image(image)
                    inserted = True
            if inserted:
                return

        super().insertFromMimeData(source)

    @staticmethod
    def _image_urls(source) -> list[Path]:
        """Local image files named by a drag or clipboard payload."""
        if not source.hasUrls():
            return []
        out: list[Path] = []
        for url in source.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
                out.append(path)
        return out

    # -- images ---------------------------------------------------------
    def insert_image(self, image: QImage) -> None:
        """Store ``image`` on disk and reference it at the cursor."""
        data = self._encode_png(image)
        if not data:
            return
        try:
            name = self._store.save_bytes(data, ".png")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not store image", str(exc))
            return

        fmt = QTextImageFormat()
        fmt.setName(name)
        if image.width() > MAX_DISPLAY_WIDTH:
            scale = MAX_DISPLAY_WIDTH / image.width()
            fmt.setWidth(MAX_DISPLAY_WIDTH)
            fmt.setHeight(round(image.height() * scale))
        else:
            fmt.setWidth(image.width())
            fmt.setHeight(image.height())

        # Register under the bare name too, so the image paints immediately
        # rather than only after the note is saved and reopened.
        self.document().addResource(
            QTextDocument.ResourceType.ImageResource, QUrl(name), image
        )
        self.textCursor().insertImage(fmt)

    @staticmethod
    def _encode_png(image: QImage) -> bytes:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        ok = image.save(buffer, "PNG")
        buffer.close()
        return bytes(buffer.data()) if ok else b""

    def loadResource(self, type_: int, url: QUrl):  # noqa: N802 (Qt naming)
        if type_ == QTextDocument.ResourceType.ImageResource.value:
            name = Path(url.toString()).name
            path = self._store.path_for(name)
            if path.is_file():
                image = QImage(str(path))
                if not image.isNull():
                    return image
        return super().loadResource(type_, url)

    def insert_image_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Insert image", "", "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Insert image", "That file could not be read as an image.")
            return
        self.insert_image(image)


class NoteEditor(QWidget):
    """A :class:`NoteEdit` plus its formatting toolbar."""

    def __init__(self, store: ImageStore, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.edit = NoteEdit(store, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self.edit, 1)

        self.edit.currentCharFormatChanged.connect(self._sync_toolbar)

    # -- toolbar --------------------------------------------------------
    def _build_toolbar(self) -> QWidget:
        bar = QWidget(self)
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(2)

        self.btn_bold = self._toggle("B", "Bold (Ctrl+B)", self._toggle_bold)
        self.btn_italic = self._toggle("I", "Italic (Ctrl+I)", self._toggle_italic)
        self.btn_underline = self._toggle("U", "Underline (Ctrl+U)", self._toggle_underline)
        self.btn_strike = self._toggle("S", "Strikethrough", self._toggle_strike)

        font = self.btn_bold.font()
        font.setBold(True)
        self.btn_bold.setFont(font)
        italic_font = self.btn_italic.font()
        italic_font.setItalic(True)
        self.btn_italic.setFont(italic_font)
        underline_font = self.btn_underline.font()
        underline_font.setUnderline(True)
        self.btn_underline.setFont(underline_font)
        strike_font = self.btn_strike.font()
        strike_font.setStrikeOut(True)
        self.btn_strike.setFont(strike_font)

        for b in (self.btn_bold, self.btn_italic, self.btn_underline, self.btn_strike):
            row.addWidget(b)

        row.addSpacing(8)
        row.addWidget(self._button("•", "Bullet list", self._bullet_list))
        row.addWidget(self._button("1.", "Numbered list", self._numbered_list))
        row.addSpacing(8)
        row.addWidget(self._button("A", "Text colour", self._pick_text_color))
        row.addWidget(self._icon_button(highlight_icon(), "Highlight", self._pick_highlight))
        row.addSpacing(8)
        row.addWidget(
            self._icon_button(
                image_icon(), "Insert image from file", self.edit.insert_image_from_file
            )
        )
        row.addWidget(
            self._icon_button(clear_format_icon(), "Clear formatting", self._clear_format)
        )
        row.addStretch(1)

        self._install_shortcuts()
        return bar

    def _button(self, text: str, tip: str, slot) -> QToolButton:
        b = QToolButton(self)
        b.setText(text)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setFixedSize(QSize(26, 24))
        b.clicked.connect(slot)
        return b

    def _icon_button(self, icon, tip: str, slot) -> QToolButton:
        b = self._button("", tip, slot)
        b.setIcon(icon)
        b.setIconSize(QSize(18, 18))
        return b

    def _toggle(self, text: str, tip: str, slot) -> QToolButton:
        b = self._button(text, tip, slot)
        b.setCheckable(True)
        return b

    def _install_shortcuts(self) -> None:
        for seq, slot in (
            (QKeySequence.StandardKey.Bold, self._toggle_bold),
            (QKeySequence.StandardKey.Italic, self._toggle_italic),
            (QKeySequence.StandardKey.Underline, self._toggle_underline),
        ):
            action = QAction(self)
            action.setShortcut(seq)
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(slot)
            self.addAction(action)

    # -- formatting -----------------------------------------------------
    def _merge(self, fmt: QTextCharFormat) -> None:
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self.edit.mergeCurrentCharFormat(fmt)
        self.edit.setFocus()

    def _toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        on = self.edit.fontWeight() != QFont.Weight.Bold
        fmt.setFontWeight(QFont.Weight.Bold if on else QFont.Weight.Normal)
        self._merge(fmt)

    def _toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.edit.fontItalic())
        self._merge(fmt)

    def _toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.edit.fontUnderline())
        self._merge(fmt)

    def _toggle_strike(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontStrikeOut(not self.edit.currentCharFormat().fontStrikeOut())
        self._merge(fmt)

    def _apply_list(self, style: QTextListFormat.Style) -> None:
        cursor = self.edit.textCursor()
        cursor.beginEditBlock()
        current = cursor.currentList()
        if current and current.format().style() == style:
            # Toggle off: lift the block back out of the list.
            block_fmt = cursor.blockFormat()
            block_fmt.setIndent(0)
            cursor.setBlockFormat(block_fmt)
            current.remove(cursor.block())
        else:
            fmt = QTextListFormat()
            fmt.setStyle(style)
            fmt.setIndent(1)
            cursor.createList(fmt)
        cursor.endEditBlock()
        self.edit.setFocus()

    def _bullet_list(self) -> None:
        self._apply_list(QTextListFormat.Style.ListDisc)

    def _numbered_list(self) -> None:
        self._apply_list(QTextListFormat.Style.ListDecimal)

    def _pick_text_color(self) -> None:
        color = QColorDialog.getColor(self.edit.textColor(), self, "Text colour")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self._merge(fmt)

    def _pick_highlight(self) -> None:
        color = QColorDialog.getColor(QColor("#fff59d"), self, "Highlight colour")
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self._merge(fmt)

    def _clear_format(self) -> None:
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.setCharFormat(QTextCharFormat())
        self.edit.setFocus()

    def _sync_toolbar(self, fmt: QTextCharFormat) -> None:
        self.btn_bold.setChecked(fmt.fontWeight() >= QFont.Weight.Bold)
        self.btn_italic.setChecked(fmt.fontItalic())
        self.btn_underline.setChecked(fmt.fontUnderline())
        self.btn_strike.setChecked(fmt.fontStrikeOut())

    # -- content --------------------------------------------------------
    def set_html(self, html: str) -> None:
        self.edit.setHtml(html or "")

    def html(self) -> str:
        return self.edit.toHtml()

    def plain_text(self) -> str:
        return self.edit.toPlainText()

    def is_empty(self) -> bool:
        return not self.edit.toPlainText().strip() and "<img" not in self.edit.toHtml().lower()
