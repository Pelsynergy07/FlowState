"""Native window tweaks Qt has no portable flag for."""

from __future__ import annotations

import ctypes
import logging

logger = logging.getLogger("flowstate.ui")

_WDA_EXCLUDEFROMCAPTURE = 0x00000011
_WS_EX_NOACTIVATE = 0x08000000
_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_LAYERED = 0x00080000
_GWL_EXSTYLE = -20


def make_overlay(widget, *, click_through: bool = False, exclude_from_capture: bool = False) -> None:
    """Never activates, optionally passes clicks through and stays out of screenshots."""
    hwnd = int(widget.winId())
    user32 = ctypes.windll.user32
    ex_style = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE) | _WS_EX_NOACTIVATE
    if click_through:
        ex_style |= _WS_EX_TRANSPARENT | _WS_EX_LAYERED
    user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex_style)
    if exclude_from_capture:
        try:
            user32.SetWindowDisplayAffinity(hwnd, _WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass


def bring_to_front(widget) -> None:
    """Windows' foreground lock keeps a tray app's window behind others
    unless it briefly attaches to the foreground thread."""
    try:
        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            user32.ShowWindow(hwnd, 5)  # SW_SHOW

        # Force window to top via HWND_TOPMOST toggle
        HWND_TOPMOST = -1
        HWND_NOTOPMOST = -2
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_SHOWWINDOW = 0x0040
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

        fore_hwnd = user32.GetForegroundWindow()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
        app_thread = kernel32.GetCurrentThreadId()
        if fore_thread != app_thread:
            user32.AttachThreadInput(fore_thread, app_thread, True)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.AttachThreadInput(fore_thread, app_thread, False)
        else:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def global_to_logical(x: float, y: float) -> tuple[int, int]:
    """Mouse hooks report physical pixels; Qt places widgets in logical pixels.
    On a 125%-scaled display those differ, so overlays must convert."""
    from PySide6.QtWidgets import QApplication

    screen = QApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen else 1.0
    if not ratio:
        ratio = 1.0
    return (round(x / ratio), round(y / ratio))
