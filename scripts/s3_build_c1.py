#!/usr/bin/env python3
"""Session-2 experiment S2-E3: build the C1 candidate GeoTIFF (template-conformant, GD-2 revised).

Reads the stage-1 selection from evidence/s2_c1_holdout.json, retrains the selected arm on the FULL
visible catalogue (design-B positives; for arm bc1 the catalogue enters only as labels, never as
features), masks catalogue pixels pixel-exactly in the emission, and writes:
  * docs/submissions/<name>.tif          -- the downloadable candidate (NaN exactly where the sample is)
  * /tmp/s2_c1_surface.npz               -- pre-placement surface + footprint for uniqueness_gate_v2.py
  * evidence/s3_c1_build_receipt.json    -- build receipt (sha256, counts, validator inputs)

The label (OK-to-submit vs research-only) is decided AFTER the uniqueness gate and validators run;
this script never decides it.
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
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import load_inputs, thin_emission  # noqa: E402
from gems53.c1 import build_c1_features  # noqa: E402
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402
from e2_leakfree_holdouts import hgb  # noqa: E402

SEED = 53
N_NEG = 300_000


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--holdout", default=str(ROOT / "evidence" / "s2_c1_holdout.json"))
    ap.add_argument("--out-dir", default=str(ROOT / "docs" / "submissions"))
    ap.add_argument("--surface-out", default="/tmp/s2_c1_surface.npz")
    ap.add_argument("--receipt", default=str(ROOT / "evidence" / "s3_c1_build_receipt.json"))
    args = ap.parse_args()
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fp_px = int(inp.fp.sum())

    hold = json.loads(Path(args.holdout).read_text())
    sel = hold["segment_selection"]["selected"]
    spatial = hold.get("spatial_confirmation", {})
    accepted = bool(spatial.get("acceptance", {}).get("accepted")) if spatial.get("status") == "COMPLETED" else False
    if sel is None:
        raise SystemExit("no variant qualified in stage 1; nothing to build")
    arm, variant = sel["arm"], sel["variant"]
    kind = "top" if variant.startswith("top_q") else ("thin_p" if variant.startswith("thin_p") else "thin_bin")
    q = float(variant.rsplit("_q", 1)[1].replace("p", "."))

    Xc1, c1_names = build_c1_features(inp.feats, inp.fp, inp.fp_idx)
    F = inp.feats if arm == "bands" else np.ascontiguousarray(
        np.column_stack([inp.feats, Xc1]).astype(np.float32))

    # Final training: ALL catalogue pixels are visible (prediction-time situation for arm bc1).
    rng = np.random.default_rng(SEED)
    pos_rows = inp.fp_idx[inp.cat & inp.fp]
    neg_pool = inp.fp_idx[inp.fp & ~inp.cat]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows_tr = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = hgb()
    model.fit(F[rows_tr], y)
    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, F)
    p_full[inp.cat] = 0.0  # pixel-exact catalogue mask

    np.savez_compressed(args.surface_out, surface=p_full.astype(np.float32), footprint=inp.fp)
    cand = inp.fp & ~inp.cat
    if kind == "top":
        emis = top_q_emission(p_full, cand, q, fp_px)
        kept = int(np.count_nonzero(emis))
    else:
        emis, kept, _ = thin_emission(p_full, cand, q, fp_px, value="p" if kind == "thin_p" else "bin")
        kept = int(kept)

    # Template-conformant write (GD-2 revised): NaN exactly where sample is NaN, finite in [0,1] elsewhere.
    with rasterio.open(dd / "sample_submission.tif") as s:
        sample = s.read(1)
        base_profile = s.profile.copy()
    fp_official = np.isfinite(sample)
    assert bool((fp_official == inp.fp).all()), "footprint derived from sample mismatch"
    arr = np.full((inp.H, inp.W), np.nan, dtype=np.float32)
    arr[inp.fp] = emis[inp.fp]
    assert np.isfinite(arr[inp.fp]).all() and float(arr[inp.fp].min()) >= 0.0 and float(arr[inp.fp].max()) <= 1.0

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    pixel_sha = hashlib.sha256(arr.tobytes()).hexdigest()[:8]
    name = f"gems53-c1-condmag-{variant}-{ts}-{pixel_sha}"
    out_path = Path(args.out_dir) / f"{name}.tif"
    profile = dict(driver="GTiff", height=inp.H, width=inp.W, count=1, dtype="float32",
                   crs=inp.crs, transform=inp.transform, nodata=float("nan"), compress="lzw")
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr, 1)

    receipt = {
        "schema": "gems53.s3_build_receipt.v1",
        "started_utc": started,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_s": round(time.time() - t0, 1),
        "preregistration": "docs/research/preregistration-2026-10-09-session2.md",
        "arm": arm, "variant": variant, "kind": kind, "q": q,
        "stage1_selected": sel,
        "stage2_acceptance": {"status": spatial.get("status"), "accepted": accepted,
                              "detail": spatial.get("acceptance")},
        "training": {"positives_all_catalogue": int(pos_rows.size), "negatives": int(neg_rows.size),
                     "seed": SEED, "model": "HistGradientBoostingClassifier(max_iter=200, lr=0.1, "
                                              "max_leaf_nodes=31, l2=1.0, random_state=0)"},
        "c1_features": c1_names,
        "emission": {"kind": kind, "q": q, "candidate_px": int(cand.sum()), "dots_or_emitted_px": kept},
        "surface_npz": args.surface_out,
        "file": str(out_path.relative_to(ROOT)),
        "name": name,
        "sha256_file": sha256_file(out_path),
        "pixel_sha256": hashlib.sha256(arr.tobytes()).hexdigest(),
        "bytes": out_path.stat().st_size,
        "inlane_checks": {
            "finite_all_sample_valid_px": bool(np.isfinite(arr[fp_official]).all()),
            "nan_exactly_outside_sample_valid": bool(np.isnan(arr[~fp_official]).all()),
            "values_in_0_1": bool((arr[fp_official] >= 0).all() and (arr[fp_official] <= 1).all()),
            "dtype": "float32", "nodata": "nan", "compress": "lzw",
            "crs": str(inp.crs), "transform": [float(v) for v in tuple(inp.transform)[:6]],
            "shape": [inp.H, inp.W],
        },
        "label": "PENDING-GATES",
    }
    Path(args.receipt).write_text(json.dumps(receipt, indent=2))
    print(json.dumps({"file": receipt["file"], "name": name, "dots": kept,
                      "sha256": receipt["sha256_file"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
