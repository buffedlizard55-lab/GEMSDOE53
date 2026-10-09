"""Synthetic brute-force checks of src/gems53/c1.py (session 2). No competition data involved."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from gems53.c1 import (  # noqa: E402
    build_c1_features,
    orientation_agreement,
    robust_zscore,
    structure_tensor,
)


def _line_image(n=96, k=1, width=1.0):
    """k parallel diagonal (slope 1) lines on an n x n grid."""
    y, x = np.mgrid[0:n, 0:n]
    d = (x - y) % (n // (2 * k))
    img = np.exp(-0.5 * (np.minimum(d, (n // (2 * k)) - d) / width) ** 2)
    return img.astype(np.float64)


def test_structure_tensor_flat_is_zero():
    e, c, t, l1 = structure_tensor(np.ones((32, 32)), 1.0)
    assert float(np.abs(e).max()) < 1e-9
    assert float(np.abs(c).max()) < 1e-9


def test_structure_tensor_line_energy_peaks_on_line():
    img = _line_image()
    e, c, t, l1 = structure_tensor(img, 1.0)
    # the line is at (x - y) == 0 (mod 48); energy should be highest near it
    on = (np.abs((np.mgrid[0:96, 0:96][1] - np.mgrid[0:96, 0:96][0]) % 48) <= 1)
    off = ~on
    assert e[on].mean() > 3 * e[off].mean()
    # a single straight line is perfectly coherent where it has energy
    assert c[on].mean() > 0.8


def test_agreement_parallel_vs_perpendicular():
    fp = np.ones((96, 96), dtype=bool)
    # parallel identical fields -> gated agreement ~ +c*u (positive, large on bright lines)
    img = _line_image()
    e, c, t, _ = structure_tensor(img, 1.0)
    a_self = orientation_agreement(t, c, e, t, c, e, fp)
    assert a_self.max() > 0.4  # cos(0) * c*u, u=0.5 at median energy by construction
    # perpendicular field: reflect rows to turn slope +1 lines into slope -1 lines
    img_perp = _line_image()[::-1, :].copy()
    e2, c2, t2, _ = structure_tensor(img_perp, 1.0)
    a_perp = orientation_agreement(t, c, e, t2, c2, e2, fp)
    interior = np.s_[24:72, 24:72]
    # on the bright line pixels the gated agreement must approach cos(2*90deg) * c*u = -0.5
    bright = e[interior] > np.median(e[fp])
    assert bright.any() and a_perp[interior][bright].mean() < -0.35
    # between lines the energy gate drives the score toward 0, not toward noise
    assert np.abs(a_perp[interior][~bright]).mean() < 0.15


def test_agreement_noise_field_is_gated_to_zero():
    """A pure-noise 'field' next to a real line field must not produce spurious agreement."""
    fp = np.ones((96, 96), dtype=bool)
    img = _line_image()
    e, c, t, _ = structure_tensor(img, 1.0)
    rng = np.random.default_rng(7)
    noise = rng.normal(size=(96, 96))
    en, cn, tn, _ = structure_tensor(noise, 1.0)
    a = orientation_agreement(t, c, e, tn, cn, en, fp)
    a_rev = orientation_agreement(tn, cn, en, t, c, e, fp)
    # the noise field's energy is spatially flat -> its gate u ~ 1 is NOT suppressive, but
    # agreement with random orientations must average near zero over the interior.
    interior = np.s_[16:80, 16:80]
    assert abs(float(a[interior].mean())) < 0.05
    assert abs(float(a_rev[interior].mean())) < 0.05


def test_agreement_45deg_cross_is_neutral():
    fp = np.ones((96, 96), dtype=bool)
    img = _line_image()
    e1, c1, t1, _ = structure_tensor(img, 1.0)
    # rotate orientation by 45 degrees synthetically
    t2 = t1 + np.pi / 4
    a = orientation_agreement(t1, c1, e1, t2, c1, e1, fp)
    assert float(np.abs(a).max()) < 1e-6  # cos(90deg) = 0


def test_robust_zscore_and_imputation_path():
    x = np.array([[1.0, 2.0, 3.0, np.nan], [4.0, 5.0, 100.0, 6.0]])
    mask = np.isfinite(x)
    z, med, iqr = robust_zscore(x, mask)
    assert med == 4.0
    assert iqr == pytest.approx(3.0)  # numpy linear-interpolation quartiles of [1,2,3,4,5,6,100]
    # build_c1_features contract: 14 columns, footprint pixels only
    H, W, F = 12, 12, 19
    rng = np.random.default_rng(0)
    feats = rng.normal(size=(H * W, F)).astype(np.float32)
    fp = np.ones((H, W), dtype=bool)
    fp[:2, :] = False
    fp_idx = np.full((H, W), -1, dtype=np.int32)
    fp_idx[fp] = np.arange(int(fp.sum()))
    feats_sub = feats[: int(fp.sum())]
    X, names = build_c1_features(feats_sub, fp, fp_idx)
    assert X.shape == (int(fp.sum()), 14)
    assert len(names) == 14 and len(set(names)) == 14
    assert np.isfinite(X).all()  # random normal inputs contain no sentinel NaNs
