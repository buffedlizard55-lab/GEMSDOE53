"""View-B radiometric and LiDAR-scarp layers, plus the corrected two-view split.

The correction this module exists to make
-----------------------------------------
``src/gems52/features.py`` reads band 6 of ``data/training_features.tif`` as ``mag_tilt_curvature``
and files it in **View A** (potential field).  Measured on the bytes:

=========================================  ==========  ===========================
test                                       Spearman    source
=========================================  ==========  ===========================
band 6 vs GeoDAWN ``TC`` grid              **1.0000**  data/external/geodawn_rad_u8.tif band 4
band 6 vs K + Th + U                       **0.9914**  total count *is* the window sum
band 6 vs TMI (band 14)                    -0.025      training_features.tif
band 6 vs TMI upward-continued 150 m       +0.008      data/external/geodawn_extensions_u8.tif b4
band 6 vs TMI horizontal gradient (band 3) -0.149      training_features.tif
band 6 vs TMI vertical gradient (band 9)   +0.021      training_features.tif
band 6 vs RTP (band 2)                     -0.091      training_features.tif
=========================================  ==========  ===========================

A magnetic-field derivative cannot be uncorrelated with the magnetic field.  Band 6 is the
GeoDAWN **aeroradiometric total count** grid; the TIFF tag inside the competition's own file is
wrong.  Official source: Glen, J.M.G., and Earney, T.E., 2024, *GeoDAWN: Airborne magnetic and
radiometric surveys of the northwestern Great Basin, Nevada and California*, U.S. Geological Survey
data release, https://doi.org/10.5066/P93LGLVQ  (public domain; USGS data are free of use
restrictions -- https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits ).

Consequence for the brief: the clause "View B is DEM-derived curvature and slope, **plus any
radiometric bands present in ``training_features.tif``**" resolves to exactly one band inside the
official file (band 6) and to six more in the official USGS release that the competition did not
ship (K, Th, U, Th/K, U/K, U/Th).  The H52 knowledge note that recorded "no radiometric band" is
therefore superseded, and IR-52-001 is re-scoped rather than closed.

Why radiometrics are the right *View B* physics for a buried fault
------------------------------------------------------------------
Airborne gamma-ray spectrometry measures K (%), eTh (ppm) and eU (ppm) in the top ~30-50 cm.
Three signatures matter here, and none of them needs relief:

* **Alluvium / bedrock contact.** Basin fill is Th-rich and K-poor relative to the felsic to
  intermediate volcanics of the ranges, so Th/K steps sharply across a range front.  Where the
  scarp is buried under fan alluvium the *topographic* step is gone but the *radiometric* step
  survives, because the two materials still sit either side of the plane.
* **Hydrothermal alteration.** Potassic alteration raises K and lowers Th/K; silicification and
  iron staining raise U and U/K.  Fault planes are the conduits, so alteration is linear and
  fault-parallel (this is the standard Great Basin exploration play, and the reason GeoDAWN flew
  radiometrics at all -- the survey's stated purpose is geothermal and critical-mineral mapping).
* **Moisture / radon suppression along a damage zone.** Total count drops over a wet, clay-rich
  fault gouge even with no relief at all.

All three are surface-geochemical, i.e. legitimately **View B**, and all three are approximately
conditionally independent of the potential-field evidence in View A given the label -- which is the
premise the brief asks to be tested rather than assumed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from gems52 import transform as T

FEATURES = "data/training_features.tif"
RAD_U8 = "data/external/geodawn_rad_u8.tif"
RAD_EXT_U8 = "data/external/geodawn_extensions_u8.tif"
LIDAR_U8 = "data/external/lidar_scarp_features_u8.tif"

# ---- the corrected two views -----------------------------------------------------------------
VIEW_A = [                       # potential field + subsurface.  band 6 is NOT here any more.
    "A_grav_step", "A_grav_edge", "A_grav_vg_rank", "A_grav_hg_rank", "A_grav_slope_band",
    "A_mag_step", "A_mag_edge_vg", "A_rtp_rank",
    "A_strain_inv_rank", "A_strain_inv_reg", "A_shear_rank", "A_dilate_rank",
    "A_eqdens_rank", "A_eqdist_negrank", "A_depth_base_rank", "A_cond_rank",
]
VIEW_B = [                       # surface: DEM-derived + radiometric + LiDAR scarp
    "B_scarp_p900", "B_scarp_p300", "B_scarp_fine", "B_slope_rank", "B_elev_rank",
    "B_line_resp", "B_elev_grad",
    "R_tc_step900", "R_tc_edge", "R_tc_line", "R_tc_rank",
    "R_thk_step900", "R_uk_step900", "R_thk_edge", "R_uk_edge",
    "L_step_max", "L_ex_max", "L_coh100", "L_relief", "L_cover",
]
STRIKE_LAYERS = ["A_grav_strike", "A_mag_strike", "B_scarp_strike", "R_tc_strike"]

BAND6_IS_RADIO_METRIC = dict(
    band=6, tag_name_in_file="tc", tag_category_in_file="magnetic_data",
    tag_description_in_file="Tilt angle or total curvature - magnetic field derivative for edge detection",
    identified_as="GeoDAWN aeroradiometric total count (TC)",
    official_source="https://doi.org/10.5066/P93LGLVQ",
    evidence="evidence/h55_band6_identity.json",
)


def _read(path: str, band: int, valid: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(band).astype(np.float32)
    a[~np.isfinite(a)] = np.nan
    a[a < -1e38] = np.nan
    a[~valid] = np.nan
    return a


def _u8(path: str, band: int, valid: np.ndarray) -> np.ndarray:
    """uint8 external layer -> float32, with 0 read as 'no measurement' (NaN), not as a low value."""
    with rasterio.open(path) as src:
        a = src.read(band).astype(np.float32)
    a[a <= 0] = np.nan
    a[~valid] = np.nan
    return a


def band6_identity_report(features: str = FEATURES, rad: str = RAD_U8, ext: str = RAD_EXT_U8,
                          sample: int = 150_000, seed: int = 0) -> dict:
    """Re-measure, from the bytes, the correlation table this module's docstring quotes."""
    from scipy.stats import spearmanr
    nd = -1e38
    with rasterio.open(features) as src:
        b6 = src.read(6).astype(np.float32)
        bands = {i: src.read(i).astype(np.float32) for i in (2, 3, 9, 14)}
        names = {i: (src.descriptions[i - 1] or "").split(" - ")[0] for i in bands}
    with rasterio.open(rad) as src:
        K, Th, U, TC = (src.read(i).astype(np.float32) for i in (1, 2, 3, 4))
    with rasterio.open(ext) as src:
        tmi_up = src.read(4).astype(np.float32)
    m = (b6 > nd) & (TC > 0) & (K > 0) & (Th > 0)
    idx = np.flatnonzero(m.ravel())
    rng = np.random.default_rng(seed)
    s = rng.choice(idx, size=min(sample, idx.size), replace=False)

    def col(a):
        return a.ravel()[s].astype(np.float64)

    pairs = {
        "geoDAWN_TC_grid": col(TC),
        "K_plus_Th_plus_U": col(K) + col(Th) + col(U),
        "TMI_band14": col(bands[14]),
        "TMI_up150_external": col(tmi_up),
        "TMI_horizontal_gradient_band3": col(bands[3]),
        "TMI_vertical_gradient_band9": col(bands[9]),
        "RTP_band2": col(bands[2]),
    }
    b = col(b6)
    out = dict(n_sampled=int(s.size), n_overlap_px=int(m.sum()),
               band6_min=float(np.nanmin(b)), band6_max=float(np.nanmax(b)),
               band6_mean=float(np.nanmean(b)),
               spearman={k: float(spearmanr(b, v).statistic) for k, v in pairs.items()},
               pearson={k: float(np.corrcoef(b, v)[0, 1]) for k, v in pairs.items()},
               band_names={str(k): v for k, v in names.items()})
    out["conclusion"] = ("band 6 is the GeoDAWN aeroradiometric total-count grid; the file's own "
                         "'magnetic_data / tilt angle or total curvature' tag is incorrect")
    return out


def build(work_dir: str = "work", log=None) -> dict:
    """Write the radiometric + LiDAR layers next to the H52 layers, in the same *.npy convention."""
    log = log or (lambda *a: print(*a, flush=True))
    work = Path(work_dir) / "derived"
    work.mkdir(parents=True, exist_ok=True)
    valid = np.load(work / "valid_footprint.npy")
    man_path = work / "manifest.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() else {"layers": {}}

    tc = _read(FEATURES, 6, valid)
    log(f"  band 6 (radiometric TC) finite px {int(np.isfinite(tc).sum())}")
    added = {}

    def put(name, arr):
        arr = np.asarray(arr, dtype=np.float32)
        arr[~valid] = np.nan
        np.save(work / f"{name}.npy", arr)
        r = T.rank01(arr, valid)
        np.save(work / f"{name}__rank.npy", r)
        v = arr[valid & np.isfinite(arr)]
        added[name] = dict(file=f"{name}.npy", rank_file=f"{name}__rank.npy",
                           finite_px=int(np.isfinite(arr[valid]).sum()),
                           coverage=float(np.isfinite(arr[valid]).mean()),
                           min=float(v.min()) if v.size else None,
                           p50=float(np.median(v)) if v.size else None,
                           max=float(v.max()) if v.size else None)
        manifest["layers"][name] = added[name]
        log(f"  built {name} (coverage {added[name]['coverage']:.2%})")

    step, strike = T.scarp_step(tc, valid, 900.0, 1900.0)
    put("R_tc_step900", step)
    put("R_tc_edge", T.gradient_magnitude(tc, valid))
    put("R_tc_line", T.hessian_line(tc, valid, 300.0))
    put("R_tc_rank", tc)
    np.save(work / "R_tc_strike.npy", strike.astype(np.int16))

    if Path(RAD_EXT_U8).exists():
        thk = _u8(RAD_EXT_U8, 1, valid)
        uk = _u8(RAD_EXT_U8, 2, valid)
        put("R_thk_step900", T.scarp_step(thk, valid, 900.0, 1900.0)[0])
        put("R_uk_step900", T.scarp_step(uk, valid, 900.0, 1900.0)[0])
        put("R_thk_edge", T.gradient_magnitude(thk, valid))
        put("R_uk_edge", T.gradient_magnitude(uk, valid))
    if Path(LIDAR_U8).exists():
        lv = _u8(LIDAR_U8, 12, valid)
        lvalid = np.isfinite(lv) & valid
        for band, name in ((3, "L_step_max"), (1, "L_ex_max"), (10, "L_coh100"), (9, "L_relief")):
            a = _u8(LIDAR_U8, band, valid)
            # outside the LiDAR tiles there is no measurement at all: hold it at the footprint
            # median rather than at 0, so a rank cannot read "no LiDAR" as "no scarp"
            med = float(np.nanmedian(a[lvalid])) if lvalid.any() else 0.0
            a = np.where(lvalid, a, med)
            a[~valid] = np.nan
            put(name, a)
        # the LiDAR acquisition footprint is itself a feature: catalogue-fault density is 1.2445 %
        # inside it and 0.9838 % outside, so a model that cannot see the coverage mask will read
        # "no LiDAR" as "no scarp" and mis-rank a quarter of the region.  Measured, not assumed.
        put("L_cover", np.where(lvalid, 1.0, 0.0).astype(np.float32))
    manifest["radiometric_view_b"] = BAND6_IS_RADIO_METRIC
    man_path.write_text(json.dumps(manifest, indent=1))
    log(f"wrote {len(added)} H55 layers into {work}")
    return added
