"""No foreground-window tracking on this platform yet."""

from __future__ import annotations


def get_foreground_window() -> int:
    return 0


def get_window_title(handle: int) -> str:
    return ""


def restore_foreground_window(handle: int) -> bool:
    return False
