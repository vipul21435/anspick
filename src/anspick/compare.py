"""Scoring under one or several extractors, and where they disagree.

``score``
    For each extractor: the accuracy over records with a reference, its Wilson interval,
    the number of outputs with no answer, and the number flagged doubtful (the doubt flag
    belongs to the built-in extractors; ``field:`` and ``re:`` extractors report none).
``disagree``
    Every extractor is compared with a reference extractor (the first one given). For
    each pair: the accuracy gap, a paired bootstrap interval for it, the number of
    outputs where the two extracted answers differ, and the gap broken down by the pair
    of rules that fired. The gap is ``(1/n) sum_i (c_ref,i - c_other,i)`` over records
    with a reference; grouping the terms by ``(rule under the reference, rule under the
    other)`` splits it exactly, and each group's share is its sum over the gap.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from anspick.core import POLICIES
from anspick.equiv import equivalent, same_answer
from anspick.extractors import Answer, Extractor
from anspick.records import Record
from anspick.stats import paired_bootstrap, wilson


@dataclass(frozen=True)
class EquivOptions:
    rel_tol: float = 1e-6
    abs_tol: float = 0.0
    percent: str = "both"


@dataclass
class Run:
    """One extractor applied to every record."""

    name: str
    answers: list[Answer]
    correct: list[bool | None]

    @property
    def graded(self) -> list[bool]:
        return [c for c in self.correct if c is not None]


def run_extractor(
    ex: Extractor, records: Sequence[Record], eq: EquivOptions | None = None
) -> Run:
    eq = eq or EquivOptions()
    answers = [ex.run(r) for r in records]
    correct: list[bool | None] = []
    for rec, ans in zip(records, answers, strict=True):
        if rec.gold is None:
            correct.append(None)
            continue
        rule = equivalent(
            ans.answer,
            rec.gold,
            rec.type,
            rec.options,
            rec.labels,
            eq.rel_tol,
            eq.abs_tol,
            eq.percent,
        )
        correct.append(rule is not None)
    return Run(ex.spec, answers, correct)


@dataclass
class ScoreRow:
    extractor: str
    n: int
    correct: int
    accuracy: float | None
    low: float | None
    high: float | None
    no_answer: int
    doubtful: int | None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def score_row(run: Run, confidence: float = 0.95) -> ScoreRow:
    graded = run.graded
    n, k = len(graded), sum(graded)
    lo, hi = wilson(k, n, confidence) if n else (None, None)
    return ScoreRow(
        extractor=run.name,
        n=n,
        correct=k,
        accuracy=k / n if n else None,
        low=lo,
        high=hi,
        no_answer=sum(a.answer is None for a in run.answers),
        doubtful=sum(bool(a.doubt) for a in run.answers) if run.name in POLICIES else None,
    )


@dataclass
class PairReport:
    reference: str
    other: str
    n: int
    gap: float
    low: float
    high: float
    differ: int
    flips_ref_only: int
    flips_other_only: int
    by_rule: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def compare_pair(
    ref: Run,
    other: Run,
    records: Sequence[Record],
    confidence: float = 0.95,
    rounds: int = 2000,
    seed: int = 0,
) -> PairReport:
    idx = [i for i, c in enumerate(ref.correct) if c is not None]
    a = [bool(ref.correct[i]) for i in idx]
    b = [bool(other.correct[i]) for i in idx]
    n = len(idx)
    gap = (sum(a) - sum(b)) / n if n else 0.0
    lo, hi = paired_bootstrap(a, b, confidence, rounds, seed) if n else (0.0, 0.0)
    differ = sum(
        not same_answer(ref.answers[i].answer, other.answers[i].answer, records[i].type)
        for i in range(len(records))
    )
    groups: Counter[tuple[str, str]] = Counter()
    counts: Counter[tuple[str, str]] = Counter()
    for i, ca, cb in zip(idx, a, b, strict=True):
        if ca == cb:
            continue
        key = (ref.answers[i].rule or "none", other.answers[i].rule or "none")
        groups[key] += int(ca) - int(cb)
        counts[key] += 1
    by_rule = []
    for key, s in sorted(groups.items(), key=lambda kv: (-abs(kv[1]), kv[0])):
        by_rule.append(
            {
                "rule_reference": key[0],
                "rule_other": key[1],
                "items": counts[key],
                "contribution": s / n,
                "share": (s / n) / gap if gap else None,
            }
        )
    return PairReport(
        reference=ref.name,
        other=other.name,
        n=n,
        gap=gap,
        low=lo,
        high=hi,
        differ=differ,
        flips_ref_only=sum(x and not y for x, y in zip(a, b, strict=True)),
        flips_other_only=sum(y and not x for x, y in zip(a, b, strict=True)),
        by_rule=by_rule,
    )


def differing_items(runs: Sequence[Run], records: Sequence[Record]) -> list[int]:
    """Indices of records on which at least two extractors give different answers."""
    out = []
    for i, rec in enumerate(records):
        first = runs[0].answers[i].answer
        if any(not same_answer(first, r.answers[i].answer, rec.type) for r in runs[1:]):
            out.append(i)
    return out
