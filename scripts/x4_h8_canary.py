#!/usr/bin/env python3
"""X4 - leakage canary for the H8 lane features (pre-registration-h8-2026-10-09.md, experiment X4).

Single-feature separability on whole-segment hide-and-recover folds (design B, seed 53, K=5):
  positives  = withheld catalogue segments (fold k)
  negatives  = footprint pixels that are never a catalogue pixel (design-B background, 300k sample)
  features   = computed from VISIBLE segments only (or label-free bands)

Controls: the deliberately leaky full-catalogue distance (GEMSDOE29 defect reproduction, expect ~1.0)
and the H1 segment-exact distance (expect ~0.77, matching evidence/e2_leakfree_holdouts.json).

Gate: separability (max(AUC, 1-AUC)) above 0.90 = leakage until proven otherwise.

Writes evidence/x4_h8_canary.json.
Usage: python scripts/x4_h8_canary.py --data-dir /tmp/gems53-data
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
from scipy import ndimage
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import (  # noqa: E402
    h1_segment_exact_distance,
    leaky_distance_grid,
    log_dist_feature,
    dist_to,
    segment_folds,
)
from gems53.corridors import corridor_surface, relay_surface, tip_continuation_surface  # noqa: E402
from gems53.ridge import nms_centrelines, ridge_fields  # noqa: E402

K_FOLDS = 5
SEED = 53
N_NEG = 300_000
GATE = 0.90
BAND_RTP = 2


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def separability(pos: np.ndarray, neg: np.ndarray, rng) -> dict:
    pos = np.asarray(pos, dtype=np.float64)
    neg = np.asarray(neg, dtype=np.float64)
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
    ap.add_argument("--out", default=str(ROOT / "evidence" / "x4_h8_canary.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)

    with rasterio.open(dd / "sample_submission.tif") as src:
        sample = src.read(1)
    fp = np.isfinite(sample)
    with rasterio.open(dd / "labels.tif") as src:
        lab = src.read(1)
    cat = (lab == 1) & fp
    with rasterio.open(dd / "training_features.tif") as src:
        band2 = src.read(BAND_RTP).astype(np.float64)
        nod = src.nodata
    if nod is not None and np.isfinite(nod):
        band2[band2 == nod] = np.nan
    band2[band2 < -1e30] = np.nan
    valid = fp & np.isfinite(band2)

    fold_grid, n_seg, seg_lab = segment_folds(cat, K=K_FOLDS, seed=SEED)
    ridge_L, _theta, _pol, _det = ridge_fields(band2, valid)
    rng = np.random.default_rng(SEED)
    neg_pool = fp & ~cat

    results = {}
    fold_rows = []
    leaky = leaky_distance_grid(cat)          # positive control; identical in every fold
    for k in range(K_FOLDS):
        visible = cat & (fold_grid != k)
        withheld = cat & (fold_grid == k)
        pos_idx = withheld
        tip = tip_continuation_surface(visible)
        rel = relay_surface(visible)
        comb = corridor_surface(visible, ridge_L, valid)
        h1 = h1_segment_exact_distance(visible, seg_lab, cap=60)
        feats = {
            "H8_tip_continuation": tip,
            "H8_relay": rel,
            "H8_combined": comb,
            "H1_segment_exact_distance": h1,
            "C_leaky_full_catalogue_distance": leaky,
            "R_band2_ridge_strength": ridge_L,
        }
        row = {"fold": k, "n_withheld_px": int(withheld.sum()),
               "n_withheld_segments": int(len(np.unique(fold_grid[withheld]))),
               "features": {}}
        for name, arr in feats.items():
            row["features"][name] = separability(arr[pos_idx], arr[neg_pool], rng)
        fold_rows.append(row)
        print(f"fold {k}: " + ", ".join(
            f"{n}={r['separability']}" for n, r in row["features"].items()), flush=True)

    for name in fold_rows[0]["features"]:
        vals = [r["features"][name]["separability"] for r in fold_rows
                if r["features"][name]["separability"] is not None]
        results[name] = {
            "separability_max_over_folds": max(vals) if vals else None,
            "separability_mean_over_folds": float(np.mean(vals)) if vals else None,
            "gate_flag_above_0p90": bool(vals and max(vals) > GATE),
        }

    out = {
        "experiment": "X4 leakage canary for the H8 lane (pre-registration-h8-2026-10-09.md)",
        "label_type": "single-feature separability on design-B hide-and-recover folds (not DTI)",
        "inputs": {
            "training_features.tif": sha256(dd / "training_features.tif"),
            "labels.tif": sha256(dd / "labels.tif"),
            "sample_submission.tif": sha256(dd / "sample_submission.tif"),
        },
        "folds": {"K": K_FOLDS, "seed": SEED, "segments": int(n_seg)},
        "negatives": "footprint pixels that are never a catalogue pixel (300k sample per fold)",
        "positives": "withheld catalogue segments (fold k)",
        "gate": {"separability_flag_above": GATE},
        "folds_detail": fold_rows,
        "summary": results,
        "controls_expected": {
            "C_leaky_full_catalogue_distance": "about 1.0 (the GEMSDOE29 defect)",
            "H1_segment_exact_distance": "about 0.77 (evidence/e2_leakfree_holdouts.json, design B)",
        },
        "runtime_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
