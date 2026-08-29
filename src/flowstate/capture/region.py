"""Ctrl+drag rectangle selection overlay -- the reliable alternative to
the circle gesture. Selection completes (and this overlay closes) before
the screenshot is taken, so no capture-exclusion trickery is needed here."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .annotate import HIGHLIGHT_COLOR


class RegionSelectorOverlay(QWidget):
    """A translucent, full-virtual-desktop overlay. Show it when Ctrl is
    pressed during recording; it reports the selected QRect (in global
    screen coordinates) via on_selected and closes itself on release."""

    def __init__(self, on_selected: Callable[[QRect], None]):
        super().__init__()
        self._on_selected = on_selected
        self._origin: QPoint | None = None
        self._current: QPoint | None = None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event) -> None:
        self._origin = event.globalPosition().toPoint()
        self._current = self._origin
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._origin is not None:
            self._current = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._origin is not None and self._current is not None:
            rect = QRect(self._origin, self._current).normalized()
            self.close()
            if rect.width() > 5 and rect.height() > 5:
                self._on_selected(rect)
        self._origin = None
        self._current = None

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            self._origin = None
            self._current = None
            self.close()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 60))
        if self._origin is not None and self._current is not None:
            rect = QRect(self._origin, self._current).normalized()
            painter.setPen(QPen(QColor(*HIGHLIGHT_COLOR), 2))
            painter.drawRect(rect)
