# Changelog

## 0.1.0

- Extractors for numbers (LaTeX fractions and scientific notation, percent, thousands separators, signs, trailing
  units), multiple-choice labels, yes/no and true/false, and short spans, each a documented rule cascade that
  returns the answer, the rule that fired and the character span.
- Answer markers (`\boxed{}`, `####`, answer phrases) and quoted-material detection (block quotes, "Question:"
  paragraphs, long double-quoted passages, restated option lists).
- Policies `cascade`, `first`, `last` and `marker`, and a policy-independent doubt flag.
- Equivalence rules for scoring: exact rational, tolerance, percent against proportion or number, label against
  option text or index, yes against true, normalised spans.
- `anspick extract`, `score`, `disagree`, `sample` and `explain`, with Markdown and JSON output; `field:` and `re:`
  extractors for comparing other scorers.
- Wilson intervals, paired bootstrap intervals for score gaps, and an exact split of a gap by rule pair.
- Fetch script for public GSM8K generations and the results in the README.
