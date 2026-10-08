"""Synthetic regressions for the R3 paired-DEM-profile transform."""

import numpy as np
import pytest

from gems52.structural import paired_scarp_profile


def test_profile_features_are_bounded_finite_and_zero_off_footprint():
    n = 80
    y, x = np.mgrid[:n, :n]
    elev = (0.1 * x + 0.02 * y).astype(np.float32)
    valid = np.ones((n, n), bool)
    valid[:5, :7] = False
    elev[~valid] = np.nan

    concordance, asymmetry = paired_scarp_profile(elev, valid, tile_rows=13)

    for feature in (concordance, asymmetry):
        assert feature.shape == elev.shape
        assert np.isfinite(feature).all()
        assert feature.min() >= -1.0
        assert feature.max() <= 1.0
        assert np.all(feature[~valid] == 0.0)


def test_asymmetric_step_has_positive_flank_asymmetry_and_plane_does_not():
    n, center = 128, 64
    x = np.arange(n, dtype=np.float32)[None, :]
    y = np.zeros((n, n), np.float32)
    valid = np.ones_like(y, bool)

    asymmetric = np.broadcast_to(np.where(x < center, 0.2 * (x - center), 1.2 * (x - center)), y.shape).copy()
    plane = np.broadcast_to(0.7 * (x - center), y.shape).copy()

    _, asymmetric_profile = paired_scarp_profile(asymmetric, valid, tile_rows=29)
    plane_concordance, plane_asymmetry = paired_scarp_profile(plane, valid, tile_rows=29)

    assert asymmetric_profile[60, center] > 0.1
    assert plane_concordance[60, center] > 0.9
    assert abs(float(plane_asymmetry[60, center])) < 1e-4


def test_tiled_sampling_matches_single_tile_result():
    rng = np.random.default_rng(520206)
    elev = rng.normal(size=(73, 91)).astype(np.float32)
    valid = np.ones_like(elev, bool)
    valid[:4] = False
    elev[~valid] = np.nan

    tiled = paired_scarp_profile(elev, valid, tile_rows=11)
    whole = paired_scarp_profile(elev, valid, tile_rows=elev.shape[0])

    assert np.allclose(tiled[0], whole[0], atol=1e-7, rtol=1e-6)
    assert np.allclose(tiled[1], whole[1], atol=1e-7, rtol=1e-6)


def test_invalid_profile_arguments_fail_closed():
    elev = np.ones((16, 16), np.float32)
    valid = np.ones_like(elev, bool)
    with pytest.raises(ValueError, match="same-shaped"):
        paired_scarp_profile(elev, valid[:8])
    with pytest.raises(ValueError, match="positive"):
        paired_scarp_profile(elev, valid, offset_px=0)
    with pytest.raises(ValueError, match="tile_rows"):
        paired_scarp_profile(elev, valid, tile_rows=0)
    with pytest.raises(ValueError, match="3x3"):
        paired_scarp_profile(np.ones((2, 8), np.float32), np.ones((2, 8), bool))
