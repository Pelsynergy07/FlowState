"""Neo-Brutalist & Tactile Sample UI Showcase v2 for FlowState.

Incorporate all user feedback:
- Authentic tactile folded paper & fibrous grain texture (from sticker reference)
- Authentic Nomad Systems geometric emblems:
  * 4-point concave curved diamond star
  * Triple aerospace glyphs (meridian circle, solid circle, target cross circle)
  * Concentric target reticles with coordinate ticks
- Authentic mymind graphic stickers:
  * Globe wireframe sticker
  * Retro perspective sunset stripes
  * Teardrop creative badge with angled tilt
  * High-personality Syne ExtraBold & Space Mono typography
- Floating HUD made significantly more compact (250px wide instead of 340px)
- Top-tier micro-interactions:
  * 3D tactile button press (lifts on hover, depresses flush on click)
  * Custom BrutalistCheckBox with vivid cobalt/lime fills, animated pop, and geometric white check glyphs
  * Live soundbar wave physics with peak level indicator
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# --- COLOR PALETTE ---
COLOR_PAPER = QColor("#F4F0E8")        # Warm tactile art paper base
COLOR_SURFACE = QColor("#FFFFFF")      # Crisp white card surface
COLOR_SURFACE_ALT = QColor("#ECE8DC")  # Technical panel surface
COLOR_INK = QColor("#0D0D0D")          # Deep neo-brutalist ink
COLOR_MUTED = QColor("#66635D")        # Technical muted text
COLOR_BORDER = QColor("#0D0D0D")       # 2px-2.5px solid ink borders
COLOR_ACCENT = QColor("#1B3BF5")       # Electric Cobalt
COLOR_ORANGE = QColor("#FF4D00")       # Cadmium Tangerine
COLOR_LIME = QColor("#00E575")         # Signal Lime / Active state
COLOR_PINK = QColor("#FF82B4")         # Sticker Pink
COLOR_YELLOW = QColor("#FFE500")       # Cyber Yellow
COLOR_CYAN = QColor("#00E5FF")         # Retro Cyan

FONT_SERIF = "Instrument Serif"
FONT_STICKER = "Syne"
FONT_MONO = "Space Mono"
FONT_SANS = "Manrope"


def load_all_fonts():
    fonts_dir = Path(__file__).resolve().parent.parent / "src" / "flowstate" / "resources" / "fonts"
    for font_file in fonts_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(font_file))


def make_font(family: str, size: int, bold: bool = False, italic: bool = False) -> QFont:
    f = QFont()
    f.setFamily(family)
    f.setPointSize(size)
    if bold:
        f.setBold(True)
    if italic:
        f.setItalic(True)
    return f


# --- GEOMETRIC NOMAD SYSTEMS EMBLEMS ---

def draw_nomad_diamond(painter: QPainter, cx: float, cy: float, r: float, fill_color: QColor = COLOR_INK):
    """Draws the 4-point concave diamond star from the Nomad Systems reference."""
    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(fill_color)

    path = QPainterPath()
    # Top point
    path.moveTo(cx, cy - r)
    # Curve inward to Right point
    path.quadTo(cx + r * 0.22, cy - r * 0.22, cx + r, cy)
    # Curve inward to Bottom point
    path.quadTo(cx + r * 0.22, cy + r * 0.22, cx, cy + r)
    # Curve inward to Left point
    path.quadTo(cx - r * 0.22, cy + r * 0.22, cx - r, cy)
    # Curve inward back to Top point
    path.quadTo(cx - r * 0.22, cy - r * 0.22, cx, cy - r)
    path.closeSubpath()

    painter.drawPath(path)
    painter.restore()


def draw_tactical_glyphs(painter: QPainter, x: float, y: float, size: float = 16):
    """Draws the triple Nomad icons: Meridian circle, Solid circle, Target cross circle."""
    painter.save()
    r = size / 2

    # 1. Meridian Circle
    c1_x = x + r
    c1_y = y + r
    painter.setPen(QPen(COLOR_INK, 1.6))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QPointF(c1_x, c1_y), r - 1, r - 1)
    # Meridian curved line
    painter.drawArc(QRectF(c1_x - (r - 2) * 0.5, c1_y - r + 1, (r - 2), 2 * r - 2), 0, 360 * 16)
    painter.drawLine(QPointF(c1_x, c1_y - r + 1), QPointF(c1_x, c1_y + r - 1))

    # 2. Solid Filled Circle
    c2_x = x + size + 7 + r
    c2_y = y + r
    painter.setPen(QPen(COLOR_INK, 1.6))
    painter.setBrush(COLOR_INK)
    painter.drawEllipse(QPointF(c2_x, c2_y), r - 1, r - 1)

    # 3. Circle with Diagonal Cross
    c3_x = x + 2 * (size + 7) + r
    c3_y = y + r
    painter.setPen(QPen(COLOR_INK, 1.6))
    painter.setBrush(Qt.NoBrush)
    painter.drawEllipse(QPointF(c3_x, c3_y), r - 1, r - 1)
    d = (r - 2) * 0.707
    painter.drawLine(QPointF(c3_x - d, c3_y - d), QPointF(c3_x + d, c3_y + d))
    painter.drawLine(QPointF(c3_x - d, c3_y + d), QPointF(c3_x + d, c3_y - d))

    painter.restore()


def draw_nomad_reticle(painter: QPainter, cx: float, cy: float, size: float = 18):
    """Draws the Nomad Systems concentric crosshair target reticle."""
    painter.save()
    painter.setPen(QPen(COLOR_INK, 1.2))
    painter.setBrush(Qt.NoBrush)

    # Outer circle
    r = size / 2
    painter.drawEllipse(QPointF(cx, cy), r * 0.7, r * 0.7)

    # Center dot
    painter.setBrush(COLOR_INK)
    painter.drawEllipse(QPointF(cx, cy), 1.5, 1.5)

    # Extended crosshair arms
    arm = r * 1.15
    painter.drawLine(QPointF(cx - arm, cy), QPointF(cx + arm, cy))
    painter.drawLine(QPointF(cx, cy - arm), QPointF(cx, cy + arm))

    painter.restore()


# --- TACTILE NEO-BRUTALIST COMPONENTS ---

class TactileButton(QPushButton):
    """A tactile button with physical 3D brutalist offset shadow that presses down on click."""

    def __init__(
        self,
        text: str,
        bg_color: QColor = COLOR_INK,
        text_color: QColor = COLOR_SURFACE,
        parent=None,
    ):
        super().__init__(text, parent)
        self.bg_color = bg_color
        self.text_color = text_color
        self.is_hovered = False
        self.is_pressed = False
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.is_pressed = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.is_pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dynamic offsets for physical tactile click
        if self.is_pressed:
            offset_x, offset_y = 4, 4
            shadow_dist = 0
        elif self.is_hovered:
            offset_x, offset_y = -1, -1
            shadow_dist = 6
        else:
            offset_x, offset_y = 0, 0
            shadow_dist = 4

        w = self.width() - 8
        h = self.height() - 8

        # Shadow
        if shadow_dist > 0:
            shadow_rect = QRectF(4 + offset_x + shadow_dist, 4 + offset_y + shadow_dist, w, h)
            painter.setPen(Qt.NoPen)
            painter.setBrush(COLOR_INK)
            painter.drawRect(shadow_rect)

        # Button face
        btn_rect = QRectF(4 + offset_x, 4 + offset_y, w, h)
        painter.setPen(QPen(COLOR_BORDER, 2.2))
        fill = self.bg_color if not self.is_hovered else (COLOR_ACCENT if self.bg_color == COLOR_INK else COLOR_PAPER)
        painter.setBrush(fill)
        painter.drawRect(btn_rect)

        # Text
        painter.setPen(self.text_color if not (self.is_hovered and self.bg_color != COLOR_INK) else COLOR_INK)
        font = make_font(FONT_STICKER, 9, bold=True)
        painter.setFont(font)
        painter.drawText(btn_rect, Qt.AlignCenter, self.text())

        painter.end()


class BrutalistCheckBox(QAbstractButton):
    """Custom neo-brutalist checkbox with vivid state, check glyph, and tactile pop."""

    def __init__(self, text: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.is_hovered = False

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Box dimensions
        box_size = 20
        box_y = (self.height() - box_size) / 2
        box_rect = QRectF(2, box_y, box_size, box_size)

        # Shadow behind checkbox
        shadow_rect = QRectF(4.5, box_y + 2.5, box_size, box_size)
        painter.setPen(Qt.NoPen)
        painter.setBrush(COLOR_INK)
        painter.drawRect(shadow_rect)

        # Checkbox square
        painter.setPen(QPen(COLOR_BORDER, 2))
        if self.isChecked():
            painter.setBrush(COLOR_ACCENT)  # Vivid Electric Cobalt!
        else:
            painter.setBrush(COLOR_SURFACE)
        painter.drawRect(box_rect)

        # Crisp geometric checkmark glyph
        if self.isChecked():
            painter.setPen(QPen(COLOR_SURFACE, 2.5, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            check_path = QPainterPath()
            check_path.moveTo(box_rect.left() + 4.5, box_rect.top() + 10.5)
            check_path.lineTo(box_rect.left() + 8.5, box_rect.top() + 14.5)
            check_path.lineTo(box_rect.left() + 15.5, box_rect.top() + 5.5)
            painter.drawPath(check_path)

        # Label text in Syne / Manrope (always medium weight, never bold!)
        text_rect = QRectF(32, 0, self.width() - 34, self.height())
        painter.setPen(COLOR_INK)
        font = make_font(FONT_SANS, 9, bold=False)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text())

        painter.end()



class GlobeStickerBadge(QWidget):
    """Wireframe globe sticker inspired by 'MINDFUL CORP WORLDWIDE MINDFULNESS'."""

    def __init__(self, text: str = "FLOWSTATE // OFFLINE 2026", parent=None):
        super().__init__(parent)
        self.text = text
        self.setFixedSize(175, 48)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width() - 5
        h = self.height() - 5
        rect = QRectF(2, 2, w, h)
        shadow_rect = QRectF(5, 5, w, h)

        # Die-cut brutalist shadow
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(13, 13, 13, 180))
        painter.drawRoundedRect(shadow_rect, h / 2, h / 2)

        # Sticker face in Soft Pink with bold border
        painter.setPen(QPen(COLOR_BORDER, 2))
        painter.setBrush(COLOR_PINK)
        painter.drawRoundedRect(rect, h / 2, h / 2)

        # Wireframe mini globe on left
        gx, gy, gr = 20, h / 2 + 2, 13
        painter.setPen(QPen(COLOR_BORDER, 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(gx, gy), gr, gr)
        painter.drawEllipse(QPointF(gx, gy), gr * 0.45, gr)
        painter.drawLine(QPointF(gx - gr, gy), QPointF(gx + gr, gy))

        # Sticker label
        painter.setPen(COLOR_INK)
        painter.setFont(make_font(FONT_STICKER, 7, bold=True))
        painter.drawText(QRectF(38, 7, w - 44, 16), Qt.AlignLeft, "FLOWSTATE // CORE")
        painter.setFont(make_font(FONT_MONO, 7))
        painter.drawText(QRectF(38, 24, w - 44, 16), Qt.AlignLeft, "OFFLINE AI // v0.2.6")

        painter.end()


class CreativeOasisSticker(QWidget):
    """Teardrop badge inspired by 'CREATIVE OASIS'."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(68, 62)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Hard shadow
        s_pts = [QPointF(37, 5), QPointF(67, 57), QPointF(7, 57)]
        painter.setPen(Qt.NoPen)
        painter.setBrush(COLOR_INK)
        painter.drawPolygon(QPolygonF(s_pts))

        # Teardrop triangle
        pts = [QPointF(34, 2), QPointF(64, 54), QPointF(4, 54)]
        painter.setPen(QPen(COLOR_BORDER, 2))
        painter.setBrush(COLOR_YELLOW)
        painter.drawPolygon(QPolygonF(pts))

        # Center graphic: Nomad diamond
        draw_nomad_diamond(painter, 34, 34, 9, fill_color=COLOR_INK)

        # Micro text
        painter.setPen(COLOR_INK)
        painter.setFont(make_font(FONT_MONO, 5, bold=True))
        painter.drawText(QRectF(10, 42, 48, 10), Qt.AlignCenter, "0-LATENCY")

        painter.end()


# --- NARROW COMPACT FLOATING HUD ---

class CompactFloatingHUD(QWidget):
    """Refined, compact floating HUD (240px wide, tactical, clean, no ALT_R chip)."""

    def __init__(self, state: str = "recording", parent=None):
        super().__init__(parent)
        self.state = state
        self.setFixedSize(240, 60)  # Clean, compact dimensions with ample vertical clearance
        self.phase = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(45)

    def _animate(self):
        self.phase += 0.18
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width() - 5
        h = self.height() - 5
        rect = QRectF(1.5, 1.5, w, h)
        shadow = QRectF(5, 5, w, h)

        # Hard brutalist shadow
        painter.setPen(Qt.NoPen)
        painter.setBrush(COLOR_INK)
        painter.drawRoundedRect(shadow, 4, 4)

        # Solid face
        painter.setPen(QPen(COLOR_BORDER, 2))
        painter.setBrush(COLOR_SURFACE)
        painter.drawRoundedRect(rect, 4, 4)

        if self.state == "recording":
            # 1. Pulsing Signal Lime Diamond Emblem
            cx, cy = 22, h / 2 + 1.5
            pulse_r = 7.5 + 1.2 * math.sin(self.phase * 3.5)
            draw_nomad_diamond(painter, cx, cy, pulse_r, fill_color=COLOR_LIME)
            # Center black micro dot
            painter.setPen(Qt.NoPen)
            painter.setBrush(COLOR_INK)
            painter.drawEllipse(QPointF(cx, cy), 2, 2)

            # 2. Compact 5-Bar Waveform with peak gradients
            bar_start_x = 42
            bar_w = 3.5
            gap = 2.5
            max_h = 24.0
            for i in range(5):
                lvl = 0.35 + 0.6 * abs(math.sin(self.phase * 2.5 + i * 0.9))
                bh = max(3.0, lvl * max_h)
                bx = bar_start_x + i * (bar_w + gap)
                by = (h / 2 + 1.5) - bh / 2
                b_rect = QRectF(bx, by, bar_w, bh)
                if i >= 3 and lvl > 0.75:
                    painter.setBrush(COLOR_ORANGE)
                else:
                    painter.setBrush(COLOR_INK)
                painter.drawRect(b_rect)

            # 3. Instrument Serif Timer Counter (vertically centered, ample bottom clearance)
            text_x = 80
            painter.setPen(COLOR_MUTED)
            painter.setFont(make_font(FONT_MONO, 7, bold=True))
            painter.drawText(QRectF(text_x, 8, 150, 12), Qt.AlignLeft | Qt.AlignVCenter, "FLOWSTATE // REC")

            painter.setPen(COLOR_INK)
            font_timer = make_font(FONT_SERIF, 20)
            painter.setFont(font_timer)
            painter.drawText(QRectF(text_x, 18, 65, 30), Qt.AlignLeft | Qt.AlignVCenter, "00:14")

            painter.setPen(COLOR_MUTED)
            font_ms = make_font(FONT_MONO, 8)
            painter.setFont(font_ms)
            painter.drawText(QRectF(text_x + 58, 20, 35, 26), Qt.AlignLeft | Qt.AlignVCenter, ".8")

        else:
            # PROCESSING STATE (Compact 240px)
            bx, by = 16, (h - 22) / 2 + 1.5
            sq_rect = QRectF(bx, by, 22, 22)
            painter.setPen(QPen(COLOR_BORDER, 1.6))
            painter.setBrush(COLOR_ACCENT)
            painter.drawRect(sq_rect)

            # Spinning crosshair inside
            painter.setPen(QPen(COLOR_SURFACE, 1.8))
            scx = sq_rect.center().x()
            scy = sq_rect.center().y()
            cs = 5.0
            painter.drawLine(scx - cs, scy, scx + cs, scy)
            painter.drawLine(scx, scy - cs, scx, scy + cs)

            # Text
            text_x = 50
            painter.setPen(COLOR_MUTED)
            painter.setFont(make_font(FONT_MONO, 7, bold=True))
            painter.drawText(QRectF(text_x, 8, 180, 12), Qt.AlignLeft | Qt.AlignVCenter, "LOCAL LLM // QWEN2.5")

            painter.setPen(COLOR_INK)
            font_proc = make_font(FONT_SERIF, 16, italic=True)
            painter.setFont(font_proc)
            painter.drawText(QRectF(text_x, 19, 180, 28), Qt.AlignLeft | Qt.AlignVCenter, "Formatting text...")

        painter.end()


# --- MASTER SAMPLE WINDOW WITH TEXTURES & INTERACTION ---

class BrutalistPanel(QFrame):
    """Container with paper tooth, 2.5px border, and hard shadow (clean, no corner reticles)."""

    def __init__(self, parent=None, bg_color: QColor = COLOR_SURFACE, shadow_offset: int = 5):
        super().__init__(parent)
        self.bg_color = bg_color
        self.shadow_offset = shadow_offset

_paper_pixmap: QPixmap | None = None

def get_cached_paper_texture() -> QPixmap | None:
    global _paper_pixmap
    if _paper_pixmap is None:
        tex_path = Path(__file__).resolve().parent.parent / "src" / "flowstate" / "resources" / "textures" / "tangible_paper.jpg"
        if tex_path.exists():
            _paper_pixmap = QPixmap(str(tex_path))
    return _paper_pixmap


class BrutalistPanel(QFrame):
    """Container with tactile paper tooth, 2.2px border, and hard shadow (clean, no corner reticles)."""

    def __init__(self, parent=None, bg_color: QColor = COLOR_SURFACE, shadow_offset: int = 5):
        super().__init__(parent)
        self.bg_color = bg_color
        self.shadow_offset = shadow_offset

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width() - self.shadow_offset
        h = self.height() - self.shadow_offset
        r_card = QRectF(1, 1, w, h)
        r_shadow = QRectF(self.shadow_offset, self.shadow_offset, w, h)

        # 1. Shadow
        painter.setPen(Qt.NoPen)
        painter.setBrush(COLOR_INK)
        painter.drawRect(r_shadow)

        # 2. Card surface with tangible paper grain texture
        painter.fillRect(r_card, self.bg_color)
        tex = get_cached_paper_texture()
        if tex and not tex.isNull():
            painter.setCompositionMode(QPainter.CompositionMode_Multiply)
            painter.setOpacity(0.18)
            painter.drawTiledPixmap(r_card, tex)
            painter.setOpacity(1.0)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        painter.setPen(QPen(COLOR_BORDER, 2.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r_card)
        painter.end()


class MasterRevampedShowcase(QWidget):
    """Interactive Master Showcase incorporating paper grain, Syne, Nomad emblems, and compact HUD."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowState // Neo-Brutalist & Tactile Showcase v2")
        self.resize(1080, 880)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._build_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 1. Base art paper wash
        painter.fillRect(self.rect(), COLOR_PAPER)

        # 2. Tile subtle fibrous paper grain & crease texture with Multiply
        tex = get_cached_paper_texture()
        if tex and not tex.isNull():
            painter.setCompositionMode(QPainter.CompositionMode_Multiply)
            painter.setOpacity(0.20)
            painter.drawTiledPixmap(self.rect(), tex)
            painter.setOpacity(1.0)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        # 3. Technical coordinate ruler marks along bottom
        painter.setPen(QPen(COLOR_INK, 1))
        for x in range(30, self.width() - 30, 25):
            painter.drawLine(x, self.height() - 10, x, self.height() - 5)
        painter.end()


    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(18)

        # 1. HEADER WITH NOMAD GRAPHICS + STICKER BADGES
        header = BrutalistPanel(bg_color=COLOR_SURFACE, shadow_offset=6)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(28, 20, 28, 20)

        # Left title column
        left_col = QVBoxLayout()
        left_col.setSpacing(6)

        # Badge strip
        badge_strip = QHBoxLayout()
        badge_strip.setSpacing(12)

        # Nomad triple glyphs
        glyph_box = QWidget()
        glyph_box.setFixedSize(70, 24)
        glyph_box.paintEvent = lambda e: draw_tactical_glyphs(QPainter(glyph_box), 0, 4, 14)
        badge_strip.addWidget(glyph_box)

        # Syne sticker badge
        s_badge = QLabel("NMD-X7 AIRFRAME // REV 02.6")
        s_badge.setFont(make_font(FONT_MONO, 7, bold=True))
        s_badge.setStyleSheet("background: #0D0D0D; color: #FFFFFF; padding: 4px 8px; border: 1.5px solid #0D0D0D;")
        badge_strip.addWidget(s_badge)

        # Globe sticker
        globe_sticker = GlobeStickerBadge()
        badge_strip.addWidget(globe_sticker)

        # Creative Oasis teardrop
        oasis = CreativeOasisSticker()
        badge_strip.addWidget(oasis)

        badge_strip.addStretch(1)
        left_col.addLayout(badge_strip)

        # Big Expressive Instrument Serif Headline
        h1 = QLabel("FlowState Dictation")
        h1.setFont(make_font(FONT_SERIF, 38))
        h1.setStyleSheet("color: #0D0D0D; margin-top: 4px;")
        left_col.addWidget(h1)

        # Syne sub-headline
        sub = QLabel("LOCAL OFFLINE SPEECH INTELLIGENCE & SPATIAL VISUAL CAPTURE")
        sub.setFont(make_font(FONT_STICKER, 8, bold=True))
        sub.setStyleSheet("color: #66635D; letter-spacing: 1.5px;")
        left_col.addWidget(sub)

        h_layout.addLayout(left_col, 1)

        # Right Nomad Systems Technical Stamp
        nomad_box = QFrame()
        nomad_box.setFixedSize(160, 105)
        nomad_box.setStyleSheet("background: #ECE8DC; border: 2px solid #0D0D0D;")
        n_layout = QVBoxLayout(nomad_box)
        n_layout.setContentsMargins(10, 8, 10, 8)
        n_layout.setSpacing(2)

        lbl_p = QLabel("PAYLOAD TYPE M-04")
        lbl_p.setFont(make_font(FONT_MONO, 6, bold=True))
        lbl_p.setStyleSheet("color: #0D0D0D;")
        n_layout.addWidget(lbl_p)

        lbl_11 = QLabel("[ 11 ] NOMAD")
        lbl_11.setFont(make_font(FONT_STICKER, 13, bold=True))
        lbl_11.setStyleSheet("color: #0D0D0D;")
        n_layout.addWidget(lbl_11)

        lbl_sys = QLabel("250 CAL.30 LINKED")
        lbl_sys.setFont(make_font(FONT_MONO, 6))
        lbl_sys.setStyleSheet("color: #66635D;")
        n_layout.addWidget(lbl_sys)

        lbl_rev = QLabel("REV 02.6 // WIN64")
        lbl_rev.setFont(make_font(FONT_MONO, 6, bold=True))
        lbl_rev.setStyleSheet("color: #FF4D00;")
        n_layout.addWidget(lbl_rev)

        h_layout.addWidget(nomad_box)
        root.addWidget(header)

        # 2. MAIN 2-COLUMN SECTION
        cols = QHBoxLayout()
        cols.setSpacing(18)

        # LEFT COLUMN: COMPACT FLOATING HUD SHOWCASE & TACTILE BUTTONS
        left_panel = QVBoxLayout()
        left_panel.setSpacing(16)

        hud_card = BrutalistPanel(bg_color=COLOR_SURFACE, shadow_offset=5)
        hud_layout = QVBoxLayout(hud_card)
        hud_layout.setContentsMargins(22, 18, 22, 18)
        hud_layout.setSpacing(12)

        # Header
        hud_head = QHBoxLayout()
        title_hud = QLabel("Tactical Floating HUD (Compact 256px)")
        title_hud.setFont(make_font(FONT_SERIF, 21))
        title_hud.setStyleSheet("color: #0D0D0D;")
        hud_head.addWidget(title_hud)
        hud_head.addStretch(1)

        chip_spatial = QLabel("SPATIAL OVERLAY")
        chip_spatial.setFont(make_font(FONT_MONO, 7, bold=True))
        chip_spatial.setStyleSheet("background: #FF4D00; color: #FFFFFF; padding: 3px 8px; border: 1.5px solid #0D0D0D;")
        hud_head.addWidget(chip_spatial)
        hud_layout.addLayout(hud_head)

        desc_hud = QLabel("Narrower, dense, military/aerospace form-factor. Won't occlude your typing area:")
        desc_hud.setFont(make_font(FONT_SANS, 9))
        desc_hud.setStyleSheet("color: #66635D;")
        hud_layout.addWidget(desc_hud)

        # State 1: Recording HUD
        lbl_s1 = QLabel("STATE 01 // LISTENING & LIVE AUDIO")
        lbl_s1.setFont(make_font(FONT_MONO, 7, bold=True))
        lbl_s1.setStyleSheet("color: #0D0D0D; margin-top: 4px;")
        hud_layout.addWidget(lbl_s1)

        self.hud_rec = CompactFloatingHUD(state="recording")
        hud_layout.addWidget(self.hud_rec, 0, Qt.AlignCenter)

        # State 2: Processing HUD
        lbl_s2 = QLabel("STATE 02 // LOCAL LLM FORMATTING")
        lbl_s2.setFont(make_font(FONT_MONO, 7, bold=True))
        lbl_s2.setStyleSheet("color: #0D0D0D; margin-top: 6px;")
        hud_layout.addWidget(lbl_s2)

        self.hud_proc = CompactFloatingHUD(state="processing")
        hud_layout.addWidget(self.hud_proc, 0, Qt.AlignCenter)

        left_panel.addWidget(hud_card)

        # Tactile Buttons Card
        btn_card = BrutalistPanel(bg_color=COLOR_SURFACE_ALT, shadow_offset=5)
        btn_layout = QVBoxLayout(btn_card)
        btn_layout.setContentsMargins(22, 16, 22, 16)
        btn_layout.setSpacing(12)

        lbl_btns = QLabel("Interactive 3D Physical Buttons")
        lbl_btns.setFont(make_font(FONT_SERIF, 19))
        lbl_btns.setStyleSheet("color: #0D0D0D;")
        btn_layout.addWidget(lbl_btns)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)

        b1 = TactileButton("START DICTATING", bg_color=COLOR_INK, text_color=COLOR_SURFACE)
        b2 = TactileButton("OPEN SETTINGS", bg_color=COLOR_SURFACE, text_color=COLOR_INK)
        btn_row.addWidget(b1)
        btn_row.addWidget(b2)
        btn_layout.addLayout(btn_row)

        lbl_btn_hint = QLabel("↑ Hover lifts with deeper 6px shadow; Click depresses flush into paper.")
        lbl_btn_hint.setFont(make_font(FONT_MONO, 7))
        lbl_btn_hint.setStyleSheet("color: #66635D;")
        btn_layout.addWidget(lbl_btn_hint)

        left_panel.addWidget(btn_card)
        cols.addLayout(left_panel, 1)

        # RIGHT COLUMN: REVAMPED CHECKBOXES, CONTROLS & SETTINGS KIT
        right_panel = QVBoxLayout()
        right_panel.setSpacing(16)

        controls_card = BrutalistPanel(bg_color=COLOR_SURFACE, shadow_offset=5)
        ctrl_layout = QVBoxLayout(controls_card)
        ctrl_layout.setContentsMargins(24, 18, 24, 18)
        ctrl_layout.setSpacing(14)

        # Title
        c_head = QHBoxLayout()
        title_ctrl = QLabel("Settings & Tactile Controls")
        title_ctrl.setFont(make_font(FONT_SERIF, 21))
        title_ctrl.setStyleSheet("color: #0D0D0D;")
        c_head.addWidget(title_ctrl)
        c_head.addStretch(1)

        chip_ui = QLabel("NEO-BRUTALIST V2")
        chip_ui.setFont(make_font(FONT_MONO, 7, bold=True))
        chip_ui.setStyleSheet("background: #0D0D0D; color: #FFFFFF; padding: 3px 8px;")
        c_head.addWidget(chip_ui)
        ctrl_layout.addLayout(c_head)

        # Segmented Tabs in Syne font
        tab_row = QHBoxLayout()
        tab_row.setSpacing(0)
        tabs = ["GENERAL", "SHORTCUTS", "MODELS", "CAPTURE"]
        for idx, t_name in enumerate(tabs):
            tb = QPushButton(t_name)
            tb.setFixedHeight(34)
            tb.setFont(make_font(FONT_STICKER, 8, bold=True))
            if idx == 0:
                tb.setStyleSheet("""
                    QPushButton {
                        background-color: #0D0D0D;
                        color: #FFFFFF;
                        border: 2px solid #0D0D0D;
                        border-right: 1px solid #0D0D0D;
                    }
                """)
            else:
                tb.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #0D0D0D;
                        border: 2px solid #0D0D0D;
                        border-left: none;
                    }
                    QPushButton:hover {
                        background-color: #ECE8DC;
                    }
                """)
            tab_row.addWidget(tb)
        ctrl_layout.addLayout(tab_row)

        # Form Enclosure
        form_frame = QFrame()
        form_frame.setObjectName("form_frame")
        form_frame.setStyleSheet("""
            QFrame#form_frame {
                background: #FFFFFF;
                border: 2px solid #0D0D0D;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        f_layout = QVBoxLayout(form_frame)
        f_layout.setContentsMargins(14, 14, 14, 14)
        f_layout.setSpacing(12)

        # Microphone input
        lbl_mic = QLabel("01 // TRANSDUCER SELECTION")
        lbl_mic.setFont(make_font(FONT_MONO, 7, bold=True))
        lbl_mic.setStyleSheet("color: #66635D;")
        f_layout.addWidget(lbl_mic)

        combo = QComboBox()
        combo.setFixedHeight(36)
        combo.setFont(make_font(FONT_SANS, 9))
        combo.addItem("Default: Focusrite Scarlett 2i2 (WASAPI)")
        combo.addItem("Microphone (Realtek Audio)")
        combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #0D0D0D;
                padding: 4px 10px;
                background: #FFFFFF;
                color: #0D0D0D;
            }
            QComboBox::drop-down {
                border-left: 2px solid #0D0D0D;
                width: 28px;
                background: #ECE8DC;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                border: 2px solid #0D0D0D;
                color: #0D0D0D;
                selection-background-color: #1B3BF5;
                selection-color: #FFFFFF;
                outline: none;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 32px;
                padding: 6px 10px;
                color: #0D0D0D;
                background-color: #FFFFFF;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #1B3BF5;
                color: #FFFFFF;
            }
        """)
        f_layout.addWidget(combo)


        # Keybinding input
        lbl_keys = QLabel("02 // GLOBAL HOTKEY CHORD")
        lbl_keys.setFont(make_font(FONT_MONO, 7, bold=True))
        lbl_keys.setStyleSheet("color: #66635D;")
        f_layout.addWidget(lbl_keys)

        key_row = QHBoxLayout()
        key_row.setSpacing(0)
        key_input = QLineEdit("Ctrl + Shift + Space")
        key_input.setFixedHeight(36)
        key_input.setFont(make_font(FONT_MONO, 8, bold=True))
        key_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #0D0D0D;
                padding: 4px 10px;
                background: #FFFFFF;
                color: #0D0D0D;
            }
        """)
        key_row.addWidget(key_input, 1)

        key_btn = QPushButton("BIND")
        key_btn.setFixedHeight(36)
        key_btn.setFont(make_font(FONT_STICKER, 8, bold=True))
        key_btn.setStyleSheet("""
            QPushButton {
                background: #ECE8DC;
                color: #0D0D0D;
                border: 2px solid #0D0D0D;
                border-left: none;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: #00E575;
            }
        """)
        key_row.addWidget(key_btn)
        f_layout.addLayout(key_row)

        # REVAMPED CHECKBOXES (User highlighted: "especially the checkmarks are just black, make them much better")
        lbl_cb = QLabel("03 // SYSTEM BEHAVIOR TOGGLES")
        lbl_cb.setFont(make_font(FONT_MONO, 7, bold=True))
        lbl_cb.setStyleSheet("color: #66635D;")
        f_layout.addWidget(lbl_cb)

        cb1 = BrutalistCheckBox("Launch FlowState automatically on Windows boot", checked=True)
        cb2 = BrutalistCheckBox("Play acoustic tactile audio cue on record/stop", checked=True)
        cb3 = BrutalistCheckBox("Circular mouse gesture spatial screenshot capture", checked=False)
        f_layout.addWidget(cb1)
        f_layout.addWidget(cb2)
        f_layout.addWidget(cb3)

        ctrl_layout.addWidget(form_frame)
        right_panel.addWidget(controls_card)
        cols.addLayout(right_panel, 1)

        root.addLayout(cols)


def take_snapshot(output_path: Path):
    load_all_fonts()
    window = MasterRevampedShowcase()
    window.resize(1080, 880)

    pixmap = QPixmap(window.size())
    window.render(pixmap)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(output_path), "PNG")
    print(f"SUCCESS: Saved snapshot v2 to {output_path}")


def main():
    app = QApplication(sys.argv)
    load_all_fonts()

    if "--snapshot" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--snapshot") + 1]) if len(sys.argv) > sys.argv.index("--snapshot") + 1 else Path("sample_ui.png")
        take_snapshot(out_path)
        sys.exit(0)

    window = MasterRevampedShowcase()
    screen = app.primaryScreen().availableGeometry()
    x = max(0, (screen.width() - 1080) // 2)
    y = max(0, (screen.height() - 880) // 2)
    window.move(x, y)
    window.show()
    window.raise_()
    window.activateWindow()
    print("FlowState Neo-Brutalist UI Preview Window Opened at", x, y)
    sys.exit(app.exec())




if __name__ == "__main__":
    main()
