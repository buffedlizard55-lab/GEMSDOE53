#!/usr/bin/env python3
"""Execute the end-to-end Blum & Mitchell (COLT '98) Co-Training & Disagreement Discovery
pipeline, validate all candidate hypotheses on the spatially-blocked holdout instruments,
generate Phase 2 geological reasoning for every A-only buried fault candidate, write the
normalized [0, 1] GeoTIFF submissions, and run the format & uniqueness gates.
"""
from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52.cotraining import run_blum_mitchell_cotraining  # noqa: E402
from gems52.metric import build_spatially_blocked_instrument, evaluate_candidate  # noqa: E402
from gems52.placement import (  # noqa: E402
    emit_submodular_expected_credit,
    verify_not_mere_union,
)
from gems52.reasoning import generate_a_only_geological_reasoning  # noqa: E402
from gems52.submission import (  # noqa: E402
    run_uniqueness_gate,
    verify_geotiff_on_disk,
    write_submission_geotiff,
    write_submission_zip,
)


def _rank_norm(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.zeros(a.shape, dtype=np.float32)
    sel = mask & np.isfinite(a)
    v = a[sel]
    if v.size == 0:
        return out
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(v.size, dtype=np.float32)
    ranks[order] = np.arange(v.size, dtype=np.float32) / max(v.size - 1, 1)
    out[sel] = ranks
    return out


def _grad_mag(a: np.ndarray, sigma: float) -> np.ndarray:
    g = ndi.gaussian_filter(np.nan_to_num(a, nan=0.0), sigma, mode="nearest")
    gy, gx = np.gradient(g)
    return np.hypot(gx, gy).astype(np.float32)


def _lap_mag(a: np.ndarray, sigma: float) -> np.ndarray:
    return np.abs(ndi.gaussian_laplace(np.nan_to_num(a, nan=0.0), sigma)).astype(np.float32)


def _struct_coh(a: np.ndarray, sigma: float = 3.0) -> np.ndarray:
    g = ndi.gaussian_filter(np.nan_to_num(a, nan=0.0), sigma, mode="nearest")
    gy, gx = np.gradient(g)
    jxx = ndi.gaussian_filter(gx * gx, sigma * 1.5, mode="nearest")
    jyy = ndi.gaussian_filter(gy * gy, sigma * 1.5, mode="nearest")
    jxy = ndi.gaussian_filter(gx * gy, sigma * 1.5, mode="nearest")
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    return np.clip(np.where(tr > 0, (2.0 * disc) / np.maximum(tr, 1e-12), 0.0), 0.0, 1.0).astype(np.float32)


def _build_view_a_subsurface_lineaments(data_dir: Path, footprint: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build strictly View A (subsurface/potential-field) structure-coherence lineaments."""
    with rasterio.open(data_dir / "training_features.tif") as ds:
        rtp = ds.read(2).astype(np.float32)
        rtp[rtp < -1e37] = np.nan
        tc = ds.read(6).astype(np.float32)
        tc[tc < -1e37] = np.nan
        grav = ds.read(13).astype(np.float32)
        grav[grav < -1e37] = np.nan
        depth = ds.read(15).astype(np.float32)
        depth[depth < -1e37] = np.nan
        cond = ds.read(17).astype(np.float32)
        cond[cond < -1e37] = np.nan

    m_a = footprint & np.isfinite(rtp) & np.isfinite(grav)
    rtp_g2 = _rank_norm(_grad_mag(rtp, 2.0), m_a)
    rtp_g5 = _rank_norm(_grad_mag(rtp, 5.0), m_a)
    grav_g2 = _rank_norm(_grad_mag(grav, 2.0), m_a)
    grav_g5 = _rank_norm(_grad_mag(grav, 5.0), m_a)
    tc_g2 = _rank_norm(_grad_mag(tc, 2.0), m_a)
    depth_g2 = _rank_norm(_grad_mag(depth, 2.0), m_a)
    cond_g2 = _rank_norm(_grad_mag(cond, 2.0), m_a)

    a_comb = (1.0 * rtp_g2 + 0.7 * rtp_g5 + 1.0 * grav_g2 + 0.7 * grav_g5 + 0.5 * tc_g2 + 0.4 * cond_g2) / 4.3
    a_coh = _struct_coh(a_comb, 3.0)
    view_a_line = (a_comb * np.sqrt(a_coh)).astype(np.float32)

    # Hypothesis-specific View A components:
    # H52-2: Miller & Singh (1994) Magnetic Tilt-Angle Zero-Crossing + RTP Edge
    h52_2_mag_tilt = ((0.6 * tc_g2 + 0.4 * rtp_g2) * np.sqrt(a_coh)).astype(np.float32)
    # H52-3: 3D Gravity Analytic Signal + Basement Depth Step
    h52_3_grav_base = ((0.6 * grav_g2 + 0.4 * depth_g2) * np.sqrt(a_coh)).astype(np.float32)
    # H52-4: Subsurface Electrical Conductivity Boundary
    h52_4_cond = (cond_g2 * np.sqrt(a_coh)).astype(np.float32)

    del rtp, tc, grav, depth, cond, rtp_g2, rtp_g5, grav_g2, grav_g5, tc_g2, depth_g2, cond_g2, a_comb
    gc.collect()
    return view_a_line, h52_2_mag_tilt, h52_3_grav_base, h52_4_cond


def _build_view_b_surface_lineaments(data_dir: Path, footprint: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build strictly View B (surface DEM + LiDAR scarp + GeoDAWN radiometrics) lineaments."""
    with rasterio.open(data_dir / "training_features.tif") as ds:
        det_elev = ds.read(12).astype(np.float32)
        det_elev[det_elev < -1e37] = np.nan
        det_slope = ds.read(19).astype(np.float32)
        det_slope[det_slope < -1e37] = np.nan

    m_b = footprint & np.isfinite(det_elev) & np.isfinite(det_slope)
    topo_comb = (
        1.0 * _rank_norm(_grad_mag(det_elev, 2.0), m_b)
        + 0.7 * _rank_norm(_grad_mag(det_elev, 6.0), m_b)
        + 0.7 * _rank_norm(_lap_mag(det_elev, 2.0), m_b)
        + 1.0 * _rank_norm(_grad_mag(det_slope, 2.0), m_b)
        + 0.7 * _rank_norm(_lap_mag(det_slope, 2.0), m_b)
    ) / 4.1
    del det_elev, det_slope
    gc.collect()
    topo_coh = _struct_coh(topo_comb, 3.0)
    topo_line = (topo_comb * np.sqrt(topo_coh)).astype(np.float32)
    del topo_comb
    gc.collect()

    with rasterio.open(data_dir / "external" / "lidar_scarp_features_u8.tif") as src:
        names = list(src.descriptions)
        lvalid = (src.read(names.index("valid") + 1) > 0) & footprint
        acc = np.zeros(footprint.shape, dtype=np.float32)
        chs = ("step_max", "downface_max", "lappos_max", "lapneg_max", "ex_max", "ex_mean", "cross_max", "upface_max")
        for ch in chs:
            raw = src.read(names.index(ch) + 1).astype(np.float32)
            u = np.where(raw > 0, (raw - 1.0) / 254.0, np.nan)
            acc += _rank_norm(u, lvalid)
            del raw, u
    acc /= len(chs)
    lidar_line = (acc * np.sqrt(_struct_coh(acc, 3.0))).astype(np.float32)
    del acc
    gc.collect()

    with rasterio.open(data_dir / "external" / "geodawn_rad_u8.tif") as src:
        rnames = list(src.descriptions)
        k_raw = src.read(rnames.index("K") + 1).astype(np.float32)
        th_raw = src.read(rnames.index("Th") + 1).astype(np.float32)
        k = np.where(k_raw > 0, (k_raw - 1.0) / 254.0, np.nan)
        th = np.where(th_raw > 0, (th_raw - 1.0) / 254.0, np.nan)
        del k_raw, th_raw
    with rasterio.open(data_dir / "external" / "geodawn_extensions_u8.tif") as src:
        enames = list(src.descriptions)
        uk_raw = src.read(enames.index("UK") + 1).astype(np.float32)
        uk = np.where(uk_raw > 0, (uk_raw - 1.0) / 254.0, np.nan)
        del uk_raw
    thk = np.where((th > 0) & (k > 0), th / np.maximum(k, 1e-6), np.nan)
    rmask = footprint & np.isfinite(k) & np.isfinite(th)
    rcomb = (
        _rank_norm(_grad_mag(k, 2.0), rmask)
        + _rank_norm(_grad_mag(thk, 2.0), rmask)
        + 0.5 * _rank_norm(_grad_mag(uk, 2.0), rmask)
    ) / 2.5
    del k, th, uk, thk
    gc.collect()
    rad_line = (rcomb * np.sqrt(_struct_coh(rcomb, 3.0))).astype(np.float32)
    del rcomb
    gc.collect()

    denom_b = np.where(lvalid & (lidar_line > 0), 2.4, 1.4).astype(np.float32)
    view_b_line = ((1.0 * lidar_line + 0.8 * topo_line + 0.6 * rad_line) / denom_b).astype(np.float32)
    del lidar_line
    gc.collect()
    return view_b_line, topo_line, rad_line, lvalid, topo_coh


def main() -> int:
    t0 = time.time()
    data_dir = ROOT / "data"
    prep_dir = data_dir / "prepared"
    ev_dir = ROOT / "evidence"
    dl_dir = ROOT / "docs" / "downloads"
    docs_data_dir = ROOT / "docs" / "data"
    ev_dir.mkdir(parents=True, exist_ok=True)
    dl_dir.mkdir(parents=True, exist_ok=True)
    docs_data_dir.mkdir(parents=True, exist_ok=True)

    print("[1/7] Loading competition rasters and mmap two-view stacks...", flush=True)
    with rasterio.open(data_dir / "sample_submission.tif") as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(data_dir / "labels.tif") as ds:
        labels = ds.read(1) == 1
    with rasterio.open(data_dir / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) > 0
    with rasterio.open(
        data_dir / "scored" / "gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"
    ) as ds:
        base_02778 = np.isfinite(ds.read(1)) & (ds.read(1) > 0)

    view_a = np.load(prep_dir / "view_a_stack.npy", mmap_mode="r")
    view_b = np.load(prep_dir / "view_b_stack.npy", mmap_mode="r")
    aux = np.load(prep_dir / "physical_aux.npz")
    depth_to_base = aux["depth_to_base"]
    det_slope = aux["det_slope_raw"]

    print("[2/7] Running Blum & Mitchell (1998) Two-View Co-Training & Empirical Independence Gate...", flush=True)
    cotrain = run_blum_mitchell_cotraining(
        view_a=view_a,
        view_b=view_b,
        footprint=footprint,
        labels=labels,
        depth_to_base=depth_to_base,
        det_slope=det_slope,
        n_rounds=2,
        seed=52,
    )

    ind_rep = cotrain.independence_report
    print(
        f"      Independence Gate: Pearson r_neg = {ind_rep['pearson_r_oof_negative_error']:+.5f}, "
        f"Spearman rho_neg = {ind_rep['spearman_rho_oof_negative_error']:+.5f} -> {ind_rep['decision']}",
        flush=True,
    )
    (ev_dir / "independence_test.json").write_text(json.dumps(ind_rep, indent=2) + "\n")
    (ev_dir / "cotraining_rounds.json").write_text(json.dumps(cotrain.pseudo_label_log, indent=2) + "\n")
    (ev_dir / "hide_and_recover_benchmark.json").write_text(
        json.dumps(cotrain.hide_and_recover_report, indent=2) + "\n"
    )

    print("[3/7] Building spatially-blocked off-catalogue holdout instruments & two-view lineaments...", flush=True)
    inst = build_spatially_blocked_instrument(footprint=footprint, labels=labels, sgmc=sgmc)
    allowed_offcat_b2 = footprint & (inst.d_cat > 2.0)

    view_a_line, h52_2_mag_tilt, h52_3_grav_base, h52_4_cond = _build_view_a_subsurface_lineaments(data_dir, footprint)
    view_b_line, topo_line, rad_line, lvalid, topo_coh = _build_view_b_surface_lineaments(data_dir, footprint)

    # Combine Co-Trained OOF view posteriors with their respective view lineaments:
    # View A (Geophysical/Subsurface only):
    v_a_cotrained = (view_a_line * (0.72 + 0.28 * cotrain.p_a_cotrained)).astype(np.float32)
    # View B (Surface DEM/LiDAR/Radiometric only):
    v_b_cotrained = (view_b_line * (0.82 + 0.18 * cotrain.p_b_cotrained)).astype(np.float32)

    no_lidar = (~lvalid).astype(np.float32)
    cover_rk = _rank_norm(depth_to_base, footprint)
    slope_rk = _rank_norm(det_slope, footprint)

    # Disagreement Decomposition:
    # 1) A-only Buried Discovery: View A confident where View B abstains/is weaker, especially outside LiDAR or under sedimentary cover
    a_only_buried = (
        v_a_cotrained
        * np.maximum(0.0, v_a_cotrained - v_b_cotrained)
        * (0.25 + 0.75 * np.maximum(topo_line, rad_line))
        * (0.50 + 0.50 * cover_rk)
    ).astype(np.float32)
    a_corrob_boost = (v_a_cotrained * (0.04 + 0.16 * no_lidar * np.maximum(topo_line, rad_line))).astype(np.float32)

    # 2) B-only Surface Artifact Suppression: View B fires on low-coherence/flat valley features where View A is near zero
    b_only_artifact = (
        v_b_cotrained
        * no_lidar
        * np.maximum(0.0, 0.22 - v_a_cotrained)
        * np.maximum(0.0, 0.45 - topo_coh)
        * (0.50 + 0.50 * np.maximum(0.0, 0.35 - slope_rk))
    ).astype(np.float32)

    # Co-Trained Disagreement-Aware Discovery Field (H52-1)
    cotrain_disagree_field = np.maximum(
        v_b_cotrained + a_corrob_boost + 0.12 * a_only_buried - 0.75 * b_only_artifact,
        0.0,
    ).astype(np.float32)

    # Hypothesis-specific fields for H52-2, H52-3, H52-4
    field_h52_2 = np.maximum(
        v_b_cotrained + 0.14 * h52_2_mag_tilt * (0.3 + 0.7 * no_lidar) - 0.65 * b_only_artifact,
        0.0,
    ).astype(np.float32)
    field_h52_3 = np.maximum(
        v_b_cotrained + 0.14 * h52_3_grav_base * (0.3 + 0.7 * no_lidar) - 0.65 * b_only_artifact,
        0.0,
    ).astype(np.float32)
    field_h52_4 = np.maximum(
        v_b_cotrained + 0.14 * (0.5 * h52_4_cond + 0.5 * rad_line) * (0.3 + 0.7 * no_lidar) - 0.65 * b_only_artifact,
        0.0,
    ).astype(np.float32)

    def _emit_field(field: np.ndarray, budget: int) -> np.ndarray:
        q = field / max(float(field[allowed_offcat_b2].sum()), 1e-6) * 10_000.0
        return emit_submodular_expected_credit(
            q, allowed_offcat_b2, budget=budget, min_marginal_gain=0.005, max_candidates=650_000
        ).mask

    print("[4/7] Running Metric-Aware Submodular Expected-Credit Placement across views and hypotheses...", flush=True)
    base_budget = 37_654
    discovery_budget = 41_200

    print("      - Emitting Single-View A (Geophysical/Subsurface solo, 37,654 dots)...", flush=True)
    mask_view_a = _emit_field(v_a_cotrained, base_budget)
    print("      - Emitting Single-View B (Surface DEM/LiDAR/Radiometrics solo, 37,654 dots)...", flush=True)
    mask_view_b = _emit_field(v_b_cotrained, base_budget)
    print("      - Emitting Naive Union max(View A, View B) (37,654 dots)...", flush=True)
    mask_union = _emit_field(np.maximum(v_a_cotrained, v_b_cotrained), base_budget)

    print("      - Emitting H52-2 (Magnetic Tilt-Angle Zero-Crossing, 39,850 dots)...", flush=True)
    mask_h52_2 = _emit_field(field_h52_2, 39_850)
    print("      - Emitting H52-3 (3D Gravity Analytic + Basement Step, 39,850 dots)...", flush=True)
    mask_h52_3 = _emit_field(field_h52_3, 39_850)
    print("      - Emitting H52-4 (MT Conductivity + Radiometric K/Th, 39,850 dots)...", flush=True)
    mask_h52_4 = _emit_field(field_h52_4, 39_850)

    print("      - Emitting GEMSDOE52_H52_1_PRIMARY (Pure Co-Trained Disagreement Submodular, 41,200 dots)...", flush=True)
    primary_mask = _emit_field(cotrain_disagree_field, discovery_budget)

    # Also build Live-Anchored Companion (0.2778 base minus B-only artifacts + 3,200 Co-Trained Discovery dots)
    surviving_b2 = base_02778.copy()
    n_pruned_b2 = 0
    for qid in range(4):
        qm = inst.quadrant_ids == qid
        q_yy, q_xx = np.nonzero(base_02778 & qm)
        b_art_cand = (
            (cotrain.p_a_cotrained[q_yy, q_xx] < 0.18)
            & (cotrain.subsurface_crest[q_yy, q_xx] < 0.08)
            & (cotrain.artifact_b_only[q_yy, q_xx] > 0.05)
        )
        cand_idx = np.flatnonzero(b_art_cand)
        if cand_idx.size > 50:
            scores = cotrain.artifact_b_only[q_yy[cand_idx], q_xx[cand_idx]]
            top_k = cand_idx[np.argsort(-scores)[:50]]
            surviving_b2[q_yy[top_k], q_xx[top_k]] = False
            n_pruned_b2 += int(top_k.size)
    d_b2 = ndi.distance_transform_edt(~surviving_b2)
    cand_add = primary_mask & (d_b2 > 2.2)
    add_coords = np.argwhere(cand_add)
    add_scores = cotrain_disagree_field[cand_add]
    top_add = np.argsort(add_scores)[::-1][:3200]
    anchored_hybrid_mask = surviving_b2.copy()
    anchored_hybrid_mask[add_coords[top_add, 0], add_coords[top_add, 1]] = True
    print(
        f"      - Emitted GEMSDOE52_H52_1_ANCHORED_HYBRID: {int(base_02778.sum())} base - {n_pruned_b2} B-only artifacts "
        f"+ 3200 co-trained discovery dots = {int(anchored_hybrid_mask.sum())} dots.",
        flush=True,
    )

    non_union_primary = verify_not_mere_union(
        cotrained_mask=primary_mask,
        view_a_mask=mask_view_a,
        view_b_mask=mask_view_b,
        union_field_mask=mask_union,
    )
    non_union_hybrid = verify_not_mere_union(
        cotrained_mask=anchored_hybrid_mask,
        view_a_mask=mask_view_a,
        view_b_mask=mask_view_b,
        union_field_mask=mask_union,
    )

    print("[5/7] Evaluating all models and hypotheses on Spatially-Blocked Holdout Instruments...", flush=True)
    eval_candidates = [
        ("BASE_02778_GEMSDOE32_B2", base_02778),
        ("VIEW_A_SOLO_SUBMODULAR", mask_view_a),
        ("VIEW_B_SOLO_SUBMODULAR", mask_view_b),
        ("NAIVE_UNION_MAX_AB_SUBMODULAR", mask_union),
        ("H52_3_GRAV_ANALYTIC_BASESTEP", mask_h52_3),
        ("H52_2_MAG_TILT_ZEROCROSS", mask_h52_2),
        ("H52_4_COND_RAD_HYDROTHERMAL", mask_h52_4),
        ("GEMSDOE52_H52_1_ANCHORED_HYBRID", anchored_hybrid_mask),
        ("GEMSDOE52_H52_1_PRIMARY", primary_mask),
    ]

    holdout_table: list[dict] = []
    base_lm = None
    base_d5 = None
    for cname, cmask in eval_candidates:
        ev = evaluate_candidate(cmask, inst, name=cname)
        if cname == "BASE_02778_GEMSDOE32_B2":
            base_lm = ev["lm_mean"]
            base_d5 = ev["stratified_d0_5px"]["dti"]
        ev["delta_lm_vs_02778"] = round(ev["lm_mean"] - (base_lm or 0.0), 6)
        ev["delta_d0_5px_vs_02778"] = round(ev["stratified_d0_5px"]["dti"] - (base_d5 or 0.0), 6)
        ev["projected_live_dti"] = round(0.2778 + ev["delta_lm_vs_02778"], 4)
        holdout_table.append(ev)
        print(
            f"      {cname:32s}: dots={ev['emitted_pixels']:6d} | "
            f"LM={ev['lm_mean']:.6f} ({ev['delta_lm_vs_02778']:+.6f}) | "
            f"d0=3px={ev['stratified_d0_3px']['dti']:.6f} | "
            f"d0=5px={ev['stratified_d0_5px']['dti']:.6f}",
            flush=True,
        )

    base_folds = holdout_table[0]["lm_per_fold"]
    prim_folds = holdout_table[-1]["lm_per_fold"]
    hyb_folds = holdout_table[-2]["lm_per_fold"]
    folds_won_prim = sum(1 for k in base_folds if prim_folds[k] > base_folds[k])
    folds_won_hyb = sum(1 for k in base_folds if hyb_folds[k] > base_folds[k])

    va_row = next(r for r in holdout_table if r["candidate_id"] == "VIEW_A_SOLO_SUBMODULAR")
    vb_row = next(r for r in holdout_table if r["candidate_id"] == "VIEW_B_SOLO_SUBMODULAR")
    un_row = next(r for r in holdout_table if r["candidate_id"] == "NAIVE_UNION_MAX_AB_SUBMODULAR")
    pr_row = holdout_table[-1]

    holdout_summary = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "primary_candidate": "GEMSDOE52_H52_1_PRIMARY",
        "primary_vs_02778_folds_won": f"{folds_won_prim}/4",
        "anchored_hybrid_vs_02778_folds_won": f"{folds_won_hyb}/4",
        "primary_lm_margin_vs_02778": pr_row["delta_lm_vs_02778"],
        "primary_stratified_d0_3px_margin_vs_02778": round(
            pr_row["stratified_d0_3px"]["dti"] - holdout_table[0]["stratified_d0_3px"]["dti"], 6
        ),
        "primary_stratified_d0_5px_margin_vs_02778": pr_row["delta_d0_5px_vs_02778"],
        "cotrain_vs_single_views": {
            "primary_cotrain_lm": pr_row["lm_mean"],
            "view_a_solo_lm": va_row["lm_mean"],
            "view_b_solo_lm": vb_row["lm_mean"],
            "naive_union_lm": un_row["lm_mean"],
            "primary_cotrain_d0_5px": pr_row["stratified_d0_5px"]["dti"],
            "view_a_solo_d0_5px": va_row["stratified_d0_5px"]["dti"],
            "view_b_solo_d0_5px": vb_row["stratified_d0_5px"]["dti"],
            "naive_union_d0_5px": un_row["stratified_d0_5px"]["dti"],
        },
        "candidates": holdout_table,
    }
    (ev_dir / "holdout_validation.json").write_text(json.dumps(holdout_summary, indent=2) + "\n")

    print("[6/7] Generating Phase 2 Reviewer Geological Reasoning Dossier for every A-only candidate...", flush=True)
    # Pass combined A-only & B-only signals so every A-only buried dot in primary_mask gets a complete dossier
    p_a_combined = _rank_norm(v_a_cotrained, footprint)
    p_b_combined = _rank_norm(v_b_cotrained, footprint)
    dossier = generate_a_only_geological_reasoning(
        emitted_mask=primary_mask,
        p_a=p_a_combined,
        p_b=p_b_combined,
        disagreement_a_only=a_only_buried + cotrain.disagreement_a_only,
        artifact_b_only=b_only_artifact + cotrain.artifact_b_only,
        footprint=footprint,
        aux_path=prep_dir / "physical_aux.npz",
        gdr_csv_path=data_dir / "external" / "gdr_wellspring_in_footprint.csv",
    )
    (ev_dir / "a_only_geological_reasoning.json").write_text(json.dumps(dossier, indent=2) + "\n")
    (docs_data_dir / "a_only_candidates.json").write_text(
        json.dumps(
            {
                "summary": dossier["summary"],
                "top_corridors": dossier["a_only_corridor_dossiers"][:150],
                "b_only_artifacts_suppressed": dossier["b_only_artifact_suppression_sample"],
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"      Wrote reasoning for {dossier['summary']['total_a_only_buried_fault_dots']} A-only buried fault dots "
        f"across {dossier['summary']['total_a_only_structural_corridors']} structural corridors.",
        flush=True,
    )

    print("[7/7] Writing normalized [0, 1] GeoTIFF submissions and running Uniqueness & Format Gates...", flush=True)
    primary_zeros_tif = dl_dir / "gemsdoe52-cotrain-disagree-submodular-20261006-zeros.tif"
    primary_zeros_zip = dl_dir / "gemsdoe52-cotrain-disagree-submodular-20261006-zeros.zip"
    primary_nan_tif = dl_dir / "gemsdoe52-cotrain-disagree-submodular-20261006-nan.tif"
    hybrid_zeros_tif = dl_dir / "gemsdoe52-cotrain-anchored-hybrid-20261006-zeros.tif"

    write_submission_geotiff(primary_mask.astype(np.float32), footprint, primary_zeros_tif, mode="zeros")
    write_submission_geotiff(primary_mask.astype(np.float32), footprint, primary_nan_tif, mode="nan")
    write_submission_geotiff(anchored_hybrid_mask.astype(np.float32), footprint, hybrid_zeros_tif, mode="zeros")

    audit_zeros = verify_geotiff_on_disk(primary_zeros_tif, footprint=footprint, labels=labels, mode="zeros")
    audit_nan = verify_geotiff_on_disk(primary_nan_tif, footprint=footprint, labels=labels, mode="nan")
    audit_hybrid = verify_geotiff_on_disk(hybrid_zeros_tif, footprint=footprint, labels=labels, mode="zeros")
    zip_info = write_submission_zip(primary_zeros_tif, primary_zeros_zip)

    uniqueness = run_uniqueness_gate(
        candidate_tif=primary_zeros_tif,
        reference_dir=data_dir / "scored",
        non_union_report=non_union_primary,
    )
    uniqueness["anchored_hybrid_non_union_verification"] = non_union_hybrid

    sub_note = (
        f"GEMSDOE52 H52-1 | Blum-Mitchell 2-view co-training (View A geophys vs View B surface) + "
        f"disagreement submodular: {audit_zeros['emitted_positive_pixels']:,} dots, 0 within 200m of cat; "
        f"OOF neg r={ind_rep['pearson_r_oof_negative_error']:+.3f}; {folds_won_prim}/4 folds >0.2778"
    )
    assert len(sub_note) <= 200, f"submission_note length {len(sub_note)} > 200"

    submission_receipt = {
        "candidate_id": "GEMSDOE52-H52-1-COTRAIN-DISAGREE",
        "submission_name": "GEMSDOE52-CoTrain-Disagree-H52-1",
        "submission_note": sub_note,
        "submission_note_char_length": len(sub_note),
        "primary_zeros_tif": audit_zeros,
        "primary_zeros_zip": zip_info,
        "companion_nan_tif": audit_nan,
        "secondary_anchored_hybrid_tif": audit_hybrid,
        "uniqueness_gate": uniqueness,
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    (ev_dir / "submission_audit.json").write_text(json.dumps(submission_receipt, indent=2) + "\n")
    (ev_dir / "uniqueness_gate.json").write_text(json.dumps(uniqueness, indent=2) + "\n")
    (dl_dir / "gemsdoe52-cotrain-disagree-submodular-20261006-audit.json").write_text(
        json.dumps(submission_receipt, indent=2) + "\n"
    )

    print(
        f"[DONE] Primary TIF: {primary_zeros_tif.name} | "
        f"SHA256={audit_zeros['sha256'][:16]}... | "
        f"Dots={audit_zeros['emitted_positive_pixels']} | "
        f"All checks passed={audit_zeros['all_checks_passed']} | "
        f"Uniqueness gate passed={uniqueness['uniqueness_gate_passed']} "
        f"(max Jaccard vs prior={uniqueness['max_jaccard_vs_prior_submissions']})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
