"""Loads FlowState's bundled fonts (Instrument Serif, Manrope) so the UI
looks the same regardless of what's installed on the user's Windows
machine -- neither font ships with Windows by default."""

from __future__ import annotations

import logging
from importlib.resources import files

from PySide6.QtGui import QFontDatabase

logger = logging.getLogger("flowstate.ui")

_FONT_FILES = [
    "InstrumentSerif-Regular.ttf",
    "InstrumentSerif-Italic.ttf",
    "Manrope-Regular.ttf",
    "Manrope-Medium.ttf",
    "Manrope-SemiBold.ttf",
    "Manrope-Bold.ttf",
    "Manrope-ExtraBold.ttf",
]

_loaded = False


def load_bundled_fonts() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    fonts_dir = files("flowstate.resources") / "fonts"
    for filename in _FONT_FILES:
        try:
            data = (fonts_dir / filename).read_bytes()
            font_id = QFontDatabase.addApplicationFontFromData(data)
            if font_id < 0:
                logger.warning("Failed to register bundled font: %s", filename)
        except Exception:
            logger.warning("Could not load bundled font: %s", filename, exc_info=True)
