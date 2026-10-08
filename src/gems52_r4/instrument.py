"""Local pseudo-truth: build a synthetic hidden-fault set and score candidates against it.

Why this module exists, and why it must be distrusted
-----------------------------------------------------
The competition's truth ``|G|`` is never published, so a candidate cannot be scored
directly.  The workaround is to build a *pseudo-truth* ``G*`` -- take the known fault
catalogue, hide part of it, displace the hidden part to positions no catalogue records,
and score candidates against that with the real DTI metric.  It is the only in-house
assay available, and last round it produced the round's most important negative result:

    **Every such instrument measures budget, not geology.**

Within one design family the board score is a strictly monotone function of emission
size (Spearman(board, -S) = +1.0000), so a candidate that "beats" the incumbent is
mostly a candidate that spent a different budget.  Regressing the instrument against
the board with budget partialled out leaves an *exactly zero* residual -- and the first
implementation reported that as ``r = +0.0000, p = 1.0``, which reads as "no
relationship" and is the opposite of the truth: the relationship is perfect and the
regression is degenerate.  ``budget_confound`` now returns ``degenerate=True`` with
``r = None`` in that case.  A fabricated null is worse than no assay at all.

The control that settles it: uniform random scored 0.0670 at 70,000 px against the
champion's 0.052650.  An assay on which uniform random beats the incumbent cannot
promote anything, and does not.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.stats import rankdata, spearmanr

from gems52.metric import dti


# --------------------------------------------------------------------------------------
# catalogue geometry
# --------------------------------------------------------------------------------------

def component_isolation(catalogue: np.ndarray, valid: np.ndarray) -> dict:
    """Label the connected components of the catalogue inside the footprint.

    Components are the natural unit for hiding: a fault is a structure, not a pixel, and
    hiding 40% of pixels chosen at random leaves every fault half-visible.
    """
    cat = np.asarray(catalogue, dtype=bool) & np.asarray(valid, dtype=bool)
    lab, n = ndimage.label(cat, structure=np.ones((3, 3), dtype=int))
    sizes = ndimage.sum(np.ones_like(lab, dtype=np.float64), lab, range(1, n + 1)) if n else np.zeros(0)
    return {"labels": lab, "n": int(n), "sizes": np.asarray(sizes, dtype=np.int64),
            "n_px": int(cat.sum())}


def _dispersed_displacements(n: int, seed: int, min_px: float = 50.0,
                             max_px: float = 400.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0.0, 2.0 * np.pi, size=n)
    rad = rng.uniform(min_px, max_px, size=n)
    return np.column_stack([rad * np.sin(ang), rad * np.cos(ang)])


def clustered_displacement_samples(n: int, seed: int, n_clusters: int = 6,
                                   radius_px: float = 60.0,
                                   max_px: float = 400.0) -> np.ndarray:
    """Displacements concentrated around a handful of centres.

    The geological alternative to the dispersed prior: if undiscovered faults cluster
    (along a releasing bend, a stepover, a geothermal field) rather than scatter
    uniformly, an instrument tuned to the dispersed prior will mis-rank candidates that
    are right for the wrong reason.  Both priors are built; agreement between them is
    the evidence, not either one alone.
    """
    rng = np.random.default_rng(seed)
    centres = rng.uniform(-max_px, max_px, size=(n_clusters, 2))
    which = rng.integers(0, n_clusters, size=n)
    jitter = rng.normal(0.0, radius_px, size=(n, 2))
    return centres[which] + jitter


# --------------------------------------------------------------------------------------
# pseudo-truth construction
# --------------------------------------------------------------------------------------

def build_pseudo_truth(catalogue: np.ndarray, valid: np.ndarray, seed: int = 52008,
                       hide_fraction: float = 0.45, mode: str = "dispersed",
                       target_px: int = 13_500, **kw) -> dict:
    """Build ``G*``: a synthetic hidden-fault set with no catalogue support.

    A fraction of catalogue components is *hidden* and translated to new positions; the
    rest stays put and represents faults the organisers' truth also contains.  Candidates
    are then scored with the real DTI against ``G*``.

    The result is density-matched to ``target_px`` by resampling the displaced set, so
    two priors (dispersed vs clustered) can be compared at equal ``|G*|`` -- otherwise
    the comparison is partly a comparison of set sizes, which is the budget confound
    re-entering through the back door.
    """
    if mode not in ("dispersed", "clustered"):
        raise ValueError(f"mode must be 'dispersed' or 'clustered', got {mode!r}")
    iso = component_isolation(catalogue, valid)
    lab, n = iso["labels"], iso["n"]
    if n == 0:
        raise ValueError("catalogue has no components inside the footprint")
    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    n_hide = max(1, int(round(hide_fraction * n)))
    hidden = order[:n_hide]
    kept = order[n_hide:]

    disp = (_dispersed_displacements(n_hide, seed, **kw) if mode == "dispersed"
            else clustered_displacement_samples(n_hide, seed, **kw))

    shape = lab.shape
    g = np.zeros(shape, dtype=bool)
    g[np.isin(lab, kept + 1)] = True           # the part of the truth we also know

    moved = 0
    for j, ci in enumerate(hidden):
        rr, cc = np.nonzero(lab == ci + 1)
        dy, dx = disp[j]
        r2 = np.clip(np.round(rr + dy).astype(int), 0, shape[0] - 1)
        c2 = np.clip(np.round(cc + dx).astype(int), 0, shape[1] - 1)
        ok = valid[r2, c2]
        if ok.any():
            g[r2[ok], c2[ok]] = True
            moved += int(ok.sum())

    # density match to target_px
    n_now = int(g.sum())
    if n_now > target_px:
        idx = np.flatnonzero(g.ravel())
        drop = rng.choice(idx, size=n_now - target_px, replace=False)
        flat = g.ravel()
        flat[drop] = False
        g = flat.reshape(shape)
    elif n_now < target_px:
        idx = np.flatnonzero((valid & ~g).ravel())
        add = rng.choice(idx, size=min(target_px - n_now, idx.size), replace=False)
        flat = g.ravel()
        flat[add] = True
        g = flat.reshape(shape)

    return {
        "G": g,
        "mode": mode,
        "seed": int(seed),
        "n_components": int(n),
        "n_hidden": int(n_hide),
        "n_kept": int(len(kept)),
        "moved_px": int(moved),
        "size_px": int(g.sum()),
        "target_px": int(target_px),
        "size_before_match": n_now,
    }


def score_against(emission: np.ndarray, g_star: np.ndarray) -> dict:
    """DTI of an emission field against ``G*``, using the competition metric.

    The emission is treated as a weight-1 binary field, which is what a submission
    actually contains; partial weights are legal in the metric but we never ship them.
    """
    p = np.where(np.isfinite(emission), np.asarray(emission, dtype=np.float64), 0.0)
    p = np.clip(p, 0.0, 1.0)
    r = dti(p, np.asarray(g_star, dtype=np.float64))
    r["budget"] = int((p > 0).sum())
    return r


# --------------------------------------------------------------------------------------
# the confound test
# --------------------------------------------------------------------------------------

def _resid(y: np.ndarray, Z: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
    return y - Z @ beta


def budget_confound(x, board, budget, rel_tol: float = 1e-9) -> dict:
    """Spearman of ``x`` against ``board`` with ``budget`` partialled out.

    ``x`` is an instrument score, ``board`` the leaderboard score, ``budget`` the emission
    size.  All three are rank-transformed first, so this is a rank-on-rank partial
    correlation and is insensitive to monotone rescaling of any of them.

    **Degeneracy.**  If either residual has (numerically) zero variance the regression is
    degenerate and there is no partial correlation to report.  This happens when the
    board is a strictly monotone function of budget over the sample -- then regressing
    the board on budget explains all of it and the residual is exactly zero.  In that
    case ``r`` and ``p`` are ``None`` and ``degenerate`` is ``True``.  Returning
    ``r = 0.0, p = 1.0`` there is a lie: it reads as "no relationship" when the truth is
    "the relationship is perfect and cannot be separated from budget".
    """
    x = np.asarray(x, dtype=np.float64).ravel()
    b = np.asarray(board, dtype=np.float64).ravel()
    s = np.asarray(budget, dtype=np.float64).ravel()
    ok = np.isfinite(x) & np.isfinite(b) & np.isfinite(s)
    n = int(ok.sum())
    if n < 4:
        return {"r": None, "p": None, "n": n, "degenerate": True,
                "reason": f"n={n} too small for a partial correlation"}
    rx, rb, rs = rankdata(x[ok]), rankdata(b[ok]), rankdata(s[ok])
    Z = np.column_stack([np.ones(n), rs])
    ex, eb = _resid(rx, Z), _resid(rb, Z)
    tol_x = rel_tol * max(float(np.std(rx)), 1.0)
    tol_b = rel_tol * max(float(np.std(rb)), 1.0)
    degenerate = bool(np.std(ex) <= tol_x or np.std(eb) <= tol_b)
    raw = spearmanr(rx, rb)
    out = {
        "n": n,
        "raw_rho": float(raw.statistic) if np.isfinite(raw.statistic) else None,
        "raw_p": float(raw.pvalue) if np.isfinite(raw.pvalue) else None,
        "degenerate": degenerate,
        "resid_sd_x": float(np.std(ex)),
        "resid_sd_board": float(np.std(eb)),
    }
    if degenerate:
        out.update({"r": None, "p": None,
                    "reason": "zero-variance residual after regressing on budget; "
                              "board is monotone in budget over this sample, so no "
                              "budget-free relationship can be estimated"})
    else:
        pr = spearmanr(ex, eb)
        out.update({"r": float(pr.statistic), "p": float(pr.pvalue)})
    return out


# --------------------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------------------

def validate(rows: list[dict]) -> dict:
    """Run the full confound work-up over a set of {name, score, board, budget} rows.

    Also reports the uniform-random control verdict: if random at any budget scores at or
    above the incumbent, the instrument is declared unable to promote, and every other
    number here is moot.
    """
    if len(rows) < 3:
        return {"n": len(rows), "ok": False,
                "reason": "need at least 3 submissions for a rank correlation"}
    score = np.array([r["score"] for r in rows], dtype=np.float64)
    board = np.array([r["board"] for r in rows], dtype=np.float64)
    budget = np.array([r["budget"] for r in rows], dtype=np.float64)
    conf = budget_confound(score, board, budget)
    raw = spearmanr(score, board)
    out = {
        "n": len(rows),
        "names": [r["name"] for r in rows],
        "raw_rho": float(raw.statistic),
        "raw_p": float(raw.pvalue),
        "budget_partial": conf,
        "spearman_board_vs_neg_budget": float(spearmanr(board, -budget).statistic),
    }
    # random control
    rnd = [r for r in rows if r.get("kind") == "random"]
    inc = [r for r in rows if r.get("kind") == "incumbent"]
    if rnd and inc:
        best_rnd = max(r["score"] for r in rnd)
        inc_score = max(r["score"] for r in inc)
        out["random_control"] = {
            "best_random_score": float(best_rnd),
            "incumbent_score": float(inc_score),
            "random_beats_incumbent": bool(best_rnd >= inc_score),
            "verdict": ("INSTRUMENT CANNOT PROMOTE -- uniform random at or above incumbent"
                        if best_rnd >= inc_score else "random below incumbent"),
        }
    return out


# --------------------------------------------------------------------------------------
# emission IO
# --------------------------------------------------------------------------------------

def emission_paths(dirpath: str = "submission") -> list[Path]:
    p = Path(dirpath)
    return sorted(p.glob("*.tif")) if p.is_dir() else []


def load_emission(path: str) -> dict:
    """Read one submission GeoTIFF and return its mask plus a budget count."""
    import rasterio
    with rasterio.open(path) as src:
        a = src.read(1)
    m = np.isfinite(a) & (a > 0)
    return {"path": str(path), "mask": m, "budget": int(m.sum()),
            "field": np.where(m, 1.0, 0.0), "shape": a.shape,
            "values": sorted(float(v) for v in np.unique(a)[:5])}
