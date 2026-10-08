#!/usr/bin/env python3
"""Experiment 1 - leakage canary (single-feature separability on whole-segment holdouts).

Protocol (hide-and-recover): the 3,199 8-connected known-fault segments are split into 5 folds.
For fold k the withheld positives are the segments of fold k; everything else is visible.
Positives for the canary = withheld known-fault pixels of fold k. Negatives = non-fault footprint pixels
outside a 1 km buffer of withheld faults. Separability = max(AUC, 1 - AUC) so the sign of a feature does not
hide a perfect separator (a feature that is 0 on faults and >0 elsewhere has AUC 0.0 and separability 1.0).

Gate (protocol item 4): separability above 0.90 means leakage until proven otherwise.

Tests:
  A. the 19 label-free feature bands, one at a time;
  B. distance to VISIBLE known faults, cross-fitted (learn-predict separation);
  C. the GEMSDOE29 defect reproduced: distance to the FULL catalogue (withheld labels included):
     C1 in-sample on the training labels, C2 on the withheld positives of each fold.

Writes evidence/exp1_leakage_canary.json. Usage:
    python scripts/exp1_leakage_canary.py --data-dir /tmp/gems53-data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import (  # noqa: E402
    buffer_zone,
    crossfit_distance_grid,
    fine_and_quad_blocks,
    leaky_distance_grid,
    load_inputs,
    segment_exact_distance_grid,
    segment_folds,
)

GATE = 0.90
K_FOLDS = 5
N_NEG = 200_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def separability(pos: np.ndarray, neg: np.ndarray, rng) -> dict:
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if len(neg) > N_NEG:
        neg = neg[rng.choice(len(neg), N_NEG, replace=False)]
    if len(pos) == 0 or len(neg) == 0:
        return {"AUC": None, "separability": None, "n_pos": int(len(pos)), "n_neg": int(len(neg))}
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    s = np.r_[pos, neg]
    if np.unique(s).size < 2:
        return {"AUC": 0.5, "separability": 0.5, "n_pos": int(len(pos)), "n_neg": int(len(neg))}
    auc = float(roc_auc_score(y, s))
    return {"AUC": round(auc, 6), "separability": round(max(auc, 1 - auc), 6),
            "n_pos": int(len(pos)), "n_neg": int(len(neg))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "exp1_leakage_canary.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fine, _quad = fine_and_quad_blocks(inp.H, inp.W)
    fold_grid, n_seg, _L = segment_folds(inp.cat, K=K_FOLDS, seed=53)
    rng = np.random.default_rng(53)

    with rasterio.open(dd / "labels.tif") as src:
        lab_raw = src.read(1)
    report = {
        "experiment": "E1 leakage canary (whole-segment holdout)",
        "inputs": {
            "training_features.tif": {"sha256": sha256(dd / "training_features.tif")},
            "labels.tif": {"sha256": sha256(dd / "labels.tif")},
        },
        "grid": {"H": inp.H, "W": inp.W, "res_m": 100, "crs": "EPSG:32611"},
        "footprint_px": int(inp.fp.sum()),
        "known_fault_px_in_footprint": int(inp.cat.sum()),
        "known_fault_px_outside_footprint": int(((lab_raw == 1) & ~inp.fp).sum()),
        "label_values": sorted(int(v) for v in np.unique(lab_raw)),
        "fault_segments_8conn": int(n_seg),
        "folds": {"K": K_FOLDS, "seed": 53, "buffer_px": 10,
                  "withheld_segments_per_fold": [int(len(np.unique(_L[fold_grid == k]))) for k in range(K_FOLDS)],
                  "withheld_px_per_fold": [int((fold_grid == k).sum()) for k in range(K_FOLDS)]},
        "gate": {"separability_flag_above": GATE},
    }

    # ---- C1. the GEMSDOE29 defect, in-sample -------------------------------------------------
    leaky = leaky_distance_grid(inp.cat)
    pos = leaky[inp.cat & inp.fp]
    neg = leaky[inp.fp & ~inp.cat]
    report["C1_leaky_distance_in_sample"] = {
        "description": "log1p(min(dist_to_full_catalogue,60)) on the training labels it was built from",
        "value_on_known_fault_px": {"min": float(pos.min()), "max": float(pos.max()),
                                    "fraction_exactly_zero": float((pos == 0).mean()), "n": int(pos.size)},
        "value_on_background_px": {"min": float(neg.min()), "max": float(neg.max())},
        **separability(pos, neg, rng),
        "verdict": "LEAK: separable by construction (the feature is a deterministic function of the label)",
    }

    # ---- A. label-free bands, withheld positives per fold -----------------------------------
    band_rows = []
    per_fold_pos = {}
    for k in range(K_FOLDS):
        hid = inp.fp & (fold_grid == k)
        bg = inp.fp & ~inp.cat & ~buffer_zone(fold_grid == k, 10)
        per_fold_pos[k] = (hid, bg)
    for j, name in enumerate(inp.band_names):
        rows = []
        for k in range(K_FOLDS):
            hid, bg = per_fold_pos[k]
            x_hid = inp.feats[inp.fp_idx[hid], j]
            x_bg = inp.feats[inp.fp_idx[bg], j]
            rows.append(separability(x_hid, x_bg, rng))
        seps = [r["separability"] for r in rows if r["separability"] is not None]
        band_rows.append({
            "band": j + 1,
            "name": name,
            "separability_per_fold": [r["separability"] for r in rows],
            "separability_mean": round(float(np.mean(seps)), 6),
            "separability_max": round(float(np.max(seps)), 6),
            "flag": "LEAK_SUSPECT" if max(seps) > GATE else "pass",
        })
    report["A_label_free_bands"] = band_rows

    # ---- B. leak-free distance feature (learn-predict separation), per fold -------------------
    b_rows, b2_rows, c2_rows = [], [], []
    for k in range(K_FOLDS):
        visible = inp.cat & (fold_grid != k)
        hid, bg = per_fold_pos[k]
        d_free = crossfit_distance_grid(visible, fine)
        _d_train_seg, d_pred_seg = segment_exact_distance_grid(visible)
        b_rows.append(separability(d_free[hid], d_free[bg], rng))
        b2_rows.append(separability(d_pred_seg[hid], d_pred_seg[bg], rng))
        c2_rows.append(separability(leaky[hid], leaky[bg], rng))
    report["B_distance_leak_free"] = {
        "description": "distance to VISIBLE known faults (withheld segments removed), cross-fitted by 4x4 block",
        "separability_per_fold": [r["separability"] for r in b_rows],
        "AUC_per_fold": [r["AUC"] for r in b_rows],
        "separability_mean": round(float(np.mean([r["separability"] for r in b_rows])), 6),
        "flag": "LEAK_SUSPECT" if max(r["separability"] for r in b_rows) > GATE else "pass",
        "note": ("Expected to be informative (new faults often lie near known ones). That is legitimate "
                 "information available at prediction time, not a label leak."),
    }
    report["B2_distance_segment_exact"] = {
        "description": "distance to VISIBLE known faults, segment-exact learn-predict separation (H1)",
        "separability_per_fold": [r["separability"] for r in b2_rows],
        "AUC_per_fold": [r["AUC"] for r in b2_rows],
        "separability_mean": round(float(np.mean([r["separability"] for r in b2_rows])), 6),
        "separability_max": round(float(np.max([r["separability"] for r in b2_rows])), 6),
        "flag": "LEAK_SUSPECT" if max(r["separability"] for r in b2_rows) > GATE else "pass",
        "note": "Preserves proximity to fault clusters without self-leakage.",
    }
    report["C2_leaky_distance_on_withheld"] = {
        "description": "distance to the FULL catalogue (withheld labels included), evaluated on withheld positives",
        "separability_per_fold": [r["separability"] for r in c2_rows],
        "separability_mean": round(float(np.mean([r["separability"] for r in c2_rows])), 6),
        "verdict": "LEAK: a holdout scored with a feature built from its own labels is inflated",
    }

    flagged = [r["band"] for r in band_rows if r["flag"] != "pass"]
    report["summary"] = {
        "label_free_bands_flagged": flagged,
        "max_label_free_band_separability": max(r["separability_max"] for r in band_rows),
        "leak_free_distance_separability_mean": report["B_distance_leak_free"]["separability_mean"],
        "leaky_distance_in_sample_separability": report["C1_leaky_distance_in_sample"]["separability"],
        "leaky_distance_on_withheld_separability_mean": report["C2_leaky_distance_on_withheld"]["separability_mean"],
        "verdict": (
            ("label-free bands: no band above the 0.90 gate" if not flagged else f"label-free bands FLAGGED {flagged}")
            + "; leak-free distance: " + report["B_distance_leak_free"]["flag"]
            + "; leaky distance: confirmed leak (separability 1.0 in-sample; inflated on withheld folds)."
        ),
    }
    report["runtime_s"] = round(time.time() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps(report["summary"], indent=2))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
