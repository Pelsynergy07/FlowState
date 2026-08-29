"""Visual preview of FlowState's GUI style: opens a small launcher with
buttons to show the Settings window and the recording HUD. No hotkeys,
mic, or AI models are wired up -- this is purely for reviewing/tweaking
the look.

Run with:  .venv\\Scripts\\python.exe scripts\\preview_gui.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget  # noqa: E402

from flowstate.config import ConfigStore  # noqa: E402
from flowstate.ui.fonts import load_bundled_fonts  # noqa: E402
from flowstate.ui.hud import RecordingHUD  # noqa: E402
from flowstate.ui.settings_window import SettingsWindow  # noqa: E402
from flowstate.ui.theme import apply_light_palette, build_stylesheet  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    load_bundled_fonts()
    apply_light_palette(app)
    app.setStyleSheet(build_stylesheet())

    config_store = ConfigStore()
    hud = RecordingHUD(level_provider=lambda: 0.4)

    launcher = QWidget()
    launcher.setObjectName("background")
    launcher.setWindowTitle("FlowState GUI Preview")
    layout = QVBoxLayout(launcher)
    layout.setContentsMargins(28, 28, 28, 28)
    layout.setSpacing(14)

    settings_btn = QPushButton("Open Settings")
    hud_btn = QPushButton("Show Recording HUD (5s)")
    hud_processing_btn = QPushButton("Show Processing State (3s)")

    def open_settings() -> None:
        dlg = SettingsWindow(config_store)
        dlg.exec()

    def show_hud() -> None:
        hud.show_recording()
        QTimer.singleShot(5000, hud.hide_recording)

    def show_processing() -> None:
        hud.show_recording()
        hud.show_processing()
        QTimer.singleShot(3000, hud.hide_recording)

    settings_btn.clicked.connect(open_settings)
    hud_btn.clicked.connect(show_hud)
    hud_processing_btn.clicked.connect(show_processing)

    layout.addWidget(settings_btn)
    layout.addWidget(hud_btn)
    layout.addWidget(hud_processing_btn)
    launcher.resize(300, 190)
    launcher.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
