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
        # Compact width & height (ample vertical clearance for Instrument Serif)
        self.resize(240, 60)

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
        self.update()

    def hide_recording(self) -> None:
        self._state = "idle"
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._phase += 0.18
        if self._state == "recording":
            level = self._level_provider() if self._level_provider else 0.0
            self._level_history.pop(0)
            self._level_history.append(max(0.0, min(1.0, level)))
        elif self._state == "processing":
            t = time.monotonic()
            self._level_history = [
                0.4 + 0.4 * math.sin(t * 4 + i * 0.9) for i in range(_BAR_COUNT)
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

        if self._state == "recording":
            # Pulsing Signal Lime diamond emblem
            cx = 22
            cy = h / 2 + 1.5
            pulse_r = 7.5 + 1.2 * math.sin(self._phase * 3.5)
            _draw_diamond_emblem(painter, cx, cy, pulse_r, QColor(LIME))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(INK))
            painter.drawEllipse(QPointF(cx, cy), 2, 2)

            # Live 5-bar LED waveform
            bars_start_x = 40
            bar_w = 3.5
            gap = 2.5
            max_bar_h = 24.0
            for i, lvl in enumerate(self._level_history):
                bh = max(3.0, lvl * max_bar_h)
                bx = bars_start_x + i * (bar_w + gap)
                by = (h / 2 + 1.5) - bh / 2
                b_rect = QRectF(bx, by, bar_w, bh)
                if i >= 3 and lvl > 0.75:
                    painter.setBrush(QColor(ORANGE))
                else:
                    painter.setBrush(QColor(INK))
                painter.drawRect(b_rect)

            # State metadata label
            text_x = 76
            painter.setPen(QColor(MUTED_TEXT))
            painter.setFont(make_font(FONT_FAMILY_MONO, 7, bold=True))
            painter.drawText(QRectF(text_x, 8, 150, 12), Qt.AlignLeft | Qt.AlignVCenter, "FLOWSTATE // REC")

            # Instrument Serif timer (vertically centered with 13px bottom clearance)
            elapsed = time.monotonic() - self._start_time if self._start_time else 0.0
            mins, secs = divmod(int(elapsed), 60)
            tenths = int((elapsed - int(elapsed)) * 10)
            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_DISPLAY, 20))
            painter.drawText(QRectF(text_x, 18, 65, 30), Qt.AlignLeft | Qt.AlignVCenter, f"{mins:02d}:{secs:02d}")

            # Sub-second decimal in Space Mono
            painter.setPen(QColor(MUTED_TEXT))
            painter.setFont(make_font(FONT_FAMILY_MONO, 8))
            painter.drawText(QRectF(text_x + 58, 20, 35, 26), Qt.AlignLeft | Qt.AlignVCenter, f".{tenths}")

        elif self._state == "processing":
            # Processing square indicator
            bx, by = 16, (h - 22) / 2 + 1.5
            sq_rect = QRectF(bx, by, 22, 22)
            painter.setPen(QPen(QColor(BORDER), 1.6))
            painter.setBrush(QColor(ACCENT))
            painter.drawRect(sq_rect)

            # Crosshair inside
            painter.setPen(QPen(QColor(PAPER_RAISED), 1.8))
            scx = sq_rect.center().x()
            scy = sq_rect.center().y()
            cs = 5.0
            painter.drawLine(scx - cs, scy, scx + cs, scy)
            painter.drawLine(scx, scy - cs, scx, scy + cs)

            text_x = 50
            painter.setPen(QColor(MUTED_TEXT))
            painter.setFont(make_font(FONT_FAMILY_MONO, 7, bold=True))
            painter.drawText(QRectF(text_x, 8, 180, 12), Qt.AlignLeft | Qt.AlignVCenter, "LOCAL LLM // QWEN2.5")

            painter.setPen(QColor(INK))
            painter.setFont(make_font(FONT_FAMILY_DISPLAY, 16, italic=True))
            painter.drawText(QRectF(text_x, 19, 180, 28), Qt.AlignLeft | Qt.AlignVCenter, "Formatting text...")
