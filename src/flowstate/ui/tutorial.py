"""First-time user quickstart tutorial for FlowState.

Guides users through:
1. Push-to-Talk practice with live speech transcription.
2. Hands-Free recording and spatial image visual context highlighting (Hold Ctrl + drag).
"""

from __future__ import annotations

import logging
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import paths
from .fonts import make_font
from .theme import (
    BORDER,
    FONT_FAMILY,
    FONT_FAMILY_DISPLAY,
    FONT_FAMILY_MONO,
    FONT_FAMILY_STICKER,
    INK,
    LIME,
    MUTED_TEXT,
    PAPER,
    PAPER_ALT,
    PAPER_RAISED,
    YELLOW,
    build_stylesheet,
    paint_paper_background,
)
from .widgets import GeometricMotif, StickerBadge

logger = logging.getLogger("flowstate.tutorial")


class _SpatialDemoCanvas(QFrame):
    """Interactive dashboard canvas with animated guide showing how to hold Ctrl and drag."""

    def __init__(self, on_selected=None, on_unauthorized_drag=None, parent=None):
        super().__init__(parent)
        self.on_selected = on_selected
        self.on_unauthorized_drag = on_unauthorized_drag
        self.setCursor(Qt.CrossCursor)
        self.setFixedHeight(270)
        self.setProperty("role", "card")
        self.setToolTip("the thing you want to fix")
        self._drag_start: QPoint | None = None
        self._current_rect: QRect | None = None
        self._selected_rect: QRect | None = None
        self._user_interacting = False
        self._listening_active = False
        self._warning_message = ""
        self._warning_tick = 0
        self._broken_button_rect = QRect(386, 146, 185, 44)

        # Loop animation to teach user to hold Ctrl and drag
        self._anim_tick = 0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(40)  # 25 fps
        self._anim_timer.timeout.connect(self._on_anim_step)
        self._anim_timer.start()

    @property
    def listening_active(self) -> bool:
        return self._listening_active

    @listening_active.setter
    def listening_active(self, val: bool) -> None:
        self._listening_active = val
        if val:
            self._warning_tick = 0
            self._warning_message = ""
        self.update()

    def flash_warning(self, msg: str = "⚠️ PRESS HOTKEY FIRST: Tap hotkey to start listening before dragging!") -> None:
        self._warning_message = msg
        self._warning_tick = 60  # ~2.4 seconds at 25fps
        self.update()

    def _on_anim_step(self):
        if self._warning_tick > 0:
            self._warning_tick -= 1
            if self._warning_tick == 0:
                self._warning_message = ""
            self.update()

        if self._selected_rect is not None or self._user_interacting:
            if self._warning_tick <= 0:
                self._anim_timer.stop()
            return
        self._anim_tick = (self._anim_tick + 1) % 65
        self.update()

    def grab_broken_button(self) -> QPixmap:
        self._user_interacting = True
        if self._anim_timer.isActive():
            self._anim_timer.stop()
        self._current_rect = None
        self._selected_rect = None
        self.repaint()
        b = self._get_button_rect()
        pad_rect = b.adjusted(-6, -6, 6, 6)
        pad_rect = pad_rect.intersected(self.rect())
        pix = self.grab(pad_rect)
        self._selected_rect = pad_rect
        self.update()
        return pix

    def _get_button_rect(self) -> QRect:
        w = 185
        h = 44
        if self.width() > 100:
            return QRect(self.width() - 32 - w, 148, w, h)
        return self._broken_button_rect

    @property
    def broken_button_rect(self) -> QRect:
        return self._get_button_rect()

    @broken_button_rect.setter
    def broken_button_rect(self, val: QRect) -> None:
        self._broken_button_rect = val

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self._listening_active:
                self.flash_warning("⚠️ PRESS HOTKEY FIRST: Tap hotkey to start listening before dragging!")
                if self.on_unauthorized_drag:
                    self.on_unauthorized_drag()
                event.accept()
                return
            self._user_interacting = True
            if self._anim_timer.isActive() and self._warning_tick <= 0:
                self._anim_timer.stop()
            self._drag_start = event.pos()
            self._current_rect = QRect(self._drag_start, self._drag_start)
            self._selected_rect = None
            self.update()

    def mouseMoveEvent(self, event):
        if not self._listening_active:
            return
        if self._drag_start is not None:
            self._current_rect = QRect(self._drag_start, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if not self._listening_active:
            self._drag_start = None
            return
        if event.button() == Qt.LeftButton and self._drag_start is not None:
            self._selected_rect = self._current_rect
            self._drag_start = None
            self.update()
            if self.on_selected and self._selected_rect and self._selected_rect.width() > 15 and self._selected_rect.height() > 15:
                pixmap = self.grab(self._selected_rect)
                self.on_selected(self._selected_rect, pixmap)

    def _draw_cursor_pointer(self, painter: QPainter, x: int, y: int):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        cursor_poly = [
            QPoint(x, y),
            QPoint(x, y + 14),
            QPoint(x + 4, y + 10),
            QPoint(x + 7, y + 17),
            QPoint(x + 10, y + 15),
            QPoint(x + 7, y + 9),
            QPoint(x + 11, y + 9),
        ]
        painter.setPen(QPen(QColor(INK), 1.5))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawPolygon(cursor_poly)
        painter.restore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Reduced opacity for background dashboard wireframe (soft & subtle)
        painter.save()
        painter.setOpacity(0.35)

        # 1. Windows Window Top Titlebar
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#F0F0F0"))
        painter.drawRoundedRect(0, 0, self.width(), 26, 4, 4)
        painter.fillRect(0, 16, self.width(), 10, QColor("#F0F0F0"))

        # App Window Title & Icon (Left)
        painter.setFont(make_font(FONT_FAMILY_MONO, 7.5, bold=True))
        painter.setPen(QColor("#1A1A1A"))
        painter.drawText(16, 18, "🗔  APP // MOCKUP_01")

        # Native Windows Window Controls (Right: Minimize, Maximize, Close)
        ctrl_x = self.width() - 78
        painter.setPen(QPen(QColor("#666666"), 1.2))
        painter.drawLine(ctrl_x, 15, ctrl_x + 9, 15)
        painter.drawRect(ctrl_x + 22, 10, 9, 9)
        painter.drawLine(ctrl_x + 44, 10, ctrl_x + 53, 19)
        painter.drawLine(ctrl_x + 53, 10, ctrl_x + 44, 19)

        # Hairline divider below titlebar
        painter.setPen(QPen(QColor("#D0D0D0"), 1.2))
        painter.drawLine(0, 26, self.width(), 26)

        # 2. Row 1: 3 balanced cards with wireframe skeleton glyphs (NO fake readable text!)
        usable_w = self.width() - 32
        gap = 10
        card_w = (usable_w - 2 * gap) // 3
        c1_x = 16
        c2_x = c1_x + card_w + gap
        c3_x = c2_x + card_w + gap

        for i, cx in enumerate([c1_x, c2_x, c3_x]):
            card_rect = QRect(cx, 38, card_w, 78)
            painter.setPen(QPen(QColor("#1A1A1A"), 1.2))
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(card_rect, 3, 3)

            # Skeleton header bar
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#D0D0D0"))
            painter.drawRoundedRect(QRect(cx + 14, 52, 60, 7), 2, 2)

            if i < 2:
                # Value skeleton block
                painter.setBrush(QColor("#1A1A1A"))
                painter.drawRoundedRect(QRect(cx + 14, 68, 85, 18), 3, 3)
                # Trend pill bar (neutral greyscale, no green)
                painter.setBrush(QColor("#888888"))
                painter.drawRoundedRect(QRect(cx + 14, 96, 50, 7), 2, 2)
            else:
                # Button skeleton
                btn_r = QRect(cx + 12, 68, card_w - 24, 32)
                painter.setPen(QPen(QColor("#1A1A1A"), 1.2))
                painter.setBrush(QColor("#F5F5F5"))
                painter.drawRoundedRect(btn_r, 3, 3)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#888888"))
                painter.drawRoundedRect(QRect(cx + 26, 80, card_w - 52, 8), 2, 2)

        # 3. Row 2: Action panel with wireframe skeleton rows
        action_card_rect = QRect(16, 128, usable_w, 86)
        painter.setPen(QPen(QColor("#1A1A1A"), 1.2))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(action_card_rect, 3, 3)

        # Skeleton text lines
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1A1A1A"))
        painter.drawRoundedRect(QRect(32, 148, min(220, usable_w - 240), 11), 2, 2)

        painter.setBrush(QColor("#777777"))
        painter.drawRoundedRect(QRect(32, 170, min(280, usable_w - 240), 8), 2, 2)
        painter.setBrush(QColor("#AAAAAA"))
        painter.drawRoundedRect(QRect(32, 188, min(180, usable_w - 240), 8), 2, 2)

        painter.restore()

        # 4. The naturally misaligned/crooked button: skeleton glyph (Full Opacity)
        b_rect = self._get_button_rect()
        painter.save()
        center = b_rect.center()
        painter.translate(center.x(), center.y())
        painter.rotate(-5.5)
        local_rect = QRect(-b_rect.width() // 2, -b_rect.height() // 2, b_rect.width(), b_rect.height())

        painter.setPen(QPen(QColor("#1A1A1A"), 1.8))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(local_rect, 3, 3)

        # Skeleton bar inside the crooked button
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1A1A1A"))
        skel_w = min(110, b_rect.width() - 36)
        painter.drawRoundedRect(QRect(-skel_w // 2, -5, skel_w, 10), 2, 2)
        painter.restore()

        # Tooltip callout pointing to the crooked element: "the thing you want to fix"
        from PySide6.QtGui import QFontMetrics, QPolygon
        tip_text = "the thing you want to fix"
        tip_font = make_font(FONT_FAMILY_MONO, 7.5, bold=True)
        fm = QFontMetrics(tip_font)
        text_w = fm.horizontalAdvance(tip_text)
        tip_w = text_w + 16
        tip_h = 22
        tip_x = int(center.x() - tip_w / 2)
        tip_y = int(b_rect.top() - 25)

        painter.save()
        tip_rect = QRect(tip_x, tip_y, tip_w, tip_h)
        painter.setPen(QPen(QColor("#1A1A1A"), 1.2))
        painter.setBrush(QColor("#1A1A1A"))
        painter.drawRoundedRect(tip_rect, 3, 3)

        # Downward pointer triangle
        ptr_poly = QPolygon([
            QPoint(tip_x + tip_w // 2 - 5, tip_y + tip_h),
            QPoint(tip_x + tip_w // 2 + 5, tip_y + tip_h),
            QPoint(tip_x + tip_w // 2, tip_y + tip_h + 5),
        ])
        painter.drawPolygon(ptr_poly)

        # Tooltip text
        painter.setFont(tip_font)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(tip_rect, Qt.AlignCenter, tip_text)
        painter.restore()

        # 5. Bottom hint / warning banner
        if self._warning_tick > 0:
            warn_rect = QRect(16, 226, usable_w, 28)
            painter.setPen(QPen(QColor("#E03131"), 1.5))
            painter.setBrush(QColor("#FFF3BF"))
            painter.drawRoundedRect(warn_rect, 4, 4)
            painter.setFont(make_font(FONT_FAMILY_MONO, 7.8, bold=True))
            painter.setPen(QColor("#C92A2A"))
            painter.drawText(warn_rect, Qt.AlignCenter, self._warning_message)
        else:
            painter.setFont(make_font(FONT_FAMILY_MONO, 7.8))
            if not self._listening_active:
                painter.setPen(QColor("#666666"))
                painter.drawText(16, 246, ">> Tap the Hotkey above to start listening & talking.")
            elif self._selected_rect is None:
                painter.setPen(QColor("#1A1A1A"))
                painter.drawText(16, 246, ">> Step 2: Now Hold Ctrl + Click & Drag across the element while talking.")
            else:
                painter.setPen(QColor("#1A1A1A"))
                painter.drawText(16, 246, ">> Step 3: Button captured! Tap your hotkey again to finish & paste directly into chatbot.")

        # 6. Animated guide demonstration
        if self._selected_rect is None and not self._user_interacting:
            target_box = self.broken_button_rect.adjusted(-6, -6, 6, 6)
            tick = self._anim_tick

            if self._listening_active:
                if tick < 10:
                    self._draw_cursor_pointer(painter, target_box.left(), target_box.top())
                    pill_x = min(target_box.left() + 8, self.width() - 136)
                    pill_rect = QRect(pill_x, target_box.top() - 20, 118, 18)
                    painter.setPen(QPen(QColor("#1A1A1A"), 1.2))
                    painter.setBrush(QColor("#1A1A1A"))
                    painter.drawRoundedRect(pill_rect, 9, 9)
                    painter.setFont(make_font(FONT_FAMILY_MONO, 6.8, bold=True))
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(pill_rect, Qt.AlignCenter, "⌨️ Hold Ctrl + Drag")
                elif tick < 45:
                    t = (tick - 10) / 35.0
                    t = t * t * (3.0 - 2.0 * t)  # Smooth ease
                    cur_x = int(target_box.left() + (target_box.right() - target_box.left()) * t)
                    cur_y = int(target_box.top() + (target_box.bottom() - target_box.top()) * t)
                    drag_rect = QRect(target_box.topLeft(), QPoint(cur_x, cur_y))

                    painter.setPen(QPen(QColor("#1A1A1A"), 1.8, Qt.DashLine))
                    painter.setBrush(QColor(0, 0, 0, 25))
                    painter.drawRect(drag_rect)

                    # Crosshair pins
                    painter.setPen(QPen(QColor("#1A1A1A"), 1.8))
                    painter.setBrush(QColor("#1A1A1A"))
                    pcs = 4
                    for pt in [drag_rect.topLeft(), drag_rect.topRight(), drag_rect.bottomLeft(), drag_rect.bottomRight()]:
                        painter.drawRect(QRect(pt.x() - pcs // 2, pt.y() - pcs // 2, pcs, pcs))

                    self._draw_cursor_pointer(painter, cur_x, cur_y)
                    pill_x = min(cur_x - 50, self.width() - 136)
                    if pill_x < 16:
                        pill_x = 16
                    pill_rect = QRect(pill_x, target_box.top() - 20, 118, 18)
                    painter.setPen(QPen(QColor("#1A1A1A"), 1.2))
                    painter.setBrush(QColor("#1A1A1A"))
                    painter.drawRoundedRect(pill_rect, 9, 9)
                    painter.setFont(make_font(FONT_FAMILY_MONO, 6.8, bold=True))
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(pill_rect, Qt.AlignCenter, "⌨️ Hold Ctrl + Drag")
                elif tick < 62:
                    painter.setPen(QPen(QColor("#1A1A1A"), 2, Qt.DashLine))
                    painter.setBrush(QColor(0, 0, 0, 30))
                    painter.drawRect(target_box)

                    painter.setPen(QPen(QColor("#1A1A1A"), 2))
                    painter.setBrush(QColor("#1A1A1A"))
                    pcs = 4
                    for pt in [target_box.topLeft(), target_box.topRight(), target_box.bottomLeft(), target_box.bottomRight()]:
                        painter.drawRect(QRect(pt.x() - pcs // 2, pt.y() - pcs // 2, pcs, pcs))

                    self._draw_cursor_pointer(painter, target_box.right(), target_box.bottom())
                    pill_x = min(target_box.right() - 80, self.width() - 144)
                    pill_rect = QRect(pill_x, target_box.bottom() + 4, 126, 18)
                    painter.setPen(QPen(QColor("#1A1A1A"), 1.2))
                    painter.setBrush(QColor("#1A1A1A"))
                    painter.drawRoundedRect(pill_rect, 9, 9)
                    painter.setFont(make_font(FONT_FAMILY_MONO, 6.8, bold=True))
                    painter.setPen(QColor("#FFFFFF"))
                    painter.drawText(pill_rect, Qt.AlignCenter, "✦ Release to capture")

        # 7. Real user drag selection
        rect_to_draw = self._current_rect or self._selected_rect
        if rect_to_draw and rect_to_draw.isValid():
            painter.setPen(QPen(QColor(BORDER), 2, Qt.DashLine))
            painter.setBrush(QColor(214, 255, 56, 85))  # High-contrast acid green
            painter.drawRect(rect_to_draw)

            # Crosshair pins at corners
            painter.setPen(QPen(QColor(BORDER), 2))
            painter.setBrush(QColor(BORDER))
            pcs = 4
            for pt in [rect_to_draw.topLeft(), rect_to_draw.topRight(), rect_to_draw.bottomLeft(), rect_to_draw.bottomRight()]:
                painter.drawRect(QRect(pt.x() - pcs // 2, pt.y() - pcs // 2, pcs, pcs))

        painter.end()


class TutorialDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._has_captured_snippet = False
        self._is_step2_listening = False
        self.setWindowTitle("FlowState Quickstart")
        self.setStyleSheet(build_stylesheet())
        self.resize(720, 630)
        self.setMinimumSize(680, 590)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config
        self.ptt_shortcut = cfg.shortcuts.push_to_talk.upper()
        self.toggle_shortcut = cfg.shortcuts.toggle.upper()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 26, 36, 22)
        outer.setSpacing(14)

        # Top header with logo and step badge
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        from .icon import _draw_mark
        logo_lbl = QLabel()
        logo_lbl.setPixmap(_draw_mark(38, "#121212"))
        logo_lbl.setFixedSize(38, 38)
        top_row.addWidget(logo_lbl)

        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(2)
        eyebrow_row = QHBoxLayout()
        eyebrow_row.setSpacing(6)
        eyebrow_star = GeometricMotif("star", size=11, color=INK)
        eyebrow = QLabel("SYS.01 // FIRST-TIME SETUP")
        eyebrow.setProperty("role", "eyebrow")
        eyebrow_row.addWidget(eyebrow_star)
        eyebrow_row.addWidget(eyebrow)
        eyebrow_row.addStretch(1)

        self.step_headline = QLabel("Welcome to FlowState")
        self.step_headline.setProperty("role", "headline")
        header_text_col.addLayout(eyebrow_row)
        header_text_col.addWidget(self.step_headline)
        top_row.addLayout(header_text_col, 1)

        self.step_badge = StickerBadge("✦ STEP 01 / 02", bg_color=INK, text_color="#FFFFFF", is_pill=False)
        top_row.addWidget(self.step_badge)
        outer.addLayout(top_row)

        rule = QFrame()
        rule.setProperty("role", "rule")
        outer.addWidget(rule)

        # 2-Step Stacked Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_step1_ptt())
        self.stack.addWidget(self._build_step2_spatial())
        outer.addWidget(self.stack, 1)

        # Navigation row
        nav_row = QHBoxLayout()
        self.prev_btn = QPushButton("← Back")
        self.prev_btn.setProperty("role", "secondary")
        self.prev_btn.setFixedWidth(110)
        self.prev_btn.clicked.connect(self._go_prev)
        self.prev_btn.hide()

        nav_row.addWidget(self.prev_btn)
        nav_row.addStretch(1)

        self.next_btn = QPushButton("Next: Visual Highlight →")
        self.next_btn.setProperty("role", "primary")
        self.next_btn.setMinimumWidth(180)
        self.next_btn.clicked.connect(self._go_next)
        nav_row.addWidget(self.next_btn)

        outer.addLayout(nav_row)

        # Hook controller signals
        if hasattr(self._controller.signals, "recording_started"):
            self._controller.signals.recording_started.connect(self._on_recording_started)
        self._controller.signals.recording_finished.connect(self._on_speech_transcribed)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())

    # -- Step 1: Push to Talk Practice ---------------------------------
    def _build_step1_ptt(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        instr = QLabel(
            f"Hold <b>{self.ptt_shortcut}</b>, speak the phrase below aloud, then release."
        )
        instr.setFont(make_font(FONT_FAMILY, 9.5))
        instr.setWordWrap(True)
        layout.addWidget(instr)

        # Action / Hotkey prompt row (matching Step 2 style & text)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        read_badge = QLabel("READ THIS ALOUD:")
        read_badge.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        read_badge.setStyleSheet("color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 4px 8px;")
        self.sample_prompt = "I swear I'm not crazy, my computer made me say this."
        read_text = QLabel(f'"{self.sample_prompt}"')
        read_text.setFont(make_font(FONT_FAMILY_DISPLAY, 13, bold=True))
        read_text.setStyleSheet("color: #1A1A1A;")
        read_text.setWordWrap(True)
        action_row.addWidget(read_badge)
        action_row.addWidget(read_text)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        # Interactive live transcription box
        box_card = QFrame()
        box_card.setProperty("role", "card")
        bc_layout = QVBoxLayout(box_card)
        bc_layout.setContentsMargins(16, 12, 16, 12)
        bc_layout.setSpacing(6)

        bc_header = QHBoxLayout()
        bc_label = QLabel("LIVE DICTATION RESULT:")
        bc_label.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        self.step1_success_badge = StickerBadge("SPEECH CAPTURED! ✓", bg_color=LIME, text_color="#1A1A1A", is_pill=True)
        self.step1_success_badge.hide()
        bc_header.addWidget(bc_label)
        bc_header.addWidget(self.step1_success_badge)
        bc_header.addStretch(1)

        demo_paste_btn = QPushButton("PASTE SAMPLE")
        demo_paste_btn.setProperty("role", "secondary")
        demo_paste_btn.setFixedHeight(24)
        demo_paste_btn.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 8px; font-weight: 800; padding: 2px 8px;")
        demo_paste_btn.clicked.connect(self._simulate_step1_press)
        bc_header.addWidget(demo_paste_btn)
        bc_layout.addLayout(bc_header)

        self.step1_text = QTextEdit()
        self.step1_text.setPlaceholderText("Transcribed text appears here automatically when you speak...")
        self.step1_text.setFixedHeight(270)
        self.step1_text.setFont(make_font(FONT_FAMILY, 11))
        self.step1_text.textChanged.connect(self._on_step1_text_changed)
        bc_layout.addWidget(self.step1_text)

        layout.addWidget(box_card)
        layout.addStretch(1)
        return page

    def _simulate_step1_press(self) -> None:
        self.step1_text.setText(self.sample_prompt)

    def _on_step1_text_changed(self) -> None:
        has_text = bool(self.step1_text.toPlainText().strip())
        if has_text:
            self.step1_success_badge.show()
            self.next_btn.setText("Next: Visual Highlight →")
            self.next_btn.setEnabled(True)

    # -- Step 2: Hands-Free & Image Drag-and-Paste ----------------------
    def _build_step2_spatial(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        step2_instr = QLabel(
            f"Press <b>{self.toggle_shortcut}</b>, hold <b>Ctrl + Drag</b> over the button, then press it again to paste."
        )
        step2_instr.setFont(make_font(FONT_FAMILY, 9.5))
        step2_instr.setWordWrap(True)
        layout.addWidget(step2_instr)

        # Action / Hotkey prompt row
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        read_badge = QLabel("READ THIS ALOUD:")
        read_badge.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        read_badge.setStyleSheet("color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 4px 8px;")
        read_text = QLabel('"Fix this thing"')
        read_text.setFont(make_font(FONT_FAMILY_DISPLAY, 14, bold=True))
        read_text.setStyleSheet("color: #1A1A1A;")
        action_row.addWidget(read_badge)
        action_row.addWidget(read_text)
        action_row.addStretch(1)

        self.step2_hotkey_btn = QPushButton(f"🎙️ TAP HOTKEY ({self.toggle_shortcut})")
        self.step2_hotkey_btn.setCursor(Qt.PointingHandCursor)
        self.step2_hotkey_btn.setFixedHeight(30)
        self.step2_hotkey_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #121212;
                color: #FFFFFF;
                border: 2px solid #121212;
                border-radius: 4px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10px;
                font-weight: 900;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background-color: #333333;
            }}
            """
        )
        self.step2_hotkey_btn.clicked.connect(self._toggle_step2_listening)
        action_row.addWidget(self.step2_hotkey_btn)
        layout.addLayout(action_row)

        # Interactive Dashboard Canvas (235px tall, no empty gap below!)
        self.demo_canvas = _SpatialDemoCanvas(
            on_selected=self._on_spatial_selected,
            on_unauthorized_drag=self._on_unauthorized_drag,
        )
        layout.addWidget(self.demo_canvas)

        # Combined Target: Captured snippet thumbnail + Text Box
        target_card = QFrame()
        target_card.setProperty("role", "card")
        tc_layout = QVBoxLayout(target_card)
        tc_layout.setContentsMargins(14, 10, 14, 10)
        tc_layout.setSpacing(6)

        tc_header = QHBoxLayout()
        tc_label = QLabel("CAPTURED CONTEXT & TRANSCRIPTION:")
        tc_label.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        tc_header.addWidget(tc_label)

        self.step2_badge = StickerBadge("WAITING FOR HOTKEY...", bg_color="#EAE4D8", text_color="#5C5751", is_pill=True)
        tc_header.addWidget(self.step2_badge)

        tc_header.addStretch(1)

        demo_paste_btn = QPushButton("PASTE SAMPLE")
        demo_paste_btn.setProperty("role", "secondary")
        demo_paste_btn.setFixedHeight(24)
        demo_paste_btn.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 8px; font-weight: 800; padding: 2px 8px;")
        demo_paste_btn.clicked.connect(self._fill_step2_sample)
        tc_header.addWidget(demo_paste_btn)

        tc_layout.addLayout(tc_header)

        # Preview row with thumbnail + compact text box
        content_row = QHBoxLayout()
        content_row.setSpacing(10)

        self.thumbnail_label = QLabel("[ NO IMAGE CAPTURED ]")
        self.thumbnail_label.setFixedSize(95, 42)
        self.thumbnail_label.setStyleSheet("background-color: #EFE8DC; border: 1.5px dashed #5C5751; color: #5C5751; font-size: 7.5px;")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        content_row.addWidget(self.thumbnail_label)

        self.step2_text = QTextEdit()
        self.step2_text.setFont(make_font(FONT_FAMILY, 9.5))
        self.step2_text.setPlaceholderText("Transcribed thought & screenshot appear here when hotkey is pressed again...")
        self.step2_text.setFixedHeight(42)
        self.step2_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.step2_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.step2_text.setStyleSheet("QTextEdit { padding: 6px 10px; border: 1.5px solid #1A1A1A; border-radius: 3px; background-color: #FFFFFF; }")
        content_row.addWidget(self.step2_text, 1)

        tc_layout.addLayout(content_row)

        layout.addWidget(target_card)
        layout.addStretch(1)
        return page

    def _toggle_step2_listening(self) -> None:
        self._is_step2_listening = not self._is_step2_listening
        if self._is_step2_listening:
            # 1. Start listening state
            self.demo_canvas.listening_active = True
            self.step2_hotkey_btn.setText(f"⏹️ STOP HOTKEY ({self.toggle_shortcut})")
            self.step2_hotkey_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {LIME};
                    color: #121212;
                    border: 2px solid #121212;
                    border-radius: 4px;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 10px;
                    font-weight: 900;
                    padding: 4px 14px;
                }}
                QPushButton:hover {{
                    background-color: #C2F01A;
                }}
                """
            )
            self.step2_badge.setText("● LISTENING... Speak & Hold Ctrl+Drag")
            self.step2_badge.setColors(LIME, "#121212")
            self.step2_badge.show()
        else:
            # 2. Stop listening and paste into context box & clipboard
            self.demo_canvas.listening_active = False
            self.step2_hotkey_btn.setText(f"🎙️ TAP HOTKEY ({self.toggle_shortcut})")
            self.step2_hotkey_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: #121212;
                    color: #FFFFFF;
                    border: 2px solid #121212;
                    border-radius: 4px;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 10px;
                    font-weight: 900;
                    padding: 4px 14px;
                }}
                QPushButton:hover {{
                    background-color: #333333;
                }}
                """
            )
            if not self._has_captured_snippet:
                pixmap = self.demo_canvas.grab_broken_button()
                self._on_spatial_selected(self.demo_canvas.broken_button_rect, pixmap)
            final_text = "Fix this thing"
            self.step2_text.setText(final_text)
            QApplication.clipboard().setText(final_text)
            self.step2_badge.setText("PASTED INTO CHATBOT! ✓")
            self.step2_badge.setColors(LIME, "#121212")
            self.step2_badge.show()
            self.next_btn.setText("Open FlowState →")
            self.next_btn.setEnabled(True)

    def _on_unauthorized_drag(self) -> None:
        self.step2_badge.setText(f"⚠️ TAP {self.toggle_shortcut} FIRST!")
        self.step2_badge.setColors("#FFF3BF", "#C92A2A")
        self.step2_badge.show()

    def _on_spatial_selected(self, rect: QRect, pixmap: QPixmap) -> None:
        self._has_captured_snippet = True
        scaled = pixmap.scaled(95, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumbnail_label.setPixmap(scaled)
        self.thumbnail_label.setStyleSheet("border: 1.5px solid #1A1A1A; background-color: #FFFFFF;")
        if self._is_step2_listening:
            self.step2_badge.setText(f"✦ CAPTURED! Tap {self.toggle_shortcut} to finish & paste")
            self.step2_badge.setColors(LIME, "#121212")
        else:
            self.step2_badge.setText("COPIED & PASTED! ✓")
            self.step2_badge.setColors(LIME, "#121212")
        self.step2_badge.show()

    def _handle_step2_hotkey_paste(self) -> None:
        if not self._is_step2_listening:
            self._toggle_step2_listening()  # start listening
        self._toggle_step2_listening()  # finish listening and paste

    def _fill_step2_sample(self) -> None:
        if not self._has_captured_snippet:
            pixmap = self.demo_canvas.grab_broken_button()
            self._on_spatial_selected(self.demo_canvas.broken_button_rect, pixmap)
        self._is_step2_listening = False
        self.demo_canvas.listening_active = False
        self.step2_hotkey_btn.setText(f"🎙️ TAP HOTKEY ({self.toggle_shortcut})")
        self.step2_hotkey_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #121212;
                color: #FFFFFF;
                border: 2px solid #121212;
                border-radius: 4px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10px;
                font-weight: 900;
                padding: 4px 14px;
            }}
            QPushButton:hover {{
                background-color: #333333;
            }}
            """
        )
        self.step2_text.setText("Fix this thing")
        QApplication.clipboard().setText("Fix this thing")
        self.step2_badge.setText("PASTED INTO CHATBOT! ✓")
        self.step2_badge.setColors(LIME, "#121212")
        self.step2_badge.show()
        self.next_btn.setText("Open FlowState →")
        self.next_btn.setEnabled(True)

    def _on_recording_started(self) -> None:
        if self.stack.currentIndex() == 1:
            self._is_step2_listening = True
            self.demo_canvas.listening_active = True
            self.step2_hotkey_btn.setText(f"⏹️ STOP HOTKEY ({self.toggle_shortcut})")
            self.step2_hotkey_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {LIME};
                    color: #121212;
                    border: 2px solid #121212;
                    border-radius: 4px;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 10px;
                    font-weight: 900;
                    padding: 4px 14px;
                }}
                QPushButton:hover {{
                    background-color: #C2F01A;
                }}
                """
            )
            self.step2_badge.setText("● LISTENING... Speak & Hold Ctrl+Drag")
            self.step2_badge.setColors(LIME, "#121212")
            self.step2_badge.show()

    def _on_speech_transcribed(self, text: str) -> None:
        if self.stack.currentIndex() == 0:
            if text:
                self.step1_text.setText(text.strip())
        elif self.stack.currentIndex() == 1:
            self._is_step2_listening = False
            self.demo_canvas.listening_active = False
            self.step2_hotkey_btn.setText(f"🎙️ TAP HOTKEY ({self.toggle_shortcut})")
            self.step2_hotkey_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: #121212;
                    color: #FFFFFF;
                    border: 2px solid #121212;
                    border-radius: 4px;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 10px;
                    font-weight: 900;
                    padding: 4px 14px;
                }}
                QPushButton:hover {{
                    background-color: #333333;
                }}
                """
            )
            if not self._has_captured_snippet:
                pixmap = self.demo_canvas.grab_broken_button()
                self._on_spatial_selected(self.demo_canvas.broken_button_rect, pixmap)
            final_text = text.strip() if text and text.strip() else "Fix this thing"
            self.step2_text.setText(final_text)
            QApplication.clipboard().setText(final_text)
            self.step2_badge.setText("PASTED INTO CHATBOT! ✓")
            self.step2_badge.setColors(LIME, "#121212")
            self.step2_badge.show()
            self.next_btn.setText("Open FlowState →")
            self.next_btn.setEnabled(True)

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        key = event.key()

        is_toggle = (
            (modifiers & Qt.ControlModifier)
            and (modifiers & Qt.ShiftModifier)
            and key == Qt.Key_Space
        )
        is_ptt = (
            (modifiers & Qt.ControlModifier)
            and not (modifiers & Qt.ShiftModifier)
            and key == Qt.Key_M
        )

        if is_toggle or is_ptt:
            if self.stack.currentIndex() == 1:
                self._toggle_step2_listening()
                event.accept()
                return
            elif self.stack.currentIndex() == 0:
                self.step1_text.setText(self.sample_prompt)
                event.accept()
                return

        super().keyPressEvent(event)

    # -- Navigation logic ----------------------------------------------
    def _go_next(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            self.stack.setCurrentIndex(1)
            self.step_badge.setText("✦ STEP 02 / 02")
            self.step_headline.setText("Hands-Free & Visual Capture")
            self.prev_btn.show()
            self.next_btn.setText("Open FlowState →")
            self.next_btn.adjustSize()
        elif idx == 1:
            # Mark first run complete!
            paths.first_run_flag_path().write_text("done", encoding="utf-8")
            logger.info("First-run tutorial completed. Flag saved.")
            self.accept()

    def _go_prev(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 1:
            self.stack.setCurrentIndex(0)
            self.step_badge.setText("✦ STEP 01 / 02")
            self.step_headline.setText("Welcome to FlowState")
            self.prev_btn.hide()
            self.next_btn.setText("Next: Visual Highlight →")
            self.next_btn.adjustSize()

