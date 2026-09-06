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

# -- Color tokens (Warm Vintage Cream & Deep Ink Neo-Brutalist) -------------
PAPER = "#F6F2EC"         # Warm vintage newsprint cream canvas
PAPER_RAISED = "#FFFFFF"  # Clean white card surface
PAPER_ALT = "#EFE8DC"     # Tactile paper / button press tone
INK = "#1A1A1A"           # Deep charcoal black ink
MUTED_TEXT = "#5C5751"    # Warm technical grey
LINE = "#D8D2C6"          # Warm structural dividers
LINE_STRONG = "#1A1A1A"   # Bold 2.5px ink structure
BORDER = "#1A1A1A"        # Bold 2.5px solid black borders
ACCENT = "#1A1A1A"        # Deep black accent
ACCENT_SOFT = "#EFE8DC"   # Warm hover surface
LIME = "#D6FF38"          # High-contrast lime badge
ORANGE = "#FF6B35"        # High-contrast indicator
PINK = "#FF3366"          # High-contrast indicator
YELLOW = "#FFE500"        # Warm brutalist yellow
DANGER = "#D32F2F"

# -- Typography ---------------------------------------------------------
FONT_FAMILY = "Manrope"                 # Standard UI controls and prose
FONT_FAMILY_DISPLAY = "Instrument Serif" # Headlines, wordmark, timer counter
FONT_FAMILY_STICKER = "Syne"            # Expressive neo-brutalist tabs & stickers
FONT_FAMILY_MONO = "Space Mono"         # Technical stamps and metadata

# Tactile neo-brutalist geometry
RADIUS = 6
RADIUS_HUD = 8

_paper_pixmap: QPixmap | None = None


def get_paper_texture() -> QPixmap | None:
    return None


def paint_paper_background(painter: QPainter, rect, base_color: QColor | str = PAPER, opacity: float = 1.0) -> None:
    """Paints a crisp, warm neo-brutalist vintage cream paper background."""
    painter.save()
    painter.fillRect(rect, QColor(base_color))
    painter.restore()




def apply_light_palette(app) -> None:
    """Forces the warm vintage cream neo-brutalist palette."""
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
    arrow_path = (Path(__file__).parent.parent / "resources" / "icons" / "arrow_down.svg").as_posix()

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
        font-size: 10.5px;
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
        line-height: 1.4;
    }}

    QFrame[role="card"] {{
        background-color: {PAPER_RAISED};
        border: 2.5px solid {BORDER};
        border-right: 4px solid {BORDER};
        border-bottom: 4px solid {BORDER};
        border-radius: {RADIUS}px;
    }}

    QFrame[role="rule"] {{
        background-color: {LINE};
        max-height: 1.5px;
        min-height: 1.5px;
        border: none;
    }}

    QTabWidget::pane {{
        border: 2.5px solid {BORDER};
        border-right: 4px solid {BORDER};
        border-bottom: 4px solid {BORDER};
        border-radius: {RADIUS}px;
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
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 4px;
    }}

    QTabBar::tab:hover:!selected {{
        background: {PAPER_ALT};
    }}

    QTabBar::tab:selected {{
        background: {INK};
        color: #FFFFFF;
        border-bottom: 2px solid {INK};
    }}

    /* Faux 3D Neo-Brutalist Buttons */
    QPushButton {{
        background-color: #FFFFFF;
        color: {INK};
        border: 2.5px solid {BORDER};
        border-right: 4px solid {BORDER};
        border-bottom: 4px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 9px 20px;
        font-family: "{FONT_FAMILY_STICKER}";
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 0.5px;
    }}

    QPushButton:hover {{
        background-color: #FAF6EF;
        border-right: 4.5px solid {BORDER};
        border-bottom: 4.5px solid {BORDER};
    }}

    QPushButton:pressed {{
        background-color: {PAPER_ALT};
        margin-top: 2px;
        margin-left: 2px;
        border-right: 2px solid {BORDER};
        border-bottom: 2px solid {BORDER};
    }}

    QPushButton:disabled {{
        background-color: #E6E1D8;
        color: #9C968D;
        border: 2px solid #C4BEB4;
        border-right: 2px solid #C4BEB4;
        border-bottom: 2px solid #C4BEB4;
    }}

    QPushButton[role="secondary"] {{
        background-color: #FFFFFF;
        color: {INK};
        border: 2px solid {BORDER};
        border-right: 3.5px solid {BORDER};
        border-bottom: 3.5px solid {BORDER};
    }}

    QPushButton[role="secondary"]:hover {{
        background-color: #FAF6EF;
    }}

    QPushButton[role="secondary"]:pressed {{
        background-color: {PAPER_ALT};
        margin-top: 2px;
        margin-left: 2px;
        border-right: 2px solid {BORDER};
        border-bottom: 2px solid {BORDER};
    }}

    QPushButton[role="accent"], QPushButton[role="primary"] {{
        background-color: {INK};
        color: #FFFFFF;
        border: 2.5px solid {BORDER};
        border-right: 4px solid #000000;
        border-bottom: 4px solid #000000;
    }}

    QPushButton[role="accent"]:hover, QPushButton[role="primary"]:hover {{
        background-color: #2D2D2D;
    }}

    QPushButton[role="accent"]:pressed, QPushButton[role="primary"]:pressed {{
        background-color: #000000;
        margin-top: 2px;
        margin-left: 2px;
        border-right: 2px solid #000000;
        border-bottom: 2px solid #000000;
    }}

    QLineEdit, QSpinBox, QTextEdit, QPlainTextEdit {{
        background-color: {PAPER_RAISED};
        border: 2px solid {BORDER};
        border-right: 3px solid {BORDER};
        border-bottom: 3px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 8px 12px;
        font-size: 13px;
        color: {INK};
        selection-background-color: {INK};
        selection-color: {PAPER_RAISED};
    }}

    QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 2.5px solid {BORDER};
        border-right: 3.5px solid {BORDER};
        border-bottom: 3.5px solid {BORDER};
        outline: none;
    }}

    /* QComboBox and Dropdown List View (Image 4 reference style) */
    QComboBox {{
        background-color: {PAPER_RAISED};
        border: 2.5px solid {BORDER};
        border-right: 3.5px solid {BORDER};
        border-bottom: 3.5px solid {BORDER};
        border-radius: {RADIUS}px;
        padding: 8px 12px;
        padding-right: 36px;
        font-size: 13px;
        font-weight: 600;
        color: {INK};
    }}

    QComboBox:hover {{
        background-color: #FAF6EF;
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 28px;
        background-color: {INK};
        border-left: 2.5px solid {BORDER};
        border-top-right-radius: 4px;
        border-bottom-right-radius: 4px;
    }}

    QComboBox::down-arrow {{
        image: url("{arrow_path}");
        width: 10px;
        height: 6px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {PAPER_RAISED};
        border: 2.5px solid {BORDER};
        border-right: 4px solid {BORDER};
        border-bottom: 4px solid {BORDER};
        color: {INK};
        selection-background-color: {INK};
        selection-color: #FFFFFF;
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
