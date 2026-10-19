"""The one place FlowState decides which operating system it is running on.

Everything above this package (the recording flow, the text pipeline, the
UI) is shared by every platform. Everything that has to talk to the OS --
global hotkeys, pasting into another app, restoring focus, window effects,
launch at login, single-instance locking, sound cues, permissions -- lives
in one adapter per platform:

    platform/windows/   Win32 (the original FlowState implementation)
    platform/macos/     Quartz / AppKit through PyObjC

Feature code imports the small facade functions below, or the module
returned by backend(), and never imports win32*/ctypes.windll/AppKit
itself. Adding a platform (e.g. Linux, or the Android shell's Python
bridge) means adding one adapter package with the same functions; see
docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import importlib
import platform as _stdlib_platform
import sys
from functools import lru_cache
from types import ModuleType

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")


def name() -> str:
    """Human-readable OS name for UI text, e.g. "Windows" or "macOS"."""
    if IS_MACOS:
        return "macOS"
    if IS_WINDOWS:
        return "Windows"
    return "Linux"


def device_noun() -> str:
    """What to call this computer in UI copy: "this PC" vs "this Mac"."""
    return "Mac" if IS_MACOS else "PC"


def is_apple_silicon() -> bool:
    return IS_MACOS and _stdlib_platform.machine() == "arm64"


@lru_cache(maxsize=1)
def backend() -> ModuleType:
    """The adapter package for this OS. Imported lazily so merely importing
    a feature module never pulls in another OS's native libraries."""
    if IS_WINDOWS:
        return importlib.import_module("flowstate.platform.windows")
    if IS_MACOS:
        return importlib.import_module("flowstate.platform.macos")
    return importlib.import_module("flowstate.platform.generic")


def adapter(part: str) -> ModuleType:
    """One submodule of this OS's adapter: "keyboard", "clipboard", "focus",
    "window" or "system"."""
    return importlib.import_module(f"{backend().__name__}.{part}")


# -- Capabilities ------------------------------------------------------------
# UI code asks what the platform can do instead of checking the OS name, so a
# feature lands everywhere it is supported without per-OS branches in the UI.

def capabilities() -> dict[str, bool]:
    return dict(backend().CAPABILITIES)


def supports(feature: str) -> bool:
    return bool(backend().CAPABILITIES.get(feature, False))


# -- Small facades used across the UI --------------------------------------------

def open_path(path) -> None:
    """Open a file or folder in Explorer / Finder."""
    backend().open_path(path)


def drag_modifier_token() -> str:
    """Modifier held while dragging a screenshot region: Ctrl on Windows,
    Option on macOS (Control+click is a right-click there)."""
    return backend().DRAG_MODIFIER_TOKEN


def default_shortcuts() -> tuple[str, str]:
    """(toggle, push_to_talk) defaults for a fresh install on this OS."""
    return backend().DEFAULT_TOGGLE, backend().DEFAULT_PUSH_TO_TALK


def known_shortcut_conflicts() -> dict[str, str]:
    return dict(backend().KNOWN_SHORTCUT_CONFLICTS)


def build_label() -> str:
    """Shown in Settings > About, e.g. "macOS Apple silicon" or "Windows Native x64"."""
    machine = _stdlib_platform.machine().lower()
    if IS_MACOS:
        return "macOS Apple silicon" if machine == "arm64" else "macOS Intel"
    if IS_WINDOWS:
        return "Windows Native x64" if machine in ("amd64", "x86_64") else f"Windows {machine}"
    return f"{name()} {machine}"


def badge_label() -> str:
    """Short build tag for the Settings header, e.g. "WIN64" or "MAC ARM64"."""
    machine = _stdlib_platform.machine().lower()
    if IS_MACOS:
        return "MAC ARM64" if machine == "arm64" else "MAC X64"
    if IS_WINDOWS:
        return "WIN64"
    return name().upper()
