"""Fetch public GSM8K generations and write them as anspick JSONL.

Sources (downloaded, not committed):

- per-sample details of the 5-shot GSM8K runs that the archived Open LLM Leaderboard
  published on Hugging Face, one dataset per evaluated model
  (``open-llm-leaderboard-old/details_<org>__<model>``); the dataset cards state no
  licence, so only derived numbers are reported;
- the GSM8K test split (``openai/gsm8k``, MIT licence) for the reference answers, joined
  on the question text.

Usage (pyarrow is needed only here):

    uv run --with pyarrow python scripts/fetch_gsm8k_details.py DATA_DIR

writes ``DATA_DIR/gsm8k-<name>.jsonl`` with fields ``id``, ``output``, ``gold`` and
``type`` (always ``number``).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

HF = "https://huggingface.co/datasets"
GSM8K_TEST = f"{HF}/openai/gsm8k/resolve/main/main/test-00000-of-00001.parquet"

# name -> (details dataset, run timestamp)
RUNS = {
    "mistral-7b-v0.1": ("details_mistralai__Mistral-7B-v0.1", "2023-12-02T13-01-55.687268"),
    "llama-2-7b": ("details_meta-llama__Llama-2-7b-hf", "2023-09-20T14-39-46.791628"),
    "falcon-7b": ("details_tiiuae__falcon-7b", "2023-12-03T17-58-16.188347"),
}


def details_url(dataset: str, stamp: str) -> str:
    name = f"details_harness%7Cgsm8k%7C5_{stamp}.parquet"
    return f"{HF}/open-llm-leaderboard-old/{dataset}/resolve/main/{stamp}/{name}"


def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        print(f"fetching {url}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as fh:
            fh.write(resp.read())
    return dest


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    import pyarrow.parquet as pq

    out_dir = Path(argv[0])
    raw = out_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    test = pq.read_table(fetch(GSM8K_TEST, raw / "gsm8k_test.parquet")).to_pylist()
    gold = {row["question"].strip(): row["answer"].split("####")[-1].strip() for row in test}
    for name, (dataset, stamp) in RUNS.items():
        path = fetch(details_url(dataset, stamp), raw / f"{name}.parquet")
        rows = pq.read_table(path, columns=["example", "predictions"]).to_pylist()
        n_out = 0
        with open(out_dir / f"gsm8k-{name}.jsonl", "w", encoding="utf-8") as fh:
            for i, row in enumerate(rows, start=1):
                q = row["example"].strip()
                if q not in gold or not row["predictions"]:
                    continue
                rec = {
                    "id": f"q{i:04d}",
                    "type": "number",
                    "output": row["predictions"][0],
                    "gold": gold[q],
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_out += 1
        print(f"{name}: {n_out} of {len(rows)} rows joined", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
