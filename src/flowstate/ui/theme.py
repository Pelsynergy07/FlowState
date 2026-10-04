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
    """Shared desktop styling, drawn from the FlowState website's paper/ink identity."""
    arrow_path = (Path(__file__).parent.parent / "resources" / "icons" / "arrow_down.svg").as_posix()
    return f"""
    * {{ font-family: "{FONT_FAMILY}"; color: {INK}; }}
    QDialog, QMainWindow, QWidget#background {{ background: {PAPER}; }}
    QLabel {{ background: transparent; border: none; padding: 0; color: {INK}; font-size: 13px; }}
    QLabel[role="eyebrow"] {{ font-family: "{FONT_FAMILY_MONO}"; color: {MUTED_TEXT}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
    QLabel[role="headline"] {{ font-family: "{FONT_FAMILY_DISPLAY}"; font-size: 42px; font-weight: 400; }}
    QLabel[role="wordmark"] {{ font-family: "{FONT_FAMILY_DISPLAY}"; font-size: 31px; font-style: italic; }}
    QLabel[role="muted"] {{ color: {MUTED_TEXT}; font-size: 13px; }}
    QLabel[role="mono"] {{ font-family: "{FONT_FAMILY_MONO}"; color: {MUTED_TEXT}; font-size: 11px; }}
    QFrame[role="card"] {{ background: {PAPER_RAISED}; border: 1px solid {LINE}; border-radius: 6px; }}
    QFrame[role="rule"] {{ background: {LINE}; border: none; min-height: 1px; max-height: 1px; }}
    QFrame[role="shortcut-panel"] {{ background: {PAPER_ALT}; border: 1px solid {LINE}; border-radius: 6px; }}
    QLabel[role="key-hint"] {{ background: {PAPER_RAISED}; border: 1px solid {INK}; border-bottom: 3px solid {INK}; border-radius: 4px; padding: 5px 12px; font-family: "{FONT_FAMILY_MONO}"; font-size: 15px; font-weight: 700; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QTabWidget::pane {{ border: none; background: transparent; top: 0; }}
    QTabBar::tab {{ background: transparent; font-family: "{FONT_FAMILY_STICKER}"; font-weight: 700; font-size: 12px; padding: 11px 17px; margin-right: 5px; border: 1px solid transparent; border-radius: 4px; }}
    QTabBar::tab:selected {{ background: {LIME}; color: {INK}; border: 1px solid {INK}; border-bottom: 3px solid {INK}; padding-bottom: 9px; }}
    QTabBar::tab:hover:!selected {{ background: {PAPER_ALT}; border-color: {LINE}; }}
    QTabBar::tab:focus {{ border: 2px solid {INK}; }}
    QPushButton {{ background: {PAPER_RAISED}; border: 1px solid {INK}; border-right: 3px solid {INK}; border-bottom: 3px solid {INK}; border-radius: 4px; padding: 9px 18px; font-family: "{FONT_FAMILY_STICKER}"; font-weight: 700; font-size: 12px; }}
    QPushButton:hover {{ background: {PAPER_ALT}; }}
    QPushButton:pressed {{ background: {PAPER_ALT}; border-right: 1px solid {INK}; border-bottom: 1px solid {INK}; padding-left: 20px; padding-top: 11px; }}
    QPushButton:focus {{ border: 2px solid {INK}; }}
    QPushButton[role="primary"], QPushButton[role="accent"] {{ background: {LIME}; color: {INK}; }}
    QPushButton[role="primary"]:hover, QPushButton[role="accent"]:hover {{ background: #C5F02B; }}
    QPushButton[role="secondary"] {{ background: transparent; border: 1px solid {LINE}; }}
    QPushButton[role="secondary"]:hover {{ background: {PAPER_ALT}; border-color: {INK}; }}
    QPushButton[role="secondary"]:focus {{ border: 2px solid {INK}; }}
    QPushButton:disabled, QPushButton[role="primary"]:disabled, QPushButton[role="accent"]:disabled {{ background: {PAPER_ALT}; color: #918B82; border: 1px solid {LINE}; }}
    QLineEdit, QSpinBox, QTextEdit, QPlainTextEdit {{ background: {PAPER_RAISED}; border: 1px solid #B7B0A4; border-radius: 4px; padding: 8px 10px; font-size: 13px; selection-background-color: {LIME}; selection-color: {INK}; }}
    QLineEdit:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {INK}; }}
    QComboBox {{ background: {PAPER_RAISED}; border: 1px solid #B7B0A4; border-bottom: 2px solid #B7B0A4; border-radius: 4px; padding: 5px 12px; padding-right: 38px; font-size: 13px; min-height: 24px; }}
    QComboBox:hover, QComboBox:focus {{ border-color: {INK}; }}
    QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 28px; background: {INK}; border-top-right-radius: 3px; border-bottom-right-radius: 3px; }}
    QComboBox::down-arrow {{ image: url("{arrow_path}"); width: 10px; height: 6px; }}
    QComboBox QAbstractItemView {{ background: {PAPER_RAISED}; color: {INK}; border: 1px solid {INK}; selection-background-color: {LIME}; selection-color: {INK}; padding: 4px; outline: none; }}
    QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 5px 10px; }}
    QCheckBox {{ background: transparent; spacing: 10px; font-size: 13px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {INK}; border-radius: 3px; background: {PAPER_RAISED}; }}
    QCheckBox::indicator:checked {{ background: {LIME}; border: 2px solid {INK}; }}
    QSlider::groove:horizontal {{ height: 4px; background: {LINE}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {INK}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {LIME}; border: 2px solid {INK}; width: 16px; margin: -7px 0; border-radius: 4px; }}
    QSlider::handle:horizontal:focus {{ background: {INK}; }}
    QListWidget {{ background: {PAPER_RAISED}; border: 1px solid {LINE}; border-radius: 4px; padding: 4px; }}
    QListWidget::item {{ padding: 10px; border-bottom: 1px solid {LINE}; }}
    QListWidget::item:selected {{ background: {LIME}; color: {INK}; }}
    QMenu {{ background: {PAPER_RAISED}; border: 1px solid {INK}; border-radius: 4px; padding: 6px; }}
    QMenu::item {{ padding: 9px 26px 9px 12px; font-size: 13px; }}
    QMenu::item:selected {{ background: {LIME}; color: {INK}; }}
    QMenu::item:disabled {{ color: {MUTED_TEXT}; }}
    QMenu::separator {{ height: 1px; background: {LINE}; margin: 5px; }}
    QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #B9B2A6; min-height: 30px; border-radius: 4px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QProgressBar {{ background: {PAPER_ALT}; border: 1px solid {INK}; border-radius: 3px; text-align: center; font-family: "{FONT_FAMILY_MONO}"; font-size: 11px; color: {INK}; }}
    QProgressBar::chunk {{ background: {LIME}; }}
    QToolTip {{ background: {INK}; color: {PAPER_RAISED}; border: none; padding: 6px 9px; }}
    """


def setup_brutalist_combobox(combo) -> None:
    """Use an explicit light popup, independent of the Windows theme."""
    from PySide6.QtWidgets import QListView
    view = QListView(combo)
    view.setStyleSheet(
        f"QListView {{ background: {PAPER_RAISED}; color: {INK}; border: 1px solid {INK}; outline: none; padding: 4px; }} "
        f"QListView::item {{ min-height: 30px; padding: 5px 10px; color: {INK}; background: {PAPER_RAISED}; }} "
        f"QListView::item:hover, QListView::item:selected {{ background: {LIME}; color: {INK}; }}"
    )
    combo.setView(view)
