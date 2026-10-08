#!/usr/bin/env python3
"""X3 - build the pre-registered candidate GeoTIFF and run the format (G4) and uniqueness (G5) gates.

Everything here is pre-registered in evidence/preregistration_x2.json:
  * label-free ridge score on RTP band 2 (src/gems53/ridge.py, hash pinned in the pre-registration);
  * emission budget N = 44,090 binary dots, Poisson-disk spacing 2.8 px;
  * ALL known faults are masked pixel-exactly (final file: no withheld truth exists);
  * RTP no-data cells are not candidates.

Writer and validators are the TEMPLATE's shared tools (src/submission_io.py, scripts/validate_submission.py,
python -m src.submission_io validate-conformant), not copies. The GeoTIFF is float32, single band, EPSG:32611,
100 m, sample grid, NaN exactly outside the official footprint, finite 0/1 inside, nodata tag 'nan'.

Label rule (pre-registered): OK-TO-SUBMIT only if G1..G5 all pass. Otherwise DO-NOT-SUBMIT, naming the gates.
Writes submissions/<name>.tif, submissions/SUBMISSION_COMMENT.txt (<=140 chars) and evidence/x3_candidate_receipt.json.

Usage: python scripts/x3_build_candidate.py --data-dir /tmp/gems53-data --template /tmp/gems-template \
          --registry /tmp/gems53-registry
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine  # noqa: F401  (kept for explicit type clarity in receipts)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import load_inputs  # noqa: E402  (labels + footprint only; feats are not needed here)
from gems53.ridge import nms_centrelines, ridge_fields, ridge_pack_emission  # noqa: E402
import uniqueness_check as uq  # noqa: E402  (v2 check, same thresholds as the pre-registration)

N_PRIMARY = 44090
R_PX = 2.8
BAND_RTP = 2
MAX_COMMENT = 140


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template", default="/tmp/gems-template")
    ap.add_argument("--registry", default="/tmp/gems53-registry")
    ap.add_argument("--outdir", default=str(ROOT / "submissions"))
    ap.add_argument("--receipt", default=str(ROOT / "evidence" / "x3_candidate_receipt.json"))
    ap.add_argument("--surface-npy", default="/tmp/gems53-build/surface_L.npy")
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    tpl = Path(args.template)
    sample_path = dd / "sample_submission.tif"
    features_path = dd / "training_features.tif"

    with rasterio.open(sample_path) as src:
        sample = src.read(1)
        sprof = src.profile.copy()
        transform, crs, H, W = src.transform, src.crs, src.height, src.width
    fp = np.isfinite(sample)

    inp = load_inputs(str(features_path), str(dd / "labels.tif"), str(sample_path))  # labels + footprint
    cat = inp.cat  # every known fault is visible at submission time, so all are masked
    with rasterio.open(features_path) as src:
        rtp = src.read(BAND_RTP).astype(np.float64)
    rtp[rtp < -1e30] = np.nan
    del inp

    L, th, pol, _det = ridge_fields(rtp, fp)
    centre = nms_centrelines(L, th)
    cand_ok = fp & np.isfinite(rtp) & ~cat
    emis, pack_info = ridge_pack_emission(L, centre, cand_ok, N_PRIMARY, R_PX)
    out = np.where(fp, emis, np.nan).astype(np.float32)
    n_dots = int(np.count_nonzero(out == 1.0))

    # ---- write with the template's shared writer --------------------------------------------------
    sys.path.insert(0, str(tpl / "src"))
    import submission_io as sio  # noqa: E402  (template module, not a copy)

    profile = sio.clean_profile(sprof, height=H, width=W, crs=crs, transform=transform, dtype="float32",
                                compress="lzw", tiled=True, tile=256, nodata=np.nan)
    tmp_path = Path(args.outdir) / "_draft.tif"
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    write_info = sio.write_submission(tmp_path, out, profile, band_description="p(fault) dots, 1.0 = emit",
                                      tags={"method": "H2 ridge-packed n44090 r2.8", "label": "PENDING"})

    # ---- G4: template conformance + template validator --------------------------------------------
    conf = sio.conformance_findings(out, sample)
    v1 = subprocess.run([sys.executable, str(tpl / "scripts" / "validate_submission.py"), "--pred", str(tmp_path),
                         "--sample", str(sample_path), "--train", str(features_path)],
                        capture_output=True, text=True, cwd=str(tpl), timeout=600)
    v2 = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant", str(tmp_path),
                         "--sample", str(sample_path)],
                        capture_output=True, text=True, cwd=str(tpl), timeout=600)
    g4 = bool(conf["conformant"] and v1.returncode == 0 and v2.returncode == 0)

    # ---- G5: uniqueness vs every registry raster (surface pre-placement AND final dots) -----------
    surface = np.where(fp, L, np.nan)
    Path(args.surface_npy).parent.mkdir(parents=True, exist_ok=True)
    np.save(args.surface_npy, surface)
    rec = uq.check(tmp_path, Path(args.registry), fp, surface=surface)
    g5 = bool((not rec["any_drift_flag"]) and rec["n_registry_files_compared"] > 0)

    # ---- gates from the earlier pre-registered experiments ----------------------------------------
    x1 = json.loads((ROOT / "evidence" / "x1_ridge_canary.json").read_text())
    x2 = json.loads((ROOT / "evidence" / "x2_ridge_holdout.json").read_text())
    g1 = bool(x2["gates"]["G1_holdout_best"]["pass"])
    g2 = bool(x2["gates"]["G2_equal_budget"]["pass"])
    g3 = bool(x1["G3_pass"])
    gates = {"G1_holdout_best": g1, "G2_equal_budget": g2, "G3_leakage_canary": g3,
             "G4_format": g4, "G5_uniqueness": g5}
    failing = [k for k, v in gates.items() if not v]
    label = "OK-TO-SUBMIT" if not failing else "DO-NOT-SUBMIT"
    sha_draft = sha256(tmp_path)

    name = f"GEMSDOE53_H2-ridge-packed-n44090__{label}.tif"
    final_path = Path(args.outdir) / name
    comment = (f"H2 ridge-packed 44090 dots (band-2 lineaments). {label}. "
               f"Failing: {','.join(failing) if failing else 'none'}. Not a byte copy of any registry file.")
    comment = comment[:MAX_COMMENT]
    assert len(comment) <= MAX_COMMENT
    tags = {"comment": comment, "method": "H2 ridge centrelines, Poisson 2.8 px, N=44090",
            "label": label, "holdout_proxy_note": "HOLDOUT-DTI only; not organizer-confirmed"}
    write_info = sio.write_submission(final_path, out, profile, band_description="p(fault) dots, 1.0 = emit",
                                      tags=tags)
    tmp_path.unlink()
    (Path(args.outdir) / "SUBMISSION_COMMENT.txt").write_text(comment + "\n")
    # the final file must still pass the template's gates (same bytes as the validated draft, new tags only)
    v3 = subprocess.run([sys.executable, "-m", "src.submission_io", "validate-conformant", str(final_path),
                         "--sample", str(sample_path)], capture_output=True, text=True, cwd=str(tpl), timeout=600)
    rec["ours"] = str(final_path)
    rec["ours_sha256"] = sha256(final_path)
    rec["draft_sha256_before_tags"] = sha_draft

    receipt = {
        "experiment": "X3 build + format (G4) + uniqueness (G5) for the pre-registered ridge candidate",
        "label": label,
        "label_rule": "OK-TO-SUBMIT only if G1..G5 all pass (evidence/preregistration_x2.json)",
        "gates": gates,
        "failing_gates": failing,
        "file": {"path": str(final_path.relative_to(ROOT)), "sha256": sha256(final_path),
                 "bytes": int(final_path.stat().st_size), "dtype": write_info["dtype"],
                 "crs": write_info["crs"], "res": write_info["res"], "width": write_info["width"],
                 "height": write_info["height"],
                 "nodata": "nan" if (write_info["nodata"] is not None and math.isnan(float(write_info["nodata"])))
                 else write_info["nodata"],
                 "finite_px": write_info["finite_px"], "nan_px": write_info["nan_px"],
                 "nonzero_px": write_info["nonzero_px"], "dots": n_dots,
                 "block_shapes": write_info["block_shapes"], "tiled": write_info["tiled"]},
        "comment": comment,
        "comment_chars": len(comment),
        "pack_info": pack_info,
        "conformance_findings": conf,
        "validators": {
            "scripts/validate_submission.py": {"exit": v1.returncode, "tail": v1.stdout[-800:]},
            "src.submission_io validate-conformant (draft)": {"exit": v2.returncode, "tail": v2.stdout[-400:]},
            "src.submission_io validate-conformant (final)": {"exit": v3.returncode, "tail": v3.stdout[-400:]},
        },
        "uniqueness": {k: v for k, v in rec.items() if k != "results"},
        "uniqueness_top10": rec["results"][:10],
        "inputs": {"training_features.tif": sha256(features_path), "labels.tif": sha256(dd / "labels.tif"),
                   "sample_submission.tif": sha256(sample_path),
                   "ridge_module_sha256": sha256(ROOT / "src" / "gems53" / "ridge.py"),
                   "template_commit": "dcbbb19 (scripts/validate_submission.py, src/submission_io.py, src/metrics.py)"},
        "runtime_s": round(time.time() - t0, 1),
    }
    # full uniqueness receipt (all registry rows). Pixels of the draft and final file are identical; only tags differ.
    rec["note"] = ("computed on the draft written before tags were added (identical pixel values); "
                   "the final file's sha256 is in 'ours_sha256'")
    (ROOT / "evidence" / "uniqueness_v2.json").write_text(json.dumps(rec, indent=2, default=str, allow_nan=False))
    Path(args.receipt).parent.mkdir(parents=True, exist_ok=True)
    Path(args.receipt).write_text(json.dumps(receipt, indent=2, default=str))
    print(json.dumps({"label": label, "gates": gates, "failing": failing, "file": str(final_path),
                      "dots": n_dots, "comment_chars": len(comment), "validators": [v1.returncode, v2.returncode,
                      v3.returncode], "uniqueness": {k: receipt["uniqueness"][k] for k in
                      ("n_registry_files_compared", "max_spearman_rho", "max_dot_overlap_within_3px_used",
                       "max_surface_spearman_rho", "max_surface_top_N_within_3px", "any_drift_flag")}}, indent=2,
                     default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
