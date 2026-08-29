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
from pathlib import Path

from . import models
from .. import paths
from ..cuda_support import ensure_cuda_dll_search_paths

logger = logging.getLogger("flowstate.asr")


class TranscriptionEngine:
    """Lazy-loaded, self-healing wrapper around faster-whisper.

    device_preference:
      "auto" (default) - use CUDA if available, else fall back to the
                          smaller CPU model so a first transcription on a
                          CPU-only laptop is still fast.
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
        # Set once _load_locked() fails outright (both CUDA and CPU
        # attempts, or a CPU-only load) -- without this, every recording
        # attempt after a failed download independently retries the whole
        # multi-GB download from scratch, so a genuinely broken network
        # turns into a fresh multi-minute stall on every single hotkey
        # press instead of a clear, immediate error after the first one.
        self._load_failure: str | None = None

    @property
    def active_device(self) -> str | None:
        return self._active_device

    @property
    def active_model_id(self) -> str | None:
        return self._active_model_id

    def resolve_target_model(self) -> models.ModelSpec:
        """Which model _load() would pick right now, without loading or
        downloading anything -- lets a caller (onboarding) pre-download
        with real progress before the actual, blocking load happens."""
        want_cuda = self._device_preference == "cuda" or (
            self._device_preference == "auto" and self._probe_cuda()
        )
        if want_cuda:
            model_id = self._requested_model_id
        elif self._device_preference == "auto":
            model_id = models.CPU_FALLBACK_MODEL_ID
        else:
            model_id = self._requested_model_id
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
            if self._load_failure is not None:
                raise RuntimeError(self._load_failure)
            try:
                self._load_locked()
            except Exception as exc:
                self._load_failure = self._describe_load_error(exc)
                raise RuntimeError(self._load_failure) from exc

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
        from faster_whisper import WhisperModel

        ensure_cuda_dll_search_paths()

        want_cuda = self._device_preference == "cuda" or (
            self._device_preference == "auto" and self._probe_cuda()
        )

        if want_cuda:
            spec = models.get_model_spec(self._requested_model_id)
            try:
                candidate = WhisperModel(
                    spec.ct2_repo,
                    device="cuda",
                    compute_type=spec.gpu_compute_type,
                    download_root=str(paths.models_dir() / spec.id),
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
            cpu_model_id = self._requested_model_id
        spec = models.get_model_spec(cpu_model_id)
        self._model = WhisperModel(
            spec.ct2_repo,
            device="cpu",
            compute_type=spec.cpu_compute_type,
            download_root=str(paths.models_dir() / spec.id),
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
        segments, _info = self._model.transcribe(str(wav_path), beam_size=5)
        return [(seg.start, seg.end, seg.text.strip()) for seg in segments if seg.text.strip()]

    def transcribe(self, wav_path: Path) -> str:
        return " ".join(text for _start, _end, text in self.transcribe_segments(wav_path)).strip()
