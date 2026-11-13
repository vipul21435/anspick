import json
from pathlib import Path

import pytest

from anspick.cli import main
from anspick.records import extract, read_records

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "outputs.jsonl"


def write(tmp_path, rows):
    p = tmp_path / "in.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_extract_markdown(capsys):
    assert main(["extract", str(EXAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "| item-1 | number | 36 | hash |  |" in out


def test_extract_json_with_candidates(tmp_path, capsys):
    p = write(tmp_path, [{"output": "2 then 3", "gold": "3"}])
    assert main(["extract", str(p), "--format", "json", "--candidates", "--policy", "first"]) == 0
    row = json.loads(capsys.readouterr().out.strip())
    assert row["answer"] == "2" and row["gold"] == "3" and len(row["candidates"]) == 2
    assert row["id"] == "1"


def test_type_inferred_from_options(tmp_path):
    p = write(tmp_path, [{"output": "(B)", "options": ["x", "y"]}, {"output": "7"}])
    recs = read_records(p)
    assert [r.type for r in recs] == ["choice", "number"]


def test_bad_input_reports_error(tmp_path, capsys):
    p = tmp_path / "bad.jsonl"
    p.write_text("{not json}\n", encoding="utf-8")
    assert main(["extract", str(p)]) == 2
    assert "line 1" in capsys.readouterr().err
    p.write_text(json.dumps({"text": "1"}) + "\n", encoding="utf-8")
    assert main(["extract", str(p)]) == 2
    assert main(["extract", str(tmp_path / "missing.jsonl")]) == 2


def test_extract_dispatch_errors():
    with pytest.raises(ValueError):
        extract("1", "date")
    with pytest.raises(ValueError):
        extract("1", "number", policy="middle")


def test_score_and_disagree(capsys):
    assert main(["score", str(EXAMPLE)]) == 0
    out = capsys.readouterr().out
    assert "| cascade | 100.0 |" in out
    assert main(["disagree", str(EXAMPLE), "-e", "cascade", "-e", "first", "--show", "3"]) == 0
    out = capsys.readouterr().out
    assert "## cascade minus first" in out and "## Differing outputs" in out
    assert main(["disagree", str(EXAMPLE), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["pairs"]) == 3 and data["differing"]
    assert main(["score", str(EXAMPLE), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["scores"][0]["n"] == 8
    assert main(["disagree", str(EXAMPLE), "-e", "cascade"]) == 2


def test_sample_round_trip(tmp_path, capsys):
    out = tmp_path / "s.jsonl"
    md = tmp_path / "s.md"
    assert main(["sample", str(EXAMPLE), "-n", "3", "--out", str(out), "--markdown", str(md)]) == 0
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    assert len(rows) == 3 and md.exists()
    for r in rows:
        r["read_answer"] = r["answers"]["cascade"]
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert main(["sample", "--verdicts", str(out)]) == 0
    assert "| cascade | 3 / 3 |" in capsys.readouterr().out
    assert main(["sample", "--verdicts", str(out), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["read"] == 3
    assert main(["sample", str(EXAMPLE), "-n", "2"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 2
    assert main(["sample"]) == 2


def test_explain(capsys):
    assert main(["explain", str(EXAMPLE), "--id", "item-3"]) == 0
    out = capsys.readouterr().out
    assert "several-candidates" in out and "| marker | None |" in out
    assert main(["explain", "--text", "So (B).", "--options", "x", "y", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["picks"]["cascade"]["answer"] == "B" and data["type"] == "choice"
    assert main(["explain", str(EXAMPLE), "--id", "nope"]) == 2
    assert main(["explain"]) == 2


def test_example_script_runs():
    import runpy

    runpy.run_path(str(EXAMPLE.parent / "compare_policies.py"), run_name="__main__")


@pytest.mark.parametrize(
    "row",
    [[1, 2], {"output": "x", "options": "AB"}, {"output": "x", "type": "date"}],
)
def test_bad_records_are_rejected(tmp_path, row):
    p = write(tmp_path, [row])
    with pytest.raises(ValueError):
        read_records(p)


def test_record_fields_carry_through(tmp_path):
    p = write(tmp_path, [{"output": {"text": "x"}, "labels": ["P", "Q"], "type": "choice", "z": 1}])
    rec = read_records(p)[0]
    assert rec.output == '{"text": "x"}' and rec.labels == ["P", "Q"] and rec.extra == {"z": 1}


def test_field_extractor_reads_each_type():
    from anspick.extractors import Extractor
    from anspick.records import Record

    yn = Record("1", "x", "yesno", extra={"p": "True"})
    assert Extractor("field:p").run(yn).answer == "true"
    sp = Record("1", "x", "span", extra={"p": "  blue whale "})
    assert Extractor("field:p").run(sp).answer == "blue whale"
    sp2 = Record("1", "x", "span", extra={"p": "reasoning\nAnswer: orca"})
    assert Extractor("field:p").run(sp2).answer == "orca"
