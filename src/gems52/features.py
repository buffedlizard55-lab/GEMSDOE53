"""Build the two views' feature layers from the official rasters, with a cached manifest.

View definition (from the standing brief, and cross-checked against the band tags measured on
``data/training_features.tif``):

* **View A -- potential-field and subsurface**: isostatic gravity anomaly and its provided slope /
  vertical / horizontal gradients, magnetics (anomaly, RTP, TMI, TMI horizontal + vertical
  gradient, tilt/total-curvature), geodetic strain (dilatation, shear, second invariant),
  seismicity (density and distance), depth to basement and surface conductivity.
* **View B -- surface**: detrended elevation, its slope, and DEM-derived transforms (the
  laterally-persistent across-strike step and a Hessian line response).

**SUPERSEDED — read this before using the view split below.**  This module's original note said the
19 band tags contain *no radiometric band*, and filed band 6 in **View A** as ``A_mag_tilt_abs``
because the file's own tag reads ``data_category = magnetic_data``, "Tilt angle or total curvature -
magnetic field derivative for edge detection".  That tag is wrong.  Measured on the bytes
(``evidence/h53_band6_identity.json``, 150,000-pixel sample): Spearman(band 6, GeoDAWN total-count
grid) = **+1.0000**; Spearman(band 6, K+Th+U) = **+0.9914**, which is what a total-count channel is
by construction; and |Spearman| <= 0.149 against all five magnetic bands in the same file
(TMI -0.0250, TMI up-continued 150 m +0.0079, TMI horizontal gradient -0.1489, TMI vertical gradient
+0.0214, RTP -0.0914).  A magnetic-field derivative cannot be uncorrelated with the magnetic field,
and band 6 is strictly positive (min 2.953, max 88.573) where a tilt angle is bounded by +/- pi/2.
So the brief's clause "plus any radiometric bands present in ``training_features.tif``" resolves to
**one band**, not to none, and the two-view split below is wrong in a way that matters: it puts a
surface-geochemistry band inside the potential-field view, which corrupts the conditional-
independence test the brief asks for.  See ``registry/irregularities.json`` **IR-52-019**, which
corrects IR-52-001, and ``src/gems53/radlayers.py`` for the corrected split.  This module is kept
byte-identical because the H52 holdout evidence and the shipped H52 raster were produced by it, and
re-running them against a corrected split would make that evidence unverifiable.

Everything is computed inside the footprint only, and NaN elsewhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from . import transform as T

FEATURES_PATH = "data/training_features.tif"

# band index (1-based) and tag name, transcribed from the file's own TIFF tags -- see
# evidence/band_inventory.json which is written by scripts/prepare_data.py from the same read.
BANDS = {
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 4: "geod_2ndinv", 5: "iso_grav_slope",
    6: "mag_tilt_curvature",   # MIS-TAGGED IN THE SOURCE FILE: measured to be radiometric total
                              # count, not a magnetic derivative -- see IR-52-019 and gems53 7: "geod_shearrate", 8: "geod_dilaterate", 9: "tmi_vg",
    10: "dist_to_eq", 11: "iso_grav_vg", 12: "det_elev", 13: "iso_grav_anom",
    14: "tmi", 15: "depth_to_base_surf", 16: "eq_density", 17: "cond_surf",
    18: "iso_grav_hg", 19: "det_elev_slope",
}

VIEW_A = [
    "A_grav_step", "A_grav_edge", "A_grav_vg_rank", "A_grav_hg_rank",
    "A_mag_step", "A_mag_edge_vg", "A_mag_tilt_abs", "A_rtp_rank",
    "A_strain_inv_rank", "A_strain_inv_reg", "A_shear_rank", "A_dilate_rank",
    "A_eqdens_rank", "A_eqdist_negrank", "A_depth_base_rank", "A_cond_rank",
]
VIEW_B = [
    "B_scarp_p900", "B_scarp_p300", "B_scarp_fine", "B_slope_rank", "B_elev_rank",
    "B_line_resp", "B_elev_grad",
]


def _read(src, i):
    a = src.read(i).astype(np.float32)
    a[~np.isfinite(a)] = np.nan
    a[a < -1e38] = np.nan                 # the official nodata sentinel, -3.4028234663852886e+38
    return a


def build(work_dir: str = "work", features_path: str = FEATURES_PATH,
          scarp_half_m: float = 900.0, scarp_persist_m: float = 1900.0,
          log=None) -> dict:
    """Compute and cache every layer; returns the manifest {name: {path, stats}}."""
    work = Path(work_dir) / "derived"
    work.mkdir(parents=True, exist_ok=True)
    log = log or (lambda *a: print(*a, flush=True))
    with rasterio.open(features_path) as src:
        valid = None
        for i in range(1, src.count + 1):
            a = src.read(i)
            ok = np.isfinite(a) & (a > -1e38)
            valid = ok if valid is None else (valid & ok)
        valid = valid.astype(bool)
        log(f"footprint (all-19-band intersection): {int(valid.sum())} px "
            f"= {valid.mean():.4%} of grid")
        raw = {}
        for i, name in BANDS.items():
            raw[name] = _read(src, i)
            log(f"  read band {i:>2} {name}")

        layers: dict[str, np.ndarray] = {}

        def put(name, arr, note=""):
            arr = np.asarray(arr, dtype=np.float32)
            arr[~valid] = np.nan
            layers[name] = arr
            log(f"  built {name}")

        # ---- View A: potential-field + subsurface -------------------------------------------
        g = raw["iso_grav_anom"]
        grav_step, grav_strike = T.scarp_step(g, valid, scarp_half_m, scarp_persist_m)
        put("A_grav_step", grav_step)
        put("A_grav_edge", T.gradient_magnitude(g, valid))
        put("A_grav_vg_rank", np.abs(raw["iso_grav_vg"]))
        put("A_grav_hg_rank", np.abs(raw["iso_grav_hg"]))
        put("A_grav_slope_band", np.abs(raw["iso_grav_slope"]))
        m = raw["rtp"]
        mag_step, mag_strike = T.scarp_step(m, valid, scarp_half_m, scarp_persist_m)
        put("A_mag_step", mag_step)
        put("A_mag_edge_vg", np.abs(raw["tmi_vg"]))
        put("A_mag_tilt_abs", np.abs(raw["mag_tilt_curvature"]))
        put("A_rtp_rank", np.abs(T.gradient_magnitude(m, valid)))
        put("A_strain_inv_rank", raw["geod_2ndinv"])
        put("A_strain_inv_reg", T.box_mean(raw["geod_2ndinv"], valid, 2500.0))
        put("A_shear_rank", raw["geod_shearrate"])
        put("A_dilate_rank", raw["geod_dilaterate"])
        put("A_eqdens_rank", raw["eq_density"])
        put("A_eqdist_negrank", -raw["dist_to_eq"])
        put("A_depth_base_rank", raw["depth_to_base_surf"])
        put("A_cond_rank", raw["cond_surf"])

        # ---- View B: surface ------------------------------------------------------------------
        z, zs = raw["det_elev"], raw["det_elev_slope"]
        sc9, sc9_strike = T.scarp_step(zs, valid, scarp_half_m, scarp_persist_m)
        put("B_scarp_p900", sc9)
        put("B_scarp_p300", T.scarp_step(zs, valid, scarp_half_m, 300.0)[0])
        put("B_scarp_fine", T.scarp_step(zs, valid, 300.0, 600.0)[0])
        put("B_slope_rank", np.abs(zs))
        put("B_elev_rank", z)
        put("B_line_resp", T.hessian_line(z, valid, 300.0))
        put("B_elev_grad", T.gradient_magnitude(z, valid))

        # strike of maximum response -- used by the coherence gate at emission time
        put("A_grav_strike", grav_strike)
        put("A_mag_strike", mag_strike)
        put("B_scarp_strike", sc9_strike)

    # rank-encode [0,1] inside the footprint for the learners, keep raw for the physics audit
    manifest = {"footprint_px": int(valid.sum()), "shape": list(valid.shape), "layers": {}}
    np.save(work / "valid_footprint.npy", valid)
    for name, arr in layers.items():
        r = T.rank01(arr, valid)
        np.save(work / f"{name}.npy", arr)
        np.save(work / f"{name}__rank.npy", r)
        v = arr[valid]
        rv = r[valid]
        manifest["layers"][name] = dict(
            file=f"{name}.npy", rank_file=f"{name}__rank.npy",
            nan_px=int(np.isnan(arr).sum()),
            min=float(np.nanmin(v)), p50=float(np.nanpercentile(v, 50)), max=float(np.nanmax(v)),
            rank_mean=float(np.nanmean(rv)),
        )
    (work / "manifest.json").write_text(json.dumps(manifest, indent=1))
    log(f"wrote {work}/manifest.json with {len(layers)} layers")
    return manifest
