#!/usr/bin/env python3
"""S3-C (pre-registration S3, section 6): build the unique S3 candidate file, validate it, run the uniqueness gate, label.

Decision (read from evidence/s3b_h8_holdout.json, pre-registered):
  * if the H8 selected variant beats the current holdout best (verdict.beats_holdout_best), the file is H8 (arm h8);
  * otherwise the file is the E2 design-B frozen control (arm bands, variant top_q0p02). This is the pre-registered
    fallback. It is a control, not a recommended submission, and it is labelled as such.

Everything after the decision follows scripts/e3_build_candidate.py exactly: final model on ALL known faults (same
recipe), the SHARED template writer and conform step, the SHARED template validators, the in-lane checks, the
uniqueness gate against the registry rebuilt on 2026-10-08, and a label rule. The label is OK TO SUBMIT only if
every gate passes. Otherwise it is RESEARCH-ONLY / DO NOT SUBMIT.

Usage: python scripts/s3c_build_candidate.py --registry /tmp/gems53-registry-now
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
from scipy import ndimage
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import load_inputs, load_template_module, thin_emission  # noqa: E402
from gems53.h8 import h8_feature_matrix  # noqa: E402
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402
from e3_build_candidate import parse_variant, pixel_sha256, sha256, topq_mask  # noqa: E402  (shared helpers)
from uniqueness_gate import run_gate  # noqa: E402

N_NEG = 300_000
SEED = 53
E2 = ROOT / "evidence" / "e2_leakfree_holdouts.json"
S3B = ROOT / "evidence" / "s3b_h8_holdout.json"
S3A = ROOT / "evidence" / "s3a_leakage_repro.json"


def hgb():
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                          l2_regularization=1.0, random_state=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template-root", default="/tmp/gems-template")
    ap.add_argument("--registry", default="/tmp/gems53-registry-now")
    ap.add_argument("--outdir", default=str(ROOT / "docs" / "submissions"))
    ap.add_argument("--evidence", default=str(ROOT / "evidence"))
    args = ap.parse_args()
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    s3b = json.loads(S3B.read_text())
    e2 = json.loads(E2.read_text())

    # ---- 1. decision (pre-registered) ----
    beats = bool(s3b.get("verdict", {}).get("beats_holdout_best", False))
    if beats:
        sel = s3b["stage1"]["selected"]
        spec = {"arm": "h8", "variant": sel}
        decision = "H8 selected variant beats the current holdout best (E2 H1 thin_bin_q0p1) on spatial folds"
        spatial_val = s3b["stage2"]["pooled_DTI"]["h8_selected"]
    else:
        spec = {"arm": "bands", "variant": "top_q0p02"}
        decision = ("H8 did not beat the current holdout best (pre-registered negative). The file is the pre-registered "
                    "frozen control (E2 design-B baseline, bands top-q 0.02): a unique control, not a recommendation")
        spatial_val = e2["spatial_confirmation"]["baseline"]["pooled_DTI"]
    kind, q = parse_variant(spec["variant"])
    spec.update(kind=kind, q=q)
    print("candidate spec:", spec, "|", decision, flush=True)

    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fp_px = int(inp.fp.sum())

    # ---- 2. final model on ALL known faults, same recipe as E3 (arm bands or h8) ----
    if spec["arm"] == "h8":
        with rasterio.open(dd / "training_features.tif") as src:
            raw13 = src.read(13)
        h8_fp, _R, _thr = h8_feature_matrix(raw13, inp.fp)
        del raw13
        F_all = np.column_stack([inp.feats, h8_fp]).astype(np.float32)
        del h8_fp
    else:
        F_all = inp.feats
    rng = np.random.default_rng(SEED)
    pos_rows = inp.fp_idx[inp.cat]
    neg_pool = inp.fp_idx[inp.fp & ~inp.cat]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = hgb()
    model.fit(F_all[rows], y)
    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, F_all)
    p_full[inp.cat] = 0.0                       # known faults are not predicted (pixel-exact mask)
    cand = inp.fp & ~inp.cat
    pre_mask = topq_mask(p_full, cand, q, fp_px)
    if kind == "top":
        emis = top_q_emission(p_full, cand, q, fp_px)
        kept = int(np.count_nonzero(emis))
    else:
        emis, kept, _ = thin_emission(p_full, cand, q, fp_px, value="p" if kind == "thin_p" else "bin")
        kept = int(kept)
    emis = np.where(inp.fp, emis, 0.0).astype(np.float32)
    del F_all, model
    print(f"final dots (nonzero): {kept}; pre-placement candidates {int(pre_mask.sum())}", flush=True)

    # ---- 3. conform to the official template mask (shared writer) ----
    tr = load_template_module("submission_io", args.template_root)
    with rasterio.open(dd / "sample_submission.tif") as src:
        sref = src.read(1)
        profile = tr.clean_profile(src.profile.copy(), dtype="float32", nodata=src.nodata)
    field = np.where(inp.fp, emis, np.nan).astype(np.float32)
    conformed, conf = tr.conform_to_template(field, sref)
    pixel_hash = pixel_sha256(np.nan_to_num(conformed, nan=-1.0))
    date_tag = time.strftime("%Y%m%d", time.gmtime())
    stem = f"gems53-s3-{spec['arm']}-{spec['variant']}-{date_tag}-{pixel_hash[:8]}"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_tif = outdir / f"{stem}.tif"
    tmp_tif = Path("/tmp/g53/validate_tmp") / f"{stem}.tif"
    tmp_tif.parent.mkdir(parents=True, exist_ok=True)
    tr.write_submission(tmp_tif, conformed, profile, band_description="tmp (validation only)", tags={})

    # ---- 4. validators on the bytes that will be shipped ----
    v1 = subprocess.run([sys.executable, str(Path(args.template_root) / "scripts" / "validate_submission.py"),
                         "--pred", str(tmp_tif), "--sample", str(dd / "sample_submission.tif"),
                         "--train", str(dd / "training_features.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    v2 = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant", str(tmp_tif),
                         "--sample", str(dd / "sample_submission.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    with rasterio.open(tmp_tif) as s, rasterio.open(dd / "sample_submission.tif") as t:
        arr = s.read(1)
        inlane = {
            "crs_epsg": s.crs.to_epsg(), "crs_ok": s.crs.to_epsg() == 32611,
            "shape_ok": (s.height, s.width) == (t.height, t.width) == (3730, 3292),
            "transform_ok": tuple(s.transform) == tuple(t.transform),
            "res_ok": s.res == (100.0, 100.0), "count_ok": s.count == 1, "dtype": s.dtypes[0],
            "nodata": None if s.nodata is None else str(s.nodata),
            "nodata_ok": bool(s.nodata is not None and np.isnan(s.nodata) and t.nodata is not None and np.isnan(t.nodata)),
            "nan_inside_footprint": int(np.isnan(arr[np.isfinite(sref)]).sum()),
            "finite_outside_template": int(np.isfinite(arr[~np.isfinite(sref)]).sum()),
            "values_in_0_1_whole_array": bool(np.nanmin(arr) >= 0.0 and np.nanmax(arr) <= 1.0),
            "finite_px": int(np.isfinite(arr).sum()), "nonzero_px": int(np.count_nonzero(np.nan_to_num(arr))),
            "min": float(np.nanmin(arr)), "max": float(np.nanmax(arr)),
        }
    inlane["all_ok"] = bool(inlane["crs_ok"] and inlane["shape_ok"] and inlane["transform_ok"] and inlane["res_ok"]
                            and inlane["count_ok"] and inlane["dtype"] == "float32" and inlane["nodata_ok"]
                            and inlane["nan_inside_footprint"] == 0 and inlane["finite_outside_template"] == 0
                            and inlane["values_in_0_1_whole_array"] and inlane["nonzero_px"] > 0)
    validators_ok = bool(v1.returncode == 0 and v2.returncode == 0 and inlane["all_ok"])
    print("validators ok:", validators_ok, "| template validate exit", v1.returncode, "| conformant exit", v2.returncode,
          flush=True)

    # ---- 5. uniqueness gate on the same pixels (pre-placement surface + candidates, and final dots) ----
    gate_json = Path(args.evidence) / f"uniqueness_gate_{stem}.json"
    gate = run_gate(None, [args.registry], gate_json, surface=np.where(inp.fp, p_full, 0.0),
                    candidates=pre_mask, footprint=inp.fp, final_array=conformed)
    print("gate any_drift:", gate["any_drift_flag"], "| n_flagged", gate["n_flagged"], "| max", gate["max"], flush=True)

    # ---- 6. label (pre-registered rule: OK only if every gate passes) ----
    holdout_ok = bool(beats)
    uniq_ok = not gate["any_drift_flag"]
    verdict_ok = bool(holdout_ok and validators_ok and uniq_ok)
    label = "Validated / OK to submit" if verdict_ok else "Research-only / DO NOT SUBMIT"
    gates = {"holdout_beats_current_best": holdout_ok, "format_validators_all": validators_ok,
             "uniqueness_no_drift_flag": uniq_ok}
    tag_word = "OK TO SUBMIT" if verdict_ok else "RESEARCH-ONLY DO NOT SUBMIT"
    note = f"{tag_word} | GEMS53-S3 {spec['arm']} {spec['variant']} | HOLDOUT-DTI spatial {spatial_val:.4f} | not organizer-scored"
    note = note[:140]
    assert len(note) <= 140

    # ---- 7. write the shipped file ONCE, re-validate those bytes ----
    tags = dict(source="GEMSDOE53 s3c_build_candidate.py", name=stem, status=label,
                spec=f"{spec['arm']} {spec['variant']}", pixel_sha256=pixel_hash, note=note)
    info = tr.write_submission(out_tif, conformed, profile,
                               band_description=f"fault-presence probability (GEMS53 S3 {spec['arm']} {spec['variant']}) - {label}",
                               tags=tags)
    v3 = subprocess.run([sys.executable, str(Path(args.template_root) / "scripts" / "validate_submission.py"),
                         "--pred", str(out_tif), "--sample", str(dd / "sample_submission.tif"),
                         "--train", str(dd / "training_features.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    v4 = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant", str(out_tif),
                         "--sample", str(dd / "sample_submission.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    if v3.returncode != 0 or v4.returncode != 0:
        raise SystemExit("final file failed the template validators: " + v3.stdout[-400:] + v4.stdout[-200:])
    tmp_tif.unlink(missing_ok=True)
    print("wrote", out_tif, info["bytes"], "B sha256", info["sha256"], "| label:", label, flush=True)

    receipt = dict(
        experiment="S3-C (pre-registration S3, section 6): candidate build, validation, uniqueness, label",
        started_utc=started, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        runtime_s=round(time.time() - t0, 1), decision=decision, candidate=spec, label=label, gates=gates,
        name=stem, note=note, note_chars=len(note), file=str(out_tif.relative_to(ROOT)), bytes=info["bytes"],
        sha256=info["sha256"], pixel_sha256=pixel_hash, finite_px=info["finite_px"], nonzero_px=info["nonzero_px"],
        final_dots=kept, pre_placement_candidates=int(pre_mask.sum()), conformance=conf,
        validators={"template_validate_submission": {"exit": v1.returncode,
                                                     "tail": v1.stdout.strip().splitlines()[-3:]},
                    "validate_conformant": {"exit": v2.returncode},
                    "final_template_validate_submission": {"exit": v3.returncode,
                                                           "tail": v3.stdout.strip().splitlines()[-3:]},
                    "final_validate_conformant": {"exit": v4.returncode}},
        inlane=inlane,
        holdout={"evaluator": "gems53.core.dti v1.0.0", "label_type": "HOLDOUT-DTI (proxy; not organizer-scored)",
                 "s3b_verdict": s3b.get("verdict"), "s3b_stage2_pooled": s3b.get("stage2", {}).get("pooled_DTI"),
                 "s3b_paired_b": s3b.get("stage2", {}).get("b_selected_minus_current_best_H1"),
                 "e2_spatial_baseline": e2["spatial_confirmation"]["baseline"],
                 "e2_segment_baseline": e2["baseline_design_B"]},
        canary={"s3a": str(S3A.relative_to(ROOT)), "s3b_h8": s3b.get("canary_h8_design_B", {}).get("max_separability")},
        uniqueness={"receipt": str(gate_json.relative_to(ROOT)), "registry_dir": args.registry,
                    "registry_unique_on_grid": gate["registry_unique_on_grid"],
                    "any_drift_flag": gate["any_drift_flag"], "n_flagged": gate["n_flagged"],
                    "max": gate["max"], "top": gate["top_by_overlap_final"][:5]},
        organizer_score=None, submitted=False,
    )
    rec_path = Path(args.evidence) / f"candidate_{stem}.json"
    rec_path.write_text(json.dumps(receipt, indent=2, default=str))
    current = dict(name=stem, file=str(out_tif.relative_to(ROOT)), sha256=info["sha256"], pixel_sha256=pixel_hash,
                   label=label, note=note, gates=gates, spec=spec, decision=decision,
                   receipt=str(rec_path.relative_to(ROOT)), organizer_score=None, submitted=False)
    (outdir / "CURRENT.json").write_text(json.dumps(current, indent=2))
    print("LABEL:", label, "| note:", note, "| file:", out_tif.name, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
