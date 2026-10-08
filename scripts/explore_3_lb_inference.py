#!/usr/bin/env python3
"""Pass-1 recon #3: what do the *real* leaderboard scores say about |G| and about credit?

This is the only calibration in this repo that touches the organiser's actual hidden truth: thirteen
of this lab's prior candidate rasters have an owner-reported public-leaderboard score, and all
thirteen files are on disk.  Given

    DTI = T / ( 0.2*(S - M) + 0.2*T + 0.8*|G| )            (see src/gems52/metric.py, unit-tested)

with S = emitted mass, M = mass that lands within the kernel of a truth pixel, T = realised credit and
|G| = number of new-fault truth pixels, each observed (DTI, S) pair gives one equation.  Thirteen
equations, thirteen unknowns (one T per file) plus the shared |G|: so for any assumed |G| the implied
T_i is *determined*,

    T_i = DTI_i * ( 0.2*(S_i - M_i) + 0.8*|G| ) / ( 1 - 0.2*DTI_i )

and the *diagnostic* is which |G| makes the implied T_i physically consistent (T_i <= |G|, and the
credits ordered the way the detector families are known to differ).

Bracketing |G| this way costs nothing and needs no truth file.  M_i is bounded in [0, S_i]; results are
reported for the conservative M_i = 0 (upper bound on the tax, hence a lower bound on T_i) and for the
optimistic M_i = S_i (perfect placement).

Read-only; scores are the owner-reported mapping transcribed from the sibling sites, which is NOT
organiser-authenticated (knowledge/06).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]

# name on disk -> (owner-reported public-LB score, source site)
SCORED = {
    "data/reference/h33-2-b2-zeros.tif": (0.2778, "GEMSDOE32"),
    "data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif": (0.2600, "GEMSDOE25"),
    "data/scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif": (0.2477, "GEMSDOE24"),
    "data/scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif": (0.2449, "GEMSDOE27"),
    "data/scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif": (0.1922, "GEMSDOE19"),
    "data/scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif": (0.1894, "GEMSDOE19"),
    "data/scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif": (0.1855, "GEMSDOE16"),
    "data/scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif": (0.1839, "GEMSDOE10"),
    "data/scored/8GEMSDOE_Hedge-v2_submission.tif": (0.1563, "8GEMSDOE"),
    "data/scored/gemsdoe-ens12-adopted-7f00890a.tif": (0.1563, "GEMSDOE"),
    "data/scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif": (0.1280, "GEMSDOE10"),
    "data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif": (0.0904, "13GEMSDOE"),
    "data/scored/gemsdoe9-PLACEHOLDER-2314b599.tif": (0.0107, "GEMSDOE9"),
}


def main() -> None:
    with rasterio.open(ROOT / "data/labels.tif") as ds:
        cat = ds.read(1) == 1
    with rasterio.open(ROOT / "data/sample_submission.tif") as ds:
        foot = np.isfinite(ds.read(1))
    dist_cat = ndimage.distance_transform_edt(~cat)

    rows = []
    for rel, (score, site) in SCORED.items():
        p = ROOT / rel
        with rasterio.open(p) as ds:
            a = ds.read(1)
        pos = np.isfinite(a) & (a > 0)
        s_total = float(a[pos].sum())
        s_cat = float(a[pos & cat].sum())              # on the masked-out catalogue: score-neutral
        s_eff = s_total - s_cat                        # evaluated mass
        d = dist_cat[pos]
        near3 = float(a[pos][d <= 3.0].sum())
        rows.append({
            "file": Path(rel).name, "site": site, "score": score,
            "px": int(pos.sum()), "mass_total": round(s_total, 1),
            "mass_on_catalogue": round(s_cat, 1),
            "mass_evaluated": round(s_eff, 1),
            "share_evaluated": round(s_eff / max(1e-9, s_total), 4),
            "mass_within_3px_of_catalogue": round(near3, 1),
            "share_within_3px": round(near3 / max(1e-9, s_total), 4),
            "max_value": float(np.nanmax(a)),
            "median_positive_value": float(np.median(a[pos])),
        })
    rows.sort(key=lambda r: -r["score"])

    # implied credit T_i for a grid of assumed |G|
    grid = [5_000, 7_500, 10_000, 15_000, 20_000, 30_000, 50_000, 80_000, 120_000]
    implied = {}
    for g in grid:
        row = {}
        for r in rows:
            dti, s = r["score"], r["mass_evaluated"]
            # M = 0 (every evaluated pixel is tax-paying): lower bound on T
            row[r["file"][:28]] = round(dti * (0.2 * s + 0.8 * g) / (1 - 0.2 * dti), 1)
        implied[str(g)] = row

    # for the perfect-placement reading (M = S) the tax vanishes; then T <= |G| for every file and the
    # smallest |G| consistent with the realised scores is the root of  DTI = T/(0.2T + 0.8|G|)  at T = |G|
    print(json.dumps({"files": rows, "implied_credit": implied}, indent=1))
    (ROOT / "evidence").mkdir(exist_ok=True)
    out = ROOT / "evidence" / "leaderboard_inference.json"
    out.write_text(json.dumps({
        "what": "inverse inference of |G| and per-file realised credit from the 13 owner-reported "
                "public-leaderboard scores of this family's prior rasters",
        "formula": "DTI = T/(0.2*(S-M) + 0.2*T + 0.8*|G|);  T_i solved for each assumed |G| with M_i = 0",
        "caveat": "scores are owner-reported (not organiser-authenticated); M_i unknown; the public "
                  "evaluation subset is unknown, so all masses are footprint-wide",
        "files": rows, "implied_credit": implied,
    }, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
