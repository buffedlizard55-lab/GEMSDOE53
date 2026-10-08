#!/usr/bin/env python3
"""Experiment E3 (pre-registered, docs/research/preregistration-2026-10-08.md, section 6).

1. Decide the candidate from E1 and E2 by the pre-registered rules.
2. Train the final model on ALL known faults (no hold-out) with the same recipe.
3. Write the GeoTIFF with the SHARED template writer (src/submission_io.py) and conform it to the official template.
4. Run the SHARED template validators and in-lane checks on the whole array.
5. Run the uniqueness gate (pre-placement surface and candidates, and final dots) against every unique registry raster.
6. Assign the label by the pre-registered rule and write docs/submissions/CURRENT.json plus evidence receipts.

Usage: python scripts/e3_build_candidate.py --data-dir /tmp/gems53-data --template-root /tmp/gems-template
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

from gems53.core import (  # noqa: E402
    dti,
    load_inputs,
    load_template_module,
    h1_segment_exact_distance,
    thin_emission,
)
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402
from uniqueness_gate import run_gate  # noqa: E402

N_NEG = 300_000
SEED = 53
BASELINE = {"arm": "bands", "variant": "top_q0p02", "q": 0.02}


def parse_variant(name: str):
    kind = name.rsplit("_q", 1)[0]
    q = float(name.rsplit("_q", 1)[1].replace("p", "."))
    return kind, q


def topq_mask(p_full, cand, q, footprint_px):
    vals = p_full[cand]
    n_keep = min(int(round(q * footprint_px)), vals.size)
    out = np.zeros(p_full.shape, dtype=bool)
    if n_keep <= 0:
        return out
    thr_idx = np.argpartition(-vals, n_keep - 1)[:n_keep]
    rr, cc = np.nonzero(cand)
    out[rr[thr_idx], cc[thr_idx]] = True
    return out


def band_desc_for(label: str) -> str:
    return f"fault-presence probability (GEMS53 candidate) - {label}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def pixel_sha256(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr, dtype="<f4").tobytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template-root", default="/tmp/gems-template")
    ap.add_argument("--e1", default=str(ROOT / "evidence" / "e1_h1_thin_holdout.json"),
                    help="design A exploration record (reference only, never used for the decision)")
    ap.add_argument("--e2", default=str(ROOT / "evidence" / "e2_leakfree_holdouts.json"))
    ap.add_argument("--registry", default="/tmp/g53/uniq")
    ap.add_argument("--outdir", default=str(ROOT / "docs" / "submissions"))
    ap.add_argument("--evidence", default=str(ROOT / "evidence"))
    args = ap.parse_args()
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    e1 = json.loads(Path(args.e1).read_text())
    e2 = json.loads(Path(args.e2).read_text())

    # ---- 1. decide the candidate (pre-registered rules) ----
    sp = e2.get("spatial_confirmation", {})
    e2_ran = e2.get("status") == "COMPLETED" and sp.get("status") == "COMPLETED"
    e2_accepted = bool(sp.get("acceptance", {}).get("accepted", False)) if e2_ran else False
    e1_sel = e2.get("segment_selection", {}).get("selected")   # design-B selection (DEV-1)
    if e1_sel is not None and e2_accepted:
        spec = {"arm": e1_sel["arm"], "variant": e1_sel["variant"]}
        decision = "design-B selection (E2 stage 1) confirmed on spatial blocks (E2 stage 2, paired lower bound > 0)"
    else:
        spec = {"arm": BASELINE["arm"], "variant": BASELINE["variant"]}
        if e1_sel is None:
            decision = ("design-B stage 1 selected nothing; the design-B holdout best (bands top-q 0.02) is the "
                        "candidate, labelled research-only")
        else:
            decision = ("design-B stage 1 selected a variant but stage 2 did not accept it; the design-B holdout best "
                        "(bands top-q 0.02) is the candidate, labelled research-only")
    kind, q = parse_variant(spec["variant"])
    spec["q"] = q
    spec["kind"] = kind
    is_selected = bool(e1_sel is not None and spec["arm"] == e1_sel["arm"] and spec["variant"] == e1_sel["variant"])
    print("candidate spec:", spec, "|", decision, flush=True)

    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fp_px = int(inp.fp.sum())
    L, n_seg = ndimage.label(inp.cat, structure=np.ones((3, 3), dtype=int))

    # ---- 2. final model on ALL known faults ----
    if spec["arm"] == "h1":
        h1 = h1_segment_exact_distance(inp.cat, L)
        F_all = np.column_stack([inp.feats, h1[inp.fp]]).astype(np.float32)
        del h1
    else:
        F_all = inp.feats
    rng = np.random.default_rng(SEED)
    pos_rows = inp.fp_idx[inp.cat]
    neg_pool = inp.fp_idx[inp.fp & ~inp.cat]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                           l2_regularization=1.0, random_state=0)
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
        value = "p" if kind == "thin_p" else "bin"
        emis, kept, _ = thin_emission(p_full, cand, q, fp_px, value=value)
        kept = int(kept)
    emis = np.where(inp.fp, emis, 0.0).astype(np.float32)
    print(f"final dots: {kept} (pre-placement candidates {int(pre_mask.sum())})", flush=True)

    # holdout number quoted for the candidate: E2 (spatial block) if it ran, else E1 (segment folds)
    if e2_ran:
        dti_proxy = sp["selected_result"]["pooled_DTI"] if is_selected else sp["baseline"]["pooled_DTI"]
    else:
        dti_proxy = e2["baseline_design_B"]["pooled_DTI"]
    # ---- 3. conform to the official template mask (shared writer), temp file for the file-based validators ----
    tr = load_template_module("submission_io", args.template_root)
    with rasterio.open(dd / "sample_submission.tif") as src:
        sref = src.read(1)
        profile = tr.clean_profile(src.profile.copy(), dtype="float32", nodata=src.nodata)
    field = np.where(inp.fp, emis, np.nan).astype(np.float32)
    conformed, conf = tr.conform_to_template(field, sref)
    pixel_hash = pixel_sha256(np.nan_to_num(conformed, nan=-1.0))
    dots_bin = int(np.count_nonzero(np.nan_to_num(conformed, nan=0.0) > 0))
    date_tag = time.strftime("%Y%m%d", time.gmtime())
    stem = f"gems53-{spec['arm']}-{spec['variant']}-{date_tag}-{pixel_hash[:8]}"
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_tif = outdir / f"{stem}.tif"
    tmp_tif = Path("/tmp/g53/validate_tmp") / f"{stem}.tif"
    tmp_tif.parent.mkdir(parents=True, exist_ok=True)
    tr.write_submission(tmp_tif, conformed, profile, band_description="tmp (validation only)", tags={})

    # ---- 4. validators on the bytes that will be shipped (shared template validator + conformance CLI) ----
    val_results = {}
    v1 = subprocess.run([sys.executable, str(Path(args.template_root) / "scripts" / "validate_submission.py"),
                         "--pred", str(tmp_tif), "--sample", str(dd / "sample_submission.tif"),
                         "--train", str(dd / "training_features.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    val_results["template_validate_submission"] = {"exit": v1.returncode,
                                                   "tail": v1.stdout.strip().splitlines()[-3:]}
    v2 = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant", str(tmp_tif),
                         "--sample", str(dd / "sample_submission.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    val_results["template_validate_conformant"] = {"exit": v2.returncode}
    with rasterio.open(tmp_tif) as s, rasterio.open(dd / "sample_submission.tif") as t:
        arr = s.read(1)
        inlane = {
            "crs_epsg": s.crs.to_epsg(), "crs_ok": s.crs.to_epsg() == 32611,
            "shape_ok": (s.height, s.width) == (t.height, t.width) == (3730, 3292),
            "transform_ok": tuple(s.transform) == tuple(t.transform),
            "res_ok": s.res == (100.0, 100.0), "count_ok": s.count == 1, "dtype": s.dtypes[0],
            "nodata": None if s.nodata is None else str(s.nodata),
            "nodata_ok": bool(s.nodata is not None and np.isnan(s.nodata) and t.nodata is not None and np.isnan(t.nodata)),
            "nan_exact_outside_template": bool(np.array_equal(np.isfinite(arr), np.isfinite(sref))),
            "values_in_0_1_whole_array": bool(np.nanmin(arr) >= 0.0 and np.nanmax(arr) <= 1.0),
            "finite_px": int(np.isfinite(arr).sum()), "nonzero_px": int(np.count_nonzero(np.nan_to_num(arr))),
            "min": float(np.nanmin(arr)), "max": float(np.nanmax(arr)),
        }
    inlane["all_ok"] = bool(inlane["crs_ok"] and inlane["shape_ok"] and inlane["transform_ok"] and inlane["res_ok"]
                            and inlane["count_ok"] and inlane["dtype"] == "float32" and inlane["nodata_ok"]
                            and inlane["nan_exact_outside_template"] and inlane["values_in_0_1_whole_array"]
                            and inlane["nonzero_px"] > 0)
    validators_ok = bool(v1.returncode == 0 and v2.returncode == 0 and inlane["all_ok"])
    print("validators ok:", validators_ok, json.dumps(val_results)[:300], flush=True)

    # ---- 5. uniqueness gate on the same pixels: pre-placement (surface + candidates) and final dots ----
    gate_json = Path(args.evidence) / f"uniqueness_gate_{stem}.json"
    gate = run_gate(None, [args.registry], gate_json, surface=np.where(inp.fp, p_full, 0.0),
                    candidates=pre_mask, footprint=inp.fp, final_array=conformed)
    print("gate any_drift:", gate["any_drift_flag"], "max:", gate["max"], flush=True)

    # ---- 6. label (pre-registered rule) ----
    canary_ok = True
    cd = e2.get("canary_design_B", {})
    canary_detail = {"bands_max_separability": cd.get("bands_max_over_all"), "bands_flag": cd.get("bands_flag"),
                     "h1_max_separability": cd.get("h1_max_separability"), "h1_flag": cd.get("h1_flag"),
                     "background": cd.get("background"), "source": "evidence/e2_leakfree_holdouts.json"}
    canary_ok = cd.get("bands_flag") == "pass"
    if spec["arm"] == "h1":
        canary_ok = canary_ok and cd.get("h1_flag") == "pass"
    holdout_ok = bool(e2_accepted and is_selected)
    uniq_ok = not gate["any_drift_flag"]
    verdict_ok = bool(holdout_ok and validators_ok and uniq_ok and canary_ok)
    label = "Validated / OK to submit" if verdict_ok else "Research-only / DO NOT SUBMIT"
    gates = {
        "holdout_gate_E2_paired_accept": holdout_ok,
        "format_validators_all": validators_ok,
        "uniqueness_no_drift_flag": uniq_ok,
        "canary_clean_for_features_in_model": canary_ok,
    }
    tag_word = "OK TO SUBMIT" if verdict_ok else "RESEARCH-ONLY DO NOT SUBMIT"
    pooled_txt = f"{dti_proxy:.4f}" if dti_proxy is not None else "n/a"
    note = f"{tag_word} | GEMS53 {spec['arm']} {spec['variant']} | proxy DTI {pooled_txt} | not organizer-scored"
    note = note[:140]
    assert len(note) <= 140

    # ---- 7. write the shipped file ONCE with the matching status tag; re-validate those bytes ----
    tags = dict(source="GEMSDOE53 e3_build_candidate.py", name=stem, status=label,
                spec=f"{spec['arm']} {spec['variant']}", pixel_sha256=pixel_hash, note=note)
    info = tr.write_submission(out_tif, conformed, profile, band_description=band_desc_for(label), tags=tags)
    v3 = subprocess.run([sys.executable, str(Path(args.template_root) / "scripts" / "validate_submission.py"),
                         "--pred", str(out_tif), "--sample", str(dd / "sample_submission.tif"),
                         "--train", str(dd / "training_features.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    v4 = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant", str(out_tif),
                         "--sample", str(dd / "sample_submission.tif")],
                        capture_output=True, text=True, cwd=args.template_root)
    final_ok = bool(v3.returncode == 0 and v4.returncode == 0)
    if not final_ok:
        label = "Research-only / DO NOT SUBMIT"
        gates["format_validators_all"] = False
        raise SystemExit("final file failed the template validators: " + v3.stdout[-400:] + v4.stdout[-200:])
    print("wrote", out_tif, info["bytes"], "B sha256", info["sha256"][:16], "| label:", label, flush=True)
    tmp_tif.unlink(missing_ok=True)

    receipt = dict(
        experiment="E3 (pre-registered): candidate build, validation, uniqueness, label",
        started_utc=started, finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        runtime_s=round(time.time() - t0, 1),
        decision=decision, candidate=spec, label=label, gates=gates,
        name=stem, note=note, note_chars=len(note),
        file=str(out_tif.relative_to(ROOT)), bytes=info["bytes"], sha256=info["sha256"],
        pixel_sha256=pixel_hash, finite_px=info["finite_px"], nonzero_px=info["nonzero_px"],
        final_dots=dots_bin, pre_placement_candidates=int(pre_mask.sum()),
        conformance=conf,
        validators={"during_build": val_results, "final_template_validate_submission": {"exit": v3.returncode,
                    "tail": v3.stdout.strip().splitlines()[-3:]}, "final_validate_conformant": {"exit": v4.returncode}},
        inlane=inlane,
        holdout={"evaluator": "gems53.core.dti v1.0.0 (parity with template src/metrics.py in E1)",
                 "design": e2.get("design"),
                 "stage1_selected": e1_sel,
                 "stage1_baseline_design_B": e2.get("baseline_design_B"),
                 "stage2_status": sp.get("status"), "stage2_baseline": sp.get("baseline"),
                 "stage2_selected": sp.get("selected_result"), "stage2_paired_difference": sp.get("paired_difference"),
                 "design_A_reference_not_used": {"file": "evidence/e1_h1_thin_holdout.json",
                                                 "bands_top_q0p02": e1["arms"]["bands"]["top_q0p02"]["pooled_DTI"]},
                 "label_type": "HOLDOUT-DTI (proxy; not organizer-scored)"},
        canary=canary_detail,
        uniqueness={"receipt": str(gate_json.relative_to(ROOT)), "any_drift_flag": gate["any_drift_flag"],
                    "n_registry_unique_on_grid": gate["registry_unique_on_grid"],
                    "max": gate["max"], "top": gate["top_by_overlap_final"][:5]},
        organizer_score=None,
        submitted=False,
    )
    rec_path = Path(args.evidence) / f"candidate_{stem}.json"
    rec_path.write_text(json.dumps(receipt, indent=2, default=str))
    current = dict(name=stem, file=str(out_tif.relative_to(ROOT)), sha256=info["sha256"],
                   pixel_sha256=pixel_hash, label=label, note=note, gates=gates, spec=spec, decision=decision,
                   receipt=str(rec_path.relative_to(ROOT)), organizer_score=None, submitted=False)
    (outdir / "CURRENT.json").write_text(json.dumps(current, indent=2))
    print("LABEL:", label, "| note:", note, "| file:", out_tif.name, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
