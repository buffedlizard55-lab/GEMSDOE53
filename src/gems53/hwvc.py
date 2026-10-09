"""H53-HWVC: hanging-wall vector concordance (label-free feature) + spaced-dot decoder + gate v2 helpers.

Pre-registered in docs/research/preregistration-2026-10-09-hwvc.md (committed before any run).

Physics. Across a Basin-and-Range normal fault the hanging wall is down-dropped and filled with sediment, so four
independent stack bands should point to the SAME "down side":
    band 12 det_elev            lower on the hanging wall      -> down-side vector  = -grad
    band 13 iso_grav_anom       lower (low-density fill)        -> down-side vector  = -grad
    band 17 cond_surf           higher (wet, clay-rich fill)    -> down-side vector  = +grad
    band 15 depth_to_base_surf  deeper basement                 -> down-side vector  = +grad
For each band b the unit down-side vector u_b is weighted by w_b = within-footprint percentile rank of |grad b|
(scale-free, in [0,1]). Channels per Gaussian scale sigma:
    R = |sum_b w_b u_b| / 4            strength x concordance, in [0,1]
    C = |sum_b w_b u_b| / sum_b w_b    concordance only (circular resultant length), in [0,1]
    nmsd = log1p(min(distance to the non-maximum-suppressed ridge of R, 60))  (Canny-style, along the mean direction)
No label, catalogue or fault information enters these channels.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

# 1-based band numbers in training_features.tif (descriptions verified from the file's band tags)
HWVC_BANDS = ((12, -1.0, "det_elev"), (13, -1.0, "iso_grav_anom"), (17, +1.0, "cond_surf"),
              (15, +1.0, "depth_to_base_surf"))
SIGMAS = (2.0, 5.0)
NMS_PERCENTILE = 80.0
DIST_CAP = 60


def fill_nearest(a: np.ndarray) -> np.ndarray:
    """Replace NaN by the value of the nearest finite pixel (avoids gradient artefacts at holes/edges)."""
    bad = ~np.isfinite(a)
    if not bad.any():
        return a.astype(np.float32, copy=True)
    idx = ndimage.distance_transform_edt(bad, return_distances=False, return_indices=True)
    return a[tuple(idx)].astype(np.float32)


def percentile_rank(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Within-mask percentile rank in [0,1]; 0 outside the mask."""
    out = np.zeros(x.shape, dtype=np.float32)
    v = x[mask]
    order = np.argsort(v, kind="stable")
    r = np.empty(v.size, dtype=np.float32)
    r[order] = np.arange(v.size, dtype=np.float32) / max(v.size - 1, 1)
    out[mask] = r
    return out


def nms_ridge(R: np.ndarray, ux: np.ndarray, uy: np.ndarray, mask: np.ndarray, pct: float = NMS_PERCENTILE) -> np.ndarray:
    """Canny-style non-maximum suppression of R across the mean down-side direction (ux, uy) (x=col, y=row)."""
    H, W = R.shape
    # quantise the mean direction to the 8-neighbourhood (always a non-zero step)
    ang = np.arctan2(uy, ux)
    dx = np.rint(np.cos(ang)).astype(np.int32)
    dy = np.rint(np.sin(ang)).astype(np.int32)
    del ang
    yy, xx = np.indices((H, W), dtype=np.int32)
    y1 = np.clip(yy + dy, 0, H - 1); x1 = np.clip(xx + dx, 0, W - 1)
    y2 = np.clip(yy - dy, 0, H - 1); x2 = np.clip(xx - dx, 0, W - 1)
    del yy, xx, dx, dy
    is_max = (R >= R[y1, x1]) & (R >= R[y2, x2])
    thr = np.percentile(R[mask], pct)
    return is_max & (R > thr) & mask


def hwvc_channels(stack_bands: dict, fp: np.ndarray) -> tuple[dict, dict]:
    """stack_bands: {band_number: 2-D float array with NaN for nodata}. Returns ({name: 2-D float32}, meta)."""
    chans, meta = {}, {"bands": [b for b, _, _ in HWVC_BANDS], "signs": [s for _, s, _ in HWVC_BANDS],
                       "sigmas": list(SIGMAS), "nms_percentile": NMS_PERCENTILE}
    filled = {b: fill_nearest(stack_bands[b]) for b, _, _ in HWVC_BANDS}
    for sg in SIGMAS:
        sx = np.zeros(fp.shape, dtype=np.float32)
        sy = np.zeros(fp.shape, dtype=np.float32)
        wsum = np.zeros(fp.shape, dtype=np.float32)
        for b, sign, _ in HWVC_BANDS:
            gy = ndimage.gaussian_filter(filled[b], sg, order=(1, 0)).astype(np.float32)  # d/drow
            gx = ndimage.gaussian_filter(filled[b], sg, order=(0, 1)).astype(np.float32)  # d/dcol
            mag = np.hypot(gx, gy)
            w = percentile_rank(mag, fp)
            with np.errstate(invalid="ignore", divide="ignore"):
                ux = np.where(mag > 0, sign * gx / mag, 0.0).astype(np.float32)
                uy = np.where(mag > 0, sign * gy / mag, 0.0).astype(np.float32)
            sx += w * ux
            sy += w * uy
            wsum += w
            del gx, gy, mag, w, ux, uy
        res = np.hypot(sx, sy)
        R = (res / len(HWVC_BANDS)).astype(np.float32)
        with np.errstate(invalid="ignore", divide="ignore"):
            C = np.where(wsum > 0, res / wsum, 0.0).astype(np.float32)
        ridge = nms_ridge(R, sx, sy, fp)
        d = ndimage.distance_transform_edt(~ridge) if ridge.any() else np.full(fp.shape, 1e6)
        nmsd = np.log1p(np.minimum(d, DIST_CAP)).astype(np.float32)
        tag = f"s{int(sg)}"
        chans[f"hwvc_R_{tag}"] = np.where(fp, R, np.nan).astype(np.float32)
        chans[f"hwvc_C_{tag}"] = np.where(fp, C, np.nan).astype(np.float32)
        chans[f"hwvc_nmsd_{tag}"] = np.where(fp, nmsd, np.nan).astype(np.float32)
        meta[f"ridge_px_{tag}"] = int(ridge.sum())
        del sx, sy, wsum, res, R, C, ridge, d, nmsd
    return chans, meta


# ------------------------------------------------------------------------------------------------
# Decoder D-S (pre-registered): flank prune, greedy spaced dots, fixed N, binary
# ------------------------------------------------------------------------------------------------

def spaced_dots(score: np.ndarray, candidates: np.ndarray, n_dots: int, min_sep: float = 2.8,
                prefilter: int = 600_000) -> np.ndarray:
    """Greedy dots in decreasing score; a candidate is kept iff no kept dot lies within Euclidean distance
    <= min_sep. Stops at n_dots. Returns a boolean (H, W) dot mask. Ties are broken by flat index (stable)."""
    H, W = score.shape
    rr, cc = np.nonzero(candidates)
    vals = score[rr, cc].astype(np.float64)
    k = min(prefilter, vals.size)
    while True:
        top = np.argpartition(-vals, k - 1)[:k] if k < vals.size else np.arange(vals.size)
        order = top[np.argsort(-vals[top], kind="stable")]
        R = int(np.floor(min_sep))
        offs = [(dy, dx) for dy in range(-R, R + 1) for dx in range(-R, R + 1) if dy * dy + dx * dx <= min_sep * min_sep]
        blocked = np.zeros((H, W), dtype=bool)
        dots = np.zeros((H, W), dtype=bool)
        n = 0
        for i in order:
            y, x = int(rr[i]), int(cc[i])
            if blocked[y, x]:
                continue
            dots[y, x] = True
            n += 1
            if n >= n_dots:
                break
            for dy, dx in offs:
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W:
                    blocked[yy, xx] = True
        if n >= n_dots or k >= vals.size:
            return dots
        k = min(vals.size, k * 2)


def decoder_ds(score: np.ndarray, fp: np.ndarray, known: np.ndarray, n_dots: int = 40_000,
               flank_px: float = 2.0, min_sep: float = 2.8) -> np.ndarray:
    """D-S: exclude pixels within flank_px of `known` faults, then spaced_dots. Returns float32 0/1 emission."""
    d = ndimage.distance_transform_edt(~known) if known.any() else np.full(fp.shape, 1e6)
    cand = fp & (d > flank_px) & np.isfinite(score)
    dots = spaced_dots(score, cand, n_dots, min_sep)
    return dots.astype(np.float32)


# ------------------------------------------------------------------------------------------------
# Gate v2 helpers (pre-registered D-1)
# ------------------------------------------------------------------------------------------------

def disk_dilate(mask: np.ndarray, r: float = 3.0) -> np.ndarray:
    """True within Euclidean distance <= r of any True pixel."""
    if not mask.any():
        return np.zeros(mask.shape, dtype=bool)
    return ndimage.distance_transform_edt(~mask) <= r


def registry_dots(arr: np.ndarray, fp: np.ndarray, k_match: int, dense_frac: float = 0.05):
    """Registry raster -> (dot mask, mode). value>0 inside footprint; if > dense_frac of footprint, top-k_match."""
    a = np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    pos = (a > 0) & fp
    npos = int(pos.sum())
    fp_px = int(fp.sum())
    if npos <= dense_frac * fp_px:
        return pos, "positive", npos
    v = a[fp]
    k = min(k_match, v.size)
    thr = np.partition(v, v.size - k)[v.size - k]
    dots = fp & (a >= thr) & (a > 0)
    return dots, "topk", npos
