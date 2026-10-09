#!/usr/bin/env python3
"""Experiment 7 - H5 (basement-depth and conductivity edges) canary + paired hide-and-recover holdout.

H5 (docs/research/hypotheses.md): multi-scale scale-normalised gradient magnitude (edge detector)
on two label-free bands that are NOT edge transforms themselves:
  f_basement     = edge(band 15, depth to basement / sedimentary cover thickness)
  f_conductivity = edge(band 17, surface conductivity)
Mechanism: basin-bounding and range-front faults juxtapose deep conductive cover against shallow
resistive basement, so the EDGES of those two layers mark faults that have no surface trace and are
therefore missing from the surface-based USGS/INGENIOUS catalogue. Non-fault mimic: depositional
onlap edges, caldera rims, landslide scarps, and inversion artefacts of the depth model itself.

Protocol item 4 first: each feature ALONE on the withheld folds (separability gate 0.90) and the
paired pixel-neighbour canary (leak check). Then the paired holdout: arm `bands` (19 bands) versus
arm `bands_h5` (19 bands + the two H5 edges), same folds, same seeds, same emission variant and q grid,
scored with the official distance-weighted Tversky. Acceptance (pre-registered): pooled DTI gain over
`bands` beyond the fold-level 95% t half-width of the paired difference at the selected q.

Writes evidence/exp7_h5_canary_holdout.json. Usage:
    python scripts/exp7_h5_canary_holdout.py --data-dir /tmp/gems53-data --variant bin
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
    edge_grid,
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
N_NEG = 300_000
N_NEG_CANARY = 200_000
H5_BANDS = {"f_basement": 15, "f_conductivity": 17}  # 1-based band indices in training_features.tif


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def separability(pos: np.ndarray, neg: np.ndarray, rng) -> dict:
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if len(neg) > N_NEG_CANARY:
        neg = neg[rng.choice(len(neg), N_NEG_CANARY, replace=False)]
    if len(pos) == 0 or len(neg) == 0:
        return {"AUC": None, "separability": None, "n_pos": int(len(pos)), "n_neg": int(len(neg))}
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    s = np.r_[pos, neg]
    if np.unique(s).size < 2:
        return {"AUC": 0.5, "separability": 0.5, "n_pos": int(len(pos)), "n_neg": int(len(neg))}
    auc = float(roc_auc_score(y, s))
    return {"AUC": round(auc, 6), "separability": round(max(auc, 1 - auc), 6),
            "n_pos": int(len(pos)), "n_neg": int(len(neg)),
            "flag_leak_if_above_0.90": bool(max(auc, 1 - auc) > 0.90)}


def local_pair_auc(feat: np.ndarray, cat: np.ndarray, fp: np.ndarray, rng, n_pairs=60_000) -> dict:
    """Paired canary: fault pixel vs an adjacent non-fault 4-neighbour. A label-free smooth feature
    cannot separate pixels one cell apart (AUC ~ 0.5); a label-encoding feature does (AUC -> 1)."""
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
    a = feat[ys, xs].astype(np.float64)
    b = feat[ny, nx].astype(np.float64)
    gt = float((a > b).mean())
    eq = float((a == b).mean())
    auc = gt + 0.5 * eq
    return {"pairs": int(ys.size), "AUC_fault_gt_neighbour": round(auc, 6),
            "separability": round(max(auc, 1 - auc), 6), "flag_leak_if_above_0.90": bool(max(auc, 1 - auc) > 0.90)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "exp7_h5_canary_holdout.json"))
    ap.add_argument("--variant", default="bin", choices=["raw", "bin", "rank", "sqrt"],
                    help="emission variant (the E6-selected rule; default bin)")
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fold_grid, n_seg, _L = segment_folds(inp.cat, K=K_FOLDS, seed=53)
    rng = np.random.default_rng(53)
    footprint_px = int(inp.fp.sum())

    report = {
        "experiment": "E7 H5 (basement/conductivity edges) canary + paired hide-and-recover holdout",
        "evaluator": {"name": "gems53.core.dti", "version": "1.1.0",
                      "formula": "TI = TPw/(TPw + 0.2 FPw + 0.8 FNw + eps); triangular kernel R=3 px (300 m)",
                      "unit_test": "tests/test_metric.py"},
        "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments; NOT organizer-scored)",
        "inputs": {"training_features.tif": sha256(dd / "training_features.tif"),
                   "labels.tif": sha256(dd / "labels.tif")},
        "hypothesis": {
            "id": "H5",
            "features": {k: f"edge(band {v})" for k, v in H5_BANDS.items()},
            "mechanism": "basin-bounding faults juxtapose deep conductive cover against shallow resistive basement; "
                         "the edges of depth-to-basement (15) and conductivity (17) mark faults with no surface trace",
            "named_non_fault_process_that_could_mimic_it": "depositional onlap edges, caldera rims, landslide scarps, "
                                                           "and artefacts of the depth-to-basement inversion itself",
            "differs_from_repo": "the stack carries the raw layers and gravity/magnetic gradients, but no edge "
                                 "(gradient-magnitude) transform of basement depth or conductivity",
        },
        "footprint_px": footprint_px,
        "known_fault_px": int(inp.cat.sum()),
        "folds": {"K": K_FOLDS, "seed": 53, "buffer_px": 10, "segments": int(n_seg),
                  "withheld_fault_px": [int((fold_grid == k).sum()) for k in range(K_FOLDS)],
                  "withheld_segments": [int(len(np.unique(_L[fold_grid == k]))) for k in range(K_FOLDS)]},
        "model": "HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, "
                 "l2_regularization=1.0, random_state=0); 300k sampled negatives per fold",
        "emission_variant": args.variant,
        "q_grid_fraction_of_footprint": Q_GRID,
        "canary": {},
        "arms": {},
        "paired": {},
    }

    # ---- H5 features on the full grid (label-free) ----
    h5_grids = {k: edge_grid(str(dd / "training_features.tif"), inp.fp, b) for k, b in H5_BANDS.items()}

    # ---- canary: each feature ALONE on the withheld folds ----
    for k in range(K_FOLDS):
        hid = inp.fp & (fold_grid == k)
        bg = inp.fp & ~inp.cat & ~buffer_zone(fold_grid == k, 10)
        for name, grid in h5_grids.items():
            rep = report["canary"].setdefault(name, {"description": f"edge of band {H5_BANDS[name]} (label-free)",
                                                     "separability_per_fold": [], "local_pair_canary": None})
            if k == 0:
                rep["local_pair_canary"] = local_pair_auc(grid, inp.cat, inp.fp, np.random.default_rng(53), 20_000)
            r = separability(grid[hid], grid[bg], rng)
            rep["separability_per_fold"].append(r["separability"])
    for name, rep in report["canary"].items():
        rep["separability_mean"] = round(float(np.mean(rep["separability_per_fold"])), 6)
        rep["separability_max"] = round(float(np.max(rep["separability_per_fold"])), 6)
        rep["verdict"] = ("LEAK_SUSPECT" if rep["separability_max"] > 0.90 or
                          rep["local_pair_canary"]["flag_leak_if_above_0.90"] else "pass")
        print(f"[canary] {name}: sep_max={rep['separability_max']:.3f} pair_AUC="
              f"{rep['local_pair_canary']['AUC_fault_gt_neighbour']:.3f} -> {rep['verdict']}", flush=True)

    # ---- paired holdout: bands vs bands_h5 ----
    h5_stack = np.column_stack([g[inp.fp] for g in h5_grids.values()]).astype(np.float32)
    arms = {"bands": inp.feats, "bands_h5": np.column_stack([inp.feats, h5_stack]).astype(np.float32)}
    pooled = {a: {q: {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0} for q in Q_GRID} for a in arms}
    for arm, F_all in arms.items():
        arm_rows = []
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
            model.fit(F_all[rows], y)
            p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
            p_full[inp.fp] = predict_chunked(model, F_all)
            p_full[visible] = 0.0
            K = kernel_to_gt(hidden)
            row = {"fold": k, "withheld_fault_px": int(hidden.sum()),
                   "withheld_segments": int(len(np.unique(_L[hidden]))),
                   "train_pos": int(pos_rows.size), "train_neg": int(neg_rows.size),
                   "features": int(F_all.shape[1]), "per_q": {}}
            for q in Q_GRID:
                keep = top_q_mask(p_full, inp.fp & ~visible, q, footprint_px)
                emis = emission_from_probability(p_full, keep, args.variant)
                r = dti_with_kernel(emis, hidden, K)
                row["per_q"][str(q)] = {"DTI": round(r["DTI"], 6), "TP_w": round(r["TP_w"], 4),
                                        "FP_w": round(r["FP_w"], 4), "FN_w": round(r["FN_w"], 4),
                                        "emitted_px": int(np.count_nonzero(emis))}
                for key in ("TP_w", "FP_w", "FN_w"):
                    pooled[arm][q][key] += r[key]
            row["seconds"] = round(time.time() - t1, 1)
            arm_rows.append(row)
            print(f"[{arm}] fold {k}: " + ", ".join(f"q={q}: {row['per_q'][str(q)]['DTI']:.4f}" for q in Q_GRID),
                  flush=True)
        pooled_out = {}
        for q in Q_GRID:
            P = pooled[arm][q]
            pooled_dti = P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9)
            per_fold = [r["per_q"][str(q)]["DTI"] for r in arm_rows]
            m = float(np.mean(per_fold))
            half = float(T_CRIT_DF4 * np.std(per_fold, ddof=1) / np.sqrt(len(per_fold)))
            pooled_out[str(q)] = {"pooled_DTI": round(float(pooled_dti), 6),
                                  "per_fold_DTI": per_fold, "per_fold_mean": round(m, 6),
                                  "CI95_t_df4_on_fold_mean": [round(m - half, 6), round(m + half, 6)],
                                  "withheld_fault_px_total": int(sum(r["withheld_fault_px"] for r in arm_rows)),
                                  "n_withheld_segments_total": int(sum(r["withheld_segments"] for r in arm_rows))}
        report["arms"][arm] = {"folds": arm_rows, "pooled": pooled_out}

    # ---- paired difference (bands_h5 - bands), t(df 4) 95% CI ----
    for q in Q_GRID:
        b = [f["per_q"][str(q)]["DTI"] for f in report["arms"]["bands"]["folds"]]
        h = [f["per_q"][str(q)]["DTI"] for f in report["arms"]["bands_h5"]["folds"]]
        d = [x - y for x, y in zip(h, b)]
        m = float(np.mean(d))
        half = float(T_CRIT_DF4 * np.std(d, ddof=1) / np.sqrt(len(d)))
        report["paired"][str(q)] = {"mean_diff_h5_minus_bands": round(m, 6),
                                    "CI95_t_df4": [round(m - half, 6), round(m + half, 6)],
                                    "per_fold_diff": [round(x, 6) for x in d]}
    best_q = max(Q_GRID, key=lambda q: report["arms"]["bands"]["pooled"][str(q)]["pooled_DTI"])
    d = report["paired"][str(best_q)]
    half = (d["CI95_t_df4"][1] - d["CI95_t_df4"][0]) / 2.0
    accept = bool(d["mean_diff_h5_minus_bands"] > half)  # gain beyond the fold-level 95% half-width
    report["selection"] = {
        "rule": "pre-stated: H5 is accepted only if its pooled DTI beats bands by more than the fold-level 95% "
                "t half-width of the paired difference at the bands-best q; otherwise the bands arm is kept",
        "bands_best_q": best_q,
        "bands_best_pooled_DTI": report["arms"]["bands"]["pooled"][str(best_q)]["pooled_DTI"],
        "h5_pooled_DTI_at_bands_best_q": report["arms"]["bands_h5"]["pooled"][str(best_q)]["pooled_DTI"],
        "paired_diff_at_bands_best_q": d,
        "fold_level_95pct_half_width": round(half, 6),
        "verdict": ("ACCEPTED" if accept else
                    "REJECTED (negative: the paired gain does not exceed the fold-level 95% half-width)"),
        "arm_for_submission": "bands_h5" if accept else "bands",
    }
    report["runtime_s"] = round(time.time() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print("wrote", args.out)
    print(json.dumps(report["selection"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
