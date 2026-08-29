"""Detects Ctrl+drag during a recording session: hold Ctrl, drag with the
left mouse button, release to capture that rectangle. The deterministic
alternative to the circle gesture -- no shape recognition, no false
positives, just "did you hold Ctrl and drag."

Only active while a recording session is in progress -- started at the
top of the recording flow and stopped the instant recording ends, same
as the circle-gesture hook, so it can never fire during ordinary use.

Deliberately a passive listener (not suppressing anything): a raw
suppressing WH_MOUSE_LL hook was tried here and caused the system cursor
to visibly stall, because Windows delivers low-level mouse hooks
synchronously in the input pipeline and any Python-side latency shows up
as stutter/freeze. The tradeoff is that the drag is also seen by
whatever's under the cursor (e.g. it can select text there too) -- a
real annoyance, but a working screenshot capture with an occasional
stray text selection beats a frozen mouse.
"""

from __future__ import annotations

import ctypes
import logging
import time
from typing import Callable

from pynput import mouse

logger = logging.getLogger("flowstate.capture")

_VK_CONTROL = 0x11
_user32 = ctypes.windll.user32

# Caps how often on_drag_move fires -- pynput's on_move callback runs on
# essentially every pixel of mouse motion, far more often than any UI needs
# to repaint a selection rectangle.
_MOVE_THROTTLE_SECONDS = 1 / 60


def _ctrl_held() -> bool:
    return bool(_user32.GetAsyncKeyState(_VK_CONTROL) & 0x8000)


class DragCaptureHook:
    def __init__(
        self,
        on_region: Callable[[int, int, int, int], None],
        on_drag_start: Callable[[int, int], None] | None = None,
        on_drag_move: Callable[[int, int], None] | None = None,
        on_drag_end: Callable[[], None] | None = None,
    ):
        """on_region receives (left, top, right, bottom) in virtual-screen
        coordinates once a Ctrl+drag completes. on_drag_start/move/end are
        optional, purely for live visual feedback (e.g. drawing the
        selection box on screen while it's being dragged) -- they fire
        for every Ctrl+drag, even ones too small for on_region to report."""
        self._on_region = on_region
        self._on_drag_start = on_drag_start
        self._on_drag_move = on_drag_move
        self._on_drag_end = on_drag_end
        self._listener: mouse.Listener | None = None
        self._drag_start: tuple[int, int] | None = None
        self._last_move_emit = 0.0

    def _on_click(self, x, y, button, pressed) -> None:
        if button != mouse.Button.left:
            return
        if pressed:
            self._drag_start = (x, y) if _ctrl_held() else None
            if self._drag_start is not None and self._on_drag_start is not None:
                try:
                    self._on_drag_start(x, y)
                except Exception:
                    logger.warning("Drag-start callback raised", exc_info=True)
            return

        if self._drag_start is None:
            return
        start_x, start_y = self._drag_start
        self._drag_start = None
        if self._on_drag_end is not None:
            try:
                self._on_drag_end()
            except Exception:
                logger.warning("Drag-end callback raised", exc_info=True)
        left, right = sorted((start_x, x))
        top, bottom = sorted((start_y, y))
        if right - left < 5 or bottom - top < 5:
            return
        try:
            self._on_region(left, top, right, bottom)
        except Exception:
            logger.warning("Drag-capture callback raised", exc_info=True)

    def _on_move(self, x, y) -> None:
        if self._drag_start is None or self._on_drag_move is None:
            return
        now = time.monotonic()
        if now - self._last_move_emit < _MOVE_THROTTLE_SECONDS:
            return
        self._last_move_emit = now
        try:
            self._on_drag_move(x, y)
        except Exception:
            logger.warning("Drag-move callback raised", exc_info=True)

    def start(self) -> None:
        self._drag_start = None
        self._listener = mouse.Listener(on_click=self._on_click, on_move=self._on_move)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._drag_start = None
