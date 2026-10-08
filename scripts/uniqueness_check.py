#!/usr/bin/env python3
"""Lane / uniqueness check against registry rasters (parallel-run protocol items 1 and 2).

For our raster and each registry raster (public GEMS submissions found in the GEMSDOE* repos):
  * Spearman rank correlation of the two rasters over a seeded random sample of footprint pixels
    (NaN treated as 0). Drift flag if > 0.90.
  * Dot overlap: share of OUR dots (value > 0) lying within 3 px (300 m) of a registry dot. Drift flag if > 70%.
  * Exact duplicate check by sha256.

Writes a JSON receipt. Usage:
    python scripts/uniqueness_check.py --ours PATH --registry DIR [--registry DIR ...] --out evidence/x.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage, stats

RHO_FLAG = 0.90
OVERLAP_FLAG = 0.70
N_SAMPLE = 300_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load01(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float64)
    return np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--registry", action="append", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ours_path = Path(args.ours)
    ours = load01(ours_path)
    dots_ours = ours > 0
    rng = np.random.default_rng(53)
    flat = ours.ravel()
    idx = rng.choice(flat.size, N_SAMPLE, replace=False)
    results = []
    for reg_dir in args.registry:
        for reg_path in sorted(Path(reg_dir).glob("*.tif")):
            reg_sha = sha256(reg_path)
            if reg_sha == sha256(ours_path):
                results.append({"file": str(reg_path), "exact_duplicate": True})
                continue
            reg = load01(reg_path)
            if reg.shape != ours.shape:
                results.append({"file": str(reg_path), "shape_mismatch": list(reg.shape)})
                continue
            rho = float(stats.spearmanr(flat[idx], reg.ravel()[idx]).statistic)
            dots_reg = reg > 0
            if dots_reg.any() and dots_ours.any():
                d = ndimage.distance_transform_edt(~dots_reg)
                within3 = float((d[dots_ours] <= 3).mean())
            else:
                within3 = 0.0
            results.append({
                "file": str(reg_path),
                "sha256": reg_sha,
                "spearman_rho_sample": round(rho, 6),
                "our_dots_within_3px_of_registry_dots": round(within3, 6),
                "registry_dots": int(dots_reg.sum()),
                "exact_duplicate": False,
                "drift_flag": bool(rho > RHO_FLAG or within3 > OVERLAP_FLAG),
            })
    receipt = {
        "ours": str(ours_path),
        "ours_sha256": sha256(ours_path),
        "ours_dots": int(dots_ours.sum()),
        "thresholds": {"spearman_rho": RHO_FLAG, "dot_overlap_within_3px": OVERLAP_FLAG},
        "n_registry_files": len(results),
        "any_drift_flag": any(r.get("drift_flag", False) or r.get("exact_duplicate", False) for r in results),
        "max_spearman_rho": max([r.get("spearman_rho_sample", -1) for r in results] or [None]),
        "max_dot_overlap_within_3px": max([r.get("our_dots_within_3px_of_registry_dots", -1) for r in results] or [None]),
        "results": sorted(results, key=lambda r: -r.get("our_dots_within_3px_of_registry_dots", -1)),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: v for k, v in receipt.items() if k != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
