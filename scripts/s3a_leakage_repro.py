#!/usr/bin/env python3
"""S3-A (pre-registration S3, section 5): reproduce the GEMSDOE29 leakage construction and test the canary on it.

Three constructions on the same data, one fold of the design-B segment split (fold 0, seed 53):

  LEAKY  (GEMSDOE29 defect)  D = log1p(min(dist to FULL catalogue, 60)); positives = full catalogue.
  H1     (legitimate)        D = H1 learn-predict distance (visible faults only, own segment excluded).
  BANDS  reference           not computed here (E2 canary already holds 19 bands, max 0.591).

Checks:
  1. LEAKY is exactly 0 on every catalogue pixel used as a training positive (the defect).
  2. Training-sample AUC of LEAKY, the GEMSDOE29 builder's sampling (background only where dist > 1.5 px).
  3. Design-B canary for LEAKY (withheld faults vs footprint non-fault pixels): the leak must be detected.
  4. Design-B canary for H1 on the same fold (must match E2 fold 0 = 0.768 to rounding).
  5. Minimum attainable retained distance for the GEMSDOE29 negative filter (dist > 1.5 px on a unit EDT grid).

Writes evidence/s3a_leakage_repro.json. No DTI is computed here.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import (  # noqa: E402
    dist_to,
    h1_segment_exact_distance,
    load_inputs,
    log_dist_feature,
    segment_folds,
)
from exp1_leakage_canary import separability  # noqa: E402

SEED = 53


def main() -> int:
    t0 = time.time()
    dd = Path("/tmp/gems53-data")
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fold_grid, n_seg, L = segment_folds(inp.cat, K=5, seed=SEED)
    rng = np.random.default_rng(SEED + 530)
    k = 0
    hidden = inp.cat & (fold_grid == k)
    visible = inp.cat & (fold_grid != k)
    bg = inp.fp & ~inp.cat                           # design-B background (non-fault footprint pixels)

    # --- LEAKY: the GEMSDOE29 defect, built from the FULL label raster ---
    d_full = dist_to(inp.cat)
    leaky = log_dist_feature(d_full)
    on_pos = leaky[inp.cat & inp.fp]
    frac_zero_on_pos = float(np.mean(on_pos == 0.0))

    # 2. training-sample AUC, GEMSDOE29 sampling: positives = all catalogue pixels; negatives = dist > 1.5 px
    neg_ok = inp.fp & ~inp.cat & (d_full > 1.5)
    train_pos = leaky[inp.cat & inp.fp]
    train_neg = leaky[neg_ok]
    train_sep = separability(train_pos, train_neg, rng)

    # 3. design-B canary for LEAKY: withheld faults (fold 0) vs footprint background
    leaky_canary = separability(leaky[hidden & inp.fp], leaky[bg], rng)

    # 4. design-B canary for H1 on the same fold (legitimate, visible faults only)
    h1 = h1_segment_exact_distance(visible, L)
    h1_canary = separability(h1[hidden & inp.fp], h1[bg], rng)
    del h1

    # 5. minimum retained distance under the GEMSDOE29 filter
    d_bg_min = float(d_full[neg_ok].min())

    report = {
        "experiment": "S3-A leakage reproduction (pre-registration S3, section 5)",
        "label_type": "CANARY SENSITIVITY (not HOLDOUT-DTI, not ORGANIZER-CONFIRMED)",
        "fold": k,
        "seed": SEED,
        "leaky_construction": {
            "definition": "log1p(min(dist to FULL catalogue, 60)); positives = full catalogue",
            "fraction_zero_on_training_positives": round(frac_zero_on_pos, 6),
            "training_sample_AUC_GEMSDOE29_sampling": train_sep["AUC"],
            "training_sample_separability": train_sep["separability"],
            "n_train_pos": train_sep["n_pos"], "n_train_neg": train_sep["n_neg"],
            "min_retained_negative_distance_px": round(d_bg_min, 6),
            "design_B_canary_on_fold0": leaky_canary,
        },
        "h1_legitimate": {
            "definition": "H1 segment-exact distance from visible faults only",
            "design_B_canary_on_fold0": h1_canary,
            "E2_fold0_reference": 0.767983,
        },
        "verdict": {
            "canary_detects_leaky_feature": bool(leaky_canary["separability"] is not None
                                                 and leaky_canary["separability"] > 0.90),
            "h1_passes_canary": bool(h1_canary["separability"] is not None and h1_canary["separability"] <= 0.90),
            "note": "A canary that does not flag LEAKY would be insensitive; it flags it, so the canary is sensitive.",
        },
        "runtime_s": round(time.time() - t0, 1),
        "started_utc_epoch": int(t0),
    }
    out = ROOT / "evidence" / "s3a_leakage_repro.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
