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
    """Graphic sticker badge for status chips and revision numbers."""

    def __init__(
        self,
        text: str,
        bg_color: QColor | str = BORDER,
        text_color: QColor | str = PAPER_RAISED,
        is_pill: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.text = text
        self.bg_color = QColor(bg_color)
        self.text_color = QColor(text_color)
        self.is_pill = is_pill
        self.setFixedHeight(24)

    def sizeHint(self):
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QFontMetrics
        font = make_font(FONT_FAMILY_MONO, 7, bold=True)
        fm = QFontMetrics(font)
        w = max(70, fm.horizontalAdvance(self.text) + 24)
        return QSize(w, 24)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(1, 1, self.width() - 3, self.height() - 3)
        radius = rect.height() / 2 if self.is_pill else 0

        # Shadow
        shadow_rect = QRectF(2.5, 2.5, rect.width(), rect.height())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 160))
        if self.is_pill:
            painter.drawRoundedRect(shadow_rect, radius, radius)
        else:
            painter.drawRect(shadow_rect)

        # Face
        painter.setPen(QPen(QColor(BORDER), 1.5))
        painter.setBrush(self.bg_color)
        if self.is_pill:
            painter.drawRoundedRect(rect, radius, radius)
        else:
            painter.drawRect(rect)

        # Text
        painter.setPen(self.text_color)
        font = make_font(FONT_FAMILY_MONO, 7, bold=True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self.text)
        painter.end()
