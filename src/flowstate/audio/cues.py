"""Start/stop sound cues. Played on a background thread so they never
block the hotkey handler."""

from __future__ import annotations

import logging
import threading
import winsound

logger = logging.getLogger("flowstate.audio")


def _play_async(alias: int) -> None:
    def _play() -> None:
        try:
            winsound.MessageBeep(alias)
        except Exception:
            logger.debug("Sound cue failed to play", exc_info=True)

    threading.Thread(target=_play, daemon=True).start()


def play_start_cue() -> None:
    _play_async(winsound.MB_ICONASTERISK)


def play_stop_cue() -> None:
    _play_async(winsound.MB_OK)
