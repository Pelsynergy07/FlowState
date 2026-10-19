"""Full-monitor screenshot capture via mss, targeting whichever monitor
contains a given point (so a circle gesture on a second monitor captures
the right screen in a multi-monitor setup)."""

from __future__ import annotations

import mss
from PIL import Image


def capture_monitor_at(x: float, y: float) -> tuple[Image.Image, dict]:
    """Returns (image, monitor_geometry). monitor_geometry has left/top so
    callers can convert virtual-screen coordinates into image-local ones."""
    with mss.mss() as sct:
        monitor = _monitor_containing(sct, x, y)
        raw = sct.grab(monitor)
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return image, monitor


def _monitor_containing(sct: "mss.base.MSSBase", x: float, y: float) -> dict:
    # monitors[0] is the union of all displays; monitors[1:] are individual ones.
    for m in sct.monitors[1:]:
        if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
            return m
    return sct.monitors[0]
