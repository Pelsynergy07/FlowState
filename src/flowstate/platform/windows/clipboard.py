"""Win32 clipboard primitives and a synthetic Ctrl+V.

UI Automation's ValuePattern and raw WM_CHAR injection are unreliable
across Electron/browser/terminal apps; clipboard + synthetic Ctrl+V works
everywhere.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import win32api
import win32clipboard
import win32con

logger = logging.getLogger("flowstate.inject")

_VK_V = 0x56


def _image_to_dib(path: Path) -> bytes:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "BMP")
    return buf.getvalue()[14:]  # CF_DIB wants BITMAPINFOHEADER + pixels, no file header


def save_clipboard() -> dict[int, object] | None:
    """Copy text and lossless image formats before replacing the clipboard.

    DIB/DIBV5 and registered PNG bytes can be restored after EmptyClipboard;
    CF_BITMAP is a GDI handle and cannot safely outlive that operation.
    """
    try:
        win32clipboard.OpenClipboard()
        try:
            formats = [win32con.CF_UNICODETEXT, win32con.CF_DIB, 17,
                       win32clipboard.RegisterClipboardFormat("PNG")]
            snapshot = {}
            for fmt in formats:
                if win32clipboard.IsClipboardFormatAvailable(fmt):
                    snapshot[fmt] = win32clipboard.GetClipboardData(fmt)
            return snapshot or None
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        logger.warning("Failed to read clipboard for save/restore", exc_info=True)
        return None


def set_clipboard_text(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        if text:
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def set_clipboard_image(image_path: Path) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, _image_to_dib(image_path))
    finally:
        win32clipboard.CloseClipboard()


def restore_clipboard(snapshot: dict[int, object] | str | None) -> None:
    if snapshot is None:
        return
    # Retain compatibility with callers that saved only text.
    if isinstance(snapshot, str):
        snapshot = {win32con.CF_UNICODETEXT: snapshot}
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        for fmt, data in snapshot.items():
            win32clipboard.SetClipboardData(fmt, data)
    finally:
        win32clipboard.CloseClipboard()


def send_paste_shortcut() -> None:
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(_VK_V, 0, 0, 0)
    win32api.keybd_event(_VK_V, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
