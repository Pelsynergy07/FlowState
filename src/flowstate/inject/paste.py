"""Clipboard-based text/image injection: save the clipboard, set the new
content, synthesize the paste shortcut (Ctrl+V on Windows, Cmd+V on macOS)
into whatever window currently has focus (the caller must have already
restored it), then restore the clipboard.

The clipboard and keystroke primitives come from the platform adapter
(platform/<os>/clipboard.py); the sequencing below is shared.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .. import platform

logger = logging.getLogger("flowstate.inject")

_backend = platform.adapter("clipboard")
if platform.IS_WINDOWS:
    from ..platform.windows.clipboard import win32clipboard  # noqa: F401  (patched by tests)

PASTE_SETTLE_SECONDS = getattr(_backend, "PASTE_SETTLE_SECONDS", 0.3)

_save_clipboard = _backend.save_clipboard
_set_clipboard_text = _backend.set_clipboard_text
_set_clipboard_image = _backend.set_clipboard_image
_restore_clipboard = _backend.restore_clipboard
_send_ctrl_v = _backend.send_paste_shortcut  # the OS paste shortcut, Cmd+V on macOS
_remember_change_count = getattr(_backend, "remember_change_count", lambda snapshot: None)


def paste_transcript(text: str, image_paths: list[Path] | None = None) -> None:
    """Pastes text, then each captured screenshot, into the
    currently-focused window -- one paste per item, each with exactly
    one clipboard format set at a time. Putting text and an image on the
    clipboard together for a single paste made some apps (browsers, chat
    inputs that accept image paste) treat the whole thing as an image
    attach and silently drop the text, so every item gets its own
    separate paste instead. Restores the original clipboard afterwards
    either way, since everything's already been delivered directly."""
    image_paths = [p for p in (image_paths or []) if p.exists()]
    snapshot = _save_clipboard()
    try:
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
        _remember_change_count(snapshot)
    finally:
        try:
            _restore_clipboard(snapshot)
        except Exception:
            logger.warning("Failed to restore original clipboard", exc_info=True)
