#!/usr/bin/env python3
"""Experiment 2 - hide-and-recover holdout of three model arms, scored with the official distance-weighted Tversky.

Design (per fold k of 5 whole-segment folds, 1 km buffer):
  visible  = known faults outside fold k      (the only catalogue information the fold may use)
  withheld = known faults inside fold k       (the ground truth scored for fold k; HOLDOUT-DTI proxy)
  training = visible positives + 300k random non-fault footprint pixels, buffer excluded
  emission = model probability over the whole footprint, visible faults masked pixel-exactly to 0,
             top-q fraction of footprint pixels kept (others 0)
  score    = DTI(alpha=0.2, beta=0.8, 300 m triangular kernel) of emission vs withheld pixels;
             pooled = sums of TP_w/FP_w/FN_w over folds, then one DTI.

Arms:
  bands        : 19 label-free feature bands only                      (no catalogue input)
  leakfree     : bands + distance to visible faults, learn-predict separated (4x4-block cross-fit)
  leaky_ablate : bands + distance to the FULL catalogue                 (GEMSDOE29 defect; demonstrates
                 that a holdout built this way is inflated; NOT a candidate)
  bands_ridge  : bands + label-free magnetic ridge on RTP (H2; no catalogue input)

Writes evidence/exp2_holdout_arms.json. Usage: python scripts/exp2_holdout_arms.py --data-dir /tmp/gems53-data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import (  # noqa: E402
    buffer_zone,
    crossfit_distance_grid,
    dti,
    fine_and_quad_blocks,
    leaky_distance_grid,
    load_inputs,
    rtp_ridge_grid,
    segment_folds,
)

K_FOLDS = 5
T_CRIT_DF4 = 2.776  # two-sided 95% t critical value, df = K-1 = 4
Q_GRID = [0.005, 0.0073, 0.01, 0.02]  # fraction of footprint pixels emitted (0.0073 ~ the 37,654-dot files)
N_NEG = 300_000
ARMS = ["bands", "leakfree", "leaky_ablate", "bands_ridge"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def predict_chunked(model, X, chunk=1_000_000):
    out = np.empty(X.shape[0], dtype=np.float32)
    for s in range(0, X.shape[0], chunk):
        out[s:s + chunk] = model.predict_proba(X[s:s + chunk])[:, 1].astype(np.float32)
    return out


def top_q_emission(p_full: np.ndarray, candidates: np.ndarray, q: float, footprint_px: int) -> np.ndarray:
    """Keep the top-q*footprint_px candidate pixels by probability; everything else 0. Values stay in [0,1]."""
    vals = p_full[candidates]
    n_keep = int(round(q * footprint_px))
    if n_keep <= 0 or vals.size == 0:
        return np.zeros_like(p_full)
    n_keep = min(n_keep, vals.size)
    thr = np.partition(vals, -n_keep)[-n_keep]
    keep = candidates & (p_full >= thr)
    # ties at the threshold can exceed n_keep; that is harmless (still in [0,1]) and is reported
    out = np.where(keep, p_full, 0.0).astype(np.float32)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "exp2_holdout_arms.json"))
    ap.add_argument("--arms", default=",".join(ARMS))
    args = ap.parse_args()
    arms = [a for a in args.arms.split(",") if a]
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fine, _q = fine_and_quad_blocks(inp.H, inp.W)
    fold_grid, n_seg, _L = segment_folds(inp.cat, K=K_FOLDS, seed=53)
    rng = np.random.default_rng(53)
    footprint_px = int(inp.fp.sum())

    report = {
        "experiment": "E2 hide-and-recover holdout, three arms",
        "evaluator": {"name": "gems53.core.dti", "version": "1.0.0",
                      "formula": "TI = TPw/(TPw + 0.2 FPw + 0.8 FNw + eps); triangular kernel R=3 px (300 m)",
                      "unit_test": "tests/test_metric.py (matches literal brute force; rules worked example)"},
        "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments; NOT organizer-scored)",
        "inputs": {"training_features.tif": sha256(dd / "training_features.tif"),
                   "labels.tif": sha256(dd / "labels.tif")},
        "footprint_px": footprint_px,
        "known_fault_px": int(inp.cat.sum()),
        "folds": {"K": K_FOLDS, "seed": 53, "buffer_px": 10, "segments": int(n_seg),
                  "withheld_fault_px": [int((fold_grid == k).sum()) for k in range(K_FOLDS)],
                  "withheld_segments": [int(len(np.unique(_L[fold_grid == k]))) for k in range(K_FOLDS)]},
        "Q_grid_fraction_of_footprint": Q_GRID,
        "model": "HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, "
                 "l2_regularization=1.0, random_state=0); negatives 300k sampled per fold",
        "arms": {},
    }

    for arm in arms:
        arm_rows = []
        pooled = {q: {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0} for q in Q_GRID}
        pooled_excl = {q: {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0} for q in Q_GRID}
        for k in range(K_FOLDS):
            t1 = time.time()
            hidden = inp.cat & (fold_grid == k)
            visible = inp.cat & (fold_grid != k)
            buf = buffer_zone(hidden, 10)
            if arm == "bands":
                F_all = inp.feats
                dist = None
            elif arm == "bands_ridge":
                if k == 0:
                    ridge_grid = rtp_ridge_grid(str(dd / "training_features.tif"), inp.fp)
                F_all = np.column_stack([inp.feats, ridge_grid[inp.fp]]).astype(np.float32)
                dist = None
            else:
                if arm == "leakfree":
                    dist = crossfit_distance_grid(visible, fine)
                else:  # leaky_ablate
                    dist = leaky_distance_grid(inp.cat)
                F_all = np.column_stack([inp.feats, dist[inp.fp]]).astype(np.float32)

            pos_mask = visible & ~buf & inp.fp
            neg_mask = inp.fp & ~inp.cat & ~buf
            pos_rows = inp.fp_idx[pos_mask]
            neg_pool = inp.fp_idx[neg_mask]
            neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
            rows = np.r_[pos_rows, neg_rows]
            y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
            model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                                   l2_regularization=1.0, random_state=0)
            model.fit(F_all[rows], y)

            p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
            p_full[inp.fp] = predict_chunked(model, F_all)
            p_full[visible] = 0.0  # pixel-exact mask of visible faults: the emission may not reuse them

            row = {"fold": k, "withheld_fault_px": int(hidden.sum()),
                   "withheld_segments": int(len(np.unique(_L[hidden]))),
                   "train_pos": int(pos_rows.size), "train_neg": int(neg_rows.size),
                   "per_q": {}}
            for q in Q_GRID:
                emis = top_q_emission(p_full, inp.fp & ~visible, q, footprint_px)
                r = dti(emis, hidden)
                row["per_q"][str(q)] = {"DTI": round(r["DTI"], 6), "TP_w": round(r["TP_w"], 4),
                                        "FP_w": round(r["FP_w"], 4), "FN_w": round(r["FN_w"], 4),
                                        "emitted_px": int(np.count_nonzero(emis))}
                for key in ("TP_w", "FP_w", "FN_w"):
                    pooled[q][key] += r[key]
            row["seconds"] = round(time.time() - t1, 1)
            arm_rows.append(row)
            print(f"[{arm}] fold {k}: " + ", ".join(f"q={q}: {row['per_q'][str(q)]['DTI']:.4f}" for q in Q_GRID),
                  flush=True)

        pooled_out = {}
        for q in Q_GRID:
            P = pooled[q]
            pooled_dti = P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9)
            per_fold = [r["per_q"][str(q)]["DTI"] for r in arm_rows]
            m = float(np.mean(per_fold))
            half = float(T_CRIT_DF4 * np.std(per_fold, ddof=1) / np.sqrt(len(per_fold)))
            pooled_out[str(q)] = {
                "pooled_DTI": round(float(pooled_dti), 6),
                "per_fold_DTI": per_fold,
                "per_fold_mean": round(m, 6),
                "CI95_t_df4_on_fold_mean": [round(m - half, 6), round(m + half, 6)],
                "withheld_fault_px_total": int(sum(r["withheld_fault_px"] for r in arm_rows)),
                "n_withheld_segments_total": int(sum(r["withheld_segments"] for r in arm_rows)),
            }
        report["arms"][arm] = {"folds": arm_rows, "pooled": pooled_out}

    report["runtime_s"] = round(time.time() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print("wrote", args.out)
    for arm in arms:
        print(arm, {q: report["arms"][arm]["pooled"][str(q)]["pooled_DTI"] for q in Q_GRID})
    return 0


if __name__ == "__main__":
    sys.exit(main())
