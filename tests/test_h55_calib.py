"""Tests for the H55 calibration: the kernel constant, the sparse identity, and the |G| bound.

Every test here is a *derivation check*, not a smoke test: the number asserted is one that a
placement decision downstream depends on, so if it moves the decision must be re-made.
"""

from __future__ import annotations

import numpy as np
import pytest

from gems52 import metric as M
from gems55 import calib


def test_kernel_disc_weight_sum_is_exact_enumeration():
    """9.380298 is the ceiling on A/S; it is enumerated, never approximated by an integral."""
    tot = sum(k for _, _, k in calib.OFFSETS)
    assert tot == pytest.approx(9.380297810508182, abs=1e-12)
    assert len(calib.OFFSETS) == 29                    # k >= 0
    assert sum(1 for _, _, k in calib.OFFSETS if k > 0) == 25   # k > 0
    assert calib.kernel_disc_sum() == pytest.approx(tot)


def test_kernel_matches_the_tested_metric_module_offset_for_offset():
    """The H55 kernel is the same lattice as src/gems52/metric.py, which tests/test_metric.py pins
    against the organiser's own worked example."""
    a = {(dy, dx): round(k, 12) for dy, dx, k in calib.OFFSETS}
    b = {(dy, dx): round(k, 12) for dy, dx, k in M.OFFSETS}
    assert a == b


def test_grey_dilate_of_one_pixel_is_the_kernel_itself():
    e = np.zeros((15, 15), bool)
    e[7, 7] = True
    K = calib.grey_dilate(e)
    assert K[7, 7] == pytest.approx(1.0)
    assert K[7, 8] == pytest.approx(1 - 1 / 3)          # d = 1 px
    assert K[7, 9] == pytest.approx(1 - 2 / 3)          # d = 2 px
    assert K[7, 10] == 0.0                              # d = 3 px -> k = 0
    assert K[8, 8] == pytest.approx(1 - np.sqrt(2) / 3)  # d = sqrt(2)
    assert K[9, 9] == pytest.approx(1 - 2 * np.sqrt(2) / 3)
    assert K[10, 10] == 0.0                             # d = 3*sqrt(2) > 3
    assert K.sum() == pytest.approx(calib.kernel_disc_sum(), abs=1e-4)


def test_grey_dilate_does_not_wrap_at_the_grid_edge():
    """A wrapped edge would invent a fault 40 m from one boundary adjacent to one 40 m from the
    other -- the regression transform.py documents for np.roll."""
    e = np.zeros((9, 9), bool)
    e[0, 0] = True
    K = calib.grey_dilate(e)
    assert K[0, 8] == 0.0 and K[8, 0] == 0.0 and K[8, 8] == 0.0
    e2 = np.zeros((9, 9), bool)
    e2[0, 8] = True
    assert calib.grey_dilate(e2)[0, 0] == 0.0


def test_grey_dilate_equals_max_cover_for_a_single_truth_pixel():
    """K(x) is exactly the metric's max_cover when the truth is one pixel -- the identity that makes
    A a legitimate proxy for T and the whole calibration possible."""
    e = np.zeros((40, 40), bool)
    e[10, 12] = True
    e[25, 30] = True
    e[25, 31] = True
    g = np.zeros((40, 40), bool)
    g[20, 20] = True
    K = calib.grey_dilate(e)
    assert K[20, 20] == pytest.approx(M.max_cover(g.astype(np.float32), e)[1][20, 20], abs=1e-6)


def test_sparse_identity_reduces_the_metric_to_two_terms():
    """With M == T the published DTI collapses to T/(0.2*S + 0.8*|G|).  This single line is what
    lets one (raster, score) pair bound |G|, so it is tested rather than asserted."""
    rng = np.random.default_rng(0)
    for _ in range(4):
        n_g = int(rng.integers(50, 200))
        G = np.zeros((120, 120), bool)
        idx = rng.choice(120 * 120, size=n_g, replace=False)
        G.ravel()[idx] = True
        E = np.zeros((120, 120), bool)
        idx = rng.choice(120 * 120, size=6 * n_g, replace=False)
        E.ravel()[idx] = True
        r = M.dti(E.astype(np.float32), G)
        T, S, Mv = r["tpw"], r["mass"], r["m_covers"]
        assert r["n_truth"] == n_g
        if abs(Mv - T) > 1e-6:            # not a sparse realisation; the identity does not apply
            continue
        assert r["dti"] == pytest.approx(T / (0.2 * S + 0.8 * n_g), rel=1e-9)
        assert r["reduced"] == pytest.approx(T / (0.2 * S + 0.8 * n_g), rel=1e-9)
        assert calib.dti_from(T, S, n_g) == pytest.approx(r["dti"], rel=1e-9)


def test_implied_truth_inverts_the_sparse_identity():
    n_g, S, T = 8129.0, 37654.0, 3898.6
    dti = calib.dti_from(T, S, n_g)
    assert calib.implied_truth(dti, S, n_g) == pytest.approx(T, rel=1e-6)


def test_lower_bound_is_saturated_by_its_own_construction():
    """|G| >= 0.2*DTI*S/(1-0.8*DTI) comes from T <= |G|; at equality the bound is exact."""
    for dti, S in ((0.2778, 37654.0), (0.1563, 227507.0), (0.0904, 206895.0)):
        n_g = calib.lower_bound_n_g(dti, S)
        T = calib.implied_truth(dti, S, n_g)
        assert T == pytest.approx(n_g, rel=1e-9)
        assert calib.dti_from(T, S, n_g) == pytest.approx(dti, rel=1e-9)
        # any smaller |G| would need T > |G|, which is impossible
        assert calib.implied_truth(dti, S, n_g * 0.999) > n_g * 0.999


def test_spacing_curve_peaks_between_500_and_600_metres():
    """The claim in knowledge/07 H55-5: for a straight trace, credited mass per emitted pixel peaks
    at s = 5-6 px, not at s = 1 (solid) and not at s = 2-3 (the family's 'dotted' spacing)."""
    curve = calib.emission_efficiency_curve()
    best = max(curve, key=lambda s: curve[s]["T_per_S"])
    assert best in (5, 6), curve
    assert curve[best]["T_per_S"] > 1.7 * curve[2]["T_per_S"]
    assert curve[best]["T_per_S"] > 2.8 * curve[1]["T_per_S"]
    # A/S saturates at the disc weight sum once the discs stop overlapping
    for s in (5, 6, 7, 8):
        assert curve[s]["A_per_S"] == pytest.approx(calib.kernel_disc_sum(), rel=1e-3)
    assert curve[1]["A_per_S"] < 0.5 * calib.kernel_disc_sum()


def test_geometry_flags_contiguous_files_as_not_sparse():
    """The calibration only trusts rows whose emission is 8-isolated; the sparsity test must be the
    one that decides, or a contiguous file silently biases |G| high."""
    e = np.zeros((30, 30), bool)
    e[10, 10] = True
    e[15, 20] = True
    g = calib.geometry(e, np.ones((30, 30), bool))
    assert g["isolated"] and g["max_component"] == 1
    e[10, 11] = True
    g2 = calib.geometry(e, np.ones((30, 30), bool))
    assert not g2["isolated"] and g2["max_component"] == 2
    assert g2["A_per_S"] < g["A_per_S"]                 # overlap costs coverage per pixel


def test_geometry_ignores_mass_outside_the_footprint():
    e = np.zeros((30, 30), bool)
    e[5, 5] = True
    foot = np.zeros((30, 30), bool)
    foot[10:, 10:] = True
    g = calib.geometry(e, foot)
    assert g["S"] == 0 and g["A"] == 0.0
