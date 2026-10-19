"""Start/stop sound cues. Played on a background thread so they never
block the hotkey handler."""

from __future__ import annotations

import logging
import threading
import winsound

logger = logging.getLogger("flowstate.audio")


def _play_beep_async(frequency: int, duration_ms: int) -> None:
    def _play() -> None:
        try:
            winsound.Beep(frequency, duration_ms)
        except Exception:
            logger.debug("Sound cue failed to play", exc_info=True)

    threading.Thread(target=_play, daemon=True).start()


def play_start_cue() -> None:
    # Gentle subtle high blip (880 Hz, 40ms) instead of Windows system asterisk error ding
    _play_beep_async(880, 40)


def play_stop_cue() -> None:
    # Gentle subtle low blip (520 Hz, 40ms)
    _play_beep_async(520, 40)
