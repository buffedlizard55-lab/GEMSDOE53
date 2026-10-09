#!/usr/bin/env python3
"""Experiment 6 - emission-rule sweep on the hide-and-recover holdout (HOLDOUT-DTI).

Question (pre-registered): the Exp 2 recipe kept the model's raw probabilities on the top-q pixels.
The metric is a budget: FN_w is penalised at beta=0.8 while FP_w is penalised at alpha=0.2, and the
registry's high-scoring files are binary value-1.0 dot rasters. Does rescaling the emission values
(bin / rank / sqrt) and/or widening the emitted volume q beat the raw recipe on the official
distance-weighted Tversky?

Design: identical to Exp 2 (5 whole-segment folds, seed 53, 1 km buffer, visible faults masked
pixel-exactly, HGB on the 19 label-free bands, 300k sampled negatives, same seeds), so the `raw`
variant at q in {0.005, 0.0073, 0.01, 0.02} must reproduce evidence/exp2_holdout_arms.json exactly
(cross-check asserted below). Emission variants are post-processing of the SAME model probabilities.

Diagnostics: per-fold AUC of the model on the withheld faults (placement quality) and the fraction of
withheld fault pixels with a kept dot within 3 px (coverage), plus the credit-per-dot and the
break-even bar 0.2*DTI (the same break-even the GEMSDOE32 analysis derives).

Writes evidence/exp6_emission_scaling.json. Usage:
    python scripts/exp6_emission_scaling.py --data-dir /tmp/gems53-data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import (  # noqa: E402
    buffer_zone,
    dti_with_kernel,
    emission_from_probability,
    kernel_to_gt,
    load_inputs,
    segment_folds,
    top_q_mask,
)

sys.path.insert(0, str(ROOT / "scripts"))
from exp2_holdout_arms import predict_chunked  # noqa: E402

K_FOLDS = 5
T_CRIT_DF4 = 2.776  # two-sided 95% t critical value, df = K-1 = 4
Q_GRID = [0.005, 0.0073, 0.01, 0.02, 0.05, 0.10, 0.20]
VARIANTS = ["raw", "bin", "rank", "sqrt"]
N_NEG = 300_000
N_NEG_AUC = 200_000
EXP2_Q = ["0.005", "0.0073", "0.01", "0.02"]  # q values where the raw variant must reproduce Exp 2


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "exp6_emission_scaling.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fold_grid, n_seg, _L = segment_folds(inp.cat, K=K_FOLDS, seed=53)
    rng = np.random.default_rng(53)
    auc_rng = np.random.default_rng(53)  # separate stream: the training-negative draws must stay identical to Exp 2
    footprint_px = int(inp.fp.sum())

    report = {
        "experiment": "E6 emission-rule sweep (value scaling x emitted volume) on the hide-and-recover holdout",
        "evaluator": {"name": "gems53.core.dti", "version": "1.1.0",
                      "formula": "TI = TPw/(TPw + 0.2 FPw + 0.8 FNw + eps); triangular kernel R=3 px (300 m); "
                                 "dti() refactored into kernel_to_gt + dti_with_kernel (shared-tool change, tests pass)",
                      "unit_test": "tests/test_metric.py (matches literal brute force; rules worked example)"},
        "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments; NOT organizer-scored)",
        "inputs": {"training_features.tif": sha256(dd / "training_features.tif"),
                   "labels.tif": sha256(dd / "labels.tif")},
        "footprint_px": footprint_px,
        "known_fault_px": int(inp.cat.sum()),
        "folds": {"K": K_FOLDS, "seed": 53, "buffer_px": 10, "segments": int(n_seg),
                  "withheld_fault_px": [int((fold_grid == k).sum()) for k in range(K_FOLDS)],
                  "withheld_segments": [int(len(np.unique(_L[fold_grid == k]))) for k in range(K_FOLDS)]},
        "model": "HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, "
                 "l2_regularization=1.0, random_state=0); 19 label-free bands; 300k sampled negatives per fold",
        "q_grid_fraction_of_footprint": Q_GRID,
        "variants": VARIANTS,
        "folds": [],
        "pooled": {},
        "reproduction_check": {},
    }

    pooled = {v: {q: {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0} for q in Q_GRID} for v in VARIANTS}
    for k in range(K_FOLDS):
        t1 = time.time()
        hidden = inp.cat & (fold_grid == k)
        visible = inp.cat & (fold_grid != k)
        buf = buffer_zone(hidden, 10)

        pos_mask = visible & ~buf & inp.fp
        neg_mask = inp.fp & ~inp.cat & ~buf
        pos_rows = inp.fp_idx[pos_mask]
        neg_pool = inp.fp_idx[neg_mask]
        neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
        rows = np.r_[pos_rows, neg_rows]
        y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
        model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                               l2_regularization=1.0, random_state=0)
        model.fit(inp.feats[rows], y)

        p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
        p_full[inp.fp] = predict_chunked(model, inp.feats)
        p_full[visible] = 0.0  # pixel-exact mask of visible faults

        # ---- diagnostics: placement quality of the model on the withheld faults ----
        bg_mask = inp.fp & ~inp.cat & ~buf
        bg_pick = auc_rng.choice(int(bg_mask.sum()), min(N_NEG_AUC, int(bg_mask.sum())), replace=False)
        auc = float(roc_auc_score(np.r_[np.ones(int(hidden.sum())), np.zeros(bg_pick.size)],
                                  np.r_[p_full[hidden], p_full[bg_mask][bg_pick]]))

        K = kernel_to_gt(hidden)
        row = {"fold": k, "withheld_fault_px": int(hidden.sum()),
               "withheld_segments": int(len(np.unique(_L[hidden]))),
               "train_pos": int(pos_rows.size), "train_neg": int(neg_rows.size),
               "model_AUC_on_withheld_faults": round(auc, 6),
               "per_variant_q": {}}
        for v in VARIANTS:
            for q in Q_GRID:
                keep = top_q_mask(p_full, inp.fp & ~visible, q, footprint_px)
                emis = emission_from_probability(p_full, keep, v)
                r = dti_with_kernel(emis, hidden, K)
                emitted = int(np.count_nonzero(emis))
                # coverage: withheld fault pixels with a kept dot within 3 px
                cov = float(K[keep & hidden].size and (K[keep] > 0).sum() and
                            float((K[hidden] > 0).mean()))  # placeholder replaced below
                d = np.abs(emis)  # recompute coverage properly: distance from hidden px to kept dots
                from scipy import ndimage
                dist_kept = ndimage.distance_transform_edt(~keep)
                coverage = float((dist_kept[hidden] <= 3).mean())
                entry = {"DTI": round(r["DTI"], 6), "TP_w": round(r["TP_w"], 4), "FP_w": round(r["FP_w"], 4),
                         "FN_w": round(r["FN_w"], 4), "emitted_px": emitted,
                         "coverage_withheld_within_3px": round(coverage, 6),
                         "credit_per_dot": round(r["TP_w"] / emitted, 6) if emitted else None,
                         "break_even_bar_0p2xDTI": round(0.2 * r["DTI"], 6)}
                row["per_variant_q"][f"{v}|{q}"] = entry
                for key in ("TP_w", "FP_w", "FN_w"):
                    pooled[v][q][key] += r[key]
        row["seconds"] = round(time.time() - t1, 1)
        report["folds"].append(row)
        print(f"[fold {k}] AUC={auc:.4f} " + ", ".join(
            f"{v}@{q}:{row['per_variant_q'][f'{v}|{q}']['DTI']:.4f}" for v in VARIANTS for q in Q_GRID[:4]),
            flush=True)

    for v in VARIANTS:
        pooled_out = {}
        for q in Q_GRID:
            P = pooled[v][q]
            pooled_dti = P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9)
            per_fold = [f["per_variant_q"][f"{v}|{q}"]["DTI"] for f in report["folds"]]
            m = float(np.mean(per_fold))
            half = float(T_CRIT_DF4 * np.std(per_fold, ddof=1) / np.sqrt(len(per_fold)))
            pooled_out[str(q)] = {
                "pooled_DTI": round(float(pooled_dti), 6),
                "per_fold_DTI": per_fold,
                "per_fold_mean": round(m, 6),
                "CI95_t_df4_on_fold_mean": [round(m - half, 6), round(m + half, 6)],
                "withheld_fault_px_total": int(sum(f["withheld_fault_px"] for f in report["folds"])),
                "n_withheld_segments_total": int(sum(f["withheld_segments"] for f in report["folds"])),
            }
        report["pooled"][v] = pooled_out

    # ---- reproduction check: raw variant must equal Exp 2 bands arm at the shared q values ----
    try:
        exp2 = json.loads((ROOT / "evidence" / "exp2_holdout_arms.json").read_text())
        checks = {}
        for q in EXP2_Q:
            e2 = exp2["arms"]["bands"]["pooled"][q]["pooled_DTI"]
            ours = report["pooled"]["raw"][q]["pooled_DTI"]
            checks[q] = {"exp2_bands_pooled_DTI": e2, "e6_raw_pooled_DTI": ours,
                         "identical": bool(abs(e2 - ours) < 5e-7)}
        report["reproduction_check"] = {
            "rule": "raw variant at q in {0.005, 0.0073, 0.01, 0.02} must reproduce the Exp 2 bands arm exactly",
            "checks": checks,
            "all_identical": all(c["identical"] for c in checks.values()),
        }
    except (OSError, KeyError) as e:
        report["reproduction_check"] = {"error": str(e)}

    report["runtime_s"] = round(time.time() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print("wrote", args.out)
    for v in VARIANTS:
        print(v, {q: report["pooled"][v][str(q)]["pooled_DTI"] for q in Q_GRID})
    print("reproduction:", report["reproduction_check"].get("all_identical"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
