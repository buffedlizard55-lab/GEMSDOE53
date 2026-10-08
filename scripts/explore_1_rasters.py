#!/usr/bin/env python3
"""Pass-1 recon: what exactly is in data/ (shapes, dtypes, value sets, footprints).

Read-only. Prints a compact report; no file is modified. Run with the venv python:

    .venv/bin/python scripts/explore_1_rasters.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]


def describe(path: Path, max_px: int = 0) -> dict:
    with rasterio.open(path) as ds:
        info = {
            "path": str(path.relative_to(ROOT)),
            "shape": [ds.height, ds.width],
            "count": ds.count,
            "dtype": ds.dtypes[0],
            "crs": str(ds.crs),
            "transform": [ds.transform.a, ds.transform.b, ds.transform.c, ds.transform.d,
                          ds.transform.e, ds.transform.f],
            "nodata": ds.nodata,
            "bounds": [round(v, 1) for v in ds.bounds],
        }
        if max_px:
            a = ds.read(1, window=rasterio.windows.Window(0, 0, ds.width, ds.height))
            a = a[:max_px, :max_px]
        else:
            a = ds.read(1)
        uniq = np.unique(a)
        info["n_unique"] = int(uniq.size)
        info["unique_sample"] = [float(v) for v in uniq[:12]]
        finite = np.isfinite(a)
        info["finite_frac"] = round(float(finite.mean()), 4)
        if finite.any():
            info["min"] = float(np.nanmin(a[finite]))
            info["max"] = float(np.nanmax(a[finite]))
        info["nonzero_px"] = int((a != 0).sum())
        return info


def main() -> None:
    out = {}
    targets = [
        ROOT / "data/sample_submission.tif",
        ROOT / "data/labels.tif",
        ROOT / "data/reference/h33-2-b2-zeros.tif",
        ROOT / "data/external/lidar_scarp_features_u8.tif",
        ROOT / "data/external/geodawn_rad_u8.tif",
        ROOT / "data/external/geodawn_extensions_u8.tif",
    ]
    for t in targets:
        if t.exists():
            out[t.name] = describe(t)
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        out["training_features"] = {
            "shape": [ds.height, ds.width], "count": ds.count, "dtype": ds.dtypes[0],
            "crs": str(ds.crs), "nodata": ds.nodata,
            "transform": [ds.transform.a, ds.transform.e, ds.transform.c, ds.transform.f],
            "band_descriptions": list(ds.descriptions),
            "band_tags": [ds.tags(i + 1) for i in range(ds.count)],
            "dataset_tags": ds.tags(),
        }
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
