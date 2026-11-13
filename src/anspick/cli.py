"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from anspick import __version__
from anspick.core import POLICIES
from anspick.records import TYPES, Record, extract_record, read_records


def _records(args: argparse.Namespace) -> list[Record]:
    return read_records(args.input, args.type, args.output_field, args.gold_field)


def _md_escape(s: object) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def cmd_extract(args: argparse.Namespace) -> int:
    recs = _records(args)
    rows = []
    for rec in recs:
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
            f"| {_md_escape(row['id'])} | {row['type']} | {_md_escape(row['answer'])} "
            f"| {row['rule']} | {', '.join(row['doubt'])} |"
        )
    return 0


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", help="JSONL file of model outputs")
    p.add_argument("--type", choices=TYPES, default="number", help="default answer type")
    p.add_argument("--output-field", default="output", help="field holding the model output")
    p.add_argument("--gold-field", default="gold", help="field holding the reference answer")
    p.add_argument("--format", choices=("md", "json"), default="md")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="anspick",
        description="Extract final answers from model outputs and measure extractor effects.",
    )
    p.add_argument("--version", action="version", version=f"anspick {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    e = sub.add_parser("extract", help="extract one answer per output")
    _common(e)
    e.add_argument("--policy", choices=POLICIES, default="cascade")
    e.add_argument("--candidates", action="store_true", help="include every candidate (JSON)")
    e.set_defaults(func=cmd_extract)
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
