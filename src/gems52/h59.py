"""H59 -- the brief's two-view co-training round on the integrity-pinned mirror.

Registered in ``knowledge/20_hypotheses_H59_preregistered.md`` and
``registry/h59_preregistration.json`` before this module existed.  Nothing here reads a
leaderboard score, a prior prediction raster, or a label-derived distance field.

What is here
------------
``SPEC``             the H59 band inventory: View A completed with the strain/seismicity
                     bands (7, 8, 10) the brief names, View B unchanged from H57.
``build_layers``     thin wrapper over :func:`gems52.h57.build_layers` with the H59 spec.
``fields``           the registered candidate ranking fields (product, vetoB, basestep,
                     seismicity) computed from the OOF view grids and the layer stack.
``strike_coherence`` local structure-tensor strike and coherence for the reasoning dossier.
``write_artifact``   the emission, the GeoTIFF, and every gate re-read from the written bytes.
``reasoning_rows``   one dossier row per emitted pixel; written geological reasoning plus an
                     explicit falsifier for every A-only pixel (the Phase-2 duty).
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

from . import grid as G
from . import h57

# --------------------------------------------------------------------------------------------
# the H59 band inventory (frozen in registry/h59_preregistration.json)
# --------------------------------------------------------------------------------------------
# View A: potential-field and subsurface, per the brief "gravity, magnetics, strain, seismicity".
# Bands 7 (geod_shearrate), 8 (geod_dilaterate) and 10 (deq_n100a15) are new to the co-training
# views; they appeared only as passive rank features in the earlier R2/structural pipelines.
VIEW_A_BANDS = [
    ("data/training_features.tif", 1, "A_mag_anom"),
    ("data/training_features.tif", 2, "A_rtp"),
    ("data/training_features.tif", 3, "A_tmi_hg"),
    ("data/training_features.tif", 4, "A_geod_2ndinv"),
    ("data/training_features.tif", 5, "A_grav_slope"),
    ("data/training_features.tif", 7, "A_geod_shearrate"),
    ("data/training_features.tif", 8, "A_geod_dilaterate"),
    ("data/training_features.tif", 9, "A_tmi_vg"),
    ("data/training_features.tif", 10, "A_deq"),
    ("data/training_features.tif", 11, "A_grav_vg"),
    ("data/training_features.tif", 13, "A_grav_anom"),
    ("data/training_features.tif", 14, "A_tmi"),
    ("data/training_features.tif", 15, "A_depth_to_base"),
    ("data/training_features.tif", 16, "A_ieq"),
    ("data/training_features.tif", 17, "A_cond_surf"),
    ("data/training_features.tif", 18, "A_grav_hg"),
]
# View B: surface -- DEM-derived elevation and slope, the radiometric total-count band that the
# organiser's own tag mislabels but which H53 measured as GeoDAWN TC (IR-52-019), plus the
# external GeoDAWN ratio grids and LiDAR scarp layers.
VIEW_B_BANDS = [
    ("data/training_features.tif", 6, "B_rad_tc"),
    ("data/training_features.tif", 12, "B_det_elev"),
    ("data/training_features.tif", 19, "B_det_elev_slope"),
    ("data/external/geodawn_rad_u8.tif", 4, "B_rad_TC"),
    ("data/external/geodawn_extensions_u8.tif", 1, "B_rad_ThK"),
    ("data/external/geodawn_extensions_u8.tif", 2, "B_rad_UK"),
    ("data/external/geodawn_extensions_u8.tif", 3, "B_rad_UTh"),
    ("data/external/lidar_scarp_features_u8.tif", 1, "B_lidar_ex_max"),
    ("data/external/lidar_scarp_features_u8.tif", 3, "B_lidar_step_max"),
    ("data/external/lidar_scarp_features_u8.tif", 7, "B_lidar_upface_max"),
    ("data/external/lidar_scarp_features_u8.tif", 9, "B_lidar_relief"),
    ("data/external/lidar_scarp_features_u8.tif", 10, "B_lidar_coh100"),
]
SPEC = VIEW_A_BANDS + VIEW_B_BANDS
VIEW_A_LAYERS = [n for _, _, n in VIEW_A_BANDS]
VIEW_B_LAYERS = [n for _, _, n in VIEW_B_BANDS]

Q_CONF = 0.60
Q_ABSTAIN = 0.40
CORRIDOR_PX = h57.CORRIDOR_PX          # <= 200 m ring around a mapped trace: never emitted
NEG_CLEAR_PX = h57.NEG_CLEAR_PX        # labelled negatives >= 500 m clear of the catalogue
SEED = 20261008
BUDGET_PRIMARY = 37_654
BUDGET_SECONDARY = 15_000


def build_layers(work: str = "work/h59", chunk: int = 600,
                 data_dir: str | Path = "data") -> dict:
    """Build (or reuse) the H59 layer stack in ``work`` from ``data_dir``."""
    return h57.build_layers(work=work, chunk=chunk, data_dir=data_dir, spec=SPEC)


def view_indices(layers: h57.Layers) -> tuple[np.ndarray, np.ndarray]:
    idx_a = layers.index([f"{n}_{s}" for n in VIEW_A_LAYERS for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in VIEW_B_LAYERS for s in ("val", "grad", "range")])
    if len(idx_a) != 3 * len(VIEW_A_LAYERS) or len(idx_b) != 3 * len(VIEW_B_LAYERS):
        raise RuntimeError("H59 view specification resolved to a wrong-size feature matrix")
    return idx_a, idx_b


# --------------------------------------------------------------------------------------------
# registered candidate fields
# --------------------------------------------------------------------------------------------
def field_product(pa: np.ndarray, pb: np.ndarray) -> np.ndarray:
    """H59-2: agreement-weighted rank ``p_A * p_B`` (both views must be warm)."""
    return (np.nan_to_num(pa, nan=0.0) * np.nan_to_num(pb, nan=0.0)).astype(np.float32)


def field_veto_b(union: np.ndarray, b_only: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """H59-1: the union field with the B-only (surface-artifact) stratum removed from the pool.

    Returns ``(field, pool_veto)`` -- the ranking values are the union's own; the veto only
    deletes the stratum from the emission pool, exactly as registered.
    """
    field = np.where(b_only, 0.0, np.nan_to_num(union, nan=0.0)).astype(np.float32)
    return field, ~np.asarray(b_only, bool)


def layer_float(layers: h57.Layers, name: str) -> np.ndarray:
    """One cached layer as a full-grid float32 in [0, 1] (rank/255).  Copy, not a view."""
    idx = layers.index([name])
    return np.asarray(layers.mm[idx[0]], dtype=np.float32) / 255.0


def field_basestep(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """H59-3: basement-step buttress field.

    ``rank(grad depth_to_basement) * rank(grad isostatic_gravity)`` restricted to at-or-above
    median modelled cover (band-15 value rank >= 128).  No catalogue, no prior, no label
    distance enters it.  Both inputs are already rank-encoded uint8 layers on the cached stack.
    """
    g15 = layer_float(layers, "A_depth_to_base_grad")
    g13 = layer_float(layers, "A_grav_anom_grad")
    field = (g15 * g13).astype(np.float32)
    del g15, g13
    d15 = layer_float(layers, "A_depth_to_base_val")
    cover = d15 >= 128.0 / 255.0
    del d15
    field[~(valid & cover)] = 0.0
    return field


def field_seismicity(layers: h57.Layers, valid: np.ndarray) -> np.ndarray:
    """H59-4: seismicity-lineament field ``rank(band 16 value) * rank(band 16 gradient)``."""
    v16 = layer_float(layers, "A_ieq_val")
    g16 = layer_float(layers, "A_ieq_grad")
    field = (v16 * g16).astype(np.float32)
    del v16, g16
    field[~valid] = 0.0
    return field


# --------------------------------------------------------------------------------------------
# strike / coherence for the reasoning dossier
# --------------------------------------------------------------------------------------------
def strike_coherence(layers: h57.Layers, valid: np.ndarray,
                      smooth: int = 9) -> tuple[np.ndarray, np.ndarray]:
    """Structure-tensor strike (radians) and coherence from the DEM-detrended-elevation layer.

    Coherence ``(|jxx - jyy|) / (jxx + jyy)`` in [0, 1]; 0 where the tensor is degenerate.  The
    window is ``smooth`` pixels, matching the scale the 100 m grid resolves.  Computed in the
    rank domain -- strike and coherence are scale-free.
    """
    val = layer_float(layers, "B_det_elev_val")
    v = ndimage.uniform_filter(val, smooth)
    del val
    gy = np.gradient(v, axis=0)
    gx = np.gradient(v, axis=1)
    del v
    jyy = ndimage.uniform_filter(gy * gy, smooth)
    jxy = ndimage.uniform_filter(gx * gy, smooth)
    jxx = ndimage.uniform_filter(gx * gx, smooth)
    del gy, gx
    tr = jxx + jyy
    with np.errstate(divide="ignore", invalid="ignore"):
        coh = np.abs(jxx - jyy) / np.where(tr > 1e-12, tr, np.nan)
        strike = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    coh = np.nan_to_num(coh, nan=0.0)
    strike = np.nan_to_num(strike, nan=0.0)
    coh[~valid] = 0.0
    return strike.astype(np.float32), coh.astype(np.float32)


# --------------------------------------------------------------------------------------------
# emission + gates
# --------------------------------------------------------------------------------------------
def emit(field: np.ndarray, pool: np.ndarray, budget: int = BUDGET_PRIMARY,
         min_px: float = 3.0, nms_px: int = 5) -> np.ndarray:
    """The registered emitter: greedy highest-first under isotropic 3 px minimum separation."""
    f = np.nan_to_num(np.asarray(field, np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    support = pool & (f > 0)
    return h57.iso_select(f, support, budget, min_px=min_px, nms_px=nms_px)


def iso_select_exact(score: np.ndarray, allowed: np.ndarray, k: int,
                     min_px: float = 3.0) -> np.ndarray:
    """Exact greedy node selection under an isotropic minimum separation -- no NMS prefilter.

    ``h57.iso_select`` first suppresses non-maxima at ``nms_px`` for speed.  That prefilter is an
    approximation, and on a smooth field it silently CAPS the emission below the requested budget
    (measured on the H59 run: 27,905 nodes against a 37,654 request for the View-B field), because
    a candidate whose higher neighbour is itself blocked by an earlier node would still have been
    taken by the pure greedy.  This function is the pure greedy: candidates in strict score order,
    each taken unless an already-taken node lies within ``min_px`` (inclusive, the metric's own
    k(3px)=0 rule).  It reaches any budget the pool can physically carry, which the incumbent
    37,654-px family proves this pool can.

    Registered use: H59's emitter amendment (registry/h59_preregistration.json), applied
    identically to every arm and to the artifact.
    """
    shape = np.shape(score)
    out = np.zeros(shape, bool)
    ys, xs = np.nonzero(allowed)
    if ys.size == 0 or k <= 0:
        return out
    f = np.nan_to_num(np.asarray(score, np.float64), nan=-np.inf, posinf=-np.inf,
                      neginf=-np.inf)
    order = np.argsort(-f[ys, xs], kind="stable")
    ys = ys[order].tolist()
    xs = xs[order].tolist()
    r = int(math.ceil(min_px))
    lim = min_px + 1e-9
    offs = [(oy, ox) for oy in range(-r, r + 1) for ox in range(-r, r + 1)
            if 0 < (oy * oy + ox * ox) ** 0.5 <= lim]
    h, w = shape
    blocked = np.zeros(shape, bool)
    taken = 0
    for y, x in zip(ys, xs):
        if blocked[y, x]:
            continue
        out[y, x] = True
        taken += 1
        if taken >= k:
            break
        for oy, ox in offs:
            py, px = y + oy, x + ox
            if 0 <= py < h and 0 <= px < w:
                blocked[py, px] = True
    return out


def spacing_stats(emitted: np.ndarray) -> dict:
    """Nearest-neighbour spacing of the emitted cells, in pixels (exact k-d tree)."""
    ys, xs = np.nonzero(emitted)
    if ys.size < 2:
        return dict(n=int(ys.size), min_nn_px=None, median_nn_px=None)
    from scipy.spatial import cKDTree
    pts = np.column_stack([ys.astype(np.float64), xs.astype(np.float64)])
    d, _ = cKDTree(pts).query(pts, k=2)      # k=2: the first hit is the point itself
    nn = d[:, 1]
    return dict(n=int(ys.size), min_nn_px=float(nn.min()), median_nn_px=float(np.median(nn)))


def not_the_union_checks(emission: np.ndarray, pa: np.ndarray, pb: np.ndarray,
                         pool: np.ndarray, budget: int = BUDGET_PRIMARY) -> dict:
    """The brief's 'not merely the union of the two views' gate, measured, not asserted."""
    em_a = iso_select_exact(np.nan_to_num(pa, nan=0.0), pool, budget)
    em_b = iso_select_exact(np.nan_to_num(pb, nan=0.0), pool, budget)
    em_u = iso_select_exact(np.maximum(np.nan_to_num(pa, nan=0.0),
                                       np.nan_to_num(pb, nan=0.0)), pool, budget)
    set_union = em_a | em_b

    def jac(a: np.ndarray, b: np.ndarray) -> float:
        inter = int((a & b).sum())
        union = int((a | b).sum())
        return float(inter / union) if union else 0.0

    return dict(
        budget=int(budget),
        view_a_emitted=int(em_a.sum()), view_b_emitted=int(em_b.sum()),
        union_emitted=int(em_u.sum()), set_union_emitted=int(set_union.sum()),
        jaccard_vs_view_a=jac(emission, em_a), jaccard_vs_view_b=jac(emission, em_b),
        jaccard_vs_union_field=jac(emission, em_u), jaccard_vs_set_union=jac(emission, set_union),
        equals_view_a=bool(np.array_equal(emission, em_a)),
        equals_view_b=bool(np.array_equal(emission, em_b)),
        equals_union_field=bool(np.array_equal(emission, em_u)),
        equals_set_union=bool(np.array_equal(emission, set_union)),
        rule="the decoded pattern must equal none of the four same-budget comparison emissions",
    )


def support_novelty(emission: np.ndarray, prior_masks: list[tuple[str, np.ndarray]],
                    reference: tuple[str, np.ndarray] | None = None) -> dict:
    """Overlap of the emission with the prior support union (reported, never gated)."""
    support = np.zeros(emission.shape, bool)
    for _, m in prior_masks:
        support |= np.asarray(m, bool)
    n = int(emission.sum())
    out = dict(prior_count=len(prior_masks), prior_support_union_px=int(support.sum()),
               emission_px=n,
               emission_on_prior_support_px=int((emission & support).sum()),
               emission_novel_px=int((emission & ~support).sum()),
               emission_novel_fraction=(float((emission & ~support).sum() / n) if n else 0.0))
    if reference is not None:
        name, ref = reference
        out["overlap_with_reference_px"] = int((emission & np.asarray(ref, bool)).sum())
        out["reference_name"] = name
        out["reference_px"] = int(np.asarray(ref, bool).sum())
    return out


# --------------------------------------------------------------------------------------------
# reasoning dossier
# --------------------------------------------------------------------------------------------
def _utmxy(rows: np.ndarray, cols: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    a, _, c, _, e, f = G.TRANSFORM            # GDAL order, measured and pinned in grid.py
    return c + (cols + 0.5) * a, f + (rows + 0.5) * e


def reasoning_rows(emission: np.ndarray, pa: np.ndarray, pb: np.ndarray,
                   strata: dict, layers: h57.Layers, valid: np.ndarray,
                   catalogue: np.ndarray, out_csv: Path) -> dict:
    """One row per emitted pixel; written geology plus a falsifier for every A-only pixel.

    Never claims a verified fault.  Band context is read as uint8 *views* into the same cached
    stack the models used (no full-grid float copies -- twelve of them would be ~590 MB); the
    catalogue enters only as a distance (context), never as a feature.
    """
    ys, xs = np.nonzero(emission)
    a_only = strata["masks"]["a_only"]
    b_only = strata["masks"]["b_only"]
    concordant = strata["masks"]["concordant"]

    def band(name: str) -> np.ndarray:
        return layers.mm[layers.index([name])[0]]          # uint8 view, no copy

    depth, cond = band("A_depth_to_base_val"), band("A_cond_surf_val")
    det_elev, slope = band("B_det_elev_val"), band("B_det_elev_slope_val")
    grav_grad, mag_grad = band("A_grav_anom_grad"), band("A_tmi_hg_grad")
    lidar_step = band("B_lidar_step_max_val")
    strike, coh = strike_coherence(layers, valid)
    ed_cat = ndimage.distance_transform_edt(~catalogue, sampling=(100.0, 100.0))
    east, north = _utmxy(ys.astype(np.float64), xs.astype(np.float64))

    def classify(i: int) -> str:
        y, x = ys[i], xs[i]
        if a_only[y, x]:
            return "A_only"
        if b_only[y, x]:
            return "B_only"
        if concordant[y, x]:
            return "concordant"
        return "neither"

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    n_rows = int(ys.size)
    n_a_only = 0
    with out_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "col", "utm_east_m", "utm_north_m", "stratum", "p_A", "p_B",
                    "depth_to_basement_rank", "conductivity_rank", "detrended_elevation_rank",
                    "slope_rank", "gravity_gradient_rank", "magnetic_gradient_rank",
                    "lidar_step_rank", "local_strike_deg", "local_coherence",
                    "distance_to_nearest_mapped_fault_m", "geological_reasoning", "falsifier"])
        for i in range(n_rows):
            y, x = int(ys[i]), int(xs[i])
            strat = classify(i)
            d_cat = float(ed_cat[y, x])
            dep = float(depth[y, x]) / 255.0
            gg = float(grav_grad[y, x]) / 255.0
            mg = float(mag_grad[y, x]) / 255.0
            ls = float(lidar_step[y, x]) / 255.0
            cdeg = math.degrees(float(strike[y, x]))
            coherence = float(coh[y, x])
            pa_i, pb_i = float(pa[y, x]), float(pb[y, x])
            if strat == "A_only":
                n_a_only += 1
                reasoning = (
                    f"Buried-structure hypothesis (View A confident {pa_i:.2f}, View B abstains "
                    f"{pb_i:.2f}). The potential-field/subsurface view places this cell in its "
                    f"confident class from magnetic and gravity gradient evidence "
                    f"(mag-HG rank {mg:.2f}, grav-grad rank {gg:.2f}) under "
                    f"{dep:.2f} ranked depth to basement, while the surface view finds no "
                    f"corresponding DEM slope ({float(slope[y, x]) / 255.0:.2f}) or LiDAR step "
                    f"({ls:.2f}) signature. Thick cover can bury a fault's surface expression "
                    f"while its potential-field edge persists; the cell is a Phase-2 review "
                    f"candidate, not a verified fault."
                )
                falsifier = (
                    f"Falsified if the band-13 gravity gradient here is a regional isostatic "
                    f"compensation edge or a survey/interpolation artifact of the gravity grid "
                    f"rather than a basement displacement, or if the depth-to-basement model "
                    f"places the step at a lithology change rather than a fault."
                )
            elif strat == "B_only":
                reasoning = (
                    f"Surface-artifact suspicion (View B confident {pb_i:.2f}, View A abstains "
                    f"{pa_i:.2f}). The surface view's lineament here has no potential-field "
                    f"corroboration; roads, levees, irrigation edges and erosion lines produce "
                    f"exactly this signature. Retained only because the shipped ranking field "
                    f"put it above the emission cut; treated as the lowest-confidence family."
                )
                falsifier = (
                    "Falsified as a fault candidate if high-resolution imagery shows an "
                    "anthropogenic or fluvial lineament; confirmed only if a potential-field "
                    "edge or seismicity alignment is later found at this location."
                )
            elif strat == "concordant":
                reasoning = (
                    f"Dual-view agreement (p_A {pa_i:.2f}, p_B {pb_i:.2f}): independent "
                    f"potential-field/subsurface and surface views both place this cell in "
                    f"their confident classes, with local strike {cdeg:.0f} deg (coherence "
                    f"{coherence:.2f}). Two conditionally-uncorrelated views agreeing is the "
                    f"highest-precision stratum the round can produce."
                )
                falsifier = (
                    "Falsified if both views key on the same underlying cause (a lithology "
                    "contact or a mapped-fault halo) rather than an uncatalogued structure."
                )
            else:
                reasoning = (
                    f"Sub-threshold shoulder (p_A {pa_i:.2f}, p_B {pb_i:.2f}): neither view is "
                    f"confident here, but the shipped ranking field placed the cell above the "
                    f"emission cut. H57 measured this shoulder stratum at 3.86x the random "
                    f"control on its holdout; carried as ranked mass, not as a stratum claim."
                )
                falsifier = (
                    "Falsified if the shoulder is field tails rather than structure; the "
                    "holdout shoulder arm is the controlling measurement."
                )
            w.writerow([y, x, round(east[i], 1), round(north[i], 1), strat,
                        round(pa_i, 4), round(pb_i, 4),
                        round(dep, 4), round(float(cond[y, x]) / 255.0, 4),
                        round(float(det_elev[y, x]) / 255.0, 4),
                        round(float(slope[y, x]) / 255.0, 4),
                        round(gg, 4), round(mg, 4), round(ls, 4),
                        round(cdeg, 1), round(coherence, 4), round(d_cat, 1),
                        reasoning, falsifier])
    return dict(rows=n_rows, a_only_rows=n_a_only, path=str(out_csv))
