"""Co-training between the two views, and the masks that make it honest.

Two subtleties in this module are the difference between a working round and a
silently broken one, and both cost real time to find.

``whole_segment_folds`` keeps the training-exclusion mask and the emission-allowed mask
    **separate**.  When a catalogue segment is held out to test whether the model can
    recover it, the held-out pixels (plus a buffer) must disappear from *training* --
    but they must stay inside the mask the emitter is allowed to place pixels in.  An
    earlier draft subtracted the training buffer from the emission mask as well, which
    made the held-out truth literally unplaceable: measured truth survival was 0.000.
    The emitter cannot recover what it is forbidden to emit.

``block_error_table`` ranks candidates over ``pos | allowed``, not over ``allowed``.
    Ranking inside the emission mask alone excludes the catalogue pixels themselves, so
    the "how many known faults did we miss" count is taken against a set that does not
    contain any known faults, and the miss rate came back all-NaN.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.stats import spearmanr


# --------------------------------------------------------------------------------------
# ranking helpers
# --------------------------------------------------------------------------------------

def _rank_within(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Tie-averaged rank of ``a`` in (0,1] among pixels selected by ``mask``.

    NaN elsewhere.  Ties are averaged rather than broken by position: with heavily
    quantised inputs (the LiDAR and radiometric layers are uint8) a large fraction of
    pixels are exactly tied, and breaking those ties by array order would make the
    "confident" set an artifact of row-major layout.
    """
    a = np.asarray(a, dtype=np.float64)
    out = np.full(a.shape, np.nan, dtype=np.float32)
    m = np.asarray(mask, dtype=bool) & np.isfinite(a)
    if not m.any():
        return out
    v = a[m]
    order = np.argsort(v, kind="mergesort")
    sv = v[order]
    diff = np.ones(sv.size, dtype=bool)
    if sv.size > 1:
        diff[1:] = sv[1:] != sv[:-1]
    grp = np.cumsum(diff) - 1
    pos = np.arange(sv.size, dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_pos = np.bincount(grp, weights=pos) / np.bincount(grp)
    r_sorted = mean_pos[grp]
    r = np.empty(sv.size, dtype=np.float64)
    r[order] = r_sorted
    out[m] = ((r + 0.5) / sv.size).astype(np.float32)
    return out


def confident_and_abstaining(score: np.ndarray, allowed: np.ndarray,
                             hi_q: float = 0.99, lo_q: float = 0.90) -> dict:
    """Split ``allowed`` into a confident head and an abstaining band.

    Both thresholds are quantiles *within the allowed set*, so the split does not move
    when the footprint changes size.  The confident head is what a view is allowed to
    teach from; the abstaining band is where it defers to the other view.
    """
    r = _rank_within(score, allowed)
    sel = np.isfinite(r)
    if not sel.any():
        return {"confident": np.zeros_like(allowed), "abstaining": np.zeros_like(allowed),
                "rank": r, "hi_value": None, "lo_value": None}
    vals = r[sel]
    hi = float(np.quantile(vals, hi_q))
    lo = float(np.quantile(vals, lo_q))
    return {
        "confident": (r >= hi) & allowed,
        "abstaining": (r >= lo) & (r < hi) & allowed,
        "rank": r,
        "hi_value": hi,
        "lo_value": lo,
    }


# --------------------------------------------------------------------------------------
# block-level error accounting
# --------------------------------------------------------------------------------------

def block_error_table(score: np.ndarray, pos: np.ndarray, allowed: np.ndarray,
                      bid: np.ndarray, budgets=(20_000, 37_654, 70_000)) -> list[dict]:
    """Per-block capture and miss rate at several budgets.

    Candidates are ranked over ``pos | allowed``.  See the module docstring: ranking over
    ``allowed`` alone removes the catalogue from the ranking set and the miss rate is
    undefined.

    ``capture`` is the fraction of that block's known positives that appear in the
    global top-k; ``miss_rate`` is 1 - capture.  Both are block-local so a block with
    no catalogue simply does not appear rather than diluting the average.
    """
    rank_mask = np.asarray(pos, dtype=bool) | np.asarray(allowed, dtype=bool)
    r = _rank_within(score, rank_mask)
    out = []
    for k in budgets:
        thr = _threshold_for_topk(r, rank_mask, int(k))
        if thr is None:
            out.append({"budget": int(k), "n_blocks": 0, "mean_capture": None,
                        "mean_miss_rate": None})
            continue
        picked = rank_mask & (r >= thr)
        caps, block_ids = [], []
        nb = int(bid.max()) + 1
        for i in range(nb):
            pb = (bid == i) & pos
            npos = int(pb.sum())
            if npos == 0:
                continue
            caps.append(float((picked & pb).sum()) / npos)
            block_ids.append(i)
        out.append({
            "budget": int(k),
            "n_blocks": len(caps),
            "mean_capture": float(np.mean(caps)) if caps else None,
            "mean_miss_rate": float(1.0 - np.mean(caps)) if caps else None,
            "threshold_rank": float(thr),
            "block_ids": block_ids,
            "per_block_capture": caps,
        })
    return out


def topk_mask(r: np.ndarray, mask: np.ndarray, k: int) -> np.ndarray:
    """Boolean mask of **exactly** the ``k`` highest-ranked pixels in ``mask``.

    A quantile threshold cannot guarantee an exact count: every pixel tied at the
    boundary value is included, which is how an emitter asked for 37,654 px shipped
    37,655.  Submissions are compared like-for-like at a fixed budget, so the count has
    to be exact; boundary ties are broken by ``argpartition``, deterministically.
    """
    m = np.asarray(mask, dtype=bool) & np.isfinite(r)
    idx = np.flatnonzero(m.ravel())
    if idx.size == 0 or k <= 0:
        return np.zeros(np.asarray(r).shape, dtype=bool)
    k = min(int(k), idx.size)
    vals = np.asarray(r).ravel()[idx]
    part = np.argpartition(vals, -k)[-k:]
    out = np.zeros(np.asarray(r).shape, dtype=bool)
    out.ravel()[idx[part]] = True
    return out


def _threshold_for_topk(r: np.ndarray, mask: np.ndarray, k: int):
    """Rank value at which exactly ``k`` masked pixels are at or above it, or None."""
    v = r[mask & np.isfinite(r)]
    if v.size == 0:
        return None
    k = min(k, v.size)
    return float(np.quantile(v, 1.0 - k / v.size))


# --------------------------------------------------------------------------------------
# independence
# --------------------------------------------------------------------------------------

def independence_verdict(score_a: np.ndarray, score_b: np.ndarray, bid: np.ndarray,
                         threshold: float = 0.60, min_px: int = 200) -> dict:
    """Per-block Spearman between the two views; the verdict is on the worst block.

    The brief asks the two views to be conditionally independent given the truth.  The
    test is not the global correlation (which is near zero by construction and tells
    you nothing) but the worst block: if the views agree strongly anywhere, they are
    not bringing independent evidence there.

    The threshold is a declared constant, 0.60, not a fitted one.
    """
    nb = int(bid.max()) + 1
    rhos, sizes = [], []
    for i in range(nb):
        m = (bid == i) & np.isfinite(score_a) & np.isfinite(score_b)
        n = int(m.sum())
        if n < min_px:
            continue
        a, b = score_a[m], score_b[m]
        if np.unique(a).size < 2 or np.unique(b).size < 2:
            continue
        rho = float(spearmanr(a, b).statistic)
        if np.isfinite(rho):
            rhos.append(rho)
            sizes.append(n)
    if not rhos:
        return {"n_blocks": 0, "max_abs_rho": None, "threshold": threshold,
                "independent": None, "verdict": "no_blocks"}
    rhos = np.asarray(rhos)
    mx = float(np.max(np.abs(rhos)))
    return {
        "n_blocks": int(rhos.size),
        "max_abs_rho": mx,
        "mean_abs_rho": float(np.mean(np.abs(rhos))),
        "threshold": threshold,
        "independent": bool(mx < threshold),
        "verdict": ("independent" if mx < threshold else "NOT independent"),
        "worst_block_rho": float(rhos[np.argmax(np.abs(rhos))]),
        "median_px_per_block": float(np.median(sizes)),
    }


# --------------------------------------------------------------------------------------
# pseudo-labelling
# --------------------------------------------------------------------------------------

def pseudo_labels(score_a: np.ndarray, score_b: np.ndarray, allowed: np.ndarray,
                  hi_q: float = 0.99, lo_q: float = 0.90) -> dict:
    """Each view teaches on the region where the other view abstains.

    A view's confident head is only used as a training label where the *other* view is
    in its abstaining band.  That is the whole point of co-training: agreement between
    two views is not new information, but one view being confident exactly where the
    other is uncertain is.
    """
    ca = confident_and_abstaining(score_a, allowed, hi_q, lo_q)
    cb = confident_and_abstaining(score_b, allowed, hi_q, lo_q)
    from_a = ca["confident"] & cb["abstaining"]
    from_b = cb["confident"] & ca["abstaining"]
    both = ca["confident"] & cb["confident"]
    return {
        "from_a": from_a,
        "from_b": from_b,
        "both_confident": both,
        "n_from_a": int(from_a.sum()),
        "n_from_b": int(from_b.sum()),
        "n_both": int(both.sum()),
        "a_rank": ca["rank"],
        "b_rank": cb["rank"],
    }


# --------------------------------------------------------------------------------------
# whole-segment holdout
# --------------------------------------------------------------------------------------

def whole_segment_folds(catalogue: np.ndarray, eligible: np.ndarray,
                        buffer_px: int = 20, k: int = 4,
                        seed: int = 20261008) -> list[dict]:
    """Hold out whole connected catalogue segments, one fold at a time.

    Returns one dict per fold with three masks that must be kept distinct:

    ``truth``
        The held-out catalogue pixels.  This is what recovery is scored against.
    ``train_exclude``
        Held-out pixels dilated by ``buffer_px``.  Removed from *training*, so the model
        cannot see the segment or its immediate surroundings.
    ``emission_allowed``
        Unchanged, and still contains the held-out segment.  The emitter must be able
        to place pixels there, otherwise measured survival is zero by construction.
    """
    cat = np.asarray(catalogue, dtype=bool)
    lab, n = ndimage.label(cat, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return []
    sizes = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1))
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    # size-balanced assignment: largest components first into the lightest fold
    fold_of = np.empty(n, dtype=int)
    load = np.zeros(k, dtype=np.int64)
    for ci in order[np.argsort(-sizes[order])]:
        f = int(np.argmin(load))
        fold_of[ci] = f
        load[f] += int(sizes[ci])
    folds = []
    for f in range(k):
        held = np.isin(lab, np.nonzero(fold_of == f)[0] + 1)
        truth = held & cat & np.asarray(eligible, dtype=bool)
        if not truth.any():
            continue
        if buffer_px > 0:
            dist = ndimage.distance_transform_edt(~held)
            train_exclude = dist <= buffer_px
        else:
            train_exclude = held.copy()
        folds.append({
            "fold": f,
            "truth": truth,
            "train_exclude": train_exclude,
            "emission_allowed": np.asarray(eligible, dtype=bool).copy(),
            "n_truth": int(truth.sum()),
            "n_train_exclude": int(train_exclude.sum()),
            "truth_contained_in_emission": bool(np.all(truth[truth] <= eligible[truth])),
        })
    return folds


def truth_survival(fold: dict) -> float:
    """Fraction of held-out truth pixels that the emission mask still permits.

    Must be 1.0 for every fold.  Anything lower means the holdout is measuring the
    mask, not the model -- the exact failure this module was rewritten to fix.
    """
    t = fold["truth"]
    if not t.any():
        return float("nan")
    return float(fold["emission_allowed"][t].mean())
