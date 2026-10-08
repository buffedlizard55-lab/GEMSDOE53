#!/usr/bin/env python3
"""Experiment 4 - leakage canary for the two top untried hypotheses (feature ALONE, training labels).

H1  segment-exact distance: distance from each pixel to the visible faults EXCLUDING only the pixel's own
    8-connected segment, as pre-registered in docs/research/hypotheses.md.
    Design check (done before any holdout run): a positive pixel on segment s is measured with s removed,
    a negative pixel is measured with every fault present. The feature therefore depends on the label
    itself. This script measures how separable that makes the classes (canary: > 0.90 = leakage).

H2  label-free magnetic ridge (multi-scale Hessian) on reduced-to-pole magnetics (band 2).
    No catalogue input at all, so no label path exists. The canary still runs on it, to measure how
    much it separates the classes by itself (expected: modest, not leakage).

Writes evidence/exp4_hypothesis_canary.json. Usage:
    python scripts/exp4_hypothesis_canary.py --data-dir /tmp/gems53-data
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import (  # noqa: E402
    DIST_CAP_PX,
    crossfit_distance_grid,
    dist_to,
    fine_and_quad_blocks,
    load_inputs,
    log_dist_feature,
    ridge_feature,
)

N_NEG = 200_000
MARGIN = DIST_CAP_PX  # a fault farther than the cap from every core pixel cannot change the capped value
SEG_LABEL_STRUCT = np.ones((3, 3), dtype=int)


def sep(pos_vals: np.ndarray, neg_vals: np.ndarray) -> dict:
    y = np.r_[np.ones(pos_vals.size), np.zeros(neg_vals.size)]
    s = np.r_[pos_vals, neg_vals]
    auc = float(roc_auc_score(y, s))
    return {"AUC": round(auc, 6), "separability": round(max(auc, 1 - auc), 6),
            "n_pos": int(pos_vals.size), "n_neg": int(neg_vals.size),
            "flag_leak_if_above_0.90": bool(max(auc, 1 - auc) > 0.90)}


def h1_positive_values(cat: np.ndarray, pos_mask: np.ndarray, lab: np.ndarray) -> np.ndarray:
    """Capped distance (log1p) from each positive pixel to the catalogue EXCLUDING its own segment."""
    out = np.empty(int(pos_mask.sum()), dtype=np.float32)
    H, W = cat.shape
    order_index = np.full(cat.shape, -1, dtype=np.int64)
    ys, xs = np.nonzero(pos_mask)
    seg_of = lab[ys, xs]
    # process per segment window
    objs = ndimage.find_objects(lab)
    pos_index_by_seg = {}
    for i, s in enumerate(seg_of):
        pos_index_by_seg.setdefault(int(s), []).append(i)
    for seg_id, idxs in pos_index_by_seg.items():
        sl = objs[seg_id - 1]
        r0 = max(sl[0].start - MARGIN * 2, 0)
        r1 = min(sl[0].stop + MARGIN * 2, H)
        c0 = max(sl[1].start - MARGIN * 2, 0)
        c1 = min(sl[1].stop + MARGIN * 2, W)
        win_cat = cat[r0:r1, c0:c1] & (lab[r0:r1, c0:c1] != seg_id)
        d = ndimage.distance_transform_edt(~win_cat) if win_cat.any() else np.full(win_cat.shape, 1e6)
        for i in idxs:
            y, x = ys[i] - r0, xs[i] - c0
            out[i] = np.log1p(min(d[y, x], DIST_CAP_PX))
    return out


def local_pair_auc(feat_pos_val_fn, cat, fp, rng, n_pairs=60_000):
    """Paired canary: a fault pixel vs one of its 4-neighbours that is NOT a fault (same footprint).
    If a feature encodes the label pixel-exactly, it separates these neighbours; a smooth
    label-free feature cannot (the two pixels are one cell apart). Returns AUC of 'fault > neighbour'."""
    ys, xs = np.nonzero(cat & fp)
    pick = rng.choice(ys.size, min(n_pairs, ys.size), replace=False)
    ys, xs = ys[pick], xs[pick]
    d = rng.integers(0, 4, size=ys.size)
    dy = np.array([-1, 1, 0, 0])[d]
    dx = np.array([0, 0, -1, 1])[d]
    ny, nx = ys + dy, xs + dx
    ok = (ny >= 0) & (ny < cat.shape[0]) & (nx >= 0) & (nx < cat.shape[1])
    ok[ok] &= fp[ny[ok], nx[ok]] & ~cat[ny[ok], nx[ok]]
    ys, xs, ny, nx = ys[ok], xs[ok], ny[ok], nx[ok]
    a = feat_pos_val_fn(ys, xs)
    b = feat_pos_val_fn(ny, nx)
    # AUC of a > b (ties count half)
    gt = (a > b).mean()
    eq = (a == b).mean()
    auc = float(gt + 0.5 * eq)
    return {"pairs": int(ys.size), "AUC_fault_gt_neighbour": round(auc, 6),
            "separability": round(max(auc, 1 - auc), 6), "flag_leak_if_above_0.90": bool(max(auc, 1 - auc) > 0.90)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "exp4_hypothesis_canary.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    import rasterio
    # --- label-segment map (8-connected, same convention as segment_folds) ---
    lab, n_seg = ndimage.label(inp.cat, structure=SEG_LABEL_STRUCT)
    rng = np.random.default_rng(53)
    neg_pool = inp.fp & ~inp.cat
    neg_idx_flat = np.flatnonzero(neg_pool)
    neg_pick = rng.choice(neg_idx_flat, min(N_NEG, neg_idx_flat.size), replace=False)
    neg_ys, neg_xs = np.unravel_index(neg_pick, neg_pool.shape)

    report = {"experiment": "E4 hypothesis canary (feature alone, training labels)",
              "label_type": "MEASURED (training-label separability; not a holdout score)",
              "segments_8conn": int(n_seg), "known_fault_px": int(inp.cat.sum()),
              "neg_sample": N_NEG, "H1": {}, "H2": {}}

    # H1: as pre-registered
    pos_mask = inp.cat & inp.fp
    pos_ys, pos_xs = np.nonzero(pos_mask)
    pos_vals = h1_positive_values(inp.cat, pos_mask, lab)
    d_all = dist_to(inp.cat)
    neg_vals = log_dist_feature(d_all[neg_ys, neg_xs])
    report["H1"] = {
        "description": "segment-exact exclusion: positives measured without their own segment; negatives with all faults",
        **sep(pos_vals, neg_vals),
        "positive_value_quantiles_log1p": [round(float(q), 4) for q in np.quantile(pos_vals, [0.05, 0.5, 0.95])],
        "negative_value_quantiles_log1p": [round(float(q), 4) for q in np.quantile(neg_vals, [0.05, 0.5, 0.95])],
    }
    # H1 local pair canary: the H1 value at a fault pixel vs an adjacent off-fault pixel.
    # Their H1 values are computed on the same footprint; for the neighbour we use the H1 definition
    # with all faults present (it is not on a fault, so nothing of its own is excluded).
    def h1_at(ys_, xs_):
        out = np.empty(ys_.size, dtype=np.float32)
        is_f = inp.cat[ys_, xs_]
        if is_f.any():
            out[is_f] = h1_positive_values(inp.cat, np.isin(np.arange(inp.cat.size).reshape(inp.cat.shape),
                                                              np.ravel_multi_index((ys_[is_f], xs_[is_f]), inp.cat.shape)), lab)
        out[~is_f] = log_dist_feature(d_all[ys_[~is_f], xs_[~is_f]])
        return out
    report["H1"]["local_pair_canary"] = local_pair_auc(h1_at, inp.cat, inp.fp, np.random.default_rng(53), 20_000)
    print("H1", report["H1"]["separability"], report["H1"]["local_pair_canary"], flush=True)

    # H2: label-free ridge on RTP band (band 2 1-based)
    with rasterio.open(dd / "training_features.tif") as src:
        rtp = src.read(2).astype(np.float64)
        nod = src.nodata
    rtp[(rtp < -1e30) | (rtp == nod)] = np.nan
    fill = np.nanmean(rtp[inp.fp])
    rtp_f = np.where(np.isfinite(rtp), rtp, fill)
    rtp_f = (rtp_f - fill)
    ridge = ridge_feature(rtp_f)
    ridge_fp = ridge[inp.fp]
    pos_r = ridge[pos_mask]
    neg_r = ridge[neg_ys, neg_xs]
    report["H2"] = {"description": "max over sigma 1,2,3 px of sigma^2 * |major eig| * linearity on RTP band (label-free)",
                    **sep(pos_r, neg_r),
                    "fp_px": int(ridge_fp.size),
                    "nan_filled_px_in_footprint": int((~np.isfinite(rtp[inp.fp])).sum())}
    # Audit of the CURRENT leakfree arm (4x4-block cross-fit, exp2/exp3): same paired canary.
    fine, _q = fine_and_quad_blocks(inp.H, inp.W)
    cf = crossfit_distance_grid(inp.cat, fine)  # all known faults visible, per-block cross-fit
    report["A_leakfree_crossfit_local_pair"] = local_pair_auc(lambda y_, x_: cf[y_, x_], inp.cat, inp.fp,
                                                              np.random.default_rng(53), 20_000)
    report["A_leakfree_crossfit_training_sep"] = sep(cf[pos_mask], cf[neg_ys, neg_xs])
    print("A_leakfree", report["A_leakfree_crossfit_local_pair"], report["A_leakfree_crossfit_training_sep"]["separability"], flush=True)
    report["H2"]["local_pair_canary"] = local_pair_auc(lambda y_, x_: ridge[y_, x_], inp.cat, inp.fp,
                                                       np.random.default_rng(53), 20_000)
    print("H2", report["H2"]["separability"], report["H2"]["local_pair_canary"], flush=True)

    report["runtime_s"] = round(time.time() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v.get("separability") if isinstance(v, dict) else v for k, v in report.items()
                      if k in ("H1", "H2")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
