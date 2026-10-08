"""Tests for the H55 emitters: the hard-core rule, the coverage-greedy, and the credit bar.

The property that matters is not "it emits k pixels".  It is that the emitter does not spend budget
on a pixel whose 300 m disc another emitted pixel already covers, because under
``DTI = T/(0.2*S + 0.8*|G|)`` such a pixel pays the full 0.2 tax and can add nothing to ``T``.
``A/S`` -- kernel-weighted coverage per emitted pixel, ceiling 9.380298 -- is the measured form of
that property, and IR-52-024 records the family leaving 14-59 % of it unspent.
"""

from __future__ import annotations

import numpy as np
import pytest

from gems52 import metric as M
from gems55 import calib, emit_opt


def _grid(n=120, seed=0, density=0.002, blobs=0):
    """A belief field.  ``blobs > 0`` makes it *clustered*, which is what a real fitted field looks
    like and the only case in which top-K and hard-core disagree: on an i.i.d. field the top K values
    are already uniformly scattered, so a spacing rule has nothing to fix."""
    from scipy import ndimage
    rng = np.random.default_rng(seed)
    valid = np.ones((n, n), bool)
    valid[:2, :] = False                      # a footprint edge, so edge handling is exercised
    rho = rng.random((n, n)).astype(np.float32) ** 4 * density
    if blobs:
        spike = np.zeros((n, n), np.float32)
        idx = rng.choice(n * n, size=blobs, replace=False)
        spike.ravel()[idx] = 1.0
        rho = rho + density * 40.0 * ndimage.gaussian_filter(spike, 2.5).astype(np.float32)
    rho[~valid] = 0.0
    return valid, rho


def test_accept_bar_agrees_with_the_module_the_metric_tests_already_pin():
    from gems52 import emit as E
    for d in (0.0, 0.05, 0.2778, 0.3195, 0.3774, 0.5, 1.0):
        assert emit_opt.accept_bar(d) == pytest.approx(E.accept_bar(d), abs=1e-12)


def test_kernel_convolve_of_a_delta_is_the_kernel():
    d = np.zeros((21, 21), np.float32)
    d[10, 10] = 1.0
    C = emit_opt.kernel_convolve(d)
    assert C[10, 10] == pytest.approx(1.0)
    assert C[10, 11] == pytest.approx(1 - 1 / 3)
    assert C[10, 13] == 0.0
    assert C.sum() == pytest.approx(calib.kernel_disc_sum(), abs=1e-4)


def test_kernel_convolve_is_the_adjoint_of_the_dilate_for_disjoint_points():
    """sum_x rho(x) K_E(x) == sum_{y in E} C(y) when no two emitted pixels share a disc cell.
    That equality is why A can stand in for T in the calibration."""
    E = np.zeros((60, 60), bool)
    E[10, 10] = True
    E[40, 45] = True
    rho = np.random.default_rng(1).random((60, 60)).astype(np.float32)
    K = emit_opt.kernel_dilate(E)
    C = emit_opt.kernel_convolve(rho)
    assert float((rho * K).sum()) == pytest.approx(float(C[E].sum()), rel=1e-5)


def test_hardcore_thin_respects_budget_and_minimum_spacing():
    valid, rho = _grid(200, seed=2)
    em = emit_opt.hardcore_thin(rho, valid, 300, 4.0)
    assert int(em.sum()) == 300
    assert not (em & ~valid).any(), "emitted outside the permitted set"
    ys, xs = np.nonzero(em)
    d = np.hypot(ys[:, None] - ys[None, :], xs[:, None] - xs[None, :])
    np.fill_diagonal(d, np.inf)
    assert d.min() >= 4.0 - 1e-9


def test_hardcore_thin_reaches_the_coverage_ceiling():
    """At an exclusion radius of >= 2R the discs are disjoint, so A/S must hit 9.380298 minus
    footprint-edge loss.  This is the whole content of H55-5."""
    valid, rho = _grid(200, seed=3)
    em = emit_opt.hardcore_thin(rho, valid, 500, 6.0)
    g = calib.geometry(em, valid)
    assert g["A_per_S"] == pytest.approx(calib.kernel_disc_sum(), rel=0.02)
    assert g["isolated"]


def test_hardcore_beats_topk_on_coverage_at_identical_budget():
    """On a *clustered* field -- the case a fitted model actually produces -- rank order packs into
    the blob and pays tax on discs it has already covered.  This is IR-52-024 in miniature."""
    valid, rho = _grid(200, seed=4, blobs=6)
    k = 500
    tk = emit_opt.topk(rho, valid, k)
    hc = emit_opt.hardcore_thin(rho, valid, k, 5.0)
    assert calib.geometry(tk, valid)["A_per_S"] < calib.geometry(hc, valid)["A_per_S"]
    assert int(tk.sum()) == int(hc.sum()) == k


def test_topk_ignores_disallowed_and_nonfinite():
    valid, rho = _grid(80, seed=5)
    rho = rho.copy()
    rho[10, 10] = np.nan
    rho[11, 11] = np.inf
    em = emit_opt.topk(rho, valid, 50)
    assert int(em.sum()) == 50
    assert not em[10, 10] and not em[11, 11]
    assert not (em & ~valid).any()


def test_coverage_greedy_never_emits_outside_the_permitted_set():
    valid, rho = _grid(120, seed=6)
    dens = emit_opt.calibrate(rho, valid, 500.0)
    em, st = emit_opt.coverage_greedy(dens, valid, 0.0, n_g=500.0, max_emit=300, batch=200)
    assert not (em & ~valid).any()
    assert int(em.sum()) <= 300
    assert st["emitted"] == int(em.sum())


def test_coverage_greedy_is_monotone_in_budget():
    """T(E) is monotone submodular, so a larger budget cannot credit less."""
    valid, rho = _grid(140, seed=7)
    dens = emit_opt.calibrate(rho, valid, 800.0)
    prev = -1.0
    for k in (50, 150, 400, 900):
        em, st = emit_opt.coverage_greedy(dens, valid, 0.0, n_g=800.0, max_emit=k, batch=200)
        assert st["T_expected"] >= prev - 1e-6
        prev = st["T_expected"]


def test_coverage_greedy_stops_at_the_bar_when_the_bar_is_binding():
    """Endogenous budget on a *flat* belief, where the marginal gain of every pixel is exactly
    ``9.380298 * density`` and the stopping condition can be checked by hand:

        accept  <=>  gain > bar * (1 - C),  gain = C = 9.380298 * c,  bar = 0.2*d / (1 - 0.2*d)

    With |G| calibrated to 100 over a 120x120 footprint, c = 100/14400 and gain = 0.0651, so
    d = 0.30 (bar 0.0638) accepts and d = 0.40 (bar 0.1333) emits nothing at all.
    """
    n, n_g = 200, 298.5
    valid = np.ones((n, n), bool)
    flat = np.ones((n, n), np.float32)
    dens = emit_opt.calibrate(flat, valid, n_g)
    gain = calib.kernel_disc_sum() * n_g / (n * n)
    assert gain == pytest.approx(0.070, abs=1e-3)
    assert emit_opt.accept_bar(0.30) * (1 - gain) < gain < emit_opt.accept_bar(0.40) * (1 - gain)
    big, sb = emit_opt.coverage_greedy(dens, valid, 0.30, n_g=n_g, max_emit=200, batch=400)
    assert int(big.sum()) >= 150          # interior pixels all clear; edge pixels have truncated discs
    small, ss = emit_opt.coverage_greedy(dens, valid, 0.40, n_g=n_g, max_emit=200, batch=400)
    assert int(small.sum()) == 0
    assert ss["bar"] > sb["bar"]


def test_calibrate_makes_the_density_sum_to_the_believed_g():
    """Without this the bar and the gain are in different units and the stop is meaningless --
    the reason holdout.emission_from_field documents calibrate_to."""
    valid, rho = _grid(100, seed=9)
    dens = emit_opt.calibrate(rho, valid, 8129.0)
    assert float(dens[valid].sum()) == pytest.approx(8129.0, rel=1e-5)
    assert not dens[~valid].any()
    assert (dens >= 0).all()


def test_calibrate_of_an_empty_field_is_empty_not_nan():
    valid, _ = _grid(50, seed=10)
    z = np.zeros((50, 50), np.float32)
    dens = emit_opt.calibrate(z, valid, 1000.0)
    assert float(dens.sum()) == 0.0
    em, st = emit_opt.coverage_greedy(dens, valid, 0.3, max_emit=100)
    assert int(em.sum()) == 0 and st["reason"] == "empty density"


def test_calibrate_clips_negative_field_values():
    """A regionally-centred field is signed by construction; negative means below background, i.e.
    no expected mass, and must not be allowed to subtract credit from its neighbours."""
    valid, _ = _grid(60, seed=11)
    f = np.full((60, 60), -1.0, np.float32)
    f[30, 30] = 5.0
    dens = emit_opt.calibrate(f, valid, 100.0)
    assert (dens >= 0).all()
    assert float(dens.sum()) == pytest.approx(100.0, rel=1e-5)


def test_the_greedy_reaches_the_coverage_ceiling_and_beats_hardcore_on_its_own_objective():
    """Measured, both field shapes.

    On a flat or a clustered belief, at identical budget, the coverage-greedy reaches ~98 % of the
    A/S ceiling *and* banks ~20 % more rho-weighted coverage than a hard-core thinning of the same
    field, and ~33 % more than plain top-K.  It therefore dominates both, and the emitter that ships
    is the greedy with a bar, not a spacing heuristic.

    This test used to assert the opposite.  It was written against a version of ``coverage_greedy``
    in which ``np.maximum(cf[nbi], kk, out=cf[nbi])`` wrote the running cover into a throwaway copy
    (fancy indexing copies), so every later pixel looked uncovered, the greedy packed into the peak
    and reported A/S = 1.8-2.1 -- worse than top-K.  That was a bug, not a property of greedy
    coverage; IR-52-025 records the correction.
    """
    for blobs in (0, 5):
        valid, rho = _grid(160, seed=13, blobs=blobs)
        dens = emit_opt.calibrate(rho, valid, 1000.0)
        g_em, g_st = emit_opt.coverage_greedy(dens, valid, 0.0, n_g=1000.0, max_emit=400, batch=400)
        h_em = emit_opt.hardcore_thin(rho, valid, 400, 5.0)
        tk = emit_opt.topk(rho, valid, 400)
        gg, gh, gt = (calib.geometry(e, valid) for e in (g_em, h_em, tk))
        assert int(g_em.sum()) == int(h_em.sum()) == int(tk.sum()) == 400
        assert gg["A_per_S"] > 0.97 * calib.kernel_disc_sum()
        assert gg["max_component"] == 1                       # nothing adjacent: no wasted overlap
        cov = lambda e: float((dens * emit_opt.kernel_dilate(e)).sum())
        assert cov(g_em) > 1.10 * cov(h_em)          # greedy beats the spacing heuristic
        assert cov(h_em) > 1.02 * cov(tk)            # and the heuristic beats rank order
        assert cov(g_em) == pytest.approx(g_st["T_expected"], rel=0.02)


def test_the_greedy_banks_exactly_what_it_claims():
    """The telescoping identity: the sum of the recorded marginal gains equals the realised
    rho-weighted coverage of the emitted set.  If the running-cover bookkeeping is wrong this is the
    test that says so, and it is the test that caught the ``out=`` bug."""
    valid, rho = _grid(140, seed=7, blobs=3)
    dens = emit_opt.calibrate(rho, valid, 800.0)
    for k in (50, 150, 400, 900):
        em, st = emit_opt.coverage_greedy(dens, valid, 0.0, n_g=800.0, max_emit=k, batch=200)
        K = emit_opt.kernel_dilate(em)
        assert float((dens * K).sum()) == pytest.approx(st["T_expected"], rel=0.01)


def test_a_denser_emission_of_the_same_set_cannot_credit_more_than_the_truth_count():
    """T <= |G| always.  A placement rule that appears to break this is double-counting a truth
    pixel, which is the single bug class this whole module exists to avoid."""
    rng = np.random.default_rng(12)
    n = 100
    G = np.zeros((n, n), bool)
    G.ravel()[rng.choice(n * n, 60, replace=False)] = True
    for S in (60, 300, 2000, 8000):
        E = np.zeros((n, n), bool)
        E.ravel()[rng.choice(n * n, min(S, n * n), replace=False)] = True
        r = M.dti(E.astype(np.float32), G)
        assert r["tpw"] <= r["n_truth"] + 1e-9
        assert r["m_covers"] <= r["mass"] + 1e-9
