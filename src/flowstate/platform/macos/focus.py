"""Remember and restore the frontmost app.

macOS has no per-window foreground handle a background app can safely
hold, so the target is the frontmost application, by process id. FlowState
never activates itself while recording, so restoring is normally a no-op;
it matters when the user clicked elsewhere (e.g. the menu bar) meanwhile.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("flowstate.inject")

_RESTORE_ATTEMPTS = 6
_RESTORE_RETRY_SECONDS = 0.05


def _frontmost():
    from AppKit import NSWorkspace

    return NSWorkspace.sharedWorkspace().frontmostApplication()


def get_foreground_window() -> int:
    """Process id of the frontmost app (0 if unknown)."""
    try:
        app = _frontmost()
        return int(app.processIdentifier()) if app is not None else 0
    except Exception:
        return 0


def get_window_title(pid: int) -> str:
    """The app's name, e.g. "Safari". Window titles would need Accessibility
    queries; the app name is what session history shows."""
    try:
        from AppKit import NSRunningApplication

        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        return str(app.localizedName()) if app is not None else ""
    except Exception:
        return ""


def restore_foreground_window(pid: int) -> bool:
    if not pid:
        return False
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

        if get_foreground_window() == pid:
            return True
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is None or app.isTerminated():
            return False
        for attempt in range(_RESTORE_ATTEMPTS):
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            time.sleep(_RESTORE_RETRY_SECONDS)
            if get_foreground_window() == pid:
                return True
        logger.warning("Could not bring %s back to the front", app.localizedName())
        return False
    except Exception:
        logger.warning("Failed to restore the frontmost app", exc_info=True)
        return False
