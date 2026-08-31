"""FlowState entry point: single-instance guard, tray icon, recording HUD,
hotkeys, and (on first run) the setup wizard. This is what the installed
.exe actually launches.
"""

from __future__ import annotations

import os
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
from .ui.update_installer import UpdateInstallDialog
from .ui.update_notifier import UpdateNotifierSignals, check_for_update_async
from .update_check import UpdateInfo


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
    # Belt-and-suspenders alongside packaging/entry_point.py's identical
    # guard: a windowed build (no console attached) has sys.stdout/stderr
    # as literally None, and logging.StreamHandler() (configure_logging,
    # right below) captures sys.stderr at construction time -- so this
    # has to run before that, no matter how this function ends up called.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

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

    def start_update(info: UpdateInfo) -> None:
        if controller.is_recording:
            QMessageBox.information(None, "FlowState", "Finish your current recording before updating.")
            return
        reply = QMessageBox.question(
            None,
            "FlowState",
            f"Update to v{info.version} now?\n\n"
            "FlowState will close and reopen automatically once the update finishes installing.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return
        dlg = UpdateInstallDialog(info)
        dlg.exec()
        if dlg.succeeded:
            controller.stop()
            app.quit()

    tray = TrayController(
        on_toggle_recording=controller.toggle_recording,
        on_open_settings=open_settings,
        on_quit=do_quit,
        on_update_requested=start_update,
    )
    controller.signals.recording_started.connect(lambda: tray.set_recording_state(True))
    controller.signals.recording_finished.connect(lambda _text: tray.set_recording_state(False))
    controller.signals.recording_finished.connect(lambda _text: tray.refresh_recent_sessions())
    controller.signals.error.connect(lambda _msg: tray.set_recording_state(False))

    def show_error(message: str) -> None:
        QMessageBox.warning(None, "FlowState", f"Something went wrong during transcription:\n\n{message}")

    controller.signals.error.connect(show_error)

    tray.show()

    update_signals = UpdateNotifierSignals()
    update_signals.checked.connect(tray.set_update_available)
    check_for_update_async(update_signals)

    is_first_run = not paths.first_run_flag_path().exists()
    # On first run, the onboarding dialog below does its own (visible,
    # progress-tracked) model download/load -- warming up here too would
    # race it for the exact same models, with the onboarding UI showing
    # no real progress while the invisible background warmup does the
    # actual work (or vice versa). Only warm up here on normal launches.
    controller.start(warmup=not is_first_run)

    if is_first_run:
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
