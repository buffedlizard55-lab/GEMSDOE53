#!/usr/bin/env python3
"""Chance baseline for the 3-px dot-overlap flag (diagnostic only; does NOT change any flag).

For each registry raster that the uniqueness check flagged, report:
  observed  = share of OUR dots within 3 px of that raster's dots (as in uniqueness_check.py)
  expected  = share of the official footprint within 3 px of that raster's dots, i.e. the overlap that
              randomly placed dots of ours would show at the same registry density.
  lift      = observed / expected. Lift near or below 1 means the flag is explained by density, not placement.
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", default=str(ROOT / "evidence/uniqueness_check.json"))
    ap.add_argument("--out", default=str(ROOT / "evidence/overlap_baseline.json"))
    ap.add_argument("--footprint", default="/tmp/gems53-data/sample_submission.tif")
    args = ap.parse_args()
    rec = json.loads(Path(args.receipt).read_text())
    ours_path = Path(rec["ours"])
    with rasterio.open(ours_path) as s:
        ours = np.nan_to_num(s.read(1).astype(np.float64)) > 0
    with rasterio.open(args.footprint) as s:
        fp = np.isfinite(s.read(1))
    rows = []
    for r in rec["results"]:
        if not (r.get("drift_flag") or r.get("exact_duplicate")):
            continue
        if r.get("exact_duplicate"):
            rows.append({"file": r["file"], "note": "exact duplicate"})
            continue
        with rasterio.open(r["file"]) as s:
            reg = np.nan_to_num(s.read(1).astype(np.float64)) > 0
        d = ndimage.distance_transform_edt(~reg)
        cover = float((d[fp] <= 3).mean())
        obs = float((d[ours] <= 3).mean())
        rows.append({
            "file": Path(r["file"]).name,
            "registry_dots": int(reg.sum()),
            "observed_overlap_ours_within_3px": round(obs, 6),
            "expected_overlap_random_placement": round(cover, 6),
            "lift": round(obs / cover, 4) if cover > 0 else None,
            "spearman_rho_sample": r.get("spearman_rho_sample"),
        })
    out = {
        "purpose": "chance baseline for the 3-px overlap flag (diagnostic only; flags unchanged)",
        "ours": rec["ours"],
        "ours_dots": int(ours.sum()),
        "footprint_px": int(fp.sum()),
        "flagged_rows": rows,
        "max_lift": max([r["lift"] for r in rows if r.get("lift") is not None] or [None]),
    }
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
