"""Yes/no and true/false answers.

Surface rules:

``yes-no``      the words ``yes`` and ``no`` (any case, whole words). ``no`` counts only
                where it cannot be a determiner: at the start of a line or sentence, or
                followed by punctuation or the end of the text ("No, ..." and "... is
                no." count; "there is no reason" does not).
``true-false``  the words ``true`` and ``false`` (any case, whole words).

Answers are normalised to ``yes``, ``no``, ``true`` and ``false``; for the doubt flag and
for scoring, ``true`` is the same answer as ``yes`` and ``false`` the same as ``no``. Both
rules form one cascade group, so the unmarked cascade takes the last word found.
"""

from __future__ import annotations

import re

from anspick.core import Candidate, Extraction, finish
from anspick.markers import MARKER_ORDER, assign_markers, find_markers, quoted_regions

FORMS: tuple[str, ...] = ("yes-no", "true-false")
RULE_GROUPS: tuple[tuple[str, ...], ...] = (FORMS,)
POSITIVE = {"yes": True, "true": True, "no": False, "false": False}

_WORD_RE = re.compile(r"(?<![\w'’-])(yes|no|true|false)(?![\w'’-])", re.IGNORECASE)
_SENTENCE_START_RE = re.compile(r"(?:^|[.!?:;\n]|\*\*)[\s*_\"'(]*$")


def polarity(answer: str) -> bool | None:
    """True for yes/true, False for no/false, None for anything else."""
    return POSITIVE.get(answer.strip().lower())


def candidates(text: str) -> list[Candidate]:
    """Every yes/no/true/false word in ``text`` with marker and quoted flags."""
    region_starts = {mk.start for mk in find_markers(text)}
    raw: list[Candidate] = []
    for m in _WORD_RE.finditer(text):
        word = m.group(1).lower()
        if word == "no":
            after = text[m.end() :]
            starts = bool(_SENTENCE_START_RE.search(text[: m.start()]))
            ends = after == "" or bool(re.match(r"[ \t]*(?:[.,!?;:)\]*]|$)", after, re.M))
            if not (starts or ends or m.start() in region_starts):
                continue
        rule = "yes-no" if word in ("yes", "no") else "true-false"
        raw.append(Candidate(word, rule, m.start(), m.end(), m.group(0)))
    quoted = quoted_regions(text)
    marks = assign_markers(text, [(c.start, c.end) for c in raw])
    return [
        Candidate(
            c.answer,
            c.rule,
            c.start,
            c.end,
            c.raw,
            marks.get(i),
            any(a <= c.start < b for a, b in quoted),
        )
        for i, c in enumerate(raw)
    ]


def extract(text: str, policy: str = "cascade") -> Extraction:
    """Extract a yes/no or true/false answer from ``text`` under ``policy``."""
    return finish(candidates(text), policy, MARKER_ORDER, RULE_GROUPS, lambda c: polarity(c.answer))
