"""FlowState entry point: single-instance guard, tray icon, recording HUD,
hotkeys, and (on first run) the setup wizard. This is what the installed
.exe actually launches.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from . import paths
from .app import RecordingController
from .logging_setup import configure_logging
from .ui.drag_overlay import DragSelectionOverlay
from .ui.fonts import load_bundled_fonts
from .ui.hud import RecordingHUD
from .ui.onboarding import OnboardingDialog
from .ui.settings_window import SettingsWindow
from .ui.theme import apply_light_palette, build_stylesheet
from .ui.tray import TrayController


def _acquire_single_instance_lock():
    """Best-effort single-instance guard via a named mutex. Returns the
    mutex handle on success, or None if another instance already holds it."""
    import win32api
    import win32event
    import winerror

    mutex = win32event.CreateMutex(None, False, "Global\\FlowStateSingleInstance")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return None
    return mutex


def main() -> int:
    logger = configure_logging()

    lock = _acquire_single_instance_lock()
    if lock is None:
        logger.error("FlowState is already running.")
        return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    load_bundled_fonts()
    apply_light_palette(app)
    app.setStyleSheet(build_stylesheet())

    from PySide6.QtWidgets import QSystemTrayIcon

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.warning("System tray is not available on this machine.")

    controller = RecordingController()

    hud = RecordingHUD(level_provider=controller.get_input_level)
    controller.signals.recording_started.connect(hud.show_recording)
    controller.signals.processing_started.connect(hud.show_processing)
    controller.signals.recording_finished.connect(lambda _text: hud.hide_recording())
    controller.signals.error.connect(lambda _msg: hud.hide_recording())

    drag_overlay = DragSelectionOverlay()
    controller.signals.drag_selection_started.connect(drag_overlay.begin)
    controller.signals.drag_selection_moved.connect(drag_overlay.move_to)
    controller.signals.drag_selection_ended.connect(drag_overlay.end)

    def open_settings() -> None:
        dlg = SettingsWindow(controller.config_store, on_applied=controller.apply_config_change, controller=controller)
        dlg.exec()
        tray.refresh_recent_sessions()

    def do_quit() -> None:
        controller.stop()
        app.quit()

    tray = TrayController(
        on_toggle_recording=controller.toggle_recording,
        on_open_settings=open_settings,
        on_quit=do_quit,
    )
    controller.signals.recording_started.connect(lambda: tray.set_recording_state(True))
    controller.signals.recording_finished.connect(lambda _text: tray.set_recording_state(False))
    controller.signals.recording_finished.connect(lambda _text: tray.refresh_recent_sessions())
    controller.signals.error.connect(lambda _msg: tray.set_recording_state(False))

    def show_error(message: str) -> None:
        QMessageBox.warning(None, "FlowState", f"Something went wrong during transcription:\n\n{message}")

    controller.signals.error.connect(show_error)

    tray.show()
    controller.start()

    if not paths.first_run_flag_path().exists():
        onboarding = OnboardingDialog(controller)
        onboarding.exec()

    logger.info(
        "FlowState is running. Toggle: %s  Push-to-talk: %s",
        controller.config_store.config.shortcuts.toggle,
        controller.config_store.config.shortcuts.push_to_talk,
    )

    exit_code = app.exec()
    controller.stop()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
