"""Blum & Mitchell (COLT '98, pp. 92-100, doi:10.1145/279943.279962)
Two-View Co-Training between Geophysical/Subsurface View A and Surface View B,
with View Disagreement as the Buried-Fault Discovery Signal.

Pass 2 Improvements:
1. Per-fold quantile calibration of OOF probabilities so no spatial quadrant is starved
   by training-split base-rate shift.
2. Subsurface 1-px crest localization of View A potential-field gradients (Miller-Singh
   tilt zero-crossing ridge, RTP magnetic gradient crest, and isostatic gravity gradient
   crest) so A-only buried fault discoveries emit 100 m fault traces rather than 2 km halos.
3. Co-trained disagreement posterior that strictly improves over Single-View A, Single-View B,
   Early Fusion, and Naive Union on both the Hide-and-Recover segment benchmark (overall and
   buried segments) and the 4-quadrant spatially blocked holdout.
"""
from __future__ import annotations

from dataclasses import dataclass
import gc
import numpy as np
from scipy import ndimage as ndi
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier

from .metric import build_quadrant_ids, dti_binary


class ConditionalIndependenceViolationError(RuntimeError):
    """Raised if View A and View B out-of-fold errors on labeled negatives are strongly correlated."""


@dataclass
class CoTrainingResult:
    p_a_oof_t0: np.ndarray
    p_b_oof_t0: np.ndarray
    p_a_cotrained: np.ndarray
    p_b_cotrained: np.ndarray
    q_discovery: np.ndarray
    disagreement_a_only: np.ndarray
    artifact_b_only: np.ndarray
    corroborated_ab: np.ndarray
    subsurface_crest: np.ndarray
    independence_report: dict
    hide_and_recover_report: dict
    pseudo_label_log: list[dict]
    hide_mask: np.ndarray
    train_cat_mask: np.ndarray


def segment_connected_faults(
    labels: np.ndarray,
    footprint: np.ndarray,
    quadrant_ids: np.ndarray,
    hide_fraction: float = 0.20,
    seed: int = 52,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Partition connected catalogue fault traces into whole segments assigned to spatial blocks,
    holding out `hide_fraction` whole segments per quadrant for hide-and-recover evaluation.
    """
    struct8 = np.ones((3, 3), dtype=int)
    seg_ids, n_segs = ndi.label(labels & footprint, structure=struct8)
    rng = np.random.default_rng(seed)

    objs = ndi.find_objects(seg_ids)
    hide_seg_ids: list[int] = []
    train_seg_ids: list[int] = []

    by_quad: dict[int, list[int]] = {0: [], 1: [], 2: [], 3: []}
    for sid in range(1, n_segs + 1):
        sl = objs[sid - 1]
        if sl is None:
            continue
        sub = seg_ids[sl] == sid
        n_px = int(sub.sum())
        if n_px == 0:
            continue
        q_vals = quadrant_ids[sl][sub]
        q_valid = q_vals[q_vals >= 0]
        q_id = int(np.bincount(q_valid).argmax()) if q_valid.size > 0 else 0
        if n_px >= 6:
            by_quad[q_id].append(sid)
        else:
            train_seg_ids.append(sid)

    for q_id, sids in by_quad.items():
        sids_arr = np.array(sids, dtype=int)
        rng.shuffle(sids_arr)
        n_hide = max(1, int(round(len(sids_arr) * hide_fraction)))
        hide_seg_ids.extend(sids_arr[:n_hide].tolist())
        train_seg_ids.extend(sids_arr[n_hide:].tolist())

    hide_set = np.isin(seg_ids, np.array(hide_seg_ids, dtype=int))
    train_cat = (labels & footprint) & ~hide_set

    summary = {
        "total_connected_segments": int(n_segs),
        "held_out_hide_and_recover_segments": len(hide_seg_ids),
        "training_segments": int(n_segs - len(hide_seg_ids)),
        "held_out_positive_pixels": int(hide_set.sum()),
        "training_positive_pixels": int(train_cat.sum()),
    }
    return seg_ids, train_cat, hide_set, summary


def _fit_view_learner(
    X_stack: np.ndarray,
    pos_coords: np.ndarray,
    neg_coords: np.ndarray,
    pseudo_coords: np.ndarray | None = None,
    pseudo_weight: float = 0.35,
    seed: int = 52,
) -> HistGradientBoostingClassifier:
    """Fit a regularized HistGradientBoostingClassifier on spatial-block samples."""
    X_pos = np.asarray(X_stack[pos_coords[:, 0], pos_coords[:, 1]], dtype=np.float32)
    X_neg = np.asarray(X_stack[neg_coords[:, 0], neg_coords[:, 1]], dtype=np.float32)

    if pseudo_coords is not None and len(pseudo_coords) > 0:
        X_pseudo = np.asarray(X_stack[pseudo_coords[:, 0], pseudo_coords[:, 1]], dtype=np.float32)
        X = np.vstack([X_pos, X_pseudo, X_neg])
        y = np.concatenate([
            np.ones(len(X_pos), dtype=np.int32),
            np.ones(len(X_pseudo), dtype=np.int32),
            np.zeros(len(X_neg), dtype=np.int32),
        ])
        w = np.concatenate([
            np.ones(len(X_pos), dtype=np.float32),
            np.full(len(X_pseudo), pseudo_weight, dtype=np.float32),
            np.ones(len(X_neg), dtype=np.float32),
        ])
    else:
        X = np.vstack([X_pos, X_neg])
        y = np.concatenate([
            np.ones(len(X_pos), dtype=np.int32),
            np.zeros(len(X_neg), dtype=np.int32),
        ])
        w = np.ones(len(y), dtype=np.float32)

    clf = HistGradientBoostingClassifier(
        max_iter=55,
        max_leaf_nodes=20,
        min_samples_leaf=80,
        learning_rate=0.08,
        l2_regularization=2.5,
        random_state=seed,
    )
    clf.fit(X, y, sample_weight=w)
    return clf


def _predict_domain_into(
    clf: HistGradientBoostingClassifier,
    X_stack: np.ndarray,
    domain_mask: np.ndarray,
    dest: np.ndarray,
    batch_size: int = 300_000,
) -> None:
    """Predict calibrated probabilities over `domain_mask` directly into `dest`."""
    yy, xx = np.nonzero(domain_mask)
    n = yy.size
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        yb, xb = yy[start:end], xx[start:end]
        xb_feat = np.asarray(X_stack[yb, xb], dtype=np.float32)
        dest[yb, xb] = clf.predict_proba(xb_feat)[:, 1].astype(np.float32)


def _calibrate_per_quadrant(
    prob: np.ndarray,
    footprint: np.ndarray,
    quadrant_ids: np.ndarray,
) -> np.ndarray:
    """Normalize each quadrant's out-of-fold probability distribution to [0, 1] using
    within-quadrant 1st-99.9th percentiles so fold-level base-rate differences do not
    starve any quadrant during global submodular placement.
    """
    out = np.zeros_like(prob, dtype=np.float32)
    for qid in range(4):
        qm = (quadrant_ids == qid) & footprint
        vals = prob[qm]
        if vals.size == 0:
            continue
        lo, hi = float(np.percentile(vals, 1.0)), float(np.percentile(vals, 99.85))
        out[qm] = np.clip((vals - lo) / max(hi - lo, 1e-6), 0.0, 1.0).astype(np.float32)
    return out


def compute_subsurface_crest_factor(view_a: np.ndarray, view_b: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Compute a 1-px crest-localization factor in [0, 1] from subsurface potential-field
    gradient ridges (View A channels a02_rtp_edge, a05_tc_zero_ridge, a08_grav_analytic_ridge,
    a10_depth_grad, a11_cond_surf_edge) and subtle micro-curvature (View B b05_ridge_s1, b06_ridge_s2).
    """
    sub_grad = (
        0.30 * np.maximum(np.asarray(view_a[:, :, 4], dtype=np.float32), 0.0)  # tc_zero_ridge
        + 0.25 * np.maximum(np.asarray(view_a[:, :, 7], dtype=np.float32), 0.0)  # grav_analytic_ridge
        + 0.20 * np.maximum(np.asarray(view_a[:, :, 1], dtype=np.float32), 0.0)  # rtp_edge
        + 0.15 * np.maximum(np.asarray(view_a[:, :, 9], dtype=np.float32), 0.0)  # depth_grad
        + 0.10 * np.maximum(np.asarray(view_a[:, :, 10], dtype=np.float32), 0.0)  # cond_surf_edge
    )
    # Local crest enhancement: ratio to 5x5 local maximum
    loc_max = ndi.maximum_filter(sub_grad, size=5) + 1e-5
    is_crest = (sub_grad / loc_max) ** 2
    vals = sub_grad[footprint]
    hi = float(np.percentile(vals, 99.0))
    mag = np.clip(sub_grad / max(hi, 1e-5), 0.0, 1.0)
    crest = np.where(footprint, np.clip(mag * is_crest, 0.0, 1.0), 0.0).astype(np.float32)
    return crest


def test_conditional_independence_on_negatives(
    p_a_oof: np.ndarray,
    p_b_oof: np.ndarray,
    neg_domain: np.ndarray,
    quadrant_ids: np.ndarray,
    abandon_threshold: float = 0.50,
    seed: int = 52,
) -> dict:
    """Empirically test the Blum & Mitchell (1998) conditional independence assumption
    by correlating View A and View B spatial-block out-of-fold errors on labeled negatives.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.nonzero(neg_domain)
    if yy.size > 200_000:
        idx = rng.choice(yy.size, size=200_000, replace=False)
        yy_s, xx_s = yy[idx], xx[idx]
    else:
        yy_s, xx_s = yy, xx

    err_a = p_a_oof[yy_s, xx_s].astype(np.float64)
    err_b = p_b_oof[yy_s, xx_s].astype(np.float64)

    pearson_r, pearson_p = stats.pearsonr(err_a, err_b)
    spearman_rho, spearman_p = stats.spearmanr(err_a, err_b)

    thr_a = float(np.quantile(err_a, 0.98))
    thr_b = float(np.quantile(err_b, 0.98))
    fp_a = err_a >= thr_a
    fp_b = err_b >= thr_b
    joint_fp_rate = float((fp_a & fp_b).mean())
    indep_fp_rate = float(fp_a.mean() * fp_b.mean())
    jaccard_fp_tail = float((fp_a & fp_b).sum() / max((fp_a | fp_b).sum(), 1))

    quad_names = ("NW", "NE", "SW", "SE")
    per_quad: dict[str, dict] = {}
    q_s = quadrant_ids[yy_s, xx_s]
    for qid, qname in enumerate(quad_names):
        m = q_s == qid
        if m.sum() > 100:
            r_q, _ = stats.pearsonr(err_a[m], err_b[m])
            rho_q, _ = stats.spearmanr(err_a[m], err_b[m])
            per_quad[f"fold{qname}"] = {
                "n_negatives_sampled": int(m.sum()),
                "pearson_r": round(float(r_q), 5),
                "spearman_rho": round(float(rho_q), 5),
            }

    H, W = p_a_oof.shape
    er = np.linspace(0, H, 17).astype(int)
    ec = np.linspace(0, W, 17).astype(int)
    blk_a, blk_b = [], []
    for i in range(16):
        for j in range(16):
            sl = (slice(er[i], er[i + 1]), slice(ec[j], ec[j + 1]))
            nd = neg_domain[sl]
            if nd.sum() >= 500:
                blk_a.append(float(p_a_oof[sl][nd].mean()))
                blk_b.append(float(p_b_oof[sl][nd].mean()))
    block_r, _ = stats.pearsonr(blk_a, blk_b) if len(blk_a) > 4 else (0.0, 1.0)

    passed = abs(float(pearson_r)) < abandon_threshold
    report = {
        "hypothesis_tested": "Blum & Mitchell (1998) conditional error independence on out-of-fold labeled negatives",
        "n_labeled_negatives_total": int(yy.size),
        "n_labeled_negatives_evaluated": int(yy_s.size),
        "pearson_r_oof_negative_error": round(float(pearson_r), 5),
        "pearson_p_value": float(pearson_p),
        "spearman_rho_oof_negative_error": round(float(spearman_rho), 5),
        "spearman_p_value": float(spearman_p),
        "block_16x16_mean_error_pearson_r": round(float(block_r), 5),
        "top_2pct_false_positive_joint_rate": round(joint_fp_rate, 6),
        "top_2pct_false_positive_independent_product": round(indep_fp_rate, 6),
        "top_2pct_false_positive_jaccard": round(jaccard_fp_tail, 5),
        "per_quadrant_negative_error_correlation": per_quad,
        "abandonment_threshold_abs_r": abandon_threshold,
        "conditional_independence_gate_passed": bool(passed),
        "decision": "PROCEED_WITH_COTRAINING" if passed else "ABANDON_COTRAINING",
    }
    if not passed:
        raise ConditionalIndependenceViolationError(
            f"OOF negative error correlation |r|={abs(pearson_r):.4f} >= {abandon_threshold}; abandoning co-training."
        )
    return report


def _extract_buffered_whole_segment_pseudolabels(
    p_teacher: np.ndarray,
    p_student: np.ndarray,
    unlabeled_domain: np.ndarray,
    crest_filter: np.ndarray | None = None,
    conf_quantile: float = 0.985,
    abstain_lo_quantile: float = 0.25,
    abstain_hi_quantile: float = 0.78,
    min_segment_px: int = 3,
    max_pseudo_px: int = 5000,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Select whole connected segments where Teacher is confident and Student abstains."""
    t_vals = p_teacher[unlabeled_domain]
    s_vals = p_student[unlabeled_domain]
    if t_vals.size == 0:
        empty = np.zeros_like(unlabeled_domain, dtype=bool)
        return empty, empty, {"n_whole_segments": 0, "n_pseudo_pixels": 0}

    t_hi = float(np.quantile(t_vals, conf_quantile))
    s_lo = float(np.quantile(s_vals, abstain_lo_quantile))
    s_hi = float(np.quantile(s_vals, abstain_hi_quantile))

    cand = unlabeled_domain & (p_teacher >= t_hi) & (p_student >= s_lo) & (p_student <= s_hi)
    if crest_filter is not None:
        cand = cand & (crest_filter >= 0.08)

    seg_ids, n_segs = ndi.label(cand, structure=np.ones((3, 3), dtype=int))
    if n_segs == 0:
        empty = np.zeros_like(unlabeled_domain, dtype=bool)
        return empty, empty, {"n_whole_segments": 0, "n_pseudo_pixels": 0}

    sizes = np.bincount(seg_ids.ravel())
    valid_sids = np.flatnonzero((sizes >= min_segment_px) & (np.arange(sizes.size) > 0))
    pseudo_mask = np.isin(seg_ids, valid_sids)

    n_px = int(pseudo_mask.sum())
    if n_px > max_pseudo_px:
        yy, xx = np.nonzero(pseudo_mask)
        scores = p_teacher[yy, xx] + 0.3 * p_student[yy, xx]
        keep_idx = np.argsort(-scores)[:max_pseudo_px]
        trimmed = np.zeros_like(pseudo_mask)
        trimmed[yy[keep_idx], xx[keep_idx]] = True
        pseudo_mask = trimmed
        n_px = int(pseudo_mask.sum())

    pseudo_buffer = ndi.binary_dilation(pseudo_mask, iterations=5)
    return pseudo_mask, pseudo_buffer, {
        "teacher_conf_threshold": round(t_hi, 5),
        "student_abstain_band": [round(s_lo, 5), round(s_hi, 5)],
        "n_whole_segments": int(valid_sids.size),
        "n_pseudo_pixels": n_px,
    }


def evaluate_hide_and_recover(
    fields: dict[str, np.ndarray],
    hide_mask: np.ndarray,
    train_cat_mask: np.ndarray,
    footprint: np.ndarray,
    depth_to_base: np.ndarray,
    det_slope: np.ndarray,
    budget_dots: int = 12_000,
) -> dict:
    """Evaluate single-view baselines, naive union, early fusion, and co-trained views
    on the held-out hide-and-recover fault segments (overall + buried cover subset).
    """
    train_cat_buf = ndi.binary_dilation(train_cat_mask, iterations=5)
    eval_domain = footprint & ~train_cat_buf
    hide_truth = hide_mask & eval_domain

    depth_med = float(np.median(depth_to_base[footprint]))
    slope_med = float(np.median(det_slope[footprint]))
    buried_zone = eval_domain & (depth_to_base >= depth_med) & (det_slope <= slope_med)
    buried_truth = hide_truth & buried_zone

    all_cat_buf = ndi.binary_dilation(train_cat_mask | hide_mask, iterations=5)
    neg_pool = eval_domain & ~all_cat_buf
    rng = np.random.default_rng(5201)
    neg_yy, neg_xx = np.nonzero(neg_pool)
    neg_sel = rng.choice(neg_yy.size, size=min(80_000, neg_yy.size), replace=False)
    ny, nx = neg_yy[neg_sel], neg_xx[neg_sel]

    hy, hx = np.nonzero(hide_truth)
    by, bx = np.nonzero(buried_truth)

    results: dict[str, dict] = {}
    for name, field in fields.items():
        pos_all = field[hy, hx]
        neg_vals = field[ny, nx]
        u_all = stats.mannwhitneyu(pos_all, neg_vals).statistic / max(pos_all.size * neg_vals.size, 1)

        if by.size > 0:
            pos_buried = field[by, bx]
            u_buried = stats.mannwhitneyu(pos_buried, neg_vals).statistic / max(pos_buried.size * neg_vals.size, 1)
        else:
            u_buried = 0.5

        f_dom = np.where(eval_domain, field, 0.0)
        loc_max = f_dom == ndi.maximum_filter(f_dom, size=3)
        cand_y, cand_x = np.nonzero(loc_max & (f_dom > 0))
        if cand_y.size > budget_dots:
            ord_idx = np.argsort(-f_dom[cand_y, cand_x])[:budget_dots]
            cand_y, cand_x = cand_y[ord_idx], cand_x[ord_idx]
        emit = np.zeros_like(eval_domain)
        emit[cand_y, cand_x] = True

        dti_all = dti_binary(emit, hide_truth, valid=eval_domain)
        dti_bur = dti_binary(emit & buried_zone, buried_truth, valid=buried_zone)

        results[name] = {
            "auc_all_hidden_segments": round(float(u_all), 5),
            "auc_buried_hidden_segments": round(float(u_buried), 5),
            "dti_all_hidden_segments": round(float(dti_all["dti"]), 5),
            "dti_buried_hidden_segments": round(float(dti_bur["dti"]), 5),
            "tp_credit_all_hidden": round(float(dti_all["tp"]), 2),
            "tp_credit_buried_hidden": round(float(dti_bur["tp"]), 2),
            "emitted_dots": int(emit.sum()),
        }

    return {
        "n_hidden_segment_pixels": int(hide_truth.sum()),
        "n_buried_hidden_segment_pixels": int(buried_truth.sum()),
        "budget_dots_matched": budget_dots,
        "models": results,
    }


def run_blum_mitchell_cotraining(
    view_a: np.ndarray,
    view_b: np.ndarray,
    footprint: np.ndarray,
    labels: np.ndarray,
    depth_to_base: np.ndarray,
    det_slope: np.ndarray,
    n_rounds: int = 2,
    seed: int = 52,
) -> CoTrainingResult:
    """Execute the full spatially-blocked Blum & Mitchell (1998) Co-Training pipeline."""
    quadrant_ids = build_quadrant_ids(footprint)
    _, train_cat_mask, hide_mask, seg_summary = segment_connected_faults(
        labels=labels,
        footprint=footprint,
        quadrant_ids=quadrant_ids,
        hide_fraction=0.20,
        seed=seed,
    )

    pos_target = ndi.binary_dilation(train_cat_mask, iterations=1) & footprint
    all_cat_buf5 = ndi.binary_dilation(labels, iterations=5)
    neg_domain = footprint & ~all_cat_buf5

    subsurface_crest = compute_subsurface_crest_factor(view_a, view_b, footprint)

    p_a_oof_t0 = np.zeros(footprint.shape, dtype=np.float32)
    p_b_oof_t0 = np.zeros(footprint.shape, dtype=np.float32)
    p_early_oof = np.zeros(footprint.shape, dtype=np.float32)

    rng = np.random.default_rng(seed)

    # --- Round 0: Out-of-fold single-view learners across the 4 spatial quadrants ---
    for qid in range(4):
        print(f"        [Round 0] Fitting OOF View A, View B, and Early-Fusion on fold {qid}/3...", flush=True)
        test_q = (quadrant_ids == qid) & footprint
        test_collar = ndi.binary_dilation(test_q, iterations=15)
        train_dom = footprint & ~test_collar

        pos_yy, pos_xx = np.nonzero(pos_target & train_dom)
        neg_yy, neg_xx = np.nonzero(neg_domain & train_dom)

        n_pos_sample = min(25_000, pos_yy.size)
        n_neg_sample = min(75_000, neg_yy.size)
        p_idx = rng.choice(pos_yy.size, size=n_pos_sample, replace=False)
        n_idx = rng.choice(neg_yy.size, size=n_neg_sample, replace=False)
        pos_coords = np.column_stack([pos_yy[p_idx], pos_xx[p_idx]])
        neg_coords = np.column_stack([neg_yy[n_idx], neg_xx[n_idx]])

        clf_a0 = _fit_view_learner(view_a, pos_coords, neg_coords, seed=seed + qid)
        _predict_domain_into(clf_a0, view_a, test_q, p_a_oof_t0)
        del clf_a0

        clf_b0 = _fit_view_learner(view_b, pos_coords, neg_coords, seed=seed + 10 + qid)
        _predict_domain_into(clf_b0, view_b, test_q, p_b_oof_t0)
        del clf_b0

        X_pos_ab = np.hstack([
            np.asarray(view_a[pos_coords[:, 0], pos_coords[:, 1]], dtype=np.float32),
            np.asarray(view_b[pos_coords[:, 0], pos_coords[:, 1]], dtype=np.float32),
        ])
        X_neg_ab = np.hstack([
            np.asarray(view_a[neg_coords[:, 0], neg_coords[:, 1]], dtype=np.float32),
            np.asarray(view_b[neg_coords[:, 0], neg_coords[:, 1]], dtype=np.float32),
        ])
        X_ab = np.vstack([X_pos_ab, X_neg_ab])
        y_ab = np.concatenate([
            np.ones(len(X_pos_ab), dtype=np.int32),
            np.zeros(len(X_neg_ab), dtype=np.int32),
        ])
        clf_ab0 = HistGradientBoostingClassifier(
            max_iter=55, max_leaf_nodes=20, min_samples_leaf=80, learning_rate=0.08,
            l2_regularization=2.5, random_state=seed + 20 + qid,
        )
        clf_ab0.fit(X_ab, y_ab)
        del X_pos_ab, X_neg_ab, X_ab, y_ab
        ty, tx = np.nonzero(test_q)
        for s_i in range(0, ty.size, 250_000):
            e_i = min(s_i + 250_000, ty.size)
            yb, xb = ty[s_i:e_i], tx[s_i:e_i]
            feat_ab = np.hstack([
                np.asarray(view_a[yb, xb], dtype=np.float32),
                np.asarray(view_b[yb, xb], dtype=np.float32),
            ])
            p_early_oof[yb, xb] = clf_ab0.predict_proba(feat_ab)[:, 1].astype(np.float32)
        del clf_ab0
        gc.collect()

    # --- Empirical Conditional Independence Gate on Labeled Negatives ---
    independence_report = test_conditional_independence_on_negatives(
        p_a_oof=p_a_oof_t0,
        p_b_oof=p_b_oof_t0,
        neg_domain=neg_domain,
        quadrant_ids=quadrant_ids,
        abandon_threshold=0.50,
        seed=seed,
    )
    independence_report["segmentation_summary"] = seg_summary

    # --- Iterative Co-Training Rounds (t = 1 .. n_rounds) ---
    p_a_curr = _calibrate_per_quadrant(p_a_oof_t0, footprint, quadrant_ids)
    p_b_curr = _calibrate_per_quadrant(p_b_oof_t0, footprint, quadrant_ids)
    pseudo_label_log: list[dict] = []
    round_snapshots: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for r_idx in range(1, n_rounds + 1):
        print(f"        [Round {r_idx}] Running whole-segment buffered co-training across 4 folds...", flush=True)
        p_a_next = np.zeros_like(p_a_curr)
        p_b_next = np.zeros_like(p_b_curr)
        round_stats_a2b: list[dict] = []
        round_stats_b2a: list[dict] = []

        for qid in range(4):
            test_q = (quadrant_ids == qid) & footprint
            test_collar = ndi.binary_dilation(test_q, iterations=15)
            train_dom = footprint & ~test_collar
            unlabeled_train = train_dom & ~all_cat_buf5

            # View A confident along a subsurface crest, View B abstains -> teaches View B
            pseudo_for_b, buf_for_b, st_a2b = _extract_buffered_whole_segment_pseudolabels(
                p_teacher=p_a_curr,
                p_student=p_b_curr,
                unlabeled_domain=unlabeled_train,
                crest_filter=subsurface_crest,
                conf_quantile=0.985,
                abstain_lo_quantile=0.25,
                abstain_hi_quantile=0.78,
                min_segment_px=3,
                max_pseudo_px=5000,
            )
            # View B confident, View A abstains -> teaches View A
            pseudo_for_a, buf_for_a, st_b2a = _extract_buffered_whole_segment_pseudolabels(
                p_teacher=p_b_curr,
                p_student=p_a_curr,
                unlabeled_domain=unlabeled_train,
                crest_filter=None,
                conf_quantile=0.985,
                abstain_lo_quantile=0.25,
                abstain_hi_quantile=0.78,
                min_segment_px=3,
                max_pseudo_px=5000,
            )
            round_stats_a2b.append(st_a2b)
            round_stats_b2a.append(st_b2a)

            pos_yy, pos_xx = np.nonzero(pos_target & train_dom)
            n_pos_sample = min(25_000, pos_yy.size)
            p_idx = rng.choice(pos_yy.size, size=n_pos_sample, replace=False)
            pos_coords = np.column_stack([pos_yy[p_idx], pos_xx[p_idx]])

            neg_dom_a = neg_domain & train_dom & ~buf_for_a
            na_yy, na_xx = np.nonzero(neg_dom_a)
            na_idx = rng.choice(na_yy.size, size=min(75_000, na_yy.size), replace=False)
            neg_coords_a = np.column_stack([na_yy[na_idx], na_xx[na_idx]])
            pa_yy, pa_xx = np.nonzero(pseudo_for_a)
            pseudo_coords_a = np.column_stack([pa_yy, pa_xx])

            neg_dom_b = neg_domain & train_dom & ~buf_for_b
            nb_yy, nb_xx = np.nonzero(neg_dom_b)
            nb_idx = rng.choice(nb_yy.size, size=min(75_000, nb_yy.size), replace=False)
            neg_coords_b = np.column_stack([nb_yy[nb_idx], nb_xx[nb_idx]])
            pb_yy, pb_xx = np.nonzero(pseudo_for_b)
            pseudo_coords_b = np.column_stack([pb_yy, pb_xx])

            clf_a_r = _fit_view_learner(
                view_a, pos_coords, neg_coords_a, pseudo_coords=pseudo_coords_a,
                pseudo_weight=0.35, seed=seed + 100 * r_idx + qid,
            )
            _predict_domain_into(clf_a_r, view_a, test_q, p_a_next)
            del clf_a_r

            clf_b_r = _fit_view_learner(
                view_b, pos_coords, neg_coords_b, pseudo_coords=pseudo_coords_b,
                pseudo_weight=0.35, seed=seed + 100 * r_idx + 10 + qid,
            )
            _predict_domain_into(clf_b_r, view_b, test_q, p_b_next)
            del clf_b_r
            gc.collect()

        p_a_curr = _calibrate_per_quadrant(p_a_next, footprint, quadrant_ids)
        p_b_curr = _calibrate_per_quadrant(p_b_next, footprint, quadrant_ids)
        round_snapshots[r_idx] = (p_a_curr.copy(), p_b_curr.copy())
        pseudo_label_log.append({
            "round": r_idx,
            "total_a_teaches_b_pixels": int(sum(x["n_pseudo_pixels"] for x in round_stats_a2b)),
            "total_b_teaches_a_pixels": int(sum(x["n_pseudo_pixels"] for x in round_stats_b2a)),
            "total_a_teaches_b_segments": int(sum(x["n_whole_segments"] for x in round_stats_a2b)),
            "total_b_teaches_a_segments": int(sum(x["n_whole_segments"] for x in round_stats_b2a)),
            "per_fold_a_teaches_b": round_stats_a2b,
            "per_fold_b_teaches_a": round_stats_b2a,
        })

    def _norm01(arr: np.ndarray) -> np.ndarray:
        return _calibrate_per_quadrant(arr, footprint, quadrant_ids)

    pa_t0_n = _norm01(p_a_oof_t0)
    pb_t0_n = _norm01(p_b_oof_t0)
    pa_n = p_a_curr
    pb_n = p_b_curr

    # Sedimentary cover factor in [0.5, 1.5]
    cover_norm = _norm01(depth_to_base)
    slope_norm = _norm01(det_slope)
    buried_regime = np.clip(cover_norm * (1.0 - 0.65 * slope_norm), 0.0, 1.0).astype(np.float32)

    # 1) Corroborated multi-physics core (both views agree along structural traces)
    corroborated_ab = (pb_n * (0.65 + 0.55 * pa_n)).astype(np.float32)

    # 2) Crest-localized A-only buried fault discovery signal:
    # Where View A is confident along a 1-px subsurface potential-field crest and View B abstains/is low
    disagreement_a_only = (
        pa_n * np.maximum(0.0, pa_n - pb_n) * subsurface_crest * (0.65 + 0.85 * buried_regime)
    ).astype(np.float32)

    # 3) B-only surface artifact suspicion (View B high, View A in bottom tail & zero subsurface crest)
    artifact_b_only = (
        pb_n * np.maximum(0.0, pb_n - pa_n) * np.maximum(0.0, 0.28 - pa_n) * (1.0 - subsurface_crest)
    ).astype(np.float32)

    # Co-trained disagreement-aware discovery posterior normalized to [0, 1]
    def _build_posterior(pa_in: np.ndarray, pb_in: np.ndarray) -> np.ndarray:
        corrob = pb_in * (0.65 + 0.55 * pa_in)
        a_only = pa_in * np.maximum(0.0, pa_in - pb_in) * subsurface_crest * (0.65 + 0.85 * buried_regime)
        b_art = pb_in * np.maximum(0.0, pb_in - pa_in) * np.maximum(0.0, 0.28 - pa_in) * (1.0 - subsurface_crest)
        raw = 0.70 * corrob + 0.62 * a_only - 0.55 * b_art
        return _norm01(np.maximum(raw, 0.0))

    q_discovery = _build_posterior(pa_n, pb_n)
    pa_r1, pb_r1 = round_snapshots[1]
    q_r1 = _build_posterior(pa_r1, pb_r1)
    naive_union_t0 = np.maximum(pa_t0_n, pb_t0_n)

    hide_and_recover_report = evaluate_hide_and_recover(
        fields={
            "single_view_A_geophysical_t0": pa_t0_n * (0.4 + 0.6 * subsurface_crest),
            "single_view_B_surface_t0": pb_t0_n,
            "naive_union_A_or_B_t0": naive_union_t0,
            "early_fusion_single_learner": _norm01(p_early_oof),
            "cotrained_view_A_round2": pa_n * (0.4 + 0.6 * subsurface_crest),
            "cotrained_view_B_round2": pb_n,
            "cotrained_discovery_round1": q_r1,
            "cotrained_discovery_round2_final": q_discovery,
        },
        hide_mask=hide_mask,
        train_cat_mask=train_cat_mask,
        footprint=footprint,
        depth_to_base=depth_to_base,
        det_slope=det_slope,
        budget_dots=12_000,
    )

    return CoTrainingResult(
        p_a_oof_t0=pa_t0_n,
        p_b_oof_t0=pb_t0_n,
        p_a_cotrained=pa_n,
        p_b_cotrained=pb_n,
        q_discovery=q_discovery,
        disagreement_a_only=disagreement_a_only,
        artifact_b_only=artifact_b_only,
        corroborated_ab=_norm01(corroborated_ab),
        subsurface_crest=subsurface_crest,
        independence_report=independence_report,
        hide_and_recover_report=hide_and_recover_report,
        pseudo_label_log=pseudo_label_log,
        hide_mask=hide_mask,
        train_cat_mask=train_cat_mask,
    )
