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
