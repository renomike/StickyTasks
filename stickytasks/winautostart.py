"""Optional "start when I sign in" registration on Windows.

Windows runs whatever it finds under the per-user Run key at sign-in, so turning
this on is a single registry value under HKEY_CURRENT_USER: no elevation, no
installer, and nothing that affects anyone else who uses the machine.

Deliberately *not* a field in settings.json.  The registry is the only thing
that decides whether Windows starts the app, and the entry can be switched off
from Task Manager's Startup tab without the app ever hearing about it, so a copy
in the settings file would be free to disagree with reality.  The checkbox reads
the registry every time it is shown instead.

Everywhere but Windows the whole module reports False and does nothing, so
callers never need to branch on the platform.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Module level so tests can point them somewhere harmless.
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "StickyTasks"


def _winreg():
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:  # pragma: no cover - Windows always has it
        return None
    return winreg


def is_available() -> bool:
    """True only on Windows, where there is a Run key to write to."""
    return _winreg() is not None


def launch_command() -> str:
    """The command line Windows should run at sign-in.

    Prefers pythonw.exe so signing in does not flash a console window, and
    points at run_stickytasks.py, which puts its own directory on sys.path and
    so does not care what the working directory is.
    """
    if getattr(sys, "frozen", False):  # packaged as a single executable
        return f'"{Path(sys.executable)}"'

    exe = Path(sys.executable)
    windowed = exe.with_name(exe.name.replace("python", "pythonw", 1))
    if windowed.exists():
        exe = windowed

    script = Path(__file__).resolve().parent.parent / "run_stickytasks.py"
    if script.exists():
        return f'"{exe}" "{script}"'
    return f'"{exe}" -m stickytasks'  # installed as a package, no script alongside


def registered_command() -> Optional[str]:
    """The command currently registered, or None if there is no entry."""
    winreg = _winreg()
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
    except OSError:  # missing key, missing value, or no read access
        return None
    return str(value) or None


def is_enabled() -> bool:
    return registered_command() is not None


def enable() -> bool:
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
    except OSError:
        return False
    return True


def disable() -> bool:
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        return True  # already gone is the outcome asked for
    except OSError:
        return False
    return True


def set_enabled(enabled: bool) -> bool:
    return enable() if enabled else disable()
