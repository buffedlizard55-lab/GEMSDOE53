"""Fitting, blocked cross-validation and full-grid prediction for the two views.

Three things here exist because the obvious implementation is wrong:

``gather``
    ``stack[np.ix_(layers, rows, cols)]`` is a *cross product* of the three index
    arrays.  With 44 layers and 300k sampled rows that asks numpy for 5.90 TiB and
    dies.  ``stack[:, rows, cols]`` broadcasts ``rows`` against ``cols`` element-wise
    instead, because the two advanced indices are adjacent; the result is ``(n, L)``
    which is what a design matrix wants.

``blocked_auc``
    A plain AUC over all pixels is dominated by the largest blocks and by the fact
    that faults are spatially contiguous, so a model that memorises one neighbourhood
    scores well.  Blocked AUC computes the AUC inside each 20 km block and averages
    over blocks, so every block counts once regardless of how many pixels it holds.
    Ranks are computed **within each block**, not globally.  This matters: the
    Mann-Whitney U statistic is defined on ranks 1..n of the block being scored, and
    substituting global ranks inflates every block's AUC by a constant -- with two
    positives and two negatives per block, a perfectly separated block scores 2.5
    instead of 1.0.  An earlier version of this function did exactly that and the
    docstring asserted the substitution was harmless; both are now fixed.

``rank_stack``
    The raw layers have wildly different tails -- band 10 reaches 4,962,515 m
    (IR-R4-002).  Every feature is rank-encoded to [0,1] inside the footprint before a
    learner sees it, which costs one sort per layer and makes the model immune to
    those tails.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier

from gems52.grid import PIXEL_M


# --------------------------------------------------------------------------------------
# rank encoding
# --------------------------------------------------------------------------------------

def rank_stack(out_dir: str = "work/cache", log=print) -> dict:
    """Write ``stack_rank.f32``: the stack with every layer rank-encoded to [0,1].

    One layer at a time, so peak memory is one grid plus its sort.  Ties share their
    average rank, which is what a rank-based model assumes.
    """
    out = Path(out_dir)
    meta = json.loads((out / "stack_meta.json").read_text())
    rows, cols = meta["shape"]
    n = meta["n_layers"]
    src = np.memmap(out / "stack.f32", dtype=np.float32, mode="r", shape=(n, rows, cols))
    dst = np.memmap(out / "stack_rank.f32", dtype=np.float32, mode="w+", shape=(n, rows, cols))
    valid = np.load(out / "footprint.npy")
    stats = {}
    for i, name in enumerate(meta["layers"]):
        a = np.asarray(src[i])
        r = np.full(a.shape, np.nan, dtype=np.float32)
        v = a[valid]
        good = np.isfinite(v)
        vg = v[good]
        if vg.size:
            rk = rankdata(vg).astype(np.float32)
            rk = (rk - 0.5) / vg.size
            out_v = np.full(v.shape, np.nan, dtype=np.float32)
            out_v[good] = rk
            r[valid] = out_v
        dst[i] = r
        dst.flush()
        stats[name] = {"finite_frac": float(good.mean()) if v.size else 0.0,
                       "n_ranked": int(good.sum())}
        del a, r, v
    dst.flush()
    del dst, src
    rm = dict(meta)
    rm["ranked"] = True
    (out / "stack_rank_meta.json").write_text(json.dumps(rm, indent=1))
    log(f"ranked {n} layers -> {out/'stack_rank.f32'}")
    return stats


def open_stack(out_dir: str = "work/cache", ranked: bool = True):
    out = Path(out_dir)
    meta = json.loads((out / ("stack_rank_meta.json" if ranked else "stack_meta.json")).read_text())
    rows, cols = meta["shape"]
    mm = np.memmap(out / ("stack_rank.f32" if ranked else "stack.f32"),
                   dtype=np.float32, mode="r", shape=(meta["n_layers"], rows, cols))
    return mm, meta


# --------------------------------------------------------------------------------------
# indexing and sampling
# --------------------------------------------------------------------------------------

def gather(stack, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
    """Element-wise gather of every layer at ``(rows[k], cols[k])`` -> ``(n, L)``.

    See the module docstring: this is deliberately not ``np.ix_``.
    """
    rows = np.ascontiguousarray(rows, dtype=np.intp)
    cols = np.ascontiguousarray(cols, dtype=np.intp)
    if rows.shape != cols.shape:
        raise ValueError(f"rows/cols shape mismatch: {rows.shape} vs {cols.shape}")
    # ``stack[:, rows, cols]`` indexes dims 1,2 with two *adjacent* advanced indices, so
    # numpy keeps the broadcast index dimension in place and the result is (L, n).  A
    # design matrix wants (n, L), hence the transpose.  Verified element-wise: with
    # L=2, n=2 this yields 4 values, where np.ix_ would have yielded 8.
    out = np.asarray(stack[:, rows, cols], dtype=np.float32)
    return np.ascontiguousarray(out.T)


def block_ids(shape, valid: np.ndarray, block_m: float = 20_000.0) -> np.ndarray:
    """Contiguous integer id of the ``block_m``-metre block containing each pixel.

    -1 outside the footprint, so callers can mask with ``bid >= 0``.  Only blocks that
    actually contain footprint pixels get an id, which is why a 3730x3292 grid at
    200 px blocks yields 142 blocks rather than the 323 the bounding box would suggest.
    """
    bp = max(1, int(round(block_m / PIXEL_M)))
    nrows, ncols = shape
    yy, xx = np.mgrid[0:nrows, 0:ncols]
    flat = (yy // bp) * (10_000) + (xx // bp)
    ids = np.full(shape, -1, dtype=np.int32)
    vals = flat[valid]
    uniq, inv = np.unique(vals, return_inverse=True)
    ids[valid] = inv.astype(np.int32)
    return ids


def make_block_folds(bid: np.ndarray, k: int = 5, seed: int = 20261008) -> np.ndarray:
    """Assign each block to one of ``k`` folds; returns a per-pixel fold array.

    Blocks, not pixels, are the unit: a fold boundary that cut through a block would
    let the model see the other half of the very structure it is being scored on.
    """
    nb = int(bid.max()) + 1
    rng = np.random.default_rng(seed)
    order = rng.permutation(nb)
    fold_of_block = np.empty(nb, dtype=np.int8)
    fold_of_block[order] = np.arange(nb) % k
    out = np.full(bid.shape, -1, dtype=np.int8)
    m = bid >= 0
    out[m] = fold_of_block[bid[m]]
    return out


def training_masks(labels: np.ndarray, valid: np.ndarray):
    """Positive (known fault) and negative masks inside the footprint."""
    lab = np.asarray(labels)
    inside = valid & np.isfinite(lab)
    pos = inside & (lab > 0.5)
    neg = inside & (lab <= 0.5) & (lab > -1e38)
    return pos, neg


def sample_training(pos: np.ndarray, neg: np.ndarray, max_pos: int = 60_000,
                    neg_per_pos: int = 4, seed: int = 20261008) -> dict:
    """Draw a class-balanced training sample; returns row/col index arrays.

    Positives are capped rather than exhausted: the catalogue is small enough that
    using all of it makes the fit depend on a handful of dense traces, and the cap keeps
    the design matrix at a predictable size.
    """
    rng = np.random.default_rng(seed)
    pr, pc = np.nonzero(pos)
    nr, nc = np.nonzero(neg)
    if pr.size > max_pos:
        sel = rng.choice(pr.size, size=max_pos, replace=False)
        pr, pc = pr[sel], pc[sel]
    want = min(nr.size, int(pr.size) * neg_per_pos)
    if nr.size > want:
        sel = rng.choice(nr.size, size=want, replace=False)
        nr, nc = nr[sel], nc[sel]
    rows = np.concatenate([pr, nr])
    cols = np.concatenate([pc, nc])
    y = np.concatenate([np.ones(pr.size, dtype=np.int8), np.zeros(nr.size, dtype=np.int8)])
    return {"rows": rows, "cols": cols, "y": y,
            "n_pos": int(pr.size), "n_neg": int(nr.size)}


# --------------------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------------------

def blocked_auc(y: np.ndarray, score: np.ndarray, bid: np.ndarray,
                min_each: int = 10) -> dict:
    """Mean per-block AUC, plus the per-block table needed to see which blocks fail.

    Blocks without both classes are skipped rather than scored 0.5, because 0.5 is a
    claim about separability in a block that contains no evidence either way.
    """
    y = np.asarray(y)
    score = np.asarray(score, dtype=np.float64)
    keep = bid >= 0
    y, score, b = y[keep], score[keep], bid[keep]
    nb = int(b.max()) + 1
    auc = np.full(nb, np.nan, dtype=np.float64)
    npos_a = np.zeros(nb, dtype=np.int64)
    nneg_a = np.zeros(nb, dtype=np.int64)
    for i in range(nb):
        m = b == i
        yy = y[m]
        if yy.size == 0:
            continue
        p = yy > 0.5
        np_i = int(p.sum())
        nn_i = int(yy.size - np_i)
        npos_a[i], nneg_a[i] = np_i, nn_i
        if np_i < min_each or nn_i < min_each:
            continue
        r = rankdata(score[m])          # ranks 1..n *within this block*
        auc[i] = (r[p].sum() - np_i * (np_i + 1.0) / 2.0) / (np_i * nn_i)
    good = auc[np.isfinite(auc)]
    return {
        "mean_auc": float(good.mean()) if good.size else float("nan"),
        "median_auc": float(np.median(good)) if good.size else float("nan"),
        "n_blocks_scored": int(good.size),
        "n_blocks_skipped": int(nb - good.size),
        "per_block": [float(x) if np.isfinite(x) else None for x in auc],
    }


# --------------------------------------------------------------------------------------
# fitting
# --------------------------------------------------------------------------------------

def _new_model(seed: int = 20261008):
    return HistGradientBoostingClassifier(
        max_iter=150, learning_rate=0.10, max_depth=6,
        min_samples_leaf=40, l2_regularization=1.0,
        early_stopping=False, random_state=seed,
    )


def fit_view(stack, layer_idx: list[int], sample: dict, bid: np.ndarray,
             fold: np.ndarray, seed: int = 20261008, log=print, cv: bool = True) -> dict:
    """Fit one view, returning out-of-fold scores and the blocked AUC.

    Out-of-fold means blocked out-of-fold: for each of the k folds the model is fitted
    on the other k-1 folds' blocks and scored on the held-out blocks, so no prediction
    ever comes from a model that saw a neighbouring part of the same structure.

    ``cv=False`` skips the cross-validation and returns only the full fit.  That is what
    the outer whole-segment holdout needs: it already holds out entire catalogue
    segments, so an inner block CV would be a second, redundant split -- and passing an
    all-zero fold array to request "no CV" silently produced an empty training set.
    """
    rows, cols, y = sample["rows"], sample["cols"], sample["y"]
    X = gather(stack, rows, cols)[:, layer_idx]
    s_bid = bid[rows, cols]
    s_fold = fold[rows, cols]
    oof = np.full(y.shape, np.nan, dtype=np.float32)
    res = None
    if cv:
        for f in np.unique(s_fold):
            if f < 0:
                continue
            tr = s_fold != f
            te = s_fold == f
            if tr.sum() == 0 or te.sum() == 0:
                continue
            m = _new_model(seed + int(f))
            m.fit(X[tr], y[tr])
            oof[te] = m.predict_proba(X[te])[:, 1].astype(np.float32)
            del m
        scored = np.isfinite(oof)
        if scored.any():
            res = blocked_auc(y[scored], oof[scored], s_bid[scored])
    full = _new_model(seed)
    full.fit(X, y)
    del X
    return {"oof": oof if cv else None, "blocked_auc": res, "model": full,
            "n_train": int(y.size), "n_layers": len(layer_idx),
            "oof_rows": rows, "oof_cols": cols}


def full_fit_predict(stack, layer_idx: list[int], model, valid: np.ndarray,
                     chunk: int = 400_000, log=print) -> np.ndarray:
    """Predict the model over the whole footprint, chunked, NaN outside.

    Chunked because the full design matrix is 5.1M rows x 44 columns at float32
    (about 900 MB), which does not fit in this box; 400k-row chunks keep the peak at
    roughly 70 MB.
    """
    rows, cols = np.nonzero(valid)
    out = np.full(valid.shape, np.nan, dtype=np.float32)
    for s in range(0, rows.size, chunk):
        e = min(s + chunk, rows.size)
        X = gather(stack, rows[s:e], cols[s:e])[:, layer_idx]
        out[rows[s:e], cols[s:e]] = model.predict_proba(X)[:, 1].astype(np.float32)
        del X
        if log and (s // chunk) % 5 == 0:
            log(f"    predicted {e}/{rows.size}", flush=True)
    return out
