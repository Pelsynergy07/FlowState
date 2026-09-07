"""Settings window: General, Shortcuts, Model, Cleanup, Capture, History.

Neo-brutalist & tactile aesthetic: stark black and white palette,
instrumental typography, Space Mono stamps, 2px solid borders,
interactive key recording, and 1-click clipboard copying for history.
"""

from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, paths
from ..audio.devices import list_input_devices
from ..config import ConfigStore
from ..hotkeys.manager import bindings_conflict
from ..session.store import list_sessions, purge_all_sessions
from ..ui.update_notifier import UpdateNotifierSignals, check_for_update_async
from ..update_check import UpdateInfo
from .autostart import set_launch_at_login
from .fonts import make_font
from .key_recorder import KeyRecorderWidget
from .theme import FONT_FAMILY, FONT_FAMILY_MONO, LIME, build_stylesheet, paint_paper_background, setup_brutalist_combobox
from .widgets import BrutalistCheckBox, StickerBadge


def _eyebrow(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setProperty("role", "eyebrow")
    return label


def _headline(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "headline")
    return label


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    label.setWordWrap(True)
    return label


def _rule() -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "rule")
    frame.setFrameShape(QFrame.NoFrame)
    return frame


def _card(*widgets: QWidget) -> QFrame:
    frame = QFrame()
    frame.setProperty("role", "card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 14, 20, 14)
    layout.setSpacing(8)
    for w in widgets:
        layout.addWidget(w)
    return frame


def _open_path(path: Path) -> None:
    os.startfile(str(path))


class SettingsWindow(QDialog):
    def __init__(
        self,
        config_store: ConfigStore,
        on_applied: Callable[[], None] | None = None,
        controller=None,
        on_update_requested: Callable[[UpdateInfo], None] | None = None,
        update_info: UpdateInfo | None = None,
    ):
        super().__init__(None, Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        self.config_store = config_store
        self._on_applied = on_applied
        self._controller = controller
        self._on_update_requested = on_update_requested
        self._update_info = update_info
        self.setWindowTitle("FlowState Settings")
        self.setStyleSheet(build_stylesheet())
        self.resize(780, 680)
        self.setMinimumSize(740, 600)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 26, 30, 22)
        outer.setSpacing(14)

        # Header with metadata version tag and dynamic update action
        header_row = QHBoxLayout()

        header_title_col = QVBoxLayout()
        header_title_col.setSpacing(4)
        header_title_col.addWidget(_eyebrow("SYS.01 // FLOWSTATE CONFIGURATION"))
        header_title_col.addWidget(_headline("Settings"))
        header_row.addLayout(header_title_col, 1)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        badge_row.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._version_badge = StickerBadge(f"v{__version__} // WIN64", bg_color=LIME, text_color="#121212", is_pill=False)
        badge_row.addWidget(self._version_badge)

        self._header_download_btn = QPushButton("DOWNLOAD UPDATE →")
        self._header_download_btn.setCursor(Qt.PointingHandCursor)
        self._header_download_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #000000;
                color: #FFFFFF;
                border: 2px solid #000000;
                border-radius: 0px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10px;
                font-weight: 900;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: #D8FF3E;
                color: #000000;
            }}
            """
        )
        self._header_download_btn.clicked.connect(self._trigger_update_install)
        self._header_download_btn.hide()
        badge_row.addWidget(self._header_download_btn)

        header_row.addLayout(badge_row)

        outer.addLayout(header_row)
        outer.addWidget(_rule())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "GENERAL")
        self.tabs.addTab(self._build_shortcuts_tab(), "SHORTCUTS")
        self.tabs.addTab(self._build_model_tab(), "MODEL")
        self.tabs.addTab(self._build_cleanup_tab(), "CLEANUP")
        self.tabs.addTab(self._build_capture_tab(), "CAPTURE")
        self.tabs.addTab(self._build_history_tab(), "HISTORY")
        self.tabs.addTab(self._build_about_tab(), "ABOUT")
        outer.addWidget(self.tabs, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("role", "secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self._save)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        outer.addLayout(button_row)

    def _restart_app(self) -> None:
        from .restart import restart_flowstate
        self.accept()
        restart_flowstate()

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())

    def bring_to_front(self) -> None:
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()
        try:
            import ctypes
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            else:
                user32.ShowWindow(hwnd, 5)  # SW_SHOW

            # Force window to top via HWND_TOPMOST toggle
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

            fore_hwnd = user32.GetForegroundWindow()
            fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, None)
            app_thread = kernel32.GetCurrentThreadId()
            if fore_thread != app_thread:
                user32.AttachThreadInput(fore_thread, app_thread, True)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.AttachThreadInput(fore_thread, app_thread, False)
            else:
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    # -- General --------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        cfg = self.config_store.config.general
        self._initial_mic = cfg.microphone_device
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        self.mic_combo = QComboBox()
        self.mic_combo.setFixedHeight(36)
        setup_brutalist_combobox(self.mic_combo)
        self.mic_combo.addItem("System default", None)
        for d in list_input_devices():
            self.mic_combo.addItem(d.name, d.name)
        idx = self.mic_combo.findData(cfg.microphone_device)
        self.mic_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_selected)

        mic_meta_widget = QWidget()
        mic_meta_row = QHBoxLayout(mic_meta_widget)
        mic_meta_row.setContentsMargins(0, 0, 0, 0)
        mic_meta_row.setSpacing(8)
        self.mic_status_lbl = QLabel("✓ Live audio stream connected")
        self.mic_status_lbl.setProperty("role", "mono")
        self.mic_status_lbl.setStyleSheet("color: #1a7f37; font-weight: 700; font-size: 11px;")
        mic_meta_row.addWidget(self.mic_status_lbl, 1)

        self._mic_restart_btn = QPushButton("↺ RESTART TO RESET AUDIO")
        self._mic_restart_btn.setProperty("role", "secondary")
        self._mic_restart_btn.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 800; padding: 4px 10px;")
        self._mic_restart_btn.clicked.connect(self._restart_app)
        self._mic_restart_btn.hide()
        mic_meta_row.addWidget(self._mic_restart_btn)

        layout.addWidget(_card(_eyebrow("01 / Microphone"), self.mic_combo, mic_meta_widget))

        self.launch_at_login = BrutalistCheckBox("Launch FlowState automatically when Windows starts", checked=cfg.launch_at_login)
        self.sound_cues = BrutalistCheckBox("Play acoustic sound cue when recording starts/stops", checked=cfg.sound_cues)
        layout.addWidget(_card(_eyebrow("02 / Behavior"), self.launch_at_login, self.sound_cues))

        layout.addStretch(1)
        return page

    def _on_mic_selected(self) -> None:
        new_mic = self.mic_combo.currentData()
        self.config_store.config.general.microphone_device = new_mic
        self.config_store.save()
        if self._controller and hasattr(self._controller, "switch_microphone"):
            self._controller.switch_microphone(new_mic)
        elif self._on_applied:
            self._on_applied()
        if new_mic != self._initial_mic:
            self._mic_restart_btn.show()
            self.mic_status_lbl.setText("● Audio source changed. Restart to reset device stream.")
            self.mic_status_lbl.setStyleSheet("color: #b05a00; font-weight: 700; font-size: 11px;")
        else:
            self._mic_restart_btn.hide()
            self.mic_status_lbl.setText("✓ Live audio stream connected")
            self.mic_status_lbl.setStyleSheet("color: #1a7f37; font-weight: 700; font-size: 11px;")


    # -- Shortcuts --------------------------------------------------------
    def _build_shortcuts_tab(self) -> QWidget:
        cfg = self.config_store.config.shortcuts
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.addWidget(
            _muted("Click any box or press RECORD, then tap your keyboard shortcut.")
        )
        header_row.addStretch(1)
        reset_btn = QPushButton("↺ Reset to Defaults")
        reset_btn.setProperty("role", "secondary")
        reset_btn.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 800; padding: 4px 10px;")
        reset_btn.clicked.connect(self._reset_shortcuts)
        header_row.addWidget(reset_btn)
        layout.addLayout(header_row)

        self.toggle_edit = KeyRecorderWidget(cfg.toggle)
        layout.addWidget(
            _card(
                _eyebrow("03 / Toggle Shortcut (Hands-Free)"),
                self.toggle_edit,
                _muted("Press once to start dictation, press again to stop and paste transcription."),
            )
        )

        self.ptt_edit = KeyRecorderWidget(cfg.push_to_talk)
        layout.addWidget(
            _card(
                _eyebrow("04 / Push-to-Talk Shortcut"),
                self.ptt_edit,
                _muted("Hold while speaking. Release key to transcribe and paste immediately."),
            )
        )

        layout.addStretch(1)
        return page

    def _reset_shortcuts(self) -> None:
        from ..hotkeys.manager import DEFAULT_PUSH_TO_TALK, DEFAULT_TOGGLE

        self.toggle_edit.setText(DEFAULT_TOGGLE)
        self.ptt_edit.setText(DEFAULT_PUSH_TO_TALK)

    # -- Model --------------------------------------------------------
    def _build_model_tab(self) -> QWidget:
        cfg = self.config_store.config.model
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        self.device_combo = QComboBox()
        self.device_combo.setFixedHeight(36)
        setup_brutalist_combobox(self.device_combo)
        self.device_combo.addItems(["auto", "cuda", "cpu"])
        self.device_combo.setCurrentText(cfg.compute_device)
        layout.addWidget(
            _card(
                _eyebrow("05 / Compute Device"),
                self.device_combo,
                _muted("Auto uses your GPU when available and falls back to CPU automatically."),
                self._build_device_status_label(),
            )
        )

        layout.addStretch(1)
        return page

    def _build_device_status_label(self) -> QLabel:
        label = QLabel()
        label.setProperty("role", "muted")
        label.setWordWrap(True)
        asr = getattr(self._controller, "_asr", None)
        active_device = getattr(asr, "active_device", None) if asr else None
        active_model = getattr(asr, "active_model_id", None) if asr else None
        if active_device == "cuda":
            label.setText(f"Currently running on: your GPU (CUDA, {active_model}) -- fast transcription.")
        elif active_device == "cpu":
            label.setText(
                f"Currently running on: CPU ({active_model}) -- no compatible NVIDIA GPU/CUDA was "
                "detected, so FlowState fell back to a smaller, CPU-friendly model. Transcription "
                "still works, just noticeably slower than on a GPU."
            )
        else:
            label.setText("Compute device not determined yet -- it's decided the first time you record.")
        return label

    # -- Cleanup --------------------------------------------------------
    def _build_cleanup_tab(self) -> QWidget:
        cfg = self.config_store.config.cleanup
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        self.vocab_check = BrutalistCheckBox(
            "Vocabulary correction (fixes domain terms, acronyms, and product names)",
            checked=cfg.vocabulary_enabled,
        )
        self.grammar_check = BrutalistCheckBox(
            "Grammar & punctuation polish (removes verbal fillers and stammers)",
            checked=cfg.grammar_enabled,
        )
        layout.addWidget(_card(_eyebrow("06 / Transcript Polish"), self.vocab_check, self.grammar_check))

        layout.addStretch(1)
        return page

    # -- Capture --------------------------------------------------------
    def _build_capture_tab(self) -> QWidget:
        cfg = self.config_store.config.capture
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        self.capture_mode = QComboBox()
        self.capture_mode.setFixedHeight(36)
        setup_brutalist_combobox(self.capture_mode)
        self.capture_mode.addItem("Hold Ctrl and drag", "drag")
        self.capture_mode.addItem("Click to draw circle", "circle")
        self.capture_mode.addItem("Off", "off")
        idx = self.capture_mode.findData(cfg.mode)
        self.capture_mode.setCurrentIndex(idx if idx >= 0 else 0)
        layout.addWidget(_card(
            _eyebrow("07 / Visual Context Highlighting"),
            self.capture_mode,
            _muted("Capture screen context alongside audio to clarify code, ambiguous references, and diagrams."),
        ))

        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(0, 100)
        self.sensitivity_slider.setValue(int(cfg.sensitivity * 100))
        self.sensitivity_label = QLabel(f"Sensitivity: {cfg.sensitivity:.2f}")
        self.sensitivity_label.setProperty("role", "mono")
        self.sensitivity_slider.valueChanged.connect(
            lambda v: self.sensitivity_label.setText(f"Sensitivity: {v / 100.0:.2f}")
        )
        layout.addWidget(_card(_eyebrow("Motion Sensitivity Threshold"), self.sensitivity_slider, self.sensitivity_label))

        layout.addStretch(1)
        return page

    # -- History --------------------------------------------------------
    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 20, 26, 20)
        layout.setSpacing(12)

        # Header action bar
        top_bar = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        header_text.addWidget(_eyebrow("08 / Session History & Clipboard"))

        # Brutalist callout chips
        chip_row = QHBoxLayout()
        chip_row.setSpacing(8)
        chip_purge = StickerBadge("✦ AUTO-PURGED ON RESTART", bg_color="#FFFFFF", text_color="#000000", is_pill=False)
        chip_copy = StickerBadge("1-CLICK CLIPBOARD COPY", bg_color="#000000", text_color="#FFFFFF", is_pill=False)
        chip_row.addWidget(chip_purge)
        chip_row.addWidget(chip_copy)
        chip_row.addStretch(1)
        header_text.addLayout(chip_row)

        top_bar.addLayout(header_text, 1)

        purge_btn = QPushButton("PURGE ALL")
        purge_btn.setProperty("role", "secondary")
        purge_btn.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 900; padding: 6px 12px;"
        )
        purge_btn.clicked.connect(self._purge_history)
        top_bar.addWidget(purge_btn)

        open_folder_btn = QPushButton("OPEN FOLDER")
        open_folder_btn.setProperty("role", "secondary")
        open_folder_btn.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 900; padding: 6px 12px;"
        )
        open_folder_btn.clicked.connect(lambda: _open_path(paths.sessions_dir()))
        top_bar.addWidget(open_folder_btn)

        layout.addLayout(top_bar)

        # Scrollable session cards area
        self._history_scroll = QScrollArea()
        self._history_scroll.setWidgetResizable(True)
        self._history_scroll.setFrameShape(QFrame.NoFrame)
        self._history_scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: 2px solid #000000;
                border-radius: 0px;
            }
            """
        )

        self._history_content = QWidget()
        self._history_layout = QVBoxLayout(self._history_content)
        self._history_layout.setContentsMargins(12, 12, 12, 12)
        self._history_layout.setSpacing(12)

        self._history_scroll.setWidget(self._history_content)
        layout.addWidget(self._history_scroll, 1)

        self._refresh_history_list()
        return page

    def _purge_history(self) -> None:
        deleted = purge_all_sessions()
        self._refresh_history_list()
        QMessageBox.information(self, "FlowState History", f"Purged {len(deleted)} session(s) from history.")

    def _refresh_history_list(self) -> None:
        # Clear existing cards
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        sessions = list_sessions()[:30]
        if not sessions:
            empty_card = QFrame()
            empty_card.setStyleSheet(
                """
                QFrame {
                    background-color: #FFFFFF;
                    border: 2px dashed #000000;
                    border-radius: 0px;
                    padding: 30px;
                }
                """
            )
            empty_layout = QVBoxLayout(empty_card)
            empty_layout.setAlignment(Qt.AlignCenter)
            empty_title = QLabel("[ NO ACTIVE SESSIONS IN CURRENT RUN ]")
            empty_title.setStyleSheet(
                f"font-family: {FONT_FAMILY_MONO}; font-size: 13px; font-weight: 900; color: #000000;"
            )
            empty_subtitle = QLabel("Transcriptions recorded during this run will appear here with 1-click copy.")
            empty_subtitle.setStyleSheet(
                "font-size: 11px; color: #666666; margin-top: 4px;"
            )
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_subtitle)
            self._history_layout.addWidget(empty_card)
            self._history_layout.addStretch(1)
            return

        for folder in sessions:
            transcript_path = folder / "transcript.txt"
            transcript = transcript_path.read_text(encoding="utf-8").strip() if transcript_path.exists() else ""
            if not transcript:
                transcript = "(No transcription recorded)"

            card = QFrame()
            card.setStyleSheet(
                """
                QFrame {
                    background-color: #FFFFFF;
                    border: 2px solid #000000;
                    border-radius: 0px;
                }
                """
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(8)

            # Card Header
            card_head = QHBoxLayout()
            date_str = folder.name
            try:
                date_part, time_part, _ = folder.name.split("-", 2)
                date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:]}  {time_part[:2]}:{time_part[2:4]}:{time_part[4:]}"
            except Exception:
                pass

            stamp = QLabel(f"REC // {date_str}")
            stamp.setStyleSheet(
                f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 900; color: #000000;"
            )
            card_head.addWidget(stamp, 1)

            card_layout.addLayout(card_head)

            # Transcript Box
            text_preview = QPlainTextEdit(transcript)
            text_preview.setReadOnly(True)
            text_preview.setStyleSheet(
                f"""
                QPlainTextEdit {{
                    background-color: #FAFAFA;
                    color: #000000;
                    border: 1px solid #CCCCCC;
                    border-radius: 0px;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 11px;
                    padding: 8px;
                }}
                """
            )
            # Estimate height based on line count
            line_count = min(max(2, len(transcript.splitlines()) + (len(transcript) // 70)), 6)
            text_preview.setFixedHeight(line_count * 20 + 20)
            card_layout.addWidget(text_preview)

            # Bottom action row
            action_row = QHBoxLayout()
            word_count = len(transcript.split())
            count_lbl = QLabel(f"{word_count} WORDS // {len(transcript)} CHARACTERS")
            count_lbl.setStyleSheet(
                f"font-family: {FONT_FAMILY_MONO}; font-size: 9px; font-weight: 700; color: #777777;"
            )
            action_row.addWidget(count_lbl, 1)

            copy_btn = QPushButton("COPY TEXT")
            copy_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: #000000;
                    color: #FFFFFF;
                    border: 2px solid #000000;
                    border-radius: 0px;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 10px;
                    font-weight: 900;
                    padding: 6px 14px;
                }}
                QPushButton:hover {{
                    background-color: #222222;
                }}
                """
            )

            def _make_copy_handler(btn: QPushButton, text: str):
                def _do_copy():
                    clipboard = QApplication.clipboard()
                    if clipboard:
                        clipboard.setText(text)
                    btn.setText("COPIED!")
                    btn.setStyleSheet(
                        f"""
                        QPushButton {{
                            background-color: #FFFFFF;
                            color: #000000;
                            border: 2px solid #000000;
                            border-radius: 0px;
                            font-family: {FONT_FAMILY_MONO};
                            font-size: 10px;
                            font-weight: 900;
                            padding: 6px 14px;
                        }}
                        """
                    )
                    QTimer.singleShot(1500, lambda: _reset_btn(btn))

                def _reset_btn(b: QPushButton):
                    b.setText("COPY TEXT")
                    b.setStyleSheet(
                        f"""
                        QPushButton {{
                            background-color: #000000;
                            color: #FFFFFF;
                            border: 2px solid #000000;
                            border-radius: 0px;
                            font-family: {FONT_FAMILY_MONO};
                            font-size: 10px;
                            font-weight: 900;
                            padding: 6px 14px;
                        }}
                        QPushButton:hover {{
                            background-color: #222222;
                        }}
                        """
                    )

                return _do_copy

            copy_btn.clicked.connect(_make_copy_handler(copy_btn, transcript))
            action_row.addWidget(copy_btn)

            card_layout.addLayout(action_row)

            self._history_layout.addWidget(card)

        self._history_layout.addStretch(1)

    # -- About --------------------------------------------------------
    def _build_about_tab(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        # 1. System Capabilities & Overview Card (Clean 2x2 grid without bulky subtext)
        about_card = QFrame()
        about_card.setProperty("role", "card")
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(18, 12, 18, 12)
        about_layout.setSpacing(8)

        about_layout.addWidget(_eyebrow("09 / SYSTEM OVERVIEW & CORE CAPABILITIES"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        def _make_about_chip(icon: str, title: str) -> QWidget:
            chip = QWidget()
            row = QHBoxLayout(chip)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            icon_badge = QLabel(icon)
            icon_badge.setFixedSize(24, 24)
            icon_badge.setAlignment(Qt.AlignCenter)
            icon_badge.setStyleSheet(
                "background-color: #FAF6EF; border: 1.5px solid #000000; "
                "border-right: 2.5px solid #000000; border-bottom: 2.5px solid #000000; "
                "border-radius: 3px; font-size: 12px;"
            )
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 800; color: #000000;")
            row.addWidget(icon_badge)
            row.addWidget(t_lbl, 1)
            return chip

        grid.addWidget(_make_about_chip("⚡", "REAL-TIME OFFLINE SPEECH ENGINE"), 0, 0)
        grid.addWidget(_make_about_chip("🧠", "LOCAL AI THOUGHT STRUCTURING"), 0, 1)
        grid.addWidget(_make_about_chip("🎯", "VISUAL CONTEXT GROUNDING"), 1, 0)
        grid.addWidget(_make_about_chip("🔒", "100% PRIVATE & ZERO TELEMETRY"), 1, 1)
        about_layout.addLayout(grid)
        layout.addWidget(about_card)

        # 2. Developer Profile Card
        dev_card = QFrame()
        dev_card.setProperty("role", "card")
        dev_card_layout = QVBoxLayout(dev_card)
        dev_card_layout.setContentsMargins(18, 12, 18, 12)
        dev_card_layout.setSpacing(8)

        dev_card_layout.addWidget(_eyebrow("10 / CREATOR & COMMUNITY"))

        author_name = QLabel("Developed with ❤️ by Pelsynergy")
        author_name.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 14px; font-weight: 900; color: #000000;")
        dev_card_layout.addWidget(author_name)

        # Social & portfolio link buttons
        links_row = QHBoxLayout()
        links_row.setSpacing(8)

        def _make_link_btn(text: str, url: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setProperty("role", "secondary")
            btn.setStyleSheet(
                f"font-family: {FONT_FAMILY_MONO}; font-size: 9px; font-weight: 900; padding: 5px 12px;"
            )
            btn.clicked.connect(lambda: webbrowser.open(url))
            return btn

        links_row.addWidget(_make_link_btn("🌐 PORTFOLIO", "https://pelsynergy.framer.website/"))
        links_row.addWidget(_make_link_btn("💼 LINKEDIN", "https://www.linkedin.com/in/pranav-kumar-95708723b/"))
        links_row.addWidget(_make_link_btn("🐙 GITHUB", "https://github.com/Pelsynergy07/FlowState"))
        links_row.addStretch(1)
        dev_card_layout.addLayout(links_row)

        layout.addWidget(dev_card)

        # 3. Release & Updates Card
        update_card = QFrame()
        update_card.setProperty("role", "card")
        update_card_layout = QVBoxLayout(update_card)
        update_card_layout.setContentsMargins(18, 12, 18, 12)
        update_card_layout.setSpacing(8)

        update_card_layout.addWidget(_eyebrow("11 / SYSTEM VERSION & LIVE UPDATES"))

        ver_row = QHBoxLayout()
        ver_lbl = QLabel(f"FlowState v{__version__} // Windows Native x64")
        ver_lbl.setStyleSheet(f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; font-weight: 800; color: #000000;")
        ver_row.addWidget(ver_lbl, 1)

        self._check_update_btn = QPushButton("CHECK FOR UPDATES")
        self._check_update_btn.setProperty("role", "secondary")
        self._check_update_btn.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 900; padding: 5px 12px;"
        )
        self._check_update_btn.clicked.connect(self._manual_check_updates)
        ver_row.addWidget(self._check_update_btn)
        update_card_layout.addLayout(ver_row)

        # Status text & Install button container
        self._update_status_lbl = QLabel("Ready to check for updates.")
        self._update_status_lbl.setProperty("role", "muted")
        update_card_layout.addWidget(self._update_status_lbl)

        self._update_action_box = QFrame()
        self._update_action_box.setStyleSheet(
            """
            QFrame {
                background-color: #000000;
                border: 2px solid #000000;
            }
            QLabel {
                color: #FFFFFF;
                background-color: transparent;
            }
            """
        )
        act_layout = QHBoxLayout(self._update_action_box)
        act_layout.setContentsMargins(16, 12, 16, 12)
        act_layout.setSpacing(12)

        self._update_banner_lbl = QLabel("NEW VERSION AVAILABLE!")
        self._update_banner_lbl.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; font-weight: 900; color: #FFFFFF; background-color: transparent;"
        )
        act_layout.addWidget(self._update_banner_lbl, 1)

        self._update_now_btn = QPushButton("INSTALL UPDATE NOW →")
        self._update_now_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: #000000;
                border: 2px solid #000000;
                border-radius: 0px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10px;
                font-weight: 900;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: #EEEEEE;
            }}
            """
        )
        self._update_now_btn.clicked.connect(self._trigger_update_install)
        act_layout.addWidget(self._update_now_btn)

        self._update_action_box.hide()
        update_card_layout.addWidget(self._update_action_box)

        layout.addWidget(update_card)

        # Populate initial status
        self.set_update_info(self._update_info)

        layout.addStretch(1)
        return page

    def set_update_info(self, info: UpdateInfo | None) -> None:
        self._update_info = info
        if hasattr(self, "_version_badge"):
            if info is None:
                self._version_badge.setText(f"v{__version__} // WIN64")
                self._version_badge.setColors(LIME, "#121212")
                if hasattr(self, "_header_download_btn"):
                    self._header_download_btn.hide()
            else:
                self._version_badge.setText(f"UPDATE AVAILABLE // v{info.version}")
                self._version_badge.setColors("#D8FF3E", "#000000")
                if hasattr(self, "_header_download_btn"):
                    self._header_download_btn.setText(f"DOWNLOAD v{info.version} →")
                    self._header_download_btn.show()

        if not hasattr(self, "_update_status_lbl"):
            return
        if info is None:
            self._update_status_lbl.setText(f"FlowState is up to date (v{__version__}).")
            self._update_action_box.hide()
        else:
            self._update_status_lbl.setText(f"Release v{info.version} is ready for installation.")
            self._update_banner_lbl.setText(f"✦ UPDATE READY: v{info.version}")
            self._update_action_box.show()

    def _manual_check_updates(self) -> None:
        self._check_update_btn.setEnabled(False)
        self._check_update_btn.setText("CHECKING...")
        self._update_status_lbl.setText("Connecting to GitHub Releases...")

        signals = UpdateNotifierSignals()

        def _on_checked(info: UpdateInfo | None):
            self._check_update_btn.setEnabled(True)
            self._check_update_btn.setText("CHECK FOR UPDATES")
            self.set_update_info(info)
            if info is None:
                self._update_status_lbl.setText(f"You are running the latest release (v{__version__}).")

        signals.checked.connect(_on_checked)
        check_for_update_async(signals, force=True)

    def _trigger_update_install(self) -> None:
        if self._update_info and self._on_update_requested:
            self.accept()
            self._on_update_requested(self._update_info)

    # -- Save --------------------------------------------------------
    def _save(self) -> None:
        cfg = self.config_store.config

        new_toggle = self.toggle_edit.text().strip() or cfg.shortcuts.toggle
        new_ptt = self.ptt_edit.text().strip() or cfg.shortcuts.push_to_talk
        if bindings_conflict(new_toggle, new_ptt):
            QMessageBox.warning(
                self,
                "FlowState",
                f"Toggle ({new_toggle!r}) and push-to-talk ({new_ptt!r}) can't share "
                "all their keys. A quick tap of the toggle shortcut would be read as "
                "push-to-talk instead, so the toggle would seem to do nothing. Pick "
                "keys that don't overlap -- e.g. alt_r for push-to-talk.",
            )
            return

        cfg.general.microphone_device = self.mic_combo.currentData()
        if cfg.general.launch_at_login != self.launch_at_login.isChecked():
            set_launch_at_login(self.launch_at_login.isChecked())
        cfg.general.launch_at_login = self.launch_at_login.isChecked()
        cfg.general.sound_cues = self.sound_cues.isChecked()

        cfg.shortcuts.toggle = new_toggle
        cfg.shortcuts.push_to_talk = new_ptt

        cfg.model.compute_device = self.device_combo.currentText()

        cfg.cleanup.vocabulary_enabled = self.vocab_check.isChecked()
        cfg.cleanup.grammar_enabled = self.grammar_check.isChecked()

        cfg.capture.mode = self.capture_mode.currentData() or "drag"
        cfg.capture.sensitivity = self.sensitivity_slider.value() / 100.0

        self.config_store.save()
        if self._on_applied:
            self._on_applied()
        self.accept()
