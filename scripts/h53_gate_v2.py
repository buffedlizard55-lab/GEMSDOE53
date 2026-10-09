#!/usr/bin/env python3
"""Uniqueness gate v2 (pre-registered D-1, docs/research/preregistration-2026-10-09-hwvc.md) against EVERY registry raster.

For each on-grid registry raster (de-duplicated by pixel hash):
  raw     : registry dots = value > 0 in footprint;           overlap_raw = share of our dots within 3 px of them
  v2      : same, but if > 5 % of footprint is positive the raster is a dense surface -> dots = its top-K (K = our dots)
            chance = share of footprint within 3 px of the v2 dots; kappa = (overlap - chance)/(1 - chance)
            duplicate iff overlap > 0.70 and kappa > 0.40
  rho     : Spearman rho on a fixed seeded 500k-footprint-pixel sample (seed 53), (a) our continuous pre-placement
            surface vs registry raster, (b) our final dot raster vs registry raster; duplicate iff |rho| > 0.90
Writes evidence/h53_gate_v2_<name>.json. Rasters stay in /tmp (not committed).
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
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems53.hwvc import registry_dots  # noqa: E402

OVERLAP_MAX, KAPPA_MAX, RHO_MAX, R_PX = 0.70, 0.40, 0.90, 3.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dots", required=True, help=".npy (H,W) 0/1 final raster")
    ap.add_argument("--surface", required=True, help=".npy (H,W) continuous pre-placement surface")
    ap.add_argument("--registry", default="/tmp/gems53-registry")
    ap.add_argument("--labels", default="/tmp/gems53-data/labels.tif")
    ap.add_argument("--name", required=True)
    ap.add_argument("--extra", nargs="*", default=[], help="extra rasters to include (e.g. this repo's own files)")
    a = ap.parse_args()
    t0 = time.time()
    lab = rasterio.open(a.labels).read(1)
    fp = lab >= 0
    H, W = fp.shape
    ours = np.load(a.dots) > 0
    surf = np.load(a.surface).astype(np.float32)
    K = int(ours.sum())
    oy, ox = np.nonzero(ours)
    rng = np.random.default_rng(53)
    fpi = np.flatnonzero(fp.ravel())
    samp = np.sort(rng.choice(fpi, 500_000, replace=False))
    s_surf = surf.ravel()[samp]
    s_ours = ours.ravel()[samp].astype(np.float32)
    files = sorted(p for p in Path(a.registry).iterdir() if p.suffix.lower() in (".tif", ".tiff")) + [Path(x) for x in a.extra]
    seen, rows, skipped = {}, [], []
    for f in files:
        try:
            with rasterio.open(f) as s:
                if (s.height, s.width) != (H, W) or s.count < 1:
                    skipped.append(dict(file=f.name, reason=f"grid {s.height}x{s.width}x{s.count}"))
                    continue
                arr = s.read(1).astype(np.float32)
        except Exception as e:  # noqa: BLE001
            skipped.append(dict(file=f.name, reason=f"unreadable: {type(e).__name__}"))
            continue
        h = hashlib.sha256(np.ascontiguousarray(np.nan_to_num(arr, nan=-9.0), dtype="<f4").tobytes()).hexdigest()
        if h in seen:
            seen[h]["aliases"].append(f.name)
            continue
        a0 = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
        raw = (a0 > 0) & fp
        nraw = int(raw.sum())
        row = dict(file=f.name, pixel_hash=h[:16], aliases=[], positive_px=nraw)
        if nraw == 0:
            row.update(mode="empty", overlap_raw=0.0, overlap=0.0, chance=0.0, kappa=0.0, rho_surface=None, rho_final=None)
        else:
            draw = ndimage.distance_transform_edt(~raw)
            row["overlap_raw"] = float((draw[oy, ox] <= R_PX).mean())
            row["chance_raw"] = float((draw[fp] <= R_PX).mean())
            dots, mode, _ = registry_dots(arr, fp, K)
            d2 = draw if mode == "positive" else ndimage.distance_transform_edt(~dots)
            ov = float((d2[oy, ox] <= R_PX).mean())
            ch = float((d2[fp] <= R_PX).mean())
            kap = (ov - ch) / (1 - ch) if ch < 1 else 0.0
            sv = a0.ravel()[samp]
            rs = rf = None
            if np.unique(sv).size > 1:
                rs = float(spearmanr(s_surf, sv).statistic)
                rf = float(spearmanr(s_ours, sv).statistic)
            row.update(mode=mode, dots_v2=int(dots.sum()), overlap=ov, chance=ch, kappa=kap, rho_surface=rs, rho_final=rf)
        row["raw_rule_flag"] = bool(row["overlap_raw"] > OVERLAP_MAX)
        row["v2_dot_flag"] = bool(row["overlap"] > OVERLAP_MAX and row["kappa"] > KAPPA_MAX)
        row["v2_rho_flag"] = bool(any(r is not None and abs(r) > RHO_MAX for r in (row["rho_surface"], row["rho_final"])))
        row["duplicate_v2"] = bool(row["v2_dot_flag"] or row["v2_rho_flag"])
        seen[h] = row
        rows.append(row)
    def top(key, n=10):
        out = []
        for r in sorted(rows, key=lambda r: -(abs(r[key]) if r[key] is not None else -1))[:n]:
            out.append(dict(file=r["file"], value=None if r[key] is None else round(r[key], 6),
                            overlap=round(r["overlap"], 4), chance=round(r.get("chance", 0.0), 4),
                            kappa=round(r["kappa"], 4), mode=r["mode"]))
        return out
    dup = [r["file"] for r in rows if r["duplicate_v2"]]
    rep = dict(gate="uniqueness v2 (pre-registered D-1, 2026-10-09)", candidate=a.name, our_dots=K,
               registry_dir=a.registry, files_seen=len(files), unique_on_grid=len(rows), skipped=len(skipped),
               thresholds=dict(overlap=OVERLAP_MAX, kappa=KAPPA_MAX, rho=RHO_MAX, radius_px=R_PX, dense_frac=0.05),
               verdict="UNIQUE (passes v2)" if not dup else "DUPLICATE under v2", duplicates_v2=dup,
               raw_rule_flag_count=int(sum(r["raw_rule_flag"] for r in rows)),
               max_overlap_v2=top("overlap"), max_kappa=top("kappa"), max_rho_surface=top("rho_surface"),
               max_rho_final=top("rho_final"), rows=rows, skipped_files=skipped, runtime_s=round(time.time() - t0, 1),
               finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    out = ROOT / "evidence" / f"h53_gate_v2_{a.name}.json"
    out.write_text(json.dumps(rep, indent=2))
    print(json.dumps({k: rep[k] for k in ("verdict", "unique_on_grid", "skipped", "raw_rule_flag_count", "duplicates_v2",
                                          "max_overlap_v2", "max_kappa", "max_rho_surface", "max_rho_final")}, indent=1))


if __name__ == "__main__":
    main()
