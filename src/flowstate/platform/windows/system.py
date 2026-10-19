"""Process-level Windows integration: single instance, restart, launch at
login, sound cues, privacy checks and hardware names."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading

logger = logging.getLogger("flowstate.platform")

_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = "FlowState"
_MUTEX_NAME = "Global\\FlowStateSingleInstance"  # installer.iss AppMutex depends on this name


def prepare_process() -> None:
    """Groups taskbar entries and notifications under FlowState's own identity."""
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pelsynergy.flowstate.app")
    except Exception:
        pass


def configure_qt_application(app) -> None:
    """Nothing to adjust on Windows."""


def acquire_single_instance_lock():
    """Best-effort single-instance guard via a named mutex. Returns the
    mutex handle on success, or None if another instance already holds it."""
    import win32api
    import win32event
    import winerror

    mutex = win32event.CreateMutex(None, False, _MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return None
    return mutex


def allow_other_instance_to_take_focus() -> None:
    try:
        import ctypes

        ctypes.windll.user32.AllowSetForegroundWindow(ctypes.c_uint(-1))
    except Exception:
        pass


def autostart_command() -> str:
    # In a packaged build sys.executable is FlowState.exe itself;
    # in dev it's python.exe, where running -m flowstate is needed.
    # In both cases, --autostart tells FlowState not to open Settings on boot.
    if getattr(sys, "frozen", False) or sys.executable.lower().endswith("flowstate.exe"):
        return f'"{sys.executable}" --autostart'
    return f'"{sys.executable}" -m flowstate --autostart'


def set_launch_at_login(enabled: bool) -> None:
    """Launch-at-login via the standard per-user Run registry key. No admin
    rights needed, no scheduled task, no installer hook required."""
    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE)
    except OSError:
        logger.warning("Could not open the Run registry key", exc_info=True)
        return
    try:
        if enabled:
            winreg.SetValueEx(key, _RUN_VALUE_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, _RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


def spawn_relaunch() -> None:
    """Starts a new FlowState a moment after this process exits."""
    exe = sys.executable
    if getattr(sys, "frozen", False):
        cmd = f'ping 127.0.0.1 -n 2 > nul & start "" "{exe}"'
    else:
        cmd = f'ping 127.0.0.1 -n 2 > nul & start "" "{exe}" -m flowstate'
    subprocess.Popen(
        cmd,
        shell=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )


def play_tone(frequency: int, duration_ms: int) -> None:
    def _play() -> None:
        try:
            import winsound

            winsound.Beep(frequency, duration_ms)
        except Exception:
            logger.debug("Sound cue failed to play", exc_info=True)

    threading.Thread(target=_play, daemon=True).start()


def microphone_access_blocked() -> bool:
    """True if Windows privacy settings stop desktop apps using the microphone.

    When blocked, every recording is silent and FlowState can only report
    "no speech detected", so setup checks it explicitly.
    """
    try:
        import winreg
    except ImportError:
        return False
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    for hive, key_path in ((winreg.HKEY_LOCAL_MACHINE, base), (winreg.HKEY_CURRENT_USER, base),
                           (winreg.HKEY_CURRENT_USER, base + r"\NonPackaged")):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                if str(winreg.QueryValueEx(key, "Value")[0]).lower() == "deny":
                    return True
        except OSError:
            continue
    return False


MICROPHONE_SETTINGS_URL = "ms-settings:privacy-microphone"


def cpu_name() -> str:
    """Readable processor name, e.g. "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz"."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return " ".join(str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).split())
    except Exception:
        import platform

        return platform.processor() or "Your processor"
