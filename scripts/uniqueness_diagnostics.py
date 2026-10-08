#!/usr/bin/env python3
"""Diagnostics for a uniqueness receipt (NOT a gate). Explains the flags; never changes a label.

For each flagged registry raster: density class, chance coverage (share of the footprint within 3 px of that raster's
dots), chance-corrected lift = overlap / coverage, footprint-only Spearman rho, and the whole-grid rho from the receipt.
Also: the share of the footprint that the densest sparse registry dot-map covers within 3 px (shows when the raw
overlap gate cannot be satisfied by any placement).

Usage: python scripts/uniqueness_diagnostics.py --receipt evidence/uniqueness_gate_<name>.json --registry /tmp/g53/uniq
       --footprint-from /tmp/gems53-data/sample_submission.tif --out evidence/uniqueness_diagnostics_<name>.json
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage, stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from uniqueness_gate import iter_registry  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--final", required=True, help="the shipped raster the receipt describes")
    ap.add_argument("--registry", action="append", required=True)
    ap.add_argument("--footprint-from", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rec = json.loads(Path(args.receipt).read_text())
    rows = {r["file"]: r for r in rec["all_rows"]}
    fp = np.isfinite(rasterio.open(args.footprint_from).read(1))
    final = np.nan_to_num(rasterio.open(args.final).read(1), nan=0.0)
    rng = np.random.default_rng(53)
    idx_fp = rng.choice(np.flatnonzero(fp.ravel()), 300_000, replace=False)
    fp_px = int(fp.sum())
    out_rows = []
    lattice_cov = []
    for name, sha, arr in iter_registry(args.registry, final.shape):
        r = rows.get(name)
        if r is None:
            continue
        rd = arr > 0
        share = float(rd.sum()) / fp_px
        cov = float((ndimage.distance_transform_edt(~rd)[fp] <= 3).mean()) if rd.any() else 0.0
        if share <= 0.25 and rd.any():
            lattice_cov.append((cov, name, int(rd.sum())))
        if r["drift_flag"] or r["overlap_final"] > 0.7:
            with np.errstate(all="ignore"):
                rho_fp = float(stats.spearmanr(final.ravel()[idx_fp], arr.ravel()[idx_fp]).statistic)
            out_rows.append(dict(
                file=name, class_=("dense(>50% nonzero)" if share > 0.5 else "mid(25-50%)" if share > 0.25 else "sparse(<=25%)"),
                reg_dots=int(rd.sum()), share_of_footprint_nonzero=round(share, 4),
                overlap_final=r["overlap_final"], chance_coverage=round(cov, 4),
                lift_over_chance=(round(r["overlap_final"] / cov, 4) if cov > 0 else None),
                rho_whole_grid_receipt=r["rho_final"],
                rho_footprint_only=(None if np.isnan(rho_fp) else round(rho_fp, 6)),
                flag_by_overlap_gt_0p70=bool(r["overlap_final"] > 0.7),
                flag_by_rho_whole_grid_gt_0p90=bool(r["rho_final"] > 0.9),
                flag_by_rho_footprint_only_gt_0p90=bool((not np.isnan(rho_fp)) and rho_fp > 0.9)))
        del arr, rd
    cls = collections.Counter(o["class_"] for o in out_rows)
    sparse = sorted([o for o in out_rows if o["class_"].startswith("sparse")], key=lambda o: -o["overlap_final"])
    top_cov = sorted(lattice_cov, reverse=True)[:3]
    diag = dict(
        receipt=args.receipt, rule_note="diagnostics only; the pre-registered verdict is taken from the receipt",
        flagged_rows_analysed=len(out_rows), flagged_by_class=dict(cls),
        flagged_by_footprint_only_rho=int(sum(o["flag_by_rho_footprint_only_gt_0p90"] for o in out_rows)),
        flagged_by_whole_grid_rho=int(sum(o["flag_by_rho_whole_grid_gt_0p90"] for o in out_rows)),
        flagged_by_overlap=int(sum(o["flag_by_overlap_gt_0p70"] for o in out_rows)),
        sparse_flagged_median_lift=(float(np.median([o["lift_over_chance"] for o in sparse if o["lift_over_chance"]]))
                                    if sparse else None),
        densest_sparse_dot_maps_by_chance_coverage=[dict(file=n, reg_dots=d, chance_coverage=round(c, 4))
                                                    for c, n, d in top_cov],
        raw_overlap_gate_satisfiable_by_any_placement=bool(not any(c > 0.30 for c, _, _ in top_cov) is False),
        note_raw_gate="If a sparse registry dot-map covers more than 99% of the footprint within 3 px, any candidate has "
                      "overlap above 70% against it, so the raw gate cannot be passed. See IR-53-28.",
        sparse_flagged_top=sparse[:10], all_flagged=out_rows,
    )
    # the satisfiability flag is "no" when the densest sparse map covers more than 70% of the footprint
    diag["raw_overlap_gate_satisfiable_by_any_placement"] = bool(not (top_cov and top_cov[0][0] > 0.70))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(diag, indent=1, default=float))
    print(json.dumps({k: v for k, v in diag.items() if k not in ("sparse_flagged_top", "all_flagged")}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
