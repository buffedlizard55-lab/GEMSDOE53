#!/usr/bin/env python3
"""Cache the GEMS57 feature cube tile-by-tile (float16) under work/feat/.

One full-grid pass, ~90 s per pass on this sandbox (measured), instead of re-reading the
419 MB feature stack for every model fit.  Nothing here is label-derived; see src/gems57/feat.py
for the physics of each transform and for the View A / View B split.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from gems57.feat import RasterSource, feature_names, tile_features  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tile", type=int, default=512)
    ap.add_argument("--out", default="work/feat")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    src = RasterSource(str(ROOT / "data/training_features.tif"))
    H, W = src.shape()
    names = feature_names()
    manifest = {"tile": args.tile, "height": H, "width": W, "features": names, "tiles": []}
    n_done = 0
    t0 = time.time()
    for r0 in range(0, H, args.tile):
        for c0 in range(0, W, args.tile):
            h = min(args.tile, H - r0)
            w = min(args.tile, W - c0)
            path = out / f"tile_r{r0}_c{c0}.npy"
            if path.exists() and not args.force:
                n_done += 1
                continue
            win = rasterio.windows.Window(c0, r0, w, h)
            cube = tile_features(src, win)
            np.save(path, cube.astype(np.float16))
            manifest["tiles"].append(dict(row=r0, col=c0, h=h, w=w, file=path.name))
            n_done += 1
            if n_done % 10 == 0:
                print(f"[{n_done}] r{r0} c{c0}  {time.time()-t0:.0f}s", flush=True)
    src.close()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"tiles written/skipped: {n_done} in {time.time()-t0:.0f}s -> {out}")


if __name__ == "__main__":
    main()
