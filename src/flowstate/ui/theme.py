"""FlowState's visual identity, v2: an airy, minimal aesthetic built on
Instrument Serif (display/headline type) and Manrope (everything else),
generous whitespace, hairline borders instead of heavy chrome, and one
consistent corner radius used everywhere so the whole app reads as a
single coherent shape language rather than a patchwork of button styles.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette

# -- Color tokens -----------------------------------------------------------
PAPER = "#FAF9F6"  # warm, airy background
PAPER_RAISED = "#FFFFFF"  # cards/panels on top of PAPER
INK = "#18181B"  # primary text -- soft near-black, not pure black
MUTED_TEXT = "#8B8883"  # secondary text
LINE = "#ECEAE5"  # hairline borders -- barely-there structure
LINE_STRONG = "#DEDBD4"  # slightly firmer rule, for inputs/emphasis
ACCENT = "#5751E0"  # refined indigo, used sparingly (focus, links, wordmark)
ACCENT_SOFT = "#EFEEFC"  # light accent tint for hover/selected backgrounds
DANGER = "#D14D3D"

# -- Typography ---------------------------------------------------------
FONT_FAMILY = "Manrope"  # UI body/controls
FONT_FAMILY_DISPLAY = "Instrument Serif"  # headlines, the FlowState wordmark

# One radius, used on every rectangular surface -- buttons, cards, inputs,
# tabs -- so nothing in the app looks like it came from a different kit.
RADIUS = 14
RADIUS_PILL = 999  # the recording HUD is a true pill, not a "button"


def apply_light_palette(app) -> None:
    """Forces a light QPalette regardless of the Windows theme setting.

    FlowState is a fixed-brand app, not one that reskins itself per OS
    theme -- without this, any widget (or part of a widget, like a
    QDialog's own window chrome) that isn't explicitly covered by the QSS
    stylesheet falls back to Qt's default palette, which follows Windows
    dark mode and looks jarring/inconsistent against the rest of the UI.
    """
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(PAPER))
    palette.setColor(QPalette.WindowText, QColor(INK))
    palette.setColor(QPalette.Base, QColor(PAPER_RAISED))
    palette.setColor(QPalette.AlternateBase, QColor(PAPER))
    palette.setColor(QPalette.Text, QColor(INK))
    palette.setColor(QPalette.Button, QColor(PAPER_RAISED))
    palette.setColor(QPalette.ButtonText, QColor(INK))
    palette.setColor(QPalette.ToolTipBase, QColor(PAPER_RAISED))
    palette.setColor(QPalette.ToolTipText, QColor(INK))
    palette.setColor(QPalette.Highlight, QColor(ACCENT))
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
    }}

    QLabel[role="eyebrow"] {{
        color: {MUTED_TEXT};
        font-family: "{FONT_FAMILY}";
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 2px;
    }}

    QLabel[role="headline"] {{
        color: {INK};
        font-family: "{FONT_FAMILY_DISPLAY}";
        font-size: 32px;
        font-weight: 400;
    }}

    QLabel[role="muted"] {{
        color: {MUTED_TEXT};
        font-size: 13px;
    }}

    QFrame[role="card"] {{
        background-color: {PAPER_RAISED};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
    }}

    QFrame[role="rule"] {{
        background-color: {LINE};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}

    QTabWidget::pane {{
        border: none;
        background: transparent;
        top: 0px;
    }}

    QTabBar::tab {{
        background: transparent;
        color: {MUTED_TEXT};
        font-family: "{FONT_FAMILY}";
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.5px;
        padding: 12px 18px;
        margin-right: 4px;
        border-bottom: 2px solid transparent;
    }}

    QTabBar::tab:selected {{
        color: {ACCENT};
        border-bottom: 2px solid {ACCENT};
    }}

    QPushButton {{
        background-color: {INK};
        color: {PAPER_RAISED};
        border: none;
        border-radius: {RADIUS}px;
        padding: 11px 22px;
        font-weight: 600;
        font-size: 13px;
    }}

    QPushButton:hover {{
        background-color: #000000;
    }}

    QPushButton:disabled {{
        background-color: {LINE_STRONG};
        color: {PAPER_RAISED};
    }}

    QPushButton[role="secondary"] {{
        background-color: transparent;
        color: {INK};
        border: 1px solid {LINE_STRONG};
    }}

    QPushButton[role="secondary"]:hover {{
        background-color: {PAPER};
        border: 1px solid {INK};
    }}

    QPushButton[role="accent"] {{
        background-color: {ACCENT};
    }}

    QPushButton[role="accent"]:hover {{
        background-color: #4A44CC;
    }}

    QComboBox, QLineEdit, QSpinBox {{
        background-color: {PAPER_RAISED};
        border: 1px solid {LINE_STRONG};
        border-radius: {RADIUS}px;
        padding: 9px 12px;
        font-size: 13px;
        selection-background-color: {ACCENT_SOFT};
        selection-color: {INK};
    }}

    QComboBox:hover, QLineEdit:hover {{
        border: 1px solid {ACCENT};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}

    QCheckBox {{
        font-size: 13px;
        spacing: 10px;
    }}

    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border-radius: 5px;
        border: 1px solid {LINE_STRONG};
        background: {PAPER_RAISED};
    }}

    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border: 1px solid {ACCENT};
    }}

    QSlider::groove:horizontal {{
        height: 3px;
        background: {LINE_STRONG};
        border-radius: 1px;
    }}

    QSlider::handle:horizontal {{
        background: {ACCENT};
        width: 15px;
        height: 15px;
        margin: -6px 0;
        border-radius: 7px;
    }}

    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 1px;
    }}

    QListWidget {{
        background: {PAPER_RAISED};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
        font-size: 13px;
        padding: 4px;
    }}

    QListWidget::item {{
        padding: 10px 8px;
        border-bottom: 1px solid {LINE};
    }}

    QListWidget::item:selected {{
        background: {ACCENT_SOFT};
        color: {ACCENT};
        border-radius: 8px;
    }}

    QMenu {{
        background-color: {PAPER_RAISED};
        border: 1px solid {LINE};
        border-radius: {RADIUS}px;
        padding: 6px;
    }}

    QMenu::item {{
        color: {INK};
        padding: 9px 28px 9px 12px;
        border-radius: 8px;
    }}

    QMenu::item:selected {{
        background-color: {ACCENT_SOFT};
        color: {ACCENT};
    }}

    QMenu::item:disabled {{
        color: {MUTED_TEXT};
    }}

    QMenu::separator {{
        height: 1px;
        background: {LINE};
        margin: 6px 8px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
    }}

    QScrollBar::handle:vertical {{
        background: {LINE_STRONG};
        border-radius: 4px;
        min-height: 24px;
    }}
    """
