"""Full-screen transparent overlay that draws the selection rectangle
live while Ctrl+dragging a screenshot region -- otherwise the drag is
invisible until you release the mouse and the screenshot has already
been taken.

Click-through (WS_EX_TRANSPARENT on Windows, ignoresMouseEvents on macOS)
so it never steals the very mouse events it's drawn in response to, and
covers the whole virtual desktop (all monitors) since a drag can cross
monitor bounds.

Coordinates in: on Windows capture/drag_hook.py reports raw physical-pixel
mouse positions (same space the actual screenshot capture uses), but Qt
positions widgets in logical/DPI-scaled pixels, so the window adapter's
global_to_logical converts them. On macOS both are already in points.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .. import platform
from .theme import ACCENT


def _physical_to_logical(x: int, y: int) -> tuple[int, int]:
    return platform.adapter("window").global_to_logical(x, y)


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
        platform.adapter("window").make_overlay(self, click_through=True, exclude_from_capture=True)

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
