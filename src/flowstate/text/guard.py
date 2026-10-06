"""Accept a model's punctuation and layout while keeping the speaker's words.

The formatter model is asked to only punctuate, fix spelling and lay text
out, but small models still paraphrase: "thanks regards" becomes
"Regards", "works" becomes "work", a clause disappears. Rejecting the
whole output for one such edit is what made FlowState paste raw blobs, so
instead the model's output is aligned word-by-word with its input and
every edit is classified:

- allowed: case changes, obvious spelling fixes, joined/split compounds,
  number words to digits, removing fillers, stutters, false starts and
  spoken layout commands ("number two", "new line") at a line break.
- anything else (synonyms, tense or grammar changes, added or dropped
  words) is reverted to the source words in place, keeping the model's
  layout around it.

If the model rewrote too much to repair cleanly, None is returned and the
caller keeps the rule-formatted source.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
# List markers and generated numbering are layout, not dictated words.
_LAYOUT = re.compile(r"(?m)^[ \t]*(?:\d{1,3}[.)]|[-*•])[ \t]+")

# Only words that carry no content when dropped. "just", "well", "kind of"
# change meaning, so a model dropping them is reverted.
_FILLERS = {"um", "umm", "uh", "uhh", "uhm", "erm", "er", "ah", "eh", "hmm", "mm", "mhm",
            "like", "basically", "so", "yeah"}
_FILLER_PHRASES = [("you", "know"), ("i", "mean"), ("so", "yeah")]
_SPOKEN_PUNCTUATION = {"comma", "period", "full", "stop", "question", "exclamation", "mark", "point",
                       "colon", "semicolon", "dash", "hyphen"}
_CUE_CORE = {"number", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
             "ninth", "tenth", "firstly", "secondly", "thirdly", "lastly", "finally", "next", "item",
             "point", "points", "bullet", "last", "new", "line", "paragraph", "step"}
_CUE_EXTRA = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
              "is", "that", "the", "and", "also", "then", "a", "of", "thing", "things", "here", "are"}
_NUMBERS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if i > 1}
_INFLECTIONS = ("", "s", "es", "ed", "d", "ing", "er", "ly", "n't")
# Text before a position that starts a sentence: start of text or line
# (after any list marker), or sentence punctuation.
_SENTENCE_END = re.compile(r"(?:\A|\n)[ \t]*(?:(?:\d{1,3}[.)]|[-*•])[ \t]+)?\Z|[.!?:][\"')\]]*\s*\Z")


def tokens(text: str) -> list[re.Match]:
    layout = [m for m in _LAYOUT.finditer(text)]
    # "60. All tests passed" is a dictated number unless the text really is
    # a numbered list (two or more numbered lines).
    if sum(m.group().strip()[:1].isdigit() for m in layout) < 2:
        layout = [m for m in layout if not m.group().strip()[:1].isdigit()]
    layout = [m.span() for m in layout]
    return [m for m in _WORD.finditer(text) if not any(a <= m.start() < b for a, b in layout)]


def _norm(word: str) -> str:
    return word.casefold().replace("’", "'")


def _number_value(words: list[str]) -> int | None:
    total = 0
    for word in words:
        if word in _NUMBERS and total % 10 == 0:
            total += _NUMBERS[word]
        elif word in _TENS and total == 0:
            total += _TENS[word]
        else:
            return None
    return total if words else None


def _is_inflection(a: str, b: str) -> bool:
    short, long = sorted((a, b), key=len)
    return any(long == short + suffix or long == short[:-1] + suffix or long == short + short[-1] + suffix
               for suffix in _INFLECTIONS if suffix) or (a.rstrip("s") == b.rstrip("s"))


def _equivalent(src: list[str], out: list[str]) -> bool:
    """Same dictated words, spelled or segmented differently."""
    squash = lambda words: re.sub(r"['’\-]", "", "".join(words))
    if squash(src) == squash(out):
        return True
    if len(out) == 1 and out[0].isdigit() and _number_value(src) == int(out[0]):
        return True
    if len(src) == 1 and src[0].isdigit() and _number_value(out) == int(src[0]):
        return True
    if len(src) == len(out) == 1:
        a, b = src[0], out[0]
        if min(len(a), len(b)) >= 4 and not _is_inflection(a, b) and not (a.isdigit() or b.isdigit()):
            return SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.8
    return False


def _deletable(src: list[str], i: int, j: int, gap: str, src_gap: str = " ") -> bool:
    """May source words i..j be dropped, given the output gap they fell into?

    src_gap is the source text between the span and the next source word.
    """
    span = src[i:j]
    rest = src[j:]
    core, k = [], 0
    while k < len(span):
        phrase = next((p for p in _FILLER_PHRASES if tuple(span[k:k + len(p)]) == p), None)
        if phrase:
            k += len(phrase)
        elif span[k] in _FILLERS:
            k += 1
        else:
            core.append(span[k])
            k += 1
    if not core:
        return True
    size = len(core)
    # Stutters and repeated phrases: "I I", "and the and the".
    if core == rest[:size] or core == src[max(0, i - size):i]:
        return True
    # A false start the speaker immediately restarts: "if I only if I do".
    # Never across a sentence end: that would be a dropped sentence.
    if size <= 3 and rest and core[0] == rest[0] and not re.search(r"[.!?\n]", src_gap):
        return True
    if all(word in _SPOKEN_PUNCTUATION for word in span) and re.search(r"[,.;:!?\-–—]", gap):
        return True
    if "\n" not in gap:
        return False
    # A joining "and"/"then" before the next list item: "..., and send the invoice".
    if _LAYOUT.match(gap.rsplit("\n", 1)[-1] + "x") and all(w in {"and", "also", "then"} for w in span):
        return True
    # Spoken list/paragraph commands vanish where the output starts a new line.
    return any(w in _CUE_CORE for w in span) and all(
        w in _CUE_CORE or w in _CUE_EXTRA or w in _FILLERS for w in span)


def _ops(source: str, output: str):
    src, out = tokens(source), tokens(output)
    a, b = [_norm(m.group()) for m in src], [_norm(m.group()) for m in out]
    return src, out, a, b, SequenceMatcher(None, a, b, autojunk=False).get_opcodes()


def _gap(output: str, out: list[re.Match], k: int) -> str:
    start = out[k - 1].end() if k > 0 else 0
    end = out[k].start() if k < len(out) else len(output)
    # The start of the output is a line start too.
    return ("\n" if k == 0 else "") + output[start:end]


def _classify(source: str, output: str):
    src, out, a, b, opcodes = _ops(source, output)
    def src_gap(i: int) -> str:
        return source[src[i - 1].end():src[i].start()] if 0 < i < len(src) else " "

    quoted = [m.span() for m in re.finditer(r'`[^`]*`|"[^"\n]*"|“[^”\n]*”', source)]

    verdicts = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            ok = True
        elif tag == "delete":
            ok = _deletable(a, i1, i2, _gap(output, out, j1), src_gap(i2))
        elif tag == "insert":
            ok = False
        else:
            ok = _equivalent(a[i1:i2], b[j1:j2])
            if not ok:
                # A deletion and a spelling fix side by side: "um gsap" -> "GSAP".
                for cut in range(1, i2 - i1):
                    if (_deletable(a, i1, i1 + cut, _gap(output, out, j1), src_gap(i1 + cut))
                            and _equivalent(a[i1 + cut:i2], b[j1:j2])):
                        ok = True
                        break
        if ok and tag != "equal" and i2 > i1 and any(
                start <= src[i].start() < end for i in range(i1, i2) for start, end in quoted):
            ok = False  # Quoted text and code are literal, stutters included.
        verdicts.append((tag, i1, i2, j1, j2, ok))
    return src, out, a, verdicts


def preserves_words(source: str, output: str) -> bool:
    """True when every word difference is an allowed formatting edit."""
    if not output.strip():
        return not tokens(source)
    return all(ok for *_, ok in _classify(source, output)[3])


def _starts_sentence(text: str, pos: int) -> bool:
    return bool(_SENTENCE_END.search(text[:pos]))


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def repair(source: str, output: str, min_kept: float = 0.7) -> str | None:
    """Revert every disallowed word edit in output to the source words.

    Returns None when too little of the source survived for the layout to
    be trustworthy (a summary or an answer rather than a formatting pass).
    """
    if not output.strip():
        return None
    src, out, a, verdicts = _classify(source, output)
    if not src:
        return output.strip()
    kept = sum(i2 - i1 for tag, i1, i2, j1, j2, ok in verdicts if ok and tag != "insert")
    if kept < len(src) * min_kept or len(out) > len(src) * 1.5 + 5:
        return None
    for tag, i1, i2, j1, j2, ok in verdicts:
        # A rewrite across a line break means the model's lines no longer
        # hold the words they would after restoring them: words would shift
        # between list items or paragraphs. Keep the source layout instead.
        if not ok and j2 > j1 and "\n" in output[out[j1].start():out[j2 - 1].end()]:
            return None
        if not ok and i2 > i1 and "\n" in source[src[i1].start():src[i2 - 1].end()]:
            return None
        # Line breaks already in the input (dictated or rule-made list items,
        # greeting and sign-off lines) are kept; a model merging them back
        # into prose is undoing correct layout.
        if tag == "equal":
            for i in range(i1 + 1, i2):
                if "\n" in source[src[i - 1].end():src[i].start()] and \
                        "\n" not in output[out[j1 + i - i1 - 1].end():out[j1 + i - i1].start()]:
                    return None
    text = output
    for tag, i1, i2, j1, j2, ok in reversed(verdicts):
        if ok:
            continue
        original = source[src[i1].start():src[i2 - 1].end()] if i2 > i1 else ""
        if original and j1 == j2:
            # A restored sentence keeps its own closing punctuation.
            original += re.match(r"[.!?,;:]*", source[src[i2 - 1].end():]).group()
        if j2 > j1:
            start, end = out[j1].start(), out[j2 - 1].end()
            if not original:
                # Drop the invented words with the separator that introduced
                # them (", please?" -> "?"); at a sentence or line start, with
                # the spaces after them instead.
                before = text[out[j1 - 1].end():start] if j1 > 0 else "\n"
                if j1 > 0 and not re.search(r"[.!?:\n]", before):
                    start = out[j1 - 1].end()
                elif j2 < len(out):
                    end += len(re.match(r"[^\S\n]*", text[end:]).group())
        elif j1 < len(out):
            start = end = out[j1].start()
            original += " "
        else:
            start = end = out[-1].end() if out else len(text)
            original = " " + original
        at_start = _starts_sentence(text, start)
        if original.strip():
            if at_start and not original[:1].isspace():
                original = _cap(original)
        text = text[:start] + original + text[end:]
        follow = start + len(original)
        nxt = re.match(r"[^\S\n]*([^\W_])", text[follow:])
        if nxt:
            p = follow + nxt.start(1)
            if not original.strip() and at_start:
                # The sentence now begins with the following word.
                text = text[:p] + text[p].upper() + text[p + 1:]
            elif original.strip() and j2 < len(out) and i2 < len(src) and not _starts_sentence(text, p) \
                    and src[i2].group()[:1].islower() and out[j2].group() != "I":
                # A word the model capitalized as a sentence start now continues one.
                text = text[:p] + text[p].lower() + text[p + 1:]
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    text = re.sub(r"[^\S\n]+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:])\s*([.!?])", r"\2", text)
    text = re.sub(r"(?m)^[^\S\n]+(?=\S)(?![-*•\d])", "", text).strip()
    return text if preserves_words(source, text) else None


def salvage_prefix(source: str, partial: str) -> str | None:
    """Use a generation cut off by the deadline for the part it covered.

    The partial output is trimmed to its last complete sentence or line,
    repaired against the matching source prefix, and the untouched source
    remainder is appended.
    """
    cut = max(partial.rfind(ch) for ch in (".", "!", "?", "\n"))
    if cut <= 0:
        return None
    head = partial[:cut + 1].rstrip()
    src = tokens(source)
    out = tokens(head)
    if len(out) < 3:
        return None
    blocks = SequenceMatcher(None, [_norm(m.group()) for m in src], [_norm(m.group()) for m in out],
                             autojunk=False).get_matching_blocks()
    blocks = [block for block in blocks if block.size]
    if not blocks or blocks[-1].b + blocks[-1].size != len(out):
        return None
    covered = blocks[-1].a + blocks[-1].size
    split = src[covered - 1].end()
    fixed = repair(source[:split], head)
    if fixed is None:
        return None
    remainder = source[split:].lstrip(" ,.;:!?")
    if not remainder.strip():
        return fixed
    if re.search(r"[.!?:]\s*$", fixed) or fixed.endswith("\n"):
        remainder = _cap(remainder)
    separator = "\n" if re.match(r"(?:[-*•]|\d+\.)\s", remainder) else " "
    return fixed + separator + remainder
