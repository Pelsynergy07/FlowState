"""Feeds live mouse movement into a CircleGestureDetector via pynput.

Only active while a recording session is in progress -- it is started at
the top of the recording flow and stopped the instant recording ends, so
the hook can never fire during ordinary mouse use.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from pynput import mouse

from .gesture import CircleGestureDetector, Sensitivity

logger = logging.getLogger("flowstate.capture")


class GestureMouseHook:
    def __init__(self, on_circle: Callable[[float, float], None], sensitivity: Sensitivity | None = None):
        self._on_circle = on_circle
        self._detector = CircleGestureDetector(sensitivity=sensitivity or Sensitivity())
        self._listener: mouse.Listener | None = None

    def _on_move(self, x: int, y: int) -> None:
        try:
            result = self._detector.add_point(float(x), float(y), time.monotonic())
        except Exception:
            logger.warning("Gesture detector raised on a move event; ignoring", exc_info=True)
            return
        if result is not None:
            cx, cy = result
            self._on_circle(cx, cy)

    def start(self) -> None:
        self._detector.reset()
        # non-suppressing: never blocks or consumes real mouse events
        self._listener = mouse.Listener(on_move=self._on_move)
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
