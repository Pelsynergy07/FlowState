"""Windows adapter: Win32 hooks, clipboard, focus and window styles.

This is FlowState's original implementation, moved here unchanged so the
rest of the app can stay OS-neutral. Submodules import pywin32/ctypes.windll
only when first used.
"""

from __future__ import annotations

import os

CAPABILITIES = {
    "cuda": True,
    "global_hotkeys": True,
    "paste_into_apps": True,
    "drag_capture": True,
    "circle_capture": True,
    "launch_at_login": True,
    "self_update": True,
    "permissions_page": False,
}

DRAG_MODIFIER_TOKEN = "ctrl"
DEFAULT_TOGGLE = "ctrl+shift+space"
DEFAULT_PUSH_TO_TALK = "ctrl+m"

# Shortcuts other popular apps already use. FlowState takes its hotkeys
# over system-wide, so the other app's shortcut stops working.
KNOWN_SHORTCUT_CONFLICTS = {
    "ctrl+m": "VS Code (toggle Tab key moves focus)",
    "ctrl+shift+space": "VS Code and JetBrains (parameter hints)",
    "ctrl+space": "autocomplete in most code editors",
    "ctrl+shift+m": "Microsoft Teams (mute)",
    "ctrl+shift+a": "Slack and many browsers",
    "alt+space": "Windows (window menu)",
    "ctrl+alt+space": "some input-method switchers",
}


def open_path(path) -> None:
    os.startfile(str(path))
