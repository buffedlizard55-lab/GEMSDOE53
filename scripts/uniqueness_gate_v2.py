#!/usr/bin/env python3
"""Uniqueness gate v2 (session 2, governance decision GD-1).

Pre-registration: docs/research/preregistration-2026-10-09-session2.md section 1.

Two readings are computed for EVERY unique-by-sha256 registry raster on the official grid,
on the surface BEFORE placement AND on the final dots:

  RAW (literal protocol values, reported unchanged):
    rho_surface_whole_grid : Spearman over all grid pixels (NaN -> 0), thresholds 0.90 / 0.70 as in session 1
    overlap_pre / overlap_final : share of our candidate/final dots within 3 px of the registry dots

  CORRECTED (GD-1, intent-faithful):
    rho_footprint : Spearman on footprint pixels where both rasters make predictions (seeded subsample)
    lift          : overlap_final / chance_coverage, chance_coverage = share of footprint within 3 px
    corrected flag: rho_footprint > 0.90  OR  (overlap > 0.70 AND lift > 1.5)

Verdict: corrected_pass = no corrected flag anywhere. Raw flags are counted and listed for
transparency; a corrected pass with raw flags is labelled CLEARED-UNDER-CORRECTED-GATE and carries IR-53-50.

Usage:
  python scripts/uniqueness_gate_v2.py --surface /tmp/surface.npz --surface-q 0.05 \\
      --final docs/submissions/X.tif --registry /tmp/gems53-registry --out evidence/gate.json
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
LIFT_FLAG = 1.5
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


def spearman_sampled(a: np.ndarray, b: np.ndarray, rng, n=N_SAMPLE):
    m = np.isfinite(a) & np.isfinite(b)
    n = int(m.sum())
    if n < 100:
        return None, n
    if n > N_SAMPLE:
        idx = rng.choice(n, N_SAMPLE, replace=False)
        av, bv = a[m][idx], b[m][idx]
    else:
        av, bv = a[m], b[m]
    if np.unique(av).size < 2 or np.unique(bv).size < 2:
        return None, n
    rho, _ = stats.spearmanr(av, bv)
    return float(rho), n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surface", required=True, help="npz with keys: surface (H,W float32), footprint (H,W bool)")
    ap.add_argument("--surface-q", type=float, required=True, help="candidate quantile used pre-placement")
    ap.add_argument("--final", required=True, help="the written submission GeoTIFF")
    ap.add_argument("--registry", required=True, nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=53)
    args = ap.parse_args()
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    sf = np.load(args.surface)
    surface, fp = sf["surface"].astype(np.float64), sf["footprint"].astype(bool)
    H, W = surface.shape
    with rasterio.open(args.final) as s:
        final = s.read(1).astype(np.float64)
        assert (s.height, s.width) == (H, W), "final raster grid mismatch"
    final_dots = np.isfinite(final) & (final > 0)
    # pre-placement candidates: top-q of surface over the footprint (as used by the builder)
    vals = surface[fp]
    n_keep = int(round(args.surface_q * int(fp.sum())))
    thr = np.partition(vals, -n_keep)[-n_keep] if n_keep > 0 else np.inf
    pre_mask = fp & (surface >= thr) & np.isfinite(surface)
    rng = np.random.default_rng(args.seed)

    rows, seen, skipped = [], {}, []
    for d in args.registry:
        for p in sorted(Path(d).glob("*.tif")):
            sha = sha256(p)
            if sha in seen:
                skipped.append({"file": p.name, "reason": f"duplicate of {seen[sha]}"})
                continue
            seen[sha] = p.name
            with rasterio.open(p) as s:
                if (s.height, s.width) != (H, W):
                    skipped.append({"file": p.name, "reason": f"grid {s.height}x{s.width} != {H}x{W}"})
                    continue
                reg = s.read(1).astype(np.float64)
            reg_dots = np.isfinite(reg) & (reg > 0)
            if not reg_dots.any():
                skipped.append({"file": p.name, "reason": "no positive pixels"})
                continue
            # chance coverage: share of footprint within R of any registry dot
            dmap = ndimage.distance_transform_edt(~reg_dots)
            chance = float((fp & (dmap <= R_PX)).sum() / max(int(fp.sum()), 1))
            overlap_pre = share_within_r(pre_mask, reg_dots)
            overlap_final = share_within_r(final_dots, reg_dots)
            lift = overlap_final / chance if chance > 0 else float("inf")
            # rank correlations
            rho_fp_surface, n1 = spearman_sampled(np.where(fp, surface, np.nan),
                                                  np.where(fp, reg, np.nan), rng)
            a_wg = np.nan_to_num(surface, nan=0.0)
            b_wg = np.nan_to_num(reg, nan=0.0)
            rho_wg_surface, n2 = spearman_sampled(a_wg.ravel(), b_wg.ravel(), rng)
            fin_masked = np.where(np.isfinite(final), final, np.nan)
            rho_fp_final, n3 = spearman_sampled(np.where(fp, fin_masked, np.nan),
                                                np.where(fp, reg, np.nan), rng)
            row = {
                "file": p.name, "sha256": sha, "reg_dots": int(reg_dots.sum()),
                "rho_surface_whole_grid": None if rho_wg_surface is None else round(rho_wg_surface, 6),
                "rho_surface_footprint": None if rho_fp_surface is None else round(rho_fp_surface, 6),
                "rho_final_footprint": None if rho_fp_final is None else round(rho_fp_final, 6),
                "overlap_pre": round(overlap_pre, 6), "overlap_final": round(overlap_final, 6),
                "chance_coverage": round(chance, 6), "lift_over_chance": round(lift, 4),
                "flag_raw": bool((rho_wg_surface is not None and rho_wg_surface > RHO_FLAG)
                                 or overlap_final > OVERLAP_FLAG),
                "flag_corrected": bool((rho_fp_surface is not None and rho_fp_surface > RHO_FLAG)
                                       or (overlap_final > OVERLAP_FLAG and lift > LIFT_FLAG)),
            }
            rows.append(row)
            if len(rows) % 100 == 0:
                print(f"[gate] {len(rows)} rasters compared ({round(time.time() - t0)}s)", flush=True)
            del reg, reg_dots, dmap

    flagged_raw = [r for r in rows if r["flag_raw"]]
    flagged_corr = [r for r in rows if r["flag_corrected"]]
    out = {
        "schema": "gems53.uniqueness_gate.v2",
        "started_utc": started,
        "gate_rule": {
            "raw": "rho_surface_whole_grid > 0.90 OR overlap_final > 0.70 (literal protocol, reported only)",
            "corrected_GD_1": "rho_surface_footprint > 0.90 OR (overlap_final > 0.70 AND lift > 1.5)",
            "preregistration": "docs/research/preregistration-2026-10-09-session2.md section 1",
        },
        "surface": args.surface, "surface_q": args.surface_q,
        "final": args.final, "final_sha256": sha256(Path(args.final)),
        "final_dots": int(final_dots.sum()), "pre_candidates": int(pre_mask.sum()),
        "registry_unique_on_grid": len(rows), "registry_skipped": len(skipped),
        "n_flagged_raw": len(flagged_raw), "n_flagged_corrected": len(flagged_corr),
        "max": {
            "rho_surface_footprint": max((r["rho_surface_footprint"] for r in rows
                                          if r["rho_surface_footprint"] is not None), default=None),
            "rho_surface_whole_grid": max((r["rho_surface_whole_grid"] for r in rows
                                           if r["rho_surface_whole_grid"] is not None), default=None),
            "overlap_final": max((r["overlap_final"] for r in rows), default=None),
            "lift_over_chance": max((r["lift_over_chance"] for r in rows
                                     if np.isfinite(r["lift_over_chance"])), default=None),
        },
        "top_by_rho_footprint": sorted(rows, key=lambda r: -(r["rho_surface_footprint"] or -2))[:10],
        "top_by_lift": sorted([r for r in rows if np.isfinite(r["lift_over_chance"])],
                              key=lambda r: -r["lift_over_chance"])[:10],
        "corrected_flagged": flagged_corr,
        "corrected_pass": len(flagged_corr) == 0,
        "verdict": ("CLEARED-UNDER-CORRECTED-GATE" if len(flagged_corr) == 0
                    else "PROTOCOL DUPLICATE / STOP"),
        "raw_flags_listed_for_transparency": flagged_raw[:50],
        "runtime_s": round(time.time() - t0, 1),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({"verdict": out["verdict"], "n_flagged_raw": len(flagged_raw),
                      "n_flagged_corrected": len(flagged_corr), "max": out["max"]}, indent=2))
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
