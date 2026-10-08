#!/usr/bin/env python3
"""Pass-1 recon #2: how is the 0.2778 reference file placed, relative to the catalogue?

Answers, with counts (no prose claims):
  * footprint size, catalogue size, mask semantics;
  * the distance histogram from every emitted pixel to the nearest catalogue pixel;
  * the share of the family's scored priors that sit in each distance band.

Read-only.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> np.ndarray:
    with rasterio.open(path) as ds:
        return ds.read(1)


def main() -> None:
    lab = read(ROOT / "data/labels.tif")
    ss = read(ROOT / "data/sample_submission.tif")
    foot = np.isfinite(ss)                      # footprint = finite in the sample submission
    cat = (lab == 1)                            # catalogued (known) fault pixels
    out = {
        "shape": list(lab.shape),
        "footprint_px": int(foot.sum()),
        "catalogue_px": int(cat.sum()),
        "catalogue_frac_of_footprint": round(float(cat.sum()) / float(foot.sum()), 6),
        "labels_unique": [float(v) for v in np.unique(lab)],
        "catalogue_inside_footprint_px": int((cat & foot).sum()),
        "catalogue_outside_footprint_px": int((cat & ~foot).sum()),
        "footprint_has_zero_in_ss": int((foot & (ss == 0)).sum()),
    }

    # distance (px) from every pixel to the nearest catalogue pixel
    dist = ndimage.distance_transform_edt(~cat)

    ref = read(ROOT / "data/reference/h33-2-b2-zeros.tif")
    refpix = ref > 0
    d = dist[refpix]
    bands = [(0.5, "0 (on catalogue)"), (1.5, "1 px"), (2.5, "2 px"), (3.5, "3 px"),
             (6.5, "4-6 px"), (10.5, "7-10 px"), (20.5, "11-20 px"), (1e9, ">20 px")]
    hist, prev = [], 0.0
    for hi, name in bands:
        n = int(((d > prev) & (d <= hi)).sum())
        hist.append({"band": name, "px": n, "share": round(n / max(1, refpix.sum()), 4)})
        prev = hi
    out["reference_0p2778_n_px"] = int(refpix.sum())
    out["reference_distance_to_catalogue_hist"] = hist
    out["reference_on_catalogue_px"] = int((refpix & cat).sum())
    out["reference_inside_footprint_px"] = int((refpix & foot).sum())
    out["reference_outside_footprint_px"] = int((refpix & ~foot).sum())

    # catalogue morphology
    lab2, n_lab = ndimage.label(cat, structure=np.ones((3, 3)))
    sizes = np.bincount(lab2.ravel())[1:]
    out["catalogue_components"] = int(n_lab)
    out["catalogue_component_size_px"] = {
        "min": int(sizes.min()), "p50": float(np.median(sizes)),
        "p90": float(np.percentile(sizes, 90)), "max": int(sizes.max()),
    }
    out["catalogue_components_ge_5px"] = int((sizes >= 5).sum())

    # what does the footprint look like: connected blocks?
    fb, nb = ndimage.label(foot, structure=np.ones((3, 3)))
    fs = np.bincount(fb.ravel())[1:]
    out["footprint_components"] = int(nb)
    out["footprint_top5_block_px"] = [int(v) for v in np.sort(fs)[::-1][:5]]
    out["footprint_top5_block_share"] = [round(float(v) / float(foot.sum()), 4)
                                        for v in np.sort(fs)[::-1][:5]]

    # how much of the catalogue is inside the largest footprint block
    big = fb == (np.argmax(fs) + 1)
    out["catalogue_in_largest_block_px"] = int((cat & big).sum())

    # prior scored submissions: where do they sit relative to the catalogue?
    priors = {}
    for p in sorted((ROOT / "data/scored").glob("*.tif")):
        a = read(p)
        pos = np.isfinite(a) & (a > 0)
        dd = dist[pos]
        priors[p.name] = {
            "n_px": int(pos.sum()),
            "share_within_3px": round(float((dd <= 3).mean()), 4) if pos.any() else None,
            "share_on_catalogue": round(float((dd < 0.5).mean()), 4) if pos.any() else None,
            "share_gt20px": round(float((dd > 20).mean()), 4) if pos.any() else None,
            "max_value": float(np.nanmax(a)),
            "min_positive": float(np.nanmin(a[pos])) if pos.any() else None,
        }
    out["priors"] = priors
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
