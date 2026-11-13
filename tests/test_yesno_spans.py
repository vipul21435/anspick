from anspick.core import DOUBT_SEVERAL
from anspick.spans import extract as extract_span
from anspick.spans import normalise_span
from anspick.yesno import extract as extract_yn
from anspick.yesno import polarity


def test_yes_no_words():
    assert extract_yn("Yes, it does.").answer == "yes"
    assert extract_yn("The claim is false.").answer == "false"
    assert extract_yn("No. The sum is odd.").answer == "no"


def test_no_as_determiner_is_skipped():
    ex = extract_yn("There is no reason to doubt it, so yes")
    assert ex.answer == "yes"
    assert ex.doubt == ()
    assert extract_yn("There is no reason").answer is None


def test_marked_yes_no():
    text = "Yes, at first glance. But wait. Final answer: no"
    ex = extract_yn(text)
    assert (ex.answer, ex.rule) == ("no", "answer")
    assert extract_yn(text, "first").answer == "yes"


def test_true_counts_as_yes_for_doubt():
    assert extract_yn("Yes. That is true.").doubt == ()
    assert extract_yn("Yes. No.").doubt == (DOUBT_SEVERAL,)
    assert polarity("TRUE") is True and polarity("maybe") is None


def test_span_after_marker():
    text = "Let me think.\nThe answer is **Mount Everest**. It is the highest."
    ex = extract_span(text)
    assert (ex.answer, ex.rule) == ("Mount Everest", "answer")
    a, b = ex.span
    assert text[a:b] == "Mount Everest"


def test_span_boxed_and_last_line():
    assert extract_span("so \\boxed{blue whale}").answer == "blue whale"
    ex = extract_span("Some reasoning here.\nParis")
    assert (ex.answer, ex.rule) == ("Paris", "last-line")
    assert extract_span("Some reasoning here.\nParis", "marker").answer is None


def test_long_last_line_is_not_a_candidate():
    long = "one two three four five six seven eight nine ten eleven twelve thirteen"
    assert extract_span(long).answer is None


def test_normalise_span():
    assert normalise_span("The  Blue-Whale!") == "blue whale"
