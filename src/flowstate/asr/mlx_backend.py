"""Whisper on Apple silicon through MLX (mlx-whisper), shaped like
faster-whisper's WhisperModel so the engine, streaming and timing code
don't care which one runs.

Same model as Windows GPU machines (large-v3-turbo), converted for MLX. On
an M2 Max a 14-second live window transcribes in about 0.7 s, versus 8-9 s
for the CTranslate2 model on the CPU.

MLX keeps its GPU streams per thread, so every load and transcription runs
on one dedicated worker thread.
"""

from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("flowstate.asr")

SAMPLE_RATE = 16000
WEIGHT_PATTERNS = ["*.json", "*.safetensors", "*.npz"]


def is_available() -> bool:
    try:
        import mlx.core  # noqa: F401
        import mlx_whisper  # noqa: F401
    except Exception:
        return False
    return True


def is_valid_model_dir(path: Path) -> bool:
    if not (path / "config.json").is_file():
        return False
    return any(f.stat().st_size > 0 for pattern in ("*.safetensors", "*.npz") for f in path.glob(pattern))


@dataclass
class Word:
    start: float
    end: float
    word: str
    probability: float = 1.0


@dataclass
class Segment:
    start: float
    end: float
    text: str
    words: list[Word] = field(default_factory=list)


@dataclass
class Info:
    language: str
    duration: float


def _load_audio(audio) -> "object":
    """float32 mono at 16 kHz from a path or an array. PyAV (a faster-whisper
    dependency) decodes and resamples, so no ffmpeg binary is needed."""
    import numpy as np

    if isinstance(audio, (str, Path)):
        from faster_whisper.audio import decode_audio

        return decode_audio(str(audio), sampling_rate=SAMPLE_RATE)
    return np.asarray(audio, dtype=np.float32)


class MlxWhisperModel:
    def __init__(self, model_dir: Path):
        self._model_dir = str(model_dir)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="FlowStateMLX")
        self._executor.submit(self._load).result()

    def _load(self) -> None:
        from mlx_whisper.load_models import load_model
        from mlx_whisper.transcribe import ModelHolder

        import mlx.core as mx

        # mlx_whisper.transcribe() caches one model by path; filling that
        # cache here makes the load happen now instead of on first use.
        ModelHolder.model = load_model(self._model_dir, dtype=mx.float16)
        ModelHolder.model_path = self._model_dir

    def transcribe(self, audio, beam_size: int = 5, word_timestamps: bool = False,
                   condition_on_previous_text: bool = False, hotwords: str | None = None,
                   initial_prompt: str | None = None, **_ignored):
        """Mirrors WhisperModel.transcribe(). mlx-whisper has no beam search
        (decoding is greedy with temperature fallback) and no hotwords, so
        hotwords are folded into the prompt, as faster-whisper does."""
        prompt = " ".join(part for part in (hotwords, initial_prompt) if part) or None
        return self._executor.submit(self._transcribe, audio, word_timestamps,
                                     condition_on_previous_text, prompt).result()

    def _transcribe(self, audio, word_timestamps, condition_on_previous_text, prompt):
        import mlx_whisper

        samples = _load_audio(audio)
        result = mlx_whisper.transcribe(
            samples,
            path_or_hf_repo=self._model_dir,
            word_timestamps=word_timestamps,
            condition_on_previous_text=condition_on_previous_text,
            initial_prompt=prompt,
            language="en" if self._english_only() else None,
            verbose=None,
        )
        segments = []
        for seg in result.get("segments", []):
            words = [Word(float(w["start"]), float(w["end"]), str(w["word"]), float(w.get("probability", 1.0)))
                     for w in seg.get("words", []) or []]
            segments.append(Segment(float(seg["start"]), float(seg["end"]), str(seg["text"]), words))
        return iter(segments), Info(language=result.get("language", "en"), duration=len(samples) / SAMPLE_RATE)

    def _english_only(self) -> bool:
        return self._model_dir.rstrip("/").endswith(".en") or ".en-" in self._model_dir
