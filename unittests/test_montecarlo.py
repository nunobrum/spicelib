#!/usr/bin/env python

# -------------------------------------------------------------------------------
# Name:        test_montecarlo.py
# Purpose:     Unit tests for the Montecarlo._get_sim_value tolerance/distribution math.
#
# Licence:     refer to the LICENSE file
# -------------------------------------------------------------------------------
"""Regression tests for ``Montecarlo._get_sim_value``.

These tests pin down the statistical contract that the per-run value
generator must satisfy. They are deliberately stdlib-only (no scipy)
so they can run anywhere spicelib does.
"""

import statistics
import sys
import unittest
from pathlib import Path

# Allow running directly from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spicelib.sim.tookit.montecarlo import Montecarlo
from spicelib.sim.tookit.tolerance_deviations import ComponentDeviation


N_SAMPLES = 2000


def _samples(value, dev, n=N_SAMPLES):
    return [float(Montecarlo._get_sim_value(value, dev)) for _ in range(n)]


class TestGetSimValueTolerance(unittest.TestCase):
    """``DeviationType.tolerance`` paths in Montecarlo._get_sim_value."""

    def test_normal_is_multiplicative_for_small_values(self):
        """Regression: previously used absolute σ = tolerance/3.

        For value=1mH and tolerance=5%, the buggy form sampled
        N(0.001, 0.0167) — σ was 17× the mean, ~16% of samples were
        negative. The fix scales σ by ``value`` so ±tol corresponds to
        ±3σ of the resulting distribution, matching the ``ntol`` macro
        emitted by ``prepare_testbench``.
        """
        nominal = 1e-3  # 1 mH inductor
        tolerance = 0.05
        dev = ComponentDeviation.from_tolerance(tolerance, distribution="normal")
        samples = _samples(nominal, dev)

        mean = statistics.fmean(samples)
        stdev = statistics.stdev(samples)
        expected_sigma = nominal * tolerance / 3

        # Mean within 3σ/√n of nominal (statistical bound on the sample mean).
        self.assertAlmostEqual(
            mean, nominal,
            delta=3 * expected_sigma / (len(samples) ** 0.5),
            msg=f"mean={mean!r}, expected ~{nominal!r}",
        )
        # σ within 15% of theoretical (2000 samples → SE ≈ 1.6%).
        self.assertGreater(stdev, 0.85 * expected_sigma,
                           msg=f"stdev={stdev!r}, expected ~{expected_sigma!r}")
        self.assertLess(stdev, 1.15 * expected_sigma,
                        msg=f"stdev={stdev!r}, expected ~{expected_sigma!r}")
        # No negatives, no values outside ±30% of nominal (5σ is ~0.83% of nominal,
        # so ±30% catches any order-of-magnitude regression).
        self.assertTrue(all(s > 0 for s in samples), "samples must stay positive")
        self.assertTrue(all(0.7 * nominal < s < 1.3 * nominal for s in samples),
                        "samples must stay within ±30% of nominal")

    def test_normal_is_multiplicative_for_large_values(self):
        """Same contract holds for resistor-scale nominals (10 kΩ, 1%)."""
        nominal = 10_000.0
        tolerance = 0.01
        dev = ComponentDeviation.from_tolerance(tolerance, distribution="normal")
        samples = _samples(nominal, dev)
        mean = statistics.fmean(samples)
        stdev = statistics.stdev(samples)
        expected_sigma = nominal * tolerance / 3
        self.assertAlmostEqual(
            mean, nominal,
            delta=3 * expected_sigma / (len(samples) ** 0.5),
        )
        self.assertGreater(stdev, 0.85 * expected_sigma)
        self.assertLess(stdev, 1.15 * expected_sigma)

    def test_uniform_path_unchanged(self):
        """Regression guard: uniform path was never broken; ensure it stays correct."""
        nominal = 25e-6  # 25 µF
        tolerance = 0.10
        dev = ComponentDeviation.from_tolerance(tolerance, distribution="uniform")
        samples = _samples(nominal, dev, n=500)
        # Every sample strictly within [nom*(1-tol), nom*(1+tol)].
        lo = nominal * (1 - tolerance)
        hi = nominal * (1 + tolerance)
        for s in samples:
            self.assertGreaterEqual(s, lo)
            self.assertLessEqual(s, hi)
        # And the mean lands near the midpoint (i.e., near nominal).
        self.assertAlmostEqual(
            statistics.fmean(samples), nominal,
            delta=tolerance * nominal / (len(samples) ** 0.5) * 5,
        )


class TestGetSimValueMinMax(unittest.TestCase):
    """``DeviationType.minmax`` paths — regression guard, not changed by this fix."""

    def test_minmax_uniform_within_bounds(self):
        dev = ComponentDeviation.from_min_max(10.0, 20.0, distribution="uniform")
        samples = _samples(0.0, dev, n=500)  # nominal ignored for minmax
        for s in samples:
            self.assertGreaterEqual(s, 10.0)
            self.assertLessEqual(s, 20.0)


class TestGetSimValueNone(unittest.TestCase):
    """``DeviationType.none`` returns the nominal unchanged."""

    def test_none_returns_value(self):
        dev = ComponentDeviation.none()
        # _get_sim_value returns the nominal unchanged for DeviationType.none.
        self.assertEqual(Montecarlo._get_sim_value(1.5, dev), 1.5)


if __name__ == "__main__":
    unittest.main()
