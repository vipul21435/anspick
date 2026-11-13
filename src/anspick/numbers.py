"""Numeric answers.

Surface rules (one scan, tried in this order at each position):

``latex-frac``   ``\\frac{3}{4}``, ``\\dfrac{-1}{2}``, ``\\tfrac12``, with an optional sign before.
``latex-sci``    ``1.5 \\times 10^{3}`` or ``2\\cdot 10^-4``.
``sci``          ``1.5e3``, ``2E-4``.
``fraction``     ``3/4`` with no spaces and not part of a date such as ``1/2/2020``.
``percent``      ``12.5%``, ``12.5\\%``, ``12.5 percent``.
``decimal``      ``-1,234.50``, ``1{,}000``, ``10,\\!000``, ``.5``; an integer is a decimal
                 without a point.

A sign counts only when it does not follow a letter, digit or closing bracket, so ``3-5``
yields 3 and 5. Trailing units (``42 cm``, ``42\\text{ cm}``) are not part of the match.
A number is marked when it sits behind a marker (see :mod:`anspick.markers`): the only
number inside a boxed group (numbers inside ``\\text{}`` groups are ignored there), or the
first number on the line after ``####`` or an answer phrase.

Answers are normalised: separators and ``+`` dropped, Unicode minus read as ``-``,
trailing zeros after the point dropped, ``-0`` written ``0``, LaTeX fractions written
``a/b``, percent kept as a ``%`` suffix, scientific notation written ``<m>e<x>``. The
cascade for unmarked numbers is simply the last number in the text.
"""

from __future__ import annotations

import re
from fractions import Fraction

from anspick.core import Candidate, Extraction, drop_overlaps, finish
from anspick.markers import MARKER_ORDER, find_markers, inside, match_brace, quoted_regions

FORMS: tuple[str, ...] = ("latex-frac", "latex-sci", "sci", "fraction", "percent", "decimal")
RULE_GROUPS: tuple[tuple[str, ...], ...] = (FORMS,)

_SIGN = r"(?:(?<![\w)\]}])[-+\u2212])?"
_SEP = r"(?:,|\{,\}|,\\!)"
_NUM = rf"(?:\d{{1,3}}(?:{_SEP}\d{{3}})+(?!\d)|\d+)(?:\.\d+)?|(?<!\d)\.\d+"

_TOKEN_RE = re.compile(
    rf"""
    (?P<lfrac>{_SIGN}\\[dt]?frac\s*(?:
        \{{\s*(?P<lfn>[-\u2212]?\d+(?:\.\d+)?)\s*\}}\s*\{{\s*(?P<lfd>[-\u2212]?\d+(?:\.\d+)?)\s*\}}
        |(?P<lfn1>\d)(?P<lfd1>\d)))
    |(?P<lsci>(?P<lsm>{_SIGN}(?:{_NUM}))\s*\\(?:times|cdot)\s*10\s*\^\s*
        (?:\{{\s*(?P<lsx>[-+\u2212]?\d+)\s*\}}|(?P<lsx1>[-+\u2212]?\d+)))
    |(?P<sci>{_SIGN}(?:\d+(?:\.\d+)?|\.\d+)[eE][-+]?\d+(?![\w.]))
    |(?P<frac>(?<![\d/.]){_SIGN}\d+/\d+(?![\d/]|\.\d))
    |(?P<pct>{_SIGN}(?:{_NUM})\s*(?:\\?%|\s?percent\b))
    |(?P<dec>{_SIGN}(?:{_NUM}))
    """,
    re.VERBOSE,
)
_TEXT_GROUP_RE = re.compile(r"\\(?:text|mathrm|mbox|textbf|mathbf|operatorname)\s*\{")


def canon_decimal(s: str) -> str:
    """Normalise a plain decimal literal such as ``-1,234.50`` to ``-1234.5``."""
    s = s.replace("\u2212", "-").replace("{,}", "").replace(",\\!", "").replace(",", "")
    s = s.strip()
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if "." in s:
        whole, frac = s.split(".", 1)
        frac = frac.rstrip("0")
    else:
        whole, frac = s, ""
    whole = whole.lstrip("0") or "0"
    out = whole + ("." + frac if frac else "")
    if neg and out != "0":
        out = "-" + out
    return out


def _frac_str(num: str, den: str, neg: bool) -> str | None:
    """``a/b`` with the sign carried on the numerator; None for a zero denominator."""
    n, d = canon_decimal(num), canon_decimal(den)
    if Fraction(d) == 0:
        return None
    for part in (n, d):
        if part.startswith("-"):
            neg = not neg
    n, d = n.lstrip("-"), d.lstrip("-")
    return ("-" if neg and n != "0" else "") + f"{n}/{d}"


def _canon(m: re.Match[str]) -> tuple[str, str] | None:
    kind = m.lastgroup
    raw = m.group(0)
    neg = raw[:1] in "-\u2212"
    if kind == "lfrac":
        num = m.group("lfn") or m.group("lfn1")
        den = m.group("lfd") or m.group("lfd1")
        got = _frac_str(num, den, neg)
        return None if got is None else (got, "latex-frac")
    if kind == "lsci":
        mant = canon_decimal(m.group("lsm"))
        exp = int((m.group("lsx") or m.group("lsx1")).replace("\u2212", "-"))
        return f"{mant}e{exp}", "latex-sci"
    if kind == "sci":
        body = raw.replace("\u2212", "-").lower()
        mant, exp = body.split("e", 1)
        return f"{canon_decimal(mant)}e{int(exp)}", "sci"
    if kind == "frac":
        body = raw.replace("\u2212", "-").lstrip("+")
        n, d = body.lstrip("-").split("/")
        got = _frac_str(n, d, body.startswith("-"))
        return None if got is None else (got, "fraction")
    if kind == "pct":
        num = re.match(rf"{_SIGN}(?:{_NUM})", raw)
        assert num is not None
        return canon_decimal(num.group(0)) + "%", "percent"
    return canon_decimal(raw), "decimal"


def parse_number(answer: str) -> tuple[Fraction, bool]:
    """Exact value of a normalised answer and whether it was written as a percent."""
    s = answer.strip()
    pct = s.endswith("%")
    if pct:
        s = s[:-1]
    if "/" in s:
        n, d = s.split("/", 1)
        return Fraction(n) / Fraction(d), pct
    return Fraction(s), pct


def tokens(text: str) -> list[Candidate]:
    """Every number in ``text``, unmarked and unquoted."""
    out: list[Candidate] = []
    for m in _TOKEN_RE.finditer(text):
        got = _canon(m)
        if got is None:
            continue
        answer, form = got
        out.append(Candidate(answer, form, m.start(), m.end(), m.group(0)))
    return out


_UNIT_POWER_RE = re.compile(r"\s*\^\s*(?:\{[^{}]*\}|[-−]?\d+)")


def _text_groups(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """``\\text{...}``-like groups in ``[start, end)``, with a unit power such as ``^2``."""
    spans = []
    for m in _TEXT_GROUP_RE.finditer(text, start, end):
        close = match_brace(text, m.end() - 1)
        if close is not None:
            stop = close + 1
            power = _UNIT_POWER_RE.match(text, stop, end)
            if power:
                stop = power.end()
            spans.append((m.start(), stop))
    return spans


def candidates(text: str) -> list[Candidate]:
    """Every number in ``text`` with its marker and quoted flag set."""
    toks = tokens(text)
    quoted = quoted_regions(text)
    marker_of: dict[int, str] = {}
    rank = {name: i for i, name in enumerate(MARKER_ORDER)}
    for mk in find_markers(text):
        if mk.name == "boxed":
            skip = _text_groups(text, mk.start, mk.end)
            inner = [
                i
                for i, t in enumerate(toks)
                if t.start >= mk.start and t.end <= mk.end and not inside(t.start, skip)
            ]
            chosen = inner if len(inner) == 1 else []
        else:
            chosen = [i for i, t in enumerate(toks) if mk.start <= t.start < mk.end][:1]
        for i in chosen:
            old = marker_of.get(i)
            if old is None or rank[mk.name] < rank[old]:
                marker_of[i] = mk.name
    out = []
    for i, t in enumerate(toks):
        out.append(
            Candidate(
                t.answer,
                t.rule,
                t.start,
                t.end,
                t.raw,
                marker=marker_of.get(i),
                quoted=inside(t.start, quoted),
            )
        )
    return drop_overlaps(out, lambda c: FORMS.index(c.rule))


def _key(c: Candidate) -> tuple[Fraction, bool]:
    return parse_number(c.answer)


def extract(text: str, policy: str = "cascade") -> Extraction:
    """Extract a numeric answer from ``text`` under ``policy``."""
    return finish(candidates(text), policy, MARKER_ORDER, RULE_GROUPS, _key)
