"""Official Distance-Weighted Tversky Index (DTI) and spatially blocked evaluation instruments.

Verified from the official competition specification (DrivenData Page 967):
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric
and NREL/DOE GEMS Prize rules (https://docs.nlr.gov/docs/fy26osti/96647.pdf).
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion, distance_transform_edt

from .spec import ALPHA, BETA, EPS_METRIC, RADIUS_PX


def kernel(d: np.ndarray | float, radius: float = RADIUS_PX) -> np.ndarray:
    """Linear triangular distance kernel k(d) = max(1 - d / R, 0), R = 3 px = 300 m."""
    return np.maximum(1.0 - np.asarray(d, dtype=np.float64) / radius, 0.0)


def kernel_offsets(radius: float = RADIUS_PX) -> list[tuple[int, int, float]]:
    """All integer grid offsets (dy, dx, k) within the positive support of k(d)."""
    r = int(np.ceil(radius))
    out: list[tuple[int, int, float]] = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            k = float(kernel(np.hypot(dy, dx), radius))
            if k > 0.0:
                out.append((dy, dx, k))
    return out


_OFFSETS = kernel_offsets()


def marginal_inclusion_threshold(current_dti: float, alpha: float = ALPHA) -> float:
    """Minimum marginal kernel credit Delta_T for an added unit-mass dot to improve DTI.

    Exact derivation:
      DTI = T / (alpha * (T + F) + beta * |G|) = T / (alpha * S + beta * |G|)
      for binary unit-mass dots where each dot contributes dT = k and dF = 1 - k,
      so d(T + F) = 1 and denominator increases by exactly alpha.
      Thus d(DTI) > 0  <=>  k > alpha * DTI.
    """
    return float(alpha * current_dti)


def dti_exact(
    pred: np.ndarray,
    truth: np.ndarray,
    valid: np.ndarray | None = None,
    known: np.ndarray | None = None,
    alpha: float = ALPHA,
    beta: float = BETA,
) -> dict:
    """Exact DTI for arbitrary continuous or binary predictions in [0, 1]."""
    pred = np.asarray(pred)
    truth = np.asarray(truth)
    if pred.ndim != 2 or pred.shape != truth.shape:
        raise ValueError("pred and truth must be 2D arrays of identical shape")
    valid_mask = np.ones(pred.shape, bool) if valid is None else np.asarray(valid, bool)
    known_mask = np.zeros(pred.shape, bool) if known is None else np.asarray(known, bool)
    active = valid_mask & ~known_mask
    vals = pred[active]
    if not np.isfinite(vals).all() or (vals < 0.0).any() or (vals > 1.0).any():
        raise ValueError("Predicted values inside active domain must be finite and in [0, 1]")
    p = np.where(active & np.isfinite(pred), pred, 0.0).astype(np.float64)
    g = active & (truth > 0)
    H, W = p.shape
    yy, xx = np.nonzero(g)
    n_g = int(yy.size)
    s_mass = float(p.sum())
    if n_g == 0:
        return {
            "tp": 0.0,
            "fp": s_mass,
            "fn": 0.0,
            "n_truth": 0,
            "mass": s_mass,
            "self_kernel_mass": 0.0,
            "dti": 0.0,
            "dti_algebra": 0.0,
            "coverage": 0.0,
        }
    credit = np.zeros(n_g, dtype=np.float64)
    for dy, dx, k in _OFFSETS:
        ny, nx = yy + dy, xx + dx
        ok = (ny >= 0) & (ny < H) & (nx >= 0) & (nx < W)
        credit[ok] = np.maximum(credit[ok], p[ny[ok], nx[ok]] * k)
    tp = float(credit.sum())
    fn = float(n_g) - tp
    dg = distance_transform_edt(~g)
    k_near = kernel(dg)
    m_mass = float((p * k_near).sum())
    fp = float((p * (1.0 - k_near)).sum())
    denom = tp + alpha * fp + beta * fn + EPS_METRIC
    denom_alg = alpha * (tp + s_mass - m_mass) + beta * n_g + EPS_METRIC
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "n_truth": n_g,
        "mass": s_mass,
        "self_kernel_mass": m_mass,
        "dti": float(tp / denom),
        "dti_algebra": float(tp / denom_alg),
        "coverage": float(tp / n_g),
    }


def dti_binary(
    pred_bool: np.ndarray,
    truth_bool: np.ndarray,
    valid: np.ndarray | None = None,
    known: np.ndarray | None = None,
    alpha: float = ALPHA,
    beta: float = BETA,
) -> dict:
    """Fast exact DTI for binary {0, 1} predictions via Euclidean distance transforms."""
    p = np.asarray(pred_bool, bool)
    g = np.asarray(truth_bool, bool)
    valid_mask = np.ones(p.shape, bool) if valid is None else np.asarray(valid, bool)
    known_mask = np.zeros(p.shape, bool) if known is None else np.asarray(known, bool)
    active = valid_mask & ~known_mask
    p = p & active
    g = g & active
    n_p = int(p.sum())
    n_g = int(g.sum())
    if n_g == 0:
        return {"tp": 0.0, "fp": float(n_p), "fn": 0.0, "n_p": n_p, "n_truth": 0, "dti": 0.0, "coverage": 0.0}
    if n_p == 0:
        return {"tp": 0.0, "fp": 0.0, "fn": float(n_g), "n_p": 0, "n_truth": n_g, "dti": 0.0, "coverage": 0.0}
    dp = distance_transform_edt(~p)
    dg = distance_transform_edt(~g)
    tp = float(kernel(dp[g]).sum())
    fn = float(n_g) - tp
    fp = float((1.0 - kernel(dg[p])).sum())
    dti_val = float(tp / (tp + alpha * fp + beta * fn + EPS_METRIC))
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "n_p": n_p,
        "n_truth": n_g,
        "dti": dti_val,
        "coverage": float(tp / n_g),
        "mean_credit_per_dot": float(tp / n_p),
    }


def dti_bruteforce(
    pred: np.ndarray,
    truth: np.ndarray,
    alpha: float = ALPHA,
    beta: float = BETA,
    radius: float = RADIUS_PX,
) -> dict:
    """Literal O(|G|*|P|) brute-force implementation of the published equations for unit tests."""
    pred = np.asarray(pred, float)
    truth = np.asarray(truth, bool)
    gs = np.argwhere(truth)
    xs = np.argwhere(pred > 0)
    tp = fn = 0.0
    for g in gs:
        best = 0.0
        for x in xs:
            d = float(np.hypot(*(x - g)))
            if d <= radius:
                best = max(best, pred[tuple(x)] * max(1.0 - d / radius, 0.0))
        tp += best
        fn += 1.0 - best
    fp = 0.0
    for x in xs:
        kmax = 0.0
        for g in gs:
            kmax = max(kmax, max(1.0 - float(np.hypot(*(x - g))) / radius, 0.0))
        fp += pred[tuple(x)] * (1.0 - kmax)
    return {"tp": tp, "fp": fp, "fn": fn, "dti": float(tp / (tp + alpha * fp + beta * fn + EPS_METRIC))}


def official_symmetric_dti(P: np.ndarray, G: np.ndarray) -> dict:
    """Symmetric distance-weighted Tversky index used in the 4-quadrant Live Mirror (LM)."""
    P = np.asarray(P, bool)
    G = np.asarray(G, bool)
    n_p = int(P.sum())
    n_g = int(G.sum())
    if n_p == 0 or n_g == 0:
        return {"dti": 0.0, "tp_w": 0.0, "tp_p": 0.0, "tp_g": 0.0, "n_p": n_p, "n_g": n_g}
    dp = distance_transform_edt(~P)
    dg = distance_transform_edt(~G)
    tp_p = float(kernel(dp[G]).sum())
    tp_g = float(kernel(dg[P]).sum())
    tp_w = 0.5 * (tp_p + tp_g)
    denom = ALPHA * n_p + BETA * n_g + BETA * (tp_g - tp_p) + EPS_METRIC
    return {
        "dti": float(tp_w / denom),
        "tp_w": tp_w,
        "tp_p": tp_p,
        "tp_g": tp_g,
        "n_p": n_p,
        "n_g": n_g,
    }


@dataclass
class QuadrantFold:
    key: str
    fold_id: int
    bbox: tuple[slice, slice]
    domain: np.ndarray
    truth: np.ndarray
    n_truth: int


@dataclass
class SpatiallyBlockedInstrument:
    footprint: np.ndarray
    labels: np.ndarray
    d_cat: np.ndarray
    sgmc_off_d3: np.ndarray
    sgmc_off_d5: np.ndarray
    quadrant_ids: np.ndarray
    folds: list[QuadrantFold]


def build_quadrant_ids(footprint: np.ndarray) -> np.ndarray:
    """Partition the active footprint into 4 spatial quadrants: 0=NW, 1=NE, 2=SW, 3=SE."""
    footprint = np.asarray(footprint, bool)
    yy, xx = np.nonzero(footprint)
    ym, xm = int(np.median(yy)), int(np.median(xx))
    H, W = footprint.shape
    gy, gx = np.ogrid[:H, :W]
    q = np.full((H, W), -1, dtype=np.int8)
    q[(gy < ym) & (gx < xm) & footprint] = 0
    q[(gy < ym) & (gx >= xm) & footprint] = 1
    q[(gy >= ym) & (gx < xm) & footprint] = 2
    q[(gy >= ym) & (gx >= xm) & footprint] = 3
    return q


def build_spatially_blocked_instrument(
    footprint: np.ndarray,
    labels: np.ndarray,
    sgmc: np.ndarray,
    domain_erode_px: int = 12,
) -> SpatiallyBlockedInstrument:
    """Build the 4-quadrant Live Mirror (LM) and stratified d0=3, d0=5 off-catalogue instruments."""
    footprint = np.asarray(footprint, bool)
    labels = np.asarray(labels, bool)
    sgmc = np.asarray(sgmc, bool)
    d_cat = distance_transform_edt(~labels)

    # Off-catalogue SGMC truth strictly outside the 300 m (3 px) and 500 m (5 px) catalogue halos
    cat_dil3 = binary_dilation(labels, iterations=3)
    sgmc_off_lm = sgmc & footprint & ~labels & ~cat_dil3
    sgmc_off_d3 = sgmc & footprint & (d_cat > 3.0)
    sgmc_off_d5 = sgmc & footprint & (d_cat > 5.0)

    quad = build_quadrant_ids(footprint)
    fold_names = ("NW", "NE", "SW", "SE")
    folds: list[QuadrantFold] = []
    for fid in range(4):
        q = quad == fid
        rows = np.flatnonzero(q.any(axis=1))
        cols = np.flatnonzero(q.any(axis=0))
        r0 = max(0, int(rows[0]) - 6)
        r1 = min(footprint.shape[0], int(rows[-1]) + 7)
        c0 = max(0, int(cols[0]) - 6)
        c1 = min(footprint.shape[1], int(cols[-1]) + 7)
        sl = (slice(r0, r1), slice(c0, c1))
        dom = binary_erosion(q, iterations=domain_erode_px)
        truth_fold = (sgmc_off_lm & dom)[sl]
        folds.append(
            QuadrantFold(
                key=f"fold{fold_names[fid]}",
                fold_id=fid,
                bbox=sl,
                domain=dom[sl],
                truth=truth_fold,
                n_truth=int(truth_fold.sum()),
            )
        )
    return SpatiallyBlockedInstrument(
        footprint=footprint,
        labels=labels,
        d_cat=d_cat,
        sgmc_off_d3=sgmc_off_d3,
        sgmc_off_d5=sgmc_off_d5,
        quadrant_ids=quad,
        folds=folds,
    )


def evaluate_candidate(
    mask: np.ndarray,
    inst: SpatiallyBlockedInstrument,
    name: str,
    g_lb_total: float = 12691.0,
) -> dict:
    """Evaluate a binary candidate on:
    1) 4-quadrant spatially blocked Live Mirror (raw & prevalence-calibrated),
    2) Stratified SGMC off-catalogue d0=3 px instrument,
    3) Stratified SGMC off-catalogue d0=5 px instrument.
    """
    m = np.asarray(mask, bool) & inst.footprint
    n_emit = int(m.sum())
    n_on_cat = int((m & inst.labels).sum())
    n_flank2 = int((m & (inst.d_cat <= 2.0)).sum())
    n_flank3 = int((m & (inst.d_cat <= 3.0)).sum())

    foot_px = float(inst.footprint.sum())
    per_fold_lm: dict[str, float] = {}
    per_fold_cal: dict[str, float] = {}
    per_fold_asym: dict[str, float] = {}
    for f in inst.folds:
        p = m[f.bbox] & f.domain
        g = f.truth
        r_sym = official_symmetric_dti(p, g)
        r_asym = dti_binary(p, g)
        per_fold_lm[f.key] = r_sym["dti"]
        per_fold_asym[f.key] = r_asym["dti"]
        if r_sym["n_g"] > 0:
            g_cal = g_lb_total * (float(f.domain.sum()) / foot_px)
            denom_cal = ALPHA * r_sym["n_p"] + BETA * g_cal + BETA * (r_sym["tp_g"] - r_sym["tp_p"]) + EPS_METRIC
            per_fold_cal[f.key] = float(r_sym["tp_w"] / denom_cal)
        else:
            per_fold_cal[f.key] = 0.0

    lm_vals = np.array(list(per_fold_lm.values()), dtype=np.float64)
    cal_vals = np.array(list(per_fold_cal.values()), dtype=np.float64)
    asym_vals = np.array(list(per_fold_asym.values()), dtype=np.float64)

    # Stratified d0=3 and d0=5 across full off-catalogue domain
    dom_d3 = inst.footprint & ~inst.labels
    res_d3 = dti_binary(m, inst.sgmc_off_d3, valid=dom_d3)
    res_d5 = dti_binary(m, inst.sgmc_off_d5, valid=dom_d3)

    return {
        "candidate_id": name,
        "emitted_pixels": n_emit,
        "on_catalogue_pixels": n_on_cat,
        "flank_le_2px_pixels": n_flank2,
        "flank_le_3px_pixels": n_flank3,
        "lm_mean": float(lm_vals.mean()),
        "lm_std": float(lm_vals.std()),
        "lm_per_fold": per_fold_lm,
        "lm_calibrated_mean": float(cal_vals.mean()),
        "lm_calibrated_per_fold": per_fold_cal,
        "asym_quad_mean": float(asym_vals.mean()),
        "asym_quad_per_fold": per_fold_asym,
        "stratified_d0_3px": res_d3,
        "stratified_d0_5px": res_d5,
    }
