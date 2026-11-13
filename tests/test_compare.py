import pytest

from anspick.compare import compare_pair, differing_items, run_extractor, score_row
from anspick.extractors import Extractor
from anspick.records import Record


def recs():
    return [
        Record("1", "3 + 4 = 7\n#### 7", "number", gold="7"),
        Record("2", "First 5, then 6.", "number", gold="6"),
        Record("3", "It is 10, not 12.", "number", gold="10"),
        Record("4", "no digits", "number", gold="1"),
        Record("5", "So 2", "number"),
        Record("6", "(B) I think", "choice", options=["x", "y"], gold="B", extra={"pred": "B"}),
    ]


def test_score_row_counts():
    rs = recs()
    run = run_extractor(Extractor("last"), rs)
    row = score_row(run)
    assert (row.n, row.correct) == (5, 3)
    assert row.accuracy == pytest.approx(0.6)
    assert row.no_answer == 1
    assert row.low < 0.6 < row.high


def test_gap_splits_exactly_by_rule_pair():
    rs = recs()
    ref = run_extractor(Extractor("cascade"), rs)
    other = run_extractor(Extractor("first"), rs)
    rep = compare_pair(ref, other, rs, seed=1)
    acc_ref = score_row(ref).accuracy
    acc_other = score_row(other).accuracy
    assert rep.gap == pytest.approx(acc_ref - acc_other)
    assert sum(g["contribution"] for g in rep.by_rule) == pytest.approx(rep.gap)
    if rep.gap:
        assert sum(g["share"] for g in rep.by_rule) == pytest.approx(1.0)
    assert rep.flips_ref_only - rep.flips_other_only == round(rep.gap * rep.n)
    assert rep.low <= rep.gap <= rep.high


def test_differing_items():
    rs = recs()
    runs = [run_extractor(Extractor(s), rs) for s in ("first", "last")]
    assert [rs[i].id for i in differing_items(runs, rs)] == ["1", "2", "3"]


def test_field_and_regex_extractors():
    rs = recs()
    run = run_extractor(Extractor("field:pred"), rs)
    assert run.answers[5].answer == "B" and run.correct[5]
    assert run.answers[0].answer is None
    rx = run_extractor(Extractor(r"re:first:#### (\-?[0-9\.\,]+)"), rs)
    assert rx.answers[0].answer == "7" and rx.answers[0].rule == "regex"
    assert rx.answers[1].answer is None
    flex = run_extractor(Extractor(r"re:last:(-?[$0-9.,]{2,})|(-?[0-9]+)"), rs)
    assert flex.answers[2].answer == "12"


def test_field_extractor_reads_numbers_and_lists():
    r = Record("1", "x", "number", gold="3", extra={"p": 3.0, "q": ["3"], "z": []})
    assert Extractor("field:p").run(r).answer == "3"
    assert Extractor("field:q").run(r).answer == "3"
    assert Extractor("field:z").run(r).answer is None


def test_bad_extractor_specs():
    for bad in ("middle", "field:", "re:first:("):
        with pytest.raises(ValueError):
            Extractor(bad)
