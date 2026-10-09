"""Core library for GEMSDOE53: data loading, leak-free features, the official metric, and submission IO.

Every constant below is traceable to the official rules / data description (see registry/sources.json):
  * distance-weighted Tversky index, alpha=0.2, beta=0.8, triangular kernel with 300 m support
    -> drivendata problem-description page, "Performance metric" section.
  * EPSG:32611, 100 m, float32, single band, same bounds, values in [0, 1]
    -> drivendata problem-description page, "Submission format" section; NLR rules PDF section 3.3.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

ALPHA = 0.2
BETA = 0.8
R_PX = 3          # 300 m support / 100 m pixels
PX_M = 100.0
EPS = 1e-9
FEATURE_NODATA_THRESHOLD = -1e30  # the feature stack's nodata is -3.4028e38
DIST_CAP_PX = 60  # same cap as the template's log1p(min(dist, 60)) column

# ----------------------------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------------------------


@dataclass
class Inputs:
    H: int
    W: int
    transform: object
    crs: object
    band_names: list
    feats: np.ndarray        # (N_fp, F) float32, footprint pixels only, row-major order
    fp_idx: np.ndarray       # (H, W) int32, index into feats or -1 outside footprint
    fp: np.ndarray           # (H, W) bool footprint mask
    cat: np.ndarray          # (H, W) bool, known (USGS/INGENIOUS) fault pixels, inside footprint


def load_inputs(features_path: str, labels_path: str, footprint_path: str) -> Inputs:
    """Load the feature stack, labels and the OFFICIAL footprint.

    The footprint is the finite-pixel mask of the organizer's sample_submission.tif (5,167,373 px in the
    provided data). It is NOT 'all feature bands finite' (that gives 5,165,840 px and drops 4,613 official
    cells, which would leave official in-footprint cells NaN). Features may still be NaN inside the footprint
    (sentinel cells in some bands); the gradient-boosting model handles missing values natively.
    """
    import rasterio

    with rasterio.open(footprint_path) as src:
        sub = src.read(1)
    fp = np.isfinite(sub)
    with rasterio.open(features_path) as src:
        arr = src.read().astype(np.float32)  # (F, H, W)
        names = [src.tags(i).get("description", f"band{i}") for i in range(1, src.count + 1)]
        transform, crs = src.transform, src.crs
        nod = src.nodata
    arr[arr < FEATURE_NODATA_THRESHOLD] = np.nan
    if nod is not None and np.isfinite(nod):
        arr[arr == nod] = np.nan
    F, H, W = arr.shape
    assert fp.shape == (H, W), "footprint template does not match feature grid"
    with rasterio.open(labels_path) as src:
        lab = src.read(1)
    cat = (lab == 1) & fp
    fp_idx = np.full((H, W), -1, dtype=np.int32)
    fp_idx[fp] = np.arange(int(fp.sum()), dtype=np.int32)
    feats = np.ascontiguousarray(arr[:, fp].T)  # (N, F), NaN where a band is sentinel
    del arr
    return Inputs(H, W, transform, crs, names, feats, fp_idx, fp, cat)


def fine_and_quad_blocks(H: int, W: int):
    """4x4 fine blocks (cross-fit units) and 2x2 quadrants (holdout folds). Returns (fine, quad) int8 arrays."""
    rows = np.array_split(np.arange(H), 4)
    cols = np.array_split(np.arange(W), 4)
    fine = np.zeros((H, W), dtype=np.int8)
    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            fine[np.ix_(r, c)] = i * 4 + j
    quad = ((fine // 4) // 2) * 2 + ((fine % 4) // 2)
    return fine, quad.astype(np.int8)


def segment_folds(cat: np.ndarray, K: int = 5, seed: int = 53):
    """Whole-fault-segment holdout. Segments = 8-connected components of the known-fault raster.

    Returns (fold_grid int8: fold id 0..K-1 for known-fault pixels, -1 elsewhere; n_segments; label grid).
    Segments are assigned to folds by a seeded permutation (balanced by segment count, not by pixels).
    """
    L, n = ndimage.label(cat, structure=np.ones((3, 3), dtype=int))
    rng = np.random.default_rng(seed)
    fold_of_seg = rng.permutation(np.arange(n) % K)
    fold_grid = np.full(cat.shape, -1, dtype=np.int8)
    m = L > 0
    fold_grid[m] = fold_of_seg[L[m] - 1].astype(np.int8)
    return fold_grid, n, L


def buffer_zone(hidden: np.ndarray, px: int = 10) -> np.ndarray:
    """True within `px` pixels (default 10 px = 1 km) of any withheld fault pixel; excluded from training."""
    if not hidden.any():
        return np.zeros(hidden.shape, dtype=bool)
    return dist_to(hidden) <= px


def dist_to(mask: np.ndarray) -> np.ndarray:
    """Euclidean distance (pixels) from every pixel to the nearest True pixel of `mask`."""
    if not mask.any():
        return np.full(mask.shape, np.float32(1e6), dtype=np.float32)
    return ndimage.distance_transform_edt(~mask).astype(np.float32)


def log_dist_feature(d_px: np.ndarray) -> np.ndarray:
    return np.log1p(np.minimum(d_px, DIST_CAP_PX)).astype(np.float32)


def crossfit_distance_grid(visible: np.ndarray, fine: np.ndarray) -> np.ndarray:
    """Learn-predict separation for the distance-to-known-faults feature.

    `visible` = the known faults that are allowed to be used at prediction time for this fold
    (for a holdout fold: all catalogue pixels EXCEPT the withheld segments).
    Each pixel's feature is the distance to `visible` computed WITHOUT the pixel's own fine block
    (4x4 blocks). A training positive therefore never sees its own label through the feature.
    Returns log1p(min(d_px, 60)) as float32 on the full grid.
    """
    H, W = visible.shape
    out = np.zeros((H, W), dtype=np.float32)
    for b in range(16):
        blk = fine == b
        if not blk.any():
            continue
        d = dist_to(visible & (fine != b))
        out[blk] = log_dist_feature(d[blk])
    return out


def leaky_distance_grid(cat: np.ndarray) -> np.ndarray:
    """DELIBERATELY LEAKY reproduction of the GEMSDOE29 defect (used only in the leakage canary/ablation)."""
    return log_dist_feature(dist_to(cat))


# ----------------------------------------------------------------------------------------------
# H2 feature: label-free magnetic ridge (multi-scale Hessian). Uses ONLY the reduced-to-pole band.
# ----------------------------------------------------------------------------------------------

RIDGE_SIGMAS_PX = (1.0, 2.0, 3.0)  # 100, 200, 300 m


def ridge_feature(band: np.ndarray, sigmas=RIDGE_SIGMAS_PX) -> np.ndarray:
    """Scale-normalised linear-ridge strength (bright or dark), max over scales. No catalogue input.

    For each scale s: lam_big / lam_small are the Hessian eigenvalues ordered by |.|;
    response = s^2 * |lam_big| * linearity, linearity = 1 - |lam_small|/|lam_big| (0 for blobs),
    clipped to >= 0. Output is max over scales, float32, same shape as the input.
    """
    from scipy import ndimage

    best = np.zeros(band.shape, dtype=np.float32)
    for s in sigmas:
        hxx = ndimage.gaussian_filter(band, s, order=(0, 2))
        hyy = ndimage.gaussian_filter(band, s, order=(2, 0))
        hxy = ndimage.gaussian_filter(band, s, order=(1, 1))
        tmp = np.sqrt(((hxx - hyy) / 2) ** 2 + hxy ** 2)
        l1 = (hxx + hyy) / 2 + tmp
        l2 = (hxx + hyy) / 2 - tmp
        use1 = np.abs(l1) >= np.abs(l2)
        big = np.where(use1, l1, l2)
        small = np.where(use1, l2, l1)
        lin = np.clip(1.0 - np.abs(small) / (np.abs(big) + 1e-12), 0.0, 1.0)
        r = (s ** 2) * np.abs(big) * lin
        best = np.maximum(best, r.astype(np.float32))
    return best


def rtp_ridge_grid(features_path: str, footprint: np.ndarray, band: int = 2) -> np.ndarray:
    """Ridge feature on the full grid from band `band` (1-based; band 2 = reduced-to-pole magnetics).

    Sentinel/NaN cells (nodata) are filled with the footprint mean before filtering so that the
    filter does not respond to the nodata edge; output is set to 0 outside the footprint.
    """
    import rasterio

    with rasterio.open(features_path) as src:
        x = src.read(band).astype(np.float64)
        nod = src.nodata
    bad = ~np.isfinite(x) | (x < FEATURE_NODATA_THRESHOLD)
    if nod is not None and np.isfinite(nod):
        bad |= x == nod
    fill = float(np.nanmean(np.where(bad, np.nan, x)[footprint]))
    x = np.where(bad, fill, x) - fill
    out = ridge_feature(x).astype(np.float32)
    out[~footprint] = 0.0
    return out


# ----------------------------------------------------------------------------------------------
# H5 feature: multi-scale edge (scale-normalised gradient magnitude) on a label-free band.
# ----------------------------------------------------------------------------------------------

EDGE_SIGMAS_PX = (1.0, 2.0, 3.0)  # 100, 200, 300 m


def edge_feature(band: np.ndarray, sigmas=EDGE_SIGMAS_PX) -> np.ndarray:
    """Scale-normalised gradient magnitude, max over scales. No catalogue input.

    For each scale s: response = s * |grad gaussian_filter(band, s)| (scale normalisation makes the
    response comparable across scales, as in ridge detection). Output is max over scales, float32.
    """
    from scipy import ndimage

    best = np.zeros(band.shape, dtype=np.float32)
    for s in sigmas:
        gx = ndimage.gaussian_filter(band, s, order=(0, 1))
        gy = ndimage.gaussian_filter(band, s, order=(1, 0))
        mag = np.hypot(gx, gy)
        best = np.maximum(best, (s * mag).astype(np.float32))
    return best


def edge_grid(features_path: str, footprint: np.ndarray, band: int) -> np.ndarray:
    """Edge feature on the full grid from band `band` (1-based). Same nodata handling as rtp_ridge_grid."""
    import rasterio

    with rasterio.open(features_path) as src:
        x = src.read(band).astype(np.float64)
        nod = src.nodata
    bad = ~np.isfinite(x) | (x < FEATURE_NODATA_THRESHOLD)
    if nod is not None and np.isfinite(nod):
        bad |= x == nod
    fill = float(np.nanmean(np.where(bad, np.nan, x)[footprint]))
    x = np.where(bad, fill, x) - fill
    out = edge_feature(x).astype(np.float32)
    out[~footprint] = 0.0
    return out


# ----------------------------------------------------------------------------------------------
# Metric: distance-weighted Tversky index (official definition)
# ----------------------------------------------------------------------------------------------


def _kernel_offsets(R: int = R_PX):
    out = []
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            d = math.hypot(dx, dy)
            if d <= R:
                out.append((dy, dx, max(1.0 - d / R, 0.0)))
    return out


def kernel_to_gt(gt: np.ndarray, R: int = R_PX) -> np.ndarray:
    """K(x) = max_{g in G} k(d(x,g)) = max(1 - d(x,G)/R, 0): the triangular-kernel credit of pixel x.

    Shared by every scorer that needs the same ground truth (the EDT is the expensive part and does
    not depend on the prediction), so holdout sweeps can precompute it once per fold.
    """
    gt = np.asarray(gt, dtype=bool)
    if gt.any():
        dgt = ndimage.distance_transform_edt(~gt)
        return np.maximum(1.0 - dgt / R, 0.0)
    return np.zeros(gt.shape, dtype=np.float64)


def dti(p: np.ndarray, gt: np.ndarray, alpha: float = ALPHA, beta: float = BETA, R: int = R_PX) -> dict:
    """Distance-weighted Tversky index of prediction map p in [0,1] against boolean ground truth gt.

    TP_w = sum_{g in G} max_{x: d(x,g)<=R} p(x) k(d(x,g))
    FP_w = sum_{x: p(x)>0} p(x) [1 - max_{g in G} k(d(x,g))]
    FN_w = sum_{g in G} [1 - max_{x: d(x,g)<=R} p(x) k(d(x,g))]
    DTI  = TP_w / (TP_w + alpha FP_w + beta FN_w + eps)
    """
    p = np.asarray(p, dtype=np.float64)
    gt = np.asarray(gt, dtype=bool)
    K = kernel_to_gt(gt, R)
    return dti_with_kernel(p, gt, K, alpha, beta, R)


def dti_with_kernel(p: np.ndarray, gt: np.ndarray, K: np.ndarray,
                    alpha: float = ALPHA, beta: float = BETA, R: int = R_PX) -> dict:
    """Same metric as dti(), with the kernel-to-ground-truth map K precomputed (see kernel_to_gt)."""
    p = np.asarray(p, dtype=np.float64)
    gt = np.asarray(gt, dtype=bool)
    H, W = p.shape
    pad = np.zeros((H + 2 * R, W + 2 * R), dtype=np.float64)
    pad[R:R + H, R:R + W] = p
    M = np.zeros((H, W), dtype=np.float64)
    for dy, dx, w in _kernel_offsets(R):
        if w <= 0:
            continue
        shifted = pad[R + dy:R + dy + H, R + dx:R + dx + W]
        np.maximum(M, w * shifted, out=M)
    tp = float(M[gt].sum())
    fn = float((1.0 - M[gt]).sum())
    fp = float((p * (1.0 - K)).sum())
    value = tp / (tp + alpha * fp + beta * fn + EPS)
    return {"TP_w": tp, "FP_w": fp, "FN_w": fn, "DTI": value, "alpha": alpha, "beta": beta, "R_px": R}


def dti_bruteforce(p: np.ndarray, gt: np.ndarray, alpha: float = ALPHA, beta: float = BETA, R: int = R_PX) -> dict:
    """Literal, slow implementation of the official formulas. Used only in tests to check dti()."""
    H, W = p.shape
    G = list(zip(*np.nonzero(gt)))
    X = [(y, x) for y in range(H) for x in range(W)]

    def k(d):
        return max(1.0 - d / R, 0.0)

    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    tp = 0.0
    fn = 0.0
    for g in G:
        best = 0.0
        for x in X:
            d = dist(x, g)
            if d <= R:
                best = max(best, p[x] * k(d))
        tp += best
        fn += 1.0 - best
    fp = 0.0
    for x in X:
        if p[x] > 0:
            mk = max((k(dist(x, g)) for g in G), default=0.0)
            fp += p[x] * (1.0 - mk)
    return {"TP_w": tp, "FP_w": fp, "FN_w": fn, "DTI": tp / (tp + alpha * fp + beta * fn + EPS)}


# ----------------------------------------------------------------------------------------------
# Emission rules (post-processing of a model probability map into a submission emission)
# ----------------------------------------------------------------------------------------------


def top_q_mask(p_full: np.ndarray, candidates: np.ndarray, q: float, footprint_px: int) -> np.ndarray:
    """Boolean mask of the top-q*footprint_px candidate pixels by probability (ties kept)."""
    vals = p_full[candidates]
    n_keep = int(round(q * footprint_px))
    if n_keep <= 0 or vals.size == 0:
        return np.zeros_like(candidates)
    n_keep = min(n_keep, vals.size)
    thr = np.partition(vals, -n_keep)[-n_keep]
    return candidates & (p_full >= thr)


def emission_from_probability(p_full: np.ndarray, keep: np.ndarray, variant: str = "raw") -> np.ndarray:
    """Emission map from a probability map and a keep mask. Variants (all values in [0, 1]):

    raw  : keep the model probability as-is (the Exp 2 recipe);
    bin  : binary dots, value 1.0 on every kept pixel (the registry's high-scoring dot files);
    rank : rank-rescaled, kept pixels get (rank)/(n_kept) in (0, 1], preserving the model order;
    sqrt : sqrt of the model probability (a midway compression of the value range).
    """
    out = np.zeros_like(p_full, dtype=np.float32)
    if not keep.any():
        return out
    if variant == "raw":
        out[keep] = p_full[keep]
    elif variant == "bin":
        out[keep] = 1.0
    elif variant == "rank":
        kept_vals = p_full[keep]
        order = np.argsort(kept_vals, kind="stable")
        ranks = np.empty(order.size, dtype=np.float64)
        ranks[order] = np.arange(1, order.size + 1, dtype=np.float64)
        out[keep] = (ranks / order.size).astype(np.float32)
    elif variant == "sqrt":
        out[keep] = np.sqrt(np.clip(p_full[keep], 0.0, 1.0))
    else:
        raise ValueError(f"unknown emission variant {variant!r}")
    return out


# ----------------------------------------------------------------------------------------------
# Submission writing and validation
# ----------------------------------------------------------------------------------------------


def write_submission(path: str, emission: np.ndarray, transform, crs, outside_nan: bool,
                     compress: str | None = "lzw", predictor: int | None = None) -> None:
    """Write a single-band float32 GeoTIFF. outside_nan=True matches the official sample_submission.tif.

    compress='lzw' matches the organizer's sample (compress=lzw, one strip per row, nodata NaN). Compression
    is lossless: pixel values are unchanged, and tests/test_submission.py checks the round-trip. A floating
    point predictor (predictor=2) is accepted for smaller files; the round-trip stays bit-exact (checked by
    the caller and by tests/test_emission_and_gate.py).
    """
    import rasterio

    H, W = emission.shape
    arr = emission.astype(np.float32, copy=True)
    if outside_nan:
        arr[np.isnan(arr)] = np.nan
    kwargs = {} if compress is None else {"compress": compress}
    if predictor is not None:
        kwargs["predictor"] = predictor
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
        crs=crs, transform=transform, nodata=(float("nan") if outside_nan else None), **kwargs,
    ) as dst:
        dst.write(arr, 1)


def validate_submission(path: str, footprint: np.ndarray, transform, crs, H: int, W: int) -> dict:
    """Checks that mirror the official format text: CRS, shape, transform, dtype, single band, values in
    [0,1] wherever finite, no NaN/inf inside the footprint, outside-footprint pixels null or NaN (only)."""
    import rasterio

    res = {"path": path, "checks": {}}
    with rasterio.open(path) as src:
        a = src.read()
        res["checks"]["single_band"] = src.count == 1
        res["checks"]["dtype_float32"] = src.dtypes[0] == "float32"
        res["checks"]["shape_matches_template"] = (src.height, src.width) == (H, W)
        res["checks"]["crs_is_EPSG_32611"] = src.crs is not None and src.crs.to_epsg() == 32611
        res["checks"]["transform_matches_template"] = tuple(src.transform)[:6] == tuple(transform)[:6]
        res["nodata"] = src.nodata
    x = a[0].astype(np.float64)
    finite = np.isfinite(x)
    inside = footprint
    res["checks"]["no_nan_or_inf_inside_footprint"] = bool(np.isfinite(x[inside]).all())
    res["checks"]["inside_footprint_in_0_1"] = bool(((x[inside] >= 0) & (x[inside] <= 1)).all())
    outside = ~inside
    # Official text (drivendata page 967, "Submission format"): "data outside the bounds is null or nan".
    # Zero outside is NOT accepted here (IR-53-18: this check used to allow zero, which the rule does not).
    res["checks"]["outside_footprint_nan"] = bool(np.isnan(x[outside]).all())
    res["checks"]["all_finite_values_in_0_1"] = bool(((x[finite] >= 0) & (x[finite] <= 1)).all())
    res["counts"] = {
        "footprint_px": int(inside.sum()),
        "finite_px": int(finite.sum()),
        "nonzero_px": int(np.count_nonzero(np.nan_to_num(x) > 0)),
        "nan_outside_px": int(np.isnan(x[outside]).sum()),
        "zero_outside_px": int((x[outside] == 0).sum()),
        "max": float(np.nanmax(x)),
        "min": float(np.nanmin(x)),
    }
    res["all_checks_passed"] = all(res["checks"].values())
    return res
