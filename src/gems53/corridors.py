"""H8 (2026-10-09): tip/relay continuation corridor surfaces with magnetic-lineament concordance.

Lane paragraph (docs/research/preregistration-h8-2026-10-09.md, section 0).  Every function here is a
function of the VISIBLE catalogue and label-free bands only.  In a holdout fold `visible` excludes the
withheld segments; at submission time `visible` is the full catalogue (legitimate at prediction time).

Geology encoded here (rules only - nothing is fitted to labels):
  * TIP CONTINUATION.  Fault segments grow by displacement-controlled propagation: the mapped trace
    ends where displacement dies, not where the structure ends.  Hidden Quaternary continuations
    therefore sit beyond the mapped tips along the local strike.  For each 8-connected segment we take
    its principal axis, find the two tip points, estimate the local strike from the tip-most 15 px and
    paint a decaying corridor outward along the extrapolated strike.
  * RELAY / STEP-OVER.  Sub-parallel segments whose along-strike projections overlap link through
    relay ramps / step-overs; the damage zone there is the classic permeable pathway for geothermal
    upflow, and hidden segments live inside it.  For every qualifying segment pair we paint a corridor
    between the facing tips.
  * MAGNETIC CONCORDANCE (label-free).  Lineament strength from the reduced-to-pole field (band 2),
    via the existing Hessian/NMS machinery in gems53.ridge, is added as a tie-breaker so corridors
    coincide with a physical edge where one exists.

All geometry is in pixel units on the competition grid (100 m px).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

# ---- pre-registered constants (preregistration-h8-2026-10-09.md, section 0) ----
TIP_REACH_PX = 120          # 12 km maximum continuation reach
TIP_STRIKE_PX = 15          # pixels from the tip used to estimate local strike
TIP_SIGMA_PX = 3.0          # cross-corridor sigma
TIP_DECAY_FLOOR_PX = 20.0   # decay = clip(seg_len/2, 20, 60)
TIP_DECAY_CAP_PX = 60.0
RELAY_MAX_GAP_PX = 60       # facing-tip gap band (2 px = pruned anyway; 60 px = 6 km)
RELAY_MIN_OVERLAP_PX = 2.0
RELAY_MAX_STRIKE_DEG = 30.0
RELAY_SIGMA_PX = 4.0
RELAY_SAMPLES_ALONG = 24
WEIGHT_TIP = 1.0
WEIGHT_RELAY = 1.2
WEIGHT_RIDGE = 0.6
PRUNE_PX = 2                # dots must be >= 2 px off the visible catalogue


# ------------------------------------------------------------------
# Segments, tips, strikes
# ------------------------------------------------------------------

def segment_table(visible: np.ndarray):
    """8-connected segments of `visible`.  Returns (seg_label, n, rows_list, cols_list)."""
    L, n = ndimage.label(visible, structure=np.ones((3, 3), dtype=bool))
    objs = ndimage.find_objects(L)
    rows_list, cols_list = [], []
    for i in range(n):
        sl = objs[i]
        m = L[sl] == (i + 1)
        rr, cc = np.nonzero(m)
        rows_list.append(rr + sl[0].start)
        cols_list.append(cc + sl[1].start)
    return L, n, rows_list, cols_list


def _pca_axis(rows: np.ndarray, cols: np.ndarray):
    r0, c0 = float(rows.mean()), float(cols.mean())
    x = np.stack([cols - c0, rows - r0], axis=1).astype(np.float64)
    if x.shape[0] < 2:
        return (c0, r0), (1.0, 0.0), 1.0
    cov = x.T @ x / max(1, x.shape[0] - 1)
    w, v = np.linalg.eigh(cov)
    direction = v[:, int(np.argmax(w))]     # principal (along-strike) unit vector (col, row)
    length = float(np.ptp(x @ direction))
    return (c0, r0), (float(direction[0]), float(direction[1])), max(length, 1.0)


def tips_and_strikes(rows: np.ndarray, cols: np.ndarray):
    """Return two records ((tip_row, tip_col), outward_unit_strike(col,row), seg_len)."""
    (c0, r0), (dc, dr), length = _pca_axis(rows, cols)
    proj = (cols - c0) * dc + (rows - r0) * dr
    out = []
    for sign in (-1.0, +1.0):
        if sign < 0:
            idx = int(np.argmin(proj))
        else:
            idx = int(np.argmax(proj))
        ty, tx = float(rows[idx]), float(cols[idx])
        near = np.abs(proj - proj[idx]) <= TIP_STRIKE_PX
        if int(near.sum()) >= 3:
            _, (lc, lr), _ = _pca_axis(rows[near], cols[near])
            if lc * dc + lr * dr < 0:       # keep orientation consistent with the global axis
                lc, lr = -lc, -lr
        else:
            lc, lr = dc, dr
        out.append(((ty, tx), (sign * lc, sign * lr), length))
    return out


# ------------------------------------------------------------------
# Windowed corridor painting
# ------------------------------------------------------------------

def _paint_gaussian(out: np.ndarray, pts: np.ndarray, weights: np.ndarray, sigma: float):
    """Max-paint Gaussian ridges along sample points, windowed (fast)."""
    if len(pts) == 0:
        return
    H, W = out.shape
    rad = int(math.ceil(3.0 * sigma))
    r0 = max(0, int(np.floor(pts[:, 0].min())) - rad)
    r1 = min(H, int(np.ceil(pts[:, 0].max())) + rad + 1)
    c0 = max(0, int(np.floor(pts[:, 1].min())) - rad)
    c1 = min(W, int(np.ceil(pts[:, 1].max())) + rad + 1)
    if r1 <= r0 or c1 <= c0:
        return
    acc = np.zeros((r1 - r0, c1 - c0), dtype=np.float64)
    ys = np.clip(pts[:, 0].astype(np.int64) - r0, 0, r1 - r0 - 1)
    xs = np.clip(pts[:, 1].astype(np.int64) - c0, 0, c1 - c0 - 1)
    np.maximum.at(acc, (ys, xs), weights.astype(np.float64))
    blur = ndimage.gaussian_filter(acc, sigma, mode="constant")
    peak = ndimage.gaussian_filter(np.zeros((2 * rad + 1, 2 * rad + 1)), sigma, mode="constant")
    peak[rad, rad] = 1.0
    peak = ndimage.gaussian_filter(peak, sigma, mode="constant").max()
    if peak > 0:
        blur /= peak
    sub = out[r0:r1, c0:c1]
    np.maximum(sub, blur, out=sub)


# ------------------------------------------------------------------
# Corridor surfaces
# ------------------------------------------------------------------

def tip_continuation_surface(visible: np.ndarray, reach_px: int = TIP_REACH_PX) -> np.ndarray:
    """Decaying corridors extrapolated outward from every visible segment tip along local strike."""
    H, W = visible.shape
    out = np.zeros((H, W), dtype=np.float64)
    _, n, rows_list, cols_list = segment_table(visible)
    for rows, cols in zip(rows_list, cols_list):
        for (ty, tx), (sc, sr), length in tips_and_strikes(rows, cols):
            decay = float(np.clip(0.5 * length, TIP_DECAY_FLOOR_PX, TIP_DECAY_CAP_PX))
            steps = np.arange(1.0, float(reach_px) + 1.0)
            w = np.exp(-steps / decay)
            pts = np.stack([ty + steps * sr, tx + steps * sc], axis=1)
            keep = (pts[:, 0] >= -3 * TIP_SIGMA_PX) & (pts[:, 0] < H + 3 * TIP_SIGMA_PX) & \
                   (pts[:, 1] >= -3 * TIP_SIGMA_PX) & (pts[:, 1] < W + 3 * TIP_SIGMA_PX)
            _paint_gaussian(out, pts[keep], w[keep], TIP_SIGMA_PX)
    return out


def relay_surface(visible: np.ndarray, max_gap_px: int = RELAY_MAX_GAP_PX) -> np.ndarray:
    """Corridors linking the facing tips of overlapping, sub-parallel segment pairs (relay/step-over)."""
    H, W = visible.shape
    out = np.zeros((H, W), dtype=np.float64)
    _, n, rows_list, cols_list = segment_table(visible)
    if n == 0:
        return out
    boxes = np.array([[r.min(), r.max(), c.min(), c.max()] for r, c in zip(rows_list, cols_list)])
    info = [_pca_axis(r, c) for r, c in zip(rows_list, cols_list)]
    for i in range(n):
        r0i, r1i, c0i, c1i = boxes[i]
        (ci0, ri0), (dci, dri), _ = info[i]
        for j in range(i + 1, n):
            r0j, r1j, c0j, c1j = boxes[j]
            if (r0j - r1i > max_gap_px) or (r0i - r1j > max_gap_px) or \
               (c0j - c1i > max_gap_px) or (c0i - c1j > max_gap_px):
                continue
            (cj0, rj0), (dcj, drj), _ = info[j]
            cosang = abs(dci * dcj + dri * drj)
            if cosang < math.cos(math.radians(RELAY_MAX_STRIKE_DEG)):
                continue
            if dci * dcj + dri * drj < 0:
                dcj, drj = -dcj, -drj
            ax = (dci + dcj, dri + drj)
            nrm = math.hypot(*ax) or 1.0
            ax = (ax[0] / nrm, ax[1] / nrm)
            perp = (-ax[1], ax[0])

            def extent(rows, cols):
                p = (cols - ci0) * ax[0] + (rows - ri0) * ax[1]
                return float(p.min()), float(p.max())

            ai0, ai1 = extent(rows_list[i], cols_list[i])
            aj0, aj1 = extent(rows_list[j], cols_list[j])
            ov0, ov1 = max(ai0, aj0), min(ai1, aj1)
            overlap = ov1 - ov0
            if overlap < RELAY_MIN_OVERLAP_PX:
                continue
            pi = 0.0
            pj = (cj0 - ci0) * perp[0] + (rj0 - ri0) * perp[1]
            gap = abs(pj - pi)
            if gap < 1.0 or gap > max_gap_px:
                continue
            ts = np.linspace(ov0, ov1, RELAY_SAMPLES_ALONG)
            ss = np.linspace(0.0, 1.0, max(3, int(gap)))
            T, S = np.meshgrid(ts, ss, indexing="ij")
            cols_p = ci0 + T * ax[0] + (pi + S * (pj - pi)) * perp[0]
            rows_p = ri0 + T * ax[1] + (pi + S * (pj - pi)) * perp[1]
            pts = np.stack([rows_p.ravel(), cols_p.ravel()], axis=1)
            ratio = overlap / gap
            w = float(np.clip(ratio, 0.2, 2.0) / 2.0) * float(np.exp(-gap / RELAY_MAX_GAP_PX))
            w = max(w, 0.05)
            _paint_gaussian(out, pts, np.full(len(pts), w), RELAY_SIGMA_PX)
    return out


def normalise01(x: np.ndarray, valid: np.ndarray) -> np.ndarray:
    if not valid.any():
        return np.zeros_like(x, dtype=np.float64)
    lo = float(x[valid].min())
    hi = float(x[valid].max())
    if hi <= lo:
        return np.zeros_like(x, dtype=np.float64)
    out = (np.asarray(x, dtype=np.float64) - lo) / (hi - lo)
    out[~valid] = 0.0
    return np.clip(out, 0.0, 1.0)


def corridor_surface(visible: np.ndarray, ridge_L: np.ndarray | None,
                     valid: np.ndarray) -> np.ndarray:
    """Pre-registered combination: w_tip*norm(tip) + w_relay*norm(relay) + w_ridge*norm(ridge)."""
    tip = tip_continuation_surface(visible)
    rel = relay_surface(visible)
    valid = valid if valid is not None else np.ones_like(visible, dtype=bool)
    s = WEIGHT_TIP * normalise01(tip, valid) + WEIGHT_RELAY * normalise01(rel, valid)
    if ridge_L is not None:
        s = s + WEIGHT_RIDGE * normalise01(ridge_L, valid)
    return s


def prune_mask(visible: np.ndarray, px: int = PRUNE_PX) -> np.ndarray:
    """True where a dot is allowed: strictly more than `px` pixels off every visible catalogue pixel.

    Matches H33-2-B2's 'b2' step ("dots within 2 px of the catalogue deleted"): distance <= px is pruned.
    """
    return ndimage.distance_transform_edt(~visible) > px
