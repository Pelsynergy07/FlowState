"""Full-monitor screenshot capture via mss, targeting whichever monitor
contains a given point (so a circle gesture on a second monitor captures
the right screen in a multi-monitor setup)."""

from __future__ import annotations

import mss
from PIL import Image


def capture_monitor_at(x: float, y: float) -> tuple[Image.Image, dict]:
    """Returns (image, monitor_geometry). monitor_geometry has left/top so
    callers can convert virtual-screen coordinates into image-local ones,
    and scale: image pixels per screen coordinate. That is 1 on Windows
    (both are physical pixels) and 2 on a Retina Mac, where mss reports
    monitors in points but grabs every physical pixel."""
    with mss.mss() as sct:
        monitor = dict(_monitor_containing(sct, x, y))
        raw = sct.grab(monitor)
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        monitor["scale"] = raw.size[0] / monitor["width"] if monitor.get("width") else 1.0
        return image, monitor


def _monitor_containing(sct: "mss.base.MSSBase", x: float, y: float) -> dict:
    # monitors[0] is the union of all displays; monitors[1:] are individual ones.
    for m in sct.monitors[1:]:
        if m["left"] <= x < m["left"] + m["width"] and m["top"] <= y < m["top"] + m["height"]:
            return m
    return sct.monitors[0]
