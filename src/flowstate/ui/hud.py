"""The recording HUD: tactical neo-brutalist floating bar.

Features:
- Compact, non-occluding 236px width
- 2px ink border with hard brutalist offset shadow
- Pulsing Signal Lime diamond recording emblem
- 5-bar live LED soundbar with peak gradient colors
- Instrument Serif timer counter
- Excluded from capture (WDA_EXCLUDEFROMCAPTURE) and never steals focus (WS_EX_NOACTIVATE)
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

_BAR_COUNT = 5
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

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Compact width & height with uniform margins
        self.resize(176, 46)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

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
        self._state = "processing"
        if not self._timer.isActive():
            self._timer.start(_METER_UPDATE_MS)
        self.update()

    def show_notice(self, message: str = "No speech detected (check mic)", duration_ms: int = 2500) -> None:
        self._state = "notice"
        self._notice_message = message
        self._timer.stop()
        self._reposition()
        self.show()
        if not self._native_flags_applied:
            self._apply_native_window_flags()
            self._native_flags_applied = True
        self.update()
        QTimer.singleShot(duration_ms, self.hide_recording)

    def hide_recording(self) -> None:
        self._state = "idle"
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

        # Allow 4px margin for hard shadow
        w = self.width() - 5
        h = self.height() - 5
        bar_rect = QRectF(1.5, 1.5, w, h)
        shadow_rect = QRectF(5, 5, w, h)

        # 1. Hard Brutalist Shadow
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BORDER))
        painter.drawRoundedRect(shadow_rect, 4, 4)

        # 2. Solid Surface & Border
        painter.setPen(QPen(QColor(BORDER), 2.2))
        painter.setBrush(QColor(PAPER_RAISED))
        painter.drawRoundedRect(bar_rect, 4, 4)

        cy = h / 2.0 + 1.5

        if self._state == "recording":
            # 1. Gentle pulsing Signal Lime diamond emblem (slower cadence)
            cx = 20.0
            pulse_r = 7.0 + 0.9 * math.sin(self._phase * 1.5)
            _draw_diamond_emblem(painter, cx, cy, pulse_r, QColor(LIME))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(INK))
            painter.drawEllipse(QPointF(cx, cy), 1.8, 1.8)

            # 2. Live 5-bar LED waveform
            bars_start_x = 35.0
            bar_w = 3.2
            gap = 2.4
            max_bar_h = 20.0
            for i, lvl in enumerate(self._level_history):
                bh = max(3.0, lvl * max_bar_h)
                bx = bars_start_x + i * (bar_w + gap)
                by = cy - bh / 2.0
                b_rect = QRectF(bx, by, bar_w, bh)
                if i >= 3 and lvl > 0.75:
                    painter.setBrush(QColor(ORANGE))
                else:
                    painter.setBrush(QColor(INK))
                painter.drawRect(b_rect)

            # 3. Clean Instrument Serif timer (vertically centered, balanced right margin)
            elapsed = time.monotonic() - self._start_time if self._start_time else 0.0
            mins, secs = divmod(int(elapsed), 60)
            tenths = int((elapsed - int(elapsed)) * 10)

            text_x = 73.0
            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_DISPLAY, 21))
            painter.drawText(QRectF(text_x, 2, 58, h), Qt.AlignLeft | Qt.AlignVCenter, f"{mins:02d}:{secs:02d}")

            # Sub-second decimal in Space Mono
            painter.setPen(QColor(MUTED_TEXT))
            painter.setFont(make_font(FONT_FAMILY_MONO, 8))
            painter.drawText(QRectF(text_x + 55, 4, 30, h), Qt.AlignLeft | Qt.AlignVCenter, f".{tenths}")

        elif self._state == "processing":
            # 1. Lively spinning diamond sparkle emblem with Signal Lime pulsing core
            cx = 22.0
            painter.save()
            painter.translate(cx, cy)
            angle = (self._phase * 40.0) % 360.0
            painter.rotate(angle)
            _draw_diamond_emblem(painter, 0, 0, 7.8, QColor(INK))
            painter.setPen(Qt.NoPen)
            core_r = 1.8 + 0.6 * math.sin(self._phase * 2.5)
            painter.setBrush(QColor(LIME))
            painter.drawEllipse(QPointF(0, 0), core_r, core_r)
            painter.restore()

            # 2. Human-like "Polishing..." text with dynamic animated ellipsis
            dots = "." * (int(self._phase * 1.5) % 3 + 1)
            display_text = f"Polishing{dots}"

            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_DISPLAY, 18, italic=True))
            painter.drawText(QRectF(40, 2, w - 44, h), Qt.AlignLeft | Qt.AlignVCenter, display_text)


        elif self._state == "notice":
            cx = 20.0
            _draw_diamond_emblem(painter, cx, cy, 7.0, QColor(ORANGE))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(PAPER_RAISED))
            painter.drawEllipse(QPointF(cx, cy), 1.8, 1.8)

            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
            msg = getattr(self, "_notice_message", "No speech detected")
            painter.drawText(QRectF(34, 2, w - 38, h), Qt.AlignLeft | Qt.AlignVCenter, msg)

