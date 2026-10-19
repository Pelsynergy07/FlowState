"""faster-whisper wrapper with lazy loading and a GPU probe.

Portability is the whole point of this module: a machine with no NVIDIA
GPU, an old driver, or missing CUDA DLLs must still transcribe correctly,
just slower. Every failure path below falls back rather than raising.

Lesson learned running this on the dev machine: ctranslate2's CUDA device
probe and WhisperModel's CUDA *construction* can both succeed even when
the actual cuBLAS/cuDNN DLLs are missing -- they load lazily and only blow
up on the first real inference. So the CUDA path below forces one tiny
real transcription inside the try/except, instead of trusting construction
alone, otherwise a missing-DLL machine would crash on the user's first
real recording instead of silently falling back to CPU.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from dataclasses import dataclass

from . import mlx_backend, models, parakeet_backend
from .. import paths
from .. import platform
from ..cuda_support import ensure_cuda_dll_search_paths

logger = logging.getLogger("flowstate.asr")

# Whisper imitates the style of its prompt. Without one, long monologues
# often come back as a single unpunctuated, lowercase run. faster-whisper
# sends `hotwords` with every 30-second window (an initial_prompt only
# reaches the first one when not conditioning on previous text), so
# punctuation and capitalization hold for the whole recording.
PUNCTUATION_PROMPT = "Hello, welcome. Here's my update: it works, and the tests pass. Thanks!"


def _is_valid_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    model_bin = path / "model.bin"
    if not model_bin.is_file() or model_bin.stat().st_size == 0:
        return False
    return True


def _find_model_dir(base_dir: Path) -> Path | None:
    if _is_valid_model_dir(base_dir):
        return base_dir
    if base_dir.is_dir():
        for mb in base_dir.rglob("model.bin"):
            if mb.is_file() and mb.stat().st_size > 0:
                parent = mb.parent
                if (parent / "config.json").is_file():
                    return parent
    return None


def _clean_corrupt_model_dir(path: Path) -> None:
    if path.exists() and not _is_valid_model_dir(path):
        import shutil

        logger.warning("Cleaning corrupted model directory: %s", path)
        try:
            shutil.rmtree(path)
        except Exception:
            logger.warning("Failed to remove corrupt model directory: %s", path, exc_info=True)


def _remove_stale_hub_caches(model_dir: Path) -> None:
    """Earlier versions also left a full huggingface cache copy of the model
    (models--owner--name) inside its folder: ~1.6 GB that is never read once
    the model files sit directly in the folder."""
    import shutil

    for stale in model_dir.glob("models--*"):
        if stale.is_dir():
            logger.info("Removing duplicate model cache: %s", stale)
            shutil.rmtree(stale, ignore_errors=True)


def _ensure_model_dir(spec: models.ModelSpec) -> Path:
    target_dir = paths.models_dir() / spec.id
    found = _find_model_dir(target_dir)
    if found is not None:
        if found == target_dir:
            _remove_stale_hub_caches(target_dir)
        return found
    _clean_corrupt_model_dir(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    from huggingface_hub import snapshot_download

    logger.info("Downloading speech model %s (%s) to %s", spec.id, spec.ct2_repo, target_dir)
    snapshot_download(repo_id=spec.ct2_repo, local_dir=str(target_dir))
    found = _find_model_dir(target_dir)
    if found is None:
        raise RuntimeError(f"Model download completed but model.bin not found in {target_dir}")
    return found


def mlx_model_dir(spec: models.ModelSpec) -> Path:
    return paths.models_dir() / f"{spec.id}-mlx"


def _ensure_mlx_model_dir(spec: models.ModelSpec) -> Path:
    target_dir = mlx_model_dir(spec)
    if mlx_backend.is_valid_model_dir(target_dir):
        return target_dir
    from huggingface_hub import snapshot_download

    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading speech model %s (%s) to %s", spec.id, spec.mlx_repo, target_dir)
    snapshot_download(repo_id=spec.mlx_repo, local_dir=str(target_dir), allow_patterns=mlx_backend.WEIGHT_PATTERNS)
    if not mlx_backend.is_valid_model_dir(target_dir):
        raise RuntimeError(f"Model download completed but no MLX weights were found in {target_dir}")
    return target_dir


def parakeet_model_dir(spec: models.ModelSpec) -> Path:
    return paths.models_dir() / f"{spec.id}-coreml"


@dataclass(frozen=True)
class DownloadPlan:
    """Where a speech model lives and how to fetch it, for onboarding's
    progress-tracked download."""

    kind: str  # "ct2" (faster-whisper), "mlx" or "parakeet"
    folder: Path
    repo: str
    approx_mb: int
    patterns: list[str] | None = None
    revision: str | None = None

    def is_ready(self) -> bool:
        if self.kind == "parakeet":
            return parakeet_backend.is_valid_model_dir(self.folder)
        if self.kind == "mlx":
            return mlx_backend.is_valid_model_dir(self.folder)
        return _find_model_dir(self.folder) is not None

    def download(self) -> None:
        from huggingface_hub import snapshot_download

        self.folder.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading speech model %s to %s", self.repo, self.folder)
        snapshot_download(repo_id=self.repo, local_dir=str(self.folder), revision=self.revision,
                          allow_patterns=self.patterns)
        if not self.is_ready():
            raise RuntimeError(f"Model download completed but the model files are incomplete in {self.folder}")


class TranscriptionEngine:
    """Lazy-loaded, self-healing speech recognizer.

    Windows/Linux: faster-whisper (CTranslate2) on CUDA or the CPU.
    Apple silicon: Parakeet v2 on the Neural Engine (the default), or
    Whisper through MLX; both fall back to faster-whisper on the CPU.

    device_preference:
      "auto" (default) - use CUDA (Windows) or the Apple silicon route if
                          available, else fall back to the smaller CPU
                          model so a first transcription on a CPU-only
                          laptop is still fast.
      "cuda"            - force CUDA; if it fails to load, fall back to
                           CPU with the originally requested model.
      "cpu"             - force CPU with the originally requested model.
    """

    def __init__(self, model_id: str = models.DEFAULT_MODEL_ID, device_preference: str = "auto"):
        self._requested_model_id = model_id
        self._device_preference = device_preference
        self._model = None
        self._active_model_id: str | None = None
        self._active_device: str | None = None
        # Guards _load(): the background warmup thread and a user hitting
        # the hotkey immediately at launch can both call transcribe() ->
        # _load() at nearly the same time.
        self._load_lock = threading.Lock()
        # Cooldown-based load failure: if loading fails, remember the error
        # for a cooldown period so rapid hotkey presses fail fast without
        # hammering the network/disk, but allow retrying after the cooldown.
        self._load_failure: str | None = None
        self._last_failure_time: float = 0.0
        self._failure_cooldown_seconds: float = 300.0  # 5-minute cooldown

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def close(self) -> None:
        """Releases the model; stops the Parakeet helper process if running."""
        model, self._model = self._model, None
        close = getattr(model, "close", None)
        if close is not None:
            close()

    @property
    def active_device(self) -> str | None:
        return self._active_device

    @property
    def active_model_id(self) -> str | None:
        return self._active_model_id

    def _apple_route(self) -> tuple[models.ModelSpec, str] | None:
        """(model, "parakeet" | "mlx") on Apple silicon, None elsewhere or when
        the user forced the CPU."""
        if not platform.is_apple_silicon() or self._device_preference == "cpu":
            return None
        spec = models.get_model_spec(self._requested_model_id)
        if spec.engine == "parakeet":
            if parakeet_backend.is_available():
                return spec, "parakeet"
            spec = models.get_model_spec(models.APPLE_SILICON_FALLBACK_MODEL_ID)
        if spec.mlx_repo and mlx_backend.is_available():
            return spec, "mlx"
        return None

    def uses_mlx(self) -> bool:
        route = self._apple_route()
        return route is not None and route[1] == "mlx"

    def _requested_whisper_id(self) -> str:
        """The requested model for the faster-whisper path: Parakeet only runs
        on Apple silicon, so a Parakeet choice becomes Whisper turbo here."""
        spec = models.get_model_spec(self._requested_model_id)
        return models.DEFAULT_MODEL_ID if spec.engine != "whisper" else spec.id

    def model_download_plan(self, cuda_available: bool | None = None) -> DownloadPlan:
        """Where the model _load() would use lives, so onboarding can
        download it with progress before the blocking load."""
        route = self._apple_route()
        if route is not None:
            spec, kind = route
            if kind == "parakeet":
                return DownloadPlan("parakeet", parakeet_model_dir(spec), parakeet_backend.REPO,
                                    spec.approx_size_mb, parakeet_backend.WEIGHT_PATTERNS, parakeet_backend.REVISION)
            return DownloadPlan("mlx", mlx_model_dir(spec), spec.mlx_repo, spec.mlx_size_mb or spec.approx_size_mb,
                                mlx_backend.WEIGHT_PATTERNS)
        spec = self.resolve_target_model(cuda_available=cuda_available)
        return DownloadPlan("ct2", paths.models_dir() / spec.id, spec.ct2_repo, spec.approx_size_mb)

    def is_target_downloaded(self, cuda_available: bool | None = None) -> bool:
        return self.model_download_plan(cuda_available=cuda_available).is_ready()

    def resolve_target_model(self, cuda_available: bool | None = None) -> models.ModelSpec:
        """Which model _load() would pick right now, without loading or
        downloading anything -- lets a caller (onboarding) pre-download
        with real progress before the actual, blocking load happens.
        cuda_available skips the (slow to import) CUDA probe when known."""
        route = self._apple_route()
        if route is not None:
            return route[0]
        if cuda_available is None and self._device_preference == "auto":
            cuda_available = self._probe_cuda()
        want_cuda = self._device_preference == "cuda" or (
            self._device_preference == "auto" and cuda_available
        )
        if want_cuda:
            model_id = self._requested_whisper_id()
        elif self._device_preference == "auto":
            model_id = models.CPU_FALLBACK_MODEL_ID
        else:
            model_id = self._requested_whisper_id()
        return models.get_model_spec(model_id)

    def _probe_cuda(self) -> bool:
        if self._device_preference == "cpu":
            return False
        try:
            import ctranslate2

            return ctranslate2.get_cuda_device_count() > 0
        except Exception:
            logger.info("CUDA probe failed; will use CPU", exc_info=True)
            return False

    @staticmethod
    def _verify_model_runs(model) -> None:
        """Forces one tiny real transcription so any lazily-loaded CUDA
        library failure happens now, inside the caller's try/except,
        instead of surfacing later during the user's real recording."""
        import numpy as np

        silence = np.zeros(1600, dtype=np.float32)  # 0.1s at 16kHz
        segments, _info = model.transcribe(silence, beam_size=1)
        list(segments)

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:  # another thread won the race
                return
            now = time.time()
            if self._load_failure is not None:
                if now - self._last_failure_time < self._failure_cooldown_seconds:
                    raise RuntimeError(self._load_failure)
                # Cooldown expired: allow retrying
                self._load_failure = None
            try:
                self._load_locked()
                self._load_failure = None
            except Exception as exc:
                self._last_failure_time = time.time()
                self._load_failure = self._describe_load_error(exc)
                raise RuntimeError(self._load_failure) from exc

    def clear_load_failure(self) -> None:
        """Allow an immediate retry (a user clicking Try Again) despite the cooldown."""
        self._load_failure = None

    @staticmethod
    def _describe_load_error(exc: Exception) -> str:
        """A short, human-readable explanation instead of a raw stack
        trace string -- this is what ends up in the "Something went
        wrong" dialog the user actually sees."""
        signature = f"{type(exc).__name__} {exc}"
        network_markers = (
            "ConnectionError",
            "Timeout",
            "TimeoutError",
            "Max retries exceeded",
            "NewConnectionError",
            "getaddrinfo failed",
            "NameResolutionError",
            "ConnectTimeout",
        )
        if any(marker in signature for marker in network_markers):
            return (
                "Could not download the speech model -- check your internet connection, "
                "then restart FlowState to try again."
            )
        return f"Could not load the speech model ({type(exc).__name__}: {exc}). Restart FlowState to try again."

    def _load_locked(self) -> None:
        route = self._apple_route()
        if route is not None and route[1] == "parakeet":
            spec = route[0]
            try:
                plan = self.model_download_plan()
                if not plan.is_ready():
                    plan.download()
                candidate = parakeet_backend.ParakeetModel(plan.folder)
                self._verify_model_runs(candidate)
                self._model = candidate
                self._active_model_id = spec.id
                self._active_device = "neural-engine"
                logger.info("ASR: loaded %s on the Apple Neural Engine", spec.id)
                return
            except Exception:
                logger.warning("ASR: Parakeet failed, falling back to Whisper on MLX", exc_info=True)
                route = (models.get_model_spec(models.APPLE_SILICON_FALLBACK_MODEL_ID), "mlx")
        if route is not None and route[1] == "mlx" and mlx_backend.is_available():
            spec = route[0]
            try:
                candidate = mlx_backend.MlxWhisperModel(_ensure_mlx_model_dir(spec))
                self._verify_model_runs(candidate)
                self._model = candidate
                self._active_model_id = spec.id
                self._active_device = "mlx"
                logger.info("ASR: loaded %s on Apple silicon (MLX)", spec.id)
                return
            except Exception:
                logger.warning("ASR: MLX failed for %s, falling back to CPU", spec.id, exc_info=True)

        from faster_whisper import WhisperModel

        ensure_cuda_dll_search_paths()

        want_cuda = self._device_preference == "cuda" or (
            self._device_preference == "auto" and self._probe_cuda()
        )

        if want_cuda:
            spec = models.get_model_spec(self._requested_whisper_id())
            try:
                model_dir = _ensure_model_dir(spec)
                candidate = WhisperModel(
                    str(model_dir),
                    device="cuda",
                    compute_type=spec.gpu_compute_type,
                )
                self._verify_model_runs(candidate)
                self._model = candidate
                self._active_model_id = spec.id
                self._active_device = "cuda"
                logger.info("ASR: loaded %s on CUDA", spec.id)
                return
            except Exception:
                logger.warning(
                    "ASR: failed to load/run %s on CUDA, falling back to CPU",
                    spec.id,
                    exc_info=True,
                )

        # CPU path. "auto" swaps down to the small CPU-friendly model so a
        # GPU-less machine still gets a fast first transcription; an
        # explicit "cuda" or "cpu" preference keeps the requested model.
        if self._device_preference == "auto":
            cpu_model_id = models.CPU_FALLBACK_MODEL_ID
        else:
            cpu_model_id = self._requested_whisper_id()
        spec = models.get_model_spec(cpu_model_id)
        model_dir = _ensure_model_dir(spec)
        self._model = WhisperModel(
            str(model_dir),
            device="cpu",
            compute_type=spec.cpu_compute_type,
        )
        self._active_model_id = spec.id
        self._active_device = "cpu"
        logger.info("ASR: loaded %s on CPU", spec.id)

    def transcribe_segments(self, wav_path: Path) -> list[tuple[float, float, str]]:
        """Like transcribe(), but keeps each segment's (start, end) time in
        seconds from the top of the recording -- needed to line up a
        mid-recording screenshot capture with the words being said around
        it."""
        if self._model is None:
            self._load()
        # Conditioning on previous text lets one hallucinated phrase feed the
        # next window; on trailing silence that produced runaway invented text.
        segments, _info = self._model.transcribe(str(wav_path), beam_size=5, hotwords=PUNCTUATION_PROMPT,
                                                 condition_on_previous_text=False)
        return [(seg.start, seg.end, seg.text.strip()) for seg in segments if seg.text.strip()]

    def transcribe(self, wav_path: Path) -> str:
        return " ".join(text for _start, _end, text in self.transcribe_segments(wav_path)).strip()

    def transcribe_words(self, wav_path: Path, context: str | None = None,
                         prompt: bool = True) -> list[tuple[float, float, str]]:
        """Word timings let overlapping live windows retain boundary words.

        context: the transcript just before this audio. Prompting with the
        real preceding words keeps punctuation and casing continuous across
        windows. prompt=False transcribes with no prompt at all, which never
        makes Whisper skip the start of the audio; it is used to re-check a
        short stretch whose words a prompted pass left out.
        """
        if self._model is None:
            self._load()
        options = {"hotwords": PUNCTUATION_PROMPT, "initial_prompt": context} if prompt else {}
        segments, _info = self._model.transcribe(
            str(wav_path), beam_size=5, word_timestamps=True,
            condition_on_previous_text=False, **options,
        )
        words = []
        for segment in segments:
            if segment.text.strip() and not segment.words:
                raise RuntimeError("Speech was recognized without word timing; recovering full recording")
            words.extend((word.start, word.end, word.word.strip()) for word in (segment.words or []) if word.word.strip())
        return words
