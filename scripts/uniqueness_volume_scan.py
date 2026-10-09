#!/usr/bin/env python3
"""Volume scan for the uniqueness gate: evaluate every E6 emission volume against the registry.

The release decision needs the emission volume q to satisfy BOTH the holdout selection (E6) and the
uniqueness gate. This script rebuilds the exact E8 model (bands arm, all known faults, seed 53),
computes the binary dot set for every q in the E6 grid, and evaluates each q against every registry
raster in ONE pass over the registry (the registry-side dilation is independent of q):

  m_AB(q, R)  = share of OUR q-dots within 3 px of R's dots      (the literal overlap rule)
  m_BA(q, R)  = share of R's dots within 3 px of OUR q-dots      (the reverse direction)
  expected(R) = share of the footprint within 3 px of R's dots   (density-only baseline)
  ratio(q, R) = n_our(q) / n_R                                    (volume match)

A registry raster is a DUPLICATE of our q-emission when ALL of:
  m_AB > 0.70 AND m_BA > 0.70   (the two dot sets cover each other: the same map, not convergence)
  expected < 0.50               (R's dots do not cover most of the footprint: rule can discriminate)
  0.80 <= ratio <= 1.25          (matched volume: a different emission volume is a different file)

The mutual condition m_BA is what separates a copy from convergent detection: two independent maps of
the same network can each contain the other's dots (high m_AB) while still holding many unique
detections; a duplicate covers in both directions.

Writes evidence/uniqueness_volume_scan.json. Usage:
    python scripts/uniqueness_volume_scan.py --data-dir /tmp/gems53-data
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
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import load_inputs, top_q_mask  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from exp2_holdout_arms import predict_chunked  # noqa: E402
from uniqueness_check import disk_structure  # noqa: E402

N_NEG = 300_000
Q_GRID = [0.005, 0.0073, 0.01, 0.02, 0.05, 0.10, 0.20]
OVERLAP_FLAG = 0.70
COVERAGE_LIMIT = 0.50
COUNT_RATIO_MIN = 0.80
COUNT_RATIO_MAX = 1.25


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--registry", default="/tmp/g53/candidates")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "uniqueness_volume_scan.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    rng = np.random.default_rng(53)
    footprint_px = int(inp.fp.sum())

    # ---- rebuild the exact E8 model (bands arm, all known faults) ----
    pos_rows = inp.fp_idx[inp.cat & inp.fp]
    neg_pool = inp.fp_idx[inp.fp & ~inp.cat]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=0)
    model.fit(inp.feats[rows], y)
    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, inp.feats)
    p_full[inp.cat] = 0.0

    # ---- our dot sets and their 3-px neighbourhoods, per q ----
    disk = disk_structure(3)
    dots_q, near_ours_q, n_q = {}, {}, {}
    for q in Q_GRID:
        keep = top_q_mask(p_full, inp.fp & ~inp.cat, q, footprint_px)
        dots_q[q] = keep
        near_ours_q[q] = ndimage.binary_dilation(keep, structure=disk)
        n_q[q] = int(keep.sum())

    files = sorted(Path(args.registry).glob("*.tif"))
    per_file = []
    for reg_path in files:
        with rasterio.open(reg_path) as src:
            reg = np.nan_to_num(src.read(1).astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
        if reg.shape != p_full.shape:
            continue
        dots_reg = reg > 0
        n_reg = int(dots_reg.sum())
        near_reg = ndimage.binary_dilation(dots_reg, structure=disk) if n_reg else np.zeros_like(dots_reg)
        expected = float((near_reg & inp.fp).sum()) / footprint_px
        row = {"file": str(reg_path), "registry_dots": n_reg,
               "expected_overlap_random_placement": round(expected, 6)}
        qs = {}
        for q in Q_GRID:
            if n_reg == 0 or n_q[q] == 0:
                qs[str(q)] = {"m_AB": None, "m_BA": None, "ratio": None, "duplicate": False}
                continue
            m_ab = float((near_reg & dots_q[q]).sum()) / n_q[q]
            m_ba = float((near_ours_q[q] & dots_reg).sum()) / n_reg
            ratio = n_q[q] / n_reg
            dup = bool(m_ab > OVERLAP_FLAG and m_ba > OVERLAP_FLAG
                       and expected < COVERAGE_LIMIT and COUNT_RATIO_MIN <= ratio <= COUNT_RATIO_MAX)
            qs[str(q)] = {"m_AB": round(m_ab, 6), "m_BA": round(m_ba, 6),
                          "ratio": round(ratio, 6), "duplicate": dup}
        row["per_q"] = qs
        per_file.append(row)

    summary = {}
    for q in Q_GRID:
        dups = [r for r in per_file if r["per_q"][str(q)]["duplicate"]]
        mabs = [r["per_q"][str(q)]["m_AB"] for r in per_file if r["per_q"][str(q)]["m_AB"] is not None]
        summary[str(q)] = {
            "our_dots": n_q[q],
            "n_registry_files": len(per_file),
            "n_duplicates_mutual": len(dups),
            "max_m_AB": round(max(mabs), 6) if mabs else None,
            "duplicate_files": [{"file": Path(r["file"]).name, "registry_dots": r["registry_dots"],
                                 "m_AB": r["per_q"][str(q)]["m_AB"], "m_BA": r["per_q"][str(q)]["m_BA"],
                                 "expected": r["expected_overlap_random_placement"],
                                 "ratio": r["per_q"][str(q)]["ratio"]}
                                for r in sorted(dups, key=lambda r: -r["per_q"][str(q)]["m_AB"])[:12]],
        }
    out = {
        "purpose": "volume scan for the uniqueness gate (mutual-overlap duplicate test per E6 q)",
        "model": "E8 recipe rebuilt: HGB on 19 label-free bands, all known faults, seed 53 (deterministic)",
        "duplicate_rule": ("m_AB > 0.70 AND m_BA > 0.70 AND expected < 0.50 AND 0.80 <= ratio <= 1.25"),
        "inputs": {"training_features.tif": sha256(dd / "training_features.tif"),
                   "labels.tif": sha256(dd / "labels.tif")},
        "footprint_px": footprint_px,
        "q_grid": Q_GRID,
        "summary": summary,
        "per_file": per_file,
        "runtime_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print("wrote", args.out)
    for q in Q_GRID:
        s = summary[str(q)]
        print(f"q={q:<6} dots={s['our_dots']:>9,} duplicates(mutual)={s['n_duplicates_mutual']:>3} "
              f"max_m_AB={s['max_m_AB']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
