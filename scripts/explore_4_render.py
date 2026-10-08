#!/usr/bin/env python3
"""Render small PNGs so the winning file's geometry can be looked at, not guessed.

Writes to work/viz/ (gitignored).  Uses only rasterio + numpy + PIL if available, else writes PGM.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "viz"
OUT.mkdir(parents=True, exist_ok=True)


def save_png(arr_u8: np.ndarray, path: Path) -> None:
    try:
        from PIL import Image
        Image.fromarray(arr_u8).save(path)
        print("wrote", path, arr_u8.shape)
    except Exception as exc:  # pragma: no cover
        print("PIL unavailable:", exc)


def stretch(a: np.ndarray, lo=2, hi=98) -> np.ndarray:
    v = a[np.isfinite(a)]
    if v.size == 0:
        return np.zeros(a.shape, dtype=np.uint8)
    l, h = np.percentile(v, [lo, hi])
    if h <= l:
        h = l + 1e-9
    return np.clip((a - l) / (h - l) * 255, 0, 255).astype(np.uint8)


def main() -> None:
    lab = rasterio.open(ROOT / "data/labels.tif").read(1) == 1
    ref = rasterio.open(ROOT / "data/reference/h33-2-b2-zeros.tif").read(1) > 0
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        det = ds.read(12).astype(np.float32)      # detrended elevation
        slope = ds.read(19).astype(np.float32)
    det[det < -1e38] = np.nan
    slope[slope < -1e38] = np.nan

    rgb = np.zeros(det.shape + (3,), dtype=np.uint8)
    rgb[..., 0] = stretch(det)                    # topography, red channel
    rgb[..., 1] = stretch(slope)                  # slope, green channel
    rgb[..., 2] = stretch(np.where(np.isfinite(det), det, np.nan))
    rgb[lab] = (0, 0, 255)                        # catalogue in blue
    rgb[ref] = (255, 60, 0)                       # the 0.2778 file in orange
    for name, k in (("overview", 1), ("zoomA", 4)):
        if k == 1:
            save_png(rgb, OUT / f"ref_vs_catalogue_{name}.png")
        else:
            h, w = rgb.shape[:2]
            for i, (r0, c0) in enumerate([(0, 0), (0, w // 2), (h // 2, 0), (h // 2, w // 2)]):
                sub = rgb[r0:r0 + h // 2, c0:c0 + w // 2]
                save_png(sub, OUT / f"ref_vs_catalogue_{name}_{i}.png")

    # where is the reference mass in feature space?  rank of det_elev / slope under its pixels
    for nm, a in (("det_elev", det), ("det_elev_slope", slope)):
        v = a[np.isfinite(a)]
        cdf = np.sort(v)
        r_ref = np.searchsorted(cdf, a[ref & np.isfinite(a)]) / cdf.size
        r_all = np.linspace(0.0, 1.0, cdf.size)
        print(f"{nm}: reference mean rank {r_ref.mean():.3f} (uniform would be 0.5), "
              f"p10 {np.percentile(r_ref,10):.3f} p90 {np.percentile(r_ref,90):.3f}")

    # nearest-catalogue distance stats of the reference around each catalogue pixel: are the
    # reference pixels anti-correlated with the catalogue at short range?
    from scipy import ndimage
    d_ref = ndimage.distance_transform_edt(~ref)
    print("catalogue pixels: median distance to nearest reference pixel "
          f"{np.median(d_ref[lab]):.1f} px, share within 3 px "
          f"{float((d_ref[lab] <= 3).mean()):.3f}")


if __name__ == "__main__":
    sys.exit(main())
