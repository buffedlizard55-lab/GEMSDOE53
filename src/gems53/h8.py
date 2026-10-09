"""H8 (2026-10-08): gravity horizontal-gradient ridge features (Blakely & Simpson 1986 maxima method).

Input  : ONE label-free layer, band 13 of training_features.tif ("Isostatic gravity anomaly - gravity after
         compensating for topographic mass"). Nothing in this module reads labels.tif, the known-fault
         raster, or any fault-derived quantity, so the three output features are label-free by construction.
Output : three per-pixel features on the full grid
         R  ridge indicator (0/1): a horizontal-gradient maximum, strong enough, and away from invalid cells
         S  ridge strength: |grad g| on ridge pixels, 0 elsewhere
         D  distance to the nearest ridge pixel (pixels, capped at 60; the caller applies log1p)

Method (Blakely and Simpson 1986, Geophysics 51(7):1494-1498, "Approximating edges of source bodies from
magnetic or gravity anomalies"):
  1. |grad g| from np.gradient with 100 m spacing (invalid cells filled with the valid median first).
  2. Non-maximum suppression: a pixel is a ridge candidate if |grad g| is >= both neighbours along the gradient
     direction, quantised to 4 sectors (0, 45, 90, 135 degrees).
  3. Keep candidates with |grad g| >= the PCT-th percentile of |grad g| over the valid footprint (PCT = 90,
     fixed before the run) and at least BORDER px away from any invalid cell (kills the footprint-edge artefact).

Honest scope: this is a first-derivative edge locator on one potential-field layer. It does not know the
geology. A ridge can be a fault, a lithological contact or a survey artefact.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

PCT = 90.0
BORDER_PX = 3
CAP_PX = 60
CELL_M = 100.0


def valid_mask(raw: np.ndarray) -> np.ndarray:
    """Valid = finite and not the GeoDAWN/organizer sentinel (|v| >= 1e30 or the -3.4028e38 nodata)."""
    a = raw.astype(np.float64)
    return np.isfinite(a) & (np.abs(a) < 1e30)


def gravity_gradient_maxima(raw: np.ndarray, footprint: np.ndarray, pct: float = PCT,
                            border_px: int = BORDER_PX):
    """Return (R, S, D_px) on the grid of `raw`. `footprint` is the official footprint (bool).

    The ridge threshold is the percentile over footprint pixels only; outside the footprint R = 0.
    """
    valid = valid_mask(raw)
    g = np.where(valid, raw.astype(np.float64), np.nan)
    med = float(np.nanmedian(g[valid & footprint]))
    gf = np.where(valid, g, med)
    gy, gx = np.gradient(gf, CELL_M, CELL_M)
    mag = np.hypot(gx, gy)
    # gradient direction folded to [0, pi): the sign of the gradient does not matter for maxima
    ang = np.mod(np.arctan2(gy, gx), np.pi)
    sector = np.floor((ang + np.pi / 8) / (np.pi / 4)).astype(int) % 4  # 0:E-W 1:NE-SW 2:N-S 3:NW-SE
    # neighbour offsets (dy, dx) perpendicular to the edge, i.e. along the gradient
    offs = {0: (0, 1), 1: (1, 1), 2: (1, 0), 3: (1, -1)}
    is_max = np.ones(mag.shape, dtype=bool)
    H, W = mag.shape
    P = np.full((H + 2, W + 2), -np.inf)
    P[1:-1, 1:-1] = mag                      # -inf padding: the border cells can still be maxima
    for s, (dy, dx) in offs.items():
        sel = sector == s
        if not sel.any():
            continue
        plus = P[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]     # mag at (y+dy, x+dx)
        minus = P[1 - dy:1 - dy + H, 1 - dx:1 - dx + W]    # mag at (y-dy, x-dx)
        is_max &= ~sel | ((mag >= plus) & (mag >= minus))
    fp = footprint.astype(bool)
    thr = float(np.percentile(mag[fp & valid], pct))
    # distance (px) to the nearest invalid cell; ridges closer than border_px are dropped
    dist_invalid = ndimage.distance_transform_edt(valid)
    R = (is_max & (mag >= thr) & fp & (dist_invalid > border_px)).astype(np.float32)
    S = np.where(R > 0, mag, 0.0).astype(np.float32)
    if R.any():
        D = np.minimum(ndimage.distance_transform_edt(R == 0), CAP_PX).astype(np.float32)
    else:
        D = np.full(R.shape, CAP_PX, dtype=np.float32)
    return R, S, D, thr


def h8_feature_matrix(raw: np.ndarray, footprint: np.ndarray):
    """Footprint-row matrix (N_fp, 3): [R, S, log1p(D)] in row-major footprint order, plus the threshold."""
    R, S, D, thr = gravity_gradient_maxima(raw, footprint)
    cols = np.column_stack([R[footprint], S[footprint], np.log1p(D[footprint])]).astype(np.float32)
    return cols, R, thr
