"""Settings window: General, Shortcuts, Model, Cleanup, Capture, History.

Airy, minimal styling: warm paper background, hairline borders, generous
whitespace, Instrument Serif for the page headline, Manrope everywhere
else, one consistent corner radius across every card/button/input.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, paths
from ..audio.devices import list_input_devices
from ..config import ConfigStore
from ..hotkeys.manager import bindings_conflict
from ..session.store import list_sessions
from .autostart import set_launch_at_login
from .theme import build_stylesheet


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
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    for w in widgets:
        layout.addWidget(w)
    return frame


def _open_path(path: Path) -> None:
    os.startfile(str(path))


class SettingsWindow(QDialog):
    def __init__(self, config_store: ConfigStore, on_applied: Callable[[], None] | None = None, controller=None):
        super().__init__()
        self.config_store = config_store
        self._on_applied = on_applied
        self._controller = controller
        self.setWindowTitle("FlowState Settings")
        self.setStyleSheet(build_stylesheet())
        self.resize(620, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 30, 32, 26)
        outer.setSpacing(18)

        outer.addWidget(_eyebrow("FlowState / Configuration"))
        outer.addWidget(_headline("Settings"))
        outer.addWidget(_rule())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "GENERAL")
        self.tabs.addTab(self._build_shortcuts_tab(), "SHORTCUTS")
        self.tabs.addTab(self._build_model_tab(), "MODEL")
        self.tabs.addTab(self._build_cleanup_tab(), "CLEANUP")
        self.tabs.addTab(self._build_capture_tab(), "CAPTURE")
        self.tabs.addTab(self._build_history_tab(), "HISTORY")
        outer.addWidget(self.tabs, 1)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("role", "secondary")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        outer.addLayout(button_row)

    # -- General --------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        cfg = self.config_store.config.general
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        layout.addWidget(_muted("Choose the microphone FlowState listens to, and basic behavior."))

        self.mic_combo = QComboBox()
        self.mic_combo.addItem("System default", None)
        for d in list_input_devices():
            self.mic_combo.addItem(d.name, d.name)
        idx = self.mic_combo.findData(cfg.microphone_device)
        self.mic_combo.setCurrentIndex(idx if idx >= 0 else 0)
        layout.addWidget(_card(_eyebrow("01 / Microphone"), self.mic_combo))

        self.launch_at_login = QCheckBox("Launch FlowState when Windows starts")
        self.launch_at_login.setChecked(cfg.launch_at_login)
        self.sound_cues = QCheckBox("Play a sound when recording starts/stops")
        self.sound_cues.setChecked(cfg.sound_cues)
        layout.addWidget(_card(_eyebrow("02 / Behavior"), self.launch_at_login, self.sound_cues))

        layout.addStretch(1)
        layout.addWidget(_muted(f"FlowState v{__version__}"))
        return page

    # -- Shortcuts --------------------------------------------------------
    def _build_shortcuts_tab(self) -> QWidget:
        cfg = self.config_store.config.shortcuts
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        layout.addWidget(
            _muted("Push-to-talk records while held. Toggle starts/stops hands-free with one press.")
        )

        self.toggle_edit = QLineEdit(cfg.toggle)
        self.toggle_edit.setPlaceholderText("e.g. ctrl+shift+space")
        layout.addWidget(_card(_eyebrow("03 / Toggle Shortcut"), self.toggle_edit))

        self.ptt_edit = QLineEdit(cfg.push_to_talk)
        self.ptt_edit.setPlaceholderText("e.g. alt_r")
        layout.addWidget(_card(_eyebrow("04 / Push-to-talk"), self.ptt_edit))

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setProperty("role", "secondary")
        reset_btn.clicked.connect(self._reset_shortcuts)
        layout.addWidget(reset_btn)

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
        """Live readout of what the ASR model actually loaded on, not just
        what's configured -- "auto" can silently mean CPU if there's no
        compatible GPU, and that's worth surfacing plainly rather than
        leaving the user to infer it from how slow transcription feels."""
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

        self.vocab_check = QCheckBox("Developer vocabulary pass (github -> GitHub, etc.)")
        self.vocab_check.setChecked(cfg.vocabulary_enabled)
        self.grammar_check = QCheckBox("Smart formatting: grammar, lists, tone (local AI model)")
        self.grammar_check.setChecked(cfg.grammar_enabled)
        layout.addWidget(
            _card(
                _eyebrow("06 / Cleanup Passes"),
                self.vocab_check,
                self.grammar_check,
                _muted(
                    "Smart formatting turns spoken enumerations into real lists and "
                    "adapts tone for messages/emails, not just punctuation."
                ),
            )
        )

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
        self.capture_mode.addItems(["circle", "drag", "off"])
        self.capture_mode.setCurrentText(cfg.mode)

        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(0, 100)
        self.sensitivity_slider.setValue(int(cfg.sensitivity * 100))

        layout.addWidget(
            _card(
                _eyebrow("07 / Screenshot Capture"),
                self.capture_mode,
                _muted("Circle: draw a loop while recording. Drag: hold Ctrl and drag a box."),
                self.sensitivity_slider,
            )
        )

        layout.addStretch(1)
        return page

    # -- History --------------------------------------------------------
    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(18)

        layout.addWidget(_eyebrow("08 / Recent Sessions"))
        self.history_list = QListWidget()
        for folder in list_sessions()[:20]:
            transcript_path = folder / "transcript.txt"
            preview = transcript_path.read_text(encoding="utf-8")[:60] if transcript_path.exists() else "(empty)"
            item = QListWidgetItem(f"{folder.name}  -  {preview}")
            item.setData(Qt.UserRole, folder)
            self.history_list.addItem(item)
        self.history_list.itemDoubleClicked.connect(self._open_history_item)
        layout.addWidget(self.history_list, 1)

        open_folder_btn = QPushButton("Open Sessions Folder")
        open_folder_btn.setProperty("role", "secondary")
        open_folder_btn.clicked.connect(lambda: _open_path(paths.sessions_dir()))
        layout.addWidget(open_folder_btn)

        return page

    def _open_history_item(self, item: QListWidgetItem) -> None:
        folder = item.data(Qt.UserRole)
        if folder:
            _open_path(folder)

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

        cfg.capture.mode = self.capture_mode.currentText()
        cfg.capture.sensitivity = self.sensitivity_slider.value() / 100.0

        self.config_store.save()
        if self._on_applied:
            self._on_applied()
        self.accept()
