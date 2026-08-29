"""Capture and restore the foreground window.

Windows rate-limits SetForegroundWindow so a background process can't just
steal focus at will; the AttachThreadInput trick (briefly sharing input
state with the target thread) is the standard, reliable workaround.
"""

from __future__ import annotations

import ctypes
import logging
import time

import win32api
import win32con
import win32gui
import win32process

logger = logging.getLogger("flowstate.inject")

_user32 = ctypes.windll.user32

_RESTORE_ATTEMPTS = 4
_RESTORE_RETRY_SECONDS = 0.05


def get_foreground_window() -> int:
    return win32gui.GetForegroundWindow()


def get_window_title(hwnd: int) -> str:
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return ""


def _attach(current_thread_id: int, other_thread_id: int) -> bool:
    if not other_thread_id or other_thread_id == current_thread_id:
        return False
    return bool(_user32.AttachThreadInput(current_thread_id, other_thread_id, True))


def restore_foreground_window(hwnd: int) -> bool:
    """Re-activates hwnd. Returns True if it ended up in the foreground.

    A single AttachThreadInput+SetForegroundWindow call can still lose to
    Windows' foreground-lock heuristic (SetForegroundWindow silently
    returns/raises without changing anything) if the currently-foreground
    window belongs to a *third* thread we never attached to, or if the
    target window hasn't finished processing being reactivated yet. We
    attach to both the target thread and whichever thread currently owns
    the foreground, and retry briefly instead of giving up on the first
    failure -- callers must not paste on the assumption this always
    succeeds after one attempt.
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
    if win32gui.GetForegroundWindow() == hwnd:
        return True

    current_thread_id = win32api.GetCurrentThreadId()
    target_thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)

    attached_target = False
    attached_fg = False
    fg_thread_id = 0
    try:
        current_fg_hwnd = win32gui.GetForegroundWindow()
        if current_fg_hwnd:
            fg_thread_id, _ = win32process.GetWindowThreadProcessId(current_fg_hwnd)

        attached_target = _attach(current_thread_id, target_thread_id)
        if fg_thread_id != target_thread_id:
            attached_fg = _attach(current_thread_id, fg_thread_id)

        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        for attempt in range(_RESTORE_ATTEMPTS):
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            if attempt < _RESTORE_ATTEMPTS - 1:
                time.sleep(_RESTORE_RETRY_SECONDS)

        logger.warning("Could not bring %s back to the foreground after %d attempts", hwnd, _RESTORE_ATTEMPTS)
        return False
    except Exception:
        logger.warning("Failed to restore foreground window", exc_info=True)
        return False
    finally:
        if attached_target:
            _user32.AttachThreadInput(current_thread_id, target_thread_id, False)
        if attached_fg:
            _user32.AttachThreadInput(current_thread_id, fg_thread_id, False)
