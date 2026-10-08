"""The round-4 layer plan: 74 declared layers, streamed one at a time into a memmap.

Why a declarative plan at all
-----------------------------
Round 3 and earlier built feature arrays ad hoc inside whichever script needed them,
so the "which layers exist" answer lived in the code of the moment and drifted.  Here
the plan is data: ``LAYER_PLAN`` is the single list of every layer this round is
allowed to use, each entry carrying its name, its view and how to build it.  Asking
for a layer that is not in the plan raises, rather than silently returning a
different array than last time.

Why streamed
------------
74 layers x 3730 x 3292 float32 is 3.6 GB.  This box has 3 GB of RAM, so the stack is
never materialised in memory: each layer is computed alone, written into its slot of a
``np.memmap``, and freed before the next one starts.  Holding the whole thing in RAM
was tried and died with exit 137 three separate times.

View assignment
---------------
Band 6 of ``training_features.tif`` is tagged ``magnetic_data`` / "Tilt angle or total
curvature" by the organisers, but measured on the bytes it is radiometric total count
(Spearman +1.0000 against the GeoDAWN TC grid, |rho| <= 0.149 against all five magnetic
bands, and strictly positive where a tilt angle is bounded by +/-pi/2).  It therefore
belongs in View B, not in the potential-field view -- see IR-52-019 and IR-52-034.  A
radiometric band sitting inside View A would corrupt the conditional-independence test
the brief asks the two views to pass.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

from gems52 import transform as Gtr
from gems52.grid import PIXEL_M


# --------------------------------------------------------------------------------------
# raw band inventory
# --------------------------------------------------------------------------------------

# 1-based band index -> short name, transcribed from the file's own TIFF tags and
# recorded in evidence/band_inventory.json.
BANDS = {
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 4: "geod_2ndinv", 5: "iso_grav_slope",
    6: "rad_total_count", 7: "geod_shearrate", 8: "geod_dilaterate", 9: "tmi_vg",
    10: "dist_to_eq", 11: "iso_grav_vg", 12: "det_elev", 13: "iso_grav_anom",
    14: "tmi", 15: "depth_to_base_surf", 16: "eq_density", 17: "cond_surf",
    18: "iso_grav_hg", 19: "det_elev_slope",
}

# External rasters, by (file, 1-based band) -> name.
EXTERNAL_RASTERS = {
    "geodawn_rad_u8.tif": {1: "rad_K", 2: "rad_Th", 3: "rad_U", 4: "rad_TC"},
    "geodawn_extensions_u8.tif": {1: "ext_ThK", 2: "ext_UK", 3: "ext_UTh", 4: "ext_TMI_up150"},
}
# Only the eight LiDAR bands the source file actually names are used.  Bands 9-12 carry
# no description, and an unnamed band is not a layer this round can justify.
LIDAR_NAMES = ["ex_max", "ex_mean", "step_max", "lapneg_max",
               "lappos_max", "downface_max", "upface_max", "cross_max"]

FEATURES = "data/training_features.tif"
EXTERNAL_DIR = "data/external"


class RawStore:
    """Lazy reader for raw bands.

    Keeps at most ``keep`` grids alive so a long builder chain cannot quietly pin
    nineteen full-resolution arrays in a 3 GB box.  Reads are float32; the nodata
    sentinel (-3.4028234663852886e+38) and any non-finite value become NaN.
    """

    def __init__(self, features: str = FEATURES, external_dir: str = EXTERNAL_DIR,
                 keep: int = 4):
        self.features = features
        self.external_dir = Path(external_dir)
        self.keep = keep
        self._cache: dict[str, np.ndarray] = {}
        self._order: list[str] = []
        self._src = None
        self._ext: dict[str, object] = {}

    # -- lifecycle -----------------------------------------------------------------
    def __enter__(self) -> "RawStore":
        import rasterio
        self._src = rasterio.open(self.features)
        return self

    def __exit__(self, *exc) -> None:
        for s in self._ext.values():
            try:
                s.close()
            except Exception:
                pass
        self._ext.clear()
        if self._src is not None:
            try:
                self._src.close()
            except Exception:
                pass
            self._src = None

    # -- reads ---------------------------------------------------------------------
    def _clean(self, a: np.ndarray) -> np.ndarray:
        a = np.asarray(a, dtype=np.float32)
        a[~np.isfinite(a)] = np.nan
        a[a < -1e38] = np.nan
        return a

    def _remember(self, name: str, arr: np.ndarray) -> np.ndarray:
        self._cache[name] = arr
        self._order.append(name)
        while len(self._order) > self.keep:
            old = self._order.pop(0)
            self._cache.pop(old, None)
        return arr

    def band(self, name: str) -> np.ndarray:
        """One band of ``training_features.tif`` by short name."""
        if name in self._cache:
            return self._cache[name]
        idx = [i for i, n in BANDS.items() if n == name]
        if not idx:
            raise KeyError(f"undeclared training band {name!r}")
        return self._remember(name, self._clean(self._src.read(idx[0])))

    def external(self, filename: str, band: int) -> np.ndarray:
        import rasterio
        key = f"{filename}#{band}"
        if key in self._cache:
            return self._cache[key]
        if filename not in self._ext:
            self._ext[filename] = rasterio.open(self.external_dir / filename)
        return self._remember(key, self._clean(self._ext[filename].read(band)))

    def lidar(self, band: int) -> np.ndarray:
        return self.external("lidar_scarp_features_u8.tif", band)

    def sgmc(self) -> np.ndarray:
        return self.external("derived_sgmc_faults_100m_u8.tif", 1)


# --------------------------------------------------------------------------------------
# generic operators
# --------------------------------------------------------------------------------------

def _sigma_px(sigma_m: float) -> float:
    return float(sigma_m) / PIXEL_M


def regional_z(a: np.ndarray, valid: np.ndarray, sigma_m: float) -> np.ndarray:
    """Long-wavelength component of ``a``, computed inside the footprint only.

    The field is filled with its footprint mean before smoothing and re-masked after,
    which is the least-committal choice available: it does not invent structure
    outside the footprint, and it avoids the edge roll-off that NaN-aware convolution
    would otherwise produce.
    """
    f = Gtr.fill_outside(a, valid, fill=float(np.nanmean(a[valid])) if valid.any() else 0.0)
    r = ndimage.gaussian_filter(f, _sigma_px(sigma_m), mode="nearest")
    return np.where(valid, r, np.nan).astype(np.float32)


def _local_stats(a: np.ndarray, valid: np.ndarray, radius_m: float):
    """Footprint-aware local mean and standard deviation over a square window.

    Counts and sums are taken over valid pixels only, so a window that is half
    outside the footprint reports the statistics of the half that is inside rather
    than being dragged toward the fill value.
    """
    w = max(1, int(round(float(radius_m) / PIXEL_M)))
    size = 2 * w + 1
    f = np.where(valid, a, 0.0).astype(np.float64)
    m = np.where(valid, 1.0, 0.0)
    n = ndimage.uniform_filter(m, size=size, mode="constant", cval=0.0)
    s1 = ndimage.uniform_filter(f, size=size, mode="constant", cval=0.0)
    s2 = ndimage.uniform_filter(f * f, size=size, mode="constant", cval=0.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(n > 0, s1 / np.maximum(n, 1e-12), np.nan)
        var = np.where(n > 0, np.maximum(s2 / np.maximum(n, 1e-12) - mean ** 2, 0.0), np.nan)
    return np.where(valid, mean, np.nan).astype(np.float32), np.where(valid, np.sqrt(var), np.nan).astype(np.float32)


def structure_tensor(a: np.ndarray, valid: np.ndarray, sigma_m: float = 300.0) -> dict:
    """2x2 gradient structure tensor of ``a``, smoothed at ``sigma_m``.

    Returns ``coherence`` (0..1, how one-dimensional the local gradient pattern is),
    ``anisotropy`` (lambda1 - lambda2) and the orientation as unit-vector components
    ``ori_x``/``ori_y``.  The integration scale defaults to 300 m because that is the
    metric's own kernel radius: an orientation estimated finer than the scoring kernel
    would be a different, noisier quantity than the one the score rewards.
    """
    f = Gtr.fill_outside(a, valid, fill=float(np.nanmean(a[valid])) if valid.any() else 0.0)
    gy, gx = np.gradient(f, PIXEL_M, PIXEL_M, edge_order=2)
    gy = np.where(valid, gy, 0.0)
    gx = np.where(valid, gx, 0.0)
    s = _sigma_px(sigma_m)
    jxx = ndimage.gaussian_filter(gx * gx, s, mode="nearest")
    jyy = ndimage.gaussian_filter(gy * gy, s, mode="nearest")
    jxy = ndimage.gaussian_filter(gx * gy, s, mode="nearest")
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    with np.errstate(invalid="ignore"):
        disc = np.sqrt(np.maximum(tr * tr - 4.0 * det, 0.0))
    l1 = 0.5 * (tr + disc)
    l2 = 0.5 * (tr - disc)
    with np.errstate(invalid="ignore", divide="ignore"):
        coh = np.where(l1 > 0, disc / np.maximum(l1, 1e-20), 0.0)
    # orientation of the dominant gradient direction, as a unit vector
    with np.errstate(invalid="ignore", divide="ignore"):
        norm = np.sqrt(jxy * jxy + np.maximum(l1 - jyy, 0.0) ** 2)
        ox = np.where(norm > 0, jxy / np.maximum(norm, 1e-20), 0.0)
        oy = np.where(norm > 0, (l1 - jyy) / np.maximum(norm, 1e-20), 0.0)
    return {
        "coherence": np.where(valid, np.clip(coh, 0.0, 1.0), np.nan).astype(np.float32),
        "anisotropy": np.where(valid, l1 - l2, np.nan).astype(np.float32),
        "ori_x": np.where(valid, ox, np.nan).astype(np.float32),
        "ori_y": np.where(valid, oy, np.nan).astype(np.float32),
    }


def azimuthal_derivatives(a: np.ndarray, valid: np.ndarray, azimuths_deg=(0.0, 45.0, 90.0, 135.0)):
    """Absolute directional derivative of ``a`` along each azimuth.

    Azimuth is measured clockwise from grid north.  Faults in this province are
    strongly aligned, so a directional derivative that integrates along the dominant
    strike sees a scarp as a coherent ridge while the across-strike derivative sees it
    as a step; both are useful, and which one is useful is exactly the question the
    two views are meant to settle empirically.
    """
    out = []
    for az in azimuths_deg:
        t = np.deg2rad(float(az))
        gy, gx = np.gradient(Gtr.fill_outside(a, valid, fill=0.0), PIXEL_M, PIXEL_M, edge_order=1)
        d = np.abs(np.cos(t) * gy + np.sin(t) * gx)
        out.append(np.where(valid, d, np.nan).astype(np.float32))
    return out


def distance_to_points(rows: np.ndarray, cols: np.ndarray, shape, valid: np.ndarray) -> np.ndarray:
    """Euclidean distance in metres from every pixel to the nearest supplied point.

    Points outside the grid or outside the footprint are dropped.  Where no point
    exists the result is NaN rather than a large number, so a downstream ranker cannot
    mistake "no data nearby" for "very far from data".
    """
    pts = np.zeros(valid.shape, dtype=bool)
    ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
    rows, cols = rows[ok], cols[ok]
    if rows.size:
        keep = valid[rows, cols]
        rows, cols = rows[keep], cols[keep]
    if rows.size == 0:
        return np.full(shape, np.nan, dtype=np.float32)
    pts[rows, cols] = True
    d = ndimage.distance_transform_edt(~pts)
    return np.where(valid, d * PIXEL_M, np.nan).astype(np.float32)


def paleo_geothermal_table(path: str = "data/external/gdr_wellspring_in_footprint.csv",
                           min_geotherm_c: float = 150.0) -> dict:
    """Read the spring catalogue and return the high-geotherm subset as point arrays.

    ``geothermcat_c`` is the cation geothermometry estimate of reservoir temperature.
    The threshold is a declared constant, not a tuned parameter: 150 C is the
    conventional lower bound for an electricity-grade geothermal system, and using a
    published cut keeps the layer from being retro-fitted to whatever happens to sit
    near the known faults.
    """
    rows, cols, temps = [], [], []
    with open(path, newline="") as fh:
        for rec in csv.DictReader(fh):
            try:
                t = float(rec.get("geothermcat_c") or "nan")
                r = int(float(rec["row"]))
                c = int(float(rec["col"]))
            except (TypeError, ValueError, KeyError):
                continue
            if not np.isfinite(t) or t < min_geotherm_c:
                continue
            rows.append(r)
            cols.append(c)
            temps.append(t)
    return {
        "row": np.asarray(rows, dtype=np.int64),
        "col": np.asarray(cols, dtype=np.int64),
        "geotherm_c": np.asarray(temps, dtype=np.float32),
        "n_total_read": None,
        "threshold_c": min_geotherm_c,
    }


def paleo_geothermal_distance(shape, valid: np.ndarray, table: dict) -> np.ndarray:
    """Negated distance in metres to the nearest high-geotherm spring.

    Negated so that, like every other layer here, larger means more prospective; a
    ranker that assumes monotone-increasing prospectivity stays correct.
    """
    d = distance_to_points(table["row"], table["col"], shape, valid)
    return np.where(np.isfinite(d), -d, np.nan).astype(np.float32)


def _point_table(path: str, row_key: str = "row", col_key: str = "col") -> dict:
    rows, cols = [], []
    with open(path, newline="") as fh:
        for rec in csv.DictReader(fh):
            try:
                rows.append(int(float(rec[row_key])))
                cols.append(int(float(rec[col_key])))
            except (TypeError, ValueError, KeyError):
                continue
    return {"row": np.asarray(rows, dtype=np.int64), "col": np.asarray(cols, dtype=np.int64)}


# --------------------------------------------------------------------------------------
# the layer plan
# --------------------------------------------------------------------------------------
# Each entry: (name, view, builder-key, kwargs).  Counts are asserted at import time so
# a future edit that drops a layer fails loudly instead of changing the model silently.

PLAN_ENTRIES: list[tuple[str, str, str, dict]] = []


def _p(name: str, view: str, builder: str, **kw):
    PLAN_ENTRIES.append((name, view, builder, kw))


# ---- View A: potential field and subsurface (30) -------------------------------------
for _n, _b, _kw in [
    ("A_grav_anom", "band", {"b": "iso_grav_anom"}),
    ("A_grav_slope_abs", "abs", {"b": "iso_grav_slope"}),
    ("A_grav_vg_abs", "abs", {"b": "iso_grav_vg"}),
    ("A_grav_hg_abs", "abs", {"b": "iso_grav_hg"}),
    ("A_grav_gradmag", "gradmag", {"b": "iso_grav_anom"}),
    ("A_grav_step900", "scarp", {"b": "iso_grav_anom", "half": 900.0, "persist": 1900.0}),
    ("A_grav_step300", "scarp", {"b": "iso_grav_anom", "half": 300.0, "persist": 600.0}),
    ("A_grav_regional", "regional", {"b": "iso_grav_anom", "sigma": 5000.0}),
    ("A_grav_residual", "residual", {"b": "iso_grav_anom", "sigma": 5000.0}),
    ("A_mag_anom", "band", {"b": "mag_anom"}),
    ("A_rtp", "band", {"b": "rtp"}),
    ("A_tmi", "band", {"b": "tmi"}),
    ("A_tmi_hg_abs", "abs", {"b": "tmi_hg"}),
    ("A_tmi_vg_abs", "abs", {"b": "tmi_vg"}),
    ("A_mag_gradmag", "gradmag", {"b": "rtp"}),
    ("A_mag_step900", "scarp", {"b": "rtp", "half": 900.0, "persist": 1900.0}),
    ("A_mag_step300", "scarp", {"b": "rtp", "half": 300.0, "persist": 600.0}),
    ("A_mag_regional", "regional", {"b": "rtp", "sigma": 5000.0}),
    ("A_mag_residual", "residual", {"b": "rtp", "sigma": 5000.0}),
    ("A_tmi_up150", "external", {"f": "geodawn_extensions_u8.tif", "i": 4}),
    ("A_tmi_up150_gradmag", "ext_gradmag", {"f": "geodawn_extensions_u8.tif", "i": 4}),
    ("A_tmi_up150_regional", "ext_regional", {"f": "geodawn_extensions_u8.tif", "i": 4, "sigma": 5000.0}),
    ("A_strain_2ndinv", "band", {"b": "geod_2ndinv"}),
    ("A_strain_shear", "band", {"b": "geod_shearrate"}),
    ("A_strain_dilate", "band", {"b": "geod_dilaterate"}),
    ("A_strain_regional", "regional", {"b": "geod_2ndinv", "sigma": 2500.0}),
    ("A_eq_density", "band", {"b": "eq_density"}),
    ("A_eq_dist_negrank", "negband", {"b": "dist_to_eq"}),
    ("A_depth_base", "band", {"b": "depth_to_base_surf"}),
    ("A_cond_surf", "band", {"b": "cond_surf"}),
]:
    _p(_n, "A", _b, **_kw)

# ---- View B: surface and radiometric (44) ---------------------------------------------
for _n, _b, _kw in [
    ("B_rad_K", "external", {"f": "geodawn_rad_u8.tif", "i": 1}),
    ("B_rad_Th", "external", {"f": "geodawn_rad_u8.tif", "i": 2}),
    ("B_rad_U", "external", {"f": "geodawn_rad_u8.tif", "i": 3}),
    ("B_rad_TC", "external", {"f": "geodawn_rad_u8.tif", "i": 4}),
    ("B_rad_ThK", "external", {"f": "geodawn_extensions_u8.tif", "i": 1}),
    ("B_rad_UK", "external", {"f": "geodawn_extensions_u8.tif", "i": 2}),
    ("B_rad_UTh", "external", {"f": "geodawn_extensions_u8.tif", "i": 3}),
    ("B_rad_TC_grad", "ext_gradmag", {"f": "geodawn_rad_u8.tif", "i": 4}),
    ("B_rad_K_regional", "ext_regional", {"f": "geodawn_rad_u8.tif", "i": 1, "sigma": 5000.0}),
    ("B_rad_K_residual", "ext_residual", {"f": "geodawn_rad_u8.tif", "i": 1, "sigma": 5000.0}),
    ("B_rad_Knorm", "ratio", {"num": ("geodawn_rad_u8.tif", 1), "den": ("geodawn_rad_u8.tif", 4)}),
    ("B_rad_Unorm", "ratio", {"num": ("geodawn_rad_u8.tif", 3), "den": ("geodawn_rad_u8.tif", 4)}),
    ("B_rad_Thnorm", "ratio", {"num": ("geodawn_rad_u8.tif", 2), "den": ("geodawn_rad_u8.tif", 4)}),
    ("B_band6_TC", "band", {"b": "rad_total_count"}),
    ("B_band6_grad", "gradmag", {"b": "rad_total_count"}),
    ("B_elev", "band", {"b": "det_elev"}),
    ("B_slope_abs", "abs", {"b": "det_elev_slope"}),
    ("B_elev_gradmag", "gradmag", {"b": "det_elev"}),
    ("B_elev_residual", "residual", {"b": "det_elev", "sigma": 2500.0}),
    ("B_scarp_p900", "scarp", {"b": "det_elev_slope", "half": 900.0, "persist": 1900.0}),
    ("B_scarp_p300", "scarp", {"b": "det_elev_slope", "half": 300.0, "persist": 600.0}),
    ("B_scarp_fine", "scarp", {"b": "det_elev_slope", "half": 300.0, "persist": 300.0}),
    ("B_line_resp", "hessian", {"b": "det_elev", "sigma": 300.0}),
    ("B_st_coherence", "st", {"b": "det_elev", "key": "coherence", "sigma": 300.0}),
    ("B_st_anisotropy", "st", {"b": "det_elev", "key": "anisotropy", "sigma": 300.0}),
    ("B_st_ori_x", "st", {"b": "det_elev", "key": "ori_x", "sigma": 300.0}),
    ("B_st_ori_y", "st", {"b": "det_elev", "key": "ori_y", "sigma": 300.0}),
    ("B_st_coh_xgmag9", "st_cross", {"b": "det_elev", "sigma": 900.0}),
] + [(f"B_lidar_{n}", "lidar", {"i": i}) for i, n in enumerate(LIDAR_NAMES, 1)] + [
    ("B_az_deriv_000", "azderiv", {"b": "det_elev", "az": 0.0}),
    ("B_az_deriv_045", "azderiv", {"b": "det_elev", "az": 45.0}),
    ("B_az_deriv_090", "azderiv", {"b": "det_elev", "az": 90.0}),
    ("B_az_deriv_135", "azderiv", {"b": "det_elev", "az": 135.0}),
    ("B_paleo_geotherm_dist", "paleo", {}),
    ("B_spring_dist", "pointdist", {"f": "gdr_wellspring_in_footprint.csv"}),
    ("B_vent_dist", "pointdist", {"f": "gdr_volcanic_vents_in_footprint.csv"}),
    ("B_fault_centroid_dist", "pointdist", {"f": "gdr_qfaults_traces.csv",
                                            "row": "centroid_row", "col": "centroid_col"}),
]:
    _p(_n, "B", _b, **_kw)


LAYER_PLAN = [{"name": n, "view": v, "builder": b, "kwargs": k} for n, v, b, k in PLAN_ENTRIES]
LAYER_NAMES = [e["name"] for e in LAYER_PLAN]
VIEW_OF = {e["name"]: e["view"] for e in LAYER_PLAN}
INDEX_OF = {n: i for i, n in enumerate(LAYER_NAMES)}

if len(set(LAYER_NAMES)) != len(LAYER_NAMES):
    dupes = sorted({n for n in LAYER_NAMES if LAYER_NAMES.count(n) > 1})
    raise ValueError(f"duplicate layer names in LAYER_PLAN: {dupes}")
_N_A = sum(1 for v in VIEW_OF.values() if v == "A")
_N_B = sum(1 for v in VIEW_OF.values() if v == "B")
if (_N_A, _N_B) != (30, 44):
    raise ValueError(f"LAYER_PLAN must have 30 View-A and 44 View-B layers, found {_N_A}/{_N_B}")


def layer_index(name: str) -> int:
    """Slot of ``name`` in the stack.  Raises on any undeclared layer, by design."""
    try:
        return INDEX_OF[name]
    except KeyError:
        raise KeyError(
            f"undeclared layer {name!r}; add it to LAYER_PLAN in {__file__}"
        ) from None


# --------------------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------------------

def _finish(arr, valid):
    a = np.asarray(arr, dtype=np.float32)
    a[~valid] = np.nan
    return a


def _build(entry: dict, store: RawStore, valid: np.ndarray, shape) -> np.ndarray:
    b, kw = entry["builder"], entry["kwargs"]
    if b == "band":
        return _finish(store.band(kw["b"]), valid)
    if b == "negband":
        return _finish(-store.band(kw["b"]), valid)
    if b == "abs":
        return _finish(np.abs(store.band(kw["b"])), valid)
    if b == "gradmag":
        return _finish(Gtr.gradient_magnitude(store.band(kw["b"]), valid), valid)
    if b == "scarp":
        return _finish(Gtr.scarp_step(store.band(kw["b"]), valid, kw["half"], kw["persist"])[0], valid)
    if b == "regional":
        return regional_z(store.band(kw["b"]), valid, kw["sigma"])
    if b == "residual":
        a = store.band(kw["b"])
        return _finish(a - regional_z(a, valid, kw["sigma"]), valid)
    if b == "hessian":
        return _finish(Gtr.hessian_line(store.band(kw["b"]), valid, kw["sigma"]), valid)
    if b == "external":
        return _finish(store.external(kw["f"], kw["i"]), valid)
    if b == "ext_gradmag":
        return _finish(Gtr.gradient_magnitude(store.external(kw["f"], kw["i"]), valid), valid)
    if b == "ext_regional":
        return regional_z(store.external(kw["f"], kw["i"]), valid, kw["sigma"])
    if b == "ext_residual":
        a = store.external(kw["f"], kw["i"])
        return _finish(a - regional_z(a, valid, kw["sigma"]), valid)
    if b == "ratio":
        (nf, ni), (df, di) = kw["num"], kw["den"]
        num, den = store.external(nf, ni), store.external(df, di)
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.where(np.abs(den) > 1e-9, num / den, np.nan)
        return _finish(r, valid)
    if b == "st":
        return _finish(structure_tensor(store.band(kw["b"]), valid, kw["sigma"])[kw["key"]], valid)
    if b == "st_cross":
        # Coherence of the elevation structure tensor computed at a coarser integration
        # scale than the metric's own 300 m kernel.  This was the single best layer on
        # the habitat contrast last round (0.6081 blocked AUC), and the reason it is
        # worth carrying both scales: 900 m responds to through-going structures that
        # the 300 m tensor averages away.
        return _finish(structure_tensor(store.band(kw["b"]), valid, kw["sigma"])["coherence"], valid)
    if b == "lidar":
        return _finish(store.lidar(kw["i"]), valid)
    if b == "azderiv":
        return _finish(azimuthal_derivatives(store.band(kw["b"]), valid, (kw["az"],))[0], valid)
    if b == "paleo":
        tab = paleo_geothermal_table()
        return paleo_geothermal_distance(shape, valid, tab)
    if b == "pointdist":
        tab = _point_table(f"{EXTERNAL_DIR}/{kw['f']}", kw.get("row", "row"), kw.get("col", "col"))
        return distance_to_points(tab["row"], tab["col"], shape, valid)
    raise ValueError(f"unknown builder {b!r}")


# --------------------------------------------------------------------------------------
# stack construction
# --------------------------------------------------------------------------------------

def footprint(features: str = FEATURES) -> np.ndarray:
    """Pixels where every band of ``training_features.tif`` carries data."""
    import rasterio
    with rasterio.open(features) as src:
        valid = None
        for i in range(1, src.count + 1):
            a = src.read(i)
            ok = np.isfinite(a) & (a > -1e38)
            valid = ok if valid is None else (valid & ok)
    return np.asarray(valid, dtype=bool)


def build_stack(out_dir: str = "work/cache", features: str = FEATURES,
                external_dir: str = EXTERNAL_DIR, names=None, log=print) -> dict:
    """Compute every planned layer and stream it into ``<out_dir>/stack.f32``.

    One layer is resident at a time.  The stack file is a C-order float32 memmap of
    shape ``(n_layers, rows, cols)``; it is opened ``r+`` and written slot by slot, so
    peak RAM is a handful of grids rather than 3.6 GB.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    valid = footprint(features)
    shape = valid.shape
    plan = [e for e in LAYER_PLAN if names is None or e["name"] in set(names)]
    if names is not None:
        for n in names:
            if n not in INDEX_OF:
                raise KeyError(f"undeclared layer {n!r}")
    stack_path = out / "stack.f32"
    meta = {
        "shape": list(shape),
        "n_layers": len(plan),
        "layers": [e["name"] for e in plan],
        "view": [e["view"] for e in plan],
        "footprint_px": int(valid.sum()),
        "dtype": "float32",
    }
    np.save(out / "footprint.npy", valid)
    stack = np.memmap(stack_path, dtype=np.float32, mode="w+", shape=(len(plan), shape[0], shape[1]))
    with RawStore(features, external_dir) as store:
        for i, entry in enumerate(plan):
            arr = _build(entry, store, valid, shape)
            stack[i] = arr
            stack.flush()
            del arr
            log(f"  [{i + 1:>2}/{len(plan)}] {entry['view']} {entry['name']}", flush=True)
    stack.flush()
    del stack
    (out / "stack_meta.json").write_text(json.dumps(meta, indent=1))
    log(f"wrote {stack_path} ({len(plan)} layers, {meta['footprint_px']} footprint px)")
    return meta


def load_stack(out_dir: str = "work/cache", mode: str = "r") -> tuple[np.memmap, dict]:
    """Open the stack read-only (the default) and return it with its metadata."""
    out = Path(out_dir)
    meta = json.loads((out / "stack_meta.json").read_text())
    rows, cols = meta["shape"]
    mm = np.memmap(out / "stack.f32", dtype=np.float32, mode=mode,
                   shape=(meta["n_layers"], rows, cols))
    return mm, meta


def view_indices(meta: dict, view: str) -> list[int]:
    return [i for i, v in enumerate(meta["view"]) if v == view]
