import pytest

from anspick.choice import extract, labels_for
from anspick.core import DOUBT_NONE, DOUBT_QUOTED, DOUBT_SEVERAL

OPTS = ["Paris", "London", "Berlin", "Madrid"]


@pytest.mark.parametrize(
    "text, answer, form",
    [
        ("I pick (B).", "B", "bracketed"),
        ("I pick [C]", "C", "bracketed"),
        ("C) Berlin is my pick", "C", "bracketed"),
        ("It must be option 2.", "B", "option-word"),
        ("Go with choice D", "D", "option-word"),
        ("The capital is Madrid.", "D", "option-text"),
        ("So, B", "B", "bare"),
    ],
)
def test_surface_forms(text, answer, form):
    ex = extract(text, options=OPTS)
    assert (ex.answer, ex.form) == (answer, form)
    a, b = ex.span
    assert text[a:b] == ex.candidates[[c.start for c in ex.candidates].index(a)].raw


def test_article_a_is_not_an_answer():
    ex = extract("A good question. The capital of France is not B.", options=OPTS)
    assert ex.answer == "B"
    assert extract("A is right", options=OPTS).answer is None
    assert extract("The answer is A because", options=OPTS).answer == "A"


def test_answer_marker_wins_over_later_letters():
    text = "The answer is C. B and D are wrong because ..."
    ex = extract(text, options=OPTS)
    assert (ex.answer, ex.rule) == ("C", "answer")
    assert extract(text, "last", options=OPTS).answer == "D"
    assert extract(text, "first", options=OPTS).answer == "C"


def test_boxed_letter():
    assert extract("\\boxed{B}", options=OPTS).rule == "boxed"


def test_option_number_out_of_range_ignored():
    assert extract("option 7", options=OPTS).answer is None


def test_restated_option_list_is_quoted():
    text = "A) Paris\nB) London\nC) Berlin\nD) Madrid\n\nI think London."
    ex = extract(text, options=OPTS)
    assert ex.answer == "B"
    assert ex.doubt == ()
    assert extract(text, "first", options=OPTS).answer == "A"
    only = extract("A) Paris\nB) London\nC) Berlin\nD) Madrid\n", options=OPTS)
    assert only.answer is None and only.doubt == (DOUBT_QUOTED,)


def test_longer_option_text_wins():
    ex = extract("It is red wine.", options=["red", "red wine"])
    assert ex.answer == "B"


def test_doubt_flags():
    assert extract("B or C, hard to say", options=OPTS).doubt == (DOUBT_SEVERAL,)
    assert extract("no idea", options=OPTS).doubt == (DOUBT_NONE,)


def test_labels():
    assert labels_for() == ["A", "B", "C", "D"]
    assert labels_for(["x", "y"]) == ["A", "B"]
    assert labels_for(labels="abc") == ["A", "B", "C"]
    with pytest.raises(ValueError):
        labels_for(labels=["AB"])
    assert extract("so E", labels="ABCDE").answer == "E"
    assert extract("so E").answer is None
