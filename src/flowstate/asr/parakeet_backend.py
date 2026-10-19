"""NVIDIA Parakeet TDT 0.6B v2 on the Apple Neural Engine, shaped like
faster-whisper's WhisperModel so the engine, streaming and screenshot
timing code don't care which recognizer runs.

FlowState's benchmark picked this for Macs: about as accurate as Whisper
large-v3-turbo on English (~2% word errors), a third of the download
(~460 MB), and about 0.1 s per 14-second live window on an M2 Max. It is
English-only; Settings offers Whisper (MLX) for other languages.

The model runs in a small Swift helper (native/macos/FlowStateParakeet,
using FluidAudio and CoreML) that stays loaded and answers one JSON line
per transcription.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
import wave
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("flowstate.asr")

REPO = "FluidInference/parakeet-tdt-0.6b-v2-coreml"
REVISION = "ee09c569f73759e6d44c9bd16766f477b2b36d39"  # the revision the benchmark measured
REQUIRED_PARTS = ("Encoder.mlmodelc", "Decoder.mlmodelc", "JointDecision.mlmodelc", "Preprocessor.mlmodelc",
                  "parakeet_vocab.json")
WEIGHT_PATTERNS = [f"{part}/*" for part in REQUIRED_PARTS[:4]] + [REQUIRED_PARTS[4]]
HELPER_NAME = "FlowStateParakeet"
SAMPLE_RATE = 16000
_MIN_SECONDS = 1.0  # the recognizer rejects shorter audio
_SENTENCE_END = (".", "?", "!")


def helper_path() -> Path | None:
    """The Swift helper: inside FlowState.app when packaged, else the
    development build in native/macos."""
    override = os.environ.get("FLOWSTATE_PARAKEET_HELPER")
    candidates = [Path(override)] if override else []
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        candidates.append(exe.parent.parent / "Helpers" / HELPER_NAME)  # FlowState.app/Contents/Helpers
    repo = Path(__file__).resolve().parents[3]
    candidates.append(repo / "native" / "macos" / HELPER_NAME / ".build" / "release" / HELPER_NAME)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def is_available() -> bool:
    import platform as stdlib_platform

    return sys.platform == "darwin" and stdlib_platform.machine() == "arm64" and helper_path() is not None


def is_valid_model_dir(path: Path) -> bool:
    return all((path / part).exists() for part in REQUIRED_PARTS)


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


def tokens_to_words(tokens: list) -> list[Word]:
    """Subword tokens with times -> words. A token starting with a space
    begins a new word; punctuation tokens attach to the word before."""
    words: list[Word] = []
    text, start, end = "", 0.0, 0.0
    for token, token_start, token_end in tokens:
        token = str(token).replace("▁", " ")
        if token[:1].isspace() and text.strip():
            words.append(Word(start, end, text.strip()))
            text = ""
        if not text.strip():
            start = float(token_start)
        text += token
        end = float(token_end)
    if text.strip():
        words.append(Word(start, end, text.strip()))
    return words


def words_to_segments(words: list[Word]) -> list[Segment]:
    """Sentence-sized segments, so screenshot references can quote what was
    said around the moment of capture."""
    segments: list[Segment] = []
    current: list[Word] = []
    for word in words:
        current.append(word)
        if word.word.endswith(_SENTENCE_END):
            segments.append(Segment(current[0].start, current[-1].end, " ".join(w.word for w in current), current))
            current = []
    if current:
        segments.append(Segment(current[0].start, current[-1].end, " ".join(w.word for w in current), current))
    return segments


def _write_wav(samples, path: Path) -> None:
    import numpy as np

    pcm = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
    if len(pcm) < int(SAMPLE_RATE * _MIN_SECONDS):
        pcm = np.pad(pcm, (0, int(SAMPLE_RATE * _MIN_SECONDS) - len(pcm)))
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes((pcm * 32767).astype(np.int16).tobytes())


def _wav_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()
    except (OSError, EOFError, wave.Error):
        return _MIN_SECONDS


class ParakeetModel:
    def __init__(self, model_dir: Path):
        self._model_dir = model_dir
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._next_id = 0
        self._log = None
        with self._lock:
            self._start()

    def _start(self) -> None:
        helper = helper_path()
        if helper is None:
            raise RuntimeError("The Parakeet speech helper is missing from this FlowState build")
        from .. import paths

        self._log = open(paths.logs_dir() / "parakeet-helper.log", "a", encoding="utf-8")
        self._proc = subprocess.Popen(
            [str(helper), str(self._model_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
            text=True, bufsize=1,
        )
        ready = self._read()
        if not ready.get("ready"):
            self.close()
            raise RuntimeError(f"Parakeet helper did not start: {ready}")
        logger.info("Parakeet helper ready in %.1fs", ready.get("load_seconds", 0.0))

    def _read(self) -> dict:
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("The Parakeet speech helper stopped; see logs/parakeet-helper.log")
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                continue
            return reply

    def _request(self, wav_path: Path) -> dict:
        with self._lock:
            for attempt in (1, 2):
                try:
                    if self._proc is None or self._proc.poll() is not None:
                        self._start()
                    self._next_id += 1
                    self._proc.stdin.write(json.dumps({"id": self._next_id, "path": str(wav_path)}) + "\n")
                    self._proc.stdin.flush()
                    reply = self._read()
                except (BrokenPipeError, OSError, RuntimeError):
                    if attempt == 2:
                        raise
                    logger.warning("Parakeet helper failed; restarting it once", exc_info=True)
                    self.close()
                    continue
                if "error" in reply:
                    raise RuntimeError(f"Parakeet could not transcribe this audio: {reply['error']}")
                return reply
            raise RuntimeError("unreachable")

    def transcribe(self, audio, beam_size: int = 5, word_timestamps: bool = False, **_ignored):
        """Mirrors WhisperModel.transcribe(). Parakeet punctuates and
        capitalizes on its own and takes no prompt, so hotwords and
        initial_prompt are ignored."""
        if isinstance(audio, (str, Path)) and _wav_seconds(Path(audio)) >= _MIN_SECONDS:
            reply = self._request(Path(audio).resolve())
            duration = reply.get("duration", 0.0)
        else:
            samples = audio
            if isinstance(audio, (str, Path)):
                from faster_whisper.audio import decode_audio

                samples = decode_audio(str(audio), sampling_rate=SAMPLE_RATE)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "short.wav"
                _write_wav(samples, path)
                reply = self._request(path)
            duration = len(samples) / SAMPLE_RATE
        words = tokens_to_words(reply.get("tokens") or [])
        segments = words_to_segments(words)
        if not segments and reply.get("text", "").strip():
            segments = [Segment(0.0, float(duration), reply["text"].strip())]
        return iter(segments), Info(language="en", duration=float(duration))

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()
            self._proc = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
