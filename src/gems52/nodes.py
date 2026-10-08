"""Sparse **node** emission for a dilated, non-differentiable truth set.

Why nodes, derived rather than asserted
---------------------------------------
``gems52.metric`` defines (and ``tests/test_metric.py`` pins):

    FPw = sum_x p(x) [1 - max_g k(d(x,g))]        q_x := max_g k(d(x,g))
    DTI = T / ( 0.2 * sum_x (1 - q_x) + 0.8*|G| + 0.2*T )

Now consider emitting a *disc* of radius r around a point c instead of the point itself.  Take a
21-pixel disc (1-px radius).  Every pixel in it that is not the peak pays the full
``0.2 * (1 - q)`` tax, while the truth pixel it was supposed to cover was already covered by the peak
at weight 1.  Concretely, for a 3-px-radius truth pixel the extra tax of a neighbouring pixel 2 px
away is ``0.2 * (1 - min(1, 1/3)) = 0.133``, and the extra credit is exactly 0.  The emitted disc is
therefore *strictly dominated* by its own centroid for this metric: same numerator, larger
denominator.  The official metric's dilation, in other words, is inside the metric, not in the
submission -- the organiser already gives 300 m of slack, and adding 100-300 m of thickness on top of
it converts free slack into taxable area.

That is why the emission in this module is a set of **nodes**, and it is also why node emission needs
its own validation: a node set has ~1/21 the pixels of a filled disc, so a recall-oriented reading
("did we find the fault?") and the metric's own credit are different questions, and both are reported.

Everything here is metric-aware in the sense that matters: the *tax* of a candidate set is computed
from the actual geometry (an exact Euclidean distance transform to the chosen nodes), not modelled,
and greedy selection is delegated to ``gems52.emit.greedy_emit``, which carries the marginal
acceptance rule ``gain > alpha*DTI/(1-alpha*DTI) * (1 - wmax)`` that the metric implies.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

R_PX = 3.0
OFFSET_WEIGHTS = tuple(
    (dy, dx, 1.0 - (dy * dy + dx * dx) ** 0.5 / R_PX)
    for dy in range(-3, 4) for dx in range(-3, 4)
    if (dy * dy + dx * dx) ** 0.5 <= R_PX + 1e-12
)


def top_k_mask(field: np.ndarray, allowed: np.ndarray, k: int) -> np.ndarray:
    """Boolean mask of the k highest-valued allowed pixels (ties broken by flat index)."""
    f = np.where(allowed, np.nan_to_num(field, nan=0.0, neginf=0.0, posinf=0.0), -np.inf)
    flat = f.ravel()
    k = int(min(max(k, 0), int(allowed.sum())))
    m = np.zeros(flat.size, dtype=bool)
    if k == 0:
        return m.reshape(field.shape)
    idx = np.argpartition(-flat, k - 1)[:k]
    idx = idx[flat[idx] > -np.inf]
    m[idx] = True
    return m.reshape(field.shape)


def local_maxima(field: np.ndarray, allowed: np.ndarray, radius_px: int = 1) -> np.ndarray:
    """Non-maximum suppression: a pixel survives iff it wins its own neighbourhood.

    The winner is decided **lexicographically** -- higher score first, earlier raster index to break
    ties -- which makes the operation deterministic on plateaus (a flat background is one big plateau
    and contributes exactly one survivor, not millions).  A version that tested only
    ``f >= maximum_filter(f)`` was written first and failed ``tests/test_nodes.py`` on a flat field,
    because every background pixel is trivially its own maximum; the tie-break is what fixes it.
    """
    r = int(radius_px)
    f = np.where(allowed, np.nan_to_num(field, nan=0.0, neginf=0.0, posinf=0.0),
                 -np.inf).astype(np.float64)
    idx = np.arange(f.size, dtype=np.int64).reshape(f.shape)
    best = f.copy()
    best_idx = idx.copy()
    big = np.iinfo(np.int64).max
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy == 0 and dx == 0:
                continue
            sh_f = np.roll(f, shift=(-dy, -dx), axis=(0, 1))
            sh_i = np.roll(idx, shift=(-dy, -dx), axis=(0, 1))
            if dy > 0:
                sh_f[:dy, :] = -np.inf
                sh_i[:dy, :] = big
            elif dy < 0:
                sh_f[dy:, :] = -np.inf
                sh_i[dy:, :] = big
            if dx > 0:
                sh_f[:, :dx] = -np.inf
                sh_i[:, :dx] = big
            elif dx < 0:
                sh_f[:, dx:] = -np.inf
                sh_i[:, dx:] = big
            better = (sh_f > best) | ((sh_f == best) & (sh_i < best_idx))
            best = np.where(better, sh_f, best)
            best_idx = np.where(better, sh_i, best_idx)
    return allowed & np.isfinite(f) & (best_idx == idx) & (f > 0.0)


def thin_plateau(field: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Keep, in every 8-connected plateau of ``mask``, the single raster-first pixel."""
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=bool))
    if n == 0:
        return mask
    order = np.arange(field.size).reshape(field.shape)
    first = np.full(n + 1, np.iinfo(np.int64).max, dtype=np.int64)
    ids = lab.ravel()
    sel = ids > 0
    np.minimum.at(first, ids[sel], order.ravel()[sel].astype(np.int64))
    return mask & (first[lab] == order)


def tax_of_nodes(nodes: np.ndarray, truth: np.ndarray, r_px: float = R_PX,
                 within: np.ndarray | None = None) -> float:
    """Exact false-positive weight ``FPw`` of a binary node set: ``sum over emitted x of (1 - q_x)``.

    ``q_x = max_g k(d(x, g))`` is the distance from the pixel **x to the nearest TRUTH pixel g** --
    not to the nearest emitted pixel.  (A first version of this function used the distance to the
    emitted set, which makes every node its own neighbour at distance 0, hence ``q = 1``, hence a tax
    of identically zero; ``tests/test_nodes.py::test_tax_identity_matches_the_metric_definition``
    caught it by comparing against the published ``FPw`` on random fields.)  A pixel exactly on a
    truth pixel therefore pays nothing, a pixel one cell away pays ``0.2/3``, and a pixel beyond
    300 m pays the full ``0.2``.

    ``within`` optionally restricts the sum to the scored region (a fold's region, say).
    """
    t = truth.astype(bool)
    n = nodes.astype(bool)
    if within is not None:
        n = n & within
    if not n.any():
        return 0.0
    d = ndimage.distance_transform_edt(~t) if t.any() else np.full(n.shape, np.inf)
    q = np.maximum(1.0 - d / r_px, 0.0)
    return float((1.0 - q)[n].sum())


def node_credit(nodes: np.ndarray, truth: np.ndarray, r_px: float = R_PX) -> tuple[float, float]:
    """(T, |G|) of a binary node set against a truth mask, using the official kernel exactly."""
    t = truth.astype(bool)
    n = nodes.astype(bool)
    if not t.any():
        return 0.0, 0.0
    # max over emitted nodes of p*k(d): EDT to the node set, kernel applied
    d = ndimage.distance_transform_edt(~n)
    k = np.maximum(1.0 - d / r_px, 0.0)
    T = float(k[t].sum())
    return T, float(t.sum())


def node_dti(nodes: np.ndarray, truth: np.ndarray, valid: np.ndarray | None = None,
             r_px: float = R_PX, alpha: float = 0.2, beta: float = 0.8) -> dict:
    """Official DTI of a binary node emission (independent of ``gems52.metric`` on purpose).

    ``gems52.metric.dti`` remains the authority for scoring submissions and folds; this function is
    the *node-space* expression of the same formula (``FNw = |G| - T`` identically) and the two are
    asserted equal in ``tests/test_nodes.py`` on random small fields, so a divergence cannot pass
    silently.

    One deliberate difference: with an empty truth mask ``gems52.metric.dti`` returns ``0.0`` by
    convention, while this returns ``NaN``, so a caller cannot mistake "there was nothing to score"
    for "the score is zero".
    """
    n = nodes.astype(bool)
    t = truth.astype(bool) if valid is None else (truth & valid)
    if not t.any():
        return {"dti": float("nan"), "T": 0.0, "G": 0.0, "nodes": int(n.sum())}
    T, G = node_credit(n, t, r_px)
    tax = tax_of_nodes(n, t, r_px, within=valid)
    den = alpha * tax + beta * G + alpha * T
    return {"dti": float(T / den) if den > 0 else 0.0, "T": T, "G": G, "tax": tax,
            "nodes": int(n.sum())}


def nodes_to_grid(rows: np.ndarray, cols: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    out = np.zeros(shape, dtype=np.float32)
    out[rows, cols] = 1.0
    return out


def grid_to_nodes(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ys, xs = np.nonzero(mask)
    return ys.astype(np.int64), xs.astype(np.int64)


def spacing_stats(nodes: np.ndarray, sample: int = 200_000, seed: int = 0) -> dict:
    """Nearest-neighbour spacing of a node set, in pixels -- the price of the emission, measured."""
    ys, xs = np.nonzero(nodes)
    n = ys.size
    if n < 2:
        return {"n": int(n), "median_px": None}
    if n > sample:
        rng = np.random.default_rng(seed)
        sel = rng.choice(n, sample, replace=False)
        ys, xs = ys[sel], xs[sel]
    pts = np.stack([ys.astype(np.float64), xs.astype(np.float64)], axis=1)
    from scipy.spatial import cKDTree
    tree = cKDTree(pts)
    d, _ = tree.query(pts, k=2)
    nn = d[:, 1]
    return {"n": int(n), "median_px": float(np.median(nn)),
            "p10_px": float(np.percentile(nn, 10)), "p90_px": float(np.percentile(nn, 90)),
            "share_within_1px": float((nn <= 1.0 + 1e-9).mean()),
            "share_within_2px": float((nn <= 2.0 + 1e-9).mean())}


def spacing_select(score: np.ndarray, allowed: np.ndarray, k: int, min_px: float = 3.0,
                   log=None) -> np.ndarray:
    """Greedy top-k under a **minimum separation**, because separation is what the metric rewards.

    Measured on the current best submission (`data/reference/h33-2-b2-zeros.tif`): 37,654 pixels, all
    isolated singles, **median nearest-neighbour distance 3.0 px** -- a dot lattice at the kernel radius
    300 m.  That is not a stylistic choice, it is the metric's optimum: two dots closer than the kernel
    radius cover the same truth pixels, so the second pays the ``0.2 * (1 - q)`` tax for no new credit,
    while dots further apart than ~2 px leave truth pixels between them half-covered.  The family's own
    sweep says the same thing in its filenames: ``dotted ... d1-5`` scored 0.2477, ``d2-8`` 0.2600.

    Implementation is a greedy over descending score with a bucket grid of cell size ``min_px``, so the
    separation check touches at most 9 buckets per candidate (no KD-tree build over 320 k points).
    """
    idx = np.flatnonzero(allowed.ravel())
    if idx.size == 0 or k <= 0:
        return np.zeros(score.shape, dtype=bool)
    val = np.nan_to_num(score.ravel()[idx], nan=-np.inf, neginf=-np.inf, posinf=np.inf)
    order = np.lexsort((idx, -val))
    h, w = score.shape
    cell = max(1.0, float(min_px))
    keep = np.zeros(score.shape, dtype=bool)
    buckets: dict[tuple[int, int], list[tuple[float, float]]] = {}
    taken = 0
    r_ceil = int(np.ceil(cell))
    d2 = cell * cell
    for pos in order:
        if val[pos] == -np.inf:
            break
        flat = int(idx[pos])
        y, x = divmod(flat, w)
        cy, cx = int(y // cell), int(x // cell)
        ok = True
        for gy in range(cy - 1, cy + 2):
            for gx in range(cx - 1, cx + 2):
                for (py, px) in buckets.get((gy, gx), ()):      # noqa: E501
                    if (py - y) ** 2 + (px - x) ** 2 < d2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if not ok:
            continue
        keep[y, x] = True
        buckets.setdefault((cy, cx), []).append((y, x))
        taken += 1
        if taken >= k:
            break
    if log:
        log(f"spacing_select: kept {taken} of a requested {k} at min separation {min_px} px")
    return keep


def emit_nodes(score: np.ndarray, allowed: np.ndarray, k: int, min_px: float = 3.0,
               log=None) -> np.ndarray:
    """Binary {0,1} node emission: greedy top-k under a minimum separation (see :func:`spacing_select`)."""
    return spacing_select(score, allowed, k, min_px=min_px, log=log).astype(np.float32)
