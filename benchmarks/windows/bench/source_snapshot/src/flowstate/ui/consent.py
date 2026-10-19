"""The one-time question asking existing users about anonymous stats.

New installs answer it on the last setup step; this covers people who
updated from a version that only had the switch in Settings > Stats.
Both answers are equally easy, and nothing is shared unless the user
chooses to.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .theme import FONT_FAMILY_DISPLAY, MUTED_TEXT, build_stylesheet

CONSENT_TEXT = (
    "Share anonymous counts: how many words and dictations, how long processing takes, and whether it "
    "worked. <b>Never</b> your audio, text, screenshots, clipboard, or anything you type. "
    "You can change this anytime in Settings → Stats."
)


class ConsentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.choice: bool | None = None
        self.setWindowTitle("FlowState")
        self.setStyleSheet(build_stylesheet())
        self.setWindowFlags((self.windowFlags() & ~Qt.WindowContextHelpButtonHint) | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 18)
        layout.setSpacing(12)
        title = QLabel("Help improve FlowState?")
        title.setStyleSheet(f"font-family: '{FONT_FAMILY_DISPLAY}'; font-size: 28px;")
        body = QLabel(CONSENT_TEXT)
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setStyleSheet("font-size: 13px;")
        note = QLabel("Only asked once.")
        note.setStyleSheet(f"font-size: 12px; color: {MUTED_TEXT};")
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(note)

        buttons = QHBoxLayout()
        self.share_btn = QPushButton("Share anonymous stats")
        self.decline_btn = QPushButton("Don't share")
        self.share_btn.clicked.connect(lambda: self._answer(True))
        self.decline_btn.clicked.connect(lambda: self._answer(False))
        buttons.addWidget(self.share_btn)
        buttons.addWidget(self.decline_btn)
        layout.addLayout(buttons)

    def _answer(self, share: bool) -> None:
        self.choice = share
        self.accept()


def ask_once(config_store, parent=None) -> None:
    """Show the question if it hasn't been answered; record the answer."""
    from ..usage import analytics_config

    analytics = config_store.config.analytics
    if analytics.asked or not analytics_config()[0]:
        return
    if analytics.enabled:
        # Already opted in from Settings before this question existed.
        analytics.asked = True
        config_store.save()
        return
    dialog = ConsentDialog(parent)
    dialog.exec()
    if dialog.choice is None:
        return  # Closed without answering: ask again next launch.
    analytics.enabled = dialog.choice
    analytics.asked = True
    config_store.save()
