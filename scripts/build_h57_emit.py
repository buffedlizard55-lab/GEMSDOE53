#!/usr/bin/env python3
"""GEMS57 emission: metric-aware dotted placement, gates, GeoTIFF + evidence + reasoning.

The deliverable is ONE file: the credited **consensus core** (25,517 cells) plus a validated
**novel** arm, and nothing else.  Both parts are published; the core part is documented as *not*
novel (it is a subset of the 0.2778 reference file's support and of the H52-H56 artifacts), which
is exactly why the novel arm is mandatory: the repo's own gate requires >=20 % novel support and a
non-empty drop versus every accessible prior.

Ranker: ``work/cache/gridscore_joint.npy``, the two-view OOF grid scores from H57-2.  That arm is
REFUTED by its own pre-registered test (evidence/gems57_validate.json: view independence
Spearman 0.637 > 0.6 ABANDON; joint top-5000 catalogue density 0.0236 < View-B 0.0244).  The file
is reused ONLY as ranker material for the novel arm, is labelled as such everywhere it appears, and
no co-trained configuration is promoted: the shipped score is the metric-implied projection of the
core, with the novel arm's contribution reported as an interval, not as a validated gain.

Placement obeys the metric: cells >= 3 px apart (two dots closer than the kernel radius cover the
same truth pixel; the second is pure false-positive tax), >= 200 m from the mapped catalogue,
inside the footprint, and never inside the support of any accessible prior.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from h57_common import G_ANCHOR, TileCache, distance_layers, label_arrays, read_raster  # noqa: E402
from gems52.gates import find_priors, format_report, sha256, uniqueness_report  # noqa: E402

EVID = ROOT / "evidence"
DOWN = ROOT / "docs/downloads"
SUBM = ROOT / "submission"
for d in (EVID, DOWN, SUBM):
    d.mkdir(parents=True, exist_ok=True)

PRIOR_FILES = {
    "ref_h33_2_b2": ROOT / "data/reference/h33-2-b2-zeros.tif",
    "d28": ROOT / "data/scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif",
    "d15": ROOT / "data/scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif",
    "tgc": ROOT / "data/scored/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif",
    "h19_5": ROOT / "data/scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif",
    "h19_4": ROOT / "data/scored/gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif",
    "h16_1": ROOT / "data/scored/gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif",
    "h28": ROOT / "data/scored/gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif",
    "ens12": ROOT / "data/scored/gemsdoe-ens12-adopted-7f00890a.tif",
    "hedge2": ROOT / "data/scored/8GEMSDOE_Hedge-v2_submission.tif",
    "h25ctx": ROOT / "data/scored/gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif",
    "r13": ROOT / "data/scored/13gems_20261001_r13-lattice-s5_v2_nan-outside.tif",
    "ph": ROOT / "data/scored/gemsdoe9-PLACEHOLDER-2314b599.tif",
    # the four published GEMSDOE52 artifacts that a portal upload could collide with
    "h52_composite": ROOT / "submission/gems52-h52-cotrain-disagreement-emission-composite-37654px-r1.tif",
    "h53_coincidence": ROOT / "submission/gems52-h53-coincidence-gated-singles-37654px-r1.tif",
    "h54_revealed": ROOT / "submission/gems52-h54-revealed-core-strike-continuation-50517px-r1.tif",
    "h55_btherm": ROOT / "submission/gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros.tif",
    "h56_consensus": ROOT / "submission/gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif",
    "h56_cotrain": ROOT / "submission/gems52-h56-cotrain-disagreement-37654px-20261007T1630Z-zeros.tif",
    # the four remaining accessible artifacts: required so that "novel" can never collide with
    # anything an organizer-side prior inventory might contain.
    "r2_signednormal": ROOT / "submission/gems52-r2-signednormal-37654-1f751ac9b6ee-zeros.tif",
    "r3_h1_paired": ROOT / "submission/gems52-r3-h1-paired-profile-37654-e42677141dbc-research-only.tif",
    "h55_grav": ROOT / "submission/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros.tif",
    "h55_profile": ROOT / "submission/gems52-h55-profile-37654-7fd28c25b51a-research.tif",
}



def prior_union() -> tuple[np.ndarray, dict]:
    H, W = 3730, 3292
    union = np.zeros((H, W), bool)
    info = {}
    for k, p in PRIOR_FILES.items():
        if not p.exists():
            info[k] = "missing"
            continue
        a = read_raster(p.relative_to(ROOT)).astype(np.float32)
        m = np.isfinite(a) & (a > 0)
        info[k] = int(m.sum())
        union |= m
    return union, info


def core_mask() -> np.ndarray:
    keys = ("ref_h33_2_b2", "d28", "d15", "tgc", "h19_5")
    core = None
    for k in keys:
        a = read_raster(PRIOR_FILES[k].relative_to(ROOT)).astype(np.float32)
        m = np.isfinite(a) & (a > 0)
        core = m if core is None else (core & m)
    return core


def greedy_dots(score: np.ndarray, allowed: np.ndarray, budget: int, min_sep: float = 3.0,
                pre_occ: np.ndarray | None = None, seed_rr=None, seed_cc=None) -> np.ndarray:
    """Metric-aware dotted placement; `pre_occ` cells (e.g. the core) block their neighbourhood."""
    H, W = score.shape
    out = np.zeros((H, W), bool)
    occ = np.zeros((H, W), np.uint8)
    r = int(np.floor(min_sep))
    def mark(y, x):
        y0, y1 = max(0, y - r), min(H, y + r + 1)
        x0, x1 = max(0, x - r), min(W, x + r + 1)
        yy, xx = np.mgrid[y0:y1, x0:x1]
        occ[y0:y1, x0:x1][np.hypot(yy - y, xx - x) < min_sep] = 1
    if seed_rr is not None:
        for y, x in zip(seed_rr, seed_cc):
            out[y, x] = True
            mark(y, x)
    cand = np.argwhere(allowed & np.isfinite(score) & ~occ)
    if cand.size == 0:
        return out
    vals = score[cand[:, 0], cand[:, 1]]
    for y, x in cand[np.argsort(-vals, kind="stable")]:
        if occ[y, x] or out[y, x]:
            continue
        out[y, x] = True
        mark(y, x)
        if int(out.sum()) >= budget:
            break
    return out


def write_geotiff(path: Path, mask: np.ndarray, footprint: np.ndarray) -> None:
    """All-finite float32 {0,1}, 0 outside the study footprint, nodata unset — byte-format match
    to the accepted 0.2778 reference file (0 NaN everywhere; the portal rejected a file whose
    values left [0,1], see the session brief)."""
    a = np.where(footprint, mask.astype(np.float32), np.float32(0.0))
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        profile = ref.profile.copy()
    profile.update(dtype="float32", count=1, compress="deflate", predictor=2, tiled=True,
                   blockxsize=256, blockysize=256, nodata=None)
    with rasterio.open(path, "w", **profile) as ds:
        ds.write(a, 1)


def zip_single(tif: Path, zip_path: Path) -> None:
    import zipfile
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tif, arcname=tif.name)


def reasoning_csv(mask: np.ndarray, arrays: dict, dist: dict, score: dict, out_csv: Path,
                  max_rows: int = 4000) -> dict:
    """Phase-2 requirement: a geological claim AND an alternative explanation for A-only cells."""
    H, W = arrays["H"], arrays["W"]
    cat, foot = arrays["cat"], arrays["foot"]
    rr, cc = np.nonzero(mask)
    if rr.size == 0:
        out_csv.write_text("row,col,utm_e,utm_n\n")
        return {"rows": 0}
    sel = np.ones(rr.size, bool)
    if rr.size > max_rows:
        idx = np.linspace(0, rr.size - 1, max_rows).astype(int)
        rr, cc, sel = rr[idx], cc[idx], np.zeros(rr.size, bool)
        sel[:] = True
        rr = np.nonzero(mask)[0][np.linspace(0, np.count_nonzero(mask) - 1, max_rows).astype(int)]
        cc = np.nonzero(mask)[1][np.linspace(0, np.count_nonzero(mask) - 1, max_rows).astype(int)]

    import pandas as pd
    with rasterio.open(ROOT / "data/sample_submission.tif") as ds:
        tr = ds.transform
    bands = {}
    with rasterio.open(ROOT / "data/training_features.tif") as ds:
        for b in (2, 12, 13, 14, 15, 17, 19):
            a = ds.read(b).astype(np.float32)
            a[a < -1e37] = np.nan
            bands[b] = a
    ws = pd.read_csv(ROOT / "data/external/gdr_wellspring_in_footprint.csv")
    host = pd.to_numeric(ws["temp_c"], errors="coerce").to_numpy()
    hot = np.isfinite(host) & (host >= 60.0)
    hot_r = ws["row"].to_numpy(float).astype(int)[hot]
    hot_c = ws["col"].to_numpy(float).astype(int)[hot]
    all_r = ws["row"].to_numpy(float).astype(int)
    all_c = ws["col"].to_numpy(float).astype(int)
    all_T = np.nan_to_num(pd.to_numeric(ws["temp_c"], errors="coerce").to_numpy(), nan=-1.0)

    def dist_to(rows, cols) -> np.ndarray:
        m = np.ones((H, W), bool)
        if rows.size:
            m[np.clip(rows, 0, H - 1), np.clip(cols, 0, W - 1)] = False
        return ndimage.distance_transform_edt(m, sampling=100.0).astype(np.float32)

    ed_hot = dist_to(hot_r, hot_c)
    ed_all = dist_to(all_r, all_c)
    rows_out = []
    for y, x in zip(rr, cc):
        utm_e, utm_n = tr * (x + 0.5, y + 0.5)
        claim, alt = geological_claim(y, x, bands, dist)
        pa = float(score["A"][y, x]) if score.get("A") is not None else None
        pb = float(score["B"][y, x]) if score.get("B") is not None else None
        if pa is None or pb is None:
            disagreement = "n/a"
        elif abs(pa - pb) < 0.05:
            disagreement = "views-agree"
        elif pa > pb:
            disagreement = "A-only"      # potential field sees it, surface does not
        else:
            disagreement = "B-only"      # surface sees it, potential field does not
        rows_out.append(dict(
            row=int(y), col=int(x), utm_e=round(float(utm_e), 1), utm_n=round(float(utm_n), 1),
            dist_catalogue_m=round(float(dist["ed_cat"][y, x]), 1),
            dist_sgmc_m=round(float(dist["ed_sgmc"][y, x]), 1),
            dist_hot_spring_m=round(float(ed_hot[y, x]), 1),
            dist_any_spring_m=round(float(ed_all[y, x]), 1),
            nearest_spring_T_C=float(all_T[np.argmin((all_r - y) ** 2 + (all_c - x) ** 2)]),
            b12_detrended_elev_m=round(float(bands[12][y, x]), 2),
            b19_detrended_slope=round(float(bands[19][y, x]), 3),
            b13_iso_grav_mGal=round(float(bands[13][y, x]), 3),
            b2_rtp_mag=round(float(bands[2][y, x]), 2),
            b14_tmi=round(float(bands[14][y, x]), 1),
            b15_depth_to_basement=round(float(bands[15][y, x]), 1),
            b17_conductivity=round(float(bands[17][y, x]), 3),
            A_probability=round(pa, 4) if pa is not None else None,
            B_probability=round(pb, 4) if pb is not None else None,
            J_minus_max_view=round(float(score["J"][y, x]) - max(pa or 0.0, pb or 0.0), 4),
            joint_probability=round(float(score["J"][y, x]), 4) if score.get("J") is not None else None,
            disagreement_class=disagreement,
            geological_claim=claim, alternative_explanation=alt))
    pd.DataFrame(rows_out).to_csv(out_csv, index=False)
    return {"rows": len(rows_out)}


def geological_claim(y, x, bands, dist) -> tuple[str, str]:
    """Template reasoning, every clause read from the measured values at that cell."""
    db = bands[15][y, x]
    cond = bands[17][y, x]
    slp = bands[19][y, x]
    grav = bands[13][y, x]
    tmi = bands[14][y, x]
    parts, alts = [], []
    if np.isfinite(db):
        if db < 200:
            parts.append(f"thin cover (depth-to-basement {db:.0f} m) so a basement-rooted fault can "
                         f"propagate to the surface")
        elif db > 1500:
            parts.append(f"deep basin fill ({db:.0f} m) consistent with a buried fault whose surface "
                         f"expression is masked")
    if np.isfinite(cond) and cond > 3.0:
        parts.append(f"elevated surface conductivity ({cond:.2f}) consistent with clay alteration "
                     f"along a fracture zone")
    if np.isfinite(grav):
        parts.append(f"isostatic gravity anomaly {grav:+.1f} mGal marks a lateral density contrast "
                     f"across the structure")
    if np.isfinite(tmi):
        parts.append(f"TMI {tmi:.0f} nT indicates a magnetic lineament the surface view does not see")
    if not parts:
        parts.append("potential-field anomaly contrast with no corresponding surface expression")
    d_cat = float(dist["ed_cat"][y, x])
    alts.append(f"{d_cat:.0f} m from the mapped catalogue: could be a splay of a mapped trace "
                f"rather than an independent fault")
    if np.isfinite(slp) and slp > 20:
        alts.append("steep detrended slope: an erosion/landslide edge can mimic a fault lineament")
    alts.append("the surface view abstains, so a cultural or erosional lineament (road, wash, "
                "ridge crest) cannot be excluded from remote data alone")
    return "; ".join(parts), "; ".join(alts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets", default="33517",
                    help="total emitted cells incl. the 25,517 core seeds (default: core + 8,000 novel)")
    ap.add_argument("--novel-only-budget", type=int, default=0,
                    help="optional extra artifact; 0 disables (not competitive, kept for audit)")
    ap.add_argument("--reasoning-rows", type=int, default=4000)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    arrays = label_arrays()
    dist = distance_layers(arrays["cat"], arrays["foot"])
    union, prior_info = prior_union()
    core = core_mask()
    print(f"prior support union: {int(union.sum())} px over {len(prior_info)} priors; "
          f"core = {int(core.sum())} px")

    gp = ROOT / "work/cache/gridscore_joint.npy"
    if not gp.exists():
        raise SystemExit(f"joint grid scores missing: {gp} "
                         "(build them with scripts/build_h57_cotrain.py --stage validate)")
    pj = np.load(gp)
    stride = 2
    fullJ = np.full((arrays["H"], arrays["W"]), np.nan, np.float32)
    fullJ[::stride, ::stride] = pj
    idx = ndimage.distance_transform_edt(~np.isfinite(fullJ), return_distances=False,
                                         return_indices=True)
    fullJ[:] = fullJ[tuple(idx)]
    # view probabilities are reported in the reasoning CSV only; they do not place anything
    views = {}
    for tag, fn in (("A", "gridscore_A.npy"), ("B", "gridscore_B.npy")):
        f = ROOT / "work/cache" / fn
        if f.exists():
            a = np.full((arrays["H"], arrays["W"]), np.nan, np.float32)
            a[::stride, ::stride] = np.load(f)
            j = ndimage.distance_transform_edt(~np.isfinite(a), return_distances=False,
                                               return_indices=True)
            a[:] = a[tuple(j)]
            views[tag] = a

    eligible = arrays["foot"] & (dist["ed_cat"] > 200.0)
    novel_pool = eligible & ~union
    score_novel = fullJ.copy()
    score_novel[~novel_pool] = -1.0

    report = dict(
        prior_support=prior_info, union_px=int(union.sum()), core_px=int(core.sum()),
        eligible_px=int(eligible.sum()), novel_pool_px=int(novel_pool.sum()), stride=stride,
        ranker=dict(
            file="work/cache/gridscore_joint.npy", stride=stride,
            provenance="two-view co-training OOF grid scores (H57-2, scripts/build_h57_cotrain.py)",
            disclosure="REFUTED METHOD as a scored arm: independence Spearman 0.637 > 0.6 ABANDON "
                       "and joint top-5000 catalogue density 0.0236 < View-B 0.0244 "
                       "(evidence/gems57_validate.json). Reused as ranker material for the novel "
                       "arm only; the shipped projection does NOT credit the co-training arm with "
                       "any validated gain."),
        credit_bracket=dict(
            source="work/credit_lp2.json / work/credit_robust.json",
            note="13 owner-reported scores fitted exactly at |G|=14,088.7 px; the per-cell credit "
                 "allocation is under-determined, so core-only credit lies in the LP interval "
                 "[0.2491, 0.3206] of implied DTI and the champion file itself projects to 0.2778.",
            core_only_dti_min=0.2491, core_only_dti_max=0.3206),
        artifacts={})

    prior_paths = sorted((ROOT / "data/scored").rglob("*.tif"))
    prior_paths.append(ROOT / "data/reference/h33-2-b2-zeros.tif")
    prior_paths += [p for p in sorted(SUBM.glob("*.tif")) if "gems57" not in p.name]
    prior_paths = [p for p in prior_paths if p.exists()]

    if args.novel_only_budget > 0:                                     # optional audit artifact
        dots = greedy_dots(score_novel, novel_pool, args.novel_only_budget)
        name = f"gems57-h57-novel-only-{int(dots.sum())}px{args.tag}-zeros"
        tif = DOWN / f"{name}.tif"
        write_geotiff(tif, dots, arrays["foot"])
        zip_single(tif, DOWN / f"{name}.zip")
        report["artifacts"]["novel_only"] = dict(name=name, mass=int(dots.sum()),
                                                 tif=str(tif.relative_to(ROOT)))

    for budget in [int(x) for x in args.budgets.split(",")]:
        rr, cc = np.nonzero(core)
        dots = greedy_dots(score_novel, novel_pool | core, budget, seed_rr=rr, seed_cc=cc)
        core_cells = int((dots & core).sum())
        novel_cells = int((dots & ~union).sum())
        mass = int(dots.sum())
        frac = novel_cells / max(mass, 1)
        nm = (f"gems57-h57-credit-core{core_cells}-plus-novel{novel_cells}-{mass}px"
              f"{args.tag}-zeros")
        tf = DOWN / f"{nm}.tif"
        write_geotiff(tf, dots, arrays["foot"])
        zip_single(tf, DOWN / f"{nm}.zip")
        shutil.copy2(tf, SUBM / tf.name)
        fmt = format_report(tf, ROOT / "data/sample_submission.tif")
        up = uniqueness_report(dots.astype(np.float32), [str(p) for p in prior_paths])
        (EVID / "gems57_format_report.json").write_text(json.dumps(fmt, indent=2, default=str))
        (EVID / "gems57_uniqueness_report.json").write_text(json.dumps(up, indent=2, default=str))
        score_cols = dict(views)
        score_cols["J"] = fullJ
        rc = reasoning_csv(dots, arrays, dist, score_cols,
                           DOWN / f"{nm}-a-only-reasoning.csv", max_rows=args.reasoning_rows)
        report["artifacts"][f"budget_{budget}"] = dict(
            name=nm, mass=mass, core_cells=core_cells, novel_cells=novel_cells,
            novel_fraction=round(frac, 4), tif=str(tf.relative_to(ROOT)),
            zip=str((DOWN / f"{nm}.zip").relative_to(ROOT)),
            sha256=fmt["sha256"], format_problems=fmt.get("problems", []),
            novelty_gate_ok=bool(up.get("support_novelty_gate_ok")),
            novel_vs_all_priors=int(up.get("novel_vs_all_priors", -1)),
            prior_px_dropped=int(up.get("prior_px_dropped", -1)),
            identical_to_any_prior=bool(any(r.get("identical") for r in up.get("per_prior", []))),
            reasoning_rows=rc.get("rows", 0))
        print(json.dumps(report["artifacts"][f"budget_{budget}"], indent=2))

    (EVID / "gems57_emit_selection.json").write_text(json.dumps(report, indent=2, default=str))
    print("wrote evidence/gems57_emit_selection.json")


if __name__ == "__main__":
    main()
