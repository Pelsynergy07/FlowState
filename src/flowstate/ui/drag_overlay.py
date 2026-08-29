"""Full-screen transparent overlay that draws the selection rectangle
live while Ctrl+dragging a screenshot region -- otherwise the drag is
invisible until you release the mouse and the screenshot has already
been taken.

Click-through (WS_EX_TRANSPARENT) so it never steals the very mouse
events it's drawn in response to, and covers the whole virtual desktop
(all monitors) since a drag can cross monitor bounds.

Coordinates in: capture/drag_hook.py reports raw physical-pixel mouse
positions straight from Win32 (same space the actual screenshot capture
uses), but Qt positions widgets in logical/DPI-scaled pixels. On a
125%-scaled display those are two different coordinate spaces, so the
box would render offset from the real cursor unless converted here.
"""

from __future__ import annotations

import ctypes

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .theme import ACCENT

_WS_EX_TRANSPARENT = 0x00000020
_WS_EX_LAYERED = 0x00080000
_GWL_EXSTYLE = -20


def _physical_to_logical(x: int, y: int) -> tuple[int, int]:
    screen = QApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen else 1.0
    if not ratio:
        ratio = 1.0
    return (round(x / ratio), round(y / ratio))


class DragSelectionOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._native_flags_applied = False
        self._start: tuple[int, int] | None = None
        self._current: tuple[int, int] | None = None

    def _apply_click_through(self) -> None:
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        ex_style = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex_style | _WS_EX_TRANSPARENT | _WS_EX_LAYERED)

    def begin(self, x: int, y: int) -> None:
        virtual_geometry = QRect()
        for screen in QApplication.screens():
            virtual_geometry = virtual_geometry.united(screen.geometry())
        self.setGeometry(virtual_geometry)

        self._start = _physical_to_logical(x, y)
        self._current = self._start
        self.show()
        if not self._native_flags_applied:
            self._apply_click_through()
            self._native_flags_applied = True
        self.update()

    def move_to(self, x: int, y: int) -> None:
        if self._start is None:
            return
        self._current = _physical_to_logical(x, y)
        self.update()

    def end(self) -> None:
        self._start = None
        self._current = None
        self.hide()

    def paintEvent(self, event) -> None:
        if self._start is None or self._current is None:
            return
        origin = self.geometry().topLeft()
        sx, sy = self._start
        cx, cy = self._current
        rect = QRect(sx - origin.x(), sy - origin.y(), cx - sx, cy - sy).normalized()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        fill = QColor(ACCENT)
        fill.setAlpha(40)
        painter.setBrush(fill)
        pen = QPen(QColor(ACCENT))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect)
