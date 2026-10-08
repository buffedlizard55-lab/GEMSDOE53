#!/usr/bin/env python3
"""Uniqueness gate for the parallel-run protocol (checked before placement AND on the final dots).

For every UNIQUE (by sha256) registry raster on the official grid:
  * rho_surface : Spearman rank correlation of our continuous surface with the registry raster (seeded sample);
  * overlap_pre : share of the pre-placement candidate pixels (top-q, before thinning) within 3 px of a registry dot;
  * rho_final   : Spearman rank correlation of the written raster with the registry raster;
  * overlap_final: share of our final dots within 3 px of a registry dot (exact Euclidean test, 29-offset lookup).
Flags (protocol): rho > 0.90 or overlap > 0.70 -> drift / duplicate. Thresholds are NOT changed here.
A chance-corrected diagnostic is reported for files flagged on overlap: lift = overlap / coverage, where coverage is
the share of footprint pixels within 3 px of that registry raster's dots (what random placement would give).

Usage (final file only):  python scripts/uniqueness_gate.py --final X.tif --registry /tmp/g53/uniq --out evidence/x.json
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
from scipy import ndimage, stats

RHO_FLAG = 0.90
OVERLAP_FLAG = 0.70
R_PX = 3
N_SAMPLE = 300_000
OFFS = [(dy, dx) for dy in range(-R_PX, R_PX + 1) for dx in range(-R_PX, R_PX + 1) if dy * dy + dx * dx <= R_PX * R_PX]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def share_within_r(ours_mask: np.ndarray, reg_dots: np.ndarray) -> float:
    ys, xs = np.nonzero(ours_mask)
    if ys.size == 0 or not reg_dots.any():
        return 0.0
    H, W = reg_dots.shape
    hit = np.zeros(ys.size, dtype=bool)
    for dy, dx in OFFS:
        yy, xx = ys + dy, xs + dx
        ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
        idx = np.nonzero(ok & ~hit)[0]
        if idx.size:
            hit[idx] |= reg_dots[yy[idx], xx[idx]]
    return float(hit.mean())


def iter_registry(registry_dirs, shape):
    """Yield (name, sha, array) for unique-by-sha256 rasters on the given grid, ONE AT A TIME (memory-safe).

    Skipped files (duplicates, other grids) are recorded in the `skipped` list passed by the caller via the
    generator's .skipped attribute.
    """
    seen = {}
    skipped = []
    for d in registry_dirs:
        for p in sorted(Path(d).glob("*.tif")):
            sha = sha256(p)
            if sha in seen:
                skipped.append({"file": p.name, "reason": f"duplicate of {seen[sha]}"})
                continue
            seen[sha] = p.name
            with rasterio.open(p) as s:
                if (s.height, s.width) != shape:
                    skipped.append({"file": p.name, "reason": f"grid {s.height}x{s.width} != {shape}"})
                    continue
                arr = np.nan_to_num(s.read(1).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
            yield p.name, sha, arr
    iter_registry.skipped = skipped


def run_gate(final_path, registry_dirs, out_json, surface=None, candidates=None, footprint=None, seed=53,
             final_array=None):
    """Gate on a file, or on an in-memory array (then final_path is only a label for the receipt)."""
    final_path = Path(final_path) if final_path is not None else None
    if final_array is not None:
        final = np.nan_to_num(np.asarray(final_array, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        final_sha = hashlib.sha256(np.ascontiguousarray(final, dtype="<f4").tobytes()).hexdigest()
        final_name = "in-memory array (pixel sha256 " + final_sha[:16] + ")"
    else:
        with rasterio.open(final_path) as s:
            final = np.nan_to_num(s.read(1).astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        final_sha = sha256(final_path)
        final_name = str(final_path)
    shape = final.shape
    fin_dots = final > 0
    if footprint is None:
        footprint = np.ones(shape, dtype=bool)
    rng = np.random.default_rng(seed)
    idx = rng.choice(final.size, N_SAMPLE, replace=False)
    surf = None if surface is None else np.nan_to_num(surface.astype(np.float32), nan=0.0).ravel()
    cand = None if candidates is None else candidates.astype(bool)
    t0 = time.time()
    rows = []
    for name, sha, arr in iter_registry(registry_dirs, shape):
        rho_f = float(stats.spearmanr(final.ravel()[idx], arr.ravel()[idx]).statistic)
        rd = arr > 0
        row = {"file": name, "sha256": sha, "reg_dots": int(rd.sum()),
               "rho_final": round(rho_f, 6),
               "overlap_final": round(share_within_r(fin_dots, rd), 6)}
        if surf is not None:
            row["rho_surface"] = round(float(stats.spearmanr(surf[idx], arr.ravel()[idx]).statistic), 6)
        if cand is not None:
            row["overlap_pre"] = round(share_within_r(cand, rd), 6)
        if row["overlap_final"] > 0.5 and rd.any():
            cov_edt = ndimage.distance_transform_edt(~rd)
            coverage = float((cov_edt[footprint] <= R_PX).mean())
            row["chance_coverage_footprint"] = round(coverage, 6)
            row["lift_over_chance"] = round(row["overlap_final"] / max(coverage, 1e-9), 4)
        worst = max(row.get("rho_final", -1), row.get("rho_surface", -1))
        row["drift_flag"] = bool(worst > RHO_FLAG or row["overlap_final"] > OVERLAP_FLAG
                                 or row.get("overlap_pre", 0.0) > OVERLAP_FLAG)
        rows.append(row)
        del arr
    skipped = iter_registry.skipped
    rows.sort(key=lambda r: -r["overlap_final"])
    maxes = {
        "max_rho_final": max(r["rho_final"] for r in rows),
        "max_overlap_final": max(r["overlap_final"] for r in rows),
    }
    if surface is not None:
        maxes["max_rho_surface"] = max(r["rho_surface"] for r in rows)
    if candidates is not None:
        maxes["max_overlap_pre"] = max(r["overlap_pre"] for r in rows)
    receipt = {
        "gate": "uniqueness (parallel-run protocol: rho > 0.90 or within-3px overlap > 0.70 = drift)",
        "thresholds": {"spearman_rho": RHO_FLAG, "dot_overlap_within_3px": OVERLAP_FLAG},
        "final_file": final_name, "final_sha256": final_sha,
        "final_dots": int(fin_dots.sum()), "footprint_px": int(footprint.sum()),
        "registry_dirs": [str(d) for d in registry_dirs],
        "registry_unique_on_grid": len(rows), "registry_skipped": len(skipped),
        "skipped_examples": skipped[:10],
        "any_drift_flag": any(r["drift_flag"] for r in rows),
        "n_flagged": int(sum(r["drift_flag"] for r in rows)),
        "max": maxes,
        "top_by_overlap_final": rows[:12],
        "all_rows_file": None,
        "seconds": round(time.time() - t0, 1),
    }
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(dict(receipt, all_rows=rows), indent=1))
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", required=True)
    ap.add_argument("--registry", action="append", required=True)
    ap.add_argument("--footprint-from", default=None, help="sample_submission.tif (finite mask = footprint)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    fp = None
    if args.footprint_from:
        with rasterio.open(args.footprint_from) as s:
            fp = np.isfinite(s.read(1))
    rec = run_gate(args.final, args.registry, args.out, footprint=fp)
    print(json.dumps({k: v for k, v in rec.items() if k not in ("top_by_overlap_final",)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
