"""Reusable neo-brutalist UI components for FlowState."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from .fonts import make_font
from .theme import ACCENT, BORDER, FONT_FAMILY, FONT_FAMILY_MONO, FONT_FAMILY_STICKER, INK, PAPER_RAISED


class BrutalistCheckBox(QAbstractButton):
    """Custom neo-brutalist checkbox.

    - Bold 2px solid border with hard offset shadow
    - Vivid Electric Cobalt fill when checked
    - Sharp geometric white checkmark
    - Text font is ALWAYS medium/regular weight (never bold)
    """

    def __init__(self, text: str, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        box_size = 18
        box_y = (self.height() - box_size) / 2
        box_rect = QRectF(2, box_y, box_size, box_size)
        shadow_rect = QRectF(4, box_y + 2, box_size, box_size)

        # 1. Brutalist hard mini shadow
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(BORDER))
        painter.drawRect(shadow_rect)

        # 2. Box surface & border
        painter.setPen(QPen(QColor(BORDER), 2))
        if self.isChecked():
            painter.setBrush(QColor(ACCENT))
        else:
            painter.setBrush(QColor(PAPER_RAISED))
        painter.drawRect(box_rect)

        # 3. Geometric white checkmark
        if self.isChecked():
            painter.setPen(QPen(QColor(PAPER_RAISED), 2.2, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
            check_path = QPainterPath()
            check_path.moveTo(box_rect.left() + 4.0, box_rect.top() + 9.5)
            check_path.lineTo(box_rect.left() + 7.5, box_rect.top() + 13.0)
            check_path.lineTo(box_rect.left() + 14.0, box_rect.top() + 5.0)
            painter.drawPath(check_path)

        # 4. Label text (always medium weight, never bold!)
        text_rect = QRectF(30, 0, self.width() - 32, self.height())
        painter.setPen(QColor(INK))
        font = make_font(FONT_FAMILY, 9, bold=False)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text())

        painter.end()


class StickerBadge(QWidget):
    """Graphic sticker badge for status chips and revision numbers with guaranteed high contrast."""

    def __init__(
        self,
        text: str,
        bg_color: QColor | str = BORDER,
        text_color: QColor | str | None = None,
        is_pill: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.text = text
        self.bg_color = QColor(bg_color)
        if text_color is not None:
            self.text_color = QColor(text_color)
        else:
            # Auto high contrast: if bg is dark, text is pure white; if light, text is dark ink
            luminance = (self.bg_color.red() * 0.299 + self.bg_color.green() * 0.587 + self.bg_color.blue() * 0.114)
            self.text_color = QColor("#FFFFFF") if luminance < 140 else QColor("#1A1A1A")

        self.is_pill = is_pill
        self.setFixedHeight(24)

    def setText(self, text: str) -> None:
        self.text = text
        self.updateGeometry()
        self.update()

    def getText(self) -> str:
        return self.text

    def sizeHint(self):
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QFontMetrics
        font = make_font(FONT_FAMILY_MONO, 7.5, bold=True)
        fm = QFontMetrics(font)
        w = max(72, fm.horizontalAdvance(self.text) + 20)
        return QSize(w, 24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(1, 1, self.width() - 3, self.height() - 3)
        radius = rect.height() / 2 if self.is_pill else 3

        # 3D Hard offset drop shadow
        shadow_rect = QRectF(2.5, 2.5, rect.width(), rect.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 200))
        if self.is_pill:
            painter.drawRoundedRect(shadow_rect, radius, radius)
        else:
            painter.drawRoundedRect(shadow_rect, radius, radius)

        # Surface & border
        painter.setPen(QPen(QColor(BORDER), 1.8))
        painter.setBrush(self.bg_color)
        painter.drawRoundedRect(rect, radius, radius)

        # Text
        painter.setPen(self.text_color)
        font = make_font(FONT_FAMILY_MONO, 7.5, bold=True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.text)
        painter.end()


import math
from PySide6.QtCore import QTimer


class ActivitySpinner(QWidget):
    """Continuous rotating geometric neo-brutalist activity indicator."""

    def __init__(self, size: int = 22, color: QColor | str = BORDER, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = QColor(color)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(40)

    def _rotate(self):
        self._angle = (self._angle + 20) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center = QPointF(self.width() / 2.0, self.height() / 2.0)
        painter.translate(center)
        painter.rotate(self._angle)

        spoke_count = 8
        radius_outer = (self.width() / 2.0) - 2.0
        radius_inner = radius_outer * 0.42

        for i in range(spoke_count):
            angle = i * (360.0 / spoke_count)
            # Smooth trailing alpha sweep
            alpha = int(45 + (210 * ((i + 1) / spoke_count)))
            c = QColor(self._color)
            c.setAlpha(alpha)
            painter.setPen(QPen(c, 2.4, Qt.SolidLine, Qt.SquareCap))
            rad = math.radians(angle)
            p1 = QPointF(radius_inner * math.cos(rad), radius_inner * math.sin(rad))
            p2 = QPointF(radius_outer * math.cos(rad), radius_outer * math.sin(rad))
            painter.drawLine(p1, p2)

        painter.end()


class GeometricMotif(QWidget):
    """Subtle neo-brutalist geometric decorative motif (star, crosshair, dot-grid)."""

    def __init__(
        self,
        motif: str = "star",
        size: int = 16,
        color: QColor | str = INK,
        parent=None,
    ):
        super().__init__(parent)
        self.motif = motif
        self.setFixedSize(size, size)
        self.color = QColor(color)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        if self.motif == "star":
            # 4-pointed diamond star (✦)
            path = QPainterPath()
            path.moveTo(cx, 1)
            path.quadTo(cx, cy, w - 1, cy)
            path.quadTo(cx, cy, cx, h - 1)
            path.quadTo(cx, cy, 1, cy)
            path.quadTo(cx, cy, cx, 1)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.color)
            painter.drawPath(path)

        elif self.motif == "cross":
            # Architectural crosshair (+)
            painter.setPen(QPen(self.color, 1.8, Qt.SolidLine, Qt.SquareCap))
            painter.drawLine(QPointF(cx, 2), QPointF(cx, h - 2))
            painter.drawLine(QPointF(2, cy), QPointF(w - 2, cy))

        elif self.motif == "dot_grid":
            # 2x2 dot matrix (::)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.color)
            radius = 1.6
            d = 3.5
            for dx in (-d, d):
                for dy in (-d, d):
                    painter.drawEllipse(QPointF(cx + dx, cy + dy), radius, radius)

        painter.end()

