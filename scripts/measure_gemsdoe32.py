#!/usr/bin/env python3
"""Measure the registry copy of GEMSDOE32 H33-2-B2 (owner claim: 0.2708 base, dots within 2 px of the catalogue removed).

Every number written to evidence/gemsdoe32_measured.json is computed here from the file bytes. Nothing is typed by hand.
Usage: python scripts/measure_gemsdoe32.py --registry /tmp/g53/uniq --data-dir /tmp/gems53-data
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems53.core import dti  # noqa: E402

FILES = {
    "nan": "GEMSDOE32__docs__downloads__gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-nan.tif",
    "zeros": "GEMSDOE32__docs__downloads__gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif",
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="/tmp/g53/uniq")
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "gemsdoe32_measured.json"))
    args = ap.parse_args()
    dd = Path(args.data_dir)
    cat = rasterio.open(dd / "labels.tif").read(1) == 1
    fp = np.isfinite(rasterio.open(dd / "sample_submission.tif").read(1))
    d_cat = ndimage.distance_transform_edt(~cat)
    out = {"owner_claims_not_verified": ["0.2708 base", "dots within 2 px of the public catalogue removed",
                                         "37,654 dots", "no organiser score exists"],
           "files": {}}
    for tag, name in FILES.items():
        p = Path(args.registry) / name
        with rasterio.open(p) as s:
            a = s.read(1).astype(np.float64)
            nod = s.nodata
        fin = np.isfinite(a)
        vals = np.unique(a[fin])
        dots = fin & (a > 0)
        rr, cc = np.nonzero(dots)
        dc = d_cat[rr, cc]
        nn = cKDTree(np.c_[rr, cc]).query(np.c_[rr, cc], k=2)[0][:, 1]
        r = dti(np.nan_to_num(a, nan=0.0).astype(np.float32), cat)
        out["files"][tag] = {
            "file": name, "sha256": sha256(p), "bytes": p.stat().st_size, "nodata": None if nod is None else str(nod),
            "finite_px": int(fin.sum()), "footprint_px": int(fp.sum()),
            "distinct_values": [float(v) for v in vals], "dots": int(dots.sum()),
            "dots_share_of_footprint": round(float(dots.sum() / fp.sum()), 6),
            "dots_within_2px_of_catalogue": round(float((dc <= 2).mean()), 6),
            "dots_within_3px_of_catalogue": round(float((dc <= 3).mean()), 6),
            "nearest_dot_distance_quantiles_px": {str(q): round(float(np.quantile(nn, q)), 3) for q in (0.05, 0.25, 0.5, 0.75)},
            "share_dots_whose_nearest_dot_is_over_3px": round(float((nn > 3).mean()), 6),
            "in_catalogue_DTI_diagnostic": round(float(r["DTI"]), 6),
            "outside_footprint_is_nan": bool(np.array_equal(fin, fp)),
        }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: {kk: v[kk] for kk in ("dots", "dots_within_2px_of_catalogue", "nearest_dot_distance_quantiles_px", "outside_footprint_is_nan")}
                      for k, v in out["files"].items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
