"""Phase 2 manual verification: record 5s from the default mic, transcribe
it, and print the result plus which device (CUDA/CPU) was used.

Run with:  .venv\\Scripts\\python.exe scripts\\smoke_record.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from flowstate.asr.engine import TranscriptionEngine  # noqa: E402
from flowstate.audio.recorder import Recorder  # noqa: E402
from flowstate.logging_setup import configure_logging  # noqa: E402


def main() -> None:
    logger = configure_logging()
    recorder = Recorder()
    print("Recording for 5 seconds... speak now.")
    recorder.start()
    time.sleep(5)
    wav_path = Path.cwd() / "_smoke_test.wav"
    recorder.stop_and_save(wav_path)
    print(f"Saved {wav_path} ({wav_path.stat().st_size} bytes)")

    engine = TranscriptionEngine()
    print("Transcribing (first run downloads the model, may take a while)...")
    text = engine.transcribe(wav_path)

    print(f"\nDevice used: {engine.active_device}, model: {engine.active_model_id}")
    print(f"Transcript: {text!r}")

    wav_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
