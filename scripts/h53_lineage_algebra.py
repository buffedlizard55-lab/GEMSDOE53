#!/usr/bin/env python3
"""Measure the GEMSDOE d2.8 -> r1 -> H33-2-B2 lineage and invert the DTI algebra from USER-REPORTED scores.

Files (registry copies, fetched from the public GEMSDOE* repos by scripts/fetch_registry.py):
  d2.8  GEMSDOE25 gems25-dotted-h19-5-d2-8-...-zeros.tif           USER-REPORTED 0.2600
  r1    GEMSDOE28 gems28-h27-4-r1-solo-d2-8-...-allfinite.tif      USER-REPORTED 0.2708 (h27-4-r1-solo-d2-8)
  B2    GEMSDOE32 gemsdoe32-h33-h33-2-b2-...-zeros.tif             USER-REPORTED 0.2778 (public board row extradr19)

Algebra (exact, from the official metric definition, S1): with TP_w + FN_w = |G|,
    1/DTI = 0.2 + (0.2*FP_w + 0.8*|G|)/TP_w
If a step removes n dots that all have zero kernel weight to truth (pure FP: each contributes exactly 1 to FP_w)
and leaves TP_w unchanged, then  Delta(1/DTI) = 0.2*n_eff/TP_w,  so TP_w = 0.2*n_eff/Delta(1/DTI), where n_eff is
the number of removed dots inside the PUBLIC test chunks (unknown; n_eff = f*n with f = public share). Everything
derived below is therefore expressed per unit f and labelled INFERENCE (not a measurement, not an organizer number).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

REG = Path("/tmp/gems53-registry")
F = {
    "d2.8": ("GEMSDOE25__docs__downloads__gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif", 0.2600),
    "r1": ("GEMSDOE28__docs__downloads__gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif", 0.2708),
    "B2": ("GEMSDOE32__docs__downloads__gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif", 0.2778),
}
ROOT = Path(__file__).resolve().parents[1]


def main():
    lab = rasterio.open("/tmp/gems53-data/labels.tif").read(1)
    fp = lab >= 0
    cat = lab == 1
    dcat = ndimage.distance_transform_edt(~cat)
    dots, out = {}, {"label": "MEASURED geometry + INFERENCE algebra from USER-REPORTED scores", "files": {}}
    for k, (fn, s) in F.items():
        with rasterio.open(REG / fn) as src:
            a = src.read(1)
            prof = dict(nodata=src.nodata, dtype=src.dtypes[0])
        m = np.nan_to_num(a, nan=0.0) > 0
        dots[k] = m
        dd = dcat[m]


        out["files"][k] = dict(file=fn, user_reported_score=s, dots=int(m.sum()), values=sorted(set(np.unique(a[m]).round(4).tolist()))[:5],
                               nan_px=int(np.isnan(a).sum()), nodata=prof["nodata"],
                               within_1px_catalogue=int((dd <= 1).sum()), within_2px_catalogue=int((dd <= 2).sum()),
                               within_3px_catalogue=int((dd <= 3).sum()), median_dist_catalogue_px=float(np.median(dd)))
    rel = {}
    for x, y in (("r1", "d2.8"), ("B2", "r1"), ("B2", "d2.8")):
        rel[f"{x}_subset_of_{y}"] = bool((dots[x] & ~dots[y]).sum() == 0)
        rel[f"{y}_minus_{x}"] = int((dots[y] & ~dots[x]).sum())
        rel[f"{x}_minus_{y}"] = int((dots[x] & ~dots[y]).sum())
        rem = dots[y] & ~dots[x]
        rel[f"removed_{y}_to_{x}_max_dist_catalogue_px"] = float(dcat[rem].max()) if rem.any() else None
    out["set_relations"] = rel
    inv = 1.0 / np.array([F[k][1] for k in ("d2.8", "r1", "B2")])
    steps = []
    for (a_, b_), dinv in zip((("d2.8", "r1"), ("r1", "B2")), -np.diff(inv)):
        n = rel[f"{a_}_minus_{b_}"]
        steps.append(dict(step=f"{a_}->{b_}", removed_dots=n, delta_inv_dti=round(float(dinv), 5),
                          implied_TP_w_per_f=round(0.2 * n / float(dinv), 1)))
    out["inference"] = dict(
        steps=steps,
        note="If the removed dots were pure FP and TP_w unchanged, TP_w = 0.2*n*f/Delta(1/DTI). Two independent steps "
             "giving similar TP_w per f supports (does not prove) the pure-FP reading: dots on/adjacent to the "
             "catalogue earn ~no credit against the expert 'new faults' test set.")
    tp = np.mean([s["implied_TP_w_per_f"] for s in steps])
    dB = F["B2"][1]
    denom = tp * (1 / dB - 0.2)  # = 0.2 FP + 0.8 G (per f)
    out["inference"]["B2_decomposition_per_f"] = dict(TP_w=round(tp, 1), **{"0.2FP_w+0.8G": round(denom, 1)},
        marginal_rule="adding a dot with expected credit c and FP cost f_c raises DTI iff c/f_c > 0.2*DTI/(1-0.2*DTI)",
        marginal_threshold_at_B2=round(0.2 * dB / (1 - 0.2 * dB), 4))
    p = ROOT / "evidence" / "h53_lineage_algebra.json"
    p.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
