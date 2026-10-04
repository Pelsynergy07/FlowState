"""Orchestrates the cleanup pipeline: vocabulary pass -> smart formatting."""

from __future__ import annotations

from .formatter import SmartFormatter
from .vocabulary import apply_vocabulary
from .structure import structure_text
from .disfluency import clean_disfluencies
from .dates import format_dates


class CleanupPipeline:
    def __init__(
        self,
        formatter: SmartFormatter | None = None,
        vocabulary_enabled: bool = True,
        grammar_enabled: bool = True,
    ):
        self._formatter = formatter or SmartFormatter()
        self.vocabulary_enabled = vocabulary_enabled
        self.grammar_enabled = grammar_enabled

    def preload(self) -> bool:
        return self._formatter.preload()

    def run(self, text: str, *, budget_seconds: float | None = None, allow_load: bool = True, cancel_event=None) -> str:
        result = text
        if self.vocabulary_enabled:
            result = apply_vocabulary(result)
        if self.grammar_enabled:
            result = format_dates(clean_disfluencies(result))
            # Explicit email/list/paragraph cues must work even if inference
            # is cancelled or reaches its deadline. Normalize them before
            # preservation checks so intended layout isn't treated as lost text.
            result = structure_text(result)
            result = self._formatter.correct(result, budget_seconds=budget_seconds, allow_load=allow_load, cancel_event=cancel_event)
            result = structure_text(format_dates(clean_disfluencies(result)))
        return result
