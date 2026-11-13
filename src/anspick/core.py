"""Candidates, extraction results, selection policies and the doubt flag.

Every extractor scans the text and returns a list of :class:`Candidate` objects. A
candidate carries the normalised answer, the surface rule that matched it, its character
span, the answer marker it sits behind (if any) and whether it lies inside a quoted
question or a restated option list. A policy then picks one candidate:

``cascade``
    The documented rule cascade. Quoted candidates are ignored. If any candidate sits
    behind an answer marker, the marker with the highest priority wins and its last
    occurrence is taken. Otherwise the unmarked rule groups are tried in priority order
    and the last occurrence in the first non-empty group is taken.
``first``
    The first candidate in text order, of any rule, quoted or not (a naive scorer).
``last``
    The last candidate in text order, of any rule, quoted or not.
``marker``
    Only candidates behind an answer marker, chosen as in ``cascade``; no answer if the
    output holds no marker.

The doubt flag does not depend on the policy. It looks at the unquoted marked
candidates if there are any, otherwise at every unquoted candidate, and reports
``several-candidates`` when they hold more than one distinct answer, ``no-candidate``
when nothing was found at all and ``only-quoted`` when every candidate lies inside a
quoted question or restated options.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field
from typing import Any

POLICIES: tuple[str, ...] = ("cascade", "first", "last", "marker")

DOUBT_SEVERAL = "several-candidates"
DOUBT_NONE = "no-candidate"
DOUBT_QUOTED = "only-quoted"


@dataclass(frozen=True)
class Candidate:
    """One possible answer found in an output."""

    answer: str
    rule: str
    start: int
    end: int
    raw: str
    marker: str | None = None
    quoted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "rule": self.rule,
            "span": [self.start, self.end],
            "raw": self.raw,
            "marker": self.marker,
            "quoted": self.quoted,
        }


@dataclass(frozen=True)
class Extraction:
    """The answer a policy picked, with the rule that fired and the reasons for doubt.

    ``rule`` is the cascade step that fired: the marker name for a marked candidate,
    otherwise the surface rule. ``form`` is always the surface rule.
    """

    answer: str | None
    rule: str | None
    form: str | None
    span: tuple[int, int] | None
    policy: str
    doubt: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = field(default=(), repr=False)

    @property
    def doubtful(self) -> bool:
        return bool(self.doubt)

    def to_dict(self, with_candidates: bool = False) -> dict[str, Any]:
        out: dict[str, Any] = {
            "answer": self.answer,
            "rule": self.rule,
            "form": self.form,
            "span": list(self.span) if self.span is not None else None,
            "policy": self.policy,
            "doubt": list(self.doubt),
        }
        if with_candidates:
            out["candidates"] = [c.to_dict() for c in self.candidates]
        return out


def drop_overlaps(
    cands: Sequence[Candidate], priority: Callable[[Candidate], int]
) -> list[Candidate]:
    """Keep non-overlapping candidates, preferring lower ``priority`` then longer spans."""
    ranked = sorted(cands, key=lambda c: (priority(c), -(c.end - c.start), c.start))
    kept: list[Candidate] = []
    for c in ranked:
        if all(c.end <= k.start or c.start >= k.end for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: (c.start, c.end))


def choose(
    cands: Sequence[Candidate],
    policy: str,
    marker_order: Sequence[str],
    rule_groups: Sequence[Sequence[str]],
) -> Candidate | None:
    """Pick one candidate under ``policy`` (see the module docstring)."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; expected one of {', '.join(POLICIES)}")
    if not cands:
        return None
    if policy == "first":
        return min(cands, key=lambda c: (c.start, c.end))
    if policy == "last":
        return max(cands, key=lambda c: (c.start, c.end))
    open_ = [c for c in cands if not c.quoted]
    marked = [c for c in open_ if c.marker is not None]
    if marked:
        rank = {m: i for i, m in enumerate(marker_order)}
        best = min(rank.get(c.marker or "", len(rank)) for c in marked)
        pool = [c for c in marked if rank.get(c.marker or "", len(rank)) == best]
        return max(pool, key=lambda c: (c.start, c.end))
    if policy == "marker":
        return None
    for group in rule_groups:
        pool = [c for c in open_ if c.rule in group]
        if pool:
            return max(pool, key=lambda c: (c.start, c.end))
    return None


def doubt_reasons(
    cands: Sequence[Candidate], key: Callable[[Candidate], Hashable]
) -> tuple[str, ...]:
    """Policy-independent reasons to distrust the extraction of one output."""
    if not cands:
        return (DOUBT_NONE,)
    open_ = [c for c in cands if not c.quoted]
    if not open_:
        return (DOUBT_QUOTED,)
    marked = [c for c in open_ if c.marker is not None]
    pool = marked or open_
    if len({key(c) for c in pool}) > 1:
        return (DOUBT_SEVERAL,)
    return ()


def finish(
    cands: Sequence[Candidate],
    policy: str,
    marker_order: Sequence[str],
    rule_groups: Sequence[Sequence[str]],
    key: Callable[[Candidate], Hashable],
) -> Extraction:
    """Run ``choose`` and ``doubt_reasons`` and package the result."""
    ordered = tuple(sorted(cands, key=lambda c: (c.start, c.end)))
    pick = choose(ordered, policy, marker_order, rule_groups)
    doubt = doubt_reasons(ordered, key)
    if pick is None:
        return Extraction(None, None, None, None, policy, doubt, ordered)
    return Extraction(
        answer=pick.answer,
        rule=pick.marker or pick.rule,
        form=pick.rule,
        span=(pick.start, pick.end),
        policy=policy,
        doubt=doubt,
        candidates=ordered,
    )
