"""Unit tests for the 2026-10-09 HWVC lane: decoder D-S, gate v2 helpers, HWVC sign logic, shipped-file checks."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems53.hwvc import (decoder_ds, disk_dilate, hwvc_channels, percentile_rank,  # noqa: E402
                         registry_dots, spaced_dots)


def test_spaced_dots_respects_min_sep_and_count():
    rng = np.random.default_rng(0)
    s = rng.random((60, 60))
    cand = np.ones_like(s, dtype=bool)
    dots = spaced_dots(s, cand, n_dots=50, min_sep=2.8)
    ys, xs = np.nonzero(dots)
    assert dots.sum() == 50
    d = np.hypot(ys[:, None] - ys[None], xs[:, None] - xs[None]) + np.eye(len(ys)) * 99
    assert d.min() > 2.8
    # the global maximum is always kept (greedy in decreasing score)
    assert dots[np.unravel_index(np.argmax(s), s.shape)]


def test_spaced_dots_stops_when_candidates_exhausted():
    s = np.zeros((10, 10)); s[5, 5] = 1
    cand = np.zeros_like(s, dtype=bool); cand[5, 5] = True
    assert spaced_dots(s, cand, n_dots=10).sum() == 1


def test_decoder_ds_flank_prune_and_binary():
    known = np.zeros((40, 40), dtype=bool); known[20, :] = True
    fp = np.ones_like(known)
    score = np.ones((40, 40))
    out = decoder_ds(score, fp, known, n_dots=1000, flank_px=2.0, min_sep=2.8)
    d = ndimage.distance_transform_edt(~known)
    assert set(np.unique(out)) <= {0.0, 1.0}
    assert (d[out > 0] > 2.0).all()


def test_percentile_rank_bounds():
    x = np.arange(12, dtype=float).reshape(3, 4)
    m = np.ones_like(x, dtype=bool)
    r = percentile_rank(x, m)
    assert r.min() == 0 and r.max() == 1


def test_hwvc_concordant_step_scores_higher_than_discordant():
    """A synthetic N-S normal fault at col 30: basin (west) low elevation, low gravity, high cond, deep basement."""
    H, W = 40, 60
    step = (np.arange(W)[None, :] >= 30).astype(float) * np.ones((H, 1))   # 1 = footwall (east)
    fp = np.ones((H, W), dtype=bool)
    conc = {12: step.copy(), 13: step.copy(), 17: 1 - step, 15: 1 - step}     # all agree: basin is west
    disc = {12: step.copy(), 13: 1 - step, 17: step.copy(), 15: 1 - step}     # two bands disagree
    cc, _ = hwvc_channels(conc, fp)
    cd, _ = hwvc_channels(disc, fp)
    assert cc["hwvc_C_s2"][:, 30].mean() > 0.99
    assert cd["hwvc_C_s2"][:, 30].mean() < 0.05
    assert cc["hwvc_R_s2"][:, 29:31].mean() > cd["hwvc_R_s2"][:, 29:31].mean()


def test_registry_dots_modes():
    fp = np.ones((100, 100), dtype=bool)
    sparse = np.zeros((100, 100), dtype=np.float32); sparse[::10, ::10] = 1
    m, mode, n = registry_dots(sparse, fp, k_match=50)
    assert mode == "positive" and m.sum() == 100
    dense = np.random.default_rng(1).random((100, 100)).astype(np.float32)
    m2, mode2, _ = registry_dots(dense, fp, k_match=50)
    assert mode2 == "topk" and m2.sum() == 50


def test_kappa_flags_copy_not_lattice():
    """A copy of our dots gives kappa ~1; a dense lattice (overlap > 0.7 explained by coverage) gives kappa ~0.
    Note: kappa = 1 whenever overlap = 1 exactly; with tens of thousands of dots this needs every dot inside the
    coverage, which is improbable unless coverage is ~100 % (documented limitation of gate v2)."""
    fp = np.ones((240, 240), dtype=bool)
    rng = np.random.default_rng(2)
    ours = np.zeros_like(fp); ours[rng.integers(0, 240, 3000), rng.integers(0, 240, 3000)] = True
    lattice = np.zeros_like(fp); lattice[::6, ::6] = True
    for reg, expect_dup in ((ours.copy(), True), (lattice, False)):
        dil = disk_dilate(reg, 3.0)
        ov = dil[ours].mean(); ch = dil[fp].mean()
        kap = (ov - ch) / (1 - ch) if ch < 1 else 0.0
        if not expect_dup:
            assert ov > 0.7 and abs(kap) < 0.2
        assert (ov > 0.7 and kap > 0.4) == expect_dup


CUR = ROOT / "docs" / "submissions" / "CURRENT.json"


@pytest.mark.skipif(not CUR.exists(), reason="no current pointer")
def test_shipped_file_matches_pointer_and_is_all_finite():
    import rasterio
    cur = json.loads(CUR.read_text())
    if "gate_receipt" not in cur:
        pytest.skip("pointer predates the 2026-10-09 lane")
    tif = ROOT / cur["file"]
    h = hashlib.sha256(tif.read_bytes()).hexdigest()
    assert h == cur["sha256"]
    assert len(cur["note"]) <= 140
    with rasterio.open(tif) as s:
        a = s.read(1)
        assert s.count == 1 and s.dtypes[0] == "float32" and s.crs.to_epsg() == 32611
        assert (s.height, s.width) == (3730, 3292) and s.res == (100.0, 100.0) and s.nodata is None
        assert tuple(s.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
    assert np.isfinite(a).all() and a.min() >= 0 and a.max() <= 1
    assert int((a > 0).sum()) == cur["dots"]


@pytest.mark.skipif(not CUR.exists(), reason="no current pointer")
def test_pointer_site_runcard_and_gate_agree():
    cur = json.loads(CUR.read_text())
    if "gate_receipt" not in cur:
        pytest.skip("pointer predates the 2026-10-09 lane")
    gate = json.loads((ROOT / cur["gate_receipt"]).read_text())
    rec = json.loads((ROOT / cur["receipt"]).read_text())
    card = json.loads((ROOT / "evidence" / "h53_run_card.json").read_text())
    idx = (ROOT / "docs" / "index.html").read_text()
    howto = (ROOT / "docs" / "how-to-submit.html").read_text()
    root = (ROOT / "index.html").read_text()
    dup = bool(gate["duplicates_v2"])
    # a duplicate can never be OK to submit; a non-passing format can never be OK to submit
    if dup or not rec["explicit_all_pass"]:
        assert cur["ok_to_submit"] is False
    assert card["ok_to_submit"] == cur["ok_to_submit"] and card["label"] == cur["label"] == rec["label"]
    assert card["raster"]["sha256"] == cur["sha256"] == rec["sha256"]
    if cur["ok_to_submit"]:
        assert "YES — OK to download and submit" in idx and "NO —" not in idx
    else:
        assert "NO — do not submit" in idx and "YES — OK" not in idx and "YES — OK" not in howto
        assert 'class="btn" href' not in idx and "OK to submit: NO" in root
        assert "DO-NOT-SUBMIT" in cur["file"]
    assert cur["name"] in idx and len(cur["note"]) <= 140


def test_hwvc_negative_matches_preregistered_rule():
    e2 = json.loads((ROOT / "evidence" / "h53_e2_holdout.json").read_text())
    lb = e2["stage1"]["M1_thin_bin_q0p10"]["paired_B_minus_A"]["CI95_t_df4"][0]
    m2 = e2["stage2"]["M1_thin_bin_q0p10"]["paired_B_minus_A"]["mean"]
    assert e2["promote_B"] == bool(lb > 0 and m2 > 0) is False
    assert e2["segment_folds"]["withheld_positives_total"] == 60988
    assert e2["reproduction_check"]["this_run_arm_A"] == e2["reproduction_check"]["previous_session_h1_thin_bin_q0p1_pooled"]
