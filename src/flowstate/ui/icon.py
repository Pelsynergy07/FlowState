"""FlowState's mark, drawn procedurally so the app never depends on an
external image asset: a rounded-square tile with a simple three-bar
waveform glyph in white. Idle vs. recording states swap the tile color
so the tray icon itself communicates status at a glance."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap

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
    color = DANGER if recording else ACCENT
    icon = QIcon()
    for s in (16, 24, 32, 48):
        icon.addPixmap(_draw_mark(s, color))
    return icon
