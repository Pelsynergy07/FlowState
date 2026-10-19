"""Registry of ASR models FlowState knows how to download and run.

Kept as plain data (no ctranslate2/torch imports here) so it can be
imported cheaply by the onboarding UI to show download sizes before any
heavy library is touched.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    display_name: str
    ct2_repo: str  # faster-whisper / CTranslate2 model repo on Hugging Face
    approx_size_mb: int
    gpu_compute_type: str  # compute_type passed to WhisperModel when on CUDA
    cpu_compute_type: str  # compute_type passed to WhisperModel when on CPU
    mlx_repo: str | None = None  # the same model converted for MLX (Apple silicon)
    mlx_size_mb: int = 0
    engine: str = "whisper"  # "whisper" (faster-whisper / MLX) or "parakeet" (CoreML helper, macOS)
    english_only: bool = False


MODELS: dict[str, ModelSpec] = {
    "large-v3-turbo": ModelSpec(
        id="large-v3-turbo",
        display_name="Whisper large-v3-turbo (recommended)",
        ct2_repo="deepdml/faster-whisper-large-v3-turbo-ct2",
        approx_size_mb=1600,
        gpu_compute_type="float16",
        cpu_compute_type="int8",
        mlx_repo="mlx-community/whisper-large-v3-turbo",
        mlx_size_mb=1540,
    ),
    "base.en": ModelSpec(
        id="base.en",
        display_name="Whisper base.en (CPU fallback)",
        ct2_repo="Systran/faster-whisper-base.en",
        approx_size_mb=150,
        gpu_compute_type="float16",
        cpu_compute_type="int8",
        mlx_repo="mlx-community/whisper-base.en-mlx",
        mlx_size_mb=140,
    ),
}

MODELS["parakeet-v2"] = ModelSpec(
    id="parakeet-v2",
    display_name="NVIDIA Parakeet v2 (English, Apple Neural Engine)",
    ct2_repo="",  # not a Whisper model: see asr/parakeet_backend.py
    approx_size_mb=460,
    gpu_compute_type="",
    cpu_compute_type="",
    engine="parakeet",
    english_only=True,
)

DEFAULT_MODEL_ID = "large-v3-turbo"
CPU_FALLBACK_MODEL_ID = "base.en"
# Picked by FlowState's model benchmark for Apple silicon: Whisper-turbo
# accuracy on English at a third of the size, ~0.1 s per live window.
APPLE_SILICON_MODEL_ID = "parakeet-v2"
# Used on Apple silicon when the Parakeet helper can't run, or for languages
# other than English.
APPLE_SILICON_FALLBACK_MODEL_ID = "large-v3-turbo"


def default_model_id() -> str:
    """The speech model a fresh install uses on this computer."""
    import platform as stdlib_platform
    import sys

    if sys.platform == "darwin" and stdlib_platform.machine() == "arm64":
        return APPLE_SILICON_MODEL_ID
    return DEFAULT_MODEL_ID


def get_model_spec(model_id: str) -> ModelSpec:
    try:
        return MODELS[model_id]
    except KeyError as exc:
        raise ValueError(f"Unknown ASR model id: {model_id!r}") from exc
