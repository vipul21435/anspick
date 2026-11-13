import pytest

from anspick.core import (
    DOUBT_NONE,
    DOUBT_QUOTED,
    DOUBT_SEVERAL,
    Candidate,
    choose,
    doubt_reasons,
    drop_overlaps,
    finish,
)

ORDER = ("boxed", "hash", "answer")
GROUPS = (("strong",), ("weak",))


def cand(answer, start, rule="strong", marker=None, quoted=False):
    return Candidate(answer, rule, start, start + len(answer), answer, marker, quoted)


def test_first_and_last_ignore_markers_and_quotes():
    cs = [cand("1", 0, quoted=True), cand("2", 5, marker="answer"), cand("3", 9)]
    assert choose(cs, "first", ORDER, GROUPS).answer == "1"
    assert choose(cs, "last", ORDER, GROUPS).answer == "3"


def test_cascade_prefers_highest_marker_then_last_occurrence():
    cs = [
        cand("1", 0, marker="answer"),
        cand("2", 4, marker="boxed"),
        cand("3", 8, marker="answer"),
        cand("4", 12, marker="boxed"),
        cand("5", 16),
    ]
    assert choose(cs, "cascade", ORDER, GROUPS).answer == "4"
    assert choose(cs, "marker", ORDER, GROUPS).answer == "4"


def test_cascade_falls_back_to_rule_groups_in_order():
    cs = [cand("1", 0, rule="weak"), cand("2", 4, rule="strong"), cand("3", 8, rule="weak")]
    assert choose(cs, "cascade", ORDER, GROUPS).answer == "2"
    assert choose(cs, "marker", ORDER, GROUPS) is None


def test_cascade_skips_quoted_candidates():
    cs = [cand("1", 0, marker="answer", quoted=True), cand("2", 4)]
    assert choose(cs, "cascade", ORDER, GROUPS).answer == "2"
    assert choose([cs[0]], "cascade", ORDER, GROUPS) is None


def test_unknown_policy_raises():
    with pytest.raises(ValueError):
        choose([], "middle", ORDER, GROUPS)


def test_doubt_reasons():
    assert doubt_reasons([], str) == (DOUBT_NONE,)
    assert doubt_reasons([cand("1", 0, quoted=True)], str) == (DOUBT_QUOTED,)
    key = lambda c: c.answer  # noqa: E731
    assert doubt_reasons([cand("1", 0), cand("2", 3)], key) == (DOUBT_SEVERAL,)
    # once a marker is present only marked candidates count
    assert doubt_reasons([cand("1", 0), cand("2", 3, marker="answer")], key) == ()
    assert doubt_reasons([cand("2", 0), cand("2", 3)], key) == ()


def test_drop_overlaps_prefers_priority_then_length():
    a = Candidate("B", "paren", 0, 3, "(B)")
    b = Candidate("B", "bare", 1, 2, "B")
    c = Candidate("C", "bare", 5, 6, "C")
    kept = drop_overlaps([b, a, c], lambda x: 0 if x.rule == "paren" else 1)
    assert kept == [a, c]


def test_finish_reports_marker_as_rule_and_surface_as_form():
    cs = [cand("7", 2, marker="hash")]
    ex = finish(cs, "cascade", ORDER, GROUPS, lambda c: c.answer)
    assert (ex.answer, ex.rule, ex.form, ex.span) == ("7", "hash", "strong", (2, 3))
    d = ex.to_dict(with_candidates=True)
    assert d["candidates"][0]["marker"] == "hash"
    assert not ex.doubtful
