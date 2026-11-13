"""Intervals for accuracies and for paired accuracy differences.

``wilson``
    The Wilson score interval for a binomial proportion,
    ``(p + z^2/2n +- z sqrt(p(1-p)/n + z^2/4n^2)) / (1 + z^2/n)``.
``paired_bootstrap``
    A percentile bootstrap for the difference of two accuracies measured on the same
    items: items are resampled with replacement and the mean of the per-item
    difference ``c_a - c_b`` is recomputed, ``rounds`` times with a fixed seed.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from statistics import NormalDist


def z_for(confidence: float) -> float:
    if not 0 < confidence < 1:
        raise ValueError("confidence must be in (0, 1)")
    return NormalDist().inv_cdf(0.5 + confidence / 2)


def wilson(k: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for ``k`` successes out of ``n``."""
    if n <= 0:
        return (0.0, 1.0)
    if not 0 <= k <= n:
        raise ValueError("need 0 <= k <= n")
    z = z_for(confidence)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def paired_bootstrap(
    a: Sequence[bool],
    b: Sequence[bool],
    confidence: float = 0.95,
    rounds: int = 2000,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap interval for ``mean(a) - mean(b)`` over paired items."""
    if len(a) != len(b):
        raise ValueError("paired samples must have the same length")
    n = len(a)
    if n == 0:
        return (0.0, 0.0)
    d = [int(x) - int(y) for x, y in zip(a, b, strict=True)]
    if all(x == 0 for x in d):
        return (0.0, 0.0)
    rng = random.Random(seed)
    stats = sorted(sum(rng.choices(d, k=n)) / n for _ in range(rounds))
    lo_i = int(math.floor((1 - confidence) / 2 * (rounds - 1)))
    hi_i = int(math.ceil((1 + confidence) / 2 * (rounds - 1)))
    return (stats[lo_i], stats[hi_i])
