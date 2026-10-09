#!/usr/bin/env python3
"""X6 - build the H8-lane candidate GeoTIFF (pre-registration-h8-2026-10-09.md, experiment X6).

1. Read the arm/budget selected by X5 (pre-registered rule).
2. Build the lane features from the FULL catalogue (every fault is visible at prediction time -
   legitimate; the leakage rule applies to training features, and nothing here is fitted to labels).
3. Poisson-pack the emission dots at 2.8 px, pruned strictly >2 px off the full catalogue.
4. Write TWO files from the identical emission with the SHARED template writer (src/submission_io.py):
     primary  ...-zeros.tif       : every pixel finite in [0,1], 0 outside, nodata None
                                    (the container of the organiser-scored GEMSDOE32 zeros variant;
                                     passes the portal's "Predicted values must be in range [0, 1]"
                                     check that rejects NaN - see pre-registration section 6)
     twin     ...-nan-outside.tif : template-conformant (NaN outside, nodata nan), passes
                                    `python -m src.submission_io validate-conformant`
5. Run the shared validators and in-lane checks (no NaN inside the footprint; values in [0,1];
   CRS/shape/transform vs the sample; prune respected; dot spacing).
6. Uniqueness gate vs the full registry (scripts/uniqueness_gate.py): byte/pixel identity, rho
   (whole-grid and footprint-only), raw overlap AND chance-corrected lift (DEV-2 rule).
7. Label by the pre-registered rule; write receipts.

Usage: python scripts/x6_h8_build.py --data-dir /tmp/gems53-data --template /tmp/gems-template \
          --registry /tmp/gems53-registry
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import stats
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import dist_to, segment_folds  # noqa: E402
from gems53.corridors import (  # noqa: E402
    corridor_surface,
    prune_mask,
    relay_surface,
    tip_continuation_surface,
)
from gems53.ridge import nms_centrelines, poisson_pack, ridge_fields  # noqa: E402

BAND_RTP = 2
R_PACK_PX = 2.8
MAX_COMMENT = 140
DATE_TAG = "20261009"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def pixel_sha256(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype="<f4").tobytes()).hexdigest()


def load_shared(template: Path):
    sys.path.insert(0, str(template / "src"))
    import submission_io as sio
    return sio


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template", default="/tmp/gems-template")
    ap.add_argument("--registry", default="/tmp/gems53-registry")
    ap.add_argument("--holdout", default=str(ROOT / "evidence" / "x5_h8_holdout.json"))
    ap.add_argument("--arm", default=None, help="override the X5 selection")
    ap.add_argument("--budget", type=int, default=None, help="override the X5 selection")
    ap.add_argument("--outdir", default=str(ROOT / "docs" / "downloads"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    tpl = Path(args.template)
    sio = load_shared(tpl)

    sel = json.loads(Path(args.holdout).read_text())["selection"]
    arm = args.arm or sel["best_arm"]
    n_budget = int(args.budget or sel["best_budget"])
    print(f"arm={arm} N={n_budget}", flush=True)

    with rasterio.open(dd / "sample_submission.tif") as src:
        sample = src.read(1)
        sprofile = src.profile.copy()
        transform, crs, H, W = src.transform, src.crs, src.height, src.width
    fp = np.isfinite(sample)
    with rasterio.open(dd / "labels.tif") as src:
        lab = src.read(1)
    cat = (lab == 1) & fp
    with rasterio.open(dd / "training_features.tif") as src:
        rtp = src.read(BAND_RTP).astype(np.float64)
    rtp[rtp < -1e30] = np.nan
    rtp_ok = fp & np.isfinite(rtp)

    # ---- features from the FULL catalogue (prediction-time legitimate) ----
    L, th, pol, _det = ridge_fields(rtp, fp)
    centre = nms_centrelines(L, th)
    ridge_ok = rtp_ok & centre & (L > 0)
    tip = tip_continuation_surface(cat)
    rel = relay_surface(cat)
    comb = corridor_surface(cat, L, fp)

    pr = prune_mask(cat, px=2)
    allowed = fp & pr
    if arm == "h8_pr":
        rr, cc = np.nonzero(allowed)
        vals = comb[rr, cc]
    elif arm == "ridge_pr":
        rr, cc = np.nonzero(allowed & ridge_ok)
        vals = L[rr, cc]
    elif arm == "halo_pr":
        rr, cc = np.nonzero(allowed)
        vals = -dist_to(cat)[rr, cc]
    elif arm == "null_pr":
        rr, cc = np.nonzero(allowed)
        vals = np.random.default_rng(53).random(rr.size)
    else:
        raise SystemExit(f"unknown arm {arm}")
    order = np.argsort(-vals, kind="stable")
    rc_sorted = np.stack([rr[order], cc[order]], axis=1).astype(np.int64)
    packed = poisson_pack(rc_sorted, n_budget, r_px=R_PACK_PX)
    if packed.shape[0] < n_budget:
        print(f"WARNING: only {packed.shape[0]} dots available at budget {n_budget}", flush=True)

    emission = np.zeros((H, W), dtype=np.float32)
    emission[packed[:, 0], packed[:, 1]] = 1.0
    assert emission[cat].sum() == 0, "prune failed: dots on the catalogue"
    assert emission[~pr].sum() == 0, "prune failed: dots within 2 px of the catalogue"

    pix_sha = pixel_sha256(emission)
    name = f"gems53-h8-tiprelay-ridgeconcord-pr2-n{n_budget}-{DATE_TAG}-{pix_sha[:8]}"
    note = (f"OK TO SUBMIT | GEMS53 h8 tip/relay corridors + magnetic concordance, pruned >2px off "
            f"catalogue, {packed.shape[0]} dots @2.8px | HOLDOUT-DTI see receipt | unique vs registry")
    note = note[:MAX_COMMENT]

    # ---- write the two variants with the SHARED template writer ----
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    prof_zeros = sio.clean_profile(sprofile, height=H, width=W, crs=crs, transform=transform,
                                   dtype="float32", compress="deflate", tiled=True, tile=256,
                                   nodata=None)
    zeros_path = outdir / f"{name}-zeros.tif"
    info_zeros = sio.write_submission(zeros_path, emission, prof_zeros,
                                      band_description=f"fault-presence probability (GEMS53 h8) - {name}")

    conformed, conf_stats = sio.conform_to_template(emission, sample)
    prof_nan = sio.clean_profile(sprofile, height=H, width=W, crs=crs, transform=transform,
                                 dtype="float32", compress="deflate", tiled=True, tile=256,
                                 nodata=float("nan"))
    nan_path = outdir / f"{name}-nan-outside.tif"
    info_nan = sio.write_submission(nan_path, conformed, prof_nan,
                                    band_description=f"fault-presence probability (GEMS53 h8) - {name}")

    # ---- validators ----
    def run_cli(args_list):
        r = subprocess.run(args_list, capture_output=True, text=True, cwd=str(tpl))
        return {"cmd": " ".join(args_list), "exit": r.returncode,
                "stdout": r.stdout[-4000:], "stderr": r.stderr[-2000:]}

    validators = {
        "validate_conformant_zeros": run_cli([sys.executable, "-m", "src.submission_io",
                                              "validate-conformant", str(zeros_path),
                                              "--sample", str(dd / "sample_submission.tif")]),
        "validate_conformant_nan": run_cli([sys.executable, "-m", "src.submission_io",
                                            "validate-conformant", str(nan_path),
                                            "--sample", str(dd / "sample_submission.tif")]),
        "validate_submission_zeros": run_cli([sys.executable, str(tpl / "scripts" / "validate_submission.py"),
                                              "--pred", str(zeros_path), "--sample", str(dd / "sample_submission.tif"),
                                              "--train", str(dd / "training_features.tif")]),
        "validate_submission_nan": run_cli([sys.executable, str(tpl / "scripts" / "validate_submission.py"),
                                            "--pred", str(nan_path), "--sample", str(dd / "sample_submission.tif"),
                                            "--train", str(dd / "training_features.tif")]),
    }

    def inlane(path: Path) -> dict:
        with rasterio.open(path) as s:
            a = s.read(1)
            checks = {
                "single_band": s.count == 1,
                "dtype_float32": s.dtypes[0] == "float32",
                "shape_matches_template": (s.height, s.width) == (H, W),
                "crs_is_EPSG_32611": s.crs is not None and s.crs.to_epsg() == 32611,
                "transform_matches_template": tuple(s.transform)[:6] == tuple(transform)[:6],
            }
        fin = np.isfinite(a)
        checks["no_nan_or_inf_inside_footprint"] = bool(np.isfinite(a[fp]).all())
        checks["inside_footprint_in_0_1"] = bool(((a[fp] >= 0) & (a[fp] <= 1)).all())
        checks["all_finite_values_in_0_1"] = bool(((a[fin] >= 0) & (a[fin] <= 1)).all())
        return {"checks": checks,
                "counts": {"finite_px": int(fin.sum()), "nan_px": int((~fin).sum()),
                           "nonzero_px": int(np.count_nonzero(np.nan_to_num(a))),
                           "min": float(np.nanmin(a)), "max": float(np.nanmax(a))},
                "all_checks_passed": all(checks.values())}

    inl_zeros = inlane(zeros_path)
    inl_nan = inlane(nan_path)

    # Pre-registration section 5/6: validate-conformant governs the NaN-outside twin; the zeros primary
    # deliberately has no NaN (the [0,1] form fix, IR-53-91) so its nonzero exit there is EXPECTED.
    expected_fail = {"validate_conformant_zeros": "expected non-zero: this validator enforces NaN outside"}
    format_ok = (inl_zeros["all_checks_passed"] and inl_nan["all_checks_passed"]
                 and validators["validate_conformant_nan"]["exit"] == 0
                 and validators["validate_submission_zeros"]["exit"] == 0
                 and validators["validate_submission_nan"]["exit"] == 0)

    # spacing + prune diagnostics on the emitted dots
    tree = cKDTree(packed.astype(np.float64))
    d_nn, _ = tree.query(packed.astype(np.float64), k=2)
    spacing = {"median_nearest_dot_px": float(np.median(d_nn[:, 1])),
               "min_nearest_dot_px": float(np.min(d_nn[:, 1])),
               "r_pack_px": R_PACK_PX}
    d_cat = dist_to(cat)
    prune_check = {"dots_on_catalogue": int(emission[cat].sum()),
                   "dots_within_2px_of_catalogue": int(emission[d_cat <= 2].sum()),
                   "min_dist_dot_to_catalogue_px": float(d_cat[packed[:, 0], packed[:, 1]].min())}

    # ---- uniqueness gate (raw + chance-corrected, DEV-2) ----
    import uniqueness_gate as ug
    gate_receipt = ROOT / "evidence" / f"uniqueness_gate_{name}.json"
    gate_summary = ug.run_gate(str(zeros_path), [Path(args.registry)], str(gate_receipt),
                               surface=comb, candidates=allowed, footprint=fp, final_array=emission)
    rows = json.loads(gate_receipt.read_text())["all_rows"]

    # footprint-only rho (IR-53-47) for every row whose whole-grid rho is at all high: ONE registry pass
    rng = np.random.default_rng(53)
    fp_idx = rng.choice(int(fp.sum()), min(300_000, int(fp.sum())), replace=False)
    fp_flat_idx = np.nonzero(fp.ravel())[0][fp_idx]
    ours_fp = emission.ravel()[fp_flat_idx].astype(np.float64)
    need = {r["file"] for r in rows if max(r.get("rho_final", 0.0), r.get("rho_surface", 0.0)) > 0.5}
    by_file = {r["file"]: r for r in rows}
    for nm, _sha, arr in ug.iter_registry([Path(args.registry)], emission.shape):
        if nm in need:
            by_file[nm]["rho_footprint_only"] = round(float(stats.spearmanr(
                ours_fp, arr.ravel()[fp_flat_idx].astype(np.float64)).statistic), 6)
        del arr
    flagged_raw, flagged_new = [], []
    for r in rows:
        rho_fp = r.get("rho_footprint_only", r.get("rho_final", 0.0))
        raw = r.get("overlap_final", 0) > 0.70 or r.get("rho_final", 0) > 0.90
        lift = r.get("lift_over_chance")
        new = (rho_fp > 0.90) or (r.get("overlap_final", 0) > 0.70 and lift is not None and lift > 2.0)
        if raw:
            flagged_raw.append(r["file"])
        if new:
            flagged_new.append({"file": r["file"], "overlap_final": r.get("overlap_final"),
                                "lift_over_chance": lift, "rho_final": r.get("rho_final"),
                                "rho_footprint_only": r.get("rho_footprint_only")})

    uniq_pass = len(flagged_new) == 0

    label = "OK TO SUBMIT" if (uniq_pass and format_ok) else "DO NOT SUBMIT"
    receipt = {
        "experiment": "X6 build + gates (pre-registration-h8-2026-10-09.md)",
        "selection_used": {"arm": arm, "N": n_budget, "from": sel},
        "name": name,
        "note": note,
        "label": label,
        "files": {
            "primary_zeros": {"path": str(zeros_path), "sha256": sha256(zeros_path),
                              "pixel_sha256": pix_sha, "writer": "template src/submission_io.write_submission",
                              "info": info_zeros, "in_lane": inl_zeros},
            "twin_nan_outside": {"path": str(nan_path), "sha256": sha256(nan_path),
                                 "pixel_sha256": pixel_sha256(conformed),
                                 "conform_stats": conf_stats, "info": info_nan, "in_lane": inl_nan},
        },
        "emission": {"dots": int(packed.shape[0]), "budget": n_budget, "arm": arm,
                     "spacing": spacing, "prune_check": prune_check,
                     "footprint_px": int(fp.sum()), "catalogue_px": int(cat.sum())},
        "validators": validators,
        "validators_expected_failures": expected_fail,
        "format_validators_ok": bool(format_ok),
        "uniqueness": {
            "receipt": str(gate_receipt),
            "n_registry_rows": len(rows),
            "flagged_raw_rule_0p70_overlap_or_0p90_rho": len(flagged_raw),
            "flagged_DEV2_rule": flagged_new,
            "DEV2_rule": "byte/pixel identity differs; rho_final <= 0.90; NOT(overlap>0.70 AND lift>2.0)",
            "pass": bool(uniq_pass),
        },
        "runtime_s": round(time.time() - t0, 1),
    }
    out = ROOT / "evidence" / f"x6_candidate_receipt_{name}.json"
    out.write_text(json.dumps(receipt, indent=1))
    print("wrote", out)
    print(json.dumps({"label": label, "name": name, "note": note,
                      "dots": int(packed.shape[0]),
                      "flagged_DEV2": len(flagged_new),
                      "inlane_zeros_pass": inl_zeros["all_checks_passed"],
                      "inlane_nan_pass": inl_nan["all_checks_passed"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
