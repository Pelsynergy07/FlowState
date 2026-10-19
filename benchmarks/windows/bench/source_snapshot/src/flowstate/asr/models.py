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


MODELS: dict[str, ModelSpec] = {
    "large-v3-turbo": ModelSpec(
        id="large-v3-turbo",
        display_name="Whisper large-v3-turbo (recommended)",
        ct2_repo="deepdml/faster-whisper-large-v3-turbo-ct2",
        approx_size_mb=1600,
        gpu_compute_type="float16",
        cpu_compute_type="int8",
    ),
    "base.en": ModelSpec(
        id="base.en",
        display_name="Whisper base.en (CPU fallback)",
        ct2_repo="Systran/faster-whisper-base.en",
        approx_size_mb=150,
        gpu_compute_type="float16",
        cpu_compute_type="int8",
    ),
}

DEFAULT_MODEL_ID = "large-v3-turbo"
CPU_FALLBACK_MODEL_ID = "base.en"


def get_model_spec(model_id: str) -> ModelSpec:
    try:
        return MODELS[model_id]
    except KeyError as exc:
        raise ValueError(f"Unknown ASR model id: {model_id!r}") from exc
