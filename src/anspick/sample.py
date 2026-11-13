"""A labelled sample of disagreements, read one by one.

``draw``
    Picks up to ``n`` records on which the extractors give different answers, with a
    fixed seed, and writes them as JSONL rows carrying the output, each extractor's
    answer and an empty ``read_answer`` field. A Markdown copy lays the same rows out
    for reading.
``tally``
    Reads the rows back once ``read_answer`` is filled in (the answer the output commits
    to, or ``"none"`` when it commits to none) and reports, for each extractor, how
    often its answer matches the read answer, with a Wilson interval. Matching uses the
    equivalence rules of :mod:`anspick.equiv` for the record's type; an extractor that
    returned nothing is right exactly when the read answer is ``"none"``.

Because the rows are drawn from disagreements only, these accuracies describe the
extractors on the outputs where the choice matters, not on the whole set.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from anspick.compare import Run, differing_items
from anspick.equiv import equivalent
from anspick.records import Record
from anspick.stats import wilson

NONE_WORDS = {"none", "no answer", "-", "n/a"}


def draw(
    runs: Sequence[Run], records: Sequence[Record], n: int, seed: int = 0
) -> list[dict[str, Any]]:
    """Rows for reading: up to ``n`` disagreements chosen with ``seed``."""
    pool = differing_items(runs, records)
    rng = random.Random(seed)
    picked = sorted(rng.sample(pool, min(n, len(pool))))
    rows = []
    for i in picked:
        rec = records[i]
        row: dict[str, Any] = {
            "id": rec.id,
            "type": rec.type,
            "output": rec.output,
            "answers": {r.name: r.answers[i].answer for r in runs},
            "read_answer": None,
        }
        if rec.options is not None:
            row["options"] = rec.options
        if rec.labels is not None:
            row["labels"] = rec.labels
        rows.append(row)
    return rows


def to_markdown(rows: Sequence[dict[str, Any]]) -> str:
    out = ["# Sample for reading", ""]
    for row in rows:
        out.append(f"## {row['id']}")
        out.append("")
        out.append("```")
        out.append(row["output"].replace("```", "'''"))
        out.append("```")
        out.append("")
        if row.get("options"):
            labels = row.get("labels") or [chr(65 + i) for i in range(len(row["options"]))]
            pairs = zip(labels, row["options"], strict=False)
            opts = ", ".join(f"{lab}: {opt}" for lab, opt in pairs)
            out.append(f"options: {opts}")
            out.append("")
        for name, ans in row["answers"].items():
            out.append(f"- `{name}`: {ans}")
        out.append("- read answer: ")
        out.append("")
    return "\n".join(out)


@dataclass
class TallyRow:
    extractor: str
    n: int
    right: int
    accuracy: float | None
    low: float | None
    high: float | None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _matches(answer: str | None, read: Any, row: dict[str, Any]) -> bool:
    is_none = read is None or (isinstance(read, str) and read.strip().lower() in NONE_WORDS)
    if is_none:
        return answer is None
    return (
        equivalent(answer, read, row["type"], row.get("options"), row.get("labels"))
        is not None
    )


def tally(rows: Sequence[dict[str, Any]], confidence: float = 0.95) -> tuple[list[TallyRow], int]:
    """Per-extractor agreement with the read answers, and the number of rows read."""
    done = [r for r in rows if r.get("read_answer") not in (None, "")]
    names: list[str] = []
    for r in done:
        for name in r["answers"]:
            if name not in names:
                names.append(name)
    out = []
    for name in names:
        hits = [_matches(r["answers"].get(name), r["read_answer"], r) for r in done]
        k, n = sum(hits), len(hits)
        lo, hi = wilson(k, n, confidence) if n else (None, None)
        out.append(TallyRow(name, n, k, k / n if n else None, lo, hi))
    return out, len(done)


def read_rows(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    for i, r in enumerate(rows, start=1):
        if not isinstance(r, dict) or "answers" not in r or "type" not in r:
            raise ValueError(f"line {i}: not a sample row (needs 'answers' and 'type')")
    return rows
