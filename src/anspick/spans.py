"""Short free-text answers.

Surface rules:

``marker-span``  the text a marker governs: the content of a boxed group, or the rest of
                 the line after ``####`` or an answer phrase, cut at the first sentence
                 end (". ", "! ", "? ") and stripped of surrounding quotes, emphasis
                 marks and trailing punctuation.
``last-line``    the last non-empty line, when it holds no marker and has at most
                 ``max_words`` words (12 by default), stripped the same way.

The normalised answer is the stripped span; :func:`normalise_span` (lower case, articles
"a", "an", "the" removed, punctuation removed, spaces collapsed) is used for comparing
spans, both for the doubt flag and for scoring.
"""

from __future__ import annotations

import re
import string

from anspick.core import Candidate, Extraction, finish
from anspick.markers import MARKER_ORDER, find_markers, quoted_regions

FORMS: tuple[str, ...] = ("marker-span", "last-line")
RULE_GROUPS: tuple[tuple[str, ...], ...] = (("last-line",),)
_STRIP = " \t\r\n*_`\"'“”‘’.,;:!?"
_SENT_END_RE = re.compile(r"[.!?](?=\s)")
_ARTICLES_RE = re.compile(r"\b(?:a|an|the)\b")
_PUNCT = set(string.punctuation) | {"“", "”", "‘", "’"}


def normalise_span(s: str) -> str:
    """Lower case, drop punctuation and the articles a/an/the, collapse spaces."""
    s = s.lower()
    s = "".join(" " if ch in _PUNCT else ch for ch in s)
    s = _ARTICLES_RE.sub(" ", s)
    return " ".join(s.split())


def _trim(text: str, a: int, b: int) -> tuple[int, int]:
    while a < b and text[a] in _STRIP:
        a += 1
    while b > a and text[b - 1] in _STRIP:
        b -= 1
    return a, b


def candidates(text: str, max_words: int = 12) -> list[Candidate]:
    """Marker spans plus the last short line, with quoted flags."""
    quoted = quoted_regions(text)
    out: list[Candidate] = []
    for mk in find_markers(text):
        a, b = mk.start, mk.end
        if mk.name != "boxed":
            cut = _SENT_END_RE.search(text, a, b)
            if cut:
                b = cut.start()
        a, b = _trim(text, a, b)
        if a < b:
            q = any(x <= mk.at < y for x, y in quoted)
            out.append(Candidate(text[a:b], "marker-span", a, b, text[a:b], mk.name, q))
    lines = list(re.finditer(r"(?m)^.*\S.*$", text))
    if lines:
        m = lines[-1]
        a, b = _trim(text, m.start(), m.end())
        if a < b and len(text[a:b].split()) <= max_words:
            q = any(x <= a < y for x, y in quoted)
            if not any(m.start() <= c.start < m.end() for c in out):
                out.append(Candidate(text[a:b], "last-line", a, b, text[a:b], None, q))
    return sorted(out, key=lambda c: (c.start, c.end))


def extract(text: str, policy: str = "cascade", max_words: int = 12) -> Extraction:
    """Extract a short span from ``text`` under ``policy``."""
    return finish(
        candidates(text, max_words),
        policy,
        MARKER_ORDER,
        RULE_GROUPS,
        lambda c: normalise_span(c.answer),
    )
