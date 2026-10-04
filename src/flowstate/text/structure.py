"""Fast, content-preserving layout for explicit dictated email/list cues."""
from __future__ import annotations

import re

_MARKER = re.compile(
    r"(?<!\w)(?:and\s+)?(?:"
    r"(?P<bullet>bullet point|next bullet)\b|"
    r"(?m:^[ \t]*(?P<rendered_bullet>[-*])[ \t]+)|"
    r"(?P<next>next[,\s]+(?:one|item|point)(?:\s+is(?:\s+that)?)?)\b|"
    r"(?P<number>number\s+(?P<number_value>one|two|three|four|five|six|seven|eight|nine|ten|\d+))\b|"
    r"(?P<ordinal>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b"
    r"(?:\s+(?P<item>one|item)(?:\s+is)?)?|"
    r"(?P<digit>\d{1,2})\.(?=\s+\S))[,.:]?\s*",
    re.IGNORECASE,
)

_ORDINALS = {word: index for index, word in enumerate(
    ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"), 1
)}
_NUMBERS = {word: index for index, word in enumerate(
    ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"), 1
)}


def _is_numbered_list(text: str, markers: list[re.Match]) -> bool:
    if len(markers) < 2:
        return False
    prefix = text[:markers[0].start()].strip()
    # Conversational framing is as valid as an explicit 'list of tasks'.
    if prefix.endswith(":") or re.search(r"\b(?:list|tasks|steps|items|things|checks|points)\b", prefix, re.IGNORECASE):
        return True
    if sum(bool(marker.group("number") or marker.group("item")) for marker in markers) >= 2:
        return True
    if all(marker.group("digit") and not text[text.rfind("\n", 0, marker.start()) + 1:marker.start()].strip()
           for marker in markers):
        return True
    values = []
    for marker in markers:
        value = (marker.group("ordinal") or marker.group("number_value") or marker.group("digit")).lower()
        values.append(_ORDINALS.get(value, _NUMBERS.get(value, int(value) if value.isdigit() else 0)))
    ordered = all(right == left + 1 for left, right in zip(values, values[1:]))
    if not ordered:
        return False
    if not prefix and values[0] == 1:
        return True
    # A window may begin halfway through a list, after part of the previous
    # item. Require a coherent sequence and action language, not date ordinals.
    return len(markers) >= 3 and all(re.match(
        r"(?:verify|check|confirm|open|review|test|ensure|update|install|create|add|remove|save|send|fix|deploy)\b",
        text[marker.end():], re.IGNORECASE
    ) for marker in markers)


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
    markers = [marker for marker in _MARKER.finditer(text) if not marker.group("digit")
               or not text[text.rfind("\n", 0, marker.start()) + 1:marker.start()].strip()
               or re.search(r"[.!?:]\s*$", text[:marker.start()])
               or re.match(r"(?:verify|check|confirm|open|review|test|ensure|update|install|create|add|remove|save|send|fix|deploy)\b",
                           text[marker.end():], re.IGNORECASE)]
    transitions = [marker for marker in markers if marker.group("next")]
    conversational = bool(transitions) and len(markers) >= 2 and (
        len(transitions) >= 2 or re.search(r"\b(?:list|findings|issues|tasks|steps|items|things|checks|points)\b",
                                          text[:markers[0].start()], re.IGNORECASE)
    )
    use_bullets = conversational and not any(marker.group("number") or marker.group("digit") for marker in markers) and (
        sum(bool(marker.group("ordinal")) for marker in markers) <= 1
    )
    is_list = bool(markers) and (
        conversational
        or
        all(marker.group("bullet") or marker.group("rendered_bullet") for marker in markers)
        or (not any(marker.group("bullet") or marker.group("rendered_bullet") or marker.group("next") for marker in markers)
            and _is_numbered_list(text, markers))
    )
    if is_list:
        intro = text[:markers[0].start()].strip()
        intro = re.sub(r"\b(of|and|the|a|an|to|from|with|for)\.\s*\n\s*(?=[a-z])", r"\1 ", intro, flags=re.IGNORECASE)
        if intro and intro[-1].isalnum():
            intro += ":"
        items = []
        for index, marker in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            item = text[marker.end():end].strip()
            if not item:
                # Ambiguous layout must never erase an empty marker or content.
                return subject + text
            # Recording-window boundaries are soft wraps, not new list items.
            item = re.sub(r"\s*\n+\s*", " ", item)
            prefix = "- " if marker.group("bullet") or marker.group("rendered_bullet") or use_bullets else f"{index + 1}. "
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
