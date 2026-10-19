"""Fallback adapter for platforms without a native one yet (e.g. Linux).

Enough for the app to start, record from the tray and copy the result to
the clipboard; global shortcuts and pasting into other apps are off. It is
also the template for a new adapter: implement the same submodules
(keyboard, clipboard, focus, window, system) as platform/windows.
"""

from __future__ import annotations

import subprocess

CAPABILITIES = {
    "cuda": True,
    "global_hotkeys": False,
    "paste_into_apps": False,
    "drag_capture": False,
    "circle_capture": False,
    "launch_at_login": False,
    "self_update": False,
    "permissions_page": False,
}

DRAG_MODIFIER_TOKEN = "ctrl"
DEFAULT_TOGGLE = "ctrl+shift+space"
DEFAULT_PUSH_TO_TALK = "ctrl+m"
KNOWN_SHORTCUT_CONFLICTS: dict[str, str] = {}


def open_path(path) -> None:
    subprocess.Popen(["xdg-open", str(path)])
