#!/usr/bin/env python3
"""Write the E3 dot raster as the session's submission GeoTIFF and validate it line by line.

Format (pre-registered D-2, copied from the organizer-accepted GEMSDOE32 H33-2-B2 zeros file, measured in
evidence/h53_lineage_algebra.json): float32, single band, EPSG:32611, 3292x3730, 100 m, sample transform,
nodata UNSET, all pixels finite, dots = 1.0, everything else 0.0 (inside AND outside the footprint).

Writer: the shared template's src/submission_io.write_submission (imported by file path, never copied).
Validation: (1) our explicit checks, (2) the template's scripts/validate_submission.py, (3) the template's
`validate-conformant`. (3) requires NaN outside the footprint and is EXPECTED to report non-conformance for the
all-finite format; the same check is run on the organizer-accepted GEMSDOE32 zeros file as a control.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems53.core import load_template_module  # noqa: E402

CONTROL = "/tmp/gems53-registry/GEMSDOE32__docs__downloads__gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif"


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def explicit_checks(path, sample_path):
    with rasterio.open(sample_path) as s:
        tpl = s.read(1)
        sp = s.profile
    fp = np.isfinite(tpl)
    with rasterio.open(path) as d:
        a = d.read(1)
        prof = d.profile
        res = d.res
    chk = {
        "single_band": prof["count"] == 1,
        "dtype_float32": prof["dtype"] == "float32",
        "crs_epsg_32611": rasterio.crs.CRS.from_user_input(prof["crs"]).to_epsg() == 32611,
        "shape_matches_sample": (prof["height"], prof["width"]) == (sp["height"], sp["width"]),
        "transform_matches_sample": tuple(prof["transform"])[:6] == tuple(sp["transform"])[:6],
        "resolution_100m": tuple(res) == (100.0, 100.0),
        "no_nan_anywhere": int(np.isnan(a).sum()) == 0,
        "no_inf": int(np.isinf(a).sum()) == 0,
        "no_nan_inside_footprint": int(np.isnan(a[fp]).sum()) == 0,
        "values_in_0_1": bool((a >= 0).all() and (a <= 1).all()),
        "outside_footprint_all_zero": bool((a[~fp] == 0).all()),
        "nodata_unset": prof.get("nodata") is None,
    }
    stats = dict(min=float(a.min()), max=float(a.max()), dots=int((a > 0).sum()), unique_values=np.unique(a).tolist()[:5],
                 footprint_px=int(fp.sum()), dots_outside_footprint=int(((a > 0) & ~fp).sum()))
    return chk, stats


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return dict(cmd=" ".join(cmd), exit=p.returncode, stdout_tail=p.stdout[-1500:], stderr_tail=p.stderr[-500:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dots", required=True)
    ap.add_argument("--prefix", required=True, help="e.g. gems53-hwvc-n40000")
    ap.add_argument("--note", required=True)
    ap.add_argument("--status", required=True)
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template-root", default="/tmp/gems-template")
    ap.add_argument("--outdir", default=str(ROOT / "docs" / "submissions"))
    a = ap.parse_args()
    if len(a.note) > 140:
        raise SystemExit(f"note is {len(a.note)} chars (> 140)")
    sample = Path(a.data_dir) / "sample_submission.tif"
    dots = np.load(a.dots).astype(np.float32)
    dots = np.where(dots > 0, 1.0, 0.0).astype(np.float32)
    pix8 = hashlib.sha256(np.ascontiguousarray(dots, dtype="<f4").tobytes()).hexdigest()[:8]
    name = f"{a.prefix}-20261009-{pix8}-zeros"
    out = Path(a.outdir) / f"{name}.tif"
    sio = load_template_module("submission_io", a.template_root)
    with rasterio.open(sample) as s:
        prof = sio.clean_profile(s.profile, nodata=None, compress="deflate", tile=256)
    info = sio.write_submission(out, dots, prof, band_description="fault_dots",
                                tags={"name": name, "note": a.note, "status": a.status,
                                      "source": "GEMSDOE53 scripts/h53_write_submission.py"})
    chk, stats = explicit_checks(out, sample)
    tv = run([sys.executable, "scripts/validate_submission.py", "--pred", str(out), "--sample", str(sample),
              "--train", str(Path(a.data_dir) / "training_features.tif")], a.template_root)
    tc = run([sys.executable, "-m", "src.submission_io", "validate-conformant", str(out), "--sample", str(sample)], a.template_root)
    ctrl = {}
    if Path(CONTROL).exists():
        cchk, cstats = explicit_checks(CONTROL, sample)
        ctrl = dict(file=Path(CONTROL).name, user_reported_score=0.2778, explicit_checks=cchk, stats=cstats,
                    template_validate_conformant=run([sys.executable, "-m", "src.submission_io", "validate-conformant",
                                                      CONTROL, "--sample", str(sample)], a.template_root))
    rec = dict(name=name, file=str(out.relative_to(ROOT)), bytes=out.stat().st_size, sha256=sha256_file(out),
               pixel_sha256_8=pix8, note=a.note, note_chars=len(a.note), status=a.status,
               writer=dict(template_module="src/submission_io.py write_submission", info=info),
               explicit_checks=chk, explicit_all_pass=all(chk.values()), stats=stats,
               template_validate_submission=tv, template_validate_conformant=tc,
               control_organizer_accepted_zeros_file=ctrl)
    rp = ROOT / "evidence" / f"h53_submission_{name}.json"
    rp.write_text(json.dumps(rec, indent=2, default=str))
    print(json.dumps({k: rec[k] for k in ("name", "file", "bytes", "sha256", "explicit_all_pass", "stats")}, indent=1, default=str))
    print("template validate_submission exit", tv["exit"], "| validate-conformant exit", tc["exit"],
          "| control conformant exit", ctrl.get("template_validate_conformant", {}).get("exit"))


if __name__ == "__main__":
    main()
