"""Interactive in-app first-time user onboarding tutorial module for FlowState.

Guides users through:
1. Push-to-Talk practice with live speech transcription into a test box.
2. Hands-Free recording and spatial drag-and-drop context highlighting.
3. Shortcut customization, 1-click clipboard history, and automatic restart purging.
"""

from __future__ import annotations

import logging
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
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
    """Interactive card inside Step 2 that lets the user click and drag
    to experience spatial visual highlight selection."""

    def __init__(self, on_selected=None, parent=None):
        super().__init__(parent)
        self.on_selected = on_selected
        self.setCursor(Qt.CrossCursor)
        self.setFixedHeight(140)
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
                self.on_selected(self._selected_rect)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Subtle drafting corner ticks (+)
        painter.setPen(QPen(QColor("#A8A299"), 1.5))
        cs = 5
        painter.drawLine(8, 8 + cs, 8, 8)
        painter.drawLine(8, 8, 8 + cs, 8)
        painter.drawLine(self.width() - 8 - cs, 8, self.width() - 8, 8)
        painter.drawLine(self.width() - 8, 8, self.width() - 8, 8 + cs)
        painter.drawLine(8, self.height() - 8 - cs, 8, self.height() - 8)
        painter.drawLine(8, self.height() - 8, 8 + cs, self.height() - 8)
        painter.drawLine(self.width() - 8 - cs, self.height() - 8, self.width() - 8, self.height() - 8)
        painter.drawLine(self.width() - 8, self.height() - 8 - cs, self.width() - 8, self.height() - 8)

        # Mock code/document content inside the canvas
        painter.setPen(QColor("#7A746C"))
        painter.setFont(make_font(FONT_FAMILY_MONO, 8))
        painter.drawText(20, 30, "def calculate_quarterly_projection(metrics):")
        painter.drawText(36, 48, "growth = metrics.retention_rate * 1.42")
        painter.drawText(36, 66, "return growth.project(months=12)")
        painter.drawText(20, 86, "# Try clicking and dragging across this code block to select it!")

        # Draw active dragging rectangle
        rect_to_draw = self._current_rect or self._selected_rect
        if rect_to_draw and rect_to_draw.isValid():
            # Highlight fill
            painter.setPen(QPen(QColor(BORDER), 2, Qt.DashLine))
            painter.setBrush(QColor(214, 255, 56, 70))  # Semi-transparent lime
            painter.drawRect(rect_to_draw)

            # Draw crosshair pins at corners
            painter.setPen(QPen(QColor(BORDER), 2))
            painter.setBrush(QColor(BORDER))
            cs = 4
            for pt in [rect_to_draw.topLeft(), rect_to_draw.topRight(), rect_to_draw.bottomLeft(), rect_to_draw.bottomRight()]:
                painter.drawRect(QRect(pt.x() - cs//2, pt.y() - cs//2, cs, cs))

        painter.end()


class TutorialDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("FlowState Interactive Tutorial")
        self.setStyleSheet(build_stylesheet())
        self.resize(680, 580)
        self.setMinimumSize(640, 540)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config
        self.ptt_shortcut = cfg.shortcuts.push_to_talk.upper()
        self.toggle_shortcut = cfg.shortcuts.toggle.upper()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 28, 36, 24)
        outer.setSpacing(14)

        # Top header with step tabs, subtle geometric star motif and badge
        top_row = QHBoxLayout()
        header_text_col = QVBoxLayout()
        header_text_col.setSpacing(2)
        eyebrow_row = QHBoxLayout()
        eyebrow_row.setSpacing(6)
        eyebrow_star = GeometricMotif("star", size=11, color=INK)
        eyebrow = QLabel("INTERACTIVE ONBOARDING // TUTORIAL")
        eyebrow.setProperty("role", "eyebrow")
        eyebrow_row.addWidget(eyebrow_star)
        eyebrow_row.addWidget(eyebrow)
        eyebrow_row.addStretch(1)

        self.step_headline = QLabel("Welcome to the Practice Arena")
        self.step_headline.setProperty("role", "headline")
        header_text_col.addLayout(eyebrow_row)
        header_text_col.addWidget(self.step_headline)
        top_row.addLayout(header_text_col, 1)

        self.step_badge = StickerBadge("✦ STEP 01 / 03", bg_color=INK, text_color="#FFFFFF", is_pill=False)
        top_row.addWidget(self.step_badge)
        outer.addLayout(top_row)

        rule = QFrame()
        rule.setProperty("role", "rule")
        outer.addWidget(rule)

        # Stacked pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_step1_ptt())
        self.stack.addWidget(self._build_step2_toggle())
        self.stack.addWidget(self._build_step3_privacy())
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

        self.next_btn = QPushButton("Next Step →")
        self.next_btn.setProperty("role", "primary")
        self.next_btn.setMinimumWidth(170)
        self.next_btn.clicked.connect(self._go_next)
        nav_row.addWidget(self.next_btn)

        outer.addLayout(nav_row)

        # Hook controller transcription signal to populate Step 1
        self._controller.signals.recording_finished.connect(self._on_speech_transcribed)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())

    # -- Step 1: Push to Talk Practice ---------------------------------
    def _build_step1_ptt(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
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
            "FlowState runs 100% locally on my machine with zero lag and total privacy."
        )
        prompt_text = QLabel(f'"{self.sample_prompt}"')
        prompt_text.setFont(make_font(FONT_FAMILY_DISPLAY, 18))
        prompt_text.setStyleSheet("color: #1A1A1A;")
        prompt_text.setWordWrap(True)
        pc_layout.addWidget(pc_eyebrow)
        pc_layout.addWidget(prompt_text)
        layout.addWidget(prompt_card)

        # Interactive live transcription / paste target box
        box_card = QFrame()
        box_card.setProperty("role", "card")
        bc_layout = QVBoxLayout(box_card)
        bc_layout.setContentsMargins(16, 12, 16, 12)
        bc_layout.setSpacing(6)

        bc_header = QHBoxLayout()
        bc_label = QLabel("LIVE DICTATION RESULT (AUTO-RECEIVES TRANSCRIPTION):")
        bc_label.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        self.step1_success_badge = StickerBadge("SPEECH DETECTED! ✓", bg_color=LIME, text_color="#1A1A1A", is_pill=True)
        self.step1_success_badge.hide()
        bc_header.addWidget(bc_label)
        bc_header.addStretch(1)
        bc_header.addWidget(self.step1_success_badge)
        bc_layout.addLayout(bc_header)

        self.step1_text = QTextEdit()
        self.step1_text.setPlaceholderText("Transcribed text will appear here automatically when you release the hotkey, or you can paste text here...")
        self.step1_text.setFixedHeight(85)
        self.step1_text.textChanged.connect(self._on_step1_text_changed)
        bc_layout.addWidget(self.step1_text)

        layout.addWidget(box_card)
        layout.addStretch(1)
        return page

    def _on_speech_transcribed(self, text: str) -> None:
        if self.stack.currentIndex() == 0 and text:
            self.step1_text.setText(text.strip())

    def _on_step1_text_changed(self) -> None:
        has_text = bool(self.step1_text.toPlainText().strip())
        if has_text:
            self.step1_success_badge.show()
            self.next_btn.setText("Next: Hands-Free && Spatial →")
            self.next_btn.setEnabled(True)

    # -- Step 2: Hands-Free & Spatial Context Selection -----------------
    def _build_step2_toggle(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        desc = QLabel(
            f"<b>Hands-Free Mode:</b> Press <b>{self.toggle_shortcut}</b> once to start continuous recording without holding any keys. "
            "Press it again when you're done speaking to transcribe and format automatically."
        )
        desc.setFont(make_font(FONT_FAMILY, 9.5))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        spatial_desc = QLabel(
            "<b>Spatial Visual Capture:</b> While recording hands-free, you can click and drag across any window or code on screen. "
            "FlowState captures that exact region so the local AI understands what you are pointing at."
        )
        spatial_desc.setFont(make_font(FONT_FAMILY, 9.5))
        spatial_desc.setWordWrap(True)
        layout.addWidget(spatial_desc)

        # Interactive Spatial Demo Canvas
        canvas_card = QFrame()
        canvas_card.setProperty("role", "card")
        cc_layout = QVBoxLayout(canvas_card)
        cc_layout.setContentsMargins(14, 10, 14, 12)
        cc_layout.setSpacing(6)

        cc_header = QHBoxLayout()
        cc_header_lbl = QLabel("PRACTICE SPATIAL HIGHLIGHT (DRAG MOUSE BELOW):")
        cc_header_lbl.setFont(make_font(FONT_FAMILY_MONO, 8, bold=True))
        self.step2_badge = StickerBadge("REGION SELECTED! ✓", bg_color=YELLOW, text_color="#1A1A1A", is_pill=True)
        self.step2_badge.hide()
        cc_header.addWidget(cc_header_lbl)
        cc_header.addStretch(1)
        cc_header.addWidget(self.step2_badge)
        cc_layout.addLayout(cc_header)

        demo_canvas = _SpatialDemoCanvas(on_selected=self._on_spatial_selected)
        cc_layout.addWidget(demo_canvas)
        layout.addWidget(canvas_card)

        layout.addStretch(1)
        return page

    def _on_spatial_selected(self, rect: QRect) -> None:
        self.step2_badge.setText(f"REGION SELECTED ({rect.width()}x{rect.height()}px) ✓")
        self.step2_badge.show()

    # -- Step 3: Shortcuts, Clipboard Copy & Privacy --------------------
    def _build_step3_privacy(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(12)

        # 1. Custom Shortcuts Card
        sc_card = QFrame()
        sc_card.setProperty("role", "card")
        sc_layout = QVBoxLayout(sc_card)
        sc_layout.setContentsMargins(16, 12, 16, 12)
        sc_layout.setSpacing(6)

        sc_header = QHBoxLayout()
        sc_idx = QLabel("[ 01 ]")
        sc_idx.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
        sc_idx.setStyleSheet("color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 2px 5px;")
        sc_idx.setFixedWidth(40)
        sc_idx.setAlignment(Qt.AlignCenter)
        sc_title = QLabel("CLICK-TO-RECORD SHORTCUTS")
        sc_title.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
        sc_header.addWidget(sc_idx)
        sc_header.addWidget(sc_title)
        sc_header.addStretch(1)

        sc_text = QLabel(
            "You never have to type out shortcut names. In Settings, simply click the key chip "
            "and press your desired key or combination to rebind it instantly."
        )
        sc_text.setFont(make_font(FONT_FAMILY, 9.5))
        sc_text.setStyleSheet("color: #5C5751;")
        sc_text.setWordWrap(True)
        sc_layout.addLayout(sc_header)
        sc_layout.addWidget(sc_text)
        layout.addWidget(sc_card)

        # 2. History Clipboard Card
        hist_card = QFrame()
        hist_card.setProperty("role", "card")
        hc_layout = QVBoxLayout(hist_card)
        hc_layout.setContentsMargins(16, 12, 16, 12)
        hc_layout.setSpacing(6)

        hc_header = QHBoxLayout()
        hc_idx = QLabel("[ 02 ]")
        hc_idx.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
        hc_idx.setStyleSheet("color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 2px 5px;")
        hc_idx.setFixedWidth(40)
        hc_idx.setAlignment(Qt.AlignCenter)
        hc_title = QLabel("1-CLICK CLIPBOARD COPY")
        hc_title.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
        hc_header.addWidget(hc_idx)
        hc_header.addWidget(hc_title)
        hc_header.addStretch(1)

        hc_text = QLabel("In History, click [ COPY TEXT ] on any past transcript to copy it back into your clipboard.")
        hc_text.setFont(make_font(FONT_FAMILY, 9.5))
        hc_text.setStyleSheet("color: #5C5751;")
        hc_text.setWordWrap(True)

        sample_row = QHBoxLayout()
        self.sample_copy_btn = QPushButton("COPY TEXT")
        self.sample_copy_btn.setProperty("role", "secondary")
        self.sample_copy_btn.setFixedWidth(130)
        self.sample_copy_btn.clicked.connect(self._test_copy_sample)
        sample_preview = QLabel('"Refactored the authentication token validation flow."')
        sample_preview.setFont(make_font(FONT_FAMILY_DISPLAY, 13))
        sample_preview.setStyleSheet("color: #1A1A1A;")
        sample_row.addWidget(self.sample_copy_btn)
        sample_row.addWidget(sample_preview, 1)

        hc_layout.addLayout(hc_header)
        hc_layout.addWidget(hc_text)
        hc_layout.addLayout(sample_row)
        layout.addWidget(hist_card)

        # 3. Automatic Privacy Purge Notice Card
        purge_card = QFrame()
        purge_card.setProperty("role", "card")
        pc_layout = QVBoxLayout(purge_card)
        pc_layout.setContentsMargins(16, 12, 16, 12)
        pc_layout.setSpacing(6)

        pc_header = QHBoxLayout()
        pc_idx = QLabel("[ 03 ]")
        pc_idx.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
        pc_idx.setStyleSheet("color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 2px 5px;")
        pc_idx.setFixedWidth(40)
        pc_idx.setAlignment(Qt.AlignCenter)
        pc_title = QLabel("AUTOMATIC RESTART PURGE")
        pc_title.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
        pc_badge = StickerBadge("100% PRIVATE", bg_color=LIME, text_color="#1A1A1A", is_pill=True)
        pc_header.addWidget(pc_idx)
        pc_header.addWidget(pc_title)
        pc_header.addStretch(1)
        pc_header.addWidget(pc_badge)
        pc_layout.addLayout(pc_header)

        pc_text = QLabel(
            "Every time FlowState restarts or your computer reboots, all session folders and audio "
            "files are automatically purged so that your history stays clean and never clutters your disk."
        )
        pc_text.setFont(make_font(FONT_FAMILY, 9.5))
        pc_text.setStyleSheet("color: #5C5751;")
        pc_text.setWordWrap(True)
        pc_layout.addWidget(pc_text)
        layout.addWidget(purge_card)

        layout.addStretch(1)
        return page

    def _test_copy_sample(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText("Refactored the authentication token validation flow.")
        self.sample_copy_btn.setText("COPIED! ✓")
        self.sample_copy_btn.setEnabled(False)

    # -- Navigation logic ----------------------------------------------
    def _go_next(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            self.stack.setCurrentIndex(1)
            self.step_badge.setText("✦ STEP 02 / 03")
            self.step_headline.setText("Hands-Free & Spatial Context")
            self.prev_btn.show()
            self.next_btn.setText("Next: Shortcuts && Privacy →")
            self.next_btn.adjustSize()
        elif idx == 1:
            self.stack.setCurrentIndex(2)
            self.step_badge.setText("✦ STEP 03 / 03")
            self.step_headline.setText("Shortcuts, Clipboard & Privacy")
            self.prev_btn.show()
            self.next_btn.setText("Finish && Launch FlowState →")
            self.next_btn.adjustSize()
        elif idx == 2:
            # Mark first run complete!
            paths.first_run_flag_path().write_text("done", encoding="utf-8")
            logger.info("Onboarding tutorial completed. First run flag written.")
            self.accept()

    def _go_prev(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 1:
            self.stack.setCurrentIndex(0)
            self.step_badge.setText("✦ STEP 01 / 03")
            self.step_headline.setText("Welcome to the Practice Arena")
            self.prev_btn.hide()
            self.next_btn.setText("Next: Hands-Free && Spatial →")
            self.next_btn.adjustSize()
        elif idx == 2:
            self.stack.setCurrentIndex(1)
            self.step_badge.setText("✦ STEP 02 / 03")
            self.step_headline.setText("Hands-Free & Spatial Context")
            self.prev_btn.show()
            self.next_btn.setText("Next: Shortcuts && Privacy →")
            self.next_btn.adjustSize()
