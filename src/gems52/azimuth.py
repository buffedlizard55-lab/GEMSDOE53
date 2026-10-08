"""Circular statistics for *axial* orientation data (lineaments, strikes).

Why this module exists, and why it is not ``np.corrcoef``
---------------------------------------------------------
A lineament azimuth is an **axial** quantity: 5 degrees and 185 degrees are the same line.  Naive
arithmetic on degrees therefore (a) puts a discontinuity at 0/180 that a real line does not have and
(b) makes two perfectly parallel lines "180 apart".  Every directional statistic in this repository
goes through this module so that the doubled-angle trick is applied in one tested place instead of
being re-derived (and half-forgotten) at each call site.

The standard construction (Mardia & Jupp, *Directional Statistics*, 2nd ed., §2.2 for the circular
mean of angular data; the axial case is the same construction on the doubled angle):

    z = 2 * theta_rad                      # axial -> circular
    C = mean(cos z), S = mean(sin z)
    mean_axial = 0.5 * atan2(S, C)         # back to [0, pi)
    R          = hypot(C, S)               # resultant length, in [0, 1]
    spread     = sqrt(-2 ln R)             # circular standard deviation, radians

``R`` is the load-bearing number for a *single* field: it is 1 for perfectly aligned azimuths and 0 for
a uniformly random one, and it is *scale-free*, so it can be compared between two channels with
different noise levels.

**The coupling statistic is not that R.**  For two independent axial fields, the folded difference
``d = axial_difference(a, b)`` is uniform on ``[0, pi/2]`` (the doubled difference is uniform on the
circle), so ``E[exp(i*2*d)] = i*2/pi`` and the naive resultant ``|mean(exp(i*2*d))|`` tends to
**2/pi = 0.6366, not 0**.  A statistic with a null of 0.64 would call two unrelated datasets
"aligned", so :func:`axial_agreement` reports instead

    cos2_mean = mean( cos(2*d) )          null 0, +1 when every pixel agrees, -1 when perpendicular

whose null is exactly 0 because ``cos`` is odd about ``pi/4`` on the uniform folded difference.  The
2/pi value is pinned in ``tests/test_azimuth.py`` so the trap cannot be re-entered.

Reference for the axial construction: Mardia, K. V. & Jupp, P. E. (2000), *Directional Statistics*,
Wiley, ISBN 978-0-471-95333-3 (the circular-mean and resultant-length definitions used above are
§2.2.2, eqs. 2.2.7-2.2.9; the axial case is the ``2*theta`` reduction on p. 18).
"""

from __future__ import annotations

import numpy as np

TWO_PI = 2.0 * np.pi


def wrap_axial(theta_rad: np.ndarray) -> np.ndarray:
    """Fold an angle into [0, pi): the canonical representation of an undirected line."""
    t = np.mod(np.asarray(theta_rad, dtype=np.float64), np.pi)
    return np.where(t < 0.0, t + np.pi, t)


def axial_difference(a_rad, b_rad) -> np.ndarray:
    """Smallest angle between two *lines*, in [0, pi/2] radians.

    >>> round(float(np.degrees(axial_difference(0.0, np.deg2rad(5.0)))), 3)
    5.0
    >>> round(float(np.degrees(axial_difference(0.0, np.deg2rad(175.0)))), 3)
    5.0
    >>> round(float(np.degrees(axial_difference(0.0, np.deg2rad(90.0)))), 3)
    90.0
    """
    d = np.abs(wrap_axial(np.asarray(a_rad, np.float64) - np.asarray(b_rad, np.float64)))
    return np.minimum(d, np.pi - d)


def axial_resultant(a_rad, weights=None) -> tuple[float, float, float]:
    """(mean_axial_rad, R, n) of an axial sample; NaN-safe, weight-aware.

    ``R`` in [0, 1] is the resultant length: 1 = everyone agrees, ~0 = no preferred azimuth.
    """
    a = np.asarray(a_rad, dtype=np.float64).ravel()
    ok = np.isfinite(a)
    if weights is None:
        w = np.ones_like(a)
    else:
        w = np.asarray(weights, dtype=np.float64).ravel()
        ok &= np.isfinite(w) & (w > 0)
    if ok.sum() == 0:
        return float("nan"), 0.0, 0
    z = 2.0 * wrap_axial(a[ok])
    w = w[ok]
    w = w / w.sum()
    c = float(np.sum(w * np.cos(z)))
    s = float(np.sum(w * np.sin(z)))
    r = float(np.hypot(c, s))
    return float(0.5 * np.arctan2(s, c)) % np.pi, r, int(ok.sum())


def axial_agreement(a_rad: np.ndarray, b_rad: np.ndarray,
                    w_a=None, w_b=None, mask: np.ndarray | None = None) -> dict:
    """How strongly two axial *fields* are aligned, with the sample size that produced it.

    Primary output ``cos2_mean`` = ``mean(cos(2*delta))``: null 0 for independent fields (the folded
    difference is uniform on [0, pi/2], and cos is odd about pi/4 there), +1 when every pixel agrees,
    -1 when the two fields are perpendicular.  ``R`` is returned alongside as the *concentration* of
    the doubled difference -- informative, but with a null of 2/pi, never a test statistic on its own.
    """
    a = np.asarray(a_rad, dtype=np.float64)
    b = np.asarray(b_rad, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch {a.shape} vs {b.shape}")
    ok = np.isfinite(a) & np.isfinite(b)
    if mask is not None:
        ok &= np.asarray(mask, dtype=bool)
    if w_a is not None:
        ok &= np.isfinite(w_a) & (w_a > 0)
    if w_b is not None:
        ok &= np.isfinite(w_b) & (w_b > 0)
    n = int(ok.sum())
    if n == 0:
        return {"mean_diff_deg": float("nan"), "R": 0.0, "n": 0, "cos2_mean": float("nan")}
    d = axial_difference(a[ok], b[ok])
    w = np.ones(n)
    if w_a is not None:
        w = w * np.asarray(w_a, dtype=np.float64)[ok]
    if w_b is not None:
        w = w * np.asarray(w_b, dtype=np.float64)[ok]
    if not np.all(w > 0):
        return {"mean_diff_deg": float("nan"), "R": 0.0, "n": n, "cos2_mean": float("nan")}
    w = w / w.sum()
    c = float(np.sum(w * np.cos(2.0 * d)))
    s = float(np.sum(w * np.sin(2.0 * d)))
    r = float(np.hypot(c, s))
    return {
        "mean_diff_deg": float(np.degrees(np.sum(w * d))),
        "R": r,
        "R_null_independent": 2.0 / np.pi,
        "n": n,
        "cos2_mean": c,
    }


def null_R_threshold(n: int, alpha: float = 0.05) -> float:
    """Resultant length above which an axial sample of size ``n`` is significant at ``alpha``.

    The Rayleigh test for uniformity on the circle of doubled angles: ``2*n*R^2`` is asymptotically
    chi-square with 2 degrees of freedom, so the critical ``R`` is ``sqrt(-ln(alpha) / n)``
    (Mardia & Jupp 2000, §6.2.2, Rayleigh test).  For n = 100 at alpha = 0.05 that is 0.173: a
    *statistical* threshold, not a tuned one.
    """
    if n <= 0:
        return float("inf")
    return float(np.sqrt(-np.log(alpha) / float(n)))


def mean_axial_deg(a_rad, weights=None) -> float:
    m, _, _ = axial_resultant(a_rad, weights)
    return float(np.degrees(m)) if np.isfinite(m) else float("nan")
