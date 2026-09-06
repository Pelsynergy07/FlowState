"""FlowState entry point: single-instance guard, tray icon, recording HUD,
hotkeys, and (on first run) the setup wizard. This is what the installed
.exe actually launches.
"""

from __future__ import annotations

import os
import sys
import time

from PySide6.QtCore import Qt, QTimer
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

    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pelsynergy.flowstate.app")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    IPC_SERVER_NAME = "FlowStateSingleInstanceIPC"

    # Single-instance guard via Windows named mutex
    lock = _acquire_single_instance_lock()
    if lock is None:
        logger.info("FlowState is already running. Signaling instance to activate window...")
        try:
            import ctypes
            ctypes.windll.user32.AllowSetForegroundWindow(ctypes.c_uint(-1))
        except Exception:
            pass
        test_socket = QLocalSocket()
        for attempt in range(6):
            test_socket.connectToServer(IPC_SERVER_NAME)
            if test_socket.waitForConnected(500):
                test_socket.write(b"ACTIVATE\n")
                test_socket.flush()
                test_socket.waitForBytesWritten(500)
                test_socket.disconnectFromServer()
                logger.info("Activation signal sent to running instance.")
                break
            time.sleep(0.25)
        else:
            logger.warning("Could not connect to IPC server on running instance.")
        os._exit(0)

    # Start IPC server immediately so any quick subsequent launches connect right away
    ipc_server = QLocalServer(app)
    QLocalServer.removeServer(IPC_SERVER_NAME)
    ipc_server.listen(IPC_SERVER_NAME)
    logger.info("IPC server listening on %s: %s", IPC_SERVER_NAME, ipc_server.isListening())

    def _handle_ipc_connection():
        logger.info("Incoming single-instance IPC connection detected.")
        while ipc_server.hasPendingConnections():
            conn = ipc_server.nextPendingConnection()
            if conn:
                conn.close()
        open_settings()

    ipc_server.newConnection.connect(_handle_ipc_connection)

    from .session.store import purge_all_sessions
    try:
        purge_all_sessions()
        logger.info("Purged session history on startup.")
    except Exception as e:
        logger.warning("Could not purge session history on startup: %s", e)

    load_bundled_fonts()
    apply_light_palette(app)
    app.setStyleSheet(build_stylesheet())

    from .ui.icon import build_app_icon
    app.setWindowIcon(build_app_icon())

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

    settings_dlg: SettingsWindow | None = None
    current_update_info: UpdateInfo | None = None

    def open_settings() -> None:
        nonlocal settings_dlg
        logger.info("open_settings invoked. Existing dialog visible: %s", settings_dlg.isVisible() if settings_dlg else False)
        try:
            if settings_dlg is not None and settings_dlg.isVisible():
                settings_dlg.bring_to_front()
                return
            settings_dlg = SettingsWindow(
                controller.config_store,
                on_applied=controller.apply_config_change,
                controller=controller,
                on_update_requested=start_update,
                update_info=current_update_info,
            )
            def _on_closed():
                nonlocal settings_dlg
                tray.refresh_recent_sessions()
            settings_dlg.finished.connect(_on_closed)
            settings_dlg.bring_to_front()
            logger.info("SettingsWindow brought to front successfully.")
        except Exception:
            logger.error("Failed to open SettingsWindow", exc_info=True)

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

    def _handle_no_speech() -> None:
        hud.show_notice("No speech detected (check mic)")
        if QSystemTrayIcon.isSystemTrayAvailable():
            tray.tray_icon.showMessage(
                "FlowState",
                "No speech was detected. Please check your microphone in Settings.",
                QSystemTrayIcon.Information,
                3000,
            )

    controller.signals.no_speech_detected.connect(_handle_no_speech)

    tray.show()

    def _handle_update_checked(info: UpdateInfo | None) -> None:
        nonlocal current_update_info
        current_update_info = info
        tray.set_update_available(info)
        if info is not None and QSystemTrayIcon.isSystemTrayAvailable():
            tray.tray_icon.showMessage(
                "FlowState Update Available",
                f"Release v{info.version} is available. Open Settings to update.",
                QSystemTrayIcon.Information,
                4000,
            )
        if settings_dlg is not None and settings_dlg.isVisible():
            settings_dlg.set_update_info(info)

    update_signals = UpdateNotifierSignals()
    update_signals.checked.connect(_handle_update_checked)
    check_for_update_async(update_signals)

    is_first_run = ("--first-run" in sys.argv) or (not paths.first_run_flag_path().exists())
    # On first run, the onboarding dialog below does its own (visible,
    # progress-tracked) model download/load -- warming up here too would
    # race it for the exact same models, with the onboarding UI showing
    # no real progress while the invisible background warmup does the
    # actual work (or vice versa). Only warm up here on normal launches.
    controller.start(warmup=not is_first_run)

    if is_first_run:
        from .ui.tutorial import TutorialDialog
        onboarding = OnboardingDialog(controller)
        onboarding.exec()
        if onboarding.skipped:
            paths.first_run_flag_path().write_text("done", encoding="utf-8")
            logger.info("User skipped onboarding. Opening settings directly.")
            QTimer.singleShot(150, open_settings)
        else:
            tutorial = TutorialDialog(controller)
            tutorial.exec()
            logger.info("Scheduling initial open_settings() after tutorial completion")
            QTimer.singleShot(200, open_settings)
    elif "--autostart" not in sys.argv:
        # If user opened the app explicitly (not silent boot startup), show settings!
        logger.info("Scheduling initial open_settings()")
        QTimer.singleShot(100, open_settings)

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
