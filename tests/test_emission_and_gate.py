"""Tests for the shared-tool additions of session 3 (2026-10-08):
  * kernel_to_gt / dti_with_kernel must reproduce dti() exactly (the refactor must not change the metric);
  * the emission variants must stay in [0, 1] and keep the intended value shape;
  * the 3-px disk dilation used by the uniqueness gate must equal the EDT rule (d <= 3).
"""
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from gems53.core import (  # noqa: E402
    dti,
    dti_with_kernel,
    emission_from_probability,
    kernel_to_gt,
    top_q_mask,
)
from uniqueness_check import disk_structure  # noqa: E402


def test_kernel_refactor_matches_dti_on_random_grids():
    rng = np.random.default_rng(1)
    for trial in range(5):
        H, W = 17, 15
        gt = rng.random((H, W)) < 0.05
        if not gt.any():
            gt[4, 4] = True
        p = np.where(rng.random((H, W)) < 0.4, rng.random((H, W)), 0.0)
        a = dti(p, gt)
        b = dti_with_kernel(p, gt, kernel_to_gt(gt))
        for key in ("TP_w", "FP_w", "FN_w", "DTI"):
            assert abs(a[key] - b[key]) < 1e-9, (trial, key)


def test_emission_variants_stay_in_0_1_and_keep_order():
    rng = np.random.default_rng(2)
    p = rng.random((40, 50)).astype(np.float32)
    cand = np.zeros((40, 50), bool)
    cand[10:30, 10:40] = True
    keep = top_q_mask(p, cand, 0.1, 40 * 50)
    assert keep.any() and keep.sum() <= int(round(0.1 * 40 * 50)) + 40  # ties can add a few
    for variant in ("raw", "bin", "rank", "sqrt"):
        e = emission_from_probability(p, keep, variant)
        assert e.min() >= 0.0 and e.max() <= 1.0, variant
        assert np.count_nonzero(e) == int(keep.sum()), variant
        assert (e[keep] > 0).all(), variant
    e_bin = emission_from_probability(p, keep, "bin")
    assert (e_bin[keep] == 1.0).all()
    e_rank = emission_from_probability(p, keep, "rank")
    assert abs(float(e_rank[keep].max()) - 1.0) < 1e-6
    # rank preserves the model order
    vals = p[keep]
    r = e_rank[keep]
    order_v = np.argsort(vals, kind="stable")
    order_r = np.argsort(r, kind="stable")
    assert (order_v == order_r).all()
    # raw keeps the probability, everything else is 0
    e_raw = emission_from_probability(p, keep, "raw")
    assert np.allclose(e_raw[keep], p[keep])
    assert (e_raw[~keep] == 0).all()


def test_top_q_mask_empty_when_q_zero():
    p = np.ones((10, 10), np.float32)
    cand = np.ones((10, 10), bool)
    assert not top_q_mask(p, cand, 0.0, 100).any()


def test_disk_dilation_equals_edt_within_3px():
    rng = np.random.default_rng(3)
    dots = rng.random((60, 70)) < 0.02
    disk = disk_structure(3)
    near_dil = ndimage.binary_dilation(dots, structure=disk)
    d = ndimage.distance_transform_edt(~dots)
    near_edt = d <= 3
    assert (near_dil == near_edt).all()
    # the disk has 29 pixels (Euclidean radius 3)
    assert int(disk.sum()) == 29
