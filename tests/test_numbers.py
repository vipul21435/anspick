from fractions import Fraction

import pytest

from anspick.core import DOUBT_NONE, DOUBT_QUOTED, DOUBT_SEVERAL
from anspick.numbers import canon_decimal, extract, parse_number, tokens


@pytest.mark.parametrize(
    "raw, want",
    [
        ("-1,234.50", "-1234.5"),
        ("007", "7"),
        ("-0.0", "0"),
        ("+3", "3"),
        ("1{,}000", "1000"),
        ("10,\\!000", "10000"),
        ("−2", "-2"),
        (".5", "0.5"),
    ],
)
def test_canon_decimal(raw, want):
    assert canon_decimal(raw) == want


@pytest.mark.parametrize(
    "text, answer, form",
    [
        ("so we get 42.", "42", "decimal"),
        ("total is 1,234,567 apples", "1234567", "decimal"),
        ("x = -3.25", "-3.25", "decimal"),
        ("ratio 3/4", "3/4", "fraction"),
        ("value \\frac{3}{4}", "3/4", "latex-frac"),
        ("value -\\dfrac{1}{2}", "-1/2", "latex-frac"),
        ("value \\tfrac12", "1/2", "latex-frac"),
        ("value \\frac{-1}{-2}", "1/2", "latex-frac"),
        ("growth of 12.5%", "12.5%", "percent"),
        ("growth of 12.5\\%", "12.5%", "percent"),
        ("growth of 40 percent", "40%", "percent"),
        ("about 1.5e3 m", "1.5e3", "sci"),
        ("about 2E-4", "2e-4", "sci"),
        ("about 1.5 \\times 10^{3}", "1.5e3", "latex-sci"),
        ("about 2\\cdot 10^-4", "2e-4", "latex-sci"),
        ("it is 42 cm long", "42", "decimal"),
    ],
)
def test_surface_forms(text, answer, form):
    ex = extract(text)
    assert (ex.answer, ex.form) == (answer, form)
    a, b = ex.span
    assert text[a:b].strip()


def test_minus_between_digits_is_not_a_sign():
    assert [t.answer for t in tokens("3-5")] == ["3", "5"]


def test_date_is_not_a_fraction():
    assert all(t.rule != "fraction" for t in tokens("on 1/2/2020"))


def test_zero_denominator_is_skipped():
    assert all(t.rule != "fraction" for t in tokens("1/0"))
    assert all(t.rule != "latex-frac" for t in tokens("\\frac{1}{0}"))


def test_boxed_beats_later_numbers():
    text = "Thus \\boxed{18}. Check: 18 + 2 = 20."
    ex = extract(text)
    assert (ex.answer, ex.rule) == ("18", "boxed")
    assert extract(text, "last").answer == "20"
    assert extract(text, "first").answer == "18"


def test_boxed_with_text_unit_is_marked():
    ex = extract("\\boxed{12\\text{ cm}^2}")
    assert (ex.answer, ex.rule) == ("12", "boxed")


def test_boxed_with_two_numbers_is_not_marked():
    ex = extract("\\boxed{3, 4}", "marker")
    assert ex.answer is None


def test_nested_boxed_fraction():
    assert extract("\\boxed{\\frac{3}{4}}").answer == "3/4"


def test_hash_marker_gsm8k():
    text = "She has 5 + 3 = 8 apples.\n#### 8\n"
    ex = extract(text)
    assert (ex.answer, ex.rule) == ("8", "hash")


def test_answer_phrase_takes_first_number_on_line():
    text = "We add 2 and 3.\nThe answer is 5 because 2 + 3 = 5."
    ex = extract(text, "marker")
    assert (ex.answer, ex.rule) == ("5", "answer")
    a, b = ex.span
    assert text[a:b] == "5"


def test_marker_policy_without_marker():
    assert extract("just 4 and 5", "marker").answer is None


def test_doubt_several():
    assert extract("maybe 4 or maybe 5").doubt == (DOUBT_SEVERAL,)
    assert extract("4, I mean 4.0").doubt == ()


def test_doubt_none_and_quoted():
    assert extract("no digits here").doubt == (DOUBT_NONE,)
    assert extract("> How many is 2 + 2?\n").doubt == (DOUBT_QUOTED,)


def test_question_paragraph_is_quoted():
    text = "Question: Tom has 7 apples and eats 2.\n\nHe has 5 left."
    ex = extract(text)
    assert ex.answer == "5"
    assert extract(text, "first").answer == "7"


def test_parse_number():
    assert parse_number("3/4") == (Fraction(3, 4), False)
    assert parse_number("12.5%") == (Fraction(25, 2), True)
    assert parse_number("1.5e3") == (Fraction(1500), False)
