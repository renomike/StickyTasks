"""The settings dialog's one piece of real logic: the sign-in checkbox.

Whether Windows starts the app is a registry entry, not a setting, so the box is
filled in from the registry and applied separately from the rest of the dialog's
result. These tests stand in for that module rather than touching the real key.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from stickytasks import winautostart  # noqa: E402
from stickytasks.config import Settings  # noqa: E402
from stickytasks.ui.settings_dialog import SettingsDialog  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def run_key(monkeypatch):
    """A stand-in for the Run key: `enabled` is what Windows would report."""
    state = {"available": True, "enabled": False}
    monkeypatch.setattr(winautostart, "is_available", lambda: state["available"])
    monkeypatch.setattr(winautostart, "is_enabled", lambda: state["enabled"])
    return state


@pytest.fixture
def dialog(qapp, run_key):
    def build():
        return SettingsDialog(Settings())

    return build


def test_the_box_shows_what_windows_has_registered(dialog, run_key):
    run_key["enabled"] = True
    assert dialog().chk_autostart.isChecked()


def test_leaving_the_box_alone_asks_for_nothing(dialog, run_key):
    run_key["enabled"] = True
    assert dialog().autostart_wanted() is None


def test_ticking_the_box_asks_for_registration(dialog):
    d = dialog()
    assert not d.chk_autostart.isChecked()
    d.chk_autostart.setChecked(True)
    assert d.autostart_wanted() is True


def test_unticking_the_box_asks_for_removal(dialog, run_key):
    run_key["enabled"] = True
    d = dialog()
    d.chk_autostart.setChecked(False)
    assert d.autostart_wanted() is False


def test_nothing_is_asked_for_where_there_is_no_run_key(dialog, run_key):
    run_key["available"] = False
    d = dialog()
    assert not d.chk_autostart.isEnabled()
    assert d.autostart_wanted() is None


def test_the_setting_file_keeps_no_second_opinion(dialog):
    """Only the registry decides, so settings.json must not carry a copy."""
    d = dialog()
    d.chk_autostart.setChecked(True)
    saved = d.result_settings().to_dict()
    assert not [k for k in saved if "start" in k and k != "start_hidden"]
