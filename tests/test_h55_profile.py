import numpy as np

from gems52.structural import normal_profile


def test_normal_profile_recovers_step_and_is_finite_on_valid_domain():
    yy, xx = np.mgrid[:81, :81]
    dem = np.where(xx >= 40, 120.0, 0.0).astype(np.float32)
    valid = np.ones(dem.shape, dtype=bool)
    valid[:5, :] = False
    valid[-5:, :] = False
    valid[:, :5] = False
    valid[:, -5:] = False
    features = normal_profile(dem, valid, sigma=1.5, offset_px=3.0, tangent_px=3.0)

    assert len(features) == 4
    assert all(feature.shape == dem.shape for feature in features)
    assert all(np.isfinite(feature).all() for feature in features)
    assert all(np.all(feature[~valid] == 0) for feature in features)
    assert np.max(features[0][30:51, 37:44]) > 20.0
    assert np.max(features[1][30:51, 37:44]) > 1.0
    assert np.max(features[3][30:51, 37:44]) > 20.0


def test_normal_profile_is_flat_for_a_planar_surface():
    yy, xx = np.mgrid[:51, :51]
    dem = (2.0 * xx + 3.0 * yy).astype(np.float32)
    valid = np.ones(dem.shape, dtype=bool)
    features = normal_profile(dem, valid, sigma=1.0, offset_px=3.0, tangent_px=2.0)
    assert np.max(np.abs(features[0][8:-8, 8:-8])) < 1e-3
    assert np.max(features[1][8:-8, 8:-8]) < 1e-3
    assert np.max(features[2][8:-8, 8:-8]) < 1e-3
    assert np.max(features[3][8:-8, 8:-8]) < 1e-3


def test_registered_normal_profile_offsets_generate_all_scale_channels():
    yy, xx = np.mgrid[:81, :81]
    dem = np.where(xx >= 40, 120.0, 0.0).astype(np.float32)
    valid = np.ones(dem.shape, dtype=bool)
    features = normal_profile(dem, valid, offsets_px=(1, 2, 3, 4, 6))
    assert len(features) == 20
    assert all(np.isfinite(feature).all() for feature in features)
    assert all(np.max(np.abs(feature)) > 0 for feature in features)
