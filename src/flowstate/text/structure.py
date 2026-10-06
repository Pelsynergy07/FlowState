"""Fast, content-preserving layout for explicit dictated email/list cues."""
from __future__ import annotations

import re

_MARKER = re.compile(
    r"(?<!\w)(?:and\s+)?(?:"
    r"(?P<bullet>bullet point|next bullet)\b|"
    r"(?m:^[ \t]*(?P<rendered_bullet>[-*])[ \t]+)|"
    r"(?P<next>next[,\s]+(?:one|item|point)(?:\s+is(?:\s+that)?)?)\b|"
    r"(?P<number>number\s+(?P<number_value>one|two|three|four|five|six|seven|eight|nine|ten|\d+))\b"
    r"(?:,?\s+is\b(?:\s+that\b|(?!\s+(?:it|there|this|he|she)\b)))?|"
    # "first is water bottle", "second one is pencil", "third, is that ...":
    # the spoken "is" belongs to the cue, not the item. A question such as
    # "first, is it working?" keeps its "is".
    r"(?P<ordinal>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b"
    r"(?:\s+(?P<item>one|item))?"
    r"(?:,?\s+is\b(?:\s+that\b|(?!\s+(?:it|there|this|he|she)\b)))?|"
    r"(?P<digit>\d{1,2})\.(?=\s+\S))[,.:]?\s*",
    re.IGNORECASE,
)

_ORDINALS = {word: index for index, word in enumerate(
    ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"), 1
)}
_NUMBERS = {word: index for index, word in enumerate(
    ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"), 1
)}


def _marker_value(marker: re.Match) -> int | None:
    """1 for "first"/"number one"/"1.", 2 for "second", ...; None for bullets."""
    value = (marker.group("ordinal") or marker.group("number_value") or marker.group("digit") or "").lower()
    if not value:
        return None
    return _ORDINALS.get(value, _NUMBERS.get(value, int(value) if value.isdigit() else None))


_NOT_A_CUE_BEFORE = re.compile(
    r"\b(?:the|a|an|my|our|your|his|her|their|its|this|of|january|february|march|april|may|june|july|"
    r"august|september|october|november|december)\s+$", re.IGNORECASE)


def _adjectival_ordinal(text: str, marker: re.Match) -> bool:
    """"May first", "the first meeting", "my second try": not list cues."""
    return bool(marker.group("ordinal")) and bool(_NOT_A_CUE_BEFORE.search(text[:marker.start()]))


def _capitalize_item(item: str) -> str:
    """List items start with a capital, unless the word has its own casing (iPhone)."""
    first = item.split(" ", 1)[0]
    return item[:1].upper() + item[1:] if first.islower() else item


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
    # "first ... second ... third ..." spoken in order is an enumeration even
    # without a "here are the things" lead-in. (Dates and "the first X" are
    # filtered out earlier, see _adjectival_ordinal.)
    if len(markers) >= 3 and values[0] == 1:
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
    # A dictation may contain several independent documents. Apply layout to
    # each section rather than letting a preceding list consume an email, or
    # requiring the greeting to be the first words of the entire recording.
    # Keep the framing words: they are content, not commands to execute.
    section_cues = re.compile(
        r"(?:\bI (?:wanted|want|would like) to (?:write|send) (?:this|an?) email\b|"
        r"\b(?:dear|hi|hello|hey)\s+[\w'-]+(?:\s+[\w'-]+)?[,!]?\s+"
        r"(?=(?:hope|please|I|we|could|can)\b)|"
        r"(?:shopping|grocery|packing) list\b)", re.IGNORECASE,
    )
    boundaries = []
    for match in section_cues.finditer(text):
        prefix = text[:match.start()]
        if not prefix.strip():
            continue
        # Keep an explicitly dictated subject with its greeting; the email
        # formatter below needs both to recognize the Subject line.
        if (re.match(r"^\s*subject(?:\s+line)?(?:\s+is)?[: ]+", prefix, re.IGNORECASE)
                and not re.search(r"\b(?:dear|hi|hello|hey)\s+", prefix, re.IGNORECASE)):
            continue
        boundaries.append(match.start())
    if boundaries:
        starts = [0, *boundaries, len(text)]
        return "\n\n".join(structure_text(text[start:end].strip())
                            for start, end in zip(starts, starts[1:])
                            if text[start:end].strip())

    # An explicitly named inventory is a list even without spoken markers.
    # Limit this to short comma-delimited entries; ordinary prose and quoted
    # values containing commas must not become arbitrary bullets.
    inventory = re.match(
        r"^((?:shopping|grocery|packing) list(?:\s+(?:to buy|to pack|of|is))?)\s*[:,]?\s+(.+)$",
        text, re.IGNORECASE | re.DOTALL,
    )
    if inventory and not re.search(r"[\n\"“”]", inventory.group(2)):
        entries = [entry.strip() for entry in inventory.group(2).split(",")]
        if len(entries) >= 2 and all(entry and len(entry.split()) <= 6 for entry in entries):
            entries[-1] = re.sub(r"^and\s+", "", entries[-1], flags=re.IGNORECASE)
            return inventory.group(1).strip() + ":\n\n" + "\n".join("- " + _capitalize_item(entry) for entry in entries)
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
    markers = [marker for marker in _MARKER.finditer(text) if not _adjectival_ordinal(text, marker)]
    markers = [marker for marker in markers if not marker.group("digit")
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
        # "first ... second ... third ..." then later "first ... second ...":
        # a second list. Split before it, at the last sentence break, so its
        # introduction isn't swallowed by the previous list's last item.
        values = [_marker_value(marker) for marker in markers]
        restart = next((k for k in range(1, len(markers))
                        if values[k] == 1 and any(value and value > 1 for value in values[:k])), None)
        if restart is not None:
            gap_start, gap_end = markers[restart - 1].end(), markers[restart].start()
            breaks = list(re.finditer(r"[.!?][\"')]*\s+", text[gap_start:gap_end]))
            split = gap_start + breaks[-1].end() if breaks else gap_end
            return subject + structure_text(text[:split].strip()) + "\n\n" + structure_text(text[split:].strip())
        intro = text[:markers[0].start()].strip()
        intro = re.sub(r"\b(of|and|the|a|an|to|from|with|for)\.\s*\n\s*(?=[a-z])", r"\1 ", intro, flags=re.IGNORECASE)
        if intro and intro[-1].isalnum():
            intro += ":"
        items = []
        outro = ""
        for index, marker in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            item = text[marker.end():end].strip()
            if index + 1 == len(markers) and "\n\n" in item:
                # A paragraph after the last item is not part of the list.
                item, outro = (part.strip() for part in item.split("\n\n", 1))
            if not item:
                # Ambiguous layout must never erase an empty marker or content.
                return subject + text
            # Recording-window boundaries are soft wraps, not new list items.
            item = re.sub(r"\s*\n+\s*", " ", item)
            # The comma that separated spoken items isn't part of the item.
            item = re.sub(r"[,;]\s*$", "", item)
            prefix = "- " if marker.group("bullet") or marker.group("rendered_bullet") or use_bullets else f"{index + 1}. "
            items.append(prefix + _capitalize_item(item))
        text = (intro + "\n\n" if intro else "") + "\n".join(items) + ("\n\n" + outro if outro else "")
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
            body = body[0].upper() + body[1:]
            # Common dictated pleasantry followed by the actual message.
            # Add punctuation and a paragraph without rewriting any words.
            body = re.sub(
                r"^(Hope\s+[^\n.!?]{1,80}?\b(?:well|great|good|okay|ok))[.!]?\s+(?=(?:please|I|we)\b)",
                lambda match: match.group(1) + ".\n\n", body, flags=re.IGNORECASE,
            )
            body = re.sub(r"(?<=\n\n)[a-z]", lambda match: match.group().upper(), body)
            text = head + ",\n\n" + body
            closing = re.search(
                r"\b(thanks(?:\s+regards)?|thank you|best regards|kind regards|regards|sincerely|best wishes)[,.!]?"
                r"(?:\s+((?!(?:for|to|that|again)\b)[\w'-]+(?:\s+[\w'-]+){0,2}))?[.!]?\s*$",
                body, flags=re.IGNORECASE,
            )
            # A closing already on its own line was laid out by the model.
            if closing and not re.search(r"\n[^\S\n]*$", body[:closing.start()]):
                content = body[:closing.start()].rstrip()
                signoff = closing.group(1)
                signoff = signoff[0].upper() + signoff[1:]
                if signoff.casefold() == "thanks regards":
                    signoff = "Thanks\nRegards"
                signature = closing.group(2)
                text = head + ",\n\n" + content + "\n\n" + signoff + (
                    ",\n" + signature if signature else "")
    return subject + text.strip()
