import json

import pytest

from anspick.compare import run_extractor
from anspick.extractors import Extractor
from anspick.records import Record
from anspick.sample import draw, read_rows, tally, to_markdown


def setup():
    rs = [Record(str(i), f"First {i}, then {i + 1}.", "number", gold=str(i + 1)) for i in range(10)]
    rs.append(Record("same", "Only 4.", "number", gold="4"))
    runs = [run_extractor(Extractor(s), rs) for s in ("first", "last")]
    return rs, runs


def test_draw_only_disagreements_and_is_seeded():
    rs, runs = setup()
    rows = draw(runs, rs, 5, seed=2)
    assert len(rows) == 5
    assert all(r["id"] != "same" for r in rows)
    assert rows == draw(runs, rs, 5, seed=2)
    assert len(draw(runs, rs, 50)) == 10
    assert rows[0]["read_answer"] is None
    md = to_markdown(rows)
    assert md.count("## ") == 5 and "- read answer: " in md


def test_tally_against_read_answers(tmp_path):
    rs, runs = setup()
    rows = draw(runs, rs, 4, seed=0)
    for r in rows:
        r["read_answer"] = r["answers"]["last"]
    rows[0]["read_answer"] = "none"
    rows[1]["read_answer"] = None
    p = tmp_path / "s.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    result, done = tally(read_rows(str(p)))
    assert done == 3
    by = {t.extractor: t for t in result}
    assert by["last"].right == 2 and by["first"].right == 0
    assert by["last"].accuracy == pytest.approx(2 / 3)


def test_none_read_answer_matches_missing_extraction():
    rows = [{"id": "1", "type": "number", "answers": {"marker": None}, "read_answer": "none"}]
    result, _ = tally(rows)
    assert result[0].right == 1


def test_read_rows_rejects_other_files(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps({"output": "1"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_rows(str(p))
