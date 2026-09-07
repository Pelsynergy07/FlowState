"""Launch-at-login via the standard per-user Run registry key. No admin
rights needed, no scheduled task, no installer hook required."""

from __future__ import annotations

import logging
import sys
import winreg

logger = logging.getLogger("flowstate.ui")

_RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "FlowState"


def _build_command() -> str:
    # In a packaged build sys.executable is FlowState.exe itself;
    # in dev it's python.exe, where running -m flowstate is needed.
    # In both cases, --autostart tells FlowState not to open Settings on boot.
    if getattr(sys, "frozen", False) or sys.executable.lower().endswith("flowstate.exe"):
        return f'"{sys.executable}" --autostart'
    return f'"{sys.executable}" -m flowstate --autostart'


def set_launch_at_login(enabled: bool) -> None:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE)
    except OSError:
        logger.warning("Could not open the Run registry key", exc_info=True)
        return
    try:
        if enabled:
            cmd = _build_command()
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, _VALUE_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
