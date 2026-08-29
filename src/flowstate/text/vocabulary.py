"""Deterministic developer-vocabulary casing/acronym pass.

Runs first in the cleanup pipeline, before the grammar model, and is pure
rule-based -- zero model download, runs in milliseconds. It only fixes
known words/phrases (github -> GitHub); it never touches sentence-level
capitalization or punctuation, which is the grammar model's job.
"""

from __future__ import annotations

import json
import re
from importlib.resources import files

from .. import paths

_cache: dict[str, object] = {"user_mtime": None, "merged": None}


def _load_default_vocab() -> dict[str, str]:
    data = files("flowstate.resources").joinpath("vocabulary_default.json").read_text(encoding="utf-8")
    return json.loads(data)


def _load_user_vocab() -> dict[str, str]:
    path = paths.vocabulary_user_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _current_user_mtime() -> float | None:
    path = paths.vocabulary_user_path()
    return path.stat().st_mtime if path.exists() else None


def get_merged_vocabulary(force_reload: bool = False) -> dict[str, str]:
    """Default vocabulary merged with user overrides. The user file is
    only re-read when its modification time has changed, so this is cheap
    to call on every transcription."""
    mtime = _current_user_mtime()
    if not force_reload and _cache["merged"] is not None and _cache["user_mtime"] == mtime:
        return _cache["merged"]  # type: ignore[return-value]

    merged = _load_default_vocab()
    merged.update(_load_user_vocab())
    _cache["merged"] = merged
    _cache["user_mtime"] = mtime
    return merged


def _build_pattern(vocab: dict[str, str]) -> re.Pattern:
    # Longest phrase first, so "ci cd" matches before a bare "ci" or "cd".
    phrases = sorted(vocab.keys(), key=len, reverse=True)
    escaped = [re.escape(p).replace(r"\ ", r"\s+") for p in phrases if p]
    if not escaped:
        return re.compile(r"(?!)")  # matches nothing
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", flags=re.IGNORECASE)


def apply_vocabulary(text: str, vocab: dict[str, str] | None = None) -> str:
    if not text:
        return text
    vocab = vocab if vocab is not None else get_merged_vocabulary()
    if not vocab:
        return text

    lookup = {k.lower(): v for k, v in vocab.items()}
    pattern = _build_pattern(vocab)

    def _replace(match: re.Match) -> str:
        normalized = re.sub(r"\s+", " ", match.group(0)).lower()
        return lookup.get(normalized, match.group(0))

    return pattern.sub(_replace, text)
