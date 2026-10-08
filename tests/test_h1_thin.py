"""Checks for H1 (segment-exact distance) and M1 (greedy dominating thinning).

Each check compares the vectorised implementation with a literal brute-force computation on a small grid,
so a mistake in the windowing or the greedy loop cannot pass silently.
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import (  # noqa: E402
    DIST_CAP_PX,
    R_PX,
    dti,
    greedy_dominating_dots,
    load_template_module,
    h1_segment_exact_distance,
    thin_emission,
)


def _brute_h1(visible, seg_label, cap=DIST_CAP_PX):
    """Literal definition: distance to visible faults not in the pixel's own segment (if on a visible segment)."""
    H, W = visible.shape
    vis_pts = list(zip(*np.nonzero(visible)))
    out = np.zeros((H, W), dtype=np.float64)
    for y in range(H):
        for x in range(W):
            own = seg_label[y, x]
            on_visible_segment = visible[y, x] and own > 0
            pts = [p for p in vis_pts if not (on_visible_segment and seg_label[p] == own)]
            if not pts:
                d = math.inf
            else:
                d = min(math.hypot(y - py, x - px) for py, px in pts)
            out[y, x] = math.log1p(min(d, cap))
    return out


def test_h1_matches_bruteforce_on_random_grid():
    rng = np.random.default_rng(7)
    H, W = 40, 45
    cat = np.zeros((H, W), dtype=bool)
    # a few random short "faults" (random walks), some touching each other
    for _ in range(6):
        y, x = rng.integers(0, H), rng.integers(0, W)
        for _ in range(int(rng.integers(3, 12))):
            cat[y % H, x % W] = True
            y += int(rng.integers(-1, 2))
            x += int(rng.integers(-1, 2))
    seg, n = ndimage.label(cat, structure=np.ones((3, 3), dtype=int))
    assert n >= 2
    # H1 contract: visible = union of WHOLE segments (segments are either visible or withheld)
    keep_ids = np.flatnonzero(rng.random(n + 1) < 0.7)
    keep_ids = np.union1d(keep_ids, [1])            # segment 1 is always visible
    visible = cat & np.isin(seg, keep_ids[keep_ids > 0])
    got = h1_segment_exact_distance(visible, seg, cap=DIST_CAP_PX).astype(np.float64)
    want = _brute_h1(visible, seg, cap=DIST_CAP_PX)
    assert np.allclose(got, want, atol=1e-6), float(np.abs(got - want).max())


def test_h1_self_exclusion_is_real():
    """A visible segment's own pixels must not see that segment (their feature is not 0)."""
    H, W = 20, 20
    cat = np.zeros((H, W), dtype=bool)
    cat[5, 2:18] = True                   # one long horizontal fault
    seg, _ = ndimage.label(cat, structure=np.ones((3, 3), dtype=int))
    got = h1_segment_exact_distance(cat, seg)
    assert np.all(got[5, 2:18] == np.float32(np.log1p(DIST_CAP_PX)))   # no other visible fault -> capped
    assert got[0, 0] == np.float32(np.log1p(math.hypot(5, 2)))         # background sees the fault


def test_greedy_dots_are_separated_and_dominating():
    rng = np.random.default_rng(3)
    H, W = 30, 30
    cand = rng.random((H, W)) < 0.25
    rr, cc = np.nonzero(cand)
    vals = rng.random(rr.size)
    keep = greedy_dominating_dots(rr, cc, vals, (H, W), R_PX)
    kr, kc = rr[keep], cc[keep]
    # pairwise separation strictly greater than R
    for i in range(kr.size):
        for j in range(i + 1, kr.size):
            assert math.hypot(kr[i] - kr[j], kc[i] - kc[j]) > R_PX
    # every candidate is within R of a kept dot (dominating)
    for r, c in zip(rr, cc):
        assert np.min(np.hypot(kr - r, kc - c)) <= R_PX + 1e-9


def test_thin_emission_selects_top_q_and_values():
    rng = np.random.default_rng(11)
    p = rng.random((25, 25)).astype(np.float32)
    cand = np.ones_like(p, dtype=bool)
    em_p, n_kept, n_sel = thin_emission(p, cand, q=0.2, footprint_px=p.size, value="p")
    em_b, n_kept_b, _ = thin_emission(p, cand, q=0.2, footprint_px=p.size, value="bin")
    assert n_sel == int(round(0.2 * p.size)) and n_kept == n_kept_b
    assert np.count_nonzero(em_p) == n_kept and np.count_nonzero(em_b) == n_kept
    assert set(np.unique(em_b[em_b > 0]).tolist()) == {1.0}
    assert float(em_p.min()) >= 0.0 and float(em_p.max()) <= 1.0


def test_core_dti_matches_template_metric_when_available():
    """Parity with the shared template metric (src/metrics.py) on random arrays."""
    try:
        tm = load_template_module("metrics")
    except FileNotFoundError:
        return  # template not cloned in this environment; the run card records whether parity was executed
    rng = np.random.default_rng(5)
    for _ in range(3):
        gt = rng.random((60, 70)) < 0.03
        pred = np.where(rng.random((60, 70)) < 0.2, rng.random((60, 70)), 0.0).astype(np.float32)
        a = dti(pred, gt)["DTI"]
        b = tm.compute_distance_weighted_tversky(pred, gt)
        b = float(b["DTI"]) if isinstance(b, dict) else float(b)
        assert abs(a - b) < 1e-5, (a, b)
