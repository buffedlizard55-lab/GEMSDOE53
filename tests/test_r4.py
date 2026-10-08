"""Round-4 regression tests.

Every test here corresponds to a defect that actually cost time, not to a coverage
target.  The docstrings say which one, because next session will not remember and the
failure mode is silent in most cases.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from gems52_r4 import arms as A          # noqa: E402
from gems52_r4 import bias as B          # noqa: E402
from gems52_r4 import cotraining as C    # noqa: E402
from gems52_r4 import instrument as I    # noqa: E402
from gems52_r4 import layers as L        # noqa: E402
from gems52_r4 import model as M         # noqa: E402
from gems52_r4 import reasoning as R     # noqa: E402


# --------------------------------------------------------------------------------------
# layers
# --------------------------------------------------------------------------------------

def test_layer_plan_has_declared_counts():
    """The view split is an assumption the model rests on; a silent change is a bug."""
    n_a = sum(1 for v in L.VIEW_OF.values() if v == "A")
    n_b = sum(1 for v in L.VIEW_OF.values() if v == "B")
    assert (n_a, n_b) == (30, 44), f"expected 30/44, found {n_a}/{n_b}"
    assert len(L.LAYER_NAMES) == len(set(L.LAYER_NAMES))


def test_undeclared_layer_raises():
    """Asking for a layer not in the plan must raise, not fall back to something else."""
    with pytest.raises(KeyError):
        L.layer_index("A_not_a_real_layer")


def test_band6_is_in_view_b():
    """Band 6 is radiometric total count, not a magnetic tilt derivative (IR-52-019/034)."""
    assert L.VIEW_OF["B_band6_TC"] == "B"


def test_regional_and_residual_reconstruct_the_field():
    a = np.random.default_rng(0).normal(size=(40, 40)).astype(np.float32)
    valid = np.ones((40, 40), dtype=bool)
    reg = L.regional_z(a, valid, 1000.0)
    res = a - reg
    assert np.isfinite(reg).all() and np.isfinite(res).all()
    assert np.allclose(res + reg, a, atol=1e-4), "residual + regional must be the field"
    assert abs(float(np.mean(res))) < 0.05, "the residual should carry no mean"


def test_structure_tensor_coherence_is_bounded():
    yy, xx = np.mgrid[0:64, 0:64]
    a = (np.sin(xx / 4.0) * 3.0 + yy * 0.1).astype(np.float32)
    valid = np.ones_like(a, dtype=bool)
    st = L.structure_tensor(a, valid, 300.0)
    assert np.nanmin(st["coherence"]) >= 0.0
    assert np.nanmax(st["coherence"]) <= 1.0


def test_distance_to_points_is_zero_at_a_point():
    shape = (30, 30)
    valid = np.ones(shape, dtype=bool)
    d = L.distance_to_points(np.array([5]), np.array([7]), shape, valid)
    assert d[5, 7] == pytest.approx(0.0)
    assert d[5, 8] == pytest.approx(100.0)


def test_distance_to_points_empty_is_nan_not_huge():
    shape = (10, 10)
    d = L.distance_to_points(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                             shape, np.ones(shape, dtype=bool))
    assert np.isnan(d).all(), "no data must read as NaN, not as 'very far'"


# --------------------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------------------

def test_gather_is_element_wise_not_a_cross_product():
    """np.ix_ with three arrays is a cross product: it asked numpy for 5.90 TiB."""
    st = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
    g = M.gather(st, np.array([0, 2]), np.array([1, 3]))
    assert g.shape == (2, 2)
    assert g.tolist() == [[1.0, 13.0], [11.0, 23.0]]


def test_gather_rejects_mismatched_index_shapes():
    st = np.zeros((2, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        M.gather(st, np.array([0, 1]), np.array([0]))


def test_blocked_auc_uses_within_block_ranks():
    """Global ranks inflated a perfectly separated block to 2.5 instead of 1.0."""
    bid = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    y = np.array([1, 1, 0, 0, 1, 1, 0, 0])
    perfect = M.blocked_auc(y, np.array([9, 8, 1, 0, 9, 8, 1, 0], float), bid, min_each=2)
    reversed_ = M.blocked_auc(y, np.array([0, 1, 8, 9, 0, 1, 8, 9], float), bid, min_each=2)
    tied = M.blocked_auc(y, np.ones(8), bid, min_each=2)
    assert perfect["mean_auc"] == pytest.approx(1.0)
    assert reversed_["mean_auc"] == pytest.approx(0.0)
    assert tied["mean_auc"] == pytest.approx(0.5)


def test_blocked_auc_skips_single_class_blocks():
    bid = np.array([0, 0, 0, 1, 1, 1])
    y = np.array([1, 1, 1, 0, 0, 0])
    r = M.blocked_auc(y, np.array([3, 2, 1, 6, 5, 4], float), bid, min_each=2)
    assert r["n_blocks_scored"] == 0
    assert r["n_blocks_skipped"] == 2, "a block with no evidence must not score 0.5"


def test_block_ids_marks_outside_as_minus_one():
    shape = (600, 600)
    valid = np.ones(shape, dtype=bool)
    valid[:100, :] = False
    b = M.block_ids(shape, valid, 20_000.0)
    assert (b[~valid] == -1).all()
    assert b[valid].min() == 0


def test_folds_cover_every_block():
    shape = (600, 600)
    valid = np.ones(shape, dtype=bool)
    b = M.block_ids(shape, valid, 20_000.0)
    f = M.make_block_folds(b, 5)
    assert set(np.unique(f[f >= 0])) == {0, 1, 2, 3, 4}


# --------------------------------------------------------------------------------------
# cotraining
# --------------------------------------------------------------------------------------

def test_rank_within_averages_ties():
    """LiDAR and radiometric layers are uint8; breaking ties by position is an artifact."""
    a = np.array([[1.0, 2.0, 2.0, 5.0]])
    r = C._rank_within(a, np.ones((1, 4), dtype=bool))
    assert r[0, 1] == r[0, 2], "tied values must receive the same rank"


def test_rank_within_excludes_nan_from_the_ranking():
    a = np.array([[1.0, np.nan, 3.0]])
    r = C._rank_within(a, np.ones((1, 3), dtype=bool))
    assert np.isnan(r[0, 1])
    assert np.isfinite(r[0, 0]) and np.isfinite(r[0, 2])


def test_whole_segment_folds_keep_truth_placeable():
    """Survival was 0.000 when the training buffer also shrank the emission mask."""
    cat = np.zeros((40, 40), dtype=bool)
    cat[5:10, 5:10] = True
    cat[25:30, 25:30] = True
    folds = C.whole_segment_folds(cat, np.ones((40, 40), dtype=bool), buffer_px=3, k=2)
    assert len(folds) == 2
    for f in folds:
        assert C.truth_survival(f) == pytest.approx(1.0)
        assert f["train_exclude"].sum() > f["truth"].sum(), "buffer must exceed the segment"


def test_block_error_table_ranks_over_pos_and_allowed():
    """Ranking over allowed alone removes the catalogue and the miss rate is all-NaN."""
    score = np.arange(16, dtype=float).reshape(4, 4)
    pos = np.zeros((4, 4), dtype=bool)
    pos[3, 2:] = True                       # the two highest scores
    allowed = np.ones((4, 4), dtype=bool)
    allowed[3, 2:] = False
    bid = np.zeros((4, 4), dtype=int)
    rows = C.block_error_table(score, pos, allowed, bid, budgets=(2, 4))
    for row in rows:
        assert row["mean_capture"] == pytest.approx(1.0)
        assert row["mean_miss_rate"] == pytest.approx(0.0)


def test_independence_verdict_fires_on_agreement():
    rng = np.random.default_rng(0)
    n = 4000
    bid = np.zeros(n, dtype=int)
    bid[n // 2:] = 1
    x = rng.random(n)
    v_id = C.independence_verdict(x, x + rng.normal(0, 0.01, n), bid)
    v_rand = C.independence_verdict(rng.random(n), rng.random(n), bid)
    assert v_id["independent"] is False
    assert v_rand["independent"] is True


# --------------------------------------------------------------------------------------
# instrument -- the budget confound
# --------------------------------------------------------------------------------------

def test_budget_confound_refuses_to_fabricate_a_null():
    """board monotone in budget leaves a zero-variance residual.

    The first implementation reported r=0.0, p=1.0 there, which reads as "no
    relationship" when the truth is that the relationship is perfect and inseparable
    from budget.
    """
    budget = np.arange(1, 11, dtype=float)
    board = 2.0 * budget
    x = np.array([5, 1, 9, 3, 7, 2, 8, 4, 6, 0], dtype=float)
    r = I.budget_confound(x, board, budget)
    assert r["degenerate"] is True
    assert r["r"] is None and r["p"] is None, "must not report 0.0/1.0 for a degenerate fit"


def test_budget_confound_recovers_a_real_relationship():
    rng = np.random.default_rng(1)
    n = 40
    budget = rng.uniform(1000, 70000, n)
    board = 0.3 * budget / 70000 + rng.normal(0, 0.05, n)
    x = board + rng.normal(0, 0.02, n)
    r = I.budget_confound(x, board, budget)
    assert r["degenerate"] is False
    assert r["r"] > 0.8


def test_budget_confound_reports_null_for_noise():
    rng = np.random.default_rng(2)
    n = 40
    budget = rng.uniform(1000, 70000, n)
    board = 0.3 * budget / 70000 + rng.normal(0, 0.05, n)
    r = I.budget_confound(rng.normal(0, 1, n), board, budget)
    assert r["degenerate"] is False
    assert abs(r["r"]) < 0.5


def test_random_control_declares_instrument_useless():
    rows = [{"name": "inc", "score": 0.052650, "board": 0.2778, "budget": 37654,
             "kind": "incumbent"},
            {"name": "r1", "score": 0.0513, "board": 0.0, "budget": 37654, "kind": "random"},
            {"name": "r2", "score": 0.0670, "board": 0.0, "budget": 70000, "kind": "random"}]
    v = I.validate(rows)
    assert v["random_control"]["random_beats_incumbent"] is True
    assert "CANNOT PROMOTE" in v["random_control"]["verdict"]


def test_pseudo_truth_is_density_matched():
    rng = np.random.default_rng(0)
    cat = np.zeros((200, 200), dtype=bool)
    cat[20:40, 20:40] = True
    cat[100:130, 100:130] = True
    valid = np.ones((200, 200), dtype=bool)
    for mode in ("dispersed", "clustered"):
        t = I.build_pseudo_truth(cat, valid, seed=7, mode=mode, target_px=3000)
        assert t["size_px"] == 3000, f"{mode} not matched: {t['size_px']}"
        assert t["n_hidden"] > 0 and t["moved_px"] > 0


def test_pseudo_truth_rejects_unknown_mode():
    cat = np.zeros((50, 50), dtype=bool)
    cat[10:20, 10:20] = True
    with pytest.raises(ValueError):
        I.build_pseudo_truth(cat, np.ones((50, 50), bool), mode="sideways")


def test_score_against_reports_budget():
    g = np.zeros((40, 40), dtype=bool)
    g[10:14, 10:14] = True
    p = np.zeros((40, 40))
    p[10:14, 10:14] = 1.0
    r = I.score_against(p, g)
    assert r["budget"] == 16
    assert r["dti"] > 0.0


# --------------------------------------------------------------------------------------
# arms
# --------------------------------------------------------------------------------------

def test_arm_names_are_unique_and_complete():
    assert len(A.arm_names()) == 18
    assert len(set(A.arm_names())) == 18


def test_every_arm_produces_a_finite_field():
    rng = np.random.default_rng(0)
    a = rng.random((30, 30)).astype(np.float32)
    b = rng.random((30, 30)).astype(np.float32)
    for name in A.arm_names():
        f = A.build_arm(name, a, b)
        assert f.shape == (30, 30)
        assert np.isfinite(f).all(), f"{name} produced non-finite values"
        assert float(np.nanstd(f)) >= 0.0


def test_undeclared_arm_raises():
    a = np.ones((10, 10), np.float32)
    with pytest.raises(KeyError):
        A.build_arm("not_an_arm", a, a)


def test_random_control_emits_exactly_the_budget():
    valid = np.ones((50, 50), dtype=bool)
    valid[0, :] = False
    f = A.random_control((50, 50), valid, 137)
    assert int(np.isfinite(f).sum()) == 137
    assert not np.isfinite(f[0, :]).any(), "must stay inside the valid mask"


def test_road_veto_is_a_no_op_without_a_distance_layer():
    f = np.ones((10, 10), np.float32)
    assert np.array_equal(A.road_veto(f, None), f), "an arm must not change meaning silently"


def test_road_veto_suppresses_near_road_pixels():
    f = np.ones((10, 10), np.float32)
    d = np.full((10, 10), 5000.0, np.float32)
    d[0:3, :] = 50.0
    out = A.road_veto(f, d, 150.0)
    assert np.isnan(out[0:3, :]).all()
    assert np.isfinite(out[3:, :]).all()


def test_not_merely_union_detects_a_duplicate():
    base = np.zeros((20, 20), dtype=bool)
    base[5:10, 5:10] = True
    r = A.not_merely_union(base.copy(), [base])
    assert r["is_merely_union"] is True
    other = np.zeros((20, 20), dtype=bool)
    other[15:18, 15:18] = True
    r2 = A.not_merely_union(other, [base])
    assert r2["is_merely_union"] is False


# --------------------------------------------------------------------------------------
# bias
# --------------------------------------------------------------------------------------

def test_distance_histogram_counts_and_median():
    dist = np.zeros((10, 10), np.float32)
    dist[0, 0] = 150.0
    dist[0, 1] = 450.0
    mask = np.zeros((10, 10), dtype=bool)
    mask[0, 0] = mask[0, 1] = True
    h = B.distance_histogram(mask, dist)
    assert h["n"] == 2
    assert h["frac_within_500m"] == pytest.approx(1.0)
    assert h["frac_within_300m"] == pytest.approx(0.5)
    assert h["median_m"] == pytest.approx(300.0)


def test_residual_field_removes_the_distance_trend():
    rng = np.random.default_rng(0)
    # constant within each distance bin, so the within-bin mean removes it exactly
    dist = np.zeros((20, 20), np.float64)
    dist[:, :10] = 100.0
    dist[:, 10:] = 1500.0
    field = np.where(dist < 1000.0, 1.0, 7.0).astype(np.float32)
    res = B.residual_field(field, dist)
    assert np.nanmax(np.abs(res)) < 1e-6, "a distance-bin-constant trend must vanish"


# --------------------------------------------------------------------------------------
# reasoning
# --------------------------------------------------------------------------------------

def test_group_reducictions():
    vals = np.array([3.0, 1.0, 2.0, 5.0])
    gids = np.array([0, 0, 1, 1])
    assert R._group_min(vals, gids, 2).tolist() == [1.0, 2.0]
    assert R._group_any(np.array([False, True, False, False]), gids, 2).tolist() == [True, False]


def test_reason_table_reports_one_row_per_structure(tmp_path):
    rng = np.random.default_rng(0)
    n, shp = 3, (24, 24)
    stack = rng.random((n, shp[0], shp[1])).astype(np.float32)
    meta = {"layers": ["l0", "l1", "l2"]}
    mask = np.zeros(shp, dtype=bool)
    mask[4:8, 4:8] = True
    mask[16:20, 16:20] = True
    dist = np.full(shp, 900.0, np.float32)
    rows = R.reason_table(mask, stack, meta, dist, np.ones(shp, bool))
    assert len(rows) == 2
    assert all(r["n_px"] == 16 for r in rows)
    p = R.write_csv(str(tmp_path / "r.csv"), rows)
    assert Path(p).exists() and Path(p).stat().st_size > 0


def test_reason_table_empty_mask_returns_no_rows():
    shp = (10, 10)
    stack = np.zeros((2, shp[0], shp[1]), np.float32)
    assert R.reason_table(np.zeros(shp, bool), stack, {"layers": ["a", "b"]},
                          np.zeros(shp, np.float32), np.ones(shp, bool)) == []


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------

def test_jsonable_replaces_nan_with_none():
    sys.path.insert(0, str(REPO / "scripts"))
    import run_r4
    out = run_r4.jsonable({"a": float("nan"), "b": [1.0, float("inf")], "c": np.float32(2.5)})
    assert out == {"a": None, "b": [1.0, None], "c": 2.5}
    import json
    json.dumps(out, allow_nan=False), "must survive a strict dump"


def test_topk_mask_returns_exactly_k_even_with_ties():
    """A quantile threshold shipped 37,655 px when 37,654 were asked for."""
    r = np.zeros((4, 4), np.float32)
    r[:2, :] = 1.0                       # eight pixels tied at the top value
    m = np.ones((4, 4), dtype=bool)
    for k in (1, 3, 8, 16, 20):
        assert int(C.topk_mask(r, m, k).sum()) == min(k, 16)


def test_topk_mask_respects_the_allowed_mask():
    r = np.arange(16, dtype=np.float32).reshape(4, 4)
    allowed = np.zeros((4, 4), dtype=bool)
    allowed[0, :] = True                # only four candidates, all low-ranked
    sel = C.topk_mask(r, allowed, 10)
    assert int(sel.sum()) == 4
    assert sel[0, :].all() and not sel[1:, :].any()
