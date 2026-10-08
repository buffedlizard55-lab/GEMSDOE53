import numpy as np

from gems52.h55 import compute_h55_features, signed_log_edge


def test_signed_log_edge_detects_step_and_keeps_both_polarities():
    yy, xx = np.mgrid[:80, :80]
    step = (xx >= 40).astype(np.float32)
    valid = np.ones(step.shape, bool)
    lap, edge, nx, ny, crossing = signed_log_edge(step, valid, sigma=3)

    assert lap.dtype == np.float32
    assert edge.dtype == np.float32
    assert crossing[:, 36:44].any()
    assert edge[:, 36:44].max() > 0
    assert np.isfinite(nx).all() and np.isfinite(ny).all()
    assert np.allclose(np.hypot(nx, ny)[np.hypot(nx, ny) > 0], 1.0)


def test_zero_crossing_edge_is_zero_for_constant_and_masked_cells():
    a = np.full((48, 52), 7.0, np.float32)
    valid = np.ones(a.shape, bool)
    valid[:5, :] = False
    a[:5, :] = np.nan
    lap, edge, nx, ny, crossing = signed_log_edge(a, valid, sigma=1)

    assert not crossing.any()
    for channel in (lap, edge, nx, ny):
        assert np.isfinite(channel).all()
        assert not channel[~valid].any()


def test_h55_pair_features_require_coincident_edges_and_are_finite():
    yy, xx = np.mgrid[:96, :96]
    gravity = (xx >= 43).astype(np.float32) * 100.0
    # Opposite field polarity still describes the same unoriented edge axis.
    rtp = (xx >= 43).astype(np.float32) * -60.0
    cover = np.full(xx.shape, 1400.0, np.float32)
    slope = np.full(xx.shape, 2.0, np.float32)
    valid = np.ones(xx.shape, bool)

    features = compute_h55_features(gravity, rtp, cover, slope, valid)
    pair = features["h55_grav_rtp_edge_pair_s3"]
    alignment = features["h55_grav_rtp_normal_agreement_s3"]
    conditioned = features["h55_grav_rtp_edge_pair_cover_quiet_s3"]

    assert len(features) == 11
    assert all(x.shape == valid.shape and np.isfinite(x).all() for x in features.values())
    assert pair[:, 38:48].max() > 0
    assert alignment[:, 38:48].max() > 0.99
    assert conditioned[:, 38:48].max() > pair[:, 38:48].max()
    assert not pair[:, :30].any()


def test_h55_rejects_unregistered_scales_and_shape_mismatch():
    a = np.zeros((12, 12), np.float32)
    with np.testing.assert_raises(ValueError):
        compute_h55_features(a, a, a, a, np.ones_like(a, bool), sigmas=(1, 2))
    with np.testing.assert_raises(ValueError):
        signed_log_edge(a, np.ones((11, 12), bool), sigma=1)
