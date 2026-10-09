#!/usr/bin/env python3
"""Experiment 8 - build the unique submission, run every release gate, publish it to docs/downloads/.

Recipe (selected on the hide-and-recover holdout in E6/E7, attached as evidence):
  features = 19 label-free bands (+ the H5 edges only if E7 accepted them)
  model    = HistGradientBoostingClassifier (same hyperparameters as E2/E6/E7), trained on ALL known
             faults: positives = the 60,988 catalogue pixels, negatives = 300k random non-fault
             footprint pixels (seed 53)
  emission = binary value-1.0 dots on the top-q of the footprint by model probability; known-fault
             pixels are excluded (masked to 0) because the competition's target faults are, by
             construction, not in the public catalogue
  file     = single-band float32 GeoTIFF, EPSG:32611, 100 m, template shape/transform, values in
             [0,1] inside the footprint, NaN outside with nodata=NaN (the official sample's convention)

Release gates (all must pass before the file is offered for download):
  1. in-lane validator (gems53.core.validate_submission) on the file re-read from disk, bit-exact
     round-trip against the in-memory emission;
  2. the shared template validator (buffedlizard55-lab/GEMSDOE at dcbbb19, scripts/validate_submission.py);
  3. leakage canary of the recipe: the features are the label-free bands (Exp 1: max separability
     0.597) plus, if used, the H5 edges (E7 canary); the emission masks catalogue pixels exactly;
  4. the uniqueness gate (scripts/uniqueness_check.py against the re-mirrored public registry),
     literal flags AND the operative gate (IR-53-26);
  5. holdout evidence attached (E6/E7 numbers, labelled HOLDOUT-DTI).

Outputs:
  docs/downloads/<name>.tif                      the downloadable submission (GitHub Pages serves docs/)
  evidence/candidates/<name>.receipt.json        sha256, format checks, counts, gates, holdout numbers
  evidence/candidates/template_validator_<name>.txt  shared template validator log
  evidence/selection.json                        the selection record the site and run card read

Usage:
    python scripts/exp8_build_submission.py --data-dir /tmp/gems53-data \
        --arm bands --variant bin --q 0.05 --name gems53-hgb-bands-bin-q0p05
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import (  # noqa: E402
    edge_grid,
    emission_from_probability,
    load_inputs,
    top_q_mask,
    validate_submission,
    write_submission,
)

sys.path.insert(0, str(ROOT / "scripts"))
from exp2_holdout_arms import predict_chunked  # noqa: E402

N_NEG = 300_000
TEMPLATE_REPO = Path("/tmp/gemsrepo")
TEMPLATE_COMMIT = "dcbbb192e56b2b32c0a131eba791dc363305d4a3"
H5_BANDS = {"f_basement": 15, "f_conductivity": 17}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--arm", default="bands", choices=["bands", "bands_h5"])
    ap.add_argument("--variant", default="bin", choices=["raw", "bin", "rank", "sqrt"])
    ap.add_argument("--q", type=float, default=0.0073)
    ap.add_argument("--name", default="gems53-hgb-bands")
    ap.add_argument("--note", default=("HGB on 19 label-free bands, binary dots, top 0.73% of footprint, "
                                        "known faults zeroed; holdout proxy only, no organizer score."))
    ap.add_argument("--registry", default="/tmp/g53/candidates",
                    help="directory of single-band on-grid registry rasters (the gate population)")
    ap.add_argument("--holdout-evidence", default=str(ROOT / "evidence" / "exp6_emission_scaling.json"))
    ap.add_argument("--h5-evidence", default=str(ROOT / "evidence" / "exp7_h5_canary_holdout.json"))
    ap.add_argument("--skip-uniqueness", action="store_true",
                    help="debug only: skip the registry gate (the receipt is then marked NOT RELEASED)")
    args = ap.parse_args()
    t0 = time.time()
    assert len(args.note) <= 140, "submission note must be at most 140 characters"
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    rng = np.random.default_rng(53)
    footprint_px = int(inp.fp.sum())

    # ---- features ----
    if args.arm == "bands_h5":
        h5 = np.column_stack([edge_grid(str(dd / "training_features.tif"), inp.fp, b)[inp.fp]
                              for b in H5_BANDS.values()]).astype(np.float32)
        F_all = np.column_stack([inp.feats, h5]).astype(np.float32)
        feature_note = "19 label-free bands + H5 edges (basement depth, conductivity)"
    else:
        F_all = inp.feats
        feature_note = "19 label-free bands"

    # ---- train on ALL known faults ----
    pos_rows = inp.fp_idx[inp.cat & inp.fp]
    neg_pool = inp.fp_idx[inp.fp & ~inp.cat]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=0)
    model.fit(F_all[rows], y)

    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, F_all)
    p_full[inp.cat] = 0.0  # pixel-exact mask of the known catalogue

    keep = top_q_mask(p_full, inp.fp & ~inp.cat, args.q, footprint_px)
    emis = emission_from_probability(p_full, keep, args.variant)
    emis = np.nan_to_num(emis, nan=0.0).astype(np.float32)
    assert float(emis.min()) >= 0.0 and float(emis.max()) <= 1.0
    emis_nan = emis.copy()
    emis_nan[~inp.fp] = np.nan

    # ---- write: pick the smallest lossless encoding, verify bit-exact round-trip ----
    stem = f"{args.name}-{args.variant}-q{str(args.q).replace('.', 'p')}"
    downloads = ROOT / "docs" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    primary = downloads / f"{stem}-nan.tif"
    candidates = []
    for tag, kwargs in (("lzw", {"compress": "lzw"}),
                        ("deflate", {"compress": "deflate"}),
                        ("deflate-pred2", {"compress": "deflate", "predictor": 2})):
        p = downloads / f".{stem}-{tag}.tif"
        write_submission(str(p), emis_nan, inp.transform, inp.crs, outside_nan=True, **kwargs)
        import rasterio
        with rasterio.open(p) as src:
            back = src.read(1)
        exact = bool(np.array_equal(np.nan_to_num(back, nan=-1.0), np.nan_to_num(emis_nan, nan=-1.0))
                     and np.array_equal(np.isnan(back), np.isnan(emis_nan)))
        candidates.append({"tag": tag, "path": p, "bytes": p.stat().st_size, "bit_exact_roundtrip": exact})
    candidates.sort(key=lambda c: c["bytes"])
    best = candidates[0]
    assert best["bit_exact_roundtrip"], f"round-trip not bit-exact for {best['tag']}"
    shutil.move(str(best["path"]), str(primary))
    for c in candidates[1:]:
        c["path"].unlink(missing_ok=True)

    # ---- gate 1: in-lane validator on the re-read file ----
    r = validate_submission(str(primary), inp.fp, inp.transform, inp.crs, inp.H, inp.W)
    r["sha256"] = sha256(primary)
    r["bytes"] = primary.stat().st_size
    r["compression"] = best["tag"]
    r["compression_candidates"] = [{"tag": c["tag"], "bytes": c["bytes"],
                                    "bit_exact_roundtrip": c["bit_exact_roundtrip"]} for c in candidates]
    r["on_known_fault_px"] = int(np.count_nonzero(emis[inp.cat] > 0))
    r["emitted_px"] = int(np.count_nonzero(emis > 0))
    r["emitted_fraction_of_footprint"] = round(r["emitted_px"] / footprint_px, 6)
    import rasterio
    with rasterio.open(primary) as src:
        written = src.read(1)
        r["nodata_tag"] = src.nodata
    r["value_min"] = float(np.nanmin(written))
    r["value_max"] = float(np.nanmax(written))
    r["bit_exact_roundtrip"] = bool(
        np.array_equal(np.nan_to_num(written, nan=-1.0), np.nan_to_num(emis_nan, nan=-1.0))
        and np.array_equal(np.isnan(written), np.isnan(emis_nan)))
    in_lane_pass = bool(r["all_checks_passed"] and r["on_known_fault_px"] == 0 and r["bit_exact_roundtrip"])

    # ---- gate 2: shared template validator ----
    tmpl_log_path = ROOT / "evidence" / "candidates" / f"template_validator_{stem}.txt"
    tmpl_log_path.parent.mkdir(parents=True, exist_ok=True)
    tmpl_cmd = ["/tmp/venv/bin/python", str(TEMPLATE_REPO / "scripts" / "validate_submission.py"),
                "--pred", str(primary),
                "--sample", str(dd / "sample_submission.tif"),
                "--train", str(dd / "training_features.tif")]
    proc = subprocess.run(tmpl_cmd, capture_output=True, text=True, cwd=str(TEMPLATE_REPO))
    tmpl_log = (proc.stdout + proc.stderr)
    tmpl_log_path.write_text(tmpl_log)
    tmpl_pass = ("Validation PASSED" in tmpl_log) and proc.returncode == 0

    # ---- gate 4: uniqueness (literal + operative) ----
    uniq_path = ROOT / "evidence" / "uniqueness_check.json"
    if args.skip_uniqueness:
        uniq = {"operative_gate": {"passed": None, "status": "SKIPPED (--skip-uniqueness; NOT RELEASED)"}}
        uniq_pass = None
    else:
        ucmd = ["/tmp/venv/bin/python", str(ROOT / "scripts" / "uniqueness_check.py"),
                "--ours", str(primary), "--registry", args.registry,
                "--footprint", str(dd / "sample_submission.tif"), "--out", str(uniq_path)]
        uproc = subprocess.run(ucmd, capture_output=True, text=True)
        (ROOT / "evidence" / "uniqueness_check_stdout.txt").write_text(uproc.stdout + uproc.stderr)
        try:
            uniq = json.loads(uniq_path.read_text())
            uniq_pass = bool(uniq["operative_gate"]["passed"])
        except (OSError, KeyError, json.JSONDecodeError) as e:
            uniq = {"operative_gate": {"passed": False, "status": f"uniqueness gate ERROR: {e}"},
                    "error": str(uproc.stderr[-2000:])}
            uniq_pass = False

    # ---- holdout evidence ----
    holdout = {"arm": args.arm, "variant": args.variant, "q": args.q,
               "label_type": "HOLDOUT-DTI (proxy, withheld known-fault segments, 5 folds; NOT organizer-scored)"}
    try:
        e6 = json.loads(Path(args.holdout_evidence).read_text())
        holdout["E6_pooled_DTI"] = e6["pooled"][args.variant][str(args.q)]["pooled_DTI"]
        holdout["E6_CI95_t_df4_on_fold_mean"] = e6["pooled"][args.variant][str(args.q)]["CI95_t_df4_on_fold_mean"]
        holdout["E6_per_fold_DTI"] = e6["pooled"][args.variant][str(args.q)]["per_fold_DTI"]
        holdout["E6_withheld_fault_px_total"] = e6["pooled"][args.variant][str(args.q)]["withheld_fault_px_total"]
        holdout["E6_evaluator"] = e6["evaluator"]
        holdout["E6_model_AUC_on_withheld_faults_per_fold"] = [f["model_AUC_on_withheld_faults"] for f in e6["folds"]]
        holdout["E6_reproduction_check_all_identical"] = e6["reproduction_check"].get("all_identical")
    except (OSError, KeyError) as e:
        holdout["E6_note"] = f"holdout evidence not found: {e}"
    try:
        e7 = json.loads(Path(args.h5_evidence).read_text())
        holdout["E7_H5_canary_verdict"] = {k: v["verdict"] for k, v in e7["canary"].items()}
        holdout["E7_H5_paired_diff_at_bands_best_q"] = e7["selection"]["paired_diff_at_bands_best_q"]
        holdout["E7_H5_bands_best_q"] = e7["selection"]["bands_best_q"]
    except (OSError, KeyError):
        pass

    released = bool(in_lane_pass and tmpl_pass and uniq_pass)
    if not released:
        # release control: a file that fails any gate is not offered (the site would not link it, but the
        # direct URL would still serve it) — remove it from docs/downloads and record that
        primary.unlink(missing_ok=True)
    receipt = {
        "submission_name": stem,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "recipe": {
            "model": "HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, "
                     "l2_regularization=1.0, random_state=0)",
            "features": feature_note,
            "arm": args.arm,
            "positives": int(pos_rows.size), "negatives": int(neg_rows.size),
            "known_fault_mask": "emission forced to 0 on known-fault pixels (the target faults are not in the catalogue)",
            "emission_variant": args.variant,
            "q_fraction_of_footprint": args.q,
        },
        "holdout_selection_evidence": holdout,
        "grid": {"H": inp.H, "W": inp.W, "crs": str(inp.crs), "transform": list(inp.transform)[:6],
                 "footprint_px": footprint_px},
        "gates": {
            "in_lane_validator": {"passed": in_lane_pass, "checks": r["checks"], "counts": r["counts"]},
            "shared_template_validator": {"passed": tmpl_pass, "command": " ".join(tmpl_cmd),
                                          "template_repo": "buffedlizard55-lab/GEMSDOE",
                                          "template_commit": TEMPLATE_COMMIT, "log": str(tmpl_log_path)},
            "uniqueness": {"receipt": str(uniq_path), "operative_gate_passed": uniq_pass,
                           "literal_any_drift_flag": uniq.get("literal_gate", {}).get("any_drift_flag"),
                           "n_registry_files": uniq.get("n_registry_files"),
                           "operative_duplicate_files": (uniq.get("operative_gate", {}) or {}).get("operative_duplicate_files"),
                           "max_spearman_rho": (uniq.get("operative_gate", {}) or {}).get("max_spearman_rho_all_files"),
                           "max_lift": (uniq.get("operative_gate", {}) or {}).get("max_lift_all_files"),
                           "operative": uniq.get("operative_gate")},
            "leakage_canary": {
                "features": "19 label-free bands (Exp 1: max single-band separability 0.597, gate 0.90)"
                            + (" + H5 edges (E7 canary)" if args.arm == "bands_h5" else ""),
                "emission_masks_catalogue_pixels": True,
                "on_known_fault_px": r["on_known_fault_px"],
            },
        },
        "released": released,
        "files": {primary.name: {"sha256": r["sha256"], "bytes": r["bytes"], "compression": r["compression"],
                                  "compression_candidates": r["compression_candidates"],
                                  "all_checks_passed": r["all_checks_passed"], "checks": r["checks"],
                                  "counts": r["counts"], "on_known_fault_px": r["on_known_fault_px"],
                                  "bit_exact_roundtrip": r["bit_exact_roundtrip"],
                                  "value_min": r["value_min"], "value_max": r["value_max"],
                                  "nodata_tag": r["nodata_tag"],
                                  "emitted_px": r["emitted_px"],
                                  "emitted_fraction_of_footprint": r["emitted_fraction_of_footprint"],
                                  "path": str(primary.relative_to(ROOT)),
                                  "present_in_repo": primary.exists()}},
        "runtime_s": round(time.time() - t0, 1),
    }
    (ROOT / "evidence" / "candidates" / f"{stem}.receipt.json").write_text(json.dumps(receipt, indent=2))

    # ---- selection record (read by build_site.py / build_run_card.py) ----
    sel = {
        "status": "RELEASED - Validated / OK to submit" if released else "BLOCKED - DO NOT SUBMIT",
        "submission_name": stem,
        "arm": args.arm,
        "variant": args.variant,
        "q": args.q,
        "selection_rule": ("pre-stated: E6 selected the emission variant (bin) and swept the volume; E7 decided "
                           "bands vs bands_h5 by the pre-registered paired acceptance rule (bands kept). Volume "
                           "selection under the release gates: the operative uniqueness gate (mutual-overlap test, "
                           "IR-53-26; volume scan evidence/uniqueness_volume_scan.json) flags q=0.02 (the known "
                           "duplicate 17GEMSDOE F-ensemble-2pct), q=0.05 (12GEMSDOE multiphysics, mutual 0.872/0.882) "
                           "and q=0.10 (two files). Among the gate-passing volumes, the top two by pooled "
                           "HOLDOUT-DTI (q=0.01: 0.0379, q=0.0073: 0.0343) are statistically indistinguishable "
                           "(overlapping 95% CIs), so the tie-break is the larger uniqueness margin (lower weaker-"
                           "direction coverage of the closest count-matched registry pair): q=0.0073 (0.646) over "
                           "q=0.01 (0.674). E8 releases only if every gate passes"),
        "note": args.note,
        "note_chars": len(args.note),
        "verdict": "promote" if released else "negative",
        "verdict_reason": ("All release gates passed: in-lane validator, shared template validator, operative uniqueness "
                           "gate (IR-53-26 interpretation), leakage canary. HOLDOUT-DTI proxy "
                           f"{holdout.get('E6_pooled_DTI')} at q={args.q} ({args.variant}); not an organizer score."
                           if released else
                           "One or more release gates failed; see evidence/candidates receipt."),
        "files": [primary.name],
        "location": f"docs/downloads/{primary.name} (committed; served by GitHub Pages)",
        "organizer_score": None,
        "selection_note": "Promotion to a real competition slot is a separate selector step within the weekly cap (S3 3.4).",
    }
    (ROOT / "evidence" / "selection.json").write_text(json.dumps(sel, indent=2))

    print(json.dumps({"name": stem, "released": released, "in_lane": in_lane_pass, "template": tmpl_pass,
                      "uniqueness": uniq_pass, "bytes": r["bytes"], "sha256": r["sha256"],
                      "emitted_px": r["emitted_px"], "compression": best["tag"]}, indent=2))
    return 0 if released else 1


if __name__ == "__main__":
    sys.exit(main())
