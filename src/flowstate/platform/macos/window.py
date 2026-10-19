"""AppKit window tweaks Qt has no portable flag for."""

from __future__ import annotations

import logging

logger = logging.getLogger("flowstate.ui")


def _ns_window(widget):
    """The widget's NSWindow, or None when Qt isn't drawing through AppKit
    (e.g. the offscreen platform used by tests, where winId is no NSView)."""
    import ctypes

    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.platformName() != "cocoa":
        return None
    import objc

    view = objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))
    return view.window()


def make_overlay(widget, *, click_through: bool = False, exclude_from_capture: bool = False) -> None:
    """Floats above full-screen apps on every Space, never hides when another
    app is active (Qt tool windows do by default) and optionally ignores the
    mouse and stays out of screenshots and screen sharing."""
    try:
        from AppKit import (
            NSStatusWindowLevel,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSWindowCollectionBehaviorStationary,
            NSWindowSharingNone,
        )

        window = _ns_window(widget)
        if window is None:
            return
        window.setHidesOnDeactivate_(False)
        window.setLevel_(NSStatusWindowLevel)
        window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
            | NSWindowCollectionBehaviorStationary
            | NSWindowCollectionBehaviorIgnoresCycle
        )
        if click_through:
            window.setIgnoresMouseEvents_(True)
        if exclude_from_capture:
            window.setSharingType_(NSWindowSharingNone)
    except Exception:
        logger.warning("Could not apply overlay window settings", exc_info=True)


def bring_to_front(widget) -> None:
    """A menu-bar app is never active on its own; activate it so the window
    comes in front of the app the user was in."""
    try:
        from AppKit import NSApplication

        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        widget.raise_()
        widget.activateWindow()
    except Exception:
        logger.debug("Could not activate FlowState", exc_info=True)


def global_to_logical(x: float, y: float) -> tuple[int, int]:
    """Quartz mouse positions are already in points, the same space Qt uses."""
    return (round(x), round(y))
