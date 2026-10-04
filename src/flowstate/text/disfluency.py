"""Conservative removal of speech hesitations, without rewriting content."""
from __future__ import annotations

import re


def clean_disfluencies(text: str) -> str:
    def clean(part: str) -> str:
        # Repeated discourse phrases are clear false starts. A single 'I mean'
        # between two quantities can be a correction, so retain that case.
        part = re.sub(r"\b(?:i mean[\s,]+){2,}", "", part, flags=re.IGNORECASE)
        part = re.sub(r"\b(?:sort of[\s,]+){2,}(?:like\s+)?", "", part, flags=re.IGNORECASE)
        part = re.sub(r"(?<!\w)(?:um|Um|uh|Uh|erm|Erm)(?!\w)[, ]*", "", part)
        part = re.sub(r"\bbasically\b[, ]*", "", part, flags=re.IGNORECASE)
        # Don't collapse emphatic negatives, intensifiers, grammatical 'had
        # had'/'that that', or repeated quantities. They can change meaning.
        protected = {"no", "not", "never", "very", "really", "yes", "had", "that"}
        pattern = re.compile(r"\b([A-Za-z]+)(?:[ ,]+\1\b)+", re.IGNORECASE)
        part = pattern.sub(lambda match: match.group() if match.group(1).lower() in protected else match.group(1), part)
        part = re.sub(r"[^\S\n]+([,.!?])", r"\1", part)
        part = re.sub(r"[ \t]{2,}", " ", part)
        return part

    # Quoted text and code are literal data, even if they contain repetitions.
    parts = re.split(r'(`[^`]*`|"[^"\n]*")', text)
    return "".join(part if index % 2 else clean(part) for index, part in enumerate(parts)).strip()
