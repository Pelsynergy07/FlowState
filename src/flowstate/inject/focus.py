"""Remember the window (Windows) or app (macOS) that had focus when a
recording started, and bring it back before pasting.

The handle is opaque to callers: an HWND on Windows, a process id on macOS.
Implementations live in platform/<os>/focus.py.
"""

from __future__ import annotations

from .. import platform

_backend = platform.adapter("focus")

get_foreground_window = _backend.get_foreground_window
get_window_title = _backend.get_window_title
restore_foreground_window = _backend.restore_foreground_window
