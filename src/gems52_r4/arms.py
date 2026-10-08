"""Arms: the ways two views can be combined into one candidate field.

Eighteen arms are declared, from the two trivial single-view baselines through
consensus, gating and disagreement.  They are built **one at a time**: eighteen fields
at 3730x3292 float32 is 882 MB, and materialising all of them together is what killed
the previous run with exit 137.  ``build_arm(name, a, b)`` returns a single field and
the caller is expected to score and discard it.

The arms exist to be *eliminated*.  Consensus and intersection arms feel like the
obvious way to combine two views, and last round every one of them measured worse than
uniform random on its own assay (0.0224-0.0255 against random's 0.02875).  Keeping them
in the slate is what makes that a finding rather than an assumption.
"""

from __future__ import annotations

import numpy as np

from .cotraining import _rank_within, confident_and_abstaining


ARM_NAMES = [
    "A_only", "B_only",                                   # single-view baselines
    "mean", "max", "min", "geom_mean", "rank_sum",        # symmetric combinations
    "A_gated_by_B", "B_gated_by_A",                       # gating
    "intersect_top10", "union_top10", "consensus_top50",  # consensus / intersection
    "A_minus_B", "B_minus_A", "agreement",                # contrast
    "A_where_B_abstains", "B_where_A_abstains",           # co-training deferral
    "cotrain_disagreement",                               # disagreement-weighted
]

if len(ARM_NAMES) != len(set(ARM_NAMES)):
    raise ValueError("duplicate arm names")


def arm_names() -> list[str]:
    return list(ARM_NAMES)


def _sanity(a: np.ndarray, b: np.ndarray):
    if a.shape != b.shape:
        raise ValueError(f"view shape mismatch: {a.shape} vs {b.shape}")
    return np.isfinite(a) & np.isfinite(b)


def build_arm(name: str, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """One combined field for arm ``name``; NaN wherever either view is undefined."""
    both = _sanity(a, b)
    ra = _rank_within(a, both)
    rb = _rank_within(b, both)
    out = np.full(a.shape, np.nan, dtype=np.float32)

    if name == "A_only":
        out[both] = ra[both]
    elif name == "B_only":
        out[both] = rb[both]
    elif name == "mean":
        out[both] = 0.5 * (ra[both] + rb[both])
    elif name == "max":
        out[both] = np.maximum(ra[both], rb[both])
    elif name == "min":
        out[both] = np.minimum(ra[both], rb[both])
    elif name == "geom_mean":
        out[both] = np.sqrt(np.maximum(ra[both], 0.0) * np.maximum(rb[both], 0.0))
    elif name == "rank_sum":
        out[both] = ra[both] + rb[both]
    elif name == "A_gated_by_B":
        out[both] = gate_coarse_on_fine(ra, rb, q=0.90)[both]
    elif name == "B_gated_by_A":
        out[both] = gate_coarse_on_fine(rb, ra, q=0.90)[both]
    elif name == "intersect_top10":
        out[both] = np.minimum(ra[both], rb[both]) * ((ra[both] >= 0.90) & (rb[both] >= 0.90))
    elif name == "union_top10":
        m = (ra[both] >= 0.90) | (rb[both] >= 0.90)
        out[both] = np.where(m, np.maximum(ra[both], rb[both]),
                             0.5 * (ra[both] + rb[both]) * 1e-3)
    elif name == "consensus_top50":
        m = (ra[both] >= 0.50) & (rb[both] >= 0.50)
        out[both] = np.where(m, 0.5 * (ra[both] + rb[both]),
                             0.25 * (ra[both] + rb[both]))
    elif name == "A_minus_B":
        out[both] = ra[both] - rb[both]
    elif name == "B_minus_A":
        out[both] = rb[both] - ra[both]
    elif name == "agreement":
        out[both] = 1.0 - np.abs(ra[both] - rb[both])
    elif name == "A_where_B_abstains":
        out[both] = _deferral(ra, rb, both)[both]
    elif name == "B_where_A_abstains":
        out[both] = _deferral(rb, ra, both)[both]
    elif name == "cotrain_disagreement":
        out[both] = np.abs(ra[both] - rb[both]) * np.minimum(ra[both], rb[both])
    else:
        raise KeyError(f"undeclared arm {name!r}")
    out[~both] = np.nan
    return np.asarray(out, dtype=np.float32)


def _deferral(primary: np.ndarray, other: np.ndarray, both: np.ndarray,
              hi_q: float = 0.99, lo_q: float = 0.90) -> np.ndarray:
    """Primary view's confidence, but only credited where the other view abstains."""
    ca = confident_and_abstaining(primary, both, hi_q, lo_q)
    co = confident_and_abstaining(other, both, hi_q, lo_q)
    return np.where(co["abstaining"], ca["rank"], 0.0)


def gate_coarse_on_fine(coarse: np.ndarray, fine: np.ndarray, q: float = 0.90) -> np.ndarray:
    """Keep the coarse field only where the fine field is itself in its top ``q``.

    Gating rather than averaging: a smooth potential-field anomaly covers ground a fault
    need not occupy, and the surface view is the one that can say where the ground
    actually broke.  Below the gate the coarse field is scaled down, not zeroed, so
    ordering information survives for tie-breaking.
    """
    r = _rank_within(fine, np.isfinite(fine))
    m = np.isfinite(r) & (r >= q)
    out = np.where(m, coarse, 0.25 * coarse)
    return np.where(np.isfinite(coarse), out, np.nan).astype(np.float32)


def road_veto(field: np.ndarray, distance_field: np.ndarray | None,
              min_distance_m: float = 150.0) -> np.ndarray:
    """Suppress pixels closer than ``min_distance_m`` to a road.

    Road and claim-density layers measure *accessibility*, not geology: a fault under a
    road is over-represented in every catalogue because that is where a geologist could
    stop the truck.  Distance layers for roads scored 0.4763 and closed claims 0.4609
    against the catalogue last round -- useful as a predictor of where mapping happened,
    and therefore exactly what must be vetoed rather than rewarded.

    Returns the field unchanged when no distance layer is available, so an arm cannot
    silently change meaning depending on which externals happened to restore.
    """
    if distance_field is None:
        return field
    d = np.asarray(distance_field, dtype=np.float32)
    out = np.where(np.isfinite(d) & (d < min_distance_m), np.nan, field)
    return out.astype(np.float32)


def random_control(shape, valid: np.ndarray, budget: int, seed: int = 20261008) -> np.ndarray:
    """Uniform random field of exactly ``budget`` pixels -- the arms must beat it.

    This is the control that decides whether an arm is worth anything.  It is not a
    strawman: an arm that cannot beat uniform random on the same budget is fitted to
    accessibility and catalogue density, not to structure.
    """
    idx = np.flatnonzero(np.asarray(valid, dtype=bool).ravel())
    n = min(int(budget), idx.size)
    rng = np.random.default_rng(seed)
    pick = rng.choice(idx, size=n, replace=False)
    out = np.full(shape, np.nan, dtype=np.float32)
    out.ravel()[pick] = rng.random(n).astype(np.float32)
    return out


def not_merely_union(new_mask: np.ndarray, base_masks: list[np.ndarray],
                     max_jaccard: float = 0.90) -> dict:
    """Check a candidate is not just the union of things already shipped.

    A union of prior submissions is trivially "new" in bytes and worthless as science: it
    adds the false-positive mass of every parent.  The Jaccard against each base and
    against their union is reported so the claim "this is a genuinely different field" is
    a measurement.
    """
    new = np.asarray(new_mask, dtype=bool)
    out = {"n_new": int(new.sum()), "max_jaccard": None, "per_base": [], "is_merely_union": False}
    if not base_masks:
        return out
    best = 0.0
    for i, bm in enumerate(base_masks):
        b = np.asarray(bm, dtype=bool)
        inter = int((new & b).sum())
        uni = int((new | b).sum())
        j = inter / uni if uni else 0.0
        out["per_base"].append({"base": i, "jaccard": float(j), "inter": inter, "union": uni})
        best = max(best, j)
    anybase = np.zeros_like(new)
    for bm in base_masks:
        anybase |= np.asarray(bm, dtype=bool)
    inter = int((new & anybase).sum())
    uni = int((new | anybase).sum())
    j_union = inter / uni if uni else 0.0
    out["jaccard_vs_union"] = float(j_union)
    out["max_jaccard"] = float(max(best, j_union))
    out["is_merely_union"] = bool(out["max_jaccard"] > max_jaccard)
    return out
