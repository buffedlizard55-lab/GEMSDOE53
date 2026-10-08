import numpy as np
import pytest

from gems52.h55_paired_shoulders import paired_shoulder_features


def test_flat_surface_has_zero_direction_and_features():
    elevation = np.full((40, 50), 12.5, np.float32)
    valid = np.ones(elevation.shape, bool)
    features = paired_shoulder_features(elevation, valid)
    assert len(features) == 9
    assert all(value.shape == elevation.shape for value in features.values())
    assert all(np.isfinite(value).all() for value in features.values())
    assert all(np.count_nonzero(value) == 0 for value in features.values())


def test_planar_slope_has_zero_second_difference_and_balanced_sides():
    yy, xx = np.indices((64, 64), dtype=np.float32)
    elevation = 4.0 * xx + 2.0 * yy
    valid = np.ones(elevation.shape, bool)
    features = paired_shoulder_features(elevation, valid, offsets_px=(2,), sigma_px=0)
    second = features["B_h55_paired_second_difference_2"][10:-10, 10:-10]
    asymmetry = features["B_h55_paired_asymmetry_2"][10:-10, 10:-10]
    relief = features["B_h55_paired_balanced_relief_2"][10:-10, 10:-10]
    assert np.max(np.abs(second)) < 2e-4
    assert np.max(asymmetry) < 1e-5
    assert np.all(relief > 0)


def test_symmetric_bowl_has_positive_curvature_off_its_flat_minimum():
    yy, xx = np.indices((81, 81), dtype=np.float32)
    elevation = 0.02 * ((xx - 40) ** 2 + (yy - 40) ** 2)
    valid = np.ones(elevation.shape, bool)
    features = paired_shoulder_features(elevation, valid, offsets_px=(3,), sigma_px=0)
    center = (40, 40)
    point = (40, 41)
    assert all(value[center] == 0 for value in features.values())
    assert features["B_h55_paired_second_difference_3"][point] > 0
    assert features["B_h55_paired_balanced_relief_3"][point] > 0
    assert np.isfinite(features["B_h55_paired_asymmetry_3"][point])


def test_invalid_center_is_zero_and_output_is_finite():
    yy, xx = np.indices((48, 48), dtype=np.float32)
    elevation = xx + 0.5 * yy
    valid = np.ones(elevation.shape, bool)
    valid[24, 24] = False
    elevation[24, 24] = np.nan
    features = paired_shoulder_features(elevation, valid, offsets_px=(2, 4))
    assert all(np.isfinite(value).all() for value in features.values())
    assert all(value[24, 24] == 0 for value in features.values())


@pytest.mark.parametrize(
    "elevation,valid,kwargs",
    [
        (np.zeros((4, 4, 4)), np.ones((4, 4), bool), {}),
        (np.zeros((4, 4)), np.ones((3, 4), bool), {}),
        (np.zeros((4, 4)), np.ones((4, 4), bool), {"pixel_size_m": 0}),
        (np.zeros((4, 4)), np.ones((4, 4), bool), {"offsets_px": (0,)}),
        (np.zeros((4, 4)), np.ones((4, 4), bool), {"offsets_px": ()}),
    ],
)
def test_rejects_invalid_inputs(elevation, valid, kwargs):
    with pytest.raises(ValueError):
        paired_shoulder_features(elevation, valid, **kwargs)
