"""Accessibility bias: how far an emission sits from the catalogue, and how to remove it.

The halo defect
---------------
The training target ("a fault is mapped here") and the evaluation truth ("a fault exists
here and is NOT in the catalogue") are inversely related.  Measured last round: our
top-37,654 pixels sat a median of 412 m from the nearest catalogue trace with 58% inside
500 m, while the champion's sat a median of 1,965 m away with nothing at all inside
300 m.  Deleting a 6,436-pixel ring within 200 m of a mapped trace from an earlier
submission cost **exactly zero** credit, which is the cleanest available proof that
near-catalogue emission is not rewarded.

So a model trained to predict the catalogue learns to hug it, and the distance-to-
catalogue distribution of its emission is a direct read-out of how much of its score is
accessibility rather than geology.  The functions here measure that, and
``residual_field`` strips the distance trend out of a score so what is left can be
inspected without the halo dominating.
"""

from __future__ import annotations

import numpy as np


def distance_histogram(mask: np.ndarray, dist: np.ndarray,
                       bins=(0, 100, 200, 300, 500, 750, 1000, 2000, 4000, 1e9)) -> dict:
    """Distribution of catalogue-distance over an emitted set, in metres.

    The bin edges are fixed rather than adaptive so two submissions can be compared
    bin-for-bin.  The first three bins matter most: they are where the halo lives.
    """
    m = np.asarray(mask, dtype=bool)
    d = np.asarray(dist, dtype=np.float32)
    v = d[m & np.isfinite(d)]
    edges = np.asarray(bins, dtype=np.float64)
    counts, _ = np.histogram(v, bins=edges)
    out = {
        "n": int(v.size),
        "edges_m": [float(x) if np.isfinite(x) else None for x in edges],
        "counts": [int(c) for c in counts],
        "median_m": float(np.median(v)) if v.size else None,
        "mean_m": float(np.mean(v)) if v.size else None,
    }
    for lim in (300.0, 500.0, 1000.0):
        out[f"frac_within_{int(lim)}m"] = float(np.mean(v <= lim)) if v.size else None
    return out


def match_distance_histogram(source_mask: np.ndarray, target_hist: dict,
                             dist: np.ndarray) -> np.ndarray:
    """Per-pixel weights that make ``source``'s distance distribution match ``target``'s.

    Comparing two emissions at different budgets confounds size with placement.  Matching
    the distance histogram first removes the placement part, so whatever difference
    remains is attributable to the field rather than to where it happens to sit relative
    to the catalogue.
    """
    m = np.asarray(source_mask, dtype=bool)
    d = np.asarray(dist, dtype=np.float64)
    edges = np.asarray([np.inf if x is None else x for x in target_hist["edges_m"]],
                       dtype=np.float64)
    src_counts, _ = np.histogram(d[m & np.isfinite(d)], bins=edges)
    tgt = np.asarray(target_hist["counts"], dtype=np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.where(src_counts > 0, tgt / np.maximum(src_counts, 1.0), 0.0)
    idx = np.digitize(d, edges[1:-1], right=False)
    out = np.zeros(d.shape, dtype=np.float32)
    out[m & np.isfinite(d)] = w[np.clip(idx[m & np.isfinite(d)], 0, w.size - 1)]
    return out


def residual_field(field: np.ndarray, dist: np.ndarray,
                   bins=(0, 200, 400, 600, 800, 1000, 1500, 2000, 3000, 1e9)) -> np.ndarray:
    """Subtract the per-distance-bin mean from ``field``.

    What survives is the part of the score that is not explained by how far a pixel sits
    from the catalogue -- i.e. the part that is not halo.
    """
    f = np.asarray(field, dtype=np.float32)
    d = np.asarray(dist, dtype=np.float64)
    ok = np.isfinite(f) & np.isfinite(d)
    edges = np.asarray(bins, dtype=np.float64)
    idx = np.digitize(d, edges[1:-1], right=False)
    out = np.full(f.shape, np.nan, dtype=np.float32)
    for i in range(len(edges) - 1):
        m = ok & (idx == i)
        if not m.any():
            continue
        out[m] = f[m] - float(np.mean(f[m]))
    return out
