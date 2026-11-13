"""Reading JSONL records and dispatching them to the right extractor.

A record is one JSON object per line. Fields (names can be changed on the command line):

``output``   the model output (required).
``type``     ``choice``, ``number``, ``yesno`` or ``span``. When missing, a record with
             ``options`` is ``choice`` and anything else uses the default type.
``options``  the option texts, in label order (multiple choice only).
``labels``   the option labels, if they are not ``A``, ``B``, ... (multiple choice only).
``gold``     the reference answer (optional; needed for scoring).
``id``       an identifier (optional; the line number is used when missing).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anspick import choice, numbers, spans, yesno
from anspick.core import POLICIES, Extraction

TYPES: tuple[str, ...] = ("choice", "number", "yesno", "span")


@dataclass
class Record:
    """One model output to extract from."""

    id: str
    output: str
    type: str
    options: list[str] | None = None
    labels: list[str] | None = None
    gold: Any = None
    extra: dict[str, Any] = field(default_factory=dict)


def extract(
    text: str,
    kind: str,
    policy: str = "cascade",
    options: list[str] | None = None,
    labels: list[str] | str | None = None,
) -> Extraction:
    """Extract an answer of type ``kind`` from ``text`` under ``policy``."""
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}; expected one of {', '.join(POLICIES)}")
    if kind == "choice":
        return choice.extract(text, policy, options=options, labels=labels)
    if kind == "number":
        return numbers.extract(text, policy)
    if kind == "yesno":
        return yesno.extract(text, policy)
    if kind == "span":
        return spans.extract(text, policy)
    raise ValueError(f"unknown answer type {kind!r}; expected one of {', '.join(TYPES)}")


def extract_record(rec: Record, policy: str = "cascade") -> Extraction:
    return extract(rec.output, rec.type, policy, rec.options, rec.labels)


def to_record(
    obj: dict[str, Any],
    line_no: int,
    default_type: str = "number",
    output_field: str = "output",
    gold_field: str = "gold",
) -> Record:
    """Build a :class:`Record` from one parsed JSON object."""
    if not isinstance(obj, dict):
        raise ValueError(f"line {line_no}: expected a JSON object")
    if output_field not in obj:
        raise ValueError(f"line {line_no}: missing field {output_field!r}")
    out = obj[output_field]
    text = out if isinstance(out, str) else json.dumps(out)
    options = obj.get("options")
    if options is not None:
        if not isinstance(options, list):
            raise ValueError(f"line {line_no}: 'options' must be a list")
        options = [str(o) for o in options]
    kind = obj.get("type") or ("choice" if options else default_type)
    if kind not in TYPES:
        raise ValueError(f"line {line_no}: unknown type {kind!r}")
    labels = obj.get("labels")
    if labels is not None:
        labels = [str(x) for x in labels]
    rid = obj.get("id", line_no)
    known = {output_field, gold_field, "type", "options", "labels", "id"}
    return Record(
        id=str(rid),
        output=text,
        type=kind,
        options=options,
        labels=labels,
        gold=obj.get(gold_field),
        extra={k: v for k, v in obj.items() if k not in known},
    )


def iter_jsonl(lines: Iterable[str]) -> Iterator[tuple[int, dict[str, Any]]]:
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            yield i, json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"line {i}: not valid JSON ({e.msg})") from None


def read_records(
    path: str | Path,
    default_type: str = "number",
    output_field: str = "output",
    gold_field: str = "gold",
) -> list[Record]:
    """Read every record of a JSONL file (``-`` is not handled here)."""
    with open(path, encoding="utf-8") as fh:
        return [
            to_record(obj, i, default_type, output_field, gold_field)
            for i, obj in iter_jsonl(fh)
        ]
