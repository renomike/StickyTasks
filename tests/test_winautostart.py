"""Registering StickyTasks to start when Windows signs in.

The round-trip tests point RUN_KEY at a scratch key of our own, so nothing here
touches the real Run key the machine actually starts from.
"""

import sys
from pathlib import Path

import pytest

from stickytasks import winautostart

SCRATCH_KEY = r"Software\StickyTasks\pytest-autostart"

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="there is no registry here")
other_platforms = pytest.mark.skipif(sys.platform == "win32", reason="the quiet path is elsewhere")


@pytest.fixture
def scratch_key(monkeypatch):
    """Point the module at a key we own, and take it away again afterwards."""
    monkeypatch.setattr(winautostart, "RUN_KEY", SCRATCH_KEY)
    yield SCRATCH_KEY

    import winreg

    for key in (SCRATCH_KEY, str(Path(SCRATCH_KEY).parent)):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except OSError:
            pass  # already gone, or the parent still holds something of the user's


def test_launch_command_quotes_what_it_runs():
    """Both halves are quoted: a user's path routinely has spaces in it."""
    command = winautostart.launch_command()
    assert command.startswith('"')
    assert command.count('"') in (2, 4)


def test_launch_command_targets_something_that_can_start_the_app():
    command = winautostart.launch_command()
    assert "run_stickytasks.py" in command or "-m stickytasks" in command


@windows_only
def test_prefers_the_interpreter_that_shows_no_console():
    exe = Path(sys.executable)
    if not exe.with_name(exe.name.replace("python", "pythonw", 1)).exists():
        pytest.skip("no pythonw.exe beside this interpreter")
    assert "pythonw" in winautostart.launch_command()


@windows_only
def test_enabling_then_disabling_leaves_no_trace(scratch_key):
    assert not winautostart.is_enabled()

    assert winautostart.enable()
    assert winautostart.is_enabled()
    assert winautostart.registered_command() == winautostart.launch_command()

    assert winautostart.disable()
    assert not winautostart.is_enabled()
    assert winautostart.registered_command() is None


@windows_only
def test_disabling_what_was_never_enabled_is_success(scratch_key):
    """The caller asked for "not registered", and that is the state it is in."""
    assert winautostart.disable()
    assert winautostart.disable()


@windows_only
def test_set_enabled_follows_the_flag(scratch_key):
    winautostart.set_enabled(True)
    assert winautostart.is_enabled()
    winautostart.set_enabled(False)
    assert not winautostart.is_enabled()


@windows_only
def test_enabling_twice_refreshes_rather_than_duplicates(scratch_key):
    """One value per app: re-enabling rewrites it, e.g. after a move."""
    winautostart.enable()
    winautostart.enable()
    assert winautostart.registered_command() == winautostart.launch_command()
    assert winautostart.disable()
    assert not winautostart.is_enabled()


@other_platforms
def test_degrades_quietly_where_there_is_no_run_key():
    assert not winautostart.is_available()
    assert not winautostart.is_enabled()
    assert not winautostart.enable()
    assert not winautostart.disable()
    assert winautostart.registered_command() is None
