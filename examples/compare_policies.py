"""Score the bundled example outputs under every policy with the Python API.

    python examples/compare_policies.py
"""

from pathlib import Path

from anspick.compare import compare_pair, run_extractor, score_row
from anspick.extractors import Extractor
from anspick.records import extract, read_records

HERE = Path(__file__).resolve().parent


def main() -> None:
    recs = read_records(HERE / "outputs.jsonl")
    runs = [run_extractor(Extractor(p), recs) for p in ("cascade", "first", "last", "marker")]
    for run in runs:
        row = score_row(run)
        print(f"{row.extractor:8s} {row.correct}/{row.n}  ({row.low:.2f} to {row.high:.2f})")
    rep = compare_pair(runs[0], runs[1], recs)
    print(f"cascade minus first: {rep.gap:+.3f}, answers differ on {rep.differ} outputs")
    for g in rep.by_rule:
        print(f"  {g['rule_reference']} vs {g['rule_other']}: {g['items']} item(s)")
    ex = extract("Thus \\boxed{18}. Check: 18 + 2 = 20.", "number")
    print(ex.answer, ex.rule, ex.span, ex.doubt)


if __name__ == "__main__":
    main()
