import pytest

from stickytasks.imagestore import ImageStore

PNG = b"\x89PNG\r\n\x1a\n" + b"fake image payload"


def test_same_bytes_stored_once(tmp_path):
    store = ImageStore(tmp_path)
    a = store.save_bytes(PNG)
    b = store.save_bytes(PNG)
    assert a == b
    assert len(list(tmp_path.iterdir())) == 1


def test_different_bytes_get_different_names(tmp_path):
    store = ImageStore(tmp_path)
    assert store.save_bytes(PNG) != store.save_bytes(PNG + b"x")


def test_unknown_suffix_normalised_to_png(tmp_path):
    store = ImageStore(tmp_path)
    assert store.save_bytes(PNG, ".exe").endswith(".png")


def test_empty_payload_rejected(tmp_path):
    with pytest.raises(ValueError):
        ImageStore(tmp_path).save_bytes(b"")


def test_path_for_cannot_escape_the_store(tmp_path):
    store = ImageStore(tmp_path)
    escaped = store.path_for("../../etc/passwd")
    assert escaped.parent == tmp_path
    assert escaped.name == "passwd"


def test_purge_removes_only_unreferenced(tmp_path):
    store = ImageStore(tmp_path)
    keep = store.save_bytes(PNG)
    drop = store.save_bytes(PNG + b"other")

    assert store.purge_unreferenced({keep}) == 1
    assert store.exists(keep)
    assert not store.exists(drop)


def test_purge_ignores_non_image_files(tmp_path):
    store = ImageStore(tmp_path)
    (tmp_path / "notes.txt").write_text("leave me alone")
    store.purge_unreferenced(set())
    assert (tmp_path / "notes.txt").exists()
