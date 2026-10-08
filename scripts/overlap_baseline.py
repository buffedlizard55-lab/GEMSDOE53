#!/usr/bin/env python3
"""Chance baseline for the 3-px dot-overlap flag (diagnostic only; does NOT change any flag). Version 2.

For each registry row whose overlap flag fired in evidence/uniqueness_v2.json:
  observed  = share of OUR dots within 3 px of that raster's dots (the value the flag uses)
  expected  = share of the official footprint within 3 px of that raster's dots (cover of the registry pattern)
  random    = share of RANDOM footprint pixels (same count as our dots) within 3 px of that raster's dots (seeded)
  lift      = observed / expected. Near 1 means the flag is explained by the registry's density or geometry,
              not by where our dots were placed.

Writes evidence/overlap_baseline_v2.json. The v1 file (evidence/overlap_baseline.json) is kept for the record.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import uniqueness_check as uq  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", default=str(ROOT / "evidence" / "uniqueness_v2.json"))
    ap.add_argument("--registry", default="/tmp/gems53-registry")
    ap.add_argument("--sample", default="/tmp/gems53-data/sample_submission.tif")
    ap.add_argument("--surface", default="/tmp/gems53-build/surface_L.npy")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "overlap_baseline_v2.json"))
    args = ap.parse_args()
    rec = json.loads(Path(args.receipt).read_text())
    with rasterio.open(args.sample) as s:
        fp = np.isfinite(s.read(1))
    ours_path = Path(rec["ours"])
    ours = uq.load_plain(ours_path) > 0
    ours_rc = np.stack(np.nonzero(ours), axis=1)
    n_ours = ours_rc.shape[0]
    idx = np.flatnonzero(fp.ravel())
    rng = np.random.default_rng(53)
    pick = rng.choice(idx, n_ours, replace=False)
    rand_rc = np.stack(np.unravel_index(pick, fp.shape), axis=1)

    flagged = [r for r in rec["results"] if "overlap" in (r.get("drift_flags") or [])]
    surface_flagged = [r for r in rec["results"] if "surface_overlap" in (r.get("drift_flags") or [])]
    surface_npy = Path(args.surface) if args.surface else None
    surf_rc = None
    if surface_flagged and surface_npy is not None and surface_npy.exists():
        surf = np.load(surface_npy)
        surf_rc = uq.top_n_rc(surf, fp, n_ours)
    rows = []
    for r in flagged:
        reg = uq.load_plain(Path(args.registry) / r["file"])
        if r.get("registry_dense"):
            reg_rc = uq.top_n_rc(reg, fp, n_ours)
            mode = "dense_top_N"
        else:
            reg_rc = np.stack(np.nonzero(reg > 0), axis=1)
            mode = "nonzero_dots"
        tree = cKDTree(reg_rc)
        obs = float((tree.query(ours_rc, k=1)[0] <= uq.WITHIN_PX).mean())
        rnd = float((tree.query(rand_rc, k=1)[0] <= uq.WITHIN_PX).mean())
        dist = ndimage.distance_transform_edt(~_mask(reg_rc, fp.shape))
        exp_cover = float(((dist <= uq.WITHIN_PX) & fp).sum() / fp.sum())
        rows.append({"check": "dots", "file": r["file"], "mode": mode, "registry_points": int(reg_rc.shape[0]),
                     "observed": round(obs, 6), "random_dots_share": round(rnd, 6),
                     "expected_footprint_cover": round(exp_cover, 6),
                     "lift_vs_cover": round(obs / exp_cover, 4) if exp_cover > 0 else None,
                     "lift_vs_random": round(obs / rnd, 4) if rnd > 0 else None})
    # surface check: observed = our pre-placement top-N surface pixels within 3 px of the registry's top-N;
    # chance = random footprint pixels (same count) within 3 px of the same registry top-N
    for r in surface_flagged:
        if surf_rc is None:
            break
        reg = uq.load_plain(Path(args.registry) / r["file"])
        reg_rc = uq.top_n_rc(reg, fp, n_ours)
        tree = cKDTree(reg_rc)
        obs = float((tree.query(surf_rc, k=1)[0] <= uq.WITHIN_PX).mean())
        rnd = float((tree.query(rand_rc, k=1)[0] <= uq.WITHIN_PX).mean())
        dist = ndimage.distance_transform_edt(~_mask(reg_rc, fp.shape))
        exp_cover = float(((dist <= uq.WITHIN_PX) & fp).sum() / fp.sum())
        rows.append({"check": "surface_top_N", "file": r["file"], "mode": "dense_top_N" if r.get("registry_dense") else "nonzero_dots",
                     "registry_points": int(reg_rc.shape[0]),
                     "observed": round(obs, 6), "random_dots_share": round(rnd, 6),
                     "expected_footprint_cover": round(exp_cover, 6),
                     "lift_vs_cover": round(obs / exp_cover, 4) if exp_cover > 0 else None,
                     "lift_vs_random": round(obs / rnd, 4) if rnd > 0 else None})
    out = {
        "purpose": "chance baseline for the 3-px overlap flag (diagnostic only; flags unchanged)",
        "receipt": str(Path(args.receipt).relative_to(ROOT)) if Path(args.receipt).is_relative_to(ROOT) else args.receipt,
        "ours": rec["ours"], "ours_dots": n_ours, "footprint_px": int(fp.sum()),
        "flagged_rows": len(rows), "flagged_dot_rows": sum(1 for r in rows if r["check"] == "dots"),
        "flagged_surface_rows": sum(1 for r in rows if r["check"] == "surface_top_N"), "rows": rows,
        "max_lift_vs_cover": max([r["lift_vs_cover"] for r in rows if r["lift_vs_cover"] is not None] or [None]),
        "min_lift_vs_cover": min([r["lift_vs_cover"] for r in rows if r["lift_vs_cover"] is not None] or [None]),
    }
    Path(args.out).write_text(json.dumps(out, indent=2, allow_nan=False))
    print(json.dumps({k: out[k] for k in ("flagged_rows", "max_lift_vs_cover", "min_lift_vs_cover")}, indent=2))
    return 0


def _mask(points_rc: np.ndarray, shape) -> np.ndarray:
    m = np.zeros(shape, dtype=bool)
    if points_rc.shape[0]:
        m[points_rc[:, 0], points_rc[:, 1]] = True
    return m


if __name__ == "__main__":
    sys.exit(main())
