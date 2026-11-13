# anspick

Extract the final answer (an option letter, a number, yes/no, a short span) from free-form model output with
documented rules, flag the outputs where the extraction is doubtful, and measure how far the choice of extractor
moves a benchmark score.

## Why this is hard

Models wrap answers in prose, restate the options, give two candidates, write the number in LaTeX or with units,
or answer after a long derivation full of other numbers. A scorer that takes the first match and one that takes the
last can disagree on most outputs, and whatever they disagree on is counted as model error. Alzahrani et al. (2024)
report that changing the method of answer selection, among other small perturbations, moves models by up to 8
places in MMLU rankings; Wang et al. (2024) argue for scoring instruction-tuned models on their text answers
rather than first-token probabilities, which makes extraction part of the score; Molfese et al. (2025) find that common answer-extraction strategies for multiple-choice
evaluation often disagree with human judgment; Yu et al. (2024) note that the regular expressions evaluation
frameworks use for extraction frequently fail. anspick makes the extraction rules explicit, keeps every candidate
it saw, and reports how much of a score gap each rule accounts for.

## Install

```
pip install git+https://github.com/vipul21435/anspick
```

Python 3.10 or newer, no runtime dependencies.

## Quickstart

Input is JSONL, one object per line: `output` (the model output), `type` (`number`, `choice`, `yesno` or `span`;
a record with `options` is `choice`), and optionally `options`, `labels`, `gold` and `id`.

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

Every candidate in one output, and what each policy picks:

```
anspick explain --text $'Question: what is 6 / 8?\n\nMaybe 12 parts... no.\nFinal answer: \\boxed{\\frac{3}{4}}, i.e. 0.75'
```

```
record text (number); doubt: none

| # | answer | rule | marker | quoted | span | text |
|---|---|---|---|---|---|---|
| 1 | 6 | decimal |  | yes | 18-19 | 6 |
| 2 | 8 | decimal |  | yes | 22-23 | 8 |
| 3 | 12 | decimal |  |  | 32-34 | 12 |
| 4 | 3/4 | latex-frac | boxed |  | 69-80 | \frac{3}{4} |
| 5 | 0.75 | decimal |  |  | 88-92 | 0.75 |

| policy | answer | rule |
|---|---|---|
| cascade | 3/4 | boxed |
| first | 6 | decimal |
| last | 0.75 | decimal |
| marker | 3/4 | boxed |
```

Scores under two extractors, with intervals, and the gap split by the rules that fired:

```
anspick disagree examples/outputs.jsonl -e cascade -e first
```

```
8 records; extractors differ on 3

| extractor | accuracy % | 95 % interval | no answer | doubtful |
|---|---|---|---|---|
| cascade | 100.0 | 67.6 to 100.0 | 0 | 2 |
| first | 62.5 | 30.6 to 86.3 | 0 | 2 |

## cascade minus first

gap +37.5 points (95 % paired bootstrap +0.0 to +75.0), answers differ on 3, right only under cascade: 3, right only under first: 0

| rule under cascade | rule under first | items | contribution (points) | share of gap |
|---|---|---|---|---|
| answer | bracketed | 1 | +12.5 | 33 % |
| hash | decimal | 1 | +12.5 | 33 % |
| option-text | bare | 1 | +12.5 | 33 % |
```

The other commands are `anspick score` (the accuracy table alone) and `anspick sample` (draw disagreements for
reading, then tally the read verdicts). Every command takes `--format json`. `examples/compare_policies.py` does the
same through the Python API.

## How it works

**Candidates.** Each extractor scans the whole output and returns every candidate with its normalised answer, the
surface rule that matched, its character span, the answer marker governing it (if any) and whether it sits inside
quoted material. The rules for each answer type are listed in the module docstrings; in short:

- numbers (`numbers.py`): `\frac{3}{4}`, `\dfrac`, `\tfrac12`, `1.5 \times 10^{3}`, `1.5e3`, `3/4` (not dates),
  `12.5%` / `12.5\%` / `12.5 percent`, and decimals with `,`, `{,}` or `,\!` thousands separators. A sign counts
  only when it does not follow a digit or letter, so `3-5` gives 3 and 5. Trailing units and `\text{ cm}` groups
  are not part of the number. Answers are normalised (`-1,234.50` to `-1234.5`, `\frac{-1}{2}` to `-1/2`);
- multiple choice (`choice.py`): `(B)` / `[B]`, `B)` at a line start or after a marker, `option 2` / `choice B`,
  the option text restated (the longest match wins), and a bare label letter (a bare `A` or `I` followed by a
  lowercase word is read as English);
- yes/no (`yesno.py`): `yes`, `no`, `true`, `false`, with `no` counted only where it cannot be a determiner;
- short spans (`spans.py`): the text a marker governs, cut at the first sentence end, or the last short line.

**Markers**, in priority order: `\boxed{...}` (braces matched), `####` (the convention of the GSM8K reference
solutions, Cobbe et al. 2021), and answer phrases such as "the answer is", "Answer:" or "the correct option is".

**Quoted material**: lines starting with `>`, a "Question:" paragraph (up to a blank line or an answer marker),
double-quoted passages of five words or more, and, for multiple choice, a restated option list.

**Policies.** `cascade` ignores quoted candidates, takes the strongest marker present (its last occurrence), and
otherwise falls back to the unmarked rules in their documented order, last occurrence first. `first` and `last` take
the first or last candidate in the text regardless of markers and quoting: the two naive scorers. `marker` takes
only marked candidates and returns nothing when the output has no marker. `disagree`, `score` and `sample` also
accept `field:NAME` (an answer already stored in the record) and `re:first:PATTERN` / `re:last:PATTERN`, so a
scorer's own regular expression can be run beside the built-in rules.

**Doubt flag**, independent of the policy: `several-candidates` when the unquoted marked candidates (or, with no
marker, all unquoted candidates) hold more than one distinct answer; `no-candidate`; `only-quoted` when every
candidate is inside quoted material.

**Equivalence** (`equiv.py`), one rule at a time: exact rational equality (`3/4` = `0.75` = `\frac{3}{4}`), a
relative and absolute tolerance, percent against proportion or against the bare number (`25%` matches `0.25` and
`25` by default; `--percent` selects one reading or none), option label against label, option text or a 0-based
index, yes against true, and normalised spans. The number, yes/no and span rules are symmetric. The MATH release
compares answers as strings after a fixed normalisation (Hendrycks et al. 2021, `modeling/math_equivalence.py`:
`\dfrac` to `\frac`, `\frac12` to `\frac{1}{2}`, units, `\%` and spaces removed); anspick reads LaTeX numbers in
the same spirit but compares them by value, so `0.75` also matches `\frac{3}{4}`.

**Intervals and the gap split.** Accuracies carry Wilson score intervals. For two extractors on the same items the
gap is `(1/n) sum_i (c_ref,i - c_other,i)`, with a seeded paired percentile bootstrap interval (2000 rounds by
default). Grouping the non-zero terms by the pair (rule under the reference, rule under the other) splits the gap
exactly; each group's share is its sum over the gap.

**Reading sample.** `anspick sample` draws up to `-n` outputs on which the extractors give different answers (fixed
seed) and writes them as JSONL with an empty `read_answer` field, plus a Markdown copy for reading. Once the read
answers are filled in (the answer the output commits to, or `none`), `anspick sample --verdicts FILE` reports how
often each extractor agrees with them, with Wilson intervals. These rates describe the extractors on
disagreements, not on the whole set.

## Results on public data

Data: GSM8K test generations (1,319 per run, 5-shot) published as per-sample details by the archived Open LLM
Leaderboard on Hugging Face, one dataset per evaluated model. Reference answers come from the GSM8K test split
(`openai/gsm8k`, licence stated on its page: MIT), joined on the question text. The details datasets' cards say
"[More Information Needed]" under licensing, so no outputs are committed: `scripts/fetch_gsm8k_details.py`
downloads them (about 15 MB) and writes the JSONL files used below. Rows are labelled by details dataset and run
timestamp; each dataset card names the model it says was evaluated.

```
uv run --with pyarrow python scripts/fetch_gsm8k_details.py DATA
anspick disagree DATA/gsm8k-mistral-7b-v0.1.jsonl -e cascade -e first -e last -e marker \
  -e 're:first:#### (\-?[0-9\.\,]+)' -e 're:last:(-?[$0-9.,]{2,})|(-?[0-9]+)'
```

and the same for `gsm8k-llama-2-7b.jsonl` and `gsm8k-falcon-7b.jsonl`. Accuracy in %, with the 95 % Wilson
interval; the last column counts outputs flagged doubtful:

| details dataset (run) | first | last | marker | cascade | doubtful |
|---|---|---|---|---|---|
| `details_mistralai__Mistral-7B-v0.1` (2023-12-02T13-01-55) | 1.9 (1.3 to 2.8) | 37.8 (35.3 to 40.5) | 37.8 (35.3 to 40.5) | 37.8 (35.3 to 40.5) | 148 (11.2 %) |
| `details_meta-llama__Llama-2-7b-hf` (2023-09-20T14-39-46) | 1.7 (1.2 to 2.6) | 8.9 (7.5 to 10.5) | 7.1 (5.9 to 8.6) | 8.9 (7.5 to 10.5) | 526 (39.9 %) |
| `details_tiiuae__falcon-7b` (2023-12-03T17-58-16) | 1.9 (1.3 to 2.8) | 5.0 (4.0 to 6.3) | 4.6 (3.6 to 5.9) | 5.0 (4.0 to 6.3) | 299 (22.7 %) |

What the runs show:

- First-match is far below the rest because the first number in a GSM8K derivation is usually a quantity from the
  question. For the Mistral run the cascade-minus-first gap is +35.9 points (paired bootstrap +33.2 to +38.7); 93 %
  of it comes from outputs where the cascade read the `####` line and first-match read a plain decimal earlier on.
- Marker-only and last-match differ on the outputs that never reach a `####` line. In the Llama-2 run most outputs
  stop after their first line (median length 89 characters) and 787 of 1,319 have no marker; last-match, and the
  cascade that falls back to it, score 1.7 points higher (+1.1 to +2.5) by crediting 23 outputs whose last number
  equals the reference.
- The two regular expressions are the `strict-match` and `flexible-extract` patterns from the lm-evaluation-harness
  GSM8K task file, applied here with anspick's equivalence; they are not the harness's own reported scores. They
  stay within 0.1 points of `marker` and `last` on all three runs.
- The doubt flag fires on 11 % to 40 % of outputs. Most of these have no marker and several different numbers
  (118, 446 and 241 outputs); 30, 80 and 44 hold no number at all; 14 falcon-7b outputs carry conflicting markers.

**Read sample.** From the falcon-7b run, 30 outputs on which `cascade`, `last` and `marker` disagree were drawn with
seed 0 and read one by one; for each, the answer the output commits to was written down, or `none` when it stops
before committing to one:

```
anspick sample DATA/gsm8k-falcon-7b.jsonl -e cascade -e last -e marker -n 30 --seed 0 --out sample.jsonl
anspick sample --verdicts sample.jsonl
```

28 of the 30 outputs commit to no answer: most loop on a calculator annotation (`<<40-100=<<40-100=...`) or repeat
one sentence until the length limit. `marker` agreed with the read answer on 28 of 30 (93.3 %, Wilson 78.7 to
98.2), `cascade` and `last` on 1 of 30 (3.3 %, 0.6 to 16.7): on these outputs the fallback picks a number out of an
unfinished loop. The other two were `#### 1 minute and 30 seconds`, where every extractor reads a single number (1
or 30) instead of 1.5 minutes, and a one-line output ending "is 5". The verdict file is not committed.

## Limitations

- Rules are surface patterns. Negation ("the answer is not B"), self-correction in prose ("40, no wait, 42") and
  answers spread over several lines are not understood; the doubt flag is the only signal for them.
- Numbers written in words ("forty-two"), mixed numbers (`1 1/2`), compound quantities (`1 minute and 30 seconds`),
  fractions with spaces (`6 / 8`) and symbolic answers (`\sqrt{2}`, intervals, expressions) are not parsed as
  numbers. Spans are compared only by normalised string equality.
- A "Question:" paragraph is detected only at a line start and runs to a blank line or an answer marker.
- The rule for "no" is a heuristic and will misread some uses.
- The real-data run covers one free-form arithmetic benchmark and three runs from one harness; multiple-choice,
  yes/no and span extraction are tested on hand-written fixtures only.
- The read sample is 30 outputs from one run, drawn from disagreements only.

## Related tools

- [lm-evaluation-harness](https://github.com/EleutherAI/lm-evaluation-harness) applies regex filter pipelines to
  generations (its task guide, section "Filters"); anspick can run such patterns beside its own rules.
- xFinder (Yu et al. 2024) is a trained model for answer extraction and matching; anspick is rule-based and runs no
  model.
- [evaltable](https://github.com/vipul21435/evaltable) reads harness result files;
  [callmatch](https://github.com/vipul21435/callmatch) scores tool calls;
  [evalstats](https://github.com/vipul21435/evalstats) gives error bars and paired comparisons for evaluations;
  [graderguard](https://github.com/vipul21435/graderguard) audits graders.

## References

- Cobbe, K., Kosaraju, V., Bavarian, M., Chen, M., Jun, H., Kaiser, L., Plappert, M., Tworek, J., Hilton, J.,
  Nakano, R., Hesse, C., Schulman, J. (2021). Training Verifiers to Solve Math Word Problems. arXiv:2110.14168.
- Hendrycks, D., Burns, C., Kadavath, S., Arora, A., Basart, S., Tang, E., Song, D., Steinhardt, J. (2021).
  Measuring Mathematical Problem Solving With the MATH Dataset. arXiv:2103.03874.
- Yu, Q., Zheng, Z., Song, S., Li, Z., Xiong, F., Tang, B., Chen, D. (2024). xFinder: Large Language Models as
  Automated Evaluators for Reliable Evaluation. arXiv:2405.11874.
- Wang, X., Hu, C., Ma, B., Röttger, P., Plank, B. (2024). Look at the Text: Instruction-Tuned Language Models are
  More Robust Multiple Choice Selectors than You Think. arXiv:2404.08382.
- Alzahrani, N., Alyahya, H. A., Alnumay, Y., Alrashed, S., Alsubaie, S., Almushaykeh, Y., Mirza, F., Alotaibi, N.,
  Altwairesh, N., Alowisheq, A., Bari, M. S., Khan, H. (2024). When Benchmarks are Targets: Revealing the
  Sensitivity of Large Language Model Leaderboards. arXiv:2402.01781.
- Molfese, F. M., Moroni, L., Gioffré, L., Scirè, A., Conia, S., Navigli, R. (2025). Right Answer, Wrong Score:
  Uncovering the Inconsistencies of LLM Evaluation in Multiple-Choice Question Answering. arXiv:2503.14996.

## Licence

MIT, see `LICENSE`.

Built by Vipul Raj Jha · https://vipul21435.github.io
