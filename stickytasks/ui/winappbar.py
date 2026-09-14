"""Optional Windows AppBar registration.

Registering as an AppBar is what makes the desktop *reserve* the strip of screen
the panel occupies, so a maximised window stops at the panel's edge instead of
sliding underneath it.  There is no cross-platform equivalent, so this is a
Windows-only extra: everywhere else :func:`is_available` returns False and the
panel simply floats on top.

Implemented with ctypes against shell32 so there is no pywin32 dependency.
"""

from __future__ import annotations

import sys
from typing import Optional

ABM_NEW = 0x00000000
ABM_REMOVE = 0x00000001
ABM_QUERYPOS = 0x00000002
ABM_SETPOS = 0x00000003

ABE_LEFT = 0
ABE_TOP = 1
ABE_RIGHT = 2
ABE_BOTTOM = 3

_WM_APPBAR_CALLBACK = 0x0400 + 0x7A5  # WM_USER + arbitrary offset

_loaded = False
_shell32 = None
_APPBARDATA = None


def is_available() -> bool:
    """True only on Windows with shell32 loadable."""
    return _load()


def _load() -> bool:
    global _loaded, _shell32, _APPBARDATA
    if _loaded:
        return _shell32 is not None
    _loaded = True
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class APPBARDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uCallbackMessage", wintypes.UINT),
                ("uEdge", wintypes.UINT),
                ("rc", wintypes.RECT),
                ("lParam", wintypes.LPARAM),
            ]

        shell32 = ctypes.windll.shell32
        shell32.SHAppBarMessage.restype = ctypes.c_size_t
        shell32.SHAppBarMessage.argtypes = [wintypes.DWORD, ctypes.POINTER(APPBARDATA)]

        _shell32 = shell32
        _APPBARDATA = APPBARDATA
        return True
    except Exception:  # pragma: no cover - Windows-only path
        _shell32 = None
        return False


class AppBar:
    """Reserves a screen edge for one window handle.

    Every method is a no-op returning False when AppBar support is unavailable,
    so callers never need to branch on the platform.
    """

    def __init__(self, hwnd: int):
        self.hwnd = int(hwnd)
        self.registered = False
        self._edge = ABE_RIGHT

    def register(self) -> bool:
        if self.registered or not _load():
            return False
        import ctypes

        data = _APPBARDATA()
        data.cbSize = ctypes.sizeof(_APPBARDATA)
        data.hWnd = self.hwnd
        data.uCallbackMessage = _WM_APPBAR_CALLBACK
        ok = bool(_shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(data)))
        self.registered = ok
        return ok

    def reserve(self, edge: str, left: int, top: int, right: int, bottom: int) -> Optional[tuple]:
        """Ask the shell to reserve a rectangle.

        Returns the rectangle the shell actually granted, which may differ from
        the one requested if another AppBar (or the taskbar) already owns part
        of that edge.  Returns None when unavailable or not registered.
        """
        if not self.registered or not _load():
            return None
        import ctypes

        self._edge = ABE_LEFT if edge == "left" else ABE_RIGHT
        data = _APPBARDATA()
        data.cbSize = ctypes.sizeof(_APPBARDATA)
        data.hWnd = self.hwnd
        data.uEdge = self._edge
        data.rc.left, data.rc.top, data.rc.right, data.rc.bottom = left, top, right, bottom

        _shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(data))
        # QUERYPOS may shrink the span; re-assert our thickness against the edge.
        width = right - left
        if self._edge == ABE_RIGHT:
            data.rc.left = data.rc.right - width
        else:
            data.rc.right = data.rc.left + width
        _shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(data))
        return (data.rc.left, data.rc.top, data.rc.right, data.rc.bottom)

    def unregister(self) -> bool:
        if not self.registered or not _load():
            return False
        import ctypes

        data = _APPBARDATA()
        data.cbSize = ctypes.sizeof(_APPBARDATA)
        data.hWnd = self.hwnd
        _shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(data))
        self.registered = False
        return True
