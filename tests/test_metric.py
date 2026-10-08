"""Tests for the DTI transcription.  These are the load-bearing tests in the repository: if the
metric is wrong, every holdout number in this project is wrong.

Pins used:
  * the published formula's own arithmetic on the page's worked triple
    (TPw 3.00, FPw 1.89, FNw 2.00 -> 0.60 printed on the page, 0.6026516... exact);
  * an analytic single-pixel case in which the metric degenerates to the kernel weight;
  * the two algebraic identities the whole method rests on (FNw = |G| - TPw; the credit bar);
  * agreement with a loop-for-loop brute-force transcription of the published equations.
"""

from __future__ import annotations

import numpy as np
import pytest

from gems52 import metric as M


def test_published_worked_example_arithmetic():
    """The page prints TPw=3.00, FPw=1.89, FNw=2.00 and '0.60'.  Exact value is 0.6026516673."""
    num, den = 3.00, 3.00 + 0.2 * 1.89 + 0.8 * 2.00
    assert M.R_M == 300.0 and M.ALPHA == 0.2 and M.BETA == 0.8
    assert num / den == pytest.approx(0.6026516673, abs=1e-9)
    assert round(num / den, 2) == 0.60


def test_identity_fn_is_size_minus_tp():
    rng = np.random.default_rng(0)
    for _ in range(6):
        g = (rng.random((40, 40)) < 0.05)
        p = rng.random((40, 40)) * (rng.random((40, 40)) < 0.08)
        if not g.any():
            continue
        r = M.dti(p, g)
        assert r["fnw"] == pytest.approx(r["n_truth"] - r["tpw"], abs=1e-9)


def test_reduced_form_matches_direct_form():
    rng = np.random.default_rng(7)
    for _ in range(5):
        g = (rng.random((50, 50)) < 0.04)
        p = np.where(rng.random((50, 50)) < 0.06, 1.0, 0.0)
        r = M.dti(p, g)
        T, S, MM = r["tpw"], r["mass"], r["m_covers"]
        red = T / (0.2 * (T + S - MM) + 0.8 * r["n_truth"])
        assert r["dti"] == pytest.approx(red, abs=1e-12)
        assert r["reduced"] == pytest.approx(r["dti"], abs=1e-12)


def test_single_pixel_case_is_exactly_the_kernel_weight():
    """|G| = 1 and one emitted pixel: DTI = k(d) exactly, for any d.  Analytic, no numerics."""
    g = np.zeros((21, 21), dtype=bool)
    g[10, 10] = True
    for d_px, expect in [(0, 1.0), (1, 2 / 3), (2, 1 / 3), (3, 0.0)]:
        p = np.zeros_like(g, dtype=np.float64)
        p[10, 10 + d_px] = 1.0
        assert M.dti(p, g)["dti"] == pytest.approx(expect, abs=1e-12)
    p = np.zeros_like(g, dtype=np.float64)
    p[10 + 1, 10 + 1] = 1.0                       # d = sqrt(2) px
    assert M.dti(p, g)["dti"] == pytest.approx(1 - np.sqrt(2) / 3, abs=1e-12)


def test_bruteforce_matches_fast_implementation():
    rng = np.random.default_rng(11)
    for _ in range(4):
        g = (rng.random((24, 26)) < 0.06)
        p = np.where(rng.random((24, 26)) < 0.10, rng.choice([0.3, 0.7, 1.0]), 0.0)
        if not g.any() or not (p > 0).any():
            continue
        assert M.dti(p, g)["dti"] == pytest.approx(M.dti_bruteforce(p, g), abs=1e-9)


def _marginal_pieces(p, g, y, x):
    """(c, wmax) for adding one unit of mass at (y, x): c = sum of incremental truth credit,
    wmax = this pixel's best kernel weight.  Brute force over the kernel disc."""
    c = 0.0
    wmax = 0.0
    m, _, _ = M.max_cover(p, g)
    gi = np.argwhere(g)
    mfull = np.zeros(g.shape)
    mfull[tuple(gi.T)] = m
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            d = (dy * dy + dx * dx) ** 0.5 * M.PIXEL_M
            if d > M.R_M + 1e-9:
                continue
            yy, xx = y + dy, x + dx
            if not (0 <= yy < g.shape[0] and 0 <= xx < g.shape[1]) or not g[yy, xx]:
                continue
            k = 1.0 - d / M.R_M
            c += max(0.0, k - mfull[yy, xx])
            wmax = max(wmax, k)
    return c, wmax, float(m.sum())


def test_credit_bar_is_the_exact_marginal_condition():
    """The general marginal rule, verified pixel by pixel against the metric itself.

    Adding one unit at pixel x changes the numerator by c = sum over truth pixels of the
    incremental cover, and the denominator by (1-beta)*c + alpha*(1 - wmax).  So

        dDTI > 0  <=>  c * (1 - alpha*DTI) > alpha * DTI * (1 - wmax)

    which for a pixel covering exactly one uncovered truth pixel reduces to the credit bar
    ``w > alpha * DTI``.  Both the general form and the reduction are checked here.
    """
    rng = np.random.default_rng(3)
    g = np.zeros((60, 60), dtype=bool)
    # four isolated truth pixels, all pairwise further apart than the kernel support, so a
    # candidate pixel can cover at most one of them and the single-pixel reduction is exercised
    for (yy, xx) in [(10, 10), (10, 40), (40, 10), (40, 40)]:
        g[yy, xx] = True
    base_mask = np.zeros((60, 60), dtype=bool)
    base_mask[10, 40] = True                               # cover one of the four
    p0 = base_mask.astype(float)
    base = M.dti(p0, g)["dti"]
    assert base > 0
    bar = M.credit_bar(base)
    q0 = M.max_cover(p0, g)[1]
    cands = np.argwhere(~base_mask)
    picked = cands[rng.choice(len(cands), size=60, replace=False)]
    # also add the informative ones by hand: neighbours of an uncovered trace
    picked = np.vstack([picked, [[10, 11], [10, 12], [10, 13], [11, 10], [9, 9], [10, 41], [10, 42]]])
    n_single = 0
    for (y, x) in picked:
        c, wmax, _ = _marginal_pieces(p0, g, y, x)
        p1 = p0.copy()
        p1[y, x] = 1.0
        d = M.dti(p1, g)["dti"] - base
        pred = c * (1 - M.ALPHA * base) - M.ALPHA * base * (1 - wmax)
        assert np.sign(d) == np.sign(pred) or abs(d) < 1e-15, (y, x, c, wmax, pred, d)
        if c > 0 and abs(c - wmax) < 1e-12:          # single uncovered truth pixel
            assert np.sign(d) == np.sign(wmax - bar)
            n_single += 1
    assert n_single >= 5, "fixture too dense to exercise the single-pixel reduction"


def test_bigger_values_are_monotonically_better_on_a_fixed_support():
    """DTI is NOT scale-invariant: the 0.8*|G| term is a constant, so shrinking p only loses credit.

    This is why the emission problem here is a *placement* problem and why the optimum over the
    soft family is the {0,1} mask: for any pixel that is the best cover of a truth pixel with
    weight k > 0, d DTI / d p > 0, and for k = 0 any positive value only adds tax.
    """
    rng = np.random.default_rng(5)
    g = (rng.random((40, 40)) < 0.02)
    p = np.where(rng.random((40, 40)) < 0.05, 1.0, 0.0)
    a = M.dti(p, g)["dti"]
    assert a > 0
    assert M.dti(0.37 * p, g)["dti"] < a
    assert M.dti(0.9 * p, g)["dti"] < a
    # and on a one-dot case the monotonicity is exact and checkable analytically
    g2 = np.zeros((9, 9), dtype=bool)
    g2[4, 4] = True
    prev = -1.0
    for lam in (0.1, 0.25, 0.5, 0.75, 1.0):
        p2 = np.zeros((9, 9))
        p2[4, 5] = lam                                   # k = 2/3
        val = M.dti(p2, g2)["dti"]
        # analytic: T = lam*k, FPw = lam*(1-k), FNw = 1 - lam*k
        #       DTI = lam*k / (lam*k + 0.2*lam*(1-k) + 0.8*(1 - lam*k)) = lam*k / (0.2*lam + 0.8)
        assert val == pytest.approx(lam * (2 / 3) / (0.2 * lam + 0.8), abs=1e-12)
        assert val > prev
        prev = val


def test_no_wraparound_at_the_grid_edge():
    """A prediction in the last column must not cover a truth pixel in the first column."""
    g = np.zeros((10, 10), dtype=bool)
    g[5, 0] = True
    p = np.zeros((10, 10))
    p[5, 9] = 1.0
    assert M.dti(p, g)["dti"] == 0.0
