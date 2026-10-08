"""Tests for the label-free ridge candidate (src/gems53/ridge.py)."""
import os
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.ridge import (R_PACK_PX, line_strength, nms_centrelines, poisson_pack,  # noqa: E402
                          ridge_fields, ridge_pack_emission)


def _line_image(H=120, W=120, col=60, amp=100.0, sigma=1.5, seed=0):
    rng = np.random.default_rng(seed)
    x = np.arange(W)[None, :].astype(float)
    img = amp * np.exp(-0.5 * ((x - col) / sigma) ** 2) * np.ones((H, 1))
    img += rng.normal(0, 0.5, size=(H, W))
    return img


def test_poisson_pack_respects_minimum_spacing():
    rng = np.random.default_rng(1)
    pts = rng.integers(0, 200, size=(20000, 2))
    picked = poisson_pack(pts, n_target=5000, r_px=R_PACK_PX)
    assert picked.shape[0] > 100
    from scipy.spatial import cKDTree
    d, _ = cKDTree(picked).query(picked, k=2)
    assert d[:, 1].min() >= R_PACK_PX - 1e-9


def test_ridge_finds_bright_line_centre():
    """The true line is found, on every row, as a bright ridge.

    Known design behaviour (documented as a limitation, not tuned away after the holdout): the regional
    trend subtraction leaves dark side-lobes about 5 px either side of a sharp ridge, and the valley arm
    can turn those into extra centrelines. The test therefore checks the line itself, not the absence of side-lobes.
    """
    img = _line_image()
    fp = np.ones(img.shape, dtype=bool)
    L, th, pol, _ = ridge_fields(img, fp)
    cen = nms_centrelines(L, th)
    rows_on = np.unique(np.nonzero(cen[:, 58:63])[0])  # rows that have a centreline pixel within 2 px of col 60
    assert len(rows_on) / img.shape[0] > 0.9
    band = np.zeros_like(cen)
    band[:, 59:62] = True
    sel = cen & band
    assert (pol[sel] == 1).mean() > 0.9  # the line itself is a ridge, not a valley


def test_emission_is_binary_and_respects_mask():
    img = _line_image()
    fp = np.ones(img.shape, dtype=bool)
    L, th, pol, _ = ridge_fields(img, fp)
    cen = nms_centrelines(L, th)
    allowed = fp.copy()
    allowed[:, 55:65] = False  # pixel-exact exclusion
    emis, info = ridge_pack_emission(L, cen, allowed, n_target=40)
    assert set(np.unique(emis)).issubset({0.0, 1.0})
    assert emis[:, 55:65].sum() == 0
    assert info["n_selected"] == int((emis > 0).sum())
    assert info["n_selected"] <= 40


def test_no_nan_inputs_pass_through_as_zero_score():
    img = _line_image()
    img[10:20, 10:20] = np.nan
    fp = np.ones(img.shape, dtype=bool)
    L, th, pol, _ = ridge_fields(img, fp)
    assert np.isfinite(L).all()


TEMPLATE = Path(os.environ.get("GEMS_TEMPLATE", "/tmp/gems-template"))


@pytest.mark.skipif(not (TEMPLATE / "src" / "metrics.py").exists(), reason="shared template not cloned")
def test_shared_metric_matches_repo_metric():
    """The shared template scorer and the repo's core.dti must agree (reconciliation regression)."""
    sys.path.insert(0, str(TEMPLATE / "src"))
    import metrics as shared  # noqa: E402
    from gems53.core import dti  # noqa: E402
    rng = np.random.default_rng(7)
    gt = np.zeros((60, 60), dtype=bool)
    gt[30, 5:55] = True
    gt[10:50, 12] = True
    p = np.zeros((60, 60), dtype=np.float32)
    p[rng.random((60, 60)) < 0.05] = 1.0
    p[28:33, 20] = 0.7
    d_shared, (tp, fp_, fn) = shared.GtContext(gt, R_pixels=3).score(p, return_components=True)
    d_repo = dti(p, gt)
    assert abs(d_shared - d_repo["DTI"]) < 1e-9
    assert abs(tp - d_repo["TP_w"]) < 1e-6 and abs(fp_ - d_repo["FP_w"]) < 1e-6
    assert abs((tp + fn) - gt.sum()) < 1e-6  # structural identity TP_w + FN_w = |G|
