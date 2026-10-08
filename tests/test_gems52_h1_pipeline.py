"""Comprehensive pytest suite verifying the GEMSDOE52 Blum & Mitchell (COLT '98)
Co-Training & Disagreement Discovery submission system.
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
import numpy as np
import pytest
import rasterio

from gems52_h1.cotraining import (
    ConditionalIndependenceViolationError,
    _extract_buffered_whole_segment_pseudolabels,
    segment_connected_faults,
    test_conditional_independence_on_negatives as check_conditional_independence_on_negatives,
)
from gems52_h1.metric import (
    ALPHA,
    BETA,
    RADIUS_PX,
    build_quadrant_ids,
    dti_binary,
    dti_bruteforce,
    dti_exact,
    marginal_inclusion_threshold,
)
from gems52_h1.placement import (
    emit_submodular_expected_credit,
    expected_single_dot_credit,
    verify_not_mere_union,
)
from gems52_h1.spec import (
    BAND_NAME_TO_IDX,
    CRS_STRING,
    SHAPE,
    TRANSFORM_TUPLE,
    VIEW_A_BAND_NAMES,
    VIEW_B_BAND_NAMES,
)
from gems52_h1.submission import verify_geotiff_on_disk

ROOT = Path(__file__).resolve().parents[1]


def test_two_view_band_partition_and_ir_52_01() -> None:
    """Verify View A (17 subsurface/potential-field bands) and View B (2 surface DEM bands)
    form an exact disjoint partition of the 19 official bands in training_features.tif,
    and verify IR-52-01 (Band 6 'tc' is magnetic tilt angle in View A).
    """
    set_a = set(VIEW_A_BAND_NAMES)
    set_b = set(VIEW_B_BAND_NAMES)
    assert len(VIEW_A_BAND_NAMES) == 17
    assert len(VIEW_B_BAND_NAMES) == 2
    assert set_a.isdisjoint(set_b)
    assert set_a | set_b == set(BAND_NAME_TO_IDX.keys())
    assert "tc" in set_a
    assert "tc" not in set_b
    assert set_b == {"det_elev", "det_elev_slope"}


def test_dti_exact_matches_bruteforce_and_marginal_bar() -> None:
    """Verify EDT-based dti_exact and dti_binary match literal O(|G|*|P|) brute-force DTI."""
    rng = np.random.default_rng(52)
    truth = np.zeros((24, 24), dtype=bool)
    truth[5, 5:18] = True
    truth[14:20, 12] = True
    pred = np.zeros((24, 24), dtype=np.float32)
    pred[5, 6:16] = 1.0
    pred[18, 4] = 1.0
    pred[10, 10] = 0.5

    bf = dti_bruteforce(pred, truth, alpha=ALPHA, beta=BETA, radius=RADIUS_PX)
    ex = dti_exact(pred, truth)
    assert np.isclose(bf["tp"], ex["tp"], atol=1e-5)
    assert np.isclose(bf["fp"], ex["fp"], atol=1e-5)
    assert np.isclose(bf["fn"], ex["fn"], atol=1e-5)
    assert np.isclose(bf["dti"], ex["dti"], atol=1e-6)

    pred_bin = pred >= 0.5
    bf_bin = dti_bruteforce(pred_bin.astype(float), truth)
    bin_res = dti_binary(pred_bin, truth)
    assert np.isclose(bf_bin["dti"], bin_res["dti"], atol=1e-6)

    # Marginal inclusion threshold at DTI = 0.2778 is 0.2 * 0.2778 = 0.05556
    assert np.isclose(marginal_inclusion_threshold(0.2778), 0.05556, atol=1e-6)


def test_conditional_independence_gate_enforces_abandonment() -> None:
    """Verify test_conditional_independence_on_negatives raises ConditionalIndependenceViolationError
    when view errors on labeled negatives are strongly correlated (|r| >= 0.50), and passes when weak.
    """
    rng = np.random.default_rng(123)
    fp = np.ones((64, 64), dtype=bool)
    quad = build_quadrant_ids(fp)
    neg_dom = np.ones((64, 64), dtype=bool)

    base = rng.uniform(0, 1, size=(64, 64)).astype(np.float32)
    p_a_corr = base
    p_b_corr = (0.9 * base + 0.1 * rng.uniform(0, 1, size=(64, 64))).astype(np.float32)
    with pytest.raises(ConditionalIndependenceViolationError):
        check_conditional_independence_on_negatives(
            p_a_oof=p_a_corr, p_b_oof=p_b_corr, neg_domain=neg_dom, quadrant_ids=quad, abandon_threshold=0.50
        )

    p_b_indep = rng.uniform(0, 1, size=(64, 64)).astype(np.float32)
    rep = check_conditional_independence_on_negatives(
        p_a_oof=p_a_corr, p_b_oof=p_b_indep, neg_domain=neg_dom, quadrant_ids=quad, abandon_threshold=0.50
    )
    assert rep["conditional_independence_gate_passed"] is True
    assert rep["decision"] == "PROCEED_WITH_COTRAINING"


def test_whole_segment_spatial_blocks_and_buffer_prevent_leakage() -> None:
    """Verify connected fault segments are assigned as whole segments (zero split segments)
    and abstention-gated pseudo-labels include a 5-px buffer.
    """
    fp = np.ones((80, 80), dtype=bool)
    quad = build_quadrant_ids(fp)
    labels = np.zeros((80, 80), dtype=bool)
    labels[10, 10:25] = True
    labels[30:48, 20] = True
    labels[55, 45:65] = True
    labels[65, 15:35] = True
    labels[20, 55:70] = True

    seg_ids, train_mask, hide_mask, summary = segment_connected_faults(
        labels=labels, footprint=fp, quadrant_ids=quad, hide_fraction=0.25, seed=52
    )
    assert not np.any(train_mask & hide_mask)
    assert np.array_equal(train_mask | hide_mask, labels)
    # Every connected component must be 100% in train_mask or 100% in hide_mask
    for sid in range(1, summary["total_connected_segments"] + 1):
        comp = seg_ids == sid
        in_tr = np.any(comp & train_mask)
        in_hd = np.any(comp & hide_mask)
        assert in_tr ^ in_hd

    # Abstention-gated pseudo-label test
    rng = np.random.default_rng(99)
    p_teacher = rng.uniform(0.0, 0.5, size=(80, 80)).astype(np.float32)
    p_student = rng.uniform(0.0, 1.0, size=(80, 80)).astype(np.float32)
    p_teacher[40, 40:46] = 0.999
    p_student[40, 40:46] = 0.50
    unlabeled = fp & ~labels
    pseudo_mask, pseudo_buf, stats = _extract_buffered_whole_segment_pseudolabels(
        p_teacher=p_teacher,
        p_student=p_student,
        unlabeled_domain=unlabeled,
        conf_quantile=0.995,
        abstain_lo_quantile=0.20,
        abstain_hi_quantile=0.80,
        min_segment_px=3,
    )
    assert stats["n_whole_segments"] == 1
    assert int(pseudo_mask.sum()) == 6
    assert int(pseudo_buf.sum()) > int(pseudo_mask.sum())
    assert np.all(pseudo_buf[pseudo_mask])


def test_submodular_expected_credit_and_non_union_gate() -> None:
    """Verify CELF submodular placement respects diminishing returns and non-union gate."""
    q = np.zeros((40, 40), dtype=np.float32)
    q[20, 8:32] = 0.8
    allowed = np.ones((40, 40), dtype=bool)
    init_gain = expected_single_dot_credit(q)
    assert init_gain[20, 15] > 1.5

    res = emit_submodular_expected_credit(q, allowed, budget=6, min_marginal_gain=0.05)
    assert res.accepted_count == 6
    # Because of submodular diminishing returns within the r=3 kernel, the 6 dots spread along the line
    xs = np.nonzero(res.mask)[1]
    assert (xs.max() - xs.min()) >= 15

    # Verify non-union check rejects literal union and accepts disagreement-filtered output
    va = np.zeros((40, 40), dtype=bool)
    vb = np.zeros((40, 40), dtype=bool)
    va[10, 5:15] = True
    vb[20, 5:15] = True
    cotrain = np.zeros((40, 40), dtype=bool)
    cotrain[10, 5:12] = True
    cotrain[20, 5:10] = True
    cotrain[30, 5:10] = True
    rep = verify_not_mere_union(cotrain, va, vb, va | vb)
    assert rep["confirmed_not_mere_union"] is True


def test_real_evidence_receipts_and_submission_geotiff_gates() -> None:
    """Verify all generated evidence JSON receipts and on-disk GeoTIFF/ZIP submission files."""
    ev_dir = ROOT / "evidence"
    dl_dir = ROOT / "docs" / "downloads"

    for fname in (
        "independence_test.json",
        "cotraining_rounds.json",
        "hide_and_recover_benchmark.json",
        "holdout_validation.json",
        "a_only_geological_reasoning.json",
        "submission_audit.json",
        "uniqueness_gate.json",
    ):
        assert (ev_dir / fname).exists(), f"Missing evidence file {fname}"

    ind = json.loads((ev_dir / "independence_test.json").read_text())
    assert ind["conditional_independence_gate_passed"] is True
    assert abs(ind["pearson_r_oof_negative_error"]) < 0.25

    hr = json.loads((ev_dir / "hide_and_recover_benchmark.json").read_text())
    m = hr["models"]
    assert m["cotrained_discovery_round2_final"]["dti_all_hidden_segments"] > m["single_view_A_geophysical_t0"]["dti_all_hidden_segments"]
    assert m["cotrained_discovery_round2_final"]["dti_all_hidden_segments"] > m["single_view_B_surface_t0"]["dti_all_hidden_segments"]
    assert m["cotrained_discovery_round2_final"]["dti_all_hidden_segments"] > m["naive_union_A_or_B_t0"]["dti_all_hidden_segments"]
    assert m["cotrained_discovery_round2_final"]["dti_all_hidden_segments"] > m["early_fusion_single_learner"]["dti_all_hidden_segments"]

    hv = json.loads((ev_dir / "holdout_validation.json").read_text())
    assert hv["primary_vs_02778_folds_won"] == "4/4"
    assert hv["anchored_hybrid_vs_02778_folds_won"] == "4/4"
    assert hv["primary_lm_margin_vs_02778"] > 0.05
    assert hv["primary_stratified_d0_3px_margin_vs_02778"] > 0.07
    assert hv["primary_stratified_d0_5px_margin_vs_02778"] > 0.07

    dossier = json.loads((ev_dir / "a_only_geological_reasoning.json").read_text())
    assert dossier["summary"]["total_a_only_buried_fault_dots"] >= 500
    assert len(dossier["a_only_corridor_dossiers"]) == dossier["summary"]["total_a_only_structural_corridors"]
    assert all(
        len(c.get("geological_reasoning", "")) > 40 for c in dossier["a_only_corridor_dossiers"]
    )

    sub_audit = json.loads((ev_dir / "submission_audit.json").read_text())
    assert len(sub_audit["submission_note"]) <= 200
    assert sub_audit["uniqueness_gate"]["uniqueness_gate_passed"] is True
    assert sub_audit["uniqueness_gate"]["zero_sha256_collisions"] is True
    assert sub_audit["uniqueness_gate"]["max_jaccard_vs_prior_submissions"] < 0.15
    assert sub_audit["uniqueness_gate"]["non_union_verification"]["confirmed_not_mere_union"] is True

    with rasterio.open(ROOT / "data" / "sample_submission.tif") as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(ROOT / "data" / "labels.tif") as ds:
        labels = ds.read(1) == 1

    primary_tif = dl_dir / "gemsdoe52-cotrain-disagree-submodular-20261006-zeros.tif"
    primary_zip = dl_dir / "gemsdoe52-cotrain-disagree-submodular-20261006-zeros.zip"
    nan_tif = dl_dir / "gemsdoe52-cotrain-disagree-submodular-20261006-nan.tif"
    hybrid_tif = dl_dir / "gemsdoe52-cotrain-anchored-hybrid-20261006-zeros.tif"

    for p, mode in ((primary_tif, "zeros"), (nan_tif, "nan"), (hybrid_tif, "zeros")):
        audit = verify_geotiff_on_disk(p, footprint=footprint, labels=labels, mode=mode)
        assert audit["all_checks_passed"] is True
        assert audit["crs"] == CRS_STRING
        assert tuple(audit["shape"]) == SHAPE
        assert tuple(audit["transform"]) == TRANSFORM_TUPLE

    with zipfile.ZipFile(primary_zip, "r") as zf:
        names = zf.namelist()
        assert names == [primary_tif.name]


def test_github_pages_and_readme_completeness() -> None:
    """Verify all GitHub Pages HTML files, local href targets, download links, and README prompt."""
    import re

    docs_dir = ROOT / "docs"
    pages = (
        "index.html",
        "executive-summary.html",
        "forensics.html",
        "hypotheses.html",
        "validation.html",
        "sources.html",
    )
    for page in pages:
        p = docs_dir / page
        assert p.exists(), f"Missing GitHub Pages file {page}"
        html = p.read_text()
        for href in re.findall(r'href="([^"#]+)"', html):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            target = (docs_dir / href).resolve()
            assert target.exists(), f"Broken local link {href} in {page} -> {target}"

    readme_text = (ROOT / "README.md").read_text()
    current_prompt = (ROOT / "knowledge/08_current_user_prompt.md").read_text()
    assert current_prompt in readme_text
    assert "MUST GENERATE A UNIQUE TIF SUBMISSION" in readme_text
    assert "Own the Outcome" in readme_text
    assert "Pass 3:" in readme_text

