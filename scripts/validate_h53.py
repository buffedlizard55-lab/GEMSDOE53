#!/usr/bin/env python3
"""H53-1 promotion gate: does cross-dataset orientation coincidence beat its controls on the
spatially-blocked, catalogue-masked instruments?  Nothing is promoted here; the slot decision is a
separate, explicit step (see docs/validation.html).

Protocol is deliberately identical to ``scripts/validate_holdout.py`` -- same fold generator, same
buffer, same prevalence, same budgets, same *greedy* emitter, same metric -- so the numbers here are
comparable with the numbers already in ``evidence/holdout_{hide,tip}.json`` rather than merely
plausible.  The two additions this arm needs are:

* a **spaced** emitter option, because the measured optimum of the incumbent (``d2-8``: 37 654 px, all
  single pixels, median nearest-neighbour distance 3.0 px) is a minimum-separation lattice, and the
  plain top-k emitter has no notion of separation;
* a **relative** control: the same emit at the same budget from a score field that has been rolled
  across the tile grid by a random tile offset, i.e. everything about the arm except the same-place
  pairing.

Arms scored: the detector's own families, the surface-only and union controls, the spaced vs top-k
emitters, the tile-rolled field, and (when present) every sibling raster in ``data/scored``.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_pipeline as R                                   # noqa: E402
from gems52 import holdout as HO                           # noqa: E402
from gems52 import nodes as N                              # noqa: E402
from gems52 import dicoincidence as DC                     # noqa: E402

EV = ROOT / "evidence"
WORK = ROOT / "work" / "dicoincidence"
SIBLINGS = [f.name for f in sorted((ROOT / "data/scored").glob("*.tif"))]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def dense(node: dict, values: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    g = np.zeros(shape, dtype=np.float32)
    g[node["row"], node["col"]] = values.astype(np.float32)
    return g


def spaced_score(field: np.ndarray, allowed: np.ndarray, budget: int, min_px: float) -> np.ndarray:
    """Top-`budget` under a minimum separation; the mass is produced inside `spacing_select`."""
    return N.emit_nodes(field, allowed, budget, min_px=min_px)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="tip,hide")
    ap.add_argument("--budgets", default="37654")
    ap.add_argument("--min-px", type=float, default=3.0)
    ap.add_argument("--n-folds", type=int, default=4)
    ap.add_argument("--arms", default="B_corr,A_corr,A_corr_deep,B_only,field_only,union")
    ap.add_argument("--emit", default="topk", choices=["topk", "greedy"],
                    help="topk matches scripts/validate_holdout.py and is the comparable setting")
    a = ap.parse_args(argv)

    valid, cat = R.load_valid_cat()
    lab = rasterio.open(ROOT / "data/labels.tif").read(1)
    z = np.load(WORK / "nodes.npz")
    arms = np.load(WORK / "arms.npz")
    node = {k: z[k] for k in ("row", "col", "tile")}
    shape = valid.shape
    fields = {k: dense(node, arms[k], shape) for k in a.arms.split(",")}
    # the control that isolates "same place" from "same fabric": roll the whole field by a random
    # multiple of the tile size, so the exact multiset of scores and every tile-internal geometry is
    # preserved and only the *pairing with this location* is destroyed (the same null as the pair
    # test, one level up).
    rng = np.random.default_rng(11)
    TILE = DC.TILE_PX
    for name in list(fields):
        dy, dx = int(rng.integers(shape[0] // TILE)), int(rng.integers(shape[1] // TILE))
        fields[f"{name}_rolled"] = np.roll(np.roll(fields[name], dy * TILE, 0), dx * TILE, 1)

    budgets = tuple(int(x) for x in a.budgets.split(","))

    out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "budgets": list(budgets), "min_px": a.min_px, "n_folds": a.n_folds,
           "notes": "greedy emitter (R.PREREG emission) unless the arm name ends in :spaced; "
                    "sibling rasters are scored as-is at full mass",
           "modes": {}}
    for mode in a.modes.split(","):
        folds = HO.make_folds(cat, valid, n_folds=a.n_folds, buffer_px=4,
                              prevalence=R.PREREG["prevalence_used"], seed=0, mode=mode)
        rows = []
        for f in folds:
            allowed0 = valid & ~f["visible"] & f["region"]
            sc = HO.arm_scores(fields, f, valid, budgets=budgets, emit=a.emit)
            for name in a.arms.split(","):
                em = spaced_score(fields[name], allowed0, budgets[0], a.min_px)
                s = HO.score(em, f, valid, extra=False)
                sc[f"{name}:spaced|{budgets[0]}"] = {k: (round(v, 5) if isinstance(v, float) else v)
                                                     for k, v in s.items()}
            rows.append(dict(fold=f["fold"], n_truth=f["n_truth"], scores=sc))
            best = max(sc.items(), key=lambda kv: kv[1]["dti"])
            log(f"  {mode} fold {f['fold']} ({f['n_truth']} truth px): best {best[0]} "
                f"{best[1]['dti']:.4f}")
        keys = sorted({k for r in rows for k in r["scores"]})
        summary = {}
        for k in keys:
            v = np.array([r["scores"][k]["dti"] for r in rows], dtype=np.float64)
            summary[k] = dict(mean=round(float(v.mean()), 5), sd=round(float(v.std()), 5),
                              best_fold=round(float(v.max()), 5), worst_fold=round(float(v.min()), 5),
                              n_folds=int(v.size))
        out["modes"][mode] = {"emit": a.emit, "per_fold": rows, "summary": summary,
                              "ranking": sorted(summary, key=lambda k: -summary[k]["mean"])}
        for nm, s in sorted(summary.items(), key=lambda kv: -kv[1]["mean"])[:12]:
            log(f"  {mode:5s} {nm:34s} mean {s['mean']:.4f} +- {s['sd']:.4f}")
    EV.mkdir(exist_ok=True)
    (EV / "h53_holdout.json").write_text(json.dumps(out, indent=1) + "\n")
    log("wrote evidence/h53_holdout.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
