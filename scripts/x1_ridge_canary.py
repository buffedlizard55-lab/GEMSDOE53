#!/usr/bin/env python3
"""X1 - leakage canary for the label-free ridge candidate (gate G3 in evidence/preregistration_x2.json).

Each ridge-derived feature is tested ALONE, per fold, against the same definition used by E1:
  positives = withheld known-fault pixels of fold k (the hidden segments)
  negatives = footprint pixels that are not known faults and lie outside the 1 km buffer of fold k
separability = max(AUC, 1 - AUC). Rule: > 0.90 means leakage until proven otherwise.

These features are computed from GeoDAWN band 2 (RTP) only and never read the labels, so the canary
should be well below 0.90. A value above 0.90 would show that the feature is leaking.
Also reports the raw RTP and the detrended RTP as references.

Writes evidence/x1_ridge_canary.json.
Usage: python scripts/x1_ridge_canary.py --data-dir /tmp/gems53-data
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import buffer_zone, load_inputs, segment_folds  # noqa: E402
from gems53.ridge import nms_centrelines, ridge_fields  # noqa: E402
from exp1_leakage_canary import separability  # noqa: E402  (same definition as E1; reused, not re-implemented)

GATE = 0.90
K_FOLDS = 5
BAND_RTP = 2  # GeoDAWN band 2: "Reduced to pole magnetic data"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "x1_ridge_canary.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fold_grid, n_seg, _L = segment_folds(inp.cat, K=K_FOLDS, seed=53)
    with rasterio.open(dd / "training_features.tif") as src:
        rtp = src.read(BAND_RTP).astype(np.float64)
        desc = src.tags(BAND_RTP).get("description", "")
        nod = src.nodata
    rtp[rtp < -1e30] = np.nan
    if nod is not None and np.isfinite(nod):
        rtp[rtp == nod] = np.nan

    L, th, pol, det = ridge_fields(rtp, inp.fp)
    centre = nms_centrelines(L, th)
    features = {
        "ridge_L_max_scale": np.where(inp.fp, L, np.nan),
        "ridge_centreline_indicator": np.where(inp.fp, centre.astype(np.float64), np.nan),
        "ridge_signed_L_(+bright,-dark)": np.where(inp.fp, np.where(pol > 0, L, -L), np.nan),
        "reference_detrended_RTP": np.where(inp.fp, det, np.nan),
        "reference_raw_RTP_band2": np.where(inp.fp, rtp, np.nan),
    }

    rng = np.random.default_rng(53)
    per_feature = {name: [] for name in features}
    for k in range(K_FOLDS):
        hidden = inp.cat & (fold_grid == k)
        buf = buffer_zone(hidden, 10)
        pos_mask = hidden & inp.fp
        neg_mask = inp.fp & ~inp.cat & ~buf
        for name, arr in features.items():
            res = separability(arr[pos_mask], arr[neg_mask], rng)
            res["fold"] = k
            per_feature[name].append(res)

    summary = {}
    for name, rows in per_feature.items():
        seps = [r["separability"] for r in rows if r["separability"] is not None]
        summary[name] = {"max_separability_over_folds": round(float(max(seps)), 6),
                         "mean_separability_over_folds": round(float(np.mean(seps)), 6),
                         "per_fold": rows}
    candidate_feats = [n for n in features if not n.startswith("reference_")]
    worst = max(summary[n]["max_separability_over_folds"] for n in candidate_feats)
    report = {
        "experiment": "X1 leakage canary for the label-free ridge candidate (protocol gate G3)",
        "label_type": "HOLDOUT-DTI-canary (feature alone vs withheld segments; no score is reported here)",
        "gate": GATE,
        "rule": "separability > 0.90 means leakage until proven otherwise",
        "inputs": {"training_features.tif": sha256(dd / "training_features.tif"),
                   "labels.tif": sha256(dd / "labels.tif"),
                   "ridge_module_sha256": sha256(ROOT / "src" / "gems53" / "ridge.py")},
        "band_used": {"index_1based": BAND_RTP, "description": desc},
        "label_access": "ridge features are computed from band 2 only; labels are used only for the separability test",
        "folds": {"K": K_FOLDS, "seed": 53, "buffer_px": 10, "segments": int(n_seg)},
        "features": summary,
        "worst_candidate_feature_separability": round(float(worst), 6),
        "G3_pass": bool(worst <= GATE),
        "runtime_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps({n: summary[n]["max_separability_over_folds"] for n in summary}, indent=2))
    print("worst candidate-feature separability:", report["worst_candidate_feature_separability"],
          "G3_pass:", report["G3_pass"])
    return 0 if report["G3_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
