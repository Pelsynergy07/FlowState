"""Start/stop sound cues. Played asynchronously so they never block the
hotkey handler (winsound on Windows, NSSound on macOS)."""

from __future__ import annotations

from .. import platform


def play_start_cue() -> None:
    # Gentle subtle high blip (880 Hz, 40ms) instead of a system alert sound
    platform.adapter("system").play_tone(880, 40)


def play_stop_cue() -> None:
    # Gentle subtle low blip (520 Hz, 40ms)
    platform.adapter("system").play_tone(520, 40)
