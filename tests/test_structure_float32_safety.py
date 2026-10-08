"""Regression tests for safe structure-tensor scaling at float32 extremes."""

import numpy as np

from gems52 import structure


def test_extreme_finite_field_does_not_overflow_tensor_products():
    rng = np.random.default_rng(20261007)
    field = (rng.normal(size=(96, 96)) * 1e30).astype(np.float32)
    valid = np.ones(field.shape, dtype=bool)

    with np.errstate(over="raise", invalid="raise", divide="raise"):
        result = structure.structure_tensor(field, valid, sigma_tensor_m=300.0)

    for values in result.values():
        assert np.isfinite(values).all()
    assert result["coherence"].min() >= 0.0
    assert result["coherence"].max() <= 1.0
    assert result["energy"].max() == np.finfo(np.float32).max


def test_subnormal_field_is_finite_and_does_not_create_nan_coherence():
    rng = np.random.default_rng(20261008)
    field = (rng.normal(size=(96, 96)) * 1e-40).astype(np.float32)
    valid = np.ones(field.shape, dtype=bool)

    with np.errstate(over="raise", invalid="raise", divide="raise"):
        result = structure.structure_tensor(field, valid, sigma_tensor_m=300.0)

    assert np.isfinite(result["coherence"]).all()
    assert result["coherence"].min() >= 0.0
    assert result["coherence"].max() <= 1.0
