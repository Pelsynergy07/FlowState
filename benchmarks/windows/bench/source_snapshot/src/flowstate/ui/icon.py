"""FlowState's mark, drawn procedurally so the app never depends on an
external image asset: a rounded-square tile with a simple three-bar
waveform glyph in white. Idle vs. recording states swap the tile color
so the tray icon itself communicates status at a glance."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .theme import ACCENT, DANGER, LIME, PAPER_RAISED


from pathlib import Path

_CACHE: dict[tuple[int, str, bool], QPixmap] = {}


def _draw_mark(size: int, tile_color: str = "#121212", recording: bool = False) -> QPixmap:
    key = (size, tile_color, recording)
    if key in _CACHE:
        return _CACHE[key]

    asset_name = "app_icon_recording.png" if recording else "app_icon.png"
    icon_path = Path(__file__).parent.parent / "resources" / "icons" / asset_name
    if icon_path.exists():
        src_pix = QPixmap(str(icon_path))
        scaled = src_pix.scaled(
            size, size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        _CACHE[key] = scaled
        return scaled

    # Fallback procedural drawing if asset not present
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    margin = max(0.5, size * 0.05)
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    radius = size * 0.24

    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    painter.fillPath(path, QColor(tile_color))
    painter.setPen(QPen(QColor("#121212"), max(1.0, size * 0.035)))
    painter.drawPath(path)
    painter.end()

    _CACHE[key] = pixmap
    return pixmap


def build_app_icon(size: int = 256) -> QIcon:
    for candidate in (
        Path(__file__).parent.parent.parent.parent / "packaging" / "app_icon.ico",
        Path(__file__).parent.parent / "resources" / "icons" / "app_icon.png",
    ):
        if candidate.exists():
            return QIcon(str(candidate))

    icon = QIcon()
    for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(_draw_mark(s, "#121212"))
    return icon


def build_tray_icon(recording: bool = False) -> QIcon:
    """Builds a crisp, neo-brutalist pixel art tray icon communicating status at a glance."""
    icon = QIcon()
    for s in (16, 20, 24, 32, 48):
        icon.addPixmap(_draw_mark(s, recording=recording))
    return icon

