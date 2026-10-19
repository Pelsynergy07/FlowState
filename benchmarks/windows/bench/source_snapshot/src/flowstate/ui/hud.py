"""Compact paper-and-ink recording status with a live meter and processing timer.

The non-activating window remains excluded from screen capture. Every state
uses the website's diamond emblem, lime accent, and editorial timer type.
"""

from __future__ import annotations

import ctypes
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget

from .fonts import make_font
from .theme import (
    ACCENT,
    BORDER,
    FONT_FAMILY_DISPLAY,
    FONT_FAMILY_MONO,
    FONT_FAMILY_STICKER,
    INK,
    LIME,
    MUTED_TEXT,
    ORANGE,
    PAPER_RAISED,
    PINK,
)

_WDA_EXCLUDEFROMCAPTURE = 0x00000011
_WS_EX_NOACTIVATE = 0x08000000
_GWL_EXSTYLE = -20

_BAR_COUNT = 7
_METER_UPDATE_MS = 45


def _draw_diamond_emblem(painter: QPainter, cx: float, cy: float, r: float, fill_color: QColor):
    """Draws the 4-point concave diamond emblem."""
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(fill_color)
    path = QPainterPath()
    path.moveTo(cx, cy - r)
    path.quadTo(cx + r * 0.22, cy - r * 0.22, cx + r, cy)
    path.quadTo(cx + r * 0.22, cy + r * 0.22, cx, cy + r)
    path.quadTo(cx - r * 0.22, cy + r * 0.22, cx - r, cy)
    path.quadTo(cx - r * 0.22, cy - r * 0.22, cx, cy - r)
    path.closeSubpath()
    painter.drawPath(path)
    painter.restore()


class RecordingHUD(QWidget):
    def __init__(self, level_provider=None):
        super().__init__()
        self._level_provider = level_provider  # callable -> float 0..1
        self._level_history = [0.0] * _BAR_COUNT
        self._start_time: float | None = None
        self._state = "idle"  # "idle" | "recording" | "processing"
        self._native_flags_applied = False
        self._phase = 0.0
        self._processing_started: float | None = None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Compact width & height with uniform margins
        self.resize(286, 66)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.timeout.connect(self.hide_recording)

    def _apply_native_window_flags(self) -> None:
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        ex_style = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, ex_style | _WS_EX_NOACTIVATE)
        try:
            user32.SetWindowDisplayAffinity(hwnd, _WDA_EXCLUDEFROMCAPTURE)
        except Exception:
            pass

    def _reposition(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.bottom() - self.height() - 44
        self.move(x, y)

    def show_recording(self) -> None:
        self._notice_timer.stop()
        self.resize(286, 66)
        self._state = "recording"
        self._start_time = time.monotonic()
        self._level_history = [0.0] * _BAR_COUNT
        self._phase = 0.0
        self._reposition()
        self.show()
        if not self._native_flags_applied:
            self._apply_native_window_flags()
            self._native_flags_applied = True
        self._timer.start(_METER_UPDATE_MS)

    def show_processing(self) -> None:
        self._notice_timer.stop()
        self.resize(286, 66)
        self._processing_started = time.monotonic()
        self._state = "processing"
        if not self._timer.isActive():
            self._timer.start(_METER_UPDATE_MS)
        self.update()

    def show_notice(self, message: str = "No speech detected (check mic)", duration_ms: int = 2500) -> None:
        self.resize(380, 66)
        self._state = "notice"
        self._notice_message = message
        self._timer.stop()
        self._reposition()
        self.show()
        if not self._native_flags_applied:
            self._apply_native_window_flags()
            self._native_flags_applied = True
        self.update()
        self._notice_timer.start(duration_ms)

    def hide_recording(self) -> None:
        self._state = "idle"
        self._notice_timer.stop()
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._phase += 0.12  # Slower, smoother pulse
        if self._state == "recording":
            level = self._level_provider() if self._level_provider else 0.0
            self._level_history.pop(0)
            self._level_history.append(max(0.0, min(1.0, level)))
        elif self._state == "processing":
            t = time.monotonic()
            self._level_history = [
                0.4 + 0.4 * math.sin(t * 3 + i * 0.9) for i in range(_BAR_COUNT)
            ]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width() - 6, self.height() - 6
        surface = QRectF(1, 1, w, h)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(INK))
        painter.drawRoundedRect(QRectF(5, 5, w, h), 5, 5)
        painter.setPen(QPen(QColor(INK), 1.5))
        painter.setBrush(QColor(PAPER_RAISED))
        painter.drawRoundedRect(surface, 5, 5)

        # The site's diamond mark anchors every recording state.
        cy = h / 2 + 1
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(LIME if self._state != "notice" else "#EFE8DC"))
        painter.drawRoundedRect(QRectF(11, 11, 39, 39), 4, 4)
        painter.save()
        painter.translate(30.5, cy)
        if self._state == "processing":
            painter.rotate((self._phase * 30) % 360)
        _draw_diamond_emblem(painter, 0, 0, 10 + 0.5 * math.sin(self._phase), QColor(INK))
        painter.setBrush(QColor(PAPER_RAISED))
        painter.drawEllipse(QPointF(0, 0), 1.8, 1.8)
        painter.restore()

        if self._state == "recording":
            painter.setPen(QColor(MUTED_TEXT))
            painter.setFont(make_font(FONT_FAMILY_MONO, 7, bold=True))
            painter.drawText(QRectF(64, 10, 100, 17), Qt.AlignVCenter, "LISTENING")
            painter.setPen(Qt.NoPen)
            for i, level in enumerate(self._level_history):
                bar_h = max(3, level * 18)
                painter.setBrush(QColor(INK))
                painter.drawRoundedRect(QRectF(65 + i * 8, 39 - bar_h / 2, 4, bar_h), 1, 1)
            elapsed = time.monotonic() - self._start_time if self._start_time else 0
            minutes, seconds = divmod(int(elapsed), 60)
            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_DISPLAY, 27))
            painter.drawText(QRectF(164, 5, 100, 47), Qt.AlignRight | Qt.AlignVCenter, f"{minutes:02d}:{seconds:02d}")
        elif self._state == "processing":
            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_DISPLAY, 17))
            painter.drawText(QRectF(64, 7, w - 75, 27), Qt.AlignVCenter, "Processing your words…")
            painter.setPen(QColor(MUTED_TEXT))
            painter.setFont(make_font(FONT_FAMILY_MONO, 7))
            elapsed = int(time.monotonic() - self._processing_started) if self._processing_started else 0
            painter.drawText(QRectF(65, 34, w - 76, 18), Qt.AlignVCenter, f"TRANSCRIBING + POLISHING   {elapsed}s")
        elif self._state == "notice":
            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_MONO, 8))
            painter.drawText(QRectF(64, 9, w - 76, h - 16), Qt.AlignLeft | Qt.AlignVCenter | Qt.TextWordWrap, getattr(self, "_notice_message", "No speech detected"))
        painter.end()
