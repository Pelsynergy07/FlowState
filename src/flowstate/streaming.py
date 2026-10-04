"""Transcribe/polish live windows while retaining the complete recorded WAV."""
from __future__ import annotations

import logging
import threading
import wave
from pathlib import Path

import numpy as np

from .text.structure import structure_text

logger = logging.getLogger("flowstate.streaming")
STEP_SECONDS = 24.0
OVERLAP_SECONDS = 6.0
LOOKAHEAD_SECONDS = 6.0


class StreamingDictation:
    def __init__(self, recorder, engine, pipeline, folder: Path):
        self._recorder = recorder
        self._engine = engine
        self._pipeline = pipeline
        self._folder = folder
        self._stop = threading.Event()
        self._cursor = 0.0
        self._segments: list[tuple[float, float, str]] = []
        self._cleaned: list[str] = []
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop_capture(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            while not self._stop.wait(0.25):
                end = self._cursor + STEP_SECONDS + LOOKAHEAD_SECONDS
                begin = max(0.0, self._cursor - OVERLAP_SECONDS)
                audio, rate = self._recorder.snapshot_audio(begin, end)
                if len(audio) / rate + 0.01 < end - begin:
                    continue
                self._process(audio, rate, begin, self._cursor + STEP_SECONDS, budget=8.0)
        except Exception as exc:
            self._error = exc
            logger.warning("Live processing failed; full recording will be recovered at stop", exc_info=True)

    def _process(self, audio, rate: int, begin: float, cutoff: float, *, budget: float, final: bool = False) -> None:
        path = self._folder / "_live_window.wav"
        try:
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                wav.writeframes(audio.tobytes())
            words = self._engine.transcribe_words(path)
            # The same time interval is owned by exactly one window. Both
            # sides hear context, but only its owned words enter the transcript.
            owned = [(begin + start, begin + end, text) for start, end, text in words
                     if self._cursor <= begin + (start + end) / 2
                     and (final or begin + (start + end) / 2 < cutoff)]
            raw = " ".join(text for _, _, text in owned)
            if raw:
                cleaned = self._pipeline.run(raw, budget_seconds=budget, allow_load=False,
                                             cancel_event=None if final else self._stop)
                self._segments.append((owned[0][0], owned[-1][1], raw))
                self._cleaned.append(cleaned)
            self._cursor = cutoff
        finally:
            path.unlink(missing_ok=True)

    def finish(self, wav_path: Path) -> tuple[list[tuple[float, float, str]], str]:
        self.stop_capture()
        self._thread.join()
        if self._error is not None:
            # Never deliver a partial prefix after any failed live window.
            segments = self._engine.transcribe_segments(wav_path)
            raw = " ".join(text for _, _, text in segments)
            return segments, structure_text(self._pipeline.run(raw, budget_seconds=2.0, allow_load=False))
        with wave.open(str(wav_path), "rb") as wav:
            rate = wav.getframerate()
            duration = wav.getnframes() / rate
            begin = max(0.0, self._cursor - OVERLAP_SECONDS)
            wav.setpos(min(wav.getnframes(), int(begin * rate)))
            audio = np.frombuffer(wav.readframes(wav.getnframes() - wav.tell()), dtype=np.int16)
        if duration > self._cursor:
            # Short recordings retain whole-message polishing. On long ones,
            # only the tail is left; give it a small final generation budget.
            budget = 2.0 if not self._segments else 0.8
            # Whisper can align its last word slightly beyond the WAV's end.
            # The final window must keep it rather than treat padding as a cutoff.
            self._process(audio, rate, begin, duration, budget=budget, final=True)
        return list(self._segments), structure_text(" ".join(self._cleaned))
