"""Per-structure geological reasoning for an emitted field.

A submission is a set of pixels; a reviewer needs to know *why* each structure is there.
This module groups an emission into connected structures and reports, for each, the
layers that most distinguish it from the footprint background, plus how far it sits from
the catalogue.

The reductions are vectorised on purpose.  The first version looped over structures and
re-opened the memmap inside the loop, which is both slow and the reason that run never
finished: 3,000 structures times 74 layers is 222,000 memmap reads.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy import ndimage


def _group_min(values: np.ndarray, gids: np.ndarray, n: int) -> np.ndarray:
    """Minimum of ``values`` within each group id, vectorised."""
    out = np.full(n, np.inf, dtype=np.float64)
    np.minimum.at(out, gids, values)
    out[~np.isfinite(out)] = np.nan
    return out


def _group_any(mask: np.ndarray, gids: np.ndarray, n: int) -> np.ndarray:
    """Whether each group contains at least one True, vectorised."""
    gids = np.asarray(gids, dtype=np.int64)
    return np.bincount(gids[np.asarray(mask, dtype=bool)], minlength=n) > 0


def _group_mean(values: np.ndarray, gids: np.ndarray, n: int) -> np.ndarray:
    s = np.bincount(gids, weights=values, minlength=n)
    c = np.bincount(gids, minlength=n)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / np.maximum(c, 1), np.nan)


def reason_table(mask: np.ndarray, stack, meta: dict, dist_to_catalogue: np.ndarray,
                 footprint: np.ndarray, score: np.ndarray | None = None,
                 max_layers: int = 3, min_px: int = 4) -> list[dict]:
    """One row per connected structure in ``mask``, with its distinguishing layers.

    "Distinguishing" is measured as the difference between the structure's mean rank and
    the footprint's mean rank on each layer, in units of the footprint's standard
    deviation.  Rank-scores are used throughout so the heavy tails in the raw layers
    (IR-R4-002) cannot let one pixel dominate a structure's profile.
    """
    m = np.asarray(mask, dtype=bool)
    lab, n = ndimage.label(m, structure=np.ones((3, 3), dtype=int))
    if n == 0:
        return []
    gid = lab[m].astype(np.int64)
    gsize = np.bincount(gid, minlength=n + 1)
    keep_ids = np.nonzero(gsize >= min_px)[0]
    keep_ids = keep_ids[keep_ids > 0]
    if keep_ids.size == 0:
        return []

    rows, cols = np.nonzero(m)
    dist = np.asarray(dist_to_catalogue, dtype=np.float32)

    # footprint background statistics, one layer at a time
    names = meta["layers"]
    nl = len(names)
    bg_mean = np.zeros(nl, dtype=np.float64)
    bg_std = np.ones(nl, dtype=np.float64)
    fp_idx = np.nonzero(np.asarray(footprint, dtype=bool))
    chunk = 2_000_000
    sums = np.zeros(nl, dtype=np.float64)
    sqs = np.zeros(nl, dtype=np.float64)
    cnt = 0
    for s in range(0, fp_idx[0].size, chunk):
        e = min(s + chunk, fp_idx[0].size)
        X = np.asarray(stack[:, fp_idx[0][s:e], fp_idx[1][s:e]], dtype=np.float32)
        good = np.isfinite(X)
        Xg = np.where(good, X, 0.0)
        sums += Xg.sum(axis=1)
        sqs += (Xg * Xg).sum(axis=1)
        cnt += good.sum(axis=1)
        del X, Xg, good
    with np.errstate(invalid="ignore", divide="ignore"):
        bg_mean = sums / np.maximum(cnt, 1)
        var = np.maximum(sqs / np.maximum(cnt, 1) - bg_mean ** 2, 0.0)
    bg_std = np.sqrt(var)
    bg_std[bg_std <= 0] = np.nan

    # structure-mean per layer, accumulated over the emitted pixels only
    X = np.asarray(stack[:, rows, cols], dtype=np.float32)     # (L, n_px)
    smean = np.zeros((nl, n + 1), dtype=np.float64)
    for i in range(nl):
        smean[i] = _group_mean(np.where(np.isfinite(X[i]), X[i], np.nan), gid, n + 1)
    del X

    dist_min = _group_min(dist[m].astype(np.float64), gid, n + 1)
    dist_mean = _group_mean(dist[m].astype(np.float64), gid, n + 1)
    score_mean = (_group_mean(np.asarray(score, dtype=np.float64)[m], gid, n + 1)
                  if score is not None else None)

    out = []
    for cid in keep_ids:
        with np.errstate(invalid="ignore"):
            z = (smean[:, cid] - bg_mean) / bg_std
        z = np.where(np.isfinite(z), z, -np.inf)
        top = np.argsort(-z)[:max_layers]
        row = {
            "structure_id": int(cid),
            "n_px": int(gsize[cid]),
            "mean_dist_to_catalogue_m": float(dist_mean[cid]) if np.isfinite(dist_mean[cid]) else None,
            "min_dist_to_catalogue_m": float(dist_min[cid]) if np.isfinite(dist_min[cid]) else None,
        }
        if score_mean is not None:
            row["mean_score"] = float(score_mean[cid]) if np.isfinite(score_mean[cid]) else None
        for k, li in enumerate(top):
            if not np.isfinite(z[li]):
                continue
            row[f"top{k + 1}_layer"] = names[li]
            row[f"top{k + 1}_z"] = float(z[li])
            row[f"top{k + 1}_mean_rank"] = float(smean[li, cid])
        out.append(row)
    return out


def write_csv(path: str, rows: list[dict]) -> str:
    """Write the reason table; returns the path written."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("")
        return str(p)
    fields = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with p.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return str(p)
