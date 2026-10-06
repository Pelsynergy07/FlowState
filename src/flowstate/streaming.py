"""Transcribe/polish live windows while retaining the complete recorded WAV."""
from __future__ import annotations

import logging
import re
import threading
import time
import wave
from pathlib import Path

import numpy as np

from .text.formatter import capitalize_start, join_sections
from .text.guard import preserves_words, repair
from .text.pipeline import apply_rules
from .text.vocabulary import apply_vocabulary

logger = logging.getLogger("flowstate.streaming")
# Short live windows keep the work left after the user stops small: at most
# STEP + LOOKAHEAD seconds of speech are transcribed and formatted then.
STEP_SECONDS = 14.0
OVERLAP_SECONDS = 6.0
LOOKAHEAD_SECONDS = 4.0
LIVE_BUDGET_SECONDS = 8.0
# Stop-to-text target, leaving headroom for pasting within five seconds.
FINISH_BUDGET_SECONDS = 4.0
# A live section being formatted when the user stops may finish if quick.
STOP_GRACE_SECONDS = 1.0
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*$")


def _mid(word: tuple[float, float, str]) -> float:
    return (word[0] + word[1]) / 2


class _StopDeadline:
    """A cancel signal that fires a short grace period after stop."""

    def __init__(self, stop: threading.Event):
        self._stop = stop
        self._stopped_at: float | None = None

    def is_set(self) -> bool:
        if not self._stop.is_set():
            return False
        if self._stopped_at is None:
            self._stopped_at = time.monotonic()
        return time.monotonic() - self._stopped_at >= STOP_GRACE_SECONDS


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
        self._words: list[tuple[float, float, str]] = []
        self._pending: list[tuple[float, float, str]] = []
        # Whether the last section ended at a sentence break or pause.
        self._clean_cut = True
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop_capture(self) -> None:
        self._stop.set()

    def _window_begin(self) -> float:
        # After a cut at a sentence end or pause the next window starts right
        # there: no word straddles it, so no overlap needs aligning. A cut
        # mid-speech overlaps the previous window for acoustic context.
        return self._cursor if self._clean_cut else max(0.0, self._cursor - OVERLAP_SECONDS)

    def _run(self) -> None:
        try:
            while not self._stop.wait(0.25):
                end = self._cursor + STEP_SECONDS + LOOKAHEAD_SECONDS
                begin = self._window_begin()
                audio, rate = self._recorder.snapshot_audio(begin, end)
                if len(audio) / rate + 0.01 < end - begin:
                    continue
                self._process(audio, rate, begin, self._cursor + STEP_SECONDS, budget=LIVE_BUDGET_SECONDS)
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
            clean_start = begin >= self._cursor
            context = " ".join(text for _, _, text in self._words[-40:]) or None
            words = self._engine.transcribe_words(path, context=context)
            candidates = [(begin + start, begin + end, text) for start, end, text in words]
            start_index = None
            if clean_start:
                candidates = [word for word in candidates if _mid(word) >= self._cursor]
                start_index = 0
            elif self._words and self._words[-1][1] >= begin:
                # Timestamp estimates shift slightly between overlapping
                # windows. Align their recognized overlap before choosing the
                # new prefix; a clock-only cutoff can drop a boundary word in
                # both windows or deliver it twice.
                normalize = lambda word: "".join(re.findall(r"\w+", word.casefold()))
                prior = [normalize(text) for _, _, text in self._words[-16:]]
                current = [normalize(text) for _, _, text in candidates]
                for size in range(len(prior), 0, -1):
                    matches = [index for index in range(size, len(current) + 1)
                               if current[index - size:index] == prior[-size:]
                               and abs(candidates[index - 1][1] - self._words[-1][1]) <= 1.0]
                    if matches:
                        start_index = min(matches, key=lambda index: abs(candidates[index - 1][1] - self._words[-1][1]))
                        break
                if start_index is None:
                    # The overlap was recognized differently. If nothing new
                    # was skipped (no speech between the last committed word
                    # and the first new one), continue; never drop speech.
                    last_end = self._words[-1][1]
                    rest = [word for word in candidates if _mid(word) > last_end]
                    first = rest[0][0] if rest else begin + len(audio) / rate
                    if _has_speech(audio, rate, begin, last_end + 0.1, first - 0.1):
                        raise RuntimeError("Could not align live speech overlap; recovering complete recording")
                    logger.info("Live overlap recognized differently; continuing after %.2fs", last_end)
                    candidates = rest
                    start_index = 0
            if start_index is not None:
                candidates = candidates[start_index:]
            elif self._pending and abs((self._pending[0][0] + self._pending[0][1]) / 2 - self._cursor) <= 1.0:
                # Speech resuming after a long silence can have no committed
                # word in the overlap. Keep its previously seen first word
                # even if its new time estimate moved before the cutoff.
                token = "".join(re.findall(r"\w+", self._pending[0][2].casefold()))
                matches = [index for index, word in enumerate(candidates)
                           if "".join(re.findall(r"\w+", word[2].casefold())) == token
                           and abs(word[1] - self._pending[0][1]) <= 1.0]
                if not matches:
                    raise RuntimeError("Could not align resumed speech; recovering complete recording")
                candidates = candidates[min(matches, key=lambda index: abs(candidates[index][1] - self._pending[0][1])):]
            elif self._cursor == 0:
                pass
            else:
                candidates = [word for word in candidates if (word[0] + word[1]) / 2 >= self._cursor]
            candidates = self._fill_skipped(audio, rate, begin, candidates)
            owned = [word for word in candidates if final or _mid(word) < cutoff]
            if not final:
                # End the section at the last sentence break so each section
                # is formatted as whole sentences; the rest is re-heard (with
                # more context) in the next window.
                late = [k for k in range(len(owned) - 1) if _mid(owned[k]) >= self._cursor + STEP_SECONDS * 0.4]
                ends = [k for k in late if _SENTENCE_END.search(owned[k][2])]
                # Otherwise the longest pause: a clause boundary, not mid-phrase.
                pause = lambda k: owned[k + 1][0] - owned[k][1]
                longest = max(late, key=pause, default=None)
                cut = ends[-1] if ends else (longest if longest is not None and pause(longest) >= 0.25 else None)
                if cut is not None:
                    owned = owned[:cut + 1]
                    # owned is a time-ordered prefix of candidates.
                    cutoff = (owned[-1][1] + candidates[len(owned)][0]) / 2
                self._clean_cut = cut is not None
            self._pending = [word for word in candidates if _mid(word) >= cutoff] if not final else []
            raw = " ".join(text for _, _, text in owned)
            if raw:
                cleaned = self._pipeline.run(raw, budget_seconds=budget, allow_load=False,
                                             cancel_event=None if final else _StopDeadline(self._stop))
                self._segments.append((owned[0][0], owned[-1][1], raw))
                self._cleaned.append(cleaned)
                self._words.extend(owned)
            self._cursor = cutoff
        finally:
            path.unlink(missing_ok=True)

    def _fill_skipped(self, audio, rate: int, begin: float, candidates: list) -> list:
        """Whisper sometimes leaves out the first words of a window. If there
        is voice between the committed text and the first new word, re-hear
        just that stretch without any prompt and keep the words found."""
        anchor = self._words[-1][1] if self._words else begin
        anchor = max(anchor, begin)
        first = candidates[0][0] if candidates else begin + len(audio) / rate
        if first - anchor < 0.5 or not _has_speech(audio, rate, begin, anchor + 0.1, first - 0.1):
            return candidates
        lo, hi = max(begin, anchor - 1.0), min(begin + len(audio) / rate, first + 1.0)
        path = self._folder / "_live_gap.wav"
        try:
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(rate)
                wav.writeframes(audio[int((lo - begin) * rate):int((hi - begin) * rate)].tobytes())
            words = self._engine.transcribe_words(path, prompt=False)
        finally:
            path.unlink(missing_ok=True)
        found = [(lo + a, lo + b, text) for a, b, text in words if anchor < _mid((lo + a, lo + b, text)) < first]
        logger.info("Recovered %d word(s) Whisper skipped at %.2f-%.2fs", len(found), anchor, first)
        return found + candidates

    def finish(self, wav_path: Path) -> tuple[list[tuple[float, float, str]], str]:
        started = time.monotonic()
        self.stop_capture()
        self._thread.join()
        if self._error is not None:
            # Never deliver a partial prefix after any failed live window.
            return self._recover(wav_path)
        with wave.open(str(wav_path), "rb") as wav:
            rate = wav.getframerate()
            duration = wav.getnframes() / rate
            begin = self._window_begin()
            wav.setpos(min(wav.getnframes(), int(begin * rate)))
            audio = np.frombuffer(wav.readframes(wav.getnframes() - wav.tell()), dtype=np.int16)
        if duration > self._cursor:
            # Only the tail is left; it gets whatever remains of the budget.
            budget = max(0.5, FINISH_BUDGET_SECONDS - (time.monotonic() - started))
            # Whisper can align its last word slightly beyond the WAV's end.
            # The final window must keep it rather than treat padding as a cutoff.
            try:
                self._process(audio, rate, begin, duration, budget=budget, final=True)
            except Exception:
                logger.warning("Final live window failed; recovering complete recording", exc_info=True)
                return self._recover(wav_path)
        joined = join_sections(self._cleaned)
        if self._pipeline.grammar_enabled:
            joined = apply_rules(joined)
            raw = " ".join(text for _, _, text in self._segments)
            if self._pipeline.vocabulary_enabled:
                raw = apply_vocabulary(raw)
            source = apply_rules(raw)
            if not preserves_words(source, joined):
                # Never deliver a section that lost or changed words.
                logger.info("Assembled sections changed wording; restoring source words.")
                joined = repair(source, joined) or source
        return list(self._segments), joined

    def _recover(self, wav_path: Path) -> tuple[list[tuple[float, float, str]], str]:
        segments = self._engine.transcribe_segments(wav_path)
        raw = " ".join(text for _, _, text in segments)
        return segments, capitalize_start(self._pipeline.run(raw, budget_seconds=FINISH_BUDGET_SECONDS, allow_load=False))


def _has_speech(audio, rate: int, begin: float, start: float, end: float) -> bool:
    """Is there voice in [start, end) of a window that begins at `begin`?"""
    if end - start < 0.3:
        return False
    samples = audio.astype(np.float32).reshape(-1)
    frame = max(1, rate // 50)
    usable = len(samples) // frame * frame
    if not usable:
        return False
    energy = np.sqrt((samples[:usable].reshape(-1, frame) ** 2).mean(axis=1))
    first, last = int((start - begin) * 50), int((end - begin) * 50)
    gap = energy[max(0, first):max(0, last)]
    if not len(gap):
        return False
    quiet = np.percentile(energy, 20)
    voiced = gap > max(quiet * 4, 200.0)
    return float(voiced.mean()) > 0.2


# Kept for callers and tests that import the old private name.
_join_sections = join_sections
