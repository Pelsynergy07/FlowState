"""Clipboard through Qt; no synthetic paste on this platform yet."""

from __future__ import annotations

from pathlib import Path

PASTE_SETTLE_SECONDS = 0.0


def save_clipboard():
    return None


def set_clipboard_text(text: str) -> None:
    from PySide6.QtGui import QGuiApplication

    QGuiApplication.clipboard().setText(text)


def set_clipboard_image(image_path: Path) -> None:
    from PySide6.QtGui import QGuiApplication, QImage

    QGuiApplication.clipboard().setImage(QImage(str(image_path)))


def restore_clipboard(snapshot) -> None:
    """The result stays on the clipboard for the user to paste."""


def send_paste_shortcut() -> None:
    """Not available: the text is left on the clipboard."""
