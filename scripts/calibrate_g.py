#!/usr/bin/env python3
"""Estimate |G| -- the number of hidden public-test truth pixels -- from our own scored history.

Input: the 13 rasters in ``data/scored`` + ``data/reference`` whose scores this laboratory reported,
and whose byte counts and SHA-256s ``scripts/restore_data.py`` verified against
``registry/data_manifest.json``.  Output: ``evidence/h55_g_calibration.json``.

The estimator is the metric itself, inverted.  For a *sparse* emission (every emitted pixel
8-isolated, so no two pixels compete for the same truth pixel and ``M == T``) the published DTI
collapses to

    DTI = T / (0.2*S + 0.8*|G|)                                    (1)

which has exactly one unknown.  Solving (1) for ``T`` and imposing ``T <= |G|`` gives the bound

    |G| >= 0.2*DTI*S / (1 - 0.8*DTI)                               (2)

per submission, and the maximum over submissions is the binding lower bound.  Rows whose emission is
*not* sparse (they contain multi-pixel components, so ``M > T``) are reported separately: for them
(1) over-estimates ``T``, so their bound is still valid but slack, and they are excluded from the
point estimate.

The score values themselves are **owner-reported, not organiser-authenticated** -- the public board
publishes a number and a username, never a filename, a hash or an upload receipt (IR-52-011).  That
caveat is written into the output file, not just into this docstring.

Usage::

    python3 scripts/calibrate_g.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems55 import calib                      # noqa: E402
from gems52 import metric as M                # noqa: E402

# name -> (path relative to ROOT, owner-reported public-leaderboard DW-Tversky)
# Every pairing below is the one this laboratory published on its own GitHub Pages sites; the
# site URL that reported it is kept next to it so a human can re-check the mapping by hand.
SCORED = [
    ("h33-2-b2", "data/reference/h33-2-b2-zeros.tif", 0.2778,
     "https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html"),
    ("h25-1-dotted-d2-8", "data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
     0.2600, "https://buffedlizard55-lab.github.io/GEMSDOE25/"),
    ("h25-1-dotted-d1-5", "data/scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
     0.2477, "https://buffedlizard55-lab.github.io/GEMSDOE24/"),
    ("tgc-v2-on-d1-5", "data/scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
     0.2449, "https://buffedlizard55-lab.github.io/GEMSDOE27/"),
    ("h19-5-powerlaw", "data/scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
     0.1922, "https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html"),
    ("h19-4-multiline", "data/scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
     0.1894, "https://buffedlizard55-lab.github.io/19GEMSDOE/docs/index.html"),
    ("h16-1-topo-geophys", "data/scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
     0.1855, "https://buffedlizard55-lab.github.io/16GEMSDOE/docs/index.html"),
    ("h28-dotted-ridge", "data/scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
     0.1839, "https://buffedlizard55-lab.github.io/GEMSDOE10/"),
    ("hedge-v2", "data/scored/8GEMSDOE_Hedge-v2_submission.tif", 0.1563,
     "https://buffedlizard55-lab.github.io/8GEMSDOE/"),
    ("ens12-adopted", "data/scored/gemsdoe-ens12-adopted-7f00890a.tif", 0.1563,
     "https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html"),
    ("h25-ctx-ridge", "data/scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
     0.1280, "https://buffedlizard55-lab.github.io/GEMSDOE10/"),
    ("r13-lattice-s5", "data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif", 0.0904,
     "https://buffedlizard55-lab.github.io/13GEMSDOE/"),
    ("placeholder-2314b599", "data/scored/gemsdoe9-PLACEHOLDER-2314b599.tif", 0.0107,
     "https://buffedlizard55-lab.github.io/GEMSDOE9/docs/index.html"),
]


def main() -> int:
    with rasterio.open(ROOT / "data/labels.tif") as src:
        lab = src.read(1)
    foot = lab >= 0
    cat = lab == 1
    rows = []
    for name, rel, dti, url in SCORED:
        p = ROOT / rel
        if not p.exists():
            print(f"MISSING {p} -- run scripts/restore_data.py first", file=sys.stderr)
            return 2
        with rasterio.open(p) as src:
            a = np.nan_to_num(src.read(1).astype(np.float64), nan=0.0)
        em = a > 0
        g = calib.geometry(em, foot)
        lb = calib.lower_bound_n_g(dti, g["S"])
        rows.append(dict(name=name, path=rel, source=url, dti=dti, S=g["S"], A=round(g["A"], 1),
                         A_per_S=round(g["A_per_S"], 4),
                         spacing_efficiency=round(g["spacing_efficiency"], 4),
                         n_components=g["n_components"], max_component=g["max_component"],
                         isolated=g["isolated"], on_catalogue=int((em & cat).sum()),
                         outside_footprint=int((em & ~foot).sum()),
                         n_g_lower_bound=round(lb, 1)))
        print(f"{name:22s} S={g['S']:7d} DTI={dti:.4f} A/S={g['A_per_S']:6.3f} "
              f"eff={g['spacing_efficiency']:6.4f} maxcomp={g['max_component']:6d} "
              f"|G|>={lb:8.0f}")
    sparse = [r for r in rows if r["isolated"]]
    dense = [r for r in rows if not r["isolated"]]
    lb_sparse = max((r["n_g_lower_bound"] for r in sparse), default=float("nan"))
    lb_all = max(r["n_g_lower_bound"] for r in rows)

    # point estimate: the |G| that makes the *implied per-covered-pixel truth density*
    # rho_A = T/A as close to constant as possible across the sparse rows.  That is the only
    # cross-submission prediction the model actually makes, so it is the only thing worth fitting.
    best = None
    for n_g in np.arange(max(1000.0, np.ceil(lb_all)), 30001.0, 100.0):
        t = np.array([r["dti"] * (0.2 * r["S"] + 0.8 * n_g) for r in sparse])
        if (t > n_g).any() or (t > np.array([r["S"] for r in sparse])).any():
            continue
        rho = t / np.array([r["A"] for r in sparse])
        spread = float(np.std(rho) / np.mean(rho))
        if best is None or spread < best["rho_spread"]:
            best = dict(n_g=float(n_g), rho_spread=spread,
                        T={r["name"]: float(tt) for r, tt in zip(sparse, t)},
                        rho_A={r["name"]: float(x) for r, x in zip(sparse, rho)},
                        T_over_n_g={r["name"]: float(tt / n_g) for r, tt in zip(sparse, t)})
    payload = dict(
        method="inversion of DTI = T/(0.2*S - 0.2*M + 0.2*T + 0.8*|G|) in the sparse regime M == T",
        metric_source="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric",
        kernel_disc_weight_sum=calib.DISC_WEIGHT_SUM,
        footprint_px=int(foot.sum()), catalogue_px=int(cat.sum()),
        caveat=("scores are owner-reported from this laboratory's own GitHub Pages sites, not "
                "organiser-authenticated: the public board publishes no filename, hash or upload "
                "receipt (IR-52-011).  Raster bytes are SHA-256-verified against "
                "registry/data_manifest.json, so S, A and the geometry are exact; only DTI is "
                "second-hand."),
        n_rows=len(rows), n_sparse=len(sparse), n_contiguous=len(dense),
        n_g_lower_bound_sparse=round(lb_sparse, 1),
        n_g_lower_bound_all=round(lb_all, 1),
        binding_row_sparse=max(sparse, key=lambda r: r["n_g_lower_bound"])["name"] if sparse else None,
        binding_row_all=max(rows, key=lambda r: r["n_g_lower_bound"])["name"],
        n_g_point_estimate=(best or {}).get("n_g"),
        rho_A_spread_at_estimate=(best or {}).get("rho_spread"),
        implied_T=(best or {}).get("T"),
        implied_rho_A=(best or {}).get("rho_A"),
        implied_T_over_n_g=(best or {}).get("T_over_n_g"),
        rows=rows)
    out = ROOT / "evidence" / "h55_g_calibration.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"\nsparse rows: {len(sparse)}  contiguous rows: {len(dense)}")
    print(f"|G| >= {lb_sparse:.0f} (sparse rows)   |G| >= {lb_all:.0f} (all rows)")
    print(f"binding row: {payload['binding_row_all']}")
    if best:
        print(f"|G| point estimate {best['n_g']:.0f}  (rho_A spread {best['rho_spread']:.3f})")
        for k, v in best["rho_A"].items():
            print(f"   {k:22s} T={best['T'][k]:8.1f}  T/|G|={best['T_over_n_g'][k]:.4f}  "
                  f"rho_A={v:.5f}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
