"""Phase 4 manual milestone test: drives RecordingController.start_recording()
/ stop_recording() directly (bypassing the live hotkey listener, which needs
a real key press) with a few seconds of real microphone input.

This exercises the full pipeline: record -> WAV -> transcribe -> vocabulary
pass -> grammar pass -> session save -> foreground-window restore -> clipboard
paste.

IMPORTANT (non-technical summary): this script will count down, and during
the countdown you must click into Notepad (or whatever app you want the
text typed into) so it is the active window *before* recording starts.
The very first time you run this, it also downloads AI models (~1.6GB for
speech, one time only) -- that can take several minutes on a slow
connection and will look like nothing is happening. That is normal; just
wait for "Recording for N seconds..." to appear.

Run with:  .venv\\Scripts\\python.exe scripts\\smoke_controller.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flowstate import paths  # noqa: E402
from flowstate.app import RecordingController  # noqa: E402
from flowstate.logging_setup import configure_logging  # noqa: E402

RECORD_SECONDS = 4
COUNTDOWN_SECONDS = 6


def main() -> None:
    configure_logging()

    print("=" * 60)
    print("FlowState milestone test")
    print("=" * 60)
    print()
    print("This will pre-load the AI models now (first time only: can take")
    print("several minutes to download ~1.6GB -- that is normal, just wait).")
    print()
    controller = RecordingController()
    # Force both models to load now, while you're reading this, instead of
    # silently stalling the countdown below.
    controller._asr._load()
    controller._pipeline.preload()
    print(f"Models ready (ASR device: {controller._asr.active_device}).")
    print()
    print(f">>> Click into Notepad (or any text box) RIGHT NOW. <<<")
    print(f"You have {COUNTDOWN_SECONDS} seconds before recording starts.")
    print()
    for i in range(COUNTDOWN_SECONDS, 0, -1):
        print(i)
        time.sleep(1)

    print(f"\nRecording for {RECORD_SECONDS} seconds -- SPEAK NOW.")
    controller.start_recording()
    time.sleep(RECORD_SECONDS)
    controller.stop_recording()

    print("\nDone. The cleaned-up text should now be pasted into Notepad.")
    print(f"(Session files, including the transcript, are saved under: {paths.sessions_dir()})")


if __name__ == "__main__":
    main()
