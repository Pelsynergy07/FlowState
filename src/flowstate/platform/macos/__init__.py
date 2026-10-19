"""macOS adapter: Quartz event taps, NSPasteboard, NSWorkspace and AppKit
window tweaks, all through PyObjC.

FlowState lives in the menu bar and shows a Dock icon only while one of
its windows is open (see system.configure_qt_application). macOS asks the user for
four permissions, which onboarding walks through (see permissions.py):
Microphone, Accessibility (to paste and to use global shortcuts),
Input Monitoring (to see shortcut keys) and, for screenshots only,
Screen Recording.
"""

from __future__ import annotations

import subprocess

CAPABILITIES = {
    "cuda": False,
    "metal": True,
    "global_hotkeys": True,
    "paste_into_apps": True,
    "drag_capture": True,
    "circle_capture": True,
    "launch_at_login": True,
    "self_update": True,
    "permissions_page": True,
}

# Control+click is a right-click on macOS, so screenshot regions are dragged
# with Shift held instead.
DRAG_MODIFIER_TOKEN = "shift"
# Fn (the 🌐 key on newer keyboards) + Shift + Space: free in macOS and in
# common apps, unlike Control+Shift+Space.
DEFAULT_TOGGLE = "fn+shift+space"
# The defaults earlier Mac builds wrote to config.json; upgraded in place.
PREVIOUS_DEFAULT_TOGGLES = ("ctrl+shift+space",)
# Hold the right Option key: one key, rarely needed for typing (the left
# Option key types accents and symbols), and free of system shortcuts.
DEFAULT_PUSH_TO_TALK = "alt_r"

KNOWN_SHORTCUT_CONFLICTS = {
    "cmd+space": "Spotlight",
    "cmd+alt+space": "Finder search",
    "ctrl+space": "switching keyboard input sources",
    "ctrl+alt+space": "switching keyboard input sources",
    "cmd+shift+space": "some launchers (Raycast, Alfred)",
    "alt+space": "Raycast and Alfred",
    "ctrl+m": "Return in Terminal and many text fields",
    "cmd+m": "minimizing windows in every app",
    "cmd+shift+m": "many chat apps (mute)",
}


def open_path(path) -> None:
    subprocess.Popen(["/usr/bin/open", str(path)])
