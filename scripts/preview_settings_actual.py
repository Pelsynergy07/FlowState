"""Script to preview and capture actual SettingsWindow tabs in Stark B&W Neo-Brutalism."""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to sys.path
src_path = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_path))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from flowstate import paths
from flowstate.config import ConfigStore
from flowstate.session.model import Session
from flowstate.session.store import create_session, save_session
from flowstate.ui.fonts import load_bundled_fonts
from flowstate.ui.settings_window import SettingsWindow
from flowstate.ui.theme import apply_light_palette, build_stylesheet


def main():
    app = QApplication(sys.argv)
    load_bundled_fonts()
    apply_light_palette(app)
    app.setStyleSheet(build_stylesheet())

    paths.sessions_dir()

    # Create 2 sample sessions if none exist, so the history tab has rich cards
    s1 = create_session("Code.exe")
    s1.transcript = "Refactor the session store to automatically purge history upon machine restart and add 1-click clipboard copying."
    save_session(s1)

    s2 = create_session("chrome.exe")
    s2.transcript = "Check the latest documentation on PySide6 QKeySequence and low level keyboard hooks for Windows."
    save_session(s2)

    cfg_store = ConfigStore()
    win = SettingsWindow(cfg_store)
    win.show()

    artifact_dir = Path(r"C:\Users\Pranav Kumar\.gemini\antigravity-ide\brain\2542d745-cd64-4b0f-9635-a3ecb3bf696d")

    def capture_shortcuts():
        win.tabs.setCurrentIndex(1)  # SHORTCUTS tab
        app.processEvents()
        pix = win.grab()
        pix.save(str(artifact_dir / "shortcuts_bw_preview.png"))
        print("Captured shortcuts_bw_preview.png")

        # Start recording on toggle_edit to capture active state
        win.toggle_edit.start_recording()
        app.processEvents()
        QTimer.singleShot(150, capture_active_recording)

    def capture_active_recording():
        app.processEvents()
        pix = win.grab()
        pix.save(str(artifact_dir / "shortcuts_recording_active.png"))
        print("Captured shortcuts_recording_active.png")
        win.toggle_edit.stop_recording()

        # Now capture HISTORY tab
        QTimer.singleShot(200, capture_history)

    def capture_history():
        win.tabs.setCurrentIndex(5)  # HISTORY tab
        app.processEvents()
        pix = win.grab()
        pix.save(str(artifact_dir / "history_bw_preview.png"))
        print("Captured history_bw_preview.png")

        # Now capture GENERAL tab
        QTimer.singleShot(200, capture_general)

    def capture_general():
        win.tabs.setCurrentIndex(0)  # GENERAL tab
        app.processEvents()
        pix = win.grab()
        pix.save(str(artifact_dir / "general_bw_preview.png"))
        print("Captured general_bw_preview.png")

        QTimer.singleShot(100, app.quit)

    QTimer.singleShot(300, capture_shortcuts)
    app.exec()


if __name__ == "__main__":
    main()
