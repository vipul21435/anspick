from hypothesis import given, settings
from hypothesis import strategies as st

from anspick import choice, numbers, spans, yesno
from anspick.core import POLICIES
from anspick.equiv import number_match

pieces = st.sampled_from(
    [
        "The answer is ", "#### ", "\\boxed{", "}", "\\frac{3}{4}", "1,234.5", "-7", "12%",
        "1.5e3", "3/4", "(B)", "option 2", "A ", "yes", "No.", "true", "\n", "Question: ",
        "> ", '"', "Paris", " and ", ".", "$", "\\text{ cm}", "−", "{", "\\",
    ]
)
texts = st.one_of(st.text(max_size=80), st.lists(pieces, max_size=12).map("".join))
OPTS = ["Paris", "London", "Berlin", "Madrid"]


def check(ex, text):
    if ex.answer is None:
        assert ex.span is None
        return
    a, b = ex.span
    assert 0 <= a < b <= len(text)
    for c in ex.candidates:
        assert 0 <= c.start < c.end <= len(text)
        assert text[c.start : c.end] == c.raw


@settings(max_examples=150, deadline=None)
@given(texts)
def test_extractors_never_raise_and_spans_hold(text):
    for policy in POLICIES:
        check(numbers.extract(text, policy), text)
        check(choice.extract(text, policy, options=OPTS), text)
        check(yesno.extract(text, policy), text)
        check(spans.extract(text, policy), text)


@settings(max_examples=150, deadline=None)
@given(texts)
def test_span_contains_returned_answer(text):
    ex = spans.extract(text)
    if ex.answer is not None:
        a, b = ex.span
        assert text[a:b] == ex.answer
    yn = yesno.extract(text)
    if yn.answer is not None:
        a, b = yn.span
        assert text[a:b].lower() == yn.answer
    ch = choice.extract(text, options=OPTS)
    if ch.answer is not None and ch.form in ("bracketed", "bare"):
        a, b = ch.span
        assert ch.answer in text[a:b]


@settings(max_examples=150, deadline=None)
@given(st.integers(-10**9, 10**9), st.integers(0, 4))
def test_written_numbers_round_trip(value, places):
    text = f"so the total is {value / 10**places:.{places}f} units"
    ex = numbers.extract(text)
    assert ex.answer is not None
    assert number_match(ex.answer, str(value / 10**places), rel_tol=1e-9) is not None


words = st.sampled_from(
    ["yes", "No", "TRUE", "false", "maybe", "The Cat", "cat", "a cat!", "", "dog"]
)


@given(words, words)
def test_yes_no_and_span_equivalence_symmetric(a, b):
    from anspick.equiv import span_match, yesno_match

    assert (yesno_match(a, b) is None) == (yesno_match(b, a) is None)
    assert (span_match(a, b) is None) == (span_match(b, a) is None)
