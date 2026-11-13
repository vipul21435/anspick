"""Command-line interface: extract, score, disagree, sample, explain."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

from anspick import __version__
from anspick.compare import EquivOptions, compare_pair, differing_items, run_extractor, score_row
from anspick.core import POLICIES
from anspick.equiv import PERCENT_MODES
from anspick.extractors import Extractor
from anspick.records import TYPES, Record, extract, extract_record, read_records
from anspick.sample import draw, read_rows, tally, to_markdown

DEFAULT_EXTRACTORS = ["cascade", "first", "last", "marker"]


def _records(args: argparse.Namespace) -> list[Record]:
    return read_records(args.input, args.type, args.output_field, args.gold_field)


def _md(s: object) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{100 * x:.1f}"


def _dash(x: object) -> str:
    return "-" if x is None else str(x)


def _signed_pct(x: float | None) -> str:
    return "-" if x is None else f"{100 * x:+.1f}"


def _eq(args: argparse.Namespace) -> EquivOptions:
    return EquivOptions(args.rel_tol, args.abs_tol, args.percent)


def _extractors(args: argparse.Namespace) -> list[Extractor]:
    specs = args.extractor or DEFAULT_EXTRACTORS
    return [Extractor(s) for s in specs]


def _emit_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_extract(args: argparse.Namespace) -> int:
    rows = []
    for rec in _records(args):
        ex = extract_record(rec, args.policy)
        row = {"id": rec.id, "type": rec.type, **ex.to_dict(with_candidates=args.candidates)}
        if rec.gold is not None:
            row["gold"] = rec.gold
        rows.append(row)
    if args.format == "json":
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        return 0
    print("| id | type | answer | rule | doubt |")
    print("|---|---|---|---|---|")
    for row in rows:
        print(
            f"| {_md(row['id'])} | {row['type']} | {_md(row['answer'])} "
            f"| {row['rule']} | {', '.join(row['doubt'])} |"
        )
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    recs = _records(args)
    runs = [run_extractor(e, recs, _eq(args)) for e in _extractors(args)]
    rows = [score_row(r, args.confidence) for r in runs]
    if args.format == "json":
        _emit_json({"records": len(recs), "scores": [r.to_dict() for r in rows]})
        return 0
    level = f"{100 * args.confidence:g} %"
    print(f"{len(recs)} records, {rows[0].n if rows else 0} with a reference\n")
    print(f"| extractor | accuracy % | {level} interval | correct / n | no answer | doubtful |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {_md(r.extractor)} | {_pct(r.accuracy)} | {_pct(r.low)} to {_pct(r.high)} "
            f"| {r.correct} / {r.n} | {r.no_answer} | {_dash(r.doubtful)} |"
        )
    return 0


def cmd_disagree(args: argparse.Namespace) -> int:
    recs = _records(args)
    exs = _extractors(args)
    if len(exs) < 2:
        raise ValueError("disagree needs at least two extractors")
    runs = [run_extractor(e, recs, _eq(args)) for e in exs]
    scores = [score_row(r, args.confidence) for r in runs]
    pairs = [
        compare_pair(runs[0], r, recs, args.confidence, args.rounds, args.seed) for r in runs[1:]
    ]
    diff = differing_items(runs, recs)
    if args.format == "json":
        _emit_json(
            {
                "records": len(recs),
                "scores": [s.to_dict() for s in scores],
                "pairs": [p.to_dict() for p in pairs],
                "differing": [
                    {
                        "id": recs[i].id,
                        "gold": recs[i].gold,
                        "answers": {r.name: r.answers[i].answer for r in runs},
                    }
                    for i in diff
                ],
            }
        )
        return 0
    level = f"{100 * args.confidence:g} %"
    print(f"{len(recs)} records; extractors differ on {len(diff)}\n")
    print(f"| extractor | accuracy % | {level} interval | no answer | doubtful |")
    print("|---|---|---|---|---|")
    for s in scores:
        print(
            f"| {_md(s.extractor)} | {_pct(s.accuracy)} | {_pct(s.low)} to {_pct(s.high)} "
            f"| {s.no_answer} | {_dash(s.doubtful)} |"
        )
    for p in pairs:
        print(f"\n## {_md(p.reference)} minus {_md(p.other)}\n")
        print(
            f"gap {_signed_pct(p.gap)} points ({level} paired bootstrap "
            f"{_signed_pct(p.low)} to {_signed_pct(p.high)}), answers differ on {p.differ}, "
            f"right only under {_md(p.reference)}: {p.flips_ref_only}, "
            f"right only under {_md(p.other)}: {p.flips_other_only}\n"
        )
        if p.by_rule:
            print(f"| rule under {_md(p.reference)} | rule under {_md(p.other)} | items "
                  "| contribution (points) | share of gap |")
            print("|---|---|---|---|---|")
            for g in p.by_rule:
                share = "-" if g["share"] is None else f"{100 * g['share']:.0f} %"
                print(
                    f"| {g['rule_reference']} | {g['rule_other']} | {g['items']} "
                    f"| {_signed_pct(g['contribution'])} | {share} |"
                )
    if args.show:
        print("\n## Differing outputs\n")
        head = " | ".join(_md(r.name) for r in runs)
        print(f"| id | gold | {head} |")
        print("|---|---|" + "---|" * len(runs))
        for i in diff[: args.show]:
            cells = " | ".join(_md(r.answers[i].answer) for r in runs)
            print(f"| {_md(recs[i].id)} | {_md(recs[i].gold)} | {cells} |")
    return 0


def cmd_sample(args: argparse.Namespace) -> int:
    if args.verdicts:
        rows = read_rows(args.verdicts)
        result, done = tally(rows, args.confidence)
        if args.format == "json":
            ext = [r.to_dict() for r in result]
            _emit_json({"rows": len(rows), "read": done, "extractors": ext})
            return 0
        level = f"{100 * args.confidence:g} %"
        print(f"{done} of {len(rows)} rows read\n")
        print(f"| extractor | right / read | accuracy % | {level} interval |")
        print("|---|---|---|---|")
        for r in result:
            print(f"| {_md(r.extractor)} | {r.right} / {r.n} | {_pct(r.accuracy)} "
                  f"| {_pct(r.low)} to {_pct(r.high)} |")
        return 0
    if not args.input:
        raise ValueError("sample needs an input file, or --verdicts to read a filled sample")
    recs = _records(args)
    runs = [run_extractor(e, recs, _eq(args)) for e in _extractors(args)]
    rows = draw(runs, recs, args.n, args.seed)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as fh:
            fh.write(to_markdown(rows))
    if not args.out and not args.markdown:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(f"wrote {len(rows)} rows", file=sys.stderr)
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    if args.text is not None:
        kind = "choice" if args.options else args.type
        rec = Record("text", args.text, kind, args.options, None)
    else:
        if not args.input or args.id is None:
            raise ValueError("explain needs --text, or an input file with --id")
        found = [r for r in _records(args) if r.id == args.id]
        if not found:
            raise ValueError(f"no record with id {args.id!r}")
        rec = found[0]
    picks = {p: extract(rec.output, rec.type, p, rec.options, rec.labels) for p in POLICIES}
    base = picks["cascade"]
    if args.format == "json":
        _emit_json(
            {
                "id": rec.id,
                "type": rec.type,
                "doubt": list(base.doubt),
                "picks": {p: ex.to_dict() for p, ex in picks.items()},
                "candidates": [c.to_dict() for c in base.candidates],
            }
        )
        return 0
    print(f"record {rec.id} ({rec.type}); doubt: {', '.join(base.doubt) or 'none'}\n")
    print("| # | answer | rule | marker | quoted | span | text |")
    print("|---|---|---|---|---|---|---|")
    for i, c in enumerate(base.candidates, start=1):
        print(f"| {i} | {_md(c.answer)} | {c.rule} | {c.marker or ''} | "
              f"{'yes' if c.quoted else ''} | {c.start}-{c.end} | {_md(c.raw)} |")
    print("\n| policy | answer | rule |")
    print("|---|---|---|")
    for p, ex in picks.items():
        print(f"| {p} | {_md(ex.answer)} | {ex.rule or ''} |")
    return 0


def _input_opts(p: argparse.ArgumentParser, required: bool = True) -> None:
    if required:
        p.add_argument("input", help="JSONL file of model outputs")
    else:
        p.add_argument("input", nargs="?", help="JSONL file of model outputs")
    p.add_argument("--type", choices=TYPES, default="number", help="default answer type")
    p.add_argument("--output-field", default="output", help="field holding the model output")
    p.add_argument("--gold-field", default="gold", help="field holding the reference answer")
    p.add_argument("--format", choices=("md", "json"), default="md")


def _scoring_opts(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "-e",
        "--extractor",
        action="append",
        help="extractor spec, repeatable: a policy, field:NAME, re:first:PAT or re:last:PAT "
        f"(default: {', '.join(DEFAULT_EXTRACTORS)})",
    )
    p.add_argument("--rel-tol", type=float, default=1e-6)
    p.add_argument("--abs-tol", type=float, default=0.0)
    p.add_argument("--percent", choices=PERCENT_MODES, default="both")
    p.add_argument("--confidence", type=float, default=0.95)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anspick",
        description="Extract final answers from model outputs and measure extractor effects.",
    )
    p.add_argument("--version", action="version", version=f"anspick {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    e = sub.add_parser("extract", help="extract one answer per output")
    _input_opts(e)
    e.add_argument("--policy", choices=POLICIES, default="cascade")
    e.add_argument("--candidates", action="store_true", help="include every candidate (JSON)")
    e.set_defaults(func=cmd_extract)

    s = sub.add_parser("score", help="accuracy under each extractor, with intervals")
    _input_opts(s)
    _scoring_opts(s)
    s.set_defaults(func=cmd_score)

    d = sub.add_parser("disagree", help="compare extractors on the same outputs")
    _input_opts(d)
    _scoring_opts(d)
    d.add_argument("--rounds", type=int, default=2000, help="bootstrap rounds")
    d.add_argument("--seed", type=int, default=0)
    d.add_argument("--show", type=int, default=0, help="list this many differing outputs")
    d.set_defaults(func=cmd_disagree)

    m = sub.add_parser("sample", help="draw disagreements for reading, or tally read verdicts")
    _input_opts(m, required=False)
    _scoring_opts(m)
    m.add_argument("-n", type=int, default=30, help="rows to draw")
    m.add_argument("--seed", type=int, default=0)
    m.add_argument("--out", help="write the rows as JSONL here")
    m.add_argument("--markdown", help="write a Markdown copy for reading here")
    m.add_argument("--verdicts", help="a filled sample JSONL to tally instead of drawing")
    m.set_defaults(func=cmd_sample)

    x = sub.add_parser("explain", help="show every candidate and each policy's pick")
    _input_opts(x, required=False)
    x.add_argument("--id", help="record id to explain")
    x.add_argument("--text", help="explain this text instead of a record")
    x.add_argument("--options", nargs="*", help="option texts for --text")
    x.set_defaults(func=cmd_explain)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ValueError) as e:
        print(f"anspick: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
