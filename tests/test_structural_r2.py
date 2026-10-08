"""Numerical and spatial regressions for the new R2 implementation."""

import numpy as np
import pytest

from gems52 import emit, metric, spatial, structural, gates


def test_normalized_smoothing_has_no_zero_fill_boundary_step():
    valid = np.ones((30, 30), bool)
    valid[:, :9] = False
    a = np.where(valid, 7.0, np.nan).astype(np.float32)
    out = structural.smooth(a, valid, 3)
    assert np.max(np.abs(out[valid] - 7)) < 1e-5


def test_signed_normals_distinguish_cover_anticorrelation():
    a = np.ones((4, 4), np.float32)
    zero = np.zeros_like(a)
    assert np.allclose(structural.cosine(a, zero, -a, zero), -1)
    assert np.allclose(structural.cosine(a, zero, a, zero), 1)
    assert np.allclose(structural.cosine(zero, zero, a, zero), 0)


def test_atomic_array_writer_rereads_numerical_bytes(tmp_path):
    path = tmp_path / 'idx.npy'
    a = np.arange(40000, dtype=np.int64) + 119154
    structural.save_array(path, a)
    assert np.array_equal(np.load(path), a)
    assert not path.with_suffix('.partial').exists()


def test_feature_index_corruption_fails_before_training(tmp_path):
    import json
    v = np.ones((8, 8), bool)
    np.save(tmp_path / 'valid.npy', v)
    idx = np.arange(64)
    idx[:10] = 0
    np.save(tmp_path / 'flat_idx.npy', idx)
    (tmp_path / 'manifest.json').write_text(json.dumps({'feature_names': []}))
    with pytest.raises(ValueError, match='mapping corrupted'):
        structural.FeatureStore(tmp_path)


def test_gain_field_matches_literal_kernel_at_all_edges():
    rho = np.arange(30, dtype=np.float32).reshape(5, 6) / 100
    expected = np.zeros_like(rho)
    for y in range(5):
        for x in range(6):
            for dy, dx, k in emit.OFFSETS:
                yy, xx = y + dy, x + dx
                if 0 <= yy < 5 and 0 <= xx < 6:
                    expected[y, x] += rho[yy, xx] * k
    assert np.allclose(emit.gain_field(rho, rho.shape), expected, atol=1e-6)


def test_fp_discount_is_not_always_one_for_empty_density():
    nb, kk = emit._neighbour_tables(np.array([15]), (6, 6))
    empty = np.zeros_like(kk)
    assert emit.expected_nearest_discount(empty, kk)[0] == 0
    rho = np.full_like(kk, 0.01)
    q = emit.expected_nearest_discount(rho, kk)[0]
    assert 0 < q < 0.2
    rho.fill(0)
    center = next(i for i, (dy, dx, _) in enumerate(emit.OFFSETS) if dy == dx == 0)
    rho[0, center] = 1
    assert emit.expected_nearest_discount(rho, kk)[0] == pytest.approx(1)


def test_cost_gate_can_reject_tiny_density():
    rho = np.full((9, 9), 1e-5, np.float32)
    out, receipt = emit.greedy_emit(rho, np.ones_like(rho, bool), 0.3774, 4, pool=81, log=lambda _: None)
    assert out.sum() == 0
    assert receipt['rejects_at_stop'] == 81


def test_fixed_budget_is_deterministic_and_does_not_wrap():
    rho = np.zeros((12, 12), np.float32)
    rho[6, 0] = 1
    allowed = np.ones_like(rho, bool)
    a, receipt = emit.greedy_emit(rho, allowed, 0, 2, pool=144, log=lambda _: None)
    b, _ = emit.greedy_emit(rho, allowed, 0, 2, pool=144, log=lambda _: None)
    assert np.array_equal(a, b)
    assert a[6, 0] == 1
    assert not a[:, -3:].any()
    # There is no marginal coverage left after the single certain truth is covered.
    assert receipt['emitted'] == 1


def test_full_original_components_not_split_between_training_and_truth():
    cat = np.zeros((120, 120), bool)
    cat[40, 12:95] = True  # crosses a quadrant boundary
    cat[90, 8:42] = True
    cat[90, 90:110] = True
    valid = np.ones_like(cat)
    seen_truth = np.zeros_like(cat)
    for f in spatial.folds(cat, valid, buffer_px=5):
        assert not (f['train'] & f['region']).any()
        assert not (f['train'] & f['held_all']).any()
        assert f['receipt']['shared_train_truth_components'] == 0
        assert f['receipt']['nearest_training_to_region_px'] > 5
        seen_truth |= f['truth']
    assert np.array_equal(seen_truth, cat)


def test_independence_uses_negatives_and_abandons_strong_error_correlation():
    rows = [dict(n_negatives=30, mse_A=i / 100, mse_B=i / 200, fpr_A=i / 200, fpr_B=i / 100) for i in range(30)]
    r = spatial.independence(rows)
    assert r['n_negative_predictions'] == 900
    assert r['measured'] and not r['allow_exchange']
    assert r['max_abs_correlation'] == pytest.approx(1)


def test_constant_or_empty_errors_never_establish_independence():
    r = spatial.independence([])
    assert not r['allow_exchange'] and not r['measured']
    rows = [dict(n_negatives=40, mse_A=0, mse_B=0, fpr_A=0, fpr_B=0) for _ in range(50)]
    r = spatial.independence(rows)
    assert not r['allow_exchange']
    assert r['tests']['negative_false_positive_rate']['spearman'] is None


def test_tie_aware_spearman_does_not_invent_order_of_equal_errors():
    r = spatial.correlations([1, 1, 2, 2], [1, 2, 1, 2])
    assert r['spearman'] == pytest.approx(0)


def test_negative_block_errors_reject_unfilled_nan_oof_grid():
    pa = np.full((80, 80), np.nan, np.float32)
    pb = pa.copy()
    neg = np.ones_like(pa, bool)
    assert spatial.negative_block_errors(pa, pb, neg, 0, (0.5, 0.5)) == []
    pa[:40, :40] = 0.25
    pb[:40, :40] = 0.5
    rows = spatial.negative_block_errors(pa, pb, neg, 0, (0.8, 0.8), side=40)
    assert len(rows) == 1 and rows[0]['n_negatives'] == 1600
    assert rows[0]['mse_A'] == pytest.approx(0.25 ** 2)


def test_pseudo_components_are_whole_and_receiver_abstains():
    donor = np.zeros((100, 100), np.float32)
    receiver = np.full_like(donor, 0.5)
    donor[10, 10:16] = 0.99
    donor[20, 47:53] = 0.99  # crosses a block edge: reject entire component
    donor[80, 10:16] = 0.99  # outside training
    receiver[10, 10] = 0.95  # this pixel is confidently opposite to abstention; cannot be exchanged
    train = np.ones_like(donor, bool)
    train[70:] = False
    ids, receipts = spatial.whole_pseudo_segments(donor, receiver, train, np.zeros_like(train), 0.9, 0.4, 0.8)
    assert len(ids) == 5
    assert train.ravel()[ids].all()
    assert np.all(receiver.ravel()[ids] <= 0.8)
    assert len(receipts) == 1


def test_metric_rejects_invalid_predicted_values():
    g = np.eye(6, dtype=bool)
    for value in [np.nan, np.inf, -0.1, 1.1]:
        p = np.zeros((6, 6)); p[0, 0] = value
        with pytest.raises(ValueError, match='finite'):
            metric.dti(p, g)


def test_reduced_metric_handles_nonstandard_coefficients_and_epsilon():
    p = np.eye(6, dtype=float) * 0.8
    g = np.eye(6, dtype=bool)
    r = metric.dti(p, g, alpha=0.3, beta=0.6, eps=1e-4)
    assert r['dti'] == pytest.approx(r['reduced'])


def test_diagonal_283m_clears_isolated_pixel_bar_at_02778():
    assert metric.kernel(np.sqrt(8) * 100) > metric.credit_bar(0.2778)


def test_every_prior_is_checked_not_just_first_eight(tmp_path):
    from test_gates import write_tif
    pred = np.zeros((6, 6), np.float32); pred[2, 2] = 1
    other = np.zeros_like(pred); other[5, 5] = 1
    priors = [write_tif(tmp_path, f'p{i}.tif', other) for i in range(9)]
    priors.append(write_tif(tmp_path, 'identical_tenth.tif', pred))
    r = gates.uniqueness_report(pred, priors, top=8)
    assert r['n_priors_checked'] == 10
    assert any(x['identical'] for x in r['per_prior'])
    assert not r['ok']


def test_same_shape_wrong_fixture_crs_is_rejected(tmp_path):
    from test_gates import write_tif
    a = np.zeros((6, 6), np.float32)
    sample = write_tif(tmp_path, 'sample.tif', a)
    bad = write_tif(tmp_path, 'bad.tif', a, crs='EPSG:4326')
    assert not gates.format_report(bad, sample)['ok']


def test_same_shape_wrong_fixture_transform_is_rejected(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    from test_gates import write_tif
    a = np.zeros((6, 6), np.float32)
    sample = write_tif(tmp_path, 'sample.tif', a)
    bad = write_tif(tmp_path, 'bad.tif', a)
    with rasterio.open(bad, 'r+') as dst:
        dst.transform = from_origin(1, 6, 1, 1)
    assert not gates.format_report(bad, sample)['ok']
