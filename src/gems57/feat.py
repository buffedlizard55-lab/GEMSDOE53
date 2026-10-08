"""GEMS57 feature library — scale-free local transforms for two-view co-training.

Design rules (all enforced in code, checked in tests):
  * every feature is *local and scale-free* (no absolute elevation, no absolute band value), so
    a model fitted on map-known faults transfers to unmapped ground instead of learning
    "is this a mountain" (the failure mode `knowledge/03` records);
  * nothing label-derived may enter: no distance-to-catalogue, no SGMC mask, no prior file;
  * the two views are disjoint by *physics*, not by convenience:
      View A = potential-field + subsurface (magnetics, gravity, strain, seismicity,
               conductivity, depth-to-basement, upward-continued TMI);
      View B = surface (DEM-derived transforms + radiometric K/Th/U/TC and their ratios +
               LiDAR-derived scarp aggregates).
    Band 6 of `training_features.tif` is tagged `magnetic_data` ("tilt angle or total curvature")
    but measures as the GeoDAWN **total-count radiometric** grid (Spearman +1.000 against the
    external TC layer, min 2.95 — impossible for a tilt angle).  It is therefore assigned to
    View B.  Evidence: `work/forensics_real.json` in this session and `IR-52-019`.

Transform names:
  ``lz``  local z-score inside a 21x21 window (anomaly contrast)
  ``tg``  tilt gradient = |grad(smooth(layer))| / (|lz| + 1)  (dimensionless edge/lineament)
  ``lzg`` |grad(lz)|                                            (edge of the local anomaly)
  ``curv``  Laplacian of the detrended-elevation layer (profile-curvature proxy, DEM only)
  ``rgt``  ridge/valley top-hat response of the detrended-elevation layer (DEM only)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import rasterio
from scipy import ndimage

NODATA_THRESHOLD = -1e37
HALO = 16                    # pixels of context needed by every transform (see tests)
LZ_WINDOW = 21               # local z-score window, pixels
NODATA = -3.4028234663852886e+38

VIEW_A_LAYERS = {
    "b1": ("mag_anom", "training"),
    "b2": ("rtp", "training"),
    "b3": ("tmi_hg", "training"),
    "b9": ("tmi_vg", "training"),
    "b14": ("tmi", "training"),
    "b5": ("iso_grav_slope", "training"),
    "b11": ("iso_grav_vg", "training"),
    "b13": ("iso_grav_anom", "training"),
    "b18": ("iso_grav_hg", "training"),
    "b4": ("geod_2ndinv", "training"),
    "b7": ("geod_shearrate", "training"),
    "b8": ("geod_dilaterate", "training"),
    "b15": ("depth_to_base_surf", "training"),
    "b17": ("cond_surf", "training"),
    "b10": ("dist_to_eq", "training"),
    "b16": ("eq_density", "training"),
    "ext4": ("tmi_uc150", "external"),
}
VIEW_B_LAYERS = {
    "b12": ("det_elev", "training"),
    "b19": ("det_elev_slope", "training"),
    "b6": ("radiometric_TC", "training"),
    "rad1": ("K", "external"),
    "rad2": ("Th", "external"),
    "rad3": ("U", "external"),
    "ext1": ("Th_over_K", "external"),
    "ext2": ("U_over_K", "external"),
    "ext3": ("U_over_Th", "external"),
}
LIDAR_AGGREGATES = ("lidmax", "lidmean", "lidcov")

TRAINING_BAND = {  # layer id -> 1-based band index in data/training_features.tif
    "b1": 1, "b2": 2, "b3": 3, "b4": 4, "b5": 5, "b6": 6, "b7": 7, "b8": 8, "b9": 9,
    "b10": 10, "b11": 11, "b12": 12, "b13": 13, "b14": 14, "b15": 15, "b16": 16,
    "b17": 17, "b18": 18, "b19": 19,
}
EXTERNAL_LAYER = {  # layer id -> (file, 1-based band)
    "rad1": ("data/external/geodawn_rad_u8.tif", 1),
    "rad2": ("data/external/geodawn_rad_u8.tif", 2),
    "rad3": ("data/external/geodawn_rad_u8.tif", 3),
    "ext1": ("data/external/geodawn_extensions_u8.tif", 1),
    "ext2": ("data/external/geodawn_extensions_u8.tif", 2),
    "ext3": ("data/external/geodawn_extensions_u8.tif", 3),
    "ext4": ("data/external/geodawn_extensions_u8.tif", 4),
}
LIDAR_PATH = "data/external/lidar_scarp_features_u8.tif"


def feature_names() -> list[str]:
    """Names in exactly the order `tile_features` stacks them (asserted at runtime)."""
    out = []
    for layer in list(VIEW_A_LAYERS) + list(VIEW_B_LAYERS):
        for t in ("lz", "tg", "lzg"):
            out.append(f"{layer}_{t}")
        if layer == "b12":                      # DEM-only extras, emitted right after their layer
            out += ["b12_curv", "b12_rgt"]
    out += list(LIDAR_AGGREGATES)
    return out


VIEW_OF_FEATURE = {}
for _l in VIEW_A_LAYERS:
    for _t in ("lz", "tg", "lzg"):
        VIEW_OF_FEATURE[f"{_l}_{_t}"] = "A"
for _l in VIEW_B_LAYERS:
    for _t in ("lz", "tg", "lzg"):
        VIEW_OF_FEATURE[f"{_l}_{_t}"] = "B"
VIEW_OF_FEATURE["b12_curv"] = "B"
VIEW_OF_FEATURE["b12_rgt"] = "B"
for _k in LIDAR_AGGREGATES:
    VIEW_OF_FEATURE[_k] = "B"


class RasterSource:
    """Reads a full-grid window and returns the requested layers, NaN where nodata.

    Dataset handles are opened once and reused: a full-grid pass makes ~30 reads per tile, and
    re-opening the 419 MB feature stack per read costs more than the maths itself.
    """

    def __init__(self, training_path: str = "data/training_features.tif") -> None:
        self.training_path = training_path
        self._ds: dict[str, object] = {}

    def _open(self, path: str):
        if path not in self._ds:
            self._ds[path] = rasterio.open(path)
        return self._ds[path]

    def close(self) -> None:
        for ds in self._ds.values():
            ds.close()
        self._ds.clear()

    def shape(self) -> tuple[int, int]:
        ds = self._open(self.training_path)
        return int(ds.height), int(ds.width)

    def _read_training(self, band: int, win) -> np.ndarray:
        a = self._open(self.training_path).read(band, window=win).astype(np.float32)
        a[a <= NODATA_THRESHOLD] = np.nan
        return a

    def _read_external(self, path: str, band: int, win) -> np.ndarray:
        ds = self._open(path)
        a = ds.read(band, window=win).astype(np.float32)
        a[a == 0] = np.nan          # the u8 mirrors use 0 as nodata
        if ds.nodata is not None:
            a[a == ds.nodata] = np.nan
        return a

    def read_layer(self, layer: str, win) -> np.ndarray:
        if layer in TRAINING_BAND:
            return self._read_training(TRAINING_BAND[layer], win)
        if layer in EXTERNAL_LAYER:
            p, b = EXTERNAL_LAYER[layer]
            return self._read_external(p, b, win)
        if layer in LIDAR_AGGREGATES:
            return self._read_lidar(layer, win)
        raise KeyError(layer)

    def _read_lidar(self, which: str, win) -> np.ndarray:
        ds = self._open(LIDAR_PATH)
        n = ds.count
        a = ds.read(window=win).astype(np.float32)
        cov = (a > 0).any(axis=0)
        if which == "lidmax":
            out = np.where(cov, a.max(axis=0), np.nan)
        elif which == "lidmean":
            with np.errstate(invalid="ignore"):
                out = np.where(cov, np.nansum(a, axis=0) / np.maximum((a > 0).sum(axis=0), 1), np.nan)
        elif which == "lidcov":
            out = np.where(cov, ((a > 0).sum(axis=0) / float(n)).astype(np.float32), np.nan)
        else:
            raise KeyError(which)
        return out.astype(np.float32)


def _local_z(a: np.ndarray, window: int = LZ_WINDOW) -> np.ndarray:
    m = np.isfinite(a)
    v = np.where(m, a, 0.0)
    cnt = ndimage.uniform_filter(m.astype(np.float32), size=window)
    mu = ndimage.uniform_filter(v, size=window) / np.maximum(cnt, 1e-6)
    sq = ndimage.uniform_filter(v * v, size=window) / np.maximum(cnt, 1e-6)
    sd = np.sqrt(np.maximum(sq - mu * mu, 0.0))
    z = (np.where(m, a, mu) - mu) / np.maximum(sd, 1e-6)
    return np.where(m, z, np.nan).astype(np.float32)


def _gradmag(a: np.ndarray) -> np.ndarray:
    sm = ndimage.uniform_filter(np.nan_to_num(a, nan=0.0), size=3)
    gy = ndimage.sobel(sm, axis=0, mode="nearest")
    gx = ndimage.sobel(sm, axis=1, mode="nearest")
    return np.hypot(gx, gy).astype(np.float32)


LZ_CLIP = 10.0          # |local z| beyond 10 is a divide-by-tiny-roundoff artefact, not geology
GRAD_LOG = True         # log1p-compress gradient magnitudes (heavy-tailed across the grid)


def _transforms(a: np.ndarray) -> dict[str, np.ndarray]:
    z = np.clip(_local_z(a), -LZ_CLIP, LZ_CLIP)
    g = _gradmag(np.nan_to_num(a, nan=0.0))
    out = {
        "lz": z,
        "tg": g / (np.abs(z) + 1.0),
        "lzg": _gradmag(np.nan_to_num(z, nan=0.0)),
    }
    if GRAD_LOG:
        for k in ("tg", "lzg"):
            out[k] = np.log1p(out[k])
    return {k: np.where(np.isfinite(a), np.clip(v, -50.0, 50.0), np.nan).astype(np.float32)
            for k, v in out.items()}


def tile_features(src: RasterSource, window, pad: int = HALO,
                  layers: tuple[str, ...] | None = None) -> np.ndarray:
    """Compute the feature cube for one window, returning float32 (n_features, h, w)."""
    if layers is None:
        layers = tuple(VIEW_A_LAYERS) + tuple(VIEW_B_LAYERS) + LIDAR_AGGREGATES
    full = rasterio.windows.Window(window.col_off - pad, window.row_off - pad,
                                  window.width + 2 * pad, window.height + 2 * pad)
    # clip to the raster so edge tiles still work
    H, W = src.shape()
    r0, c0 = max(0, int(full.row_off)), max(0, int(full.col_off))
    r1, c1 = min(H, int(full.row_off + full.height)), min(W, int(full.col_off + full.width))
    read_win = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
    off_r = int(window.row_off) - r0
    off_c = int(window.col_off) - c0
    h, w = int(window.height), int(window.width)
    feats = []
    names = []
    for layer in layers:
        a = src.read_layer(layer, read_win)
        if layer in LIDAR_AGGREGATES:
            # already an aggregate statistic: used raw, no further transform
            feats.append(a[off_r:off_r + h, off_c:off_c + w])
            names.append(layer)
            continue
        tr = _transforms(a)
        for t in ("lz", "tg", "lzg"):
            feats.append(tr[t][off_r:off_r + h, off_c:off_c + w])
            names.append(f"{layer}_{t}")
        if layer == "b12":
            # profile-curvature proxy and ridge/valley top-hat of the detrended DEM
            sm = ndimage.gaussian_filter(np.nan_to_num(a, nan=0.0), 1.5)
            curv = ndimage.laplace(sm)
            k = np.ones((9, 9), np.float32); k /= k.sum()
            openv = ndimage.grey_opening(sm, size=(9, 9))
            closev = ndimage.grey_closing(sm, size=(9, 9))
            rgt = (sm - openv) + (closev - sm)
            for nm, arr in (("curv", curv), ("rgt", rgt)):
                feats.append(np.where(np.isfinite(a), arr, np.nan).astype(np.float32)
                             [off_r:off_r + h, off_c:off_c + w])
                names.append(f"{layer}_{nm}")
    assert names == feature_names(), (len(names), len(feature_names()))
    return np.stack(feats).astype(np.float32)
