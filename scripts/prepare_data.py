#!/usr/bin/env python3
"""Audit the restored competition rasters and write receipts.  Exits non-zero on any mismatch.

Nothing downstream in this repository is allowed to cite a grid constant, a band name, a label
count or a footprint size that this script has not measured from the bytes on disk.  It is the
first pass of every run.

Measured quantities are written to ``evidence/grid.json`` and ``evidence/band_inventory.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems52 import grid as G  # noqa: E402

DATA = Path("data")
OUT = Path("evidence")


def audit(path: Path, expect_bytes: int | None = None, expect_sha: str | None = None) -> dict:
    d = dict(G.read_geotiff(path))
    if expect_bytes is not None and d["bytes"] != expect_bytes:
        raise SystemExit(f"{path}: {d['bytes']} bytes != pinned {expect_bytes}")
    if expect_sha is not None and d["sha256"] != expect_sha:
        raise SystemExit(f"{path}: sha256 {d['sha256']} != pinned {expect_sha}")
    if tuple(d["transform"]) != G.TRANSFORM:
        raise SystemExit(f"{path}: transform {d['transform']} != pinned {G.TRANSFORM}")
    if (d["height"], d["width"]) != G.SHAPE:
        raise SystemExit(f"{path}: shape {(d['height'], d['width'])} != pinned {G.SHAPE}")
    if d["crs"] != G.CRS_EPSG:
        raise SystemExit(f"{path}: crs {d['crs']} != {G.CRS_EPSG}")
    return d


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pins = json.loads(Path("registry/data_manifest.json").read_text())
    pin = {f["id"]: f for f in pins["files"]}

    feats = DATA / "training_features.tif"
    labels = DATA / "labels.tif"
    sample = DATA / "sample_submission.tif"
    for p in (feats, labels, sample):
        if not p.exists():
            print(f"MISSING {p} -- run scripts/restore_data.py first", file=sys.stderr)
            return 2

    rep = {}
    rep["features"] = audit(feats, pin["training_features"]["bytes"], pin["training_features"]["sha256"])
    rep["labels"] = audit(labels, pin["labels"]["bytes"], pin["labels"]["sha256"])
    rep["sample_submission"] = audit(sample, pin["sample_submission"]["bytes"],
                                     pin["sample_submission"]["sha256"])

    # ---- labels: values, connectivity, and the three footprint candidates -------------------
    with rasterio.open(labels) as src:
        y = src.read(1)
    uniq, counts = np.unique(y, return_counts=True)
    rep["labels_values"] = {str(int(u)): int(c) for u, c in zip(uniq, counts)}
    pos = y == 1
    rep["labels_positive_px"] = int(pos.sum())

    with rasterio.open(feats) as src:
        b1 = src.read(1)
        band1_finite = np.isfinite(b1) & (b1 > -1e38)
        allb = None
        for i in range(1, src.count + 1):
            a = src.read(i)
            ok = np.isfinite(a) & (a > -1e38)
            allb = ok if allb is None else (allb & ok)
        bands = [{"band": i, "description": src.tags(i).get("description"),
                  "data_category": src.tags(i).get("data_category"),
                  "nodata": src.nodata, "dtype": src.dtypes[0], "count": src.count}
                 for i in range(1, src.count + 1)]
        res = []
        for i in range(1, src.count + 1):
            a = src.read(i)
            v = a[allb & np.isfinite(a)]
            res.append(dict(band=i, name=None, min=float(v.min()), p50=float(np.percentile(v, 50)),
                            p99=float(np.percentile(v, 99)), max=float(v.max()),
                            mean=float(v.mean()), nan_in_footprint=int((~np.isfinite(a)).sum())))
    rep["footprint_candidates"] = dict(band1_finite=int(band1_finite.sum()),
                                        all_bands_finite=int(allb.sum()))
    with rasterio.open(sample) as src:
        s = src.read(1)
        ok = np.isfinite(s) & (s > -1e38)
    rep["footprint_candidates"]["sample_submission_finite"] = int(ok.sum())
    rep["sample_submission_ones_on_labels"] = int(((s == 1) & pos).sum())
    rep["sample_submission_positive_px"] = int((s == 1).sum())

    for b, r in zip(bands, res):
        b.update(r)
    (OUT / "band_inventory.json").write_text(json.dumps(bands, indent=1))
    (OUT / "grid.json").write_text(json.dumps(rep, indent=1))

    print(json.dumps({k: v for k, v in rep.items() if k != "features"}, indent=1)[:2400])
    print("\nband tags (from the file itself):")
    for b in bands:
        print(f"  {b['band']:>2} {b['data_category']:<16} {b['description'][:74]}")
    print("\nPREPARE_OK=True")
    return 0


if __name__ == "__main__":
    sys.exit(main())
