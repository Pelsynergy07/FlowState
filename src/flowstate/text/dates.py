"""Format explicit month/day dates without guessing a year or numeric locale."""
from __future__ import annotations

import re

_MONTHS = "January February March April May June July August September October November December".split()
_ORDINALS = "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split()
_ORDINALS += ["twenty " + word for word in _ORDINALS[:9]] + ["thirtieth", "thirty first"]
_DAYS = {word: index for index, word in enumerate(_ORDINALS, 1)}
_DAY = r"(?:\d{1,2}(?:st|nd|rd|th)?|" + "|".join(re.escape(word).replace(r"\ ", r"\s+") for word in sorted(_DAYS, key=len, reverse=True)) + r")\b"
_DATE = re.compile(r"\b(?P<month>" + "|".join(_MONTHS) + r")\s+(?P<day>" + _DAY + r")"
                   r"(?:\s*(?:to|through|[–-])\s*(?P<end>" + _DAY + r"))?"
                   r"(?:,?\s+(?P<year>[12]\d{3})\b)?", re.IGNORECASE)


def format_dates(text: str) -> str:
    def day(value: str) -> int:
        value = " ".join(value.lower().split())
        return _DAYS[value] if value in _DAYS else int(re.sub(r"(?:st|nd|rd|th)$", "", value))

    def replace(match: re.Match) -> str:
        first = day(match.group("day"))
        last = day(match.group("end")) if match.group("end") else None
        if not 1 <= first <= 31 or (last is not None and not first <= last <= 31):
            return match.group()
        result = match.group("month").capitalize() + " " + str(first)
        if last is not None:
            result += "–" + str(last)
        if match.group("year"):
            result += ", " + match.group("year")
        return result

    return _DATE.sub(replace, text)
