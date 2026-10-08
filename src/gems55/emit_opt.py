"""Coverage-optimal emission: the budget is an *output* of the metric, not an input.

The object being maximised is the competition's own score, written in expectation over a belief
field ``rho`` (expected truth mass per pixel, ``sum(rho) ~ |G|``)::

    DTI(E) = T / (0.2*T + 0.2*|E| - 0.2*M + 0.8*|G|)
    T(E)   = sum_x rho(x) * max_{y in E} k(d(x,y))        (submodular, monotone)
    M(E)   = sum_{y in E} sum_x rho(x) k(d(x,y)) = sum_{y in E} C(y),   C = rho * k

Adding one pixel ``y`` changes the numerator by ``dT`` and the denominator by
``0.2*(dT + 1 - C(y))``, so the exact marginal rule is

    accept y   <=>   dT(y) > bar * (1 - C(y)),     bar = 0.2*DTI / (1 - 0.2*DTI)

which is ``src/gems52/emit.py``'s rule with the *actual* best-cover weight replaced by its
expectation ``C(y)`` (valid because ``C(y) <= 9.38 * |G| / |footprint| ~ 0.015 << 1``, i.e. the
"at most one truth pixel in range" regime the whole calibration lives in).

Three things this buys over the family's historical practice, all measured in
``evidence/h55_spacing_curve.json`` and ``evidence/h55_emission_strategy.json``:

* **No fixed budget.** The loop stops when no candidate clears the bar, so ``|E|`` is whatever the
  field and the calibrated ``|G|`` justify. Every prior submission in this family fixed
  ``K = 37654`` because that is what an earlier submission happened to contain.
* **Coverage-optimal spacing.** A straight trace sampled every ``s`` pixels credits
  ``T/S = 1.00, 1.64, 2.32, 2.56, 2.89, 2.90, 2.78`` at ``s = 1..7`` -- the optimum is 500-600 m,
  not the ~430 m the 0.2778 file used and not the 200-300 m its "dotted" ancestors used. The greedy
  finds that spacing on its own, because a pixel inside an already-covered disc has ``dT ~ 0``.
* **``A/S`` at the ceiling.** Kernel-weighted coverage per emitted pixel is bounded by the disc
  weight sum ``9.3803``; the family's best shipped file reaches ``8.04`` (86 %), a contiguous file
  reaches ``3.81`` (41 %). At equal geology, DTI is linear in ``A/S``.
"""

from __future__ import annotations

import numpy as np

R_PX = 3.0
OFFSETS: list[tuple[int, int, float]] = [
    (dy, dx, 1.0 - float(np.hypot(dy, dx)) / R_PX)
    for dy in range(-3, 4) for dx in range(-3, 4)
    if float(np.hypot(dy, dx)) <= R_PX + 1e-12
]
DISC_SUM = float(sum(k for _, _, k in OFFSETS))


def accept_bar(dti: float, alpha: float = 0.2) -> float:
    d = 1.0 - alpha * dti
    return float(alpha * dti / d) if d > 0 else float("inf")


def kernel_convolve(density: np.ndarray) -> np.ndarray:
    """``C(y) = sum_x rho(x) k(d(x,y))`` -- exact lattice, zero-padded (never np.roll)."""
    h, w = density.shape
    d = np.nan_to_num(density, nan=0.0).astype(np.float32)
    wp = np.pad(d, 3, mode="constant", constant_values=0.0)
    out = np.zeros((h, w), dtype=np.float64)
    for dy, dx, k in OFFSETS:
        if k <= 0.0:
            continue
        out += wp[3 - dy:3 - dy + h, 3 - dx:3 - dx + w] * k
    return out.astype(np.float32)


def kernel_dilate(emitted: np.ndarray) -> np.ndarray:
    """``K_E(x) = max_{y in E} k(d(x,y))``."""
    h, w = emitted.shape
    wp = np.pad(emitted.astype(np.float32), 3, mode="constant", constant_values=0.0)
    out = np.zeros((h, w), dtype=np.float32)
    for dy, dx, k in OFFSETS:
        if k <= 0.0:
            continue
        sh = wp[3 - dy:3 - dy + h, 3 - dx:3 - dx + w] * np.float32(k)
        np.maximum(out, sh, out=out)
    return out


def _neighbour_index(cands: np.ndarray, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """(flat neighbour indices y+dy, kernel weights) per candidate; -1 where off-grid."""
    h, w = shape
    r = cands // w
    cc = cands % w
    nb = np.full((cands.size, len(OFFSETS)), -1, dtype=np.int64)
    kk = np.zeros((cands.size, len(OFFSETS)), dtype=np.float32)
    for j, (dy, dx, k) in enumerate(OFFSETS):
        yy, xx = r + dy, cc + dx
        ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
        nb[ok, j] = (yy[ok] * w + xx[ok]).astype(np.int64)
        kk[ok, j] = np.float32(k)
    return nb, kk


def gain_field(dens_pad: np.ndarray, cur_pad: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Exact marginal credit of every pixel: ``g(y) = sum_j rho(y+o_j) * max(0, k_j - K_E(y+o_j))``.

    Fully vectorised (25 padded shifts, no Python loop over pixels), which is what makes a
    coverage-greedy over a 12.28 M-pixel grid affordable on a 2-core box.
    """
    h, w = shape
    g = np.zeros((h, w), dtype=np.float64)
    for dy, dx, k in OFFSETS:
        if k <= 0.0:
            continue
        sl = (slice(3 + dy, 3 + dy + h), slice(3 + dx, 3 + dx + w))
        np.add(g, dens_pad[sl] * np.maximum(0.0, k - cur_pad[sl]), out=g)
    return g


def _pad(a: np.ndarray) -> np.ndarray:
    return np.pad(a, 3, mode="constant", constant_values=0.0)


def _unpad(p: np.ndarray) -> np.ndarray:
    return p[3:-3, 3:-3]


def coverage_greedy(density: np.ndarray, allowed: np.ndarray, dti_projected: float = 0.0,
                    n_g: float | None = None, max_emit: int = 400_000, batch: int = 20_000,
                    hard_core_px: float = 6.0, log=lambda *a: None) -> tuple[np.ndarray, dict]:
    """Batched lazy-greedy on ``T(E)`` under the metric's exact marginal rule.

    ``density`` must be calibrated so its sum is the expected truth mass ``|G|`` (see
    :func:`calibrate`), otherwise ``dT`` and ``bar`` are in different units and the stop is
    meaningless.  With ``dti_projected = 0`` the bar is 0 and the loop is pure maximum-coverage at
    the budget ``max_emit`` -- the right mode for comparing emitters at *matched* budget on a fold.
    With a real ``dti_projected`` the budget is endogenous: the loop stops when no candidate clears
    the bar, and ``|E|`` is an output.

    Within a round, candidates are accepted in gain order under a hard-core exclusion of
    ``hard_core_px`` (default 6 px = 600 m).  Two pixels further apart than the kernel diameter
    cannot interact, so accepting a mutually-separated batch in one pass is exact greedy on that
    batch, not an approximation of it.
    """
    h, w = allowed.shape
    dens = np.nan_to_num(np.asarray(density, dtype=np.float32), nan=0.0)
    dens = np.where(allowed, np.maximum(dens, 0.0), 0.0).astype(np.float32)
    total = float(dens.sum())
    if total <= 0:
        return np.zeros((h, w), bool), dict(emitted=0, reason="empty density")
    dens_pad = _pad(dens.astype(np.float64))
    C = gain_field(dens_pad, _pad(np.zeros((h, w), np.float32)), (h, w)).astype(np.float32)
    bar = accept_bar(dti_projected)
    cur = np.zeros((h, w), dtype=np.float32)
    E = np.zeros((h, w), dtype=bool)
    chosen: list[int] = []
    dT_hist: list[float] = []
    r = int(np.ceil(hard_core_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = (yy * yy + xx * xx) <= hard_core_px * hard_core_px + 1e-9
    rounds = 0
    while len(chosen) < max_emit:
        rounds += 1
        g = gain_field(dens_pad, _pad(cur), (h, w))
        g = np.where(allowed & ~E, g, -np.inf)
        finite = np.flatnonzero(np.isfinite(g).ravel())
        if finite.size == 0:
            break
        gt = g.ravel()[finite]
        pos = np.flatnonzero(gt > 0.0)
        if pos.size == 0:
            break
        finite = finite[pos]
        n_take = int(min(batch, finite.size))
        top = finite[np.argpartition(-g.ravel()[finite], n_take - 1)[:n_take]]
        top = top[np.argsort(-g.ravel()[top])]
        blocked = np.zeros((h, w), dtype=bool)
        acc: list[int] = []
        stall = 0
        MAX_STALL = 4000
        for idx in top:
            if len(chosen) + len(acc) >= max_emit:
                break
            iy = int(idx) // w
            ix = int(idx) % w
            if blocked[iy, ix]:
                continue
            gi = float(g[iy, ix])
            if gi <= bar * (1.0 - float(C[iy, ix])):
                # The batch is sorted by *stale* gain, so on a strictly ranked field nothing below
                # this point clears the bar and we could stop.  On tied gains (a flat belief) the
                # order is arbitrary and stopping would abort the round, so stall-limit instead.
                stall += 1
                if stall > MAX_STALL:
                    break
                continue
            stall = 0
            acc.append(int(idx))
            y0, y1 = max(0, iy - r), min(h, iy + r + 1)
            x0, x1 = max(0, ix - r), min(w, ix + r + 1)
            sub = blocked[y0:y1, x0:x1]
            d = disc[(y0 - (iy - r)):(y0 - (iy - r)) + sub.shape[0],
                     (x0 - (ix - r)):(x0 - (ix - r)) + sub.shape[1]]
            blocked[y0:y1, x0:x1] = sub | d
        if not acc:
            break
        ai = np.array(acc, dtype=np.int64)
        E.ravel()[ai] = True
        chosen.extend(acc)
        # exact per-accepted marginal credit, in acceptance order
        nb, kk = _neighbour_index(ai, (h, w))
        cf = cur.ravel(); df = dens.ravel()
        for i in range(ai.size):
            ok = nb[i] >= 0
            nbi = nb[i][ok]
            dT = float(np.sum(df[nbi] * np.maximum(0.0, kk[i][ok] - cf[nbi])))
            dT_hist.append(dT)
            # NOT np.maximum(..., out=cf[nbi]): fancy indexing copies, so `out=` there writes into a
            # throwaway and the running cover is never raised.  That single line made every later
            # pixel look uncovered, which is why an earlier version of this greedy reported A/S of
            # 1.8-2.1 -- worse than plain top-K -- and is the bug tests/test_h55_emit.py catches.
            cf[nbi] = np.maximum(cf[nbi], kk[i][ok])
        if rounds % 2 == 0 or len(chosen) >= max_emit:
            log(f"    round {rounds}: emitted {len(chosen)}  dT_last={dT_hist[-1]:.5f} "
                f"bar={bar:.5f}")
    stats = dict(emitted=int(E.sum()), rounds=rounds, bar=bar, dti_projected=dti_projected,
                 n_g=n_g, density_sum=total, hard_core_px=hard_core_px, batch=batch,
                 dT_first=float(dT_hist[0]) if dT_hist else None,
                 dT_last=float(dT_hist[-1]) if dT_hist else None,
                 T_expected=float(sum(dT_hist)),
                 A_per_S=float(kernel_dilate(E)[allowed].sum() / max(int(E.sum()), 1)),
                 disc_ceiling=DISC_SUM,
                 spacing_efficiency=float(kernel_dilate(E)[allowed].sum()
                                          / max(int(E.sum()), 1) / DISC_SUM))
    return E, stats


def calibrate(field: np.ndarray, allowed: np.ndarray, n_g: float) -> np.ndarray:
    """Scale a non-negative ranking field so its total mass equals the calibrated ``|G|``."""
    f = np.where(allowed, np.maximum(np.nan_to_num(field, nan=0.0), 0.0), 0.0).astype(np.float32)
    tot = float(f.sum())
    return f * (float(n_g) / tot) if tot > 0 else f


def topk(field: np.ndarray, allowed: np.ndarray, k: int) -> np.ndarray:
    """The k highest-valued allowed pixels.  Non-finite values are *disqualified*, not sorted to
    the top: a +inf in a derived layer is a bug upstream, and emitting it would be a silent
    own-goal (the historical NaN/inf failures in this family all started that way)."""
    f = np.asarray(field, dtype=np.float64).ravel()
    f = np.where(allowed.ravel() & np.isfinite(f), f, -np.inf)
    k = int(min(max(k, 0), np.isfinite(f).sum()))
    out = np.zeros(f.size, dtype=bool)
    if k:
        cand = np.argpartition(-f, k - 1)[:k]
        out[cand[np.isfinite(f[cand])]] = True
    return out.reshape(allowed.shape)


def hardcore_thin(field: np.ndarray, allowed: np.ndarray, k: int, radius_px: float,
                  oversample: int = 40) -> np.ndarray:
    """Value-ordered hard-core point set: the family's historical 'dotted' emitter, parameterised.

    Takes candidates in descending field value and keeps one only if nothing already kept lies
    within ``radius_px``.  This is what "d1-5"/"d2-8"/"poisson300m" were; it is coverage-blind, so
    it discards mass that was the unique cover of a truth pixel.
    """
    f = np.asarray(field, dtype=np.float64).ravel()
    f = np.where(allowed.ravel() & np.isfinite(f), f, -np.inf)
    finite = np.flatnonzero(np.isfinite(f))
    n_take = int(min(finite.size, max(k * oversample, k)))
    pre = finite[np.argpartition(-f[finite], n_take - 1)[:n_take]]
    order = pre[np.argsort(-f[pre], kind="stable")]
    keep = np.zeros(f.size, dtype=bool)
    H, W = allowed.shape
    blocked = np.zeros((H, W), dtype=bool)
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disc = (yy * yy + xx * xx) <= radius_px * radius_px + 1e-9
    n = 0
    for idx in order:
        if n >= k:
            break
        if not np.isfinite(f[idx]):
            break
        y, x = divmod(int(idx), W)
        if blocked[y, x]:
            continue
        keep[idx] = True
        y0, y1 = max(0, y - r), min(H, y + r + 1)
        x0, x1 = max(0, x - r), min(W, x + r + 1)
        sub = blocked[y0:y1, x0:x1]
        d = disc[(y0 - (y - r)):(y0 - (y - r)) + sub.shape[0],
                 (x0 - (x - r)):(x0 - (x - r)) + sub.shape[1]]
        blocked[y0:y1, x0:x1] = sub | d
        n += 1
    return keep.reshape(allowed.shape)
