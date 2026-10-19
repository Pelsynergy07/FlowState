"""Minimal process integration for platforms without a native adapter."""

from __future__ import annotations

import subprocess
import sys

_lock = None
MICROPHONE_SETTINGS_URL = ""


def prepare_process() -> None:
    pass


def configure_qt_application(app) -> None:
    pass


def acquire_single_instance_lock():
    global _lock
    from PySide6.QtCore import QLockFile

    from ... import paths

    lock = QLockFile(str(paths.app_data_dir() / "flowstate.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        return None
    _lock = lock
    return lock


def allow_other_instance_to_take_focus() -> None:
    pass


def autostart_command() -> str:
    return f'"{sys.executable}" -m flowstate --autostart'


def set_launch_at_login(enabled: bool) -> None:
    pass


def spawn_relaunch() -> None:
    subprocess.Popen(["/bin/sh", "-c", f'sleep 1; "{sys.executable}" -m flowstate'], start_new_session=True)


def play_tone(frequency: int, duration_ms: int) -> None:
    pass


def microphone_access_blocked() -> bool:
    return False


def cpu_name() -> str:
    import platform

    return platform.processor() or "Your processor"
