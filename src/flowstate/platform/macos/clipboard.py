"""NSPasteboard primitives and a synthetic Cmd+V.

Same approach as Windows: put one item on the clipboard, press the paste
shortcut in the frontmost app, then put back whatever the user had copied.
Posting the keystroke needs Accessibility access.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger("flowstate.inject")

# Apps read the pasteboard asynchronously after Cmd+V; restoring the old
# contents too early pastes those instead.
PASTE_SETTLE_SECONDS = 0.35


class _Snapshot:
    """Every item and type on the pasteboard, plus the change count at which
    FlowState replaced it (so a copy made meanwhile is never overwritten)."""

    def __init__(self, items: list[dict[str, object]]):
        self.items = items
        self.change_count_after_paste: int | None = None


def _pasteboard():
    from AppKit import NSPasteboard

    return NSPasteboard.generalPasteboard()


def save_clipboard() -> _Snapshot | None:
    try:
        board = _pasteboard()
        items = []
        for item in board.pasteboardItems() or []:
            data = {}
            for kind in item.types() or []:
                payload = item.dataForType_(kind)
                if payload is not None:
                    data[str(kind)] = payload
            if data:
                items.append(data)
        return _Snapshot(items) if items else None
    except Exception:
        logger.warning("Failed to read clipboard for save/restore", exc_info=True)
        return None


def set_clipboard_text(text: str) -> None:
    from AppKit import NSPasteboardTypeString

    board = _pasteboard()
    board.clearContents()
    if text:
        board.setString_forType_(text, NSPasteboardTypeString)


def set_clipboard_image(image_path: Path) -> None:
    from AppKit import NSImage, NSPasteboardTypePNG, NSPasteboardTypeTIFF
    from Foundation import NSData

    png = NSData.dataWithContentsOfFile_(str(image_path))
    if png is None:
        raise OSError(f"Could not read {image_path}")
    board = _pasteboard()
    board.clearContents()
    board.setData_forType_(png, NSPasteboardTypePNG)
    # Older apps only accept TIFF image data.
    image = NSImage.alloc().initWithData_(png)
    if image is not None and image.TIFFRepresentation() is not None:
        board.setData_forType_(image.TIFFRepresentation(), NSPasteboardTypeTIFF)


def restore_clipboard(snapshot) -> None:
    if snapshot is None:
        return
    from AppKit import NSPasteboardItem, NSPasteboardTypeString

    board = _pasteboard()
    if isinstance(snapshot, str):  # callers that saved only text
        board.clearContents()
        board.setString_forType_(snapshot, NSPasteboardTypeString)
        return
    if snapshot.change_count_after_paste is not None and board.changeCount() != snapshot.change_count_after_paste:
        logger.info("Clipboard changed after pasting; leaving the new contents in place.")
        return
    board.clearContents()
    restored = []
    for data in snapshot.items:
        item = NSPasteboardItem.alloc().init()
        for kind, payload in data.items():
            item.setData_forType_(payload, kind)
        restored.append(item)
    if restored:
        board.writeObjects_(restored)


def remember_change_count(snapshot) -> None:
    if isinstance(snapshot, _Snapshot):
        snapshot.change_count_after_paste = _pasteboard().changeCount()


def send_paste_shortcut() -> None:
    import Quartz

    from .keyboard import INJECTED_EVENT_MARKER, KEYCODE_V

    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for is_down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(source, KEYCODE_V, is_down)
        Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventSetIntegerValueField(event, Quartz.kCGEventSourceUserData, INJECTED_EVENT_MARKER)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.01)
