"""Clipboard-based text/image injection: save the clipboard, set the new
content, synthesize Ctrl+V into whatever window currently has focus (the
caller must have already restored it), then restore the clipboard.

UI Automation's ValuePattern and raw WM_CHAR injection are unreliable
across Electron/browser/terminal apps; clipboard + synthetic Ctrl+V works
everywhere.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import win32api
import win32clipboard
import win32con

logger = logging.getLogger("flowstate.inject")

PASTE_SETTLE_SECONDS = 0.3
_VK_V = 0x56


def _image_to_dib(path: Path) -> bytes:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "BMP")
    return buf.getvalue()[14:]  # CF_DIB wants BITMAPINFOHEADER + pixels, no file header


def _save_clipboard_text() -> str | None:
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        logger.warning("Failed to read clipboard for save/restore", exc_info=True)
        return None


def _set_clipboard_text(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        if text:
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def _set_clipboard_image(image_path: Path) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, _image_to_dib(image_path))
    finally:
        win32clipboard.CloseClipboard()


def _restore_clipboard(previous_text: str | None) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        if previous_text:
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, previous_text)
    finally:
        win32clipboard.CloseClipboard()


def _send_ctrl_v() -> None:
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(_VK_V, 0, 0, 0)
    win32api.keybd_event(_VK_V, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def paste_transcript(text: str, image_paths: list[Path] | None = None) -> None:
    """Pastes text, then each captured screenshot, into the
    currently-focused window -- one Ctrl+V per item, each with exactly
    one clipboard format set at a time. Putting text and an image on the
    clipboard together for a single paste made some apps (browsers, chat
    inputs that accept image paste) treat the whole thing as an image
    attach and silently drop the text, so every item gets its own
    separate paste instead. Restores the original clipboard afterwards
    either way, since everything's already been delivered directly."""
    image_paths = [p for p in (image_paths or []) if p.exists()]
    previous_text = _save_clipboard_text()

    _set_clipboard_text(text)
    _send_ctrl_v()
    time.sleep(PASTE_SETTLE_SECONDS)

    for image_path in image_paths:
        try:
            _set_clipboard_image(image_path)
        except Exception:
            logger.warning("Failed to place %s on clipboard", image_path, exc_info=True)
            continue
        _send_ctrl_v()
        time.sleep(PASTE_SETTLE_SECONDS)

    _restore_clipboard(previous_text)
