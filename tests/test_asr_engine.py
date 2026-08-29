from unittest.mock import patch

from flowstate.asr.engine import TranscriptionEngine
from flowstate.asr.models import CPU_FALLBACK_MODEL_ID, DEFAULT_MODEL_ID


def test_resolve_target_model_auto_with_cuda_picks_requested_model():
    engine = TranscriptionEngine(model_id=DEFAULT_MODEL_ID, device_preference="auto")
    with patch.object(engine, "_probe_cuda", return_value=True):
        assert engine.resolve_target_model().id == DEFAULT_MODEL_ID


def test_resolve_target_model_auto_without_cuda_picks_cpu_fallback():
    engine = TranscriptionEngine(model_id=DEFAULT_MODEL_ID, device_preference="auto")
    with patch.object(engine, "_probe_cuda", return_value=False):
        assert engine.resolve_target_model().id == CPU_FALLBACK_MODEL_ID


def test_resolve_target_model_explicit_cuda_ignores_probe():
    engine = TranscriptionEngine(model_id=DEFAULT_MODEL_ID, device_preference="cuda")
    with patch.object(engine, "_probe_cuda", return_value=False):
        assert engine.resolve_target_model().id == DEFAULT_MODEL_ID


def test_resolve_target_model_explicit_cpu_keeps_requested_model():
    """Matches _load_locked()'s real behavior: only "auto" downgrades to
    the small CPU-friendly model. An explicit "cpu" preference keeps
    whatever model was requested, even though it'll be slow -- the user
    asked for it specifically."""
    engine = TranscriptionEngine(model_id=DEFAULT_MODEL_ID, device_preference="cpu")
    assert engine.resolve_target_model().id == DEFAULT_MODEL_ID
