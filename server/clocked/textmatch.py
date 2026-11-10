"""Text matching for match_text and conflict_text (PRODUCT.md, "Signals per collectible").

A pattern is a set of alternatives separated by "|". An alternative is one or
more terms joined by "+", and every term must be found. Matching ignores case,
punctuation and spacing, but only matches whole words: a term matches when it
equals one word, or several consecutive words run together. Lines of read text
are taken in order, so a phrase split over two lines still matches. So "E II R",
"EIIR" and "E.II.R" all match EIIR, and GR does not match GRADE or G VI R.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable


def _words(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text).upper()
    return re.sub(r"[^0-9A-Z]+", " ", decomposed).split()


def _squash(term: str) -> str:
    return "".join(_words(term))


def _term_in_words(term: str, words: list[str]) -> bool:
    for start in range(len(words)):
        joined = ""
        for word in words[start:]:
            joined += word
            if joined == term:
                return True
            if len(joined) >= len(term):
                break
    return False


def matches(pattern: str, lines: Iterable[str]) -> bool:
    """True if any alternative in the pattern is fully present in the lines."""
    words = [word for line in lines for word in _words(line)]
    for alternative in pattern.split("|"):
        terms = [_squash(term) for term in alternative.split("+")]
        terms = [term for term in terms if term]
        if terms and all(_term_in_words(term, words) for term in terms):
            return True
    return False
