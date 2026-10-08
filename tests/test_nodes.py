"""Unit tests for the node-layer: NMS determinism, the tax identity, and metric parity.

The last test is the important one: ``nodes.node_dti`` is a *second* implementation of the official
metric (node-space form).  Two implementations of the same published formula are a liability unless
they are asserted equal, so they are, on random small fields, against ``gems52.metric.official_dti``.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems52 import metric as M
from gems52 import nodes as ND


def test_top_k_mask_selects_exactly_k_and_the_largest():
    rng = np.random.default_rng(0)
    f = rng.random((40, 50)).astype(np.float32)
    allowed = np.zeros((40, 50), dtype=bool)
    allowed[5:35, 5:45] = True
    m = ND.top_k_mask(f, allowed, 20)
    assert int(m.sum()) == 20
    assert np.all(np.isin(np.argwhere(m)[:, 0], np.arange(5, 35)))
    # any pixel outside the mask must beat every pixel inside it
    inside_min = f[m].min()
    outside_max = f[allowed & ~m].max()
    assert inside_min >= outside_max - 1e-12


def test_top_k_mask_is_a_noop_at_zero_budget():
    f = np.ones((8, 8), dtype=np.float32)
    assert ND.top_k_mask(f, np.ones((8, 8), dtype=bool), 0).sum() == 0


def test_local_maxima_is_deterministic_on_a_plateau():
    f = np.zeros((10, 10), dtype=np.float32)
    f[2:5, 2:5] = 1.0                      # a plateau: every pixel is a maximum
    allowed = np.ones_like(f, dtype=bool)
    m = ND.local_maxima(f, allowed, radius_px=1)
    assert int(m.sum()) == 1               # exactly one survivor
    assert tuple(np.argwhere(m)[0]) == (2, 2)


def test_local_maxima_keeps_separated_peaks():
    f = np.zeros((10, 10), dtype=np.float32)
    f[1, 1] = 1.0
    f[8, 8] = 1.0
    m = ND.local_maxima(f, np.ones_like(f, dtype=bool), radius_px=1)
    assert int(m.sum()) == 2


def test_tax_identity_matches_the_metric_definition():
    """tax == sum over emitted x of (1 - max_g k) must equal the published FPw, exactly."""
    rng = np.random.default_rng(1)
    shape = (60, 70)
    nodes = np.zeros(shape, dtype=bool)
    idx = rng.choice(shape[0] * shape[1], 25, replace=False)
    nodes.ravel()[idx] = True
    p = nodes.astype(np.float32)
    truth = np.zeros(shape, dtype=bool)
    tidx = rng.choice(shape[0] * shape[1], 12, replace=False)
    truth.ravel()[tidx] = True
    r = M.dti(p, truth)
    tax = ND.tax_of_nodes(nodes, truth)
    assert tax == pytest.approx(r["fpw"], rel=1e-9, abs=1e-9)


def test_node_dti_agrees_with_official_metric_on_random_fields():
    rng = np.random.default_rng(7)
    for trial in range(6):
        shape = (48, 52)
        p = (rng.random(shape) < 0.004).astype(np.float32)
        g = (rng.random(shape) < 0.006)
        ref = M.dti(p, g)
        got = ND.node_dti(p > 0, g)
        assert got["dti"] == pytest.approx(ref["dti"], rel=1e-9, abs=1e-12), f"trial {trial}"
        assert got["T"] == pytest.approx(ref["tpw"], rel=1e-9, abs=1e-9)


def test_node_dti_handles_an_empty_truth_mask():
    z = np.zeros((16, 16), dtype=bool)
    assert np.isnan(ND.node_dti(z, z)["dti"])


def test_spacing_stats_reports_the_dilation_tax_argument():
    nodes = np.zeros((30, 30), dtype=bool)
    nodes[5, 5] = nodes[5, 7] = nodes[5, 20] = True
    st = ND.spacing_stats(nodes)
    assert st["n"] == 3
    assert st["median_px"] == pytest.approx(2.0)     # 2, 2, 13 -> median 2 (nearest neighbour of the pair)
    assert st["share_within_2px"] == pytest.approx(2 / 3)
