"""First-time user quickstart tutorial for FlowState.

Guides users through:
1. Push-to-Talk practice with live speech transcription.
2. Hands-Free recording and spatial image visual context highlighting (Hold Ctrl + drag).
"""

from __future__ import annotations

import logging
from PySide6.QtCore import QPoint, QRect, Qt
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
    """Interactive visual image canvas where user holds Ctrl and drags to select a region."""

    def __init__(self, on_selected=None, parent=None):
        super().__init__(parent)
        self.on_selected = on_selected
        self.setCursor(Qt.CrossCursor)
        self.setFixedHeight(105)
        self.setProperty("role", "card")
        self._drag_start: QPoint | None = None
        self._current_rect: QRect | None = None
        self._selected_rect: QRect | None = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
            self._current_rect = QRect(self._drag_start, self._drag_start)
            self._selected_rect = None
            self.update()

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            self._current_rect = QRect(self._drag_start, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_start is not None:
            self._selected_rect = self._current_rect
            self._drag_start = None
            self.update()
            if self.on_selected and self._selected_rect and self._selected_rect.width() > 15 and self._selected_rect.height() > 15:
                # Grab the cropped thumbnail of the selected region
                pixmap = self.grab(self._selected_rect)
                self.on_selected(self._selected_rect, pixmap)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Subtle drafting corner ticks (+)
        painter.setPen(QPen(QColor("#A8A299"), 1.5))
        cs = 6
        painter.drawLine(8, 8 + cs, 8, 8)
        painter.drawLine(8, 8, 8 + cs, 8)
        painter.drawLine(self.width() - 8 - cs, 8, self.width() - 8, 8)
        painter.drawLine(self.width() - 8, 8, self.width() - 8, 8 + cs)
        painter.drawLine(8, self.height() - 8 - cs, 8, self.height() - 8)
        painter.drawLine(8, self.height() - 8, 8 + cs, self.height() - 8)
        painter.drawLine(self.width() - 8 - cs, self.height() - 8, self.width() - 8, self.height() - 8)
        painter.drawLine(self.width() - 8, self.height() - 8 - cs, self.width() - 8, self.height() - 8)

        # Visual architecture diagram mockup
        painter.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))

        # Box 1: API Gateway
        b1 = QRect(24, 28, 140, 36)
        painter.setPen(QPen(QColor(BORDER), 1.5))
        painter.setBrush(QColor("#F0ECE4"))
        painter.drawRect(b1)
        painter.setPen(QColor(INK))
        painter.drawText(b1, Qt.AlignCenter, "[ API GATEWAY ]")

        # Arrow 1
        painter.setPen(QPen(QColor(BORDER), 1.8))
        painter.drawLine(164, 46, 204, 46)
        painter.drawLine(198, 41, 204, 46)
        painter.drawLine(198, 51, 204, 46)

        # Box 2: Auth Service
        b2 = QRect(204, 28, 150, 36)
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRect(b2)
        painter.drawText(b2, Qt.AlignCenter, "[ AUTH SERVICE ]")

        # Arrow 2
        painter.drawLine(354, 46, 394, 46)
        painter.drawLine(388, 41, 394, 46)
        painter.drawLine(388, 51, 394, 46)

        # Box 3: Token Vault
        b3 = QRect(394, 28, 140, 36)
        painter.setBrush(QColor(LIME))
        painter.drawRect(b3)
        painter.drawText(b3, Qt.AlignCenter, "[ TOKEN VAULT ]")

        # Hint text
        painter.setPen(QColor("#7A746C"))
        painter.setFont(make_font(FONT_FAMILY_MONO, 8))
        painter.drawText(24, 96, ">> TIP: Hold Ctrl + Click & Drag over any component above to capture context.")

        # Draw active dragging rectangle
        rect_to_draw = self._current_rect or self._selected_rect
        if rect_to_draw and rect_to_draw.isValid():
            # Highlight fill
            painter.setPen(QPen(QColor(BORDER), 2, Qt.DashLine))
            painter.setBrush(QColor(214, 255, 56, 75))  # Semi-transparent lime
            painter.drawRect(rect_to_draw)

            # Draw crosshair pins at corners
            painter.setPen(QPen(QColor(BORDER), 2))
            painter.setBrush(QColor(BORDER))
            pcs = 4
            for pt in [rect_to_draw.topLeft(), rect_to_draw.topRight(), rect_to_draw.bottomLeft(), rect_to_draw.bottomRight()]:
                painter.drawRect(QRect(pt.x() - pcs//2, pt.y() - pcs//2, pcs, pcs))

        painter.end()


class TutorialDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("FlowState Quickstart")
        self.setStyleSheet(build_stylesheet())
        self.resize(700, 590)
        self.setMinimumSize(660, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config
        self.ptt_shortcut = cfg.shortcuts.push_to_talk.upper()
        self.toggle_shortcut = cfg.shortcuts.toggle.upper()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 26, 36, 22)
        outer.setSpacing(14)

        # Top header with step badge
        top_row = QHBoxLayout()
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

        # Hook controller transcription signal
        self._controller.signals.recording_finished.connect(self._on_speech_transcribed)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())

    # -- Step 1: Push to Talk Practice ---------------------------------
    def _build_step1_ptt(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(12)

        instr = QLabel(
            f"Hold your push-to-talk hotkey (<b>{self.ptt_shortcut}</b>), speak the prompt below, and release."
        )
        instr.setFont(make_font(FONT_FAMILY, 10))
        instr.setWordWrap(True)
        layout.addWidget(instr)

        # Prompt card
        prompt_card = QFrame()
        prompt_card.setProperty("role", "card")
        pc_layout = QVBoxLayout(prompt_card)
        pc_layout.setContentsMargins(18, 14, 18, 14)
        pc_eyebrow = QLabel("READ THIS ALOUD:")
        pc_eyebrow.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        pc_eyebrow.setStyleSheet("color: #5C5751;")
        self.sample_prompt = (
            "FlowState turns natural speech into clean text in real-time."
        )
        prompt_text = QLabel(f'"{self.sample_prompt}"')
        prompt_text.setFont(make_font(FONT_FAMILY_DISPLAY, 18))
        prompt_text.setStyleSheet("color: #1A1A1A;")
        prompt_text.setWordWrap(True)
        pc_layout.addWidget(pc_eyebrow)
        pc_layout.addWidget(prompt_text)
        layout.addWidget(prompt_card)

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
        bc_header.addStretch(1)
        bc_header.addWidget(self.step1_success_badge)
        bc_layout.addLayout(bc_header)

        self.step1_text = QTextEdit()
        self.step1_text.setPlaceholderText("Transcribed text appears here automatically when you speak...")
        self.step1_text.setFixedHeight(85)
        self.step1_text.textChanged.connect(self._on_step1_text_changed)
        bc_layout.addWidget(self.step1_text)

        layout.addWidget(box_card)
        layout.addStretch(1)
        return page

    def _on_speech_transcribed(self, text: str) -> None:
        if text:
            if self.stack.currentIndex() == 0:
                self.step1_text.setText(text.strip())
            elif self.stack.currentIndex() == 1:
                self.step2_text.setText(text.strip())

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
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(10)

        step2_instr = QLabel(
            f"<b>Step 2:</b> Read the statement aloud, then <b>Hold Ctrl + Drag</b> across the diagram to capture it."
        )
        step2_instr.setFont(make_font(FONT_FAMILY, 9.5))
        step2_instr.setWordWrap(True)
        layout.addWidget(step2_instr)

        # Statement prompt
        read_row = QHBoxLayout()
        read_badge = QLabel("PROMPT:")
        read_badge.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        read_badge.setStyleSheet("color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 2px 6px;")
        read_text = QLabel('"Reviewing the Token Vault component architecture."')
        read_text.setFont(make_font(FONT_FAMILY_DISPLAY, 14))
        read_row.addWidget(read_badge)
        read_row.addWidget(read_text, 1)
        layout.addLayout(read_row)

        # Interactive Diagram Canvas
        demo_canvas = _SpatialDemoCanvas(on_selected=self._on_spatial_selected)
        layout.addWidget(demo_canvas)

        # Combined Target: Captured snippet chip + Text Box
        target_card = QFrame()
        target_card.setProperty("role", "card")
        tc_layout = QVBoxLayout(target_card)
        tc_layout.setContentsMargins(14, 10, 14, 10)
        tc_layout.setSpacing(8)

        tc_header = QHBoxLayout()
        tc_label = QLabel("CAPTURED CONTEXT & TRANSCRIPTION:")
        tc_label.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        tc_header.addWidget(tc_label)

        self.step2_badge = StickerBadge("IMAGE SNIPPET LINKED! ✓", bg_color=YELLOW, text_color="#1A1A1A", is_pill=True)
        self.step2_badge.hide()
        tc_header.addWidget(self.step2_badge)

        tc_header.addStretch(1)

        demo_paste_btn = QPushButton("PASTE SAMPLE")
        demo_paste_btn.setProperty("role", "secondary")
        demo_paste_btn.setFixedHeight(24)
        demo_paste_btn.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 8px; font-weight: 800; padding: 2px 8px;")
        demo_paste_btn.clicked.connect(self._fill_step2_sample)
        tc_header.addWidget(demo_paste_btn)

        tc_layout.addLayout(tc_header)

        # Preview row with thumbnail + text box
        content_row = QHBoxLayout()
        content_row.setSpacing(10)

        self.thumbnail_label = QLabel("[ NO IMAGE CAPTURED ]")
        self.thumbnail_label.setFixedSize(110, 65)
        self.thumbnail_label.setStyleSheet("background-color: #EFE8DC; border: 1.5px dashed #5C5751; color: #5C5751; font-size: 8px;")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        content_row.addWidget(self.thumbnail_label)

        self.step2_text = QTextEdit()
        self.step2_text.setPlaceholderText("Transcribed thought will appear here alongside the captured visual snippet...")
        self.step2_text.setFixedHeight(65)
        content_row.addWidget(self.step2_text, 1)

        tc_layout.addLayout(content_row)

        layout.addWidget(target_card)
        layout.addStretch(1)
        return page

    def _on_spatial_selected(self, rect: QRect, pixmap: QPixmap) -> None:
        scaled = pixmap.scaled(110, 65, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.thumbnail_label.setPixmap(scaled)
        self.thumbnail_label.setStyleSheet("border: 1.5px solid #1A1A1A; background-color: #FFFFFF;")
        self.step2_badge.setText(f"SNIPPET ATTACHED ({rect.width()}x{rect.height()}px) ✓")
        self.step2_badge.show()
        if not self.step2_text.toPlainText().strip():
            self.step2_text.setText("Reviewing the Token Vault component architecture.")
        self.next_btn.setText("Open FlowState →")
        self.next_btn.setEnabled(True)

    def _fill_step2_sample(self) -> None:
        self.step2_text.setText("Reviewing the Token Vault component architecture.")
        self.next_btn.setText("Open FlowState →")

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

