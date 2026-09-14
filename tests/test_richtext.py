"""Headless UI tests for the note editor.

These run under Qt's offscreen platform, so they exercise the real widgets
without needing a display.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6.QtCore import QMimeData, QUrl  # noqa: E402
from PySide6.QtGui import QColor, QImage, QTextDocument  # noqa: E402

from stickytasks.imagestore import ImageStore  # noqa: E402
from stickytasks.ui.richtext import MAX_DISPLAY_WIDTH, NoteEditor  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def editor(qapp, tmp_path):
    return NoteEditor(ImageStore(tmp_path / "images"))


def make_image(w=40, h=30, color="#3366cc") -> QImage:
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(QColor(color))
    return img


def test_pasted_image_is_written_to_disk(editor, tmp_path):
    editor.edit.insert_image(make_image())
    files = list((tmp_path / "images").glob("*.png"))
    assert len(files) == 1
    assert files[0].name in editor.html()


def test_image_is_referenced_by_bare_filename(editor):
    """The note must not embed an absolute path, or moving the folder breaks it."""
    editor.edit.insert_image(make_image())
    html = editor.html()
    assert 'src="' in html
    src = html.split('src="')[1].split('"')[0]
    assert "/" not in src and "\\" not in src


def test_oversized_image_is_displayed_scaled_but_stored_full_size(editor, tmp_path):
    editor.edit.insert_image(make_image(w=2000, h=1000))
    html = editor.html()
    assert f'width="{MAX_DISPLAY_WIDTH}"' in html
    stored = next((tmp_path / "images").glob("*.png"))
    assert QImage(str(stored)).width() == 2000  # original resolution kept


def test_image_survives_reopening_the_note(qapp, tmp_path):
    store = ImageStore(tmp_path / "images")
    first = NoteEditor(store)
    first.edit.insert_image(make_image())
    saved_html = first.html()

    reopened = NoteEditor(store)  # fresh document, nothing in memory
    reopened.set_html(saved_html)
    name = saved_html.split('src="')[1].split('"')[0]

    resolved = reopened.edit.loadResource(
        QTextDocument.ResourceType.ImageResource.value, QUrl(name)
    )
    assert isinstance(resolved, QImage)
    assert not resolved.isNull()


def test_identical_images_are_stored_once(editor, tmp_path):
    editor.edit.insert_image(make_image())
    editor.edit.insert_image(make_image())
    assert len(list((tmp_path / "images").glob("*.png"))) == 1


def test_paste_of_image_mime_is_accepted(editor):
    mime = QMimeData()
    mime.setImageData(make_image())
    assert editor.edit.canInsertFromMimeData(mime)
    editor.edit.insertFromMimeData(mime)
    assert "<img" in editor.html()


def test_paste_of_plain_text_still_works(editor):
    mime = QMimeData()
    mime.setText("just text")
    editor.edit.insertFromMimeData(mime)
    assert "just text" in editor.plain_text()


def test_image_file_drop_is_recognised(editor, tmp_path):
    src = tmp_path / "dropped.png"
    make_image(color="#00aa00").save(str(src))
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(src))])

    assert editor.edit.canInsertFromMimeData(mime)
    editor.edit.insertFromMimeData(mime)
    assert "<img" in editor.html()


def test_non_image_file_drop_is_not_treated_as_image(editor, tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("hello")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(src))])
    assert editor.edit._image_urls(mime) == []


def test_is_empty_accounts_for_image_only_notes(editor):
    assert editor.is_empty()
    editor.edit.insert_image(make_image())
    assert not editor.is_empty()


def test_bold_toggle_changes_format(editor):
    editor.edit.setPlainText("word")
    editor.edit.selectAll()
    editor._toggle_bold()
    assert "font-weight:700" in editor.html() or "<b" in editor.html().lower()
