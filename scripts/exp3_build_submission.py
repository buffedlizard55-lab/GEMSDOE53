#!/usr/bin/env python3
"""Experiment 3 - build the submission raster with the holdout-selected recipe, then validate it.

Recipe (identical training code to scripts/exp2_holdout_arms.py, but trained on ALL known faults):
  features  = 19 label-free bands (+ leak-free distance to known faults if the arm is 'leakfree')
  positives = all known-fault footprint pixels; negatives = 300k random non-fault footprint pixels
  emission  = P(fault) over the footprint; known-fault pixels masked to 0 (new faults are, by the
              competition's construction, not in the public catalogue); top-q of footprint kept.

Outputs (--outdir, all float32, EPSG:32611, 100 m, template transform/shape):
  <name>-nan.tif    The ONLY file. Outside the footprint = NaN with nodata tag NaN, exactly like the organizer's
                    sample_submission.tif. (A zeros-outside variant was removed: the official rule says outside
                    the bounds must be null or NaN, so zeros would not comply.)
  <name>.receipt.json  sha256, format checks, counts, and the holdout numbers it was selected on.

Usage: python scripts/exp3_build_submission.py --data-dir /tmp/gems53-data --arm leakfree --q 0.0073
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
    crossfit_distance_grid,
    fine_and_quad_blocks,
    load_inputs,
    validate_submission,
    write_submission,
)

sys.path.insert(0, str(ROOT / "scripts"))
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402

N_NEG = 300_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--arm", default="leakfree", choices=["bands", "leakfree"])
    ap.add_argument("--q", type=float, required=True)
    ap.add_argument("--name", default="gems53-hgb-xfit-q0p73")
    ap.add_argument("--outdir", default="/tmp/gems53-held")  # NOT docs/: the candidate is not offered for download
    ap.add_argument("--holdout-evidence", default=str(ROOT / "evidence" / "exp2_holdout_arms.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fine, _q = fine_and_quad_blocks(inp.H, inp.W)
    rng = np.random.default_rng(53)
    footprint_px = int(inp.fp.sum())

    if args.arm == "leakfree":
        dist = crossfit_distance_grid(inp.cat, fine)  # all known faults visible; per-block cross-fit
        F_all = np.column_stack([inp.feats, dist[inp.fp]]).astype(np.float32)
        del dist
    else:
        F_all = inp.feats

    pos_rows = inp.fp_idx[inp.cat & inp.fp]
    neg_pool = inp.fp_idx[inp.fp & ~inp.cat]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=0)
    model.fit(F_all[rows], y)

    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, F_all)
    emis = top_q_emission(p_full, inp.fp & ~inp.cat, args.q, footprint_px)  # 0 outside, 0 on known faults
    emis = np.nan_to_num(emis, nan=0.0)
    assert float(emis.min()) >= 0.0 and float(emis.max()) <= 1.0

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    qtag = str(args.q).replace(".", "p")
    stem = f"{args.name}-q{qtag}"
    emis_nan = emis.copy()
    emis_nan[~inp.fp] = np.nan  # official convention: outside footprint = NaN
    primary = outdir / f"{stem}-nan.tif"
    write_submission(str(primary), emis_nan, inp.transform, inp.crs, outside_nan=True)

    checks = {}
    for path in (primary,):
        r = validate_submission(str(path), inp.fp, inp.transform, inp.crs, inp.H, inp.W)
        r["sha256"] = sha256(path)
        r["bytes"] = path.stat().st_size
        r["on_known_fault_px"] = int(np.count_nonzero(emis[inp.cat] > 0))
        r["emitted_px"] = int(np.count_nonzero(emis > 0))
        r["emitted_fraction_of_footprint"] = round(r["emitted_px"] / footprint_px, 6)
        checks[path.name] = r

    holdout = None
    try:
        ev = json.loads(Path(args.holdout_evidence).read_text())
        holdout = {"arm": args.arm, "q": args.q, "pooled_DTI_holdout": ev["arms"][args.arm]["pooled"][str(args.q)]["pooled_DTI"],
                   "CI95": ev["arms"][args.arm]["pooled"][str(args.q)]["CI95_t_df4_on_fold_mean"],
                   "label_type": "HOLDOUT-DTI (proxy, withheld known-fault segments, 5 folds)"}
    except (OSError, KeyError):
        holdout = {"arm": args.arm, "q": args.q, "note": "holdout evidence not found for this arm/q"}

    receipt = {
        "submission_name": stem,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "recipe": {
            "model": "HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, "
                     "l2_regularization=1.0, random_state=0)",
            "arm": args.arm,
            "positives": int(pos_rows.size), "negatives": int(neg_rows.size),
            "features": int(F_all.shape[1]),
            "known_fault_mask": "emission forced to 0 on known-fault pixels",
            "q_fraction_of_footprint": args.q,
        },
        "holdout_selection_evidence": holdout,
        "grid": {"H": inp.H, "W": inp.W, "crs": str(inp.crs), "transform": list(inp.transform)[:6],
                 "footprint_px": footprint_px},
        "files": checks,
        "runtime_s": round(time.time() - t0, 1),
    }
    (outdir / f"{stem}.receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: {"sha256": v["sha256"], "all_checks_passed": v["all_checks_passed"],
                          "counts": v["counts"]} for k, v in checks.items()}, indent=2))
    return 0 if all(v["all_checks_passed"] for v in checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
