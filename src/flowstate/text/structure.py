"""Fast, content-preserving layout for explicit dictated email/list cues."""
from __future__ import annotations

import re

_MARKER = re.compile(
    r"\b(?:(?P<bullet>bullet point|next bullet)|(?P<number>number\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)|"
    r"(?:first|second|third|fourth|fifth)(?:\s+(?:one|item)(?:\s+is)?)?))\b[,:]?\s*",
    re.IGNORECASE,
)


def structure_text(text: str) -> str:
    """Layout changes only: every piece of content is kept in source order."""
    if not text.strip():
        return text
    subject = ""
    subject_match = re.match(
        r"^\s*subject(?:\s+line)?(?:\s+is)?[: ]+(.+?)(?=\s+(?:dear|hi|hello|hey)\s+)",
        text, flags=re.IGNORECASE,
    )
    if subject_match:
        subject = "Subject: " + subject_match.group(1).strip() + "\n\n"
        text = text[subject_match.end():].strip()
    text = re.sub(r"\bnew paragraph\b[,.]?\s*", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"\bnew line\b[,.]?\s*", "\n", text, flags=re.IGNORECASE)
    markers = list(_MARKER.finditer(text))
    def family(marker):
        if marker.group("bullet"):
            return "bullet"
        return "number" if marker.group("number").lower().startswith("number ") else "ordinal"
    is_list = len(markers) >= 2 and len({family(marker) for marker in markers}) == 1
    if is_list and family(markers[0]) == "ordinal":
        prefix = text[:markers[0].start()].strip()
        is_list = not prefix or prefix.endswith(":") or bool(re.search(r"\b(?:list|tasks|steps|items)\b", prefix, re.IGNORECASE))
    if is_list:
        intro = text[:markers[0].start()].strip()
        items = []
        for index, marker in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            item = text[marker.end():end].strip()
            if not item:
                # Ambiguous layout must never erase an empty marker or content.
                return subject + text
            prefix = "- " if marker.group("bullet") else f"{index + 1}. "
            items.append(prefix + item)
        text = (intro + "\n\n" if intro else "") + "\n".join(items)
    else:
        # Numbering may restart in independently polished chunks.
        count = 0
        def renumber(match):
            nonlocal count
            count += 1
            return f"{count}. "
        if len(re.findall(r"(?m)^\s*\d+\.\s+", text)) >= 2:
            text = re.sub(r"(?m)^\s*\d+\.\s+", renumber, text)

    greeting = re.match(
        r"^\s*((?:dear|hi|hello|hey)\s+[^\n,.!?]{1,40}?)(?:[,!]+\s*|\s+(?=(?:i|we|please|could|can|hope)\b))",
        text, flags=re.IGNORECASE,
    )
    if greeting:
        head = greeting.group(1).strip()
        body = text[greeting.end():].strip()
        if body:
            head = head[0].upper() + head[1:]
            text = head + ",\n\n" + body
            closing = re.search(
                r"\b(thanks|thank you|best regards|kind regards|regards|sincerely|best wishes)[,.!]?"
                r"(?:\s+((?!(?:for|to|that|again)\b)[\w'-]+(?:\s+[\w'-]+){0,2}))?[.!]?\s*$",
                body, flags=re.IGNORECASE,
            )
            if closing:
                content = body[:closing.start()].rstrip()
                signoff = closing.group(1)
                signoff = signoff[0].upper() + signoff[1:]
                signature = closing.group(2)
                text = head + ",\n\n" + content + "\n\n" + signoff + ("\n" + signature if signature else "")
    return subject + text.strip()
