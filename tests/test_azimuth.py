"""Unit tests for the axial (mod-180) statistics used by the orientation-coincidence detector.

The identities pinned here are the ones the detector relies on; each is derived in the module
docstring from Mardia & Jupp (2000) rather than tuned.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems52 import azimuth as A


def test_axial_difference_is_mod_180():
    assert A.axial_difference(0.0, np.deg2rad(5.0)) == pytest.approx(np.deg2rad(5.0))
    assert A.axial_difference(0.0, np.deg2rad(175.0)) == pytest.approx(np.deg2rad(5.0))
    assert A.axial_difference(np.deg2rad(10.0), np.deg2rad(100.0)) == pytest.approx(np.deg2rad(90.0))
    # never exceeds 90 degrees
    rng = np.random.default_rng(0)
    d = A.axial_difference(rng.uniform(0, np.pi, 2000), rng.uniform(0, np.pi, 2000))
    assert d.max() <= np.pi / 2 + 1e-12 and d.min() >= 0.0


def test_wrap_axial_folds_into_half_circle():
    for t in (0.0, 0.5, np.pi / 2, np.pi - 1e-9, np.pi, 2 * np.pi, -0.3):
        w = A.wrap_axial(t)
        assert 0.0 <= w < np.pi


def test_resultant_is_one_for_aligned_and_near_zero_for_uniform():
    rng = np.random.default_rng(1)
    aligned = np.full(500, np.deg2rad(37.0))
    _, r, n = A.axial_resultant(aligned)
    assert r == pytest.approx(1.0, abs=1e-12) and n == 500
    uniform = rng.uniform(0.0, np.pi, 20000)
    _, r2, _ = A.axial_resultant(uniform)
    assert r2 < 0.05


def test_axial_agreement_null_is_zero_and_perfect_is_one():
    rng = np.random.default_rng(2)
    a = rng.uniform(0.0, np.pi, 4000)
    b = rng.uniform(0.0, np.pi, 4000)
    res = A.axial_agreement(a, b)
    assert abs(res["cos2_mean"]) < 0.05                      # the test statistic's null is 0
    assert res["R"] == pytest.approx(2 / np.pi, abs=0.05)     # the *concentration* null is 2/pi
    same = A.axial_agreement(a, a)
    assert same["cos2_mean"] == pytest.approx(1.0, abs=1e-9)
    assert same["R"] == pytest.approx(1.0, abs=1e-9)
    perp = A.axial_agreement(a, A.wrap_axial(a + np.pi / 2))
    assert perp["cos2_mean"] == pytest.approx(-1.0, abs=1e-9)


def test_folded_difference_of_independent_axial_fields_is_uniform():
    """The fact that makes cos2_mean the right statistic: d ~ U[0, pi/2], so E[cos 2d] = 0."""
    rng = np.random.default_rng(5)
    d = A.axial_difference(rng.uniform(0, np.pi, 200000), rng.uniform(0, np.pi, 200000))
    hist, edges = np.histogram(d, bins=8, range=(0, np.pi / 2))
    assert np.allclose(hist / hist.sum(), 1 / 8, atol=0.01)
    assert float(np.mean(np.cos(2 * d))) == pytest.approx(0.0, abs=0.01)
    assert float(np.mean(np.sin(2 * d))) == pytest.approx(2 / np.pi, abs=0.01)


def test_null_threshold_matches_rayleigh():
    # 2*n*R^2 ~ chi2_2 under uniformity, so R_crit = sqrt(-ln(alpha)/n)
    assert A.null_R_threshold(100, 0.05) == pytest.approx(np.sqrt(-np.log(0.05) / 100))
    rng = np.random.default_rng(3)
    hits = 0
    for _ in range(400):
        r = A.axial_resultant(rng.uniform(0.0, np.pi, 100))[1]
        hits += int(r > A.null_R_threshold(100, 0.05))
    assert 0.02 < hits / 400 < 0.10      # nominal 5 %, generous band for 400 draws


def test_mean_axial_deg_reports_degrees():
    x = np.deg2rad([10.0, 12.0, 8.0])
    assert A.mean_axial_deg(x) == pytest.approx(10.0, abs=0.5)
