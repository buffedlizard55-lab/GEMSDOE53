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


def dti(p: np.ndarray, gt: np.ndarray, alpha: float = ALPHA, beta: float = BETA, R: int = R_PX) -> dict:
    """Distance-weighted Tversky index of prediction map p in [0,1] against boolean ground truth gt.

    TP_w = sum_{g in G} max_{x: d(x,g)<=R} p(x) k(d(x,g))
    FP_w = sum_{x: p(x)>0} p(x) [1 - max_{g in G} k(d(x,g))]
    FN_w = sum_{g in G} [1 - max_{x: d(x,g)<=R} p(x) k(d(x,g))]
    DTI  = TP_w / (TP_w + alpha FP_w + beta FN_w + eps)
    """
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
    if gt.any():
        dgt = ndimage.distance_transform_edt(~gt)
        K = np.maximum(1.0 - dgt / R, 0.0)
    else:
        K = np.zeros_like(p)
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
# Submission writing and validation
# ----------------------------------------------------------------------------------------------


def write_submission(path: str, emission: np.ndarray, transform, crs, outside_nan: bool) -> None:
    """Write a single-band float32 GeoTIFF. outside_nan=True matches the official sample_submission.tif."""
    import rasterio

    H, W = emission.shape
    arr = emission.astype(np.float32, copy=True)
    if outside_nan:
        arr[np.isnan(arr)] = np.nan
    with rasterio.open(
        path, "w", driver="GTiff", height=H, width=W, count=1, dtype="float32",
        crs=crs, transform=transform, nodata=(float("nan") if outside_nan else None),
    ) as dst:
        dst.write(arr, 1)


def validate_submission(path: str, footprint: np.ndarray, transform, crs, H: int, W: int) -> dict:
    """Checks that mirror the official format text: CRS, shape, transform, dtype, single band, values in
    [0,1] wherever finite, no NaN/inf inside the footprint, outside-footprint pixels null or NaN OR zero."""
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
    outside_ok = bool(np.all(np.isnan(x[outside]) | (x[outside] == 0)))
    res["checks"]["outside_footprint_nan_or_zero"] = outside_ok
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


# ----------------------------------------------------------------------------------------------
# H1 (2026-10-08): segment-exact learn-predict separation
# ----------------------------------------------------------------------------------------------


def segment_exact_distance_grid(visible: np.ndarray, seg_label: np.ndarray, cap: int = DIST_CAP_PX) -> np.ndarray:
    """H1: log1p(min(d, cap)) where d is
      * the distance to the visible faults EXCLUDING the pixel's own segment, if the pixel lies on a visible segment;
      * the distance to all visible faults otherwise (background, withheld faults, emission pixels).

    `seg_label` is the 8-connected segment id of the FULL catalogue (0 = background), so the segment
    of every visible pixel is known. Each visible segment is processed inside its bounding box plus a
    `cap`-pixel halo; any visible pixel farther than `cap` from the segment is clipped to `cap` anyway, so the
    windowed result equals the global one exactly (checked against brute force in tests/test_h1_thin.py).
    """
    H, W = visible.shape
    out = log_dist_feature(dist_to(visible))
    objs = ndimage.find_objects(seg_label)
    vis_ids = np.unique(seg_label[visible])
    vis_ids = vis_ids[vis_ids > 0]
    for sid in vis_ids:
        sl = objs[int(sid) - 1]
        if sl is None:
            continue
        y0, y1 = sl[0].start, sl[0].stop
        x0, x1 = sl[1].start, sl[1].stop
        Y0, Y1 = max(0, y0 - cap), min(H, y1 + cap)
        X0, X1 = max(0, x0 - cap), min(W, x1 + cap)
        own = seg_label[y0:y1, x0:x1] == sid
        if not visible[y0:y1, x0:x1][own].all():
            raise ValueError("visible must be a union of WHOLE segments (H1 contract); segment %d is partly visible" % sid)
        others = visible[Y0:Y1, X0:X1] & (seg_label[Y0:Y1, X0:X1] != sid)
        if others.any():
            dw = ndimage.distance_transform_edt(~others)
            dseg = dw[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0]
        else:
            dseg = np.full(own.shape, np.inf)
        sub = out[y0:y1, x0:x1]
        sub[own] = np.log1p(np.minimum(dseg[own], cap)).astype(np.float32)
    return out


# ----------------------------------------------------------------------------------------------
# M1 (2026-10-08): metric-aware thinning (greedy distance-R dominating set)
# ----------------------------------------------------------------------------------------------


def greedy_dominating_dots(rows: np.ndarray, cols: np.ndarray, vals: np.ndarray, shape, R: int = R_PX) -> np.ndarray:
    """Greedy maximal set of candidates whose pairwise distance is strictly greater than R pixels.

    Candidates are visited in decreasing `vals`. A candidate is kept iff no already-kept dot lies within
    Euclidean distance R of it. Maximality means every rejected candidate lies within R of a kept dot, so the
    kept set dominates the candidate set at radius R. Returns a boolean keep-mask aligned with the inputs.
    """
    H, W = shape
    order = np.argsort(-np.asarray(vals, dtype=np.float64), kind="stable")
    offs = [(dy, dx) for dy in range(-R, R + 1) for dx in range(-R, R + 1) if dy * dy + dx * dx <= R * R]
    blocked = np.zeros((H, W), dtype=bool)
    keep = np.zeros(len(vals), dtype=bool)
    for i in order:
        y, x = int(rows[i]), int(cols[i])
        if blocked[y, x]:
            continue
        keep[i] = True
        for dy, dx in offs:
            yy, xx = y + dy, x + dx
            if 0 <= yy < H and 0 <= xx < W:
                blocked[yy, xx] = True
    return keep


def thin_emission(p_full: np.ndarray, candidates: np.ndarray, q: float, footprint_px: int,
                  value: str = "p", R: int = R_PX):
    """M1: top-q candidates by probability, then a greedy distance-R dominating set.

    value = "p"   keep the model probability on kept dots (the emission is still a probability);
    value = "bin" set kept dots to 1.0 (the template's hard floor, with the same dots).
    Returns (emission float32 (H,W), kept_dot_count, selected_candidate_count).
    """
    H, W = p_full.shape
    out = np.zeros((H, W), dtype=np.float32)
    rr, cc = np.nonzero(candidates)
    vals = p_full[rr, cc]
    n_keep = int(round(q * footprint_px))
    if n_keep <= 0 or vals.size == 0:
        return out, 0, 0
    n_keep = min(n_keep, vals.size)
    top = np.argpartition(-vals, n_keep - 1)[:n_keep]
    rr, cc, vals = rr[top], cc[top], vals[top]
    kept = greedy_dominating_dots(rr, cc, vals, (H, W), R)
    if value == "bin":
        out[rr[kept], cc[kept]] = 1.0
    elif value == "p":
        out[rr[kept], cc[kept]] = vals[kept].astype(np.float32)
    else:
        raise ValueError(f"unknown value mode {value!r}")
    return out, int(kept.sum()), int(n_keep)


# ----------------------------------------------------------------------------------------------
# Shared template tools (imported by file path, never copied into this repository)
# ----------------------------------------------------------------------------------------------

TEMPLATE_ROOT_DEFAULT = "/tmp/gems-template"


def load_template_module(name: str, template_root: str = TEMPLATE_ROOT_DEFAULT):
    """Import one module of the shared GEMSDOE template by file path (no copy, no package clash)."""
    import importlib.util
    from pathlib import Path as _P

    path = _P(template_root) / "src" / f"{name}.py"
    if not path.exists():
        raise FileNotFoundError(f"shared template module missing: {path} (run: git clone "
                                f"https://github.com/buffedlizard55-lab/GEMSDOE.git {template_root})")
    spec = importlib.util.spec_from_file_location(f"template_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
