"""The recording HUD: a small floating pill shown only while recording,
with a live level meter and elapsed time. Never steals focus (so the
field you were typing into stays focused) and never appears in your own
screenshots (so a circled screenshot never shows the HUD itself).

Styled as a clean white pill with a hairline border -- airy and quiet
rather than a bold color block, matching the rest of the app's minimal
aesthetic. The level bars and label use the accent color so the HUD
still reads clearly as "active" against any desktop.

Deliberately no QGraphicsDropShadowEffect here: combined with
WA_TranslucentBackground, a non-activating "Tool" window, and
WDA_EXCLUDEFROMCAPTURE, a graphics effect stops the window's displayed
pixels from refreshing on repaint (DWM's damage tracking seems to get
confused by the combination) -- update() keeps firing and the paint logic
runs, but nothing visibly changes, which looked like "the animation and
timer are frozen."
"""

from __future__ import annotations

import ctypes
import math
import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget

from .theme import ACCENT, FONT_FAMILY, INK, LINE, MUTED_TEXT, PAPER_RAISED

_WDA_EXCLUDEFROMCAPTURE = 0x00000011
_WS_EX_NOACTIVATE = 0x08000000
_GWL_EXSTYLE = -20

_BAR_COUNT = 5
_METER_UPDATE_MS = 60


class RecordingHUD(QWidget):
    def __init__(self, level_provider=None):
        super().__init__()
        self._level_provider = level_provider  # callable -> float 0..1
        self._level_history = [0.0] * _BAR_COUNT
        self._start_time: float | None = None
        self._state = "idle"  # "idle" | "recording" | "processing"
        self._native_flags_applied = False

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(224, 60)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _apply_native_window_flags(self) -> None:
        """Belt-and-suspenders beyond Qt's flags: WS_EX_NOACTIVATE so
        Windows itself never focuses this window, and
        WDA_EXCLUDEFROMCAPTURE so it's invisible to any screen capture,
        including our own circle-gesture screenshots."""
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
        self._reposition()
        self.show()
        if not self._native_flags_applied:
            # Applied once, not on every recording start: re-toggling
            # WDA_EXCLUDEFROMCAPTURE on this layered/translucent window each
            # time is what previously produced a HUD that stopped visibly
            # updating (timer/meter "frozen") after a few uses in one
            # session -- see the module docstring on DWM's damage tracking.
            self._apply_native_window_flags()
            self._native_flags_applied = True
        self._timer.start(_METER_UPDATE_MS)

    def show_processing(self) -> None:
        """Switches an already-visible HUD to a 'working on it' state
        while transcription/cleanup runs -- this can take a moment, and
        the level meter has nothing to show once recording has stopped."""
        self._state = "processing"
        self.update()

    def hide_recording(self) -> None:
        self._state = "idle"
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        if self._state == "recording":
            level = self._level_provider() if self._level_provider else 0.0
            self._level_history.pop(0)
            self._level_history.append(max(0.0, min(1.0, level)))
        elif self._state == "processing":
            # A gentle traveling-wave animation stands in for the level
            # meter once there's no more live audio to show.
            t = time.monotonic()
            self._level_history = [
                0.4 + 0.4 * math.sin(t * 4 + i * 0.9) for i in range(_BAR_COUNT)
            ]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        pill_rect = QRectF(0, 0, self.width(), self.height())
        pill = QPainterPath()
        pill.addRoundedRect(pill_rect, self.height() / 2, self.height() / 2)
        painter.fillPath(pill, QColor(PAPER_RAISED))
        painter.setPen(QColor(LINE))
        painter.drawPath(pill)

        # Level meter bars, left side.
        bar_area_x = 20
        bar_width = 4
        gap = 5
        max_bar_h = 22
        base_y = self.height() / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(ACCENT))
        for i, level in enumerate(self._level_history):
            h = max(4, level * max_bar_h)
            x = bar_area_x + i * (bar_width + gap)
            painter.drawRoundedRect(QRectF(x, base_y - h / 2, bar_width, h), 2, 2)

        text_x = bar_area_x + _BAR_COUNT * (bar_width + gap) + 12
        label = "Processing" if self._state == "processing" else "Listening"
        painter.setPen(QColor(INK))
        label_font = QFont(FONT_FAMILY, 12, QFont.DemiBold)
        painter.setFont(label_font)
        painter.drawText(
            QRectF(text_x, 10, self.width() - text_x - 16, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            label,
        )

        if self._state == "processing":
            # No ticking clock here -- watching seconds count up during a
            # multi-second wait reads as "this is stuck," even once it's
            # fast. A static label is calmer.
            sub_text = "working"
        else:
            elapsed = time.monotonic() - self._start_time if self._start_time else 0.0
            mins, secs = divmod(int(elapsed), 60)
            sub_text = f"{mins:02d}:{secs:02d}"
        painter.setPen(QColor(MUTED_TEXT))
        time_font = QFont(FONT_FAMILY, 11)
        painter.setFont(time_font)
        painter.drawText(
            QRectF(text_x, 30, self.width() - text_x - 16, 18),
            Qt.AlignLeft | Qt.AlignVCenter,
            sub_text,
        )
