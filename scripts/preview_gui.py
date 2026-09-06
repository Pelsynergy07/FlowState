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

    from flowstate.ui.onboarding import OnboardingDialog
    from flowstate.ui.tutorial import TutorialDialog
    from flowstate.ui.icon import build_app_icon

    app.setWindowIcon(build_app_icon())

    onboarding_btn = QPushButton("Preview Onboarding Setup")
    tutorial_btn = QPushButton("Preview 2-Step Tutorial")
    settings_btn = QPushButton("Preview Settings Window")
    hud_btn = QPushButton("Show Recording HUD (4s)")
    hud_notice_btn = QPushButton("Show No-Speech Notice (3s)")

    class DummyController:
        def __init__(self):
            self.config_store = config_store
            self.hw_name = "NVIDIA GeForce RTX 2070"
            self.is_gpu = True
            self.cores = 8
            from PySide6.QtCore import QObject, Signal
            class DummySignals(QObject):
                recording_started = Signal()
                recording_finished = Signal(str)
            self.signals = DummySignals()

    def open_onboarding() -> None:
        dlg = OnboardingDialog(DummyController())
        dlg.exec()

    def open_tutorial() -> None:
        dlg = TutorialDialog(DummyController())
        dlg.exec()

    def open_settings() -> None:
        dlg = SettingsWindow(config_store)
        dlg.exec()

    def show_hud() -> None:
        hud.show_recording()
        QTimer.singleShot(4000, hud.hide_recording)

    def show_notice() -> None:
        hud.show_notice("No speech detected (check mic)", 3000)

    onboarding_btn.clicked.connect(open_onboarding)
    tutorial_btn.clicked.connect(open_tutorial)
    settings_btn.clicked.connect(open_settings)
    hud_btn.clicked.connect(show_hud)
    hud_notice_btn.clicked.connect(show_notice)

    layout.addWidget(onboarding_btn)
    layout.addWidget(tutorial_btn)
    layout.addWidget(settings_btn)
    layout.addWidget(hud_btn)
    layout.addWidget(hud_notice_btn)
    launcher.resize(340, 260)
    launcher.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
