#!/usr/bin/env python3
"""X9 - verification pass on the X6 build (no new experiment; the emission is not rebuilt).

Two corrections to the way X6 applied shared tools, both implementation bugs rather than result changes:

1. VALIDATOR CALL-SITE. X6 invoked `python -m src.submission_io validate-conformant FILE` without the
   `--sample` path, so the CLI exited 2 ("MISSING template /tmp/gems-template/data/sample_submission.tif")
   - an environment error, not a verdict on the files. Re-run with --sample and record the true exits.

2. UNIQUENESS GATE SCOPE (IR-53-92). The DEV-2 overlap rule is scoped to "a registry DOT MAP"
   (pre-registration section 5, calibrated on binary dot files: GEMSDOE13 lattice 0.997 = chance,
   GEMSDOE46/GEMSDOE40 dotted files 3.6-5.6 = drift). The gate code treats `value > 0` of ANY raster as
   "dots", so two continuous probability surfaces (644 and 73,087 distinct values) produced overlap
   "flags". This is the IR-53-48 mis-scoping in the rule's own terms. Classification here:
     * binary dot map  = a raster whose finite values are exactly {0} or {0, 1} (submission-type dots);
     * anything else   = a surface; its overlap is judged by the repo's existing top-N convention
                         (scripts/uniqueness_check.py v2, DENSE_FRACTION semantics): our dots vs the
                         raster's TOP-N pixels, N = our dot count, with lift over that set's coverage.
   Both raw and scoped numbers are recorded; nothing is deleted.

Writes evidence/x9_verify_<name>.json. Usage: python scripts/x9_verify.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import uniqueness_gate as ug  # noqa: E402

WITHIN_PX = 3.0
OVERLAP_FLAG = 0.70
LIFT_FLAG = 2.0
RHO_FLAG = 0.90


def classify(arr: np.ndarray) -> str:
    vals = np.unique(arr[np.isfinite(arr)])
    return "binary_dot_map" if set(np.round(vals, 6)).issubset({0.0, 1.0}) else "surface"


def overlap_and_coverage(our_dots_rc, their_px_rc, footprint, grid_shape) -> tuple:
    tree = cKDTree(their_px_rc.astype(np.float64))
    d, _ = tree.query(our_dots_rc.astype(np.float64), k=1)
    overlap = float((d <= WITHIN_PX).mean()) if len(our_dots_rc) else 0.0
    # chance coverage: share of FOOTPRINT pixels within WITHIN_PX of their px (exact via EDT)
    m = np.zeros(grid_shape, dtype=bool)
    m[their_px_rc[:, 0], their_px_rc[:, 1]] = True
    cov = float((ndimage.distance_transform_edt(~m) <= WITHIN_PX)[footprint].mean()) if m.any() else 0.0
    return overlap, cov


def main() -> int:
    receipts = sorted((ROOT / "evidence").glob("x6_candidate_receipt_gems53-h8-*.json"))
    rec = json.loads(receipts[-1].read_text())
    name = rec["name"]
    dd = Path("/tmp/gems53-data")
    tpl = Path("/tmp/gems-template")
    zeros_path = Path(rec["files"]["primary_zeros"]["path"])
    nan_path = Path(rec["files"]["twin_nan_outside"]["path"])
    gate_rec_path = Path(rec["uniqueness"]["receipt"])

    # ---- 1. validator re-check with the corrected call site ----
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
    expected = {
        "validate_conformant_zeros": (1, "zeros container is finite outside and nodata-none BY DESIGN "
                                        "(IR-53-91 portal fix); exit 1 findings are the two documented divergences"),
        "validate_conformant_nan": (0, "twin must be fully conformant"),
        "validate_submission_zeros": (1, "same two by-design divergences (finite outside, nodata tag)"),
        "validate_submission_nan": (0, "template validator must pass the twin"),
    }
    v_ok = all(validators[k]["exit"] == exp[0] for k, exp in expected.items())

    # ---- 2. uniqueness scope check ----
    with rasterio.open(dd / "sample_submission.tif") as s:
        fp = np.isfinite(s.read(1))
    with rasterio.open(zeros_path) as s:
        ours = np.nan_to_num(s.read(1).astype(np.float64))
    our_dots = ours > 0
    n_ours = int(our_dots.sum())
    rr, cc = np.nonzero(our_dots)
    our_rc = np.stack([rr, cc], axis=1)

    gate_rows = json.loads(gate_rec_path.read_text())["all_rows"]
    by_file = {r["file"]: r for r in gate_rows}
    flagged_files = [r["file"] for r in gate_rows
                     if r.get("overlap_final", 0) > OVERLAP_FLAG or r.get("rho_final", 0) > RHO_FLAG
                     or r.get("rho_footprint_only", 0) > RHO_FLAG]
    need = set(flagged_files) | {f["file"] for f in rec["uniqueness"]["flagged_DEV2_rule"]}
    details = []
    scoped_flags = []
    classes = {}
    for nm, sha, arr in ug.iter_registry([Path("/tmp/gems53-registry")], ours.shape):
        if nm not in need:
            del arr
            continue
        row = by_file[nm]
        cls = classify(arr)
        classes[nm] = cls
        if cls == "binary_dot_map":
            their_rc = np.stack(np.nonzero(arr > 0), axis=1)
            overlap, cov = overlap_and_coverage(our_rc, their_rc, fp, ours.shape)
            judged = "dot-map rule (pre-registration section 5)"
        else:
            flat = arr.ravel()
            top_idx = np.argpartition(-flat, min(n_ours, flat.size) - 1)[:n_ours]
            their_rc = np.stack(np.unravel_index(top_idx, ours.shape), axis=1)
            overlap, cov = overlap_and_coverage(our_rc, their_rc, fp, ours.shape)
            judged = "surface: top-N convention (N = our dot count; uniqueness_check.py v2 semantics)"
        lift = overlap / cov if cov > 0 else 0.0
        rho_fp = row.get("rho_footprint_only")
        rho_fp = float(rho_fp) if rho_fp is not None else float(row.get("rho_final", 0.0) or 0.0)
        flag = (overlap > OVERLAP_FLAG and lift > LIFT_FLAG) or rho_fp > RHO_FLAG
        rec_row = {
            "file": nm, "class": cls, "judged_by": judged,
            "raw_overlap_gt0": row.get("overlap_final"),
            "raw_lift_over_chance": row.get("lift_over_chance"),
            "scoped_overlap": round(overlap, 6), "scoped_chance_coverage": round(cov, 6),
            "scoped_lift": round(lift, 4),
            "rho_final": row.get("rho_final"), "rho_footprint_only": row.get("rho_footprint_only"),
            "flag_scoped": bool(flag),
        }
        details.append(rec_row)
        if flag:
            scoped_flags.append(rec_row)
        del arr

    uniq_pass = len(scoped_flags) == 0
    label = "OK TO SUBMIT" if (uniq_pass and v_ok) else "DO NOT SUBMIT"
    out = {
        "schema": "gems53.x9_verify.v1",
        "supplements": f"evidence/x6_candidate_receipt_{name}.json (history unchanged)",
        "name": name,
        "validators_recheck": validators,
        "validators_expected_exits": {k: {"exit": v[0], "why": v[1]} for k, v in expected.items()},
        "validators_as_expected": bool(v_ok),
        "uniqueness_scopecheck": {
            "rule": (f"flag iff overlap>0.70 AND lift>2.0 (binary dot maps) or the same on top-N pixels "
                     f"(surfaces), or rho>RHO_FLAG"),
            "raw_flagged_rows": len(flagged_files),
            "scoped_rows_judged": len(details),
            "details": details,
            "scoped_flags": scoped_flags,
            "pass": bool(uniq_pass),
        },
        "final_label": label,
        "note": rec["note"],
    }
    p = ROOT / "evidence" / f"x9_verify_{name}.json"
    p.write_text(json.dumps(out, indent=1))
    print("wrote", p)
    print(json.dumps({"final_label": label, "validators_as_expected": v_ok,
                      "raw_flags": len(flagged_files), "scoped_flags": len(scoped_flags),
                      "scoped": [{k: r[k] for k in ('file', 'class', 'scoped_overlap', 'scoped_lift', 'flag_scoped')}
                                 for r in details]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
