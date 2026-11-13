"""Answer markers and quoted regions shared by every extractor.

Markers, in priority order:

``boxed``
    The content of ``\\boxed{...}`` or ``\\fbox{...}`` (braces matched, nesting allowed).
``hash``
    The rest of the line after ``####``, the convention of the GSM8K reference solutions.
``answer``
    The rest of the line after a phrase such as "the answer is", "Answer:",
    "final answer:", "the correct option is" or "answer must be".

Quoted regions are parts of the output that repeat the question rather than answer it:
lines starting with ``>``, a "Question:" or "Q:" paragraph (up to a blank line or an
answer marker), and double-quoted passages of five words or more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MARKER_ORDER: tuple[str, ...] = ("boxed", "hash", "answer")

_ANSWER_RE = re.compile(
    r"""
    \b(?:final\s+answer|answer|correct\s+(?:answer|option|choice))\b
    [\s*_]*
    (?:is|:|=|would\s+be|should\s+be|must\s+be|will\s+be)
    (?:\s*(?:is\b|:))?
    [\s*_:]*
    """,
    re.IGNORECASE | re.VERBOSE,
)
_HASH_RE = re.compile(r"####[ \t]*")
_BOXED_RE = re.compile(r"\\(?:boxed|fbox)\s*\{")
_QUESTION_RE = re.compile(r"(?im)^[ \t>*_]*(?:question|q)\s*[:.]")
_BLOCKQUOTE_RE = re.compile(r"(?m)^[ \t]*>.*$")
_DQUOTE_RE = re.compile(r"\"([^\"\n]{1,2000})\"|\u201c([^\u201d\n]{1,2000})\u201d")


@dataclass(frozen=True)
class Marker:
    """A marker found in the text; answers are looked for in ``[start, end)``."""

    name: str
    at: int
    start: int
    end: int


def _line_end(text: str, pos: int) -> int:
    nl = text.find("\n", pos)
    return len(text) if nl < 0 else nl


def match_brace(text: str, open_pos: int) -> int | None:
    """Return the index of the ``}`` closing the ``{`` at ``open_pos``, or None."""
    depth = 0
    for i in range(open_pos, len(text)):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text) and text[i + 1] in "{}":
            continue
        if ch == "{" and (i == 0 or text[i - 1] != "\\"):
            depth += 1
        elif ch == "}" and (i == 0 or text[i - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return i
    return None


def find_markers(text: str) -> list[Marker]:
    """Every answer marker in ``text`` with the region it governs."""
    found: list[Marker] = []
    for m in _BOXED_RE.finditer(text):
        close = match_brace(text, m.end() - 1)
        if close is not None:
            found.append(Marker("boxed", m.start(), m.end(), close))
    for m in _HASH_RE.finditer(text):
        found.append(Marker("hash", m.start(), m.end(), _line_end(text, m.end())))
    for m in _ANSWER_RE.finditer(text):
        found.append(Marker("answer", m.start(), m.end(), _line_end(text, m.end())))
    return sorted(found, key=lambda k: (k.start, MARKER_ORDER.index(k.name)))


def quoted_regions(text: str) -> list[tuple[int, int]]:
    """Spans of ``text`` that repeat the question instead of answering it."""
    regions: list[tuple[int, int]] = []
    for m in _BLOCKQUOTE_RE.finditer(text):
        regions.append((m.start(), m.end()))
    for m in _QUESTION_RE.finditer(text):
        stop = len(text)
        blank = re.search(r"\n[ \t]*\n", text[m.end():])
        if blank:
            stop = m.end() + blank.start()
        ans = _ANSWER_RE.search(text, m.end(), stop)
        if ans:
            stop = ans.start()
        regions.append((m.start(), stop))
    for m in _DQUOTE_RE.finditer(text):
        inner = m.group(1) if m.group(1) is not None else m.group(2)
        if len(inner.split()) >= 5:
            regions.append((m.start(), m.end()))
    return sorted(regions)


def inside(pos: int, regions: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in regions)


def assign_markers(text: str, spans: list[tuple[int, int]]) -> dict[int, str]:
    """Map candidate index to the strongest marker governing it.

    A boxed group marks the candidate inside it when it holds exactly one; ``hash`` and
    ``answer`` mark the first candidate starting in the rest of their line.
    """
    rank = {name: i for i, name in enumerate(MARKER_ORDER)}
    out: dict[int, str] = {}
    for mk in find_markers(text):
        if mk.name == "boxed":
            inner = [i for i, (a, b) in enumerate(spans) if a >= mk.start and b <= mk.end]
            chosen = inner if len(inner) == 1 else []
        else:
            chosen = [i for i, (a, _) in enumerate(spans) if mk.start <= a < mk.end][:1]
        for i in chosen:
            old = out.get(i)
            if old is None or rank[mk.name] < rank[old]:
                out[i] = mk.name
    return out
