#!/usr/bin/env python3
"""Inventory of public GEMSDOE* rasters mirrored from GitHub (input to scripts/uniqueness_check.py).

For every *.tif in the mirror directory: sha256, band count, dtype, shape, CRS, transform match with the
competition grid, and whether it is a candidate prediction raster (single band, competition grid).
Exact duplicates (same sha256) are collapsed to one representative. Writes JSON to --out and copies
nothing. Usage: python scripts/registry_inventory.py --mirror /tmp/g53/uniq --data-dir /tmp/gems53-data --out ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import rasterio


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mirror", default="/tmp/g53/uniq")
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with rasterio.open(Path(args.data_dir) / "sample_submission.tif") as s:
        ref = (s.height, s.width, tuple(s.transform)[:6], s.crs.to_epsg())
    rows = []
    seen = {}
    for p in sorted(Path(args.mirror).glob("*.tif")):
        row = {"file": p.name, "bytes": p.stat().st_size}
        try:
            with rasterio.open(p) as src:
                row.update({"count": src.count, "dtype": src.dtypes[0], "height": src.height, "width": src.width,
                            "epsg": src.crs.to_epsg() if src.crs else None})
                row["grid_match"] = (src.height, src.width, tuple(src.transform)[:6], row["epsg"]) == ref
        except Exception as e:  # unreadable file: record, do not guess
            row["error"] = str(e)[:200]
            rows.append(row)
            continue
        row["sha256"] = sha256(p)
        if row["sha256"] in seen:
            row["duplicate_of"] = seen[row["sha256"]]
        else:
            seen[row["sha256"]] = p.name
        row["prediction_candidate"] = bool(row["count"] == 1 and row["grid_match"] and "duplicate_of" not in row)
        if row["count"] != 1:
            row["excluded_reason"] = "multi-band (not a single-layer prediction)"
        elif not row["grid_match"]:
            row["excluded_reason"] = "grid differs from competition template"
        elif "duplicate_of" in row:
            row["excluded_reason"] = "exact duplicate of " + row["duplicate_of"]
        rows.append(row)
    summary = {
        "mirror": args.mirror,
        "files": len(rows),
        "unique_sha256": len(seen),
        "prediction_candidates": sum(r.get("prediction_candidate", False) for r in rows),
        "excluded_multiband": sum(1 for r in rows if r.get("count", 1) != 1),
        "excluded_grid": sum(1 for r in rows if r.get("count") == 1 and not r.get("grid_match", True)),
        "excluded_duplicate": sum(1 for r in rows if "duplicate_of" in r),
        "errors": sum(1 for r in rows if "error" in r),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
