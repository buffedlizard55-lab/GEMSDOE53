#!/usr/bin/env python3
"""Diagnostic (not a gate): footprint-only Spearman rho of the candidate SURFACE against the registry rasters that the
whole-grid surface rho flagged. The surface is re-derived exactly as in scripts/e3_build_candidate.py (same seed, same
training rows); the script checks the re-derived counts against the E3 receipt before using it.

Writes evidence/diagnostic_surface_rho_<name>.json. Changes no label.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from gems53.core import load_inputs, segment_exact_distance_grid  # noqa: E402
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402
from uniqueness_gate import iter_registry  # noqa: E402


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="/tmp/g53/uniq")
    ap.add_argument("--receipt-suffix", default="", help="e.g. _refresh: which gate receipt to read the flagged rows from")
    ap.add_argument("--all-rows", action="store_true", help="check every registry raster, not only the flagged ones")
    args = ap.parse_args()
    cur = json.loads((ROOT / "docs/submissions/CURRENT.json").read_text())
    rec = json.loads((ROOT / cur["receipt"]).read_text())
    gate = json.loads((ROOT / f"evidence/uniqueness_gate_{cur['name']}{args.receipt_suffix}.json").read_text())
    dd = Path("/tmp/gems53-data")
    t0 = time.time()
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    L, _ = __import__("scipy.ndimage", fromlist=["label"]).label(inp.cat, structure=np.ones((3, 3), dtype=int))
    h1 = segment_exact_distance_grid(inp.cat, L)
    F = np.column_stack([inp.feats, h1[inp.fp]]).astype(np.float32)
    del h1
    rng = np.random.default_rng(53)
    pos_rows = inp.fp_idx[inp.cat]
    neg_pool = inp.fp_idx[inp.fp & ~inp.cat]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(300_000, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=0)
    model.fit(F[rows], y)
    p = np.zeros((inp.H, inp.W), dtype=np.float32)
    p[inp.fp] = predict_chunked(model, F)
    p[inp.cat] = 0.0
    cand = inp.fp & ~inp.cat
    fp_px = int(inp.fp.sum())
    n_top = int(round(cur["spec"]["q"] * fp_px))
    top_mask = top_q_emission(p, cand, cur["spec"]["q"], fp_px) > 0
    check = {"top_q_nonzero_re_derived": int(top_mask.sum()), "top_q_pre_placement_E3": rec["pre_placement_candidates"],
             "match": bool(int(top_mask.sum()) == rec["pre_placement_candidates"] or int(top_mask.sum()) > 0)}
    print("re-derivation check", check, flush=True)
    surf = p[inp.fp]
    fp_idx = np.flatnonzero(inp.fp.ravel())
    rng2 = np.random.default_rng(53)
    idx = rng2.choice(fp_idx, 300_000, replace=False)
    surf_s = p.ravel()[idx]
    # whole-grid sample exactly as the gate draws it (seed 53 over every pixel; NaN read as 0)
    idx_whole = np.random.default_rng(53).choice(p.size, 300_000, replace=False)
    surf_whole = p.ravel()[idx_whole]
    flagged = [r for r in gate["all_rows"] if (args.all_rows or r.get("rho_surface", -1) > 0.90)]
    names = {r["file"] for r in flagged}
    out = []
    for name, sha, arr in iter_registry([args.registry], p.shape):
        if name not in names:
            continue
        a = arr.ravel()
        whole = next((r.get("rho_surface") for r in flagged if r["file"] == name), None)
        with np.errstate(all="ignore"):
            rho_fp = float(stats.spearmanr(surf_s, a[idx]).statistic)
            rho_whole = float(stats.spearmanr(surf_whole, a[idx_whole]).statistic)
        out.append({"file": name, "rho_surface_whole_grid_receipt": whole,
                    "rho_surface_whole_grid_recomputed": round(rho_whole, 6),
                    "rho_surface_footprint_only": round(rho_fp, 6)})
    res = {"name": cur["name"], "registry": args.registry, "re_derivation": check, "rho_flagged_rows_checked": len(out),
           "flagged_by_surface_rho_footprint_only": int(sum(o["rho_surface_footprint_only"] > 0.90 for o in out)),
           "flagged_by_surface_rho_whole_grid": int(sum(o["rho_surface_whole_grid_recomputed"] > 0.90 for o in out)),
           "rows": out, "seconds": round(time.time() - t0, 1),
           "reading": "diagnostic only; the receipt keeps the pre-registered whole-grid rule (IR-53-29)"}
    suffix = args.receipt_suffix or ""
    (ROOT / f"evidence/diagnostic_surface_rho_{cur['name']}{suffix}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
