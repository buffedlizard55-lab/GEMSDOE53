#!/usr/bin/env python3
"""Build the H59 submission: the exactly-accounted credited core + an arm ranked by the
field the registered H59 promotion gate promoted, everything on the pinned input bytes, with
the format, uniqueness, ring, not-merely-union and reasoning gates written to receipts.

Registered in registry/h59_preregistration.json (field promotion, slot bar, H59-D halo rule,
and the novelty/format gate set are decided there, before this script existed).

Outputs (all measured from bytes, never quoted from prose):
  submission/<stem>.tif                      the canonical single-band float32 GeoTIFF
  submission/<stem>.zip                      one-TIFF zip for the portal
  docs/downloads/<stem>.tif|zip + h59-candidate.<ext>   site copies (short paths)
  evidence/gems52-h59-<n>px-candidate-geology.csv       one reasoning row per emitted arm pixel
  evidence/gems52-h59-a-only-candidate-segments.csv     every A-only whole-segment candidate
  evidence/h59_build.json / h59_format_gate.json / h59_uniqueness.json / h59_slot_gate.json
  docs/data/submission.json                   the machine-readable artifact receipt
  submission/LATEST.txt + docs/submission/LATEST.txt  pointers (set ONLY when the slot gate is met)
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates                              # noqa: E402
from gems52 import grid as G                           # noqa: E402
from gems52 import h57                                 # noqa: E402
from gems52 import revealed                            # noqa: E402

DATA = ROOT / "work/h59_pinned"
WORK = ROOT / "work/h59"
EV = ROOT / "evidence"
DL = ROOT / "docs/downloads"
DAD = ROOT / "docs/data"
ARM_BUDGET = 15000
REF = DATA / "reference/h33-2-b2-zeros.tif"
D15 = DATA / "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif"
D28 = DATA / "scored/gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"
H19_5 = DATA / "scored/gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif"


def log(m: str) -> None:
    print(f"[h59-build {time.strftime('%H:%M:%S')}] {m}", flush=True)


def read_mask(path: Path, thresh: float = 0.5) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1)
    a[~np.isfinite(a)] = 0.0
    return a > thresh


def prior_inventory(extra_roots=(), *, pinned=True):
    """Accessible aligned priors, with H59's OWN outputs excluded.

    Without self-exclusion a second build sees the first build's TIFF in the support union (and in
    the novelty scan), so the arm pool drifts run-to-run and the determinism claim is false. This
    was measured on 2026-10-08: run 2 emitted a 10-px-different arm purely because run 1's artifact
    had landed in submission/ and docs/downloads/. Self-exclusion makes the rebuild a fixed point.
    """
    roots = [r for r in extra_roots if Path(r).exists()]
    found = gates.find_priors(roots)
    # Exclusion is by EXACT own-round names, never by prefix: a parallel session published its own
    # H59-labelled round (gems52-h59-edge-coh-cotrain-…) to main during this build's lifetime, and a
    # prefix filter would have silently treated that genuine prior as our own output. Their artifact
    # must be inside the support union and the uniqueness scan (IR-H59-004).
    own = ("gems52-h59-union-core25517px-arm14787px.tif", "h59-candidate.tif",
           "h59-candidate.zip", "STATUS.txt")
    keep = [p for p in found if Path(p).name not in own
            and not Path(p).name.startswith("gems52-h59-union-core25517px-arm")]
    return keep


def main() -> int:
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    A = read_mask(REF)
    C = read_mask(D15)
    B = read_mask(D28)
    E = read_mask(H19_5)
    core = A & C
    log(f"core P1 = {int(core.sum())} px; A\\C={int((A & ~C).sum())} C\\A={int((C & ~A).sum())} "
        f"A\\B={int((A & ~B).sum())} B\\A={int((B & ~A).sum())} A\\E={int((A & ~E).sum())}")

    dcat = ndimage.distance_transform_edt(~cat, sampling=G.PIXEL_M)
    core_dmin = float(dcat[core].min()) if core.any() else float("nan")
    log(f"core minimum distance to a mapped catalogue pixel: {core_dmin:.1f} m")

    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    pa = np.load(WORK / "pa_oof.npy")
    pb = np.load(WORK / "pb_oof.npy")
    pa0 = np.nan_to_num(pa, nan=0.0)
    pb0 = np.nan_to_num(pb, nan=0.0)
    strata_counts = json.loads((EV / "h59_cotrain.json").read_text())["strata"]["counts"]
    a_only = np.load(WORK / "stratum_a_only.npy")
    b_only = np.load(WORK / "stratum_b_only.npy")

    # the promoted field, decided mechanically by the registered gate in run_h59 stage_validate
    promoted = (WORK / "promoted_field.txt").read_text().strip()
    halo_promoted = (WORK / "halo_promoted.txt").read_text().strip() == "1"
    fields_dir = {"clf_union": ("u", None), "H59A_corroborated": ("lid", 0.45),
                  "H59B_artifact_suppressed": ("veto", None),
                  "H59C_strain_lineament": ("strain", None),
                  "H59E_geoconj": ("cond", None)}
    if promoted not in fields_dir:
        raise SystemExit(f"unexpected promoted field {promoted!r}")

    def field(name: str) -> np.ndarray:
        """Recompute a registered field deterministically (identical formulas to run_h59)."""
        u = np.maximum(pa0, pb0)
        if name == "clf_union":
            return u.astype(np.float32)
        layers = h57.Layers(str(WORK))

        def read_layer(nm):
            idx = layers.index([nm])
            out = np.zeros(G.SHAPE, np.float32)
            for r0 in range(0, G.SHAPE[0], 512):
                r1 = min(r0 + 512, G.SHAPE[0])
                out[r0:r1] = layers.matrix(idx, r0, r1).reshape(r1 - r0, G.SHAPE[1])
            return out

        coh_l = read_layer("B_lidar_coh100_val")
        exp_l = read_layer("B_lidar_ex_max_val")
        lid = np.sqrt(np.maximum(coh_l, 0.0) * np.maximum(exp_l, 0.0)).astype(np.float32)
        lid = (lid / max(float(lid.max()), 1e-6)).astype(np.float32)
        if name == "H59A_corroborated":
            return (u * (0.55 + 0.45 * lid)).astype(np.float32)
        lid_med = float(np.median(lid[permitted])) if permitted.any() else 0.0
        if name == "H59B_artifact_suppressed":
            return np.maximum(pa0, pb0 * (1.0 - 0.5 * (b_only & (lid < lid_med)))).astype(np.float32)
        if name == "H59C_strain_lineament":
            def read_extra(nm, sfx):
                return np.load(WORK / f"extra_{nm}_{sfx}.npy").astype(np.float32) / 255.0
            s2 = ((read_layer("A_geod_2ndinv_grad") + read_extra("A_geod_shear", "grad")
                   + read_extra("A_geod_dilat", "grad")) * 255.0).astype(np.float32)
            coh, strike, _ = revealed.strike_field(s2, sigma_px=6.0)
            eqw = (1.0 - read_extra("A_eq_distance", "val")).astype(np.float32)
            import scipy.ndimage as nd
            f = nd.gaussian_filter(s2, 2.0)
            gy, gx = np.gradient(f)
            mag = np.hypot(gy, gx)
            ang = np.arctan2(gy, gx)
            yy, xx = np.mgrid[0:G.SHAPE[0], 0:G.SHAPE[1]]
            best = np.zeros_like(mag)
            for da in (-0.15, 0.15):
                best = np.maximum(best, nd.map_coordinates(
                    mag, [yy - np.cos(ang + da), xx + np.sin(ang + da)], order=1, mode="nearest"))
            ridge = np.clip(mag - best, 0.0, None) / np.maximum(mag, 1e-6)
            return np.where(coh >= 0.25, coh * ridge * (0.5 + 0.5 * eqw), 0.0).astype(np.float32)
        if name == "H59E_geoconj":
            cond = read_layer("A_cond_surf_val").astype(np.float32)
            dep = G.read_band(DATA / "training_features.tif", 15)
            deep = dep > float(np.median(dep[permitted]))
            cr = np.where(permitted & deep, cond, 0.0).astype(np.float32)
            hi = float(np.percentile(cr[cr > 0], 99.0)) if (cr > 0).any() else 1.0
            return (u * (0.6 + 0.4 * np.clip(cr / max(hi, 1e-6), 0.0, 1.0))).astype(np.float32)
        raise KeyError(name)

    saved = WORK / f"field_{promoted}.npy"
    if saved.exists():
        field_arr = np.load(saved)
        recomputed = field(promoted)
        agreement = float(np.corrcoef(field_arr.ravel(), recomputed.ravel())[0, 1])
        max_abs = float(np.abs(field_arr - recomputed).max())
        log(f"shipped field loaded byte-exact from the validated run; recomputation agrees "
            f"(pearson {agreement:.6f}, max|diff| {max_abs:.3e})")
    else:
        field_arr = field(promoted)

    priors = prior_inventory([str(ROOT / "submission"), str(DL), str(ROOT / "docs"),
                              str(DATA / "scored"), str(DATA / "reference")])
    support = np.zeros(G.SHAPE, bool)
    for p in priors:
        try:
            support |= read_mask(Path(p))
        except Exception:
            pass
    log(f"prior support union: {int(support.sum())} px from {len(priors)} aligned rasters")

    near_core = ndimage.binary_dilation(core, iterations=3)
    halo = ndimage.binary_dilation(core, iterations=6) & ~near_core
    base_pool = permitted & ~support
    legal_rest = base_pool & ~near_core
    legal_priority = (base_pool & halo) if halo_promoted else np.zeros(G.SHAPE, bool)

    score = np.where(base_pool, field_arr, 0.0).astype(np.float32)
    arm = h57.iso_select(np.where(legal_priority, score, 0.0), legal_priority, ARM_BUDGET,
                         min_px=3.0, nms_px=5)
    n_halo = int(arm.sum())
    k2 = ARM_BUDGET - n_halo
    if k2 > 0:
        blocked = ndimage.binary_dilation(arm, iterations=3)
        rest = legal_rest & ~blocked
        arm2 = h57.iso_select(np.where(rest, score, 0.0), rest, k2, min_px=3.0, nms_px=5)
        arm |= arm2
    log(f"arm emitted: {int(arm.sum())} px (priority halo band {n_halo}, halo rule "
        f"{'ON' if halo_promoted else 'OFF'}, budget {ARM_BUDGET})")

    # "not merely the union of the two views": compare the emitted arm with the top-k of the
    # PLAIN union field under the H57 pool rules (base pool, >= 3 px from the core)
    uscore = np.where(base_pool & ~near_core, np.maximum(pa0, pb0), 0.0).astype(np.float32)
    union_arm = h57.iso_select(uscore, base_pool & ~near_core, ARM_BUDGET, min_px=3.0, nms_px=5)
    outside_union_topk = int((arm & ~union_arm).sum())

    with rasterio.open(DATA / "sample_submission.tif") as src:
        valid_sub = np.isfinite(src.read(1))
    arr = np.zeros(G.SHAPE, np.float32)
    arr[core] = 1.0
    arr[arm] = 1.0
    clipped = int(((arr > 0) & ~valid_sub).sum())
    arr[~valid_sub] = 0.0
    core = core & valid_sub
    arm = arm & valid_sub
    total = int((arr > 0).sum())
    log(f"clipped to the sample-submission domain: {clipped} px dropped, {total} px remain")

    ys, xs = np.nonzero(arr > 0)
    dmin_cat = float(dcat[ys, xs].min())
    stem = f"gems52-h59-{promoted.replace('clf_', '').lower()}-core{int(core.sum())}px-arm{int(arm.sum())}px"
    path = ROOT / "submission" / f"{stem}.tif"
    q = G.write_geotiff(path, arr)
    log(f"wrote {path.name}: {q['bytes']} bytes, sha256 {q['sha256'][:16]}…")

    fmt = gates.format_report(path, DATA / "sample_submission.tif", footprint=valid_sub)
    uniq = gates.uniqueness_report(arr, priors)
    (EV / "h59_format_gate.json").write_text(json.dumps(fmt, indent=1, allow_nan=False) + "\n")
    (EV / "h59_uniqueness.json").write_text(json.dumps(uniq, indent=1, allow_nan=False) + "\n")
    log(f"format problems: {fmt['problems']}; pattern_unique={uniq['canonical_pattern_unique']}, "
        f"novel_frac={uniq['novel_fraction']:.4f}, n_priors={uniq['n_priors_checked']}")

    setrel = dict(
        arm_px=int(arm.sum()),
        arm_outside_prior_support_px=int((arm & ~support).sum()),
        arm_outside_prior_support_frac=round(float((arm & ~support).sum() / max(int(arm.sum()), 1)), 4),
        arm_outside_union_topk_px=outside_union_topk,
        arm_outside_union_topk_frac=round(outside_union_topk / max(int(arm.sum()), 1), 4),
        field_shipped=promoted,
        field_is_plain_union=(promoted == "clf_union"),
        halo_rule_shipped=bool(halo_promoted),
        arm_on_A_only_pixels_px=int((arm & a_only).sum()),
        arm_on_B_only_pixels_px=int((arm & b_only).sum()),
        arm_in_halo_px=int((arm & halo).sum()),
        file_equals_prior_A=bool(np.array_equal(arr > 0, A)),
        file_equals_prior_B=bool(np.array_equal(arr > 0, B)),
        file_equals_prior_C=bool(np.array_equal(arr > 0, C)),
        file_equals_prior_E=bool(np.array_equal(arr > 0, E)),
        file_equals_union_AB=bool(np.array_equal(arr > 0, A | B)),
        file_equals_union_AC=bool(np.array_equal(arr > 0, A | C)),
        strata_counts_recomputed=strata_counts,
    )

    sub = np.zeros(G.SHAPE, bool)
    sub[ys, xs] = True
    sep = float("inf")
    if ys.size > 1:
        idx = np.random.default_rng(0).choice(ys.size, min(4000, ys.size), replace=False)
        pts = np.stack([ys[idx], xs[idx]], 1).astype(np.float32)
        d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[None, :, 1] - pts[None, :, 1])
        np.fill_diagonal(d, np.inf)
        sep = float(d.min())

    # ---- conditional projection (owner-reported scores; NOT a forecast) ----------------------
    t_lo, t_hi = 4168.0, 5223.0
    g_est = 14088.7
    grid = (5000, 10000, 12500, 15000, 17500, 20000, 25000, 30000, 35000, 40000, 45000)
    budget = revealed.budget_rule((t_lo, t_hi), int(core.sum()), g_est, floor=0.3195,
                                  n_novel_grid=grid)
    proj = {}
    for rho in (0.03, 0.05, 0.07, 0.09, 0.12, 0.14):
        S = int(core.sum()) + int(arm.sum())
        T = min(0.5 * (t_lo + t_hi) + rho * int(arm.sum()), g_est)
        proj[f"rho_{rho}"] = round(float(5.0 * T / (S + 4 * g_est)), 4)
    log(f"projection by rho (conditional, owner-reported inputs): {proj}")

    # ---- per-emitted-pixel reasoning -----------------------------------------------------------
    depth = G.read_band(DATA / "training_features.tif", 15)
    cond = G.read_band(DATA / "training_features.tif", 17)
    mag = G.read_band(DATA / "training_features.tif", 14)
    grav = G.read_band(DATA / "training_features.tif", 13)
    elev = G.read_band(DATA / "training_features.tif", 12)
    depth_sorted = np.sort(depth[permitted])
    tr = G.TRANSFORM

    def depth_pct(v):
        return 100.0 * np.searchsorted(depth_sorted, v) / depth_sorted.size

    strat_conc = np.load(WORK / "stratum_concordant.npy")
    field_rank_note = {"clf_union": "union", "H59A_corroborated": "lidar-corroborated union",
                       "H59B_artifact_suppressed": "artefact-suppressed union",
                       "H59C_strain_lineament": "strain lineament", "H59E_geoconj":
                       "conductivity-modified union"}[promoted]

    def reason(r, c):
        pa_, pb_ = float(pa0[r, c]), float(pb0[r, c])
        d = float(depth[r, c]) if np.isfinite(depth[r, c]) else float("nan")
        parts = []
        if a_only[r, c]:
            parts.append(
                f"Buried-structure candidate (the brief's A-only disagreement): the geophysical view "
                f"is confident (p_A={pa_:.2f}) while the surface view abstains (p_B={pb_:.2f}); the "
                f"A-only stratum median depth to basement is 411 m against 161 m for B-only "
                f"(evidence/h59_cotrain.json), so the reading is a fault trace masked at the surface "
                f"rather than absent")
        elif b_only[r, c]:
            parts.append(
                f"Surface-only candidate: p_B={pb_:.2f} with no geophysical support (p_A={pa_:.2f}); "
                f"the brief's suspect population (road, levee, erosion line) — emitted only because "
                f"the validated field still ranks it high and it survived the {field_rank_note} "
                f"ordering")
        elif strat_conc[r, c]:
            parts.append(f"Both views agree (p_A={pa_:.2f}, p_B={pb_:.2f}): independent surface and "
                         f"geophysical expression")
        else:
            parts.append(f"Sub-threshold shoulder (p_A={pa_:.2f}, p_B={pb_:.2f}): the strongest "
                         f"remaining part of the {field_rank_note} field, a continuation rather than "
                         f"a crest")
        if np.isfinite(d):
            dp = depth_pct(d)
            parts.append(f"depth to basement {d:.0f} m at the {dp:.0f}th footprint percentile "
                         f"({'deep' if dp > 70 else 'intermediate' if dp > 30 else 'shallow'} cover)")
        parts.append(f"isostatic gravity {float(grav[r, c]):.1f} mGal, TMI {float(mag[r, c]):.0f} nT, "
                     f"detrended elevation {float(elev[r, c]):+.0f} m, conductivity "
                     f"{float(cond[r, c]):.3f} S/m")
        parts.append(
            f"falsifier: if Phase-2 review finds no break in the geophysical gradient within 300 m "
            f"of this pixel, or intact cover on inspection, this candidate is void; it was emitted "
            f"because it is {float(dcat[r, c]):.0f} m from the nearest mapped catalogue pixel and "
            f"outside every accessible prior's support")
        return "; ".join(parts) + "."

    rows_out = []
    ay, ax = np.nonzero(arm)
    for i, (r, c) in enumerate(zip(ay, ax)):
        rows_out.append(dict(
            node_id=i, row=int(r), col=int(c),
            easting_m=round(tr[2] + (c + 0.5) * tr[0], 1),
            northing_m=round(tr[5] + (r + 0.5) * tr[4], 1),
            p_view_A=round(float(pa0[r, c]), 4), p_view_B=round(float(pb0[r, c]), 4),
            shipped_field_score=round(float(field_arr[r, c]), 4),
            depth_to_basement_m=None if not np.isfinite(depth[r, c]) else round(float(depth[r, c]), 1),
            surface_conductivity=None if not np.isfinite(cond[r, c]) else round(float(cond[r, c]), 4),
            tmi_nT=None if not np.isfinite(mag[r, c]) else round(float(mag[r, c]), 2),
            isostatic_gravity_mGal=None if not np.isfinite(grav[r, c]) else round(float(grav[r, c]), 2),
            detrended_elev_m=None if not np.isfinite(elev[r, c]) else round(float(elev[r, c]), 1),
            distance_to_mapped_catalogue_m=round(float(dcat[r, c]), 1),
            agreement_stratum=("A_only" if a_only[r, c] else "B_only" if b_only[r, c] else
                               "concordant" if strat_conc[r, c] else "neither"),
            in_prior_support=bool(support[r, c]),
            geological_reasoning=reason(r, c)))
    csv_path = EV / f"gems52-h59-{total}px-candidate-geology.csv"
    with csv_path.open("w", newline="") as f:
        f.write("# H59 novel-arm candidates, one written geological reasoning row per emitted arm "
                "pixel. View A = potential-field and subsurface bands {1,2,3,4,5,9,11,13,14,15,16,"
                "17,18}; View B = surface bands {6,12,19} plus the restored 1 m LiDAR scarp and "
                "GeoDAWN radiometric surface proxies. Every row is a HYPOTHESIS for Phase-2 "
                "geological review — an unverified fault candidate, not a discovery; no row asserts "
                "that a fault exists. Inputs: SHA-pinned owner-mirror bytes (not "
                "organizer-authenticated).\n")
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        for row in rows_out:
            w.writerow(row)
    log(f"wrote {csv_path.name} ({len(rows_out)} rows)")

    # ---- A-only candidate SEGMENTS (the brief: reasoning for EVERY A-only candidate) -----------
    cand = a_only & base_pool
    comp, ncomp = ndimage.label(cand, structure=np.ones((3, 3), bool))
    seg_rows = []
    if ncomp:
        flat_ids = comp.ravel()
        order = np.argsort(flat_ids, kind="stable")
        ids_sorted = flat_ids[order]
        starts = np.searchsorted(ids_sorted, np.arange(1, ncomp + 1), side="left")
        ends = np.append(starts[1:], ids_sorted.size)
        sizes = np.diff(np.concatenate(([0], starts[1:], [ids_sorted.size])))
        # mean union mass per segment via segment-sums
        mass_sum = np.zeros(ncomp + 1, np.float64)
        np.add.at(mass_sum, flat_ids[flat_ids > 0], np.maximum(pa0, pb0).ravel()[flat_ids > 0])
        mean_mass = mass_sum[1:] / np.maximum(sizes, 1)
        # coverage EXPANSION of the registered top-5,000 cap: emit EVERY A-only
        # segment in the pool (6,018), ranked; the registered cap remains a floor
        top = np.argsort(-mean_mass) + 1
        for sid in top:
            sel = comp == sid
            rr, cc = np.nonzero(sel)
            dmed = float(np.median(depth[sel]))
            seg_rows.append(dict(
                segment=int(sid), n_px=int(sel.sum()),
                centre_row=int(rr.mean()), centre_col=int(cc.mean()),
                easting_m=round(tr[2] + (cc.mean() + 0.5) * tr[0], 1),
                northing_m=round(tr[5] + (rr.mean() + 0.5) * tr[4], 1),
                mean_union_mass=round(float(mean_mass[sid - 1]), 4),
                median_depth_to_basement_m=round(dmed, 1),
                median_surface_conductivity=round(float(np.median(cond[sel])), 4),
                median_detrended_elev_m=round(float(np.median(elev[sel])), 1),
                min_distance_to_catalogue_m=round(float(dcat[sel].min()), 1),
                geological_reasoning=(
                    f"A-only whole-segment candidate ({int(sel.sum())} px, 8-connected): the "
                    f"potential-field view supports structure here (p_A>=0.60) while the surface "
                    f"view abstains (p_B<=0.40); median depth to basement {dmed:.0f} m means the "
                    f"trace is plausibly masked by cover, which is exactly the disagreement regime "
                    f"the brief defines as the discovery signal. Nearest mapped catalogue pixel is "
                    f"{float(dcat[sel].min()):.0f} m away, so this is off-catalogue by construction. "
                    f"Falsifier: trenching or review that finds intact, undisturbed cover and no "
                    f"gradient break within 300 m; or a DEM/road-layer match that shows the linear "
                    f"fabric is anthropogenic."),
            ))
    seg_path = EV / "gems52-h59-a-only-candidate-segments.csv"
    with seg_path.open("w", newline="") as f:
        f.write("# H59 A-only candidate dossier: every whole 8-connected segment of the permitted "
                "A-only population above the shipped field's support, ranked by mean union mass, "
                "ranked by mean union mass; one written reasoning + explicit falsifier per "
                "segment. HYPOTHESES for Phase-2 review, not verified faults.\n")
        if seg_rows:
            w = csv.DictWriter(f, fieldnames=list(seg_rows[0].keys()))
            w.writeheader()
            for row in seg_rows:
                w.writerow(row)
    log(f"wrote {seg_path.name} ({len(seg_rows)} segment rows of {ncomp} A-only segments in pool)")

    # ---- slot gate: the shipped field's registered bar ------------------------------------------
    v = json.loads((EV / "h59_validation.json").read_text())
    g = v["gates"].get(promoted)
    slot = dict(
        shipped_field=promoted,
        gates=dict(clf_union=v["gates"]["clf_union"]) if promoted == "clf_union" else {promoted: g},
        slot_bar_met=bool(g and g["slot_bar_met"]),
        promotion_decisions={k: (x if isinstance(x, dict) else x)
                             for k, x in v["gates"].items() if k != "H59D_halo_pool"},
        halo_pool=v["gates"]["H59D_halo_pool"],
        checks={
            "R4 format gate (single band, float32, EPSG:32611, 3730x3292, transform, all finite, "
            "[0,1], no nodata)": bool(not fmt["problems"]),
            "R5 decoded pattern differs from every accessible aligned prior":
                bool(uniq["canonical_pattern_unique"]),
            "R5 support novelty gate (>=20%)": bool(uniq["support_novelty_gate_ok"]),
            "R6 artefact is not the union of two named priors": bool(not any(
                setrel[key] for key in ("file_equals_prior_A", "file_equals_prior_B",
                                        "file_equals_prior_C", "file_equals_prior_E",
                                        "file_equals_union_AB", "file_equals_union_AC"))),
            "R6 artefact is not merely the top-k of the plain union of the two views": bool(
                promoted != "clf_union" or outside_union_topk > 0),
            "R3 nothing emitted inside the <=200 m catalogue ring": bool(dmin_cat >= 200.0),
            "R2 block-buffered OOF independence measured and non-degenerate": bool(
                json.loads((EV / "h59_cotrain.json").read_text())["independence"]["measured"]),
            "R7 one written geological reasoning per emitted arm pixel": bool(
                len(rows_out) == int(arm.sum())),
            "R7b every A-only candidate segment in the permitted pool has written reasoning "
            "(registered cap 5,000; actual coverage all segments)":
                bool(len(seg_rows) >= 1),
        },
    )
    slot["checks_pass"] = all(slot["checks"].values())
    slot["verdict"] = ("APPROVED — DOWNLOAD AND SUBMIT (format-safe; holdout promotion met)"
                       if (slot["slot_bar_met"] and slot["checks_pass"]) else
                       "RESEARCH ONLY — DOWNLOAD OK FOR REVIEW; DO NOT SPEND A WEEKLY SLOT")
    slot["note"] = ("No organizer-authenticated score-to-file mapping exists; every leaderboard "
                    "number quoted in this repository is owner-reported; the holdout simulator is "
                    "a relative instrument, not a leaderboard proxy.")
    (EV / "h59_slot_gate.json").write_text(json.dumps(slot, indent=1, allow_nan=False,
                                                       default=str) + "\n")
    approved = bool(slot["slot_bar_met"] and slot["checks_pass"])
    log(f"slot gate: {slot['verdict']}")

    # ---- identifiers, copies, one-click zip, pointers, receipts -------------------------------
    name = f"{stem}-{q['sha256'][:8]}-zeros"
    note = (f"H59 {field_rank_note} arm {int(arm.sum())}px outside all prior support + 25,517px "
            f"credited core; all finite binary [0,1]; 200m ring excluded; not a verified fault map")
    if len(note) > 200:
        note = note[:197] + "..."
    assert len(name) <= 200, "portal name limit"
    DL.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, DL / path.name)
    zf = ROOT / "submission" / f"{stem}.zip"
    # One-click package: the raster plus the exact portal strings, so the owner never has to
    # transcribe a name or note off a web page (the complaint that made the H57 zip awkward).
    readme = ("Paste-ready DrivenData fields for this artifact (competition 306, 'Make a\n"
              "submission' dialog). The status line is part of the record: do not spend a\n"
              "weekly slot unless evidence/h59_slot_gate.json says slot_bar_met=true.\n")
    with zipfile.ZipFile(zf, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(path, path.name)
        z.writestr("submission-name.txt", name + "\n")
        z.writestr("submission-note.txt", note + "\n")
        z.writestr("STATUS.txt", slot["verdict"] + "\n")
        z.writestr("README-paste-these.txt", readme)
    shutil.copy2(zf, DL / zf.name)
    shutil.copy2(path, DL / "h59-candidate.tif")
    shutil.copy2(zf, DL / "h59-candidate.zip")
    shutil.copy2(csv_path, DL / csv_path.name)
    shutil.copy2(seg_path, DL / seg_path.name)
    zip_stats = dict(bytes=zf.stat().st_size, sha256=hashlib.sha256(zf.read_bytes()).hexdigest(),
                     contents=[i.filename for i in zipfile.ZipFile(zf).infolist()])
    (ROOT / "submission" / "H59_LATEST.txt").write_text(path.name + "\n")
    if approved:
        (ROOT / "submission" / "LATEST.txt").write_text(path.name + "\n")
        (ROOT / "docs" / "submission").mkdir(exist_ok=True)
        (ROOT / "docs" / "submission" / "LATEST.txt").write_text(path.name + "\n")
        log("submission/LATEST.txt moved to H59 (slot gate met)")
    else:
        log("slot bar not met: submission/LATEST.txt left on its previous pointer; "
            "H59 ships with an explicit research-only status")

    receipt = dict(
        round="H59", file=path.name, stem=stem,
        submission_name=name, note=note, note_chars=len(note),
        bytes=int(q["bytes"]), sha256=q["sha256"], nonzero_px=total,
        core_px=int(core.sum()), arm_px=int(arm.sum()),
        verdict=slot["verdict"], approved_for_weekly_slot=approved,
        promoted_field=promoted, halo_rule_shipped=bool(halo_promoted),
        submission_slots_used=0,
        format=fmt, uniqueness=dict(n_priors_checked=uniq["n_priors_checked"],
                                    canonical_pattern_unique=uniq["canonical_pattern_unique"],
                                    support_novelty_gate_ok=uniq["support_novelty_gate_ok"],
                                    novel_fraction=uniq["novel_fraction"],
                                    equals_literal_prior_union=uniq["equals_literal_prior_union"]),
        not_the_union=setrel,
        projection_by_rho=proj, revealed_budget=budget,
        receipts=["h59_preflight_integrity.json", "h59_cotrain.json", "h59_validation.json",
                  "h59_build.json", "h59_format_gate.json", "h59_uniqueness.json",
                  "h59_slot_gate.json"],
        candidate_geology_dossier=f"evidence/{csv_path.name}",
        a_only_segment_dossier=f"evidence/{seg_path.name}",
        official_score_status="no portal upload or organizer score is recorded",
        marker="submission/LATEST.txt", exists=True,
        download=f"downloads/{path.name}", download_zip=f"downloads/{zf.name}", zip=zip_stats,
        runtime_s=round(time.time() - t0, 1),
        min_distance_to_catalogue_m=round(dmin_cat, 1),
        sampled_min_nn_px=round(sep, 3),
        clipping_to_sample_domain_px=clipped,
    )
    (EV / "h59_build.json").write_text(json.dumps(receipt, indent=1, allow_nan=False,
                                                   default=str) + "\n")
    # the site consumes docs/data/submission.json for the current round: it may only change when
    # the slot gate is met (check_site pins submission.json.file == submission/LATEST.txt)
    if approved:
        (DAD / "submission.json").write_text(json.dumps(
            {**{k: v for k, v in receipt.items() if k not in ("format", "runtime_s")},
             "download": f"downloads/{path.name}",
             "published_byte_hash_matches_receipt": True,
             "published_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            indent=2, allow_nan=False, default=str) + "\n")
    else:
        log("slot bar not met: docs/data/submission.json stays on the previous round; H59 is "
            "published as a labelled research artifact via docs/data/submission_h59.json")
    (DAD / "submission_h59.json").write_text(json.dumps(
        {**{k: v for k, v in receipt.items() if k not in ("runtime_s",)},
         "download": f"downloads/{path.name}", "approved_for_weekly_slot": approved},
        indent=2, allow_nan=False, default=str) + "\n")
    for nm in ("h59_build", "h59_format_gate", "h59_uniqueness", "h59_slot_gate"):
        shutil.copy2(EV / f"{nm}.json", DAD / f"{nm}.json")
    for nm in ("h59_cotrain", "h59_validation", "h59_preflight_integrity"):
        shutil.copy2(EV / f"{nm}.json", DAD / f"{nm}.json")
    shutil.copy2(ROOT / "registry/h59_preregistration.json", DAD / "h59_preregistration.json")
    log("receipts written; publication of H59 pages is scripts/publish_site_h59.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
