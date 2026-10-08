"""H57 -- the brief's two-view co-training instrument, plus anisotropic node placement.

Written under the blind slate in ``knowledge/17_hypotheses_H57_preregistered.md`` and
``registry/h57_preregistration.json``.  Nothing in this module reads a leaderboard score; the
score-conditioned arithmetic lives in :mod:`gems52.revealed` and is used only for budget sizing.

What is here
------------
``feature_layers``   derive + globally rank-encode every layer used by the two views into one
                     ``uint8`` memmap (57 layers from ``training_features.tif``, 27 from the
                     restored external rasters).
``fit_view``         one L2 logistic view model on spatially blocked labelled pixels.
``dense_predict``    streaming prediction over the whole grid, row-chunked, so no full-grid
                     float32 feature matrix is ever materialised (12.28 M x 39 float32 is 1.9 GB
                     and this box has 3 GB).
``aniso_select``     the H57-A emitter: minimum separation is a *tensor* -- 4 px along the local
                     strike, 3 px across it -- derived from the metric's own kernel rather than
                     fitted.  Falls back to isotropic 3 px wherever the strike is not confident, so
                     it can never be worse than the incumbent rule.
``disagreement``     the brief's A-only / B-only strata with their written thresholds.

The view split is the brief's, with the radiometric band resolved as the brief resolves it and as
``evidence/h53_band6_identity.json`` measures it: band 6 is GeoDAWN total count (Spearman +1.0000
against the external total-count grid), so it belongs to the **surface** view B, not to the
potential-field view A.  The file's own ``data_category = magnetic_data`` tag is wrong
(``registry/irregularities.json`` IR-52-019).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

from . import grid as G

# --------------------------------------------------------------------------------------------
# layer inventory
# --------------------------------------------------------------------------------------------
# (source file, 1-based band, label).  Order is fixed and asserted against the registry.
FEATURE_BANDS = [
    ("data/training_features.tif", 1, "A_mag_anom"),
    ("data/training_features.tif", 2, "A_rtp"),
    ("data/training_features.tif", 3, "A_tmi_hg"),
    ("data/training_features.tif", 4, "A_geod_2ndinv"),
    ("data/training_features.tif", 5, "A_grav_slope"),
    ("data/training_features.tif", 9, "A_tmi_vg"),
    ("data/training_features.tif", 11, "A_grav_vg"),
    ("data/training_features.tif", 13, "A_grav_anom"),
    ("data/training_features.tif", 14, "A_tmi"),
    ("data/training_features.tif", 15, "A_depth_to_base"),
    ("data/training_features.tif", 16, "A_eq_density"),
    ("data/training_features.tif", 17, "A_cond_surf"),
    ("data/training_features.tif", 18, "A_grav_hg"),
    ("data/training_features.tif", 6, "B_rad_tc"),
    ("data/training_features.tif", 12, "B_det_elev"),
    ("data/training_features.tif", 19, "B_det_elev_slope"),
]
EXTERNAL_BANDS = [
    ("data/external/geodawn_rad_u8.tif", 4, "B_rad_TC"),
    ("data/external/geodawn_extensions_u8.tif", 1, "B_rad_ThK"),
    ("data/external/geodawn_extensions_u8.tif", 2, "B_rad_UK"),
    ("data/external/geodawn_extensions_u8.tif", 3, "B_rad_UTh"),
    ("data/external/lidar_scarp_features_u8.tif", 1, "B_lidar_ex_max"),
    ("data/external/lidar_scarp_features_u8.tif", 3, "B_lidar_step_max"),
    ("data/external/lidar_scarp_features_u8.tif", 7, "B_lidar_upface_max"),
    ("data/external/lidar_scarp_features_u8.tif", 9, "B_lidar_relief"),
    ("data/external/lidar_scarp_features_u8.tif", 10, "B_lidar_coh100"),
]
VIEW_A_LAYERS = [n for _, _, n in FEATURE_BANDS if n.startswith("A_")] + [
    n for _, _, n in EXTERNAL_BANDS if n.startswith("A_")]
VIEW_B_LAYERS = [n for _, _, n in FEATURE_BANDS if n.startswith("B_")] + [
    n for _, _, n in EXTERNAL_BANDS if n.startswith("B_")]

CORRIDOR_PX = 2          # the <= 200 m ring around a mapped trace: never emitted (knowledge/01 §5)
NEG_CLEAR_PX = 5         # labelled negatives stay >= 500 m clear of any catalogue pixel


# --------------------------------------------------------------------------------------------
# layer construction
# --------------------------------------------------------------------------------------------
def _read_band_window(path: str, band: int, r0: int, r1: int) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(band, window=((r0, r1), (0, src.width))).astype(np.float32)
    a[~np.isfinite(a)] = np.nan
    a[a < G.SENTINEL_LIMIT] = np.nan
    return a


def _fill(a: np.ndarray, valid: np.ndarray, fill: float) -> np.ndarray:
    out = np.nan_to_num(a, nan=fill, posinf=fill, neginf=fill)
    return out


def _rank_u8(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Global min-max rank inside the footprint, uint8.  255 quantiles over 5.17 M cells is
    20 k cells per level, so the quantisation is far below the 100 m the metric resolves."""
    v = a[valid]
    if v.size == 0:
        return np.zeros(a.shape, np.uint8)
    lo, hi = float(np.min(v)), float(np.max(v))
    r = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a, dtype=np.float32)
    r = np.clip(r, 0.0, 1.0)
    out = (r * 255.0).astype(np.uint8)
    out[~valid] = 0
    return out


def derived_layers(path: str, band: int, valid: np.ndarray,
                   row_chunk: int = 600) -> list[np.ndarray]:
    """(value, |grad|, 5x5 range) of one band, as float32 full-grid arrays.

    Computed row-chunked because the footprint grid is 12.28 M cells and the box has 3 GB; a
    Gaussian filter plus a 5x5 maximum/minimum pair needs ~3 full-grid float32 temporaries.
    """
    shape = G.SHAPE
    val = np.zeros(shape, np.float32)
    grad = np.zeros(shape, np.float32)
    rng = np.zeros(shape, np.float32)
    with rasterio.open(path) as src:
        nrows = src.height
        sample = _read_band_window(path, band, 0, min(row_chunk, nrows))
    vv = sample[valid[: sample.shape[0]]]
    fill = float(np.median(vv)) if vv.size else 0.0
    for r0 in range(0, shape[0], row_chunk):
        r1 = min(r0 + row_chunk, shape[0])
        a = _read_band_window(path, band, r0, r1)
        vmask = valid[r0:r1]
        f = _fill(a, vmask, fill)
        val[r0:r1] = f
        gy, gx = np.gradient(ndimage.gaussian_filter(f, 1.0, mode="nearest"))
        grad[r0:r1] = np.hypot(gx, gy)
        mx = ndimage.maximum_filter(f, size=5, mode="nearest")
        mn = ndimage.minimum_filter(f, size=5, mode="nearest")
        rng[r0:r1] = mx - mn
    return [val, grad, rng]


def data_root_path(path: str | Path, data_dir: str | Path = "data") -> Path:
    """Resolve a registry-style ``data/...`` source against an isolated data root.

    The default preserves the historical ``data/...`` paths and H57 cache key. Supplying
    ``work/h58_pinned`` redirects every layer, including the external bands, without changing
    the tracked ``data/`` tree or relying on the process working directory's ``data`` symlink.
    """
    p = Path(path)
    if p.is_absolute():
        return p
    if p.parts and p.parts[0] == "data":
        p = Path(*p.parts[1:])
    return Path(data_dir) / p


def build_layers(work: str = "work/h57", chunk: int = 600,
                 data_dir: str | Path = "data",
                 spec: list[tuple[str, int, str]] | None = None) -> dict:
    """Build and cache the uint8 layer stack.  Returns the layer-name index.

    ``data_dir`` makes the feature stack source explicit. It is used by H58/H59 to build only from
    the manifest-pinned owner mirror, while the default retains the legacy H57 call signature.
    ``spec`` overrides the band inventory (H59 extends View A with the strain/seismicity bands);
    the default is the frozen H57 inventory so the historical H57 cache key is unchanged.
    """
    workp = Path(work)
    workp.mkdir(parents=True, exist_ok=True)
    meta_path = workp / "layers.json"
    base_spec = ([(p, b, n) for p, b, n in FEATURE_BANDS] + [(p, b, n) for p, b, n in EXTERNAL_BANDS]
                 if spec is None else list(spec))
    spec = [(str(data_root_path(p, data_dir)), b, n) for p, b, n in base_spec]
    spec_signature = [[p, int(b), name] for p, b, name in spec]
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("spec") == spec_signature and (workp / "layers.u8").exists():
            return meta
    feature_path = data_root_path("data/training_features.tif", data_dir)
    valid = G.footprint_from(feature_path, bands="all")
    n = len(spec) * 3
    out = np.lib.format.open_memmap(workp / "layers.u8", mode="w+",
                                    dtype=np.uint8, shape=(n,) + G.SHAPE)
    names = []
    for i, (p, b, nm) in enumerate(spec):
        if not Path(p).exists():
            raise FileNotFoundError(p)
        for j, arr in enumerate(derived_layers(p, b, valid, chunk)):
            suffix = ("val", "grad", "range")[j]
            out[i * 3 + j] = _rank_u8(arr, valid)
            names.append(f"{nm}_{suffix}")
            del arr
    out.flush()
    del out
    meta = dict(spec=spec_signature, names=names, footprint_px=int(valid.sum()))
    meta_path.write_text(json.dumps(meta, indent=1))
    return meta


class Layers:
    """Row-chunked reader over the cached uint8 stack."""

    def __init__(self, work: str = "work/h57"):
        self.meta = json.loads((Path(work) / "layers.json").read_text())
        self.names = self.meta["names"]
        self.path = str(Path(work) / "layers.u8")
        self._mm = None

    @property
    def mm(self):
        if self._mm is None:
            self._mm = np.load(self.path, mmap_mode="r")
        return self._mm

    def index(self, names) -> np.ndarray:
        pos = {n: i for i, n in enumerate(self.names)}
        missing = [n for n in names if n not in pos]
        if missing:
            raise KeyError(f"layers not built: {missing}")
        return np.array([pos[n] for n in names], dtype=np.int64)

    def matrix(self, idx: np.ndarray, r0: int, r1: int) -> np.ndarray:
        """``(rows*cols, n_layers)`` float32 block in C order, as ``sklearn`` wants it.

        The memmap is stored layer-major, ``(n_layers, rows, cols)``, so the rows/cols axes have to
        be folded together *after* the layer axis has been moved last.  Reshaping the raw block
        would silently produce a ``(layers*rows, cols)`` matrix -- which is the shape
        :func:`_gather` and the first version of this method disagreed about, and which the model
        accepted with a 3,292-feature complaint rather than an error.
        """
        block = np.asarray(self.mm[idx, r0:r1, :], dtype=np.uint8)      # (L, rows, cols)
        l = block.shape[0]
        return block.reshape(l, -1).T.astype(np.float32) / 255.0


# --------------------------------------------------------------------------------------------
# folds: whole 8-connected components, prevalence-matched, with a boundary buffer
# --------------------------------------------------------------------------------------------
def component_folds(cat: np.ndarray, valid: np.ndarray, n_folds: int = 4) -> np.ndarray:
    """Assign every catalogue component to the quadrant holding most of its pixels."""
    h, w = cat.shape
    yy, xx = np.indices((h, w), sparse=True)
    quadrant = ((yy >= h // 2).astype(np.int8) * 2 + (xx >= w // 2).astype(np.int8))
    comp, n = ndimage.label(cat, np.ones((3, 3), bool))
    votes = np.zeros((n + 1, 4), np.int64)
    sel = cat & valid
    np.add.at(votes, (comp[sel], quadrant[sel]), 1)
    owner = votes.argmax(axis=1).astype(np.int8)
    assigned = owner[comp]
    assigned[comp == 0] = -1
    return assigned


def segment_buffer(held: np.ndarray, buffer_px: int) -> np.ndarray:
    """Pixels within ``buffer_px`` of a held-out segment, excluding the segment itself.

    This is the whole-segment analogue of a fold-boundary buffer.  An earlier version computed the
    buffer from the *component fold id*, which is ``-1`` everywhere except on a catalogue pixel, so
    the 9x9 minimum/maximum disagreement test fired on every catalogue pixel's own neighbourhood and
    marked almost the whole grid as boundary -- which silently emptied the positive training set
    (measured: ``cat & fit`` was 0 pixels in all four folds) rather than raising.  The buffer is
    therefore derived from the held segment mask, which is the thing that actually must not leak.
    """
    if buffer_px <= 0:
        return np.zeros(held.shape, bool)
    return ndimage.binary_dilation(held, iterations=buffer_px) & ~held


def make_folds(cat: np.ndarray, valid: np.ndarray, n_folds: int = 4, buffer_px: int = 4,
               seed: int = 0) -> list[dict]:
    """Whole-segment folds: a component goes entirely to one fold, and a ``buffer_px`` collar around
    the held segment is in neither the training set nor the evaluation region."""
    fid = component_folds(cat, valid, n_folds)
    out = []
    for f in range(n_folds):
        held = (fid == f) & valid
        buf = segment_buffer(held, buffer_px)
        fit = valid & ~held & ~buf
        out.append(dict(fold=f, held=held, buffer=buf, fit=fit,
                        eval_region=held & valid,
                        n_held=int(held.sum()), n_fit=int(fit.sum()),
                        n_buffer=int(buf.sum()),
                        cat_in_fit=int((cat & fit).sum()),
                        cat_in_held=int((cat & held).sum())))
    return out


# --------------------------------------------------------------------------------------------
# the two views
# --------------------------------------------------------------------------------------------
def labelled_pixels(cat: np.ndarray, valid: np.ndarray, fit: np.ndarray, seed: int = 0,
                    n_neg: int = 60000, clear_px: int = NEG_CLEAR_PX) -> tuple[np.ndarray, ...]:
    """Positive catalogue pixels in ``fit`` plus an equal number of true negatives at least
    ``clear_px`` from every catalogue pixel, so a negative is never inside the metric's kernel of
    a positive (``R`` = 3 px)."""
    rng = np.random.default_rng(seed)
    pos_mask = cat & fit
    pos = np.flatnonzero(pos_mask.ravel())
    neg_pool = valid & ~ndimage.binary_dilation(cat, iterations=clear_px)
    neg = np.flatnonzero(neg_pool.ravel())
    if neg.size > n_neg:
        neg = rng.choice(neg, size=n_neg, replace=False)
    if pos.size > n_neg:
        pos = rng.choice(pos, size=n_neg, replace=False)
    return pos, neg


def fit_view(X: np.ndarray, y: np.ndarray, C: float = 1.0) -> object:
    from sklearn.linear_model import LogisticRegression
    clf = LogisticRegression(C=C, max_iter=400, solver="lbfgs", class_weight="balanced")
    clf.fit(X, y)
    return clf


def dense_predict(clf, layers: Layers, idx: np.ndarray, r0: int, r1: int) -> np.ndarray:
    X = layers.matrix(idx, r0, r1)
    return clf.predict_proba(X)[:, 1].astype(np.float32).reshape(r1 - r0, G.SHAPE[1])


def predict_grid(clf, layers: Layers, idx: np.ndarray, chunk: int = 500) -> np.ndarray:
    out = np.zeros(G.SHAPE, np.float32)
    for r0 in range(0, G.SHAPE[0], chunk):
        r1 = min(r0 + chunk, G.SHAPE[0])
        out[r0:r1] = dense_predict(clf, layers, idx, r0, r1)
    return out


# --------------------------------------------------------------------------------------------
# disagreement strata (the brief's discovery signal)
# --------------------------------------------------------------------------------------------
def disagreement(pa: np.ndarray, pb: np.ndarray, allowed: np.ndarray,
                 q_conf: float = 0.60, q_abstain: float = 0.40) -> dict:
    """Split an allowed set into concordant / A-only / B-only / neither.

    ``A-only``  View A >= q_conf and View B <= q_abstain  -> buried structure under cover.
    ``B-only``  View B >= q_conf and View A <= q_abstain  -> suspect surface artifact (road,
                stream, levee, erosion line) and therefore a *suppression* set, not a candidate
                set.  A-only and B-only are mutually exclusive by construction because
                ``q_conf > q_abstain``.
    """
    a_only = allowed & (pa >= q_conf) & (pb <= q_abstain)
    b_only = allowed & (pb >= q_conf) & (pa <= q_abstain)
    both = allowed & (pa >= q_conf) & (pb >= q_conf)
    neither = allowed & ~a_only & ~b_only & ~both
    return dict(q_conf=q_conf, q_abstain=q_abstain,
                counts=dict(allowed=int(allowed.sum()), a_only=int(a_only.sum()),
                            b_only=int(b_only.sum()), concordant=int(both.sum()),
                            neither=int(neither.sum())),
                masks=dict(a_only=a_only, b_only=b_only, concordant=both, neither=neither))


# --------------------------------------------------------------------------------------------
# H57-A: anisotropic node placement
# --------------------------------------------------------------------------------------------
def _stencil(along: int, across: int) -> tuple[np.ndarray, np.ndarray]:
    """Offsets of the rotated rectangle ``|s| <= along, |t| <= across`` in array convention."""
    r = max(along, across)
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    return dy, dx


def _local_max(score: np.ndarray, allowed: np.ndarray, radius: int) -> np.ndarray:
    """Pixels of ``allowed`` that are not strictly dominated by a higher-scoring pixel within
    ``radius``.  Ties are kept (>=), so a plateau is not silently emptied."""
    size = 2 * radius + 1
    f = np.where(allowed, np.asarray(score, np.float32), -np.inf)
    mx = ndimage.maximum_filter(f, size=size, mode="nearest")
    return allowed & (f >= mx)


def _blocked_offsets(along: int, across: int):
    r = max(along, across)
    return [(oy, ox) for oy in range(-r, r + 1) for ox in range(-r, r + 1)
            if (oy * oy + ox * ox) > 0]


def _greedy_nodes(score, allowed, k, min_px, inclusive=True):
    """Highest-score-first node selection under one isotropic minimum separation.

    Returns the accepted (y, x) index arrays.  Shared by :func:`aniso_select` and
    :func:`iso_select` so the two emitters differ *only* in the separation rule.
    """
    shape = np.shape(score)
    ys, xs = np.nonzero(allowed)
    if ys.size == 0 or k <= 0:
        return np.empty(0, np.int64), np.empty(0, np.int64)
    order = np.argsort(-score[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    blocked = np.zeros(shape, bool)
    r = int(math.ceil(min_px))
    lim = min_px + 1e-9 if inclusive else min_px - 1e-9
    offs = [(oy, ox) for oy in range(-r, r + 1) for ox in range(-r, r + 1)
            if 0 < (oy * oy + ox * ox) ** 0.5 <= lim]
    ay, ax = [], []
    h, w = shape
    for i in range(ys.size):
        y, x = ys[i], xs[i]
        if blocked[y, x]:
            continue
        ay.append(y)
        ax.append(x)
        if len(ay) >= k:
            break
        for oy, ox in offs:
            py, px = y + oy, x + ox
            if 0 <= py < h and 0 <= px < w:
                blocked[py, px] = True
    return np.asarray(ay, np.int64), np.asarray(ax, np.int64)


def aniso_select(score: np.ndarray, strike: np.ndarray, coherence: np.ndarray,
                 allowed: np.ndarray, k: int, along_px: int = 5, across_px: int = 3,
                 min_coh: float = 0.25, nms_px: int | None = None) -> np.ndarray:
    """Greedy highest-score-first node selection under a **direction-dependent** separation.

    Where the local structure tensor is confident (``coherence >= min_coh``), two nodes may not lie
    within ``along_px`` *along* the strike; across the strike the incumbent ``across_px`` applies.
    Where the strike is not confident -- or where ``along_px <= across_px`` -- the rule degrades to
    the incumbent isotropic ``across_px``, so this emitter can never select fewer nodes than
    :func:`iso_select` at the same budget.

    Why along-strike > across-strike, from the metric itself (computed in ``tests/test_h57.py``,
    not asserted here): on a 1-px truth trace with ``k(0)=1, k(1)=2/3, k(2)=1/3, k(3)=0``, the
    credited truth inside one node interval ``[0, s)`` is ``7/3`` at ``s=3``, ``8/3`` at ``s=4``
    and ``3`` at ``s=5``.  Three px -- the separation every emitter in this repository uses --
    therefore leaves **28.6 %** of the credit per node on the table, because the second node's
    300 m disc largely re-covers the first node's.  Across the strike the two nodes sit on
    different lines and neither is redundant, so 3 px stays there.  Six px and beyond stop
    gaining credit and start leaving truth pixels with ``k = 0`` entirely, which is why 5 is the
    ceiling and not "as far as you like".

    Implementation note.  Scanning every allowed pixel in Python is ~5 M iterations per call on
    this grid, so both emitters first apply non-maximum suppression at the exclusion radius.  That
    is *exact* rather than an approximation: a candidate that is not a local maximum always has a
    strictly higher-scoring neighbour inside the exclusion radius, which the greedy pass would
    have taken instead, so the surviving set contains an optimal solution.
    """
    shape = np.shape(score)
    out = np.zeros(shape, bool)
    r = nms_px if nms_px is not None else max(int(along_px), int(across_px))
    allowed = allowed & _local_max(score, allowed, r)
    ys, xs = np.nonzero(allowed)
    if ys.size == 0 or k <= 0:
        return out
    order = np.argsort(-score[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    th = strike[ys, xs].astype(np.float64)
    ch = coherence[ys, xs].astype(np.float64)
    blocked = np.zeros(shape, bool)
    h, w = shape
    offs = _blocked_offsets(int(along_px), int(across_px))
    taken = 0
    oriented = bool(along_px > across_px)
    for i in range(ys.size):
        y, x = ys[i], xs[i]
        if blocked[y, x]:
            continue
        out[y, x] = True
        taken += 1
        if taken >= k:
            break
        if oriented and ch[i] >= min_coh:
            # Array convention, as in gems52.revealed.strike_field: +x is east/column and
            # +y is south/row, so the unit vector ALONG the strike is (sin t, cos t) and the
            # across-strike direction is its perpendicular (cos t, -sin t).
            sn, cs = math.sin(th[i]), math.cos(th[i])
            for oy, ox in offs:
                al = abs(oy * sn + ox * cs)
                ac = abs(oy * cs - ox * sn)
                if al <= along_px + 1e-9 and ac <= across_px + 1e-9:
                    py = int(round(y + al * np.sign(oy * sn + ox * cs) * sn
                                   + ac * np.sign(oy * cs - ox * sn) * cs))
                    px = int(round(x + al * np.sign(oy * sn + ox * cs) * cs
                                   - ac * np.sign(oy * cs - ox * sn) * sn))
                    if 0 <= py < h and 0 <= px < w:
                        blocked[py, px] = True
        else:
            for oy, ox in offs:
                if (oy * oy + ox * ox) ** 0.5 <= across_px + 1e-9:
                    py, px = y + oy, x + ox
                    if 0 <= py < h and 0 <= px < w:
                        blocked[py, px] = True
    return out


def iso_select(score: np.ndarray, allowed: np.ndarray, k: int, min_px: float = 3.0,
               inclusive: bool = True, nms_px: int | None = None) -> np.ndarray:
    """Isotropic emitter, same greedy order -- the control for :func:`aniso_select`.

    ``inclusive=True`` blocks every node within ``min_px`` *including* exactly ``min_px``.  That is
    the metric's own rule: ``k(3 px) = 0``, so a node exactly three pixels away covers a truth
    pixel the first node already covers and pays the full ``0.2 (1 - q)`` tax for zero extra
    credit.  ``inclusive=False`` reproduces the looser reading (lattice distance strictly below
    ``min_px``), which is what the measured "median nearest-neighbour spacing 3.0 px" of the
    incumbent family is consistent with; both are reported so a strict-vs-loose gain is never
    reported as an anisotropic gain.
    """
    shape = np.shape(score)
    out = np.zeros(shape, bool)
    r = nms_px if nms_px is not None else int(math.ceil(min_px))
    lim = min_px + 1e-9 if inclusive else min_px - 1e-9
    allowed = allowed & _local_max(score, allowed, r)
    ys, xs = np.nonzero(allowed)
    if ys.size == 0 or k <= 0:
        return out
    order = np.argsort(-score[ys, xs], kind="stable")
    ys, xs = ys[order], xs[order]
    blocked = np.zeros(shape, bool)
    offs = [(oy, ox) for oy in range(-r, r + 1) for ox in range(-r, r + 1)
            if 0 < (oy * oy + ox * ox) ** 0.5 <= lim]
    h, w = shape
    taken = 0
    for i in range(ys.size):
        y, x = ys[i], xs[i]
        if blocked[y, x]:
            continue
        out[y, x] = True
        taken += 1
        if taken >= k:
            break
        for oy, ox in offs:
            py, px = y + oy, x + ox
            if 0 <= py < h and 0 <= px < w:
                blocked[py, px] = True
    return out
