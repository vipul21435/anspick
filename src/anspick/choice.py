"""Multiple-choice answers.

The answer is an option label (``A``, ``B``, ...). Labels come from the option list (one
letter per option, in order) or are given directly; with neither, ``A`` to ``D`` are
assumed. Surface rules, from strongest to weakest:

``bracketed``    ``(B)``, ``[B]``, or ``B)`` / ``B.`` / ``B:`` where the letter
                 starts a line or follows an answer marker.
``option-word``  ``option B``, ``choice B``, ``option 2`` / ``choice 2`` (numbers are
                 1-based and must name an existing option).
``option-text``  the text of an option restated (case and spacing ignored, whole words
                 only, at least two characters). When one option's text contains
                 another's, the longer match wins.
``bare``         a lone capital label letter. ``A`` and ``I`` double as English words, so
                 a bare ``A`` or ``I`` followed by a lowercase word is not a candidate
                 unless it directly follows an answer marker.

Overlapping matches keep the stronger rule. A restated option list (consecutive lines
``A) ...``, ``B) ...`` starting at the first label, two or more lines) counts as quoted,
as do the regions described in :mod:`anspick.markers`. The unmarked cascade tries
``bracketed`` and ``option-word`` first, then ``option-text``, then ``bare``, taking the
last occurrence in the first group that has one.
"""

from __future__ import annotations

import re
import string
from collections.abc import Sequence

from anspick.core import Candidate, Extraction, drop_overlaps, finish
from anspick.markers import MARKER_ORDER, assign_markers, find_markers, quoted_regions

FORMS: tuple[str, ...] = ("bracketed", "option-word", "option-text", "bare")
RULE_GROUPS: tuple[tuple[str, ...], ...] = (
    ("bracketed", "option-word"),
    ("option-text",),
    ("bare",),
)
DEFAULT_LABELS = "ABCD"


def labels_for(
    options: Sequence[str] | None = None, labels: str | Sequence[str] | None = None
) -> list[str]:
    """The label letters in play."""
    if labels:
        out = [str(x).strip().upper() for x in labels]
    elif options:
        if len(options) > 26:
            raise ValueError("at most 26 options are supported")
        out = list(string.ascii_uppercase[: len(options)])
    else:
        out = list(DEFAULT_LABELS)
    if any(len(x) != 1 or x not in string.ascii_uppercase for x in out):
        raise ValueError(f"labels must be single letters, got {out!r}")
    return out


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _listing_regions(text: str, labels: list[str]) -> list[tuple[int, int]]:
    """Restated option lists: consecutive labelled lines starting at the first label."""
    line_re = re.compile(r"(?m)^[ \t*-]*\(?([A-Z])[).:][ \t]+\S.*$")
    lines = list(line_re.finditer(text))
    regions: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if lines[i].group(1) != labels[0]:
            i += 1
            continue
        j = i
        while (
            j + 1 < len(lines)
            and j + 1 - i < len(labels)
            and lines[j + 1].group(1) == labels[j + 1 - i]
            and text[lines[j].end() : lines[j + 1].start()].strip() == ""
        ):
            j += 1
        if j > i:
            regions.append((lines[i].start(), lines[j].end()))
        i = j + 1
    return regions


def _raw_candidates(
    text: str, labels: list[str], options: Sequence[str] | None
) -> list[Candidate]:
    cls = "".join(labels)
    out: list[Candidate] = []
    region_starts = {mk.start for mk in find_markers(text) if mk.name != "boxed"}

    for m in re.finditer(rf"[(\[]\s*([{cls}])\s*[)\]]", text):
        out.append(Candidate(m.group(1), "bracketed", m.start(), m.end(), m.group(0)))
    for m in re.finditer(rf"(?<![\w(\[{{])([{cls}])[).:](?!\w)", text):
        before = text[: m.start()]
        line_start = before.rstrip(" \t*_") == "" or before.rstrip(" \t*_").endswith("\n")
        if line_start or m.start() in region_starts:
            out.append(Candidate(m.group(1), "bracketed", m.start(), m.end(), m.group(0)))
    word_re = re.compile(rf"\b(?:option|choice)\s+(?:([{cls}])\b|(\d+)\b)", re.IGNORECASE)
    for m in word_re.finditer(text):
        if m.group(1):
            if not m.group(1).isupper():
                continue
            label = m.group(1)
        else:
            k = int(m.group(2))
            if not 1 <= k <= len(labels):
                continue
            label = labels[k - 1]
        out.append(Candidate(label, "option-word", m.start(), m.end(), m.group(0)))
    if options:
        for label, opt in zip(labels, options, strict=False):
            key = _norm_ws(str(opt))
            if len(key) < 2:
                continue
            pat = r"\s+".join(re.escape(w) for w in key.split(" "))
            for m in re.finditer(rf"(?<!\w){pat}(?!\w)", text, re.IGNORECASE):
                out.append(Candidate(label, "option-text", m.start(), m.end(), m.group(0)))
    for m in re.finditer(rf"(?<![\w'’-])([{cls}])(?![\w'’-])", text):
        letter = m.group(1)
        if (
            letter in "AI"
            and m.start() not in region_starts
            and re.match(r"\s+[a-z]", text[m.end() :])
        ):
            continue
        out.append(Candidate(letter, "bare", m.start(), m.end(), letter))
    return out


def candidates(
    text: str,
    options: Sequence[str] | None = None,
    labels: str | Sequence[str] | None = None,
) -> list[Candidate]:
    """Every option candidate in ``text`` with marker and quoted flags set."""
    labs = labels_for(options, labels)
    raw = drop_overlaps(_raw_candidates(text, labs, options), lambda c: FORMS.index(c.rule))
    quoted = quoted_regions(text) + _listing_regions(text, labs)
    marks = assign_markers(text, [(c.start, c.end) for c in raw])
    out = []
    for i, c in enumerate(raw):
        q = any(a <= c.start < b for a, b in quoted)
        out.append(Candidate(c.answer, c.rule, c.start, c.end, c.raw, marks.get(i), q))
    return out


def extract(
    text: str,
    policy: str = "cascade",
    options: Sequence[str] | None = None,
    labels: str | Sequence[str] | None = None,
) -> Extraction:
    """Extract an option label from ``text`` under ``policy``."""
    cands = candidates(text, options, labels)
    return finish(cands, policy, MARKER_ORDER, RULE_GROUPS, lambda c: c.answer)
