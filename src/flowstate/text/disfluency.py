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
        # "Like" and "you know" set off by commas are fillers: "a lot of,
        # like, I'm trying", "say, you know, like, see". Without commas they
        # are usually words ("I like it", "do you know") and stay.
        # Before a quantity or article the commas were only there for the
        # filler: "it took, like, five minutes" -> "it took five minutes".
        part = re.sub(r",\s*(?:(?:like|you know)\s*,\s*)+(?=(?:a|an|the|about|around|\d+|one|two|three|four|five|"
                      r"six|seven|eight|nine|ten|twenty|thirty|fifty|a hundred)\b)", " ", part, flags=re.IGNORECASE)
        part = re.sub(r",\s*(?:(?:like|you know)\s*,\s*)+", ", ", part, flags=re.IGNORECASE)
        part = re.sub(r"(^|[.!?]\s+)(?:(?:like|you know|so yeah)\s*,\s*)+([a-z])",
                      lambda m: m.group(1) + m.group(2).upper(), part, flags=re.IGNORECASE)
        part = re.sub(r",\s*(?:like|you know|so yeah)\s*(?=[.!?]|$)", "", part, flags=re.IGNORECASE)
        # A repeated phrase is a restart: "I'm trying to, trying to say".
        # "again and again and again" is emphasis, so phrases joined by
        # and/or are left alone.
        part = re.sub(r"\b(\w+(?:'\w+)?(?:\s+\w+(?:'\w+)?){1,3}),?\s+\1\b",
                      lambda m: m.group() if re.search(r"\b(?:and|or)\b", m.group(1), re.IGNORECASE) else m.group(1),
                      part, flags=re.IGNORECASE)
        # Don't collapse emphatic negatives, intensifiers, grammatical 'had
        # had'/'that that', or repeated quantities. They can change meaning.
        protected = {"no", "not", "never", "very", "really", "yes", "had", "that"}
        pattern = re.compile(r"\b([A-Za-z]+(?:'[A-Za-z]+)?)(?:[ ,]+\1\b)+", re.IGNORECASE)
        part = pattern.sub(lambda match: match.group() if match.group(1).lower() in protected else match.group(1), part)
        part = re.sub(r"[^\S\n]+([,.!?])", r"\1", part)
        part = re.sub(r",\s*,", ",", part)
        part = re.sub(r"[ \t]{2,}", " ", part)
        return part

    # Quoted text and code are literal data, even if they contain repetitions.
    parts = re.split(r'(`[^`]*`|"[^"\n]*")', text)
    return "".join(part if index % 2 else clean(part) for index, part in enumerate(parts)).strip()
