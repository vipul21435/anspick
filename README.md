# anspick

Pull the final answer out of free-form model output with documented rules, flag the outputs where the
extraction is doubtful, and measure how far the choice of extractor moves a benchmark score.

Status: early. The extractors and the `extract` command work; scoring, extractor comparison and the
reading-sample workflow are not written yet.

## Install

```
pip install git+https://github.com/vipul21435/anspick
```

## Quickstart

```
anspick extract examples/outputs.jsonl
```

```
| id | type | answer | rule | doubt |
|---|---|---|---|---|
| item-1 | number | 36 | hash |  |
| item-2 | number | 3/4 | boxed |  |
| item-3 | number | 40 | decimal | several-candidates |
| item-4 | choice | C | answer |  |
| item-5 | choice | D | option-text | several-candidates |
| item-6 | yesno | no | yes-no |  |
| item-7 | number | 25% | percent |  |
| item-8 | span | the blue whale | answer |  |
```

## What works so far

- Extractors for numbers, multiple-choice labels, yes/no and true/false, and short spans. Each returns the
  answer, the rule that fired and the character span, and keeps every candidate it found.
- Policies `cascade` (the documented rule order), `first`, `last` and `marker` (answer markers only).
- A doubt flag: several different candidates, no candidate, or candidates only inside a quoted question.

The rules are documented in the module docstrings under `src/anspick/`.

## Licence

MIT, see `LICENSE`.

Built by Vipul Raj Jha · https://vipul21435.github.io
