from unittest.mock import patch

import pytest

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


def test_load_failure_is_remembered_not_retried(monkeypatch):
    """Regression test for a real bug: a failed download used to be
    silently retried from scratch on every single subsequent recording
    attempt, so a genuinely broken network turned into a fresh
    multi-minute stall every time the user pressed the hotkey instead of
    an immediate, clear error after the first failure."""
    engine = TranscriptionEngine(model_id=DEFAULT_MODEL_ID, device_preference="cpu")
    attempts = []

    def failing_load_locked():
        attempts.append(1)
        raise ConnectionError("Max retries exceeded with url: /models/foo (Caused by NewConnectionError)")

    monkeypatch.setattr(engine, "_load_locked", failing_load_locked)

    with pytest.raises(RuntimeError, match="internet connection"):
        engine._load()
    assert len(attempts) == 1

    # A second attempt must not touch the network again.
    with pytest.raises(RuntimeError, match="internet connection"):
        engine._load()
    assert len(attempts) == 1


def test_non_network_load_failure_gets_a_distinct_message(monkeypatch):
    engine = TranscriptionEngine(model_id=DEFAULT_MODEL_ID, device_preference="cpu")

    def failing_load_locked():
        raise ValueError("corrupt model file")

    monkeypatch.setattr(engine, "_load_locked", failing_load_locked)

    with pytest.raises(RuntimeError, match="corrupt model file"):
        engine._load()
