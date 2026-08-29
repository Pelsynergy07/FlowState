"""Orchestrates the cleanup pipeline: vocabulary pass -> smart formatting."""

from __future__ import annotations

from .formatter import SmartFormatter
from .vocabulary import apply_vocabulary


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

    def run(self, text: str) -> str:
        result = text
        if self.vocabulary_enabled:
            result = apply_vocabulary(result)
        if self.grammar_enabled:
            result = self._formatter.correct(result)
        return result
