"""Equivalence between an extracted answer and a reference answer.

Each rule is listed with the name :func:`equivalent` reports when it decides a match.

Numbers (both sides are first normalised by the numeric extractor, so a reference such as
``"#### 1,234"`` or ``"\\frac{3}{4}"`` is read the same way as a model output):

``exact``       equal as exact rationals. ``3/4``, ``0.75`` and ``\\frac{3}{4}`` match;
                so do ``1.5e3`` and ``1500``.
``tolerance``   ``|a - b| <= max(abs_tol, rel_tol * max(|a|, |b|))``; defaults
                ``rel_tol = 1e-6`` and ``abs_tol = 0``.
``percent``     when exactly one side was written as a percent ``p%``, it matches the
                proportion ``p / 100`` (``percent="proportion"``), the bare number ``p``
                (``percent="number"``), or either (``percent="both"``, the default,
                because reference sets disagree on how they store percentages).
                ``percent="strict"`` turns the rule off. Two percents compare as numbers.

Multiple choice:

``letter``       the labels agree, ignoring case.
``option-text``  the reference is an option's text (case and spacing ignored) and the
                 extracted label is that option's label.
``index``        the reference is a JSON integer, read as a 0-based option index.

Yes/no: ``polarity``, so ``yes`` and ``true`` match each other, as do ``no`` and
``false``; a JSON boolean reference is read the same way.

Spans: ``normalised``, equal after :func:`anspick.spans.normalise_span`.

Every rule is symmetric in its two arguments. A missing extraction (``None``) never
matches.
"""

from __future__ import annotations

import string
from collections.abc import Sequence
from fractions import Fraction
from typing import Any

from anspick import numbers, spans, yesno

PERCENT_MODES = ("both", "proportion", "number", "strict")


def norm_number(value: Any) -> str | None:
    """Normalise a number given as text or as a JSON number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return numbers.extract(repr(value)).answer
    return numbers.extract(str(value)).answer


def _close(a: Fraction, b: Fraction, rel_tol: float, abs_tol: float) -> bool:
    diff = abs(a - b)
    return float(diff) <= max(abs_tol, rel_tol * float(max(abs(a), abs(b))))


def number_match(
    a: str,
    b: str,
    rel_tol: float = 1e-6,
    abs_tol: float = 0.0,
    percent: str = "both",
) -> str | None:
    """The rule under which two normalised numbers match, or None."""
    if percent not in PERCENT_MODES:
        raise ValueError(f"percent must be one of {', '.join(PERCENT_MODES)}")
    try:
        va, pa = numbers.parse_number(a)
        vb, pb = numbers.parse_number(b)
    except (ValueError, ZeroDivisionError):
        return None
    if va == vb and pa == pb:
        return "exact"
    if pa == pb:
        return "tolerance" if _close(va, vb, rel_tol, abs_tol) else None
    if percent == "strict":
        return None
    # exactly one side is a percent; put it first
    if pb:
        va, vb = vb, va
    readings = []
    if percent in ("both", "proportion"):
        readings.append(va / 100)
    if percent in ("both", "number"):
        readings.append(va)
    for r in readings:
        if r == vb or _close(r, vb, rel_tol, abs_tol):
            return "percent"
    return None


def choice_match(
    answer: str,
    gold: Any,
    options: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
) -> str | None:
    """The rule under which an extracted label matches a multiple-choice reference."""
    labs = [str(x).upper() for x in labels] if labels else list(string.ascii_uppercase)
    if isinstance(gold, bool):
        return None
    if isinstance(gold, int):
        return "index" if 0 <= gold < len(labs) and labs[gold] == answer.upper() else None
    g = str(gold).strip()
    g = g.strip("()[]. ")
    if len(g) == 1 and g.upper() in string.ascii_uppercase:
        return "letter" if g.upper() == answer.strip().upper() else None
    if options:
        key = " ".join(str(gold).split()).lower()
        for lab, opt in zip(labs, options, strict=False):
            if " ".join(str(opt).split()).lower() == key:
                return "option-text" if lab == answer.strip().upper() else None
    return None


def yesno_match(answer: str, gold: Any) -> str | None:
    pa = yesno.polarity(answer)
    pg = gold if isinstance(gold, bool) else yesno.polarity(str(gold))
    if pa is None or pg is None:
        return None
    return "polarity" if pa == pg else None


def span_match(answer: str, gold: Any) -> str | None:
    if gold is None:
        return None
    golds = gold if isinstance(gold, list) else [gold]
    a = spans.normalise_span(answer)
    if any(a == spans.normalise_span(str(g)) for g in golds):
        return "normalised"
    return None


def equivalent(
    answer: str | None,
    gold: Any,
    kind: str,
    options: Sequence[str] | None = None,
    labels: Sequence[str] | None = None,
    rel_tol: float = 1e-6,
    abs_tol: float = 0.0,
    percent: str = "both",
) -> str | None:
    """The equivalence rule under which ``answer`` matches ``gold``, or None."""
    if answer is None or gold is None:
        return None
    if kind == "number":
        g = norm_number(gold)
        return None if g is None else number_match(answer, g, rel_tol, abs_tol, percent)
    if kind == "choice":
        return choice_match(answer, gold, options, labels)
    if kind == "yesno":
        return yesno_match(answer, gold)
    if kind == "span":
        return span_match(answer, gold)
    raise ValueError(f"unknown answer type {kind!r}")


def same_answer(a: str | None, b: str | None, kind: str, **kw: Any) -> bool:
    """Whether two extracted answers are the same answer (both missing counts as same)."""
    if a is None or b is None:
        return a is None and b is None
    if kind == "number":
        rel, abs_ = kw.get("rel_tol", 1e-6), kw.get("abs_tol", 0.0)
        return number_match(a, b, rel, abs_, "strict") is not None
    if kind == "yesno":
        return yesno_match(a, b) is not None
    if kind == "span":
        return spans.normalise_span(a) == spans.normalise_span(b)
    return a.strip().upper() == b.strip().upper()
