"""System tray icon and context menu: the app's home when no window is
open. Icon color itself communicates recording state (blue idle, red
recording) so a glance at the tray is enough."""

from __future__ import annotations

import os
from typing import Callable

from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..session.store import list_sessions
from ..update_check import UpdateInfo
from .icon import build_tray_icon


class TrayController:
    def __init__(
        self,
        on_toggle_recording: Callable[[], None],
        on_open_settings: Callable[[], None],
        on_quit: Callable[[], None],
        on_update_requested: Callable[[UpdateInfo], None] | None = None,
    ):
        self._on_toggle_recording = on_toggle_recording
        self._on_update_requested = on_update_requested
        self._update_info: UpdateInfo | None = None

        self.tray_icon = QSystemTrayIcon(build_tray_icon(recording=False))
        self.tray_icon.setToolTip("FlowState")

        self.menu = QMenu()
        self._toggle_action = self.menu.addAction("Start Listening")
        self._toggle_action.triggered.connect(on_toggle_recording)

        self.menu.addSeparator()
        # Hidden until an actual update is found (set_update_available) --
        # never shown when the app is already on the latest release.
        self._update_action = self.menu.addAction("Update available")
        self._update_action.setVisible(False)
        self._update_action.triggered.connect(self._handle_update_click)

        self.menu.addSeparator()
        self.recent_menu = self.menu.addMenu("Recent Sessions")
        self.refresh_recent_sessions()

        self.menu.addSeparator()
        settings_action = self.menu.addAction("Settings...")
        settings_action.triggered.connect(on_open_settings)

        self.menu.addSeparator()
        quit_action = self.menu.addAction("Quit FlowState")
        quit_action.triggered.connect(on_quit)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._on_toggle_recording()

    def refresh_recent_sessions(self) -> None:
        self.recent_menu.clear()
        folders = list_sessions()[:5]
        if not folders:
            empty = self.recent_menu.addAction("(no sessions yet)")
            empty.setEnabled(False)
            return
        for folder in folders:
            transcript_path = folder / "transcript.txt"
            preview = transcript_path.read_text(encoding="utf-8")[:40] if transcript_path.exists() else folder.name
            action = self.recent_menu.addAction(preview or folder.name)
            action.triggered.connect(lambda checked=False, f=folder: os.startfile(str(f)))

    def set_update_available(self, info: UpdateInfo | None) -> None:
        """Shows/hides the update menu entry. Called with None on every
        launch where the app is already current -- that's the normal case,
        so the entry must stay hidden rather than showing something stale."""
        self._update_info = info
        if info is None:
            self._update_action.setVisible(False)
            return
        self._update_action.setText(f"Update available: v{info.version}")
        self._update_action.setVisible(True)

    def _handle_update_click(self) -> None:
        if self._update_info is not None and self._on_update_requested is not None:
            self._on_update_requested(self._update_info)

    def set_recording_state(self, recording: bool) -> None:
        self.tray_icon.setIcon(build_tray_icon(recording=recording))
        self._toggle_action.setText("Stop Listening" if recording else "Start Listening")

    def show(self) -> None:
        self.tray_icon.show()
