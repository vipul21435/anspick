"""One hand-written fixture per failure mode named in the README."""

from anspick.core import DOUBT_NONE, DOUBT_QUOTED, DOUBT_SEVERAL
from anspick.records import extract

OPTS = ["Paris", "London", "Berlin", "Madrid"]


def test_long_derivation_then_marker():
    text = "First 12 * 3 = 36.\nThen 36 - 4 = 32.\nHalf of it: 32 / 2 = 16.\n#### 16"
    assert extract(text, "number").answer == "16"
    assert extract(text, "number", "first").answer == "12"


def test_marker_line_with_two_numbers_takes_the_first():
    text = "He has 4 blue and 8 red left.\n#### 4, 8"
    ex = extract(text, "number")
    assert (ex.answer, ex.rule) == ("4", "hash")


def test_unfinished_output_has_no_marked_answer():
    text = "The total is <<40+35=<<40+35=<<40+35=<<40+35"
    assert extract(text, "number", "marker").answer is None
    assert extract(text, "number", "last").answer == "35"
    assert extract(text, "number").doubt == (DOUBT_SEVERAL,)


def test_number_with_currency_and_units():
    assert extract("The answer is $1,250.00 per month.", "number").answer == "1250"
    assert extract("so \\boxed{9\\,\\text{m}^2}", "number").answer == "9"
    assert extract("Final answer: 3.5 kg", "number").answer == "3.5"


def test_two_marked_candidates_are_doubtful():
    ex = extract("The answer is 5. Hmm, the answer is 6.", "number")
    assert ex.answer == "6" and ex.doubt == (DOUBT_SEVERAL,)


def test_only_quoted_candidates():
    text = '> Which city is the capital of Germany? (A) Paris (B) London (C) Berlin (D) Madrid'
    assert extract(text, "choice", options=OPTS).doubt == (DOUBT_QUOTED,)


def test_restated_options_then_bare_letter():
    text = "A. Paris\nB. London\nC. Berlin\nD. Madrid\nAnswer: C"
    ex = extract(text, "choice", options=OPTS)
    assert (ex.answer, ex.rule) == ("C", "answer") and ex.doubt == ()


def test_option_text_restated_in_prose():
    ex = extract("Germany's capital is Berlin, not Paris.", "choice", options=OPTS)
    assert ex.doubt == (DOUBT_SEVERAL,)
    assert extract("Germany's capital is Berlin, not Paris.", "choice", "first", OPTS).answer == "C"


def test_nothing_to_extract():
    for kind in ("number", "choice", "yesno", "span"):
        assert extract("", kind).doubt == (DOUBT_NONE,)
