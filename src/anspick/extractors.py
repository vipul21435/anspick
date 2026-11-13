"""Named extractors that can be compared on the same outputs.

An extractor spec is one of:

``cascade``, ``first``, ``last``, ``marker``
    The built-in extractor for the record's answer type under that policy.
``field:NAME``
    An answer already stored in the record under ``NAME`` (for example one written by
    another scorer), normalised the way a reference answer is.
``re:first:PATTERN`` / ``re:last:PATTERN``
    A regular expression applied to the output; the first or last match is taken, its
    first non-empty group (or the whole match) is read as an answer of the record's type.

Each extractor returns an :class:`Answer`: the answer, the rule that produced it and its
span when known.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from anspick import choice, spans, yesno
from anspick.core import POLICIES
from anspick.equiv import norm_number
from anspick.records import Record, extract_record


@dataclass(frozen=True)
class Answer:
    answer: str | None
    rule: str | None
    span: tuple[int, int] | None = None
    doubt: tuple[str, ...] = ()


def _read_as(text: str, rec: Record) -> str | None:
    if rec.type == "number":
        return norm_number(text)
    if rec.type == "choice":
        return choice.extract(text, options=rec.options, labels=rec.labels).answer
    if rec.type == "yesno":
        return yesno.extract(text).answer
    return spans.extract(text).answer if "\n" in text else text.strip() or None


@dataclass(frozen=True)
class Extractor:
    """One named way of getting an answer from a record."""

    spec: str

    def __post_init__(self) -> None:
        s = self.spec
        if s in POLICIES:
            return
        if s.startswith("field:") and len(s) > 6:
            return
        if s.startswith(("re:first:", "re:last:")):
            pattern = s.split(":", 2)[2]
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"bad pattern in extractor {s!r}: {e}") from None
            return
        raise ValueError(
            f"unknown extractor {s!r}; use a policy ({', '.join(POLICIES)}), "
            "field:NAME, re:first:PATTERN or re:last:PATTERN"
        )

    def run(self, rec: Record) -> Answer:
        s = self.spec
        if s in POLICIES:
            ex = extract_record(rec, s)
            return Answer(ex.answer, ex.rule, ex.span, ex.doubt)
        if s.startswith("field:"):
            name = s[6:]
            value: Any = rec.extra.get(name)
            if isinstance(value, list):
                value = value[0] if value else None
            if value is None:
                return Answer(None, None)
            text = value if isinstance(value, str) else str(value)
            if rec.type == "number" and not isinstance(value, str):
                got = norm_number(value)
            else:
                got = _read_as(text, rec)
            return Answer(got, "field" if got is not None else None)
        _, which, pattern = s.split(":", 2)
        matches = list(re.finditer(pattern, rec.output))
        if not matches:
            return Answer(None, None)
        m = matches[0] if which == "first" else matches[-1]
        groups = [i for i in range(1, (m.re.groups or 0) + 1) if m.group(i)]
        gi = groups[0] if groups else 0
        got = _read_as(m.group(gi), rec)
        return Answer(got, "regex" if got is not None else None, (m.start(gi), m.end(gi)))
