import pytest
from hypothesis import given
from hypothesis import strategies as st

from anspick.equiv import (
    choice_match,
    equivalent,
    norm_number,
    number_match,
    same_answer,
    span_match,
    yesno_match,
)


@pytest.mark.parametrize(
    "a, b, rule",
    [
        ("3/4", "0.75", "exact"),
        ("1.5e3", "1500", "exact"),
        ("0.3333333", "0.33333331", "tolerance"),
        ("25%", "0.25", "percent"),
        ("25%", "25", "percent"),
        ("0.25", "25%", "percent"),
        ("25%", "25%", "exact"),
        ("3", "4", None),
        ("1/3", "0.333", None),
    ],
)
def test_number_match(a, b, rule):
    assert number_match(a, b) == rule
    assert number_match(b, a) == rule


def test_percent_modes():
    assert number_match("25%", "25", percent="proportion") is None
    assert number_match("25%", "0.25", percent="number") is None
    assert number_match("25%", "0.25", percent="strict") is None
    with pytest.raises(ValueError):
        number_match("1", "1", percent="odd")


def test_abs_tol():
    assert number_match("10", "10.4", abs_tol=0.5) == "tolerance"
    assert number_match("10", "10.6", abs_tol=0.5) is None


def test_gold_normalisation():
    assert norm_number("Natalia sold 48/2 = 24 clips.\n#### 1,234") == "1234"
    assert norm_number(12) == "12"
    assert norm_number(0.5) == "0.5"
    assert norm_number(1e-7) == "1e-7"
    assert norm_number(True) is None
    assert equivalent("1234", "#### 1,234", "number") == "exact"
    assert equivalent("3/4", "\\frac{3}{4}", "number") == "exact"
    assert equivalent(None, "1", "number") is None
    assert equivalent("1", "no number", "number") is None


def test_choice_match():
    opts = ["Paris", "London"]
    assert choice_match("B", "b") == "letter"
    assert choice_match("B", "(B)") == "letter"
    assert choice_match("B", "london", opts) == "option-text"
    assert choice_match("A", "London", opts) is None
    assert choice_match("B", 1) == "index"
    assert choice_match("B", 5, labels="AB") is None
    assert choice_match("B", True) is None
    assert choice_match("B", "Rome", opts) is None


def test_yesno_and_span():
    assert yesno_match("true", "yes") == "polarity"
    assert yesno_match("no", True) is None
    assert yesno_match("maybe", "yes") is None
    assert equivalent("false", False, "yesno") == "polarity"
    assert span_match("The Blue Whale", "blue whale") == "normalised"
    assert span_match("whale", ["orca", "Whale."]) == "normalised"
    assert span_match("x", None) is None
    with pytest.raises(ValueError):
        equivalent("1", "1", "date")


def test_same_answer():
    assert same_answer(None, None, "number")
    assert not same_answer("1", None, "number")
    assert same_answer("3/4", "0.75", "number")
    assert not same_answer("25%", "0.25", "number")
    assert same_answer("yes", "true", "yesno")
    assert same_answer("The cat", "cat", "span")
    assert same_answer("b", "B", "choice")


nums = st.one_of(
    st.integers(-10**6, 10**6).map(str),
    st.decimals(-1000, 1000, places=3, allow_nan=False, allow_infinity=False).map(str),
    st.tuples(st.integers(-50, 50), st.integers(1, 50)).map(lambda t: f"{t[0]}/{t[1]}"),
    st.integers(0, 200).map(lambda x: f"{x}%"),
)


@given(nums, nums)
def test_number_match_symmetric(a, b):
    na, nb = norm_number(a), norm_number(b)
    if na is None or nb is None:
        return
    for mode in ("both", "proportion", "number", "strict"):
        assert number_match(na, nb, percent=mode) == number_match(nb, na, percent=mode)
