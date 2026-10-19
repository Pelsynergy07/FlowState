# Adapted from FlowState streaming.py (MIT). Source hash is recorded by environment.json.
# The benchmark replaces capture/thread scheduling, retains the full seam/gap/guard algorithm.
import logging,re,time,wave,threading
from pathlib import Path
import numpy as np
from flowstate.text.formatter import capitalize_start,join_sections,needs_polish
from flowstate.text.guard import preserves_words,repair
from flowstate.text.pipeline import apply_rules
from flowstate.text.vocabulary import apply_vocabulary
logger=logging.getLogger(__name__)


STEP_SECONDS = 10.0

OVERLAP_SECONDS = 6.0

LOOKAHEAD_SECONDS = 4.0

LIVE_BUDGET_SECONDS = 8.0

FINISH_BUDGET_SECONDS = 4.0

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

class WindowProcessor:
    def __init__(self,engine,pipeline,folder):
        self._engine=engine;self._pipeline=pipeline;self._folder=folder
        self._stop=threading.Event();self._cursor=0.;self._segments=[];self._cleaned=[];self._words=[];self._pending=[];self._clean_cut=True


    def _window_begin(self) -> float:
            # After a cut at a sentence end or pause the next window starts right
            # there: no word straddles it, so no overlap needs aligning. A cut
            # mid-speech overlaps the previous window for acoustic context.
            return self._cursor if self._clean_cut else max(0.0, self._cursor - OVERLAP_SECONDS)

    def _process(self, audio, rate: int, begin: float, cutoff: float, *, budget: float, final: bool = False,
                     deadline: float | None = None) -> None:
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
                    # Among equally long pauses, the latest: longer sections, fewer seams.
                    longest = max(late, key=lambda k: (round(pause(k), 2), k), default=None)
                    cut = ends[-1] if ends else (longest if longest is not None and pause(longest) >= 0.25 else None)
                    if cut is not None:
                        owned = owned[:cut + 1]
                        # owned is a time-ordered prefix of candidates.
                        cutoff = (owned[-1][1] + candidates[len(owned)][0]) / 2
                    self._clean_cut = cut is not None
                self._pending = [word for word in candidates if _mid(word) >= cutoff] if not final else []
                raw = " ".join(text for _, _, text in owned)
                if raw:
                    polish = None  # automatic: only where punctuation is missing
                    if deadline is not None:
                        # After stop the user is waiting: transcription already
                        # used part of the time. Rules always run; the model only
                        # if Whisper's punctuation is missing (it mostly copies
                        # punctuated speech, and a busy GPU can make it slow).
                        budget = max(0.3, deadline - time.monotonic())
                        polish = needs_polish(raw)
                    cleaned = self._pipeline.run(raw, budget_seconds=budget, allow_load=False,
                                                 cancel_event=None if final else _StopDeadline(self._stop),
                                                 polish=polish)
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

    def _recover(self, wav_path: Path) -> tuple[list[tuple[float, float, str]], str]:
            segments = self._engine.transcribe_segments(wav_path)
            raw = " ".join(text for _, _, text in segments)
            return segments, capitalize_start(self._pipeline.run(raw, budget_seconds=FINISH_BUDGET_SECONDS, allow_load=False,
                                                                 polish=needs_polish(raw)))
