"""FlowState's mark, drawn procedurally so the app never depends on an
external image asset: a rounded-square tile with a simple three-bar
waveform glyph in white. Idle vs. recording states swap the tile color
so the tray icon itself communicates status at a glance."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .theme import ACCENT, DANGER, PAPER_RAISED


def _draw_mark(size: int, tile_color: str) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    path = QPainterPath()
    radius = size * 0.22
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.fillPath(path, QColor(tile_color))

    # Three-bar waveform glyph, centered.
    bar_color = QColor(PAPER_RAISED)
    bar_width = size * 0.11
    gap = size * 0.09
    heights = [size * 0.30, size * 0.52, size * 0.38]
    total_width = bar_width * 3 + gap * 2
    x = (size - total_width) / 2
    for h in heights:
        y = (size - h) / 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(bar_color)
        bar_path = QPainterPath()
        bar_path.addRoundedRect(QRectF(x, y, bar_width, h), bar_width / 2, bar_width / 2)
        painter.fillPath(bar_path, bar_color)
        x += bar_width + gap

    painter.end()
    return pixmap


def build_app_icon(size: int = 256) -> QIcon:
    icon = QIcon()
    for s in (16, 32, 48, 64, 128, 256):
        icon.addPixmap(_draw_mark(s, ACCENT))
    return icon


def build_tray_icon(recording: bool = False) -> QIcon:
    """Builds a tray icon guaranteed to pop out on both dark and light Windows taskbars."""
    icon = QIcon()
    for s in (16, 24, 32, 48):
        pixmap = QPixmap(s, s)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(1.0, 1.0, s - 2.0, s - 2.0)
        radius = s * 0.22

        if recording:
            # Vivid Danger Red tile with white waveform
            painter.setPen(QPen(QColor("#000000"), 1.2))
            painter.setBrush(QColor(DANGER))
            painter.drawRoundedRect(rect, radius, radius)
            bar_color = QColor("#FFFFFF")
        else:
            # Clean White tile with solid dark border & deep black waveform
            painter.setPen(QPen(QColor("#1A1A1A"), 1.4))
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(rect, radius, radius)
            bar_color = QColor("#1A1A1A")

        bar_w = max(2.0, s * 0.12)
        gap = max(1.5, s * 0.10)
        heights = [s * 0.32, s * 0.56, s * 0.40]
        total_w = bar_w * 3 + gap * 2
        x = (s - total_w) / 2.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(bar_color)
        for h in heights:
            y = (s - h) / 2.0
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, bar_w, h), bar_w / 2.0, bar_w / 2.0)
            painter.drawPath(path)
            x += bar_w + gap

        painter.end()
        icon.addPixmap(pixmap)
    return icon

