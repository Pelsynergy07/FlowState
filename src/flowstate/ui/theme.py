"""FlowState Visual Identity: Neo-Brutalist & Tactile Retro-Technical Aesthetic.

Built on:
- Instrument Serif (editorial display/headline type and timer readouts)
- Syne (quirky, expressive neo-brutalist display sans for tabs, buttons, stickers)
- Space Mono (tactical technical metadata stamps, coordinates, and hotkey chips)
- Manrope (clean, non-generic geometric body sans)
- Authentic fibrous creased paper grain texture
- High-contrast 2px ink borders, solid brutalist drop shadows, and sharp geometry
"""

from __future__ import annotations

from pathlib import Path
from PySide6.QtGui import QColor, QPalette, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

# -- Color tokens (Stark Black & White Neo-Brutalist) -----------------------
PAPER = "#FFFFFF"         # Crisp pure white base
PAPER_RAISED = "#FFFFFF"  # Pure white card surface
PAPER_ALT = "#F5F5F5"     # Subtle light grey panel surface
INK = "#000000"           # Pure deep black ink
MUTED_TEXT = "#666666"    # Technical muted grey
LINE = "#E0E0E0"          # Structural dividers
LINE_STRONG = "#000000"   # Bold 2px ink structure
BORDER = "#000000"        # 2px solid black borders
ACCENT = "#000000"        # Stark monochrome accent
ACCENT_SOFT = "#F0F0F0"   # Light grey hover
LIME = "#000000"          # High-contrast indicator
ORANGE = "#000000"        # High-contrast indicator
PINK = "#000000"          # High-contrast indicator
YELLOW = "#F5F5F5"        # High-contrast badge background
DANGER = "#000000"

# -- Typography ---------------------------------------------------------
FONT_FAMILY = "Manrope"                 # Standard UI controls and prose
FONT_FAMILY_DISPLAY = "Instrument Serif" # Headlines, wordmark, timer counter
FONT_FAMILY_STICKER = "Syne"            # Expressive neo-brutalist tabs & stickers
FONT_FAMILY_MONO = "Space Mono"         # Technical stamps and metadata

# Sharp neo-brutalist geometry
RADIUS = 0
RADIUS_HUD = 0

_paper_pixmap: QPixmap | None = None


def get_paper_texture() -> QPixmap | None:
    return None


def paint_paper_background(painter: QPainter, rect, base_color: QColor | str = PAPER, opacity: float = 1.0) -> None:
    """Paints a crisp, clean neo-brutalist stark white background with zero muddy tint."""
    painter.save()
    painter.fillRect(rect, QColor(base_color))
    painter.restore()




def apply_light_palette(app) -> None:
    """Forces the stark monochrome neo-brutalist palette."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(PAPER))
    palette.setColor(QPalette.WindowText, QColor(INK))
    palette.setColor(QPalette.Base, QColor(PAPER_RAISED))
    palette.setColor(QPalette.AlternateBase, QColor(PAPER_ALT))
    palette.setColor(QPalette.Text, QColor(INK))
    palette.setColor(QPalette.Button, QColor(PAPER_RAISED))
    palette.setColor(QPalette.ButtonText, QColor(INK))
    palette.setColor(QPalette.ToolTipBase, QColor(INK))
    palette.setColor(QPalette.ToolTipText, QColor(PAPER_RAISED))
    palette.setColor(QPalette.Highlight, QColor(INK))
    palette.setColor(QPalette.HighlightedText, QColor(PAPER_RAISED))
    palette.setColor(QPalette.PlaceholderText, QColor(MUTED_TEXT))
    app.setPalette(palette)


def build_stylesheet() -> str:
    return f"""
    * {{
        font-family: "{FONT_FAMILY}";
        color: {INK};
    }}

    QWidget#background {{
        background-color: {PAPER};
    }}

    QDialog, QMainWindow {{
        background-color: {PAPER};
    }}

    QLabel {{
        color: {INK};
        background: transparent;
        border: none;
    }}

    QLabel[role="eyebrow"] {{
        color: {MUTED_TEXT};
        font-family: "{FONT_FAMILY_MONO}";
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.5px;
    }}

    QLabel[role="headline"] {{
        color: {INK};
        font-family: "{FONT_FAMILY_DISPLAY}";
        font-size: 36px;
        font-weight: 400;
    }}

    QLabel[role="muted"] {{
        color: {MUTED_TEXT};
        font-size: 13px;
    }}

    QFrame[role="card"] {{
        background-color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-radius: {RADIUS}px;
    }}

    QFrame[role="rule"] {{
        background-color: {LINE};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}

    QTabWidget::pane {{
        border: 2px solid {BORDER};
        background-color: {PAPER_RAISED};
        top: -2px;
    }}

    QTabBar::tab {{
        background: {PAPER_RAISED};
        color: {INK};
        font-family: "{FONT_FAMILY_STICKER}";
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.5px;
        padding: 9px 12px;
        border: 2px solid {BORDER};
        border-bottom: 2px solid {BORDER};
        margin-right: 4px;
    }}

    QTabBar::tab:hover:!selected {{
        background: {PAPER_ALT};
    }}

    QTabBar::tab:selected {{
        background: {INK};
        color: {PAPER_RAISED};
        border-bottom: 2px solid {INK};
    }}

    QPushButton {{
        background-color: {INK};
        color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 10px 20px;
        font-family: "{FONT_FAMILY_STICKER}";
        font-weight: 700;
        font-size: 11.5px;
        letter-spacing: 0.5px;
    }}

    QPushButton:hover {{
        background-color: #262626;
        border-color: {BORDER};
    }}

    QPushButton:disabled {{
        background-color: #E0E0E0;
        color: #999999;
        border-color: #CCCCCC;
    }}

    QPushButton[role="secondary"] {{
        background-color: {PAPER_RAISED};
        color: {INK};
        border: 2px solid {BORDER};
    }}

    QPushButton[role="secondary"]:hover {{
        background-color: {PAPER_ALT};
        border-color: {BORDER};
    }}

    QPushButton[role="accent"] {{
        background-color: {INK};
        color: {PAPER_RAISED};
        border: 2px solid {BORDER};
    }}

    QPushButton[role="accent"]:hover {{
        background-color: #262626;
    }}

    QLineEdit, QSpinBox {{
        background-color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 8px 12px;
        font-size: 13px;
        color: {INK};
        selection-background-color: {INK};
        selection-color: {PAPER_RAISED};
    }}

    QLineEdit:focus, QSpinBox:focus {{
        border: 2px solid {BORDER};
        outline: none;
    }}

    /* QComboBox and Dropdown List View */
    QComboBox {{
        background-color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 8px 12px;
        font-size: 13px;
        color: {INK};
    }}

    QComboBox:hover {{
        border: 2px solid {BORDER};
    }}

    QComboBox::drop-down {{
        border-left: 2px solid {BORDER};
        width: 30px;
        background: {PAPER_ALT};
    }}

    QComboBox QAbstractItemView {{
        background-color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        color: {INK};
        selection-background-color: {INK};
        selection-color: {PAPER_RAISED};
        outline: none;
        padding: 4px;
        font-size: 13px;
    }}

    QComboBox QAbstractItemView::item {{
        min-height: 32px;
        padding: 6px 10px;
        color: {INK};
        border: none;
    }}

    QComboBox QAbstractItemView::item:selected {{
        background-color: {INK};
        color: {PAPER_RAISED};
    }}

    QCheckBox {{
        font-size: 13px;
        color: {INK};
        spacing: 10px;
        background: transparent;
        border: none;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 0px;
        border: 2px solid {BORDER};
        background: {PAPER_RAISED};
    }}

    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border: 2px solid {BORDER};
    }}

    QSlider::groove:horizontal {{
        height: 6px;
        background: {PAPER_ALT};
        border: 1.5px solid {BORDER};
        border-radius: 0px;
    }}

    QSlider::handle:horizontal {{
        background: {INK};
        border: 2px solid {BORDER};
        width: 18px;
        height: 18px;
        margin: -7px 0;
        border-radius: 0px;
    }}

    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border: 1.5px solid {BORDER};
    }}

    QListWidget {{
        background: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-radius: {RADIUS}px;
        font-size: 13px;
        padding: 4px;
        color: {INK};
    }}

    QListWidget::item {{
        padding: 10px 10px;
        border-bottom: 1px solid {LINE};
        color: {INK};
    }}

    QListWidget::item:selected {{
        background: {ACCENT};
        color: {PAPER_RAISED};
    }}

    QMenu {{
        background-color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 6px;
    }}

    QMenu::item {{
        color: {INK};
        padding: 8px 24px 8px 12px;
        font-family: "{FONT_FAMILY}";
        font-size: 13px;
    }}

    QMenu::item:selected {{
        background-color: {ACCENT};
        color: {PAPER_RAISED};
    }}

    QMenu::item:disabled {{
        color: {MUTED_TEXT};
    }}

    QMenu::separator {{
        height: 2px;
        background: {BORDER};
        margin: 6px 4px;
    }}

    QScrollBar:vertical {{
        background: {PAPER_ALT};
        width: 10px;
        border-left: 1px solid {BORDER};
    }}

    QScrollBar::handle:vertical {{
        background: {INK};
        min-height: 24px;
        border-radius: 0px;
    }}

    QProgressBar {{
        background-color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-radius: 0px;
        text-align: center;
        font-family: "{FONT_FAMILY_MONO}";
        font-size: 11px;
        font-weight: bold;
        color: {INK};
    }}

    QProgressBar::chunk {{
        background-color: {ACCENT};
    }}
    """
