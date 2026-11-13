import random

import pytest

from anspick.stats import paired_bootstrap, wilson, z_for


def test_wilson_hand_values():
    lo, hi = wilson(8, 10)
    assert lo == pytest.approx(0.4902, abs=1e-4)
    assert hi == pytest.approx(0.9433, abs=1e-4)
    lo, hi = wilson(0, 10)
    assert lo == 0.0
    assert hi == pytest.approx(0.2775, abs=1e-4)
    assert wilson(0, 0) == (0.0, 1.0)


def test_wilson_errors_and_z():
    with pytest.raises(ValueError):
        wilson(3, 2)
    with pytest.raises(ValueError):
        z_for(1.0)
    assert z_for(0.95) == pytest.approx(1.959964, abs=1e-6)


def test_wilson_coverage_by_simulation():
    rng = random.Random(1)
    p, n, hits, reps = 0.3, 50, 0, 2000
    for _ in range(reps):
        k = sum(rng.random() < p for _ in range(n))
        lo, hi = wilson(k, n)
        hits += lo <= p <= hi
    assert 0.93 <= hits / reps <= 0.97


def test_paired_bootstrap():
    a = [True] * 30 + [False] * 10
    b = [True] * 20 + [False] * 20
    lo, hi = paired_bootstrap(a, b, seed=3)
    assert lo < 0.25 < hi
    assert lo > 0
    assert paired_bootstrap(a, a) == (0.0, 0.0)
    assert paired_bootstrap([], []) == (0.0, 0.0)
    with pytest.raises(ValueError):
        paired_bootstrap([True], [])
