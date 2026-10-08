"""Label-free magnetic lineament candidate: multi-scale Hessian ridge/valley centrelines, packed into dots.

Hypothesis H2 (see docs/research/hypotheses.md): linear magnetic discontinuities on the reduced-to-pole
field (GeoDAWN band 2) mark structural lineaments. Bright ridges and dark valleys are both kept (a
hydrothermally altered, demagnetised fault zone is a dark linear low; a magnetite-rich dyke or
juxtaposition contact is a bright linear high). The score is computed from band 2 ALONE. It never reads
the fault labels, so it cannot leak them. The only catalogue use is the pixel-exact mask of faults that
are visible at prediction time (the same rule as every other arm).

Pipeline (all steps are deterministic):
  1. band-pass: subtract a 1.5 km normalised-convolution trend (finite footprint pixels only);
  2. scale-normalised Hessian eigenvalues at sigma in {1.5, 2.5, 3.5} px (150-350 m);
  3. line strength L = max over sigma of max(ridge, valley); across-line normal from the eigenvector;
  4. non-maximum suppression across the normal -> 1-px centrelines;
  5. Poisson-disk packing: take centreline pixels by descending L and accept a pixel only if it is
     at least `r_px` (2.8 px = 280 m) from every accepted dot. Within the 300 m kernel, closer dots
     double-count the same truth (the max in TP_w), so spacing is what keeps FP mass useful.
  6. emission = 1.0 on accepted dots, 0 elsewhere inside the footprint.

Nothing in this module reads labels. `exclude` is the set of catalogue pixels that may not be emitted.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

SIGMAS_PX = (1.5, 2.5, 3.5)
DETREND_SIGMA_PX = 15.0
R_PACK_PX = 2.8  # team's d2.8 family spacing (Poisson-disk, >= 280 m)


def normalised_detrend(field: np.ndarray, valid: np.ndarray, sigma: float = DETREND_SIGMA_PX) -> np.ndarray:
    """field - (regional trend), with the trend estimated only from valid pixels (normalised convolution)."""
    w = valid.astype(np.float64)
    x = np.where(valid, field, 0.0).astype(np.float64)
    num = ndimage.gaussian_filter(x * w, sigma, mode="reflect")
    den = ndimage.gaussian_filter(w, sigma, mode="reflect")
    trend = np.divide(num, den, out=np.zeros_like(num), where=den > 1e-6)
    out = np.where(valid, field - trend, 0.0)
    return out.astype(np.float64)


def line_strength(x: np.ndarray, sigmas=SIGMAS_PX):
    """Return (L, theta_n, polarity) on the grid of x.

    L            : max over sigma of scale-normalised max(ridge, valley) strength (>= 0)
    theta_n      : across-line normal angle in radians (x = column, y = row)
    polarity     : +1 bright ridge, -1 dark valley, 0 none
    """
    H, W = x.shape
    best = np.zeros((H, W), dtype=np.float64)
    theta = np.zeros((H, W), dtype=np.float64)
    pol = np.zeros((H, W), dtype=np.int8)
    for s in sigmas:
        s2 = s * s
        hyy = ndimage.gaussian_filter(x, s, order=(2, 0), mode="reflect") * s2  # d2/dy2 (rows)
        hxx = ndimage.gaussian_filter(x, s, order=(0, 2), mode="reflect") * s2  # d2/dx2 (cols)
        hxy = ndimage.gaussian_filter(x, s, order=(1, 1), mode="reflect") * s2
        m = 0.5 * (hxx + hyy)
        r = np.sqrt((0.5 * (hxx - hyy)) ** 2 + hxy ** 2)
        lam_plus = m + r
        lam_minus = m - r
        ridge = np.maximum(-lam_minus, 0.0)   # bright, sharply negative across-line curvature
        valley = np.maximum(lam_plus, 0.0)    # dark, sharply positive across-line curvature
        s_strength = np.maximum(ridge, valley)
        th_plus = 0.5 * np.arctan2(2.0 * hxy, hxx - hyy)  # eigenvector direction of lam_plus (x=col, y=row)
        th_n = np.where(ridge >= valley, th_plus + 0.5 * math.pi, th_plus)  # normal to a ridge = lam_minus vector
        upd = s_strength > best
        best = np.where(upd, s_strength, best)
        theta = np.where(upd, th_n, theta)
        pol = np.where(upd, np.where(ridge >= valley, 1, -1), pol).astype(np.int8)
    return best, theta, pol


def nms_centrelines(L: np.ndarray, theta_n: np.ndarray) -> np.ndarray:
    """Keep pixels whose L is >= the bilinear samples one pixel either side along the normal."""
    H, W = L.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    dx, dy = np.cos(theta_n), np.sin(theta_n)
    up = ndimage.map_coordinates(L, [yy + dy, xx + dx], order=1, mode="nearest")
    dn = ndimage.map_coordinates(L, [yy - dy, xx - dx], order=1, mode="nearest")
    return (L > 0) & (L >= up) & (L >= dn)


def poisson_pack(order_rc: np.ndarray, n_target: int, r_px: float = R_PACK_PX) -> np.ndarray:
    """Greedy Poisson-disk selection over candidate (row, col) pairs already sorted best-first.

    Accepts a candidate only if it is >= r_px from every accepted dot. Returns an (n, 2) int array.
    """
    cell = max(1, int(math.ceil(r_px)))
    grid: dict[tuple[int, int], list[tuple[int, int]]] = {}
    acc: list[tuple[int, int]] = []
    r2 = r_px * r_px
    for r, c in order_rc:
        r = int(r)
        c = int(c)
        cy, cx = r // cell, c // cell
        ok = True
        for gy in (cy - 1, cy, cy + 1):
            for gx in (cx - 1, cx, cx + 1):
                for (ar, ac) in grid.get((gy, gx), ()):
                    if (ar - r) * (ar - r) + (ac - c) * (ac - c) < r2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            acc.append((r, c))
            grid.setdefault((cy, cx), []).append((r, c))
            if len(acc) >= n_target:
                break
    return np.asarray(acc, dtype=np.int64).reshape(-1, 2)


def ridge_pack_emission(L: np.ndarray, centre: np.ndarray, candidate_ok: np.ndarray, n_target: int,
                        r_px: float = R_PACK_PX) -> tuple[np.ndarray, dict]:
    """Binary dot emission (1.0 on accepted dots, 0 elsewhere) from centreline candidates.

    candidate_ok: boolean grid of pixels that MAY be emitted (footprint minus any pixel-exact mask).
    """
    cand = centre & candidate_ok & (L > 0)
    rr, cc = np.nonzero(cand)
    vals = L[rr, cc]
    order = np.argsort(-vals, kind="stable")
    rc = np.stack([rr[order], cc[order]], axis=1)
    picked = poisson_pack(rc, n_target, r_px)
    out = np.zeros(L.shape, dtype=np.float32)
    if picked.size:
        out[picked[:, 0], picked[:, 1]] = 1.0
    info = {"n_centreline_candidates": int(cand.sum()), "n_selected": int(picked.shape[0]),
            "n_target": int(n_target), "r_px": float(r_px)}
    return out, info


def ridge_fields(rtp: np.ndarray, footprint: np.ndarray):
    """Compute (L, theta_n, polarity, detrended field) from a raw RTP grid (NaN = no data)."""
    valid = footprint & np.isfinite(rtp)
    det = normalised_detrend(rtp, valid)
    L, th, pol = line_strength(det)
    L = np.where(footprint, L, 0.0)
    return L, th, pol, det
