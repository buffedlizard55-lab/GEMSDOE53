"""The two views, the conditional-independence test, and the disagreement strata (H53).

The brief mandates the Blum & Mitchell co-training setup: View A = potential-field / subsurface
(gravity, magnetics, strain, seismicity), View B = surface (DEM-derived curvature and slope, plus any
radiometric bands present in ``training_features.tif``).  This module supplies exactly that split,
over the bands actually present (verified inventory: ``evidence/band_inventory.json``, 19 float32
bands, band descriptions read from the file), plus the external layers restored under
``data/external`` that the competition did not ship: the 12-band 1 m-LiDAR scarp-feature raster, the
4-band radiometric raster and its 4 ratio bands.

What is different from this repo's earlier co-training round, and why
--------------------------------------------------------------------
``knowledge/03`` N-1 records that co-training **pseudo-labels used as a label source** were the worst
arm measured (0.0084 tip / 0.0078 hide against uniform-random 0.0253 / 0.0396), and that the
conditional-independence abandonment test could not even fire because block-level false-alarm
variance was degenerate.  That verdict is accepted here and not re-litigated.  Two changes follow:

* the **label** is no longer the pseudo-label.  It is the revealed-preference tier derived in
  :mod:`gems52.revealed` from the organiser's own published scores -- the double-corroborated atom
  ``A & C``, whose credit density is bounded below by 16.3 % against 2.8 % for uniform-random mass.
  Using prior submissions as a *label* is the "learning and education" use the brief permits; the
  artefact emitted is not those pixels.
* the disagreement strata are used to **stratify and to suppress**, which is the rule N-1 adopted,
  and the independence test is reported on labelled negatives at the pixel level as well as the block
  level, so that a degenerate block variance cannot hide the reading.

The independence test is the brief's own: correlate the two views' out-of-fold errors on labelled
negatives over spatial blocks, and abandon the arm if they are strongly correlated.  The threshold
pre-registered for this round is |r| > 0.60 (``registry/preregistration.json``).
"""

from __future__ import annotations

import numpy as np
import rasterio
from scipy import ndimage

# Band indices are 1-based positions in training_features.tif; descriptions below were read from the
# file itself (rasterio ``descriptions``), not transcribed from a sibling repository.
VIEW_A_BANDS = {          # potential field / subsurface / strain / seismicity
    1: "mag_anom", 2: "rtp", 3: "tmi_hg", 4: "geod_2ndinv", 5: "iso_grav_anom_slope",
    6: "tc", 7: "geod_shearrate", 8: "geod_dilaterate", 9: "tmi_vg", 10: "deq_n100a15",
    11: "iso_grav_anom_vg", 13: "iso_grav_anom", 14: "tmi", 15: "depth_to_base_surf",
    16: "ieq_n100a15", 17: "cond_surf", 18: "iso_grav_anom_hg",
}
VIEW_B_BANDS = {          # surface: DEM-derived curvature and slope, plus the radiometric bands
    12: "det_elev", 19: "det_elev_slope",
}
LIDAR_BANDS = {1: "ex_max", 2: "ex_mean", 3: "step_max", 4: "lapneg_max", 5: "lappos_max",
               6: "downface_max", 7: "upface_max", 8: "cross_max", 9: "relief", 10: "coh100",
               11: "strike", 12: "valid"}
RAD_BANDS = {1: "K", 2: "Th", 3: "U", 4: "TC"}
EXT_BANDS = {1: "ThK", 2: "UK", 3: "UTh", 4: "TMI_up150"}

SENTINEL = -1e30


class Stack:
    """Band-at-a-time reader.  A 19-band float32 stack at this grid is ~931 MB uncompressed and the
    box has 3 GB, so nothing here ever holds the whole stack; nodata is replaced by the footprint
    mean *before* any derivative, because a gradient through the -3.4e38 sentinel is pure artifact."""

    def __init__(self, data_dir, footprint: np.ndarray):
        self.data_dir = str(data_dir)
        self.foot = footprint
        self._cache: dict[tuple[str, int], np.ndarray] = {}
        self._mean: dict[tuple[str, int], float] = {}

    def band(self, rel: str, b: int) -> np.ndarray:
        key = (rel, b)
        if key not in self._cache:
            while len(self._cache) >= 6:
                self._cache.pop(next(iter(self._cache)))
            with rasterio.open(f"{self.data_dir}/{rel}") as src:
                a = src.read(b).astype(np.float32)
            a[~np.isfinite(a)] = np.nan
            a[a < SENTINEL] = np.nan
            inside = a[self.foot]
            m = float(np.nanmean(inside)) if np.isfinite(inside).any() else 0.0
            a[~np.isfinite(a)] = m
            self._cache[key] = a
            self._mean[key] = m
        return self._cache[key]

    def tf(self, b: int) -> np.ndarray:
        return self.band("training_features.tif", b)

    def lidar(self, b: int) -> np.ndarray:
        return self.band("external/lidar_scarp_features_u8.tif", b)

    def rad(self, b: int) -> np.ndarray:
        return self.band("external/geodawn_rad_u8.tif", b)

    def ext(self, b: int) -> np.ndarray:
        return self.band("external/geodawn_extensions_u8.tif", b)

    # ---- local operators -------------------------------------------------------------------
    @staticmethod
    def _grad(a):
        gy, gx = np.gradient(a)
        return gx, gy

    def grad_mag(self, a) -> np.ndarray:
        gx, gy = self._grad(a)
        return np.hypot(gx, gy).astype(np.float32)

    def lap(self, a) -> np.ndarray:
        return ndimage.laplace(a).astype(np.float32)

    def range5(self, a) -> np.ndarray:
        return (ndimage.maximum_filter(a, 5) - ndimage.minimum_filter(a, 5)).astype(np.float32)

    def coherence(self, a, sigma: float = 2.5):
        """Structure-tensor anisotropy and orientation of one band."""
        gx, gy = self._grad(a)
        J11 = ndimage.gaussian_filter(gx * gx, sigma)
        J22 = ndimage.gaussian_filter(gy * gy, sigma)
        J12 = ndimage.gaussian_filter(gx * gy, sigma)
        tr = J11 + J22
        dif = J11 - J22
        coh = np.sqrt(dif * dif + 4.0 * J12 * J12) / (tr + 1e-12)
        th = 0.5 * np.arctan2(2.0 * J12, dif)
        return coh.astype(np.float32), th.astype(np.float32)


def view_feature_iter(stack: Stack, view: str):
    """Yield ``(name, full-grid float32 array)`` one at a time.

    A generator, not a dict: View A alone is ~49 full-grid float32 arrays, i.e. ~2.4 GB on a grid of
    3730 x 3292, and this box has 3 GB.  Consuming the generator one feature at a time and indexing
    into it keeps the peak at a few arrays.
    """
    if view == "A":
        for b, nm in VIEW_A_BANDS.items():
            a = stack.tf(b)
            yield f"a_{nm}", a
            yield f"a_{nm}__hg", stack.grad_mag(a)
            if b in (13, 2, 14, 15, 4):
                yield f"a_{nm}__lap", stack.lap(a)
                yield f"a_{nm}__range5", stack.range5(a)
                c, _ = stack.coherence(a)
                yield f"a_{nm}__coh", c
    else:
        for b, nm in VIEW_B_BANDS.items():
            a = stack.tf(b)
            yield f"b_{nm}", a
            yield f"b_{nm}__hg", stack.grad_mag(a)
            yield f"b_{nm}__lap", stack.lap(a)
            yield f"b_{nm}__range5", stack.range5(a)
            c, _ = stack.coherence(a)
            yield f"b_{nm}__coh", c
        for b, nm in LIDAR_BANDS.items():
            yield f"b_lidar_{nm}", stack.lidar(b).astype(np.float32)
        for b, nm in RAD_BANDS.items():
            yield f"b_rad_{nm}", stack.rad(b).astype(np.float32)
        for b, nm in EXT_BANDS.items():
            yield f"b_rad_{nm}", stack.ext(b).astype(np.float32)
        # scarp up/down-face asymmetry (H54-5): a real fault scarp is systematically asymmetric,
        # a road cut or an erosion line is not.
        up = stack.lidar(7).astype(np.float32)
        dn = stack.lidar(6).astype(np.float32)
        yield "b_scarp_asym", ((up - dn) / (up + dn + 1e-6)).astype(np.float32)
        yield "b_scarp_asym_x_step", (((up - dn) / (up + dn + 1e-6))
                                     * stack.lidar(3).astype(np.float32)).astype(np.float32)


def view_feature_names(stack: Stack, view: str) -> list[str]:
    """The names ``view_feature_iter`` will yield, in order, without building the arrays."""
    if view == "A":
        out = []
        for b, nm in VIEW_A_BANDS.items():
            out += [f"a_{nm}", f"a_{nm}__hg"]
            if b in (13, 2, 14, 15, 4):
                out += [f"a_{nm}__lap", f"a_{nm}__range5", f"a_{nm}__coh"]
        return out
    out = []
    for b, nm in VIEW_B_BANDS.items():
        out += [f"b_{nm}", f"b_{nm}__hg", f"b_{nm}__lap", f"b_{nm}__range5", f"b_{nm}__coh"]
    out += [f"b_lidar_{nm}" for nm in LIDAR_BANDS.values()]
    out += [f"b_rad_{nm}" for nm in RAD_BANDS.values()]
    out += [f"b_rad_{nm}" for nm in EXT_BANDS.values()]
    out += ["b_scarp_asym", "b_scarp_asym_x_step"]
    return out


def build_matrices(stack: Stack, view: str, index_sets: dict[str, tuple[np.ndarray, np.ndarray]]
                   ) -> tuple[dict[str, np.ndarray], list[str]]:
    """One pass over the view's features, extracting every requested index set from each.

    ``index_sets`` maps a tag to ``(rows, cols)``.  Returns ``{tag: (n, p) float32}`` plus the
    ordered feature names.  Peak memory is one full-grid feature array plus the output matrices.
    """
    names = view_feature_names(stack, view)
    mats = {t: np.empty((len(r), len(names)), dtype=np.float32)
            for t, (r, _) in index_sets.items()}
    for j, (nm, arr) in enumerate(view_feature_iter(stack, view)):
        v = np.clip(np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0), -1e6, 1e6)
        for t, (r, c) in index_sets.items():
            mats[t][:, j] = v[r, c]
        del v, arr
    return mats, names


def block_ids(shape, valid: np.ndarray, n: int = 4) -> np.ndarray:
    """Contiguous n x n spatial blocks, -1 outside the footprint."""
    h, w = shape
    rs = np.linspace(0, h, n + 1).astype(int)
    cs = np.linspace(0, w, n + 1).astype(int)
    lab = np.full(shape, -1, np.int16)
    k = 0
    for i in range(n):
        for j in range(n):
            b = np.zeros(shape, bool)
            b[rs[i]:rs[i + 1], cs[j]:cs[j + 1]] = True
            lab[b & valid] = k
            k += 1
    return lab


def independence_test(err_a: np.ndarray, err_b: np.ndarray, neg: np.ndarray,
                      blocks: np.ndarray, threshold: float = 0.60) -> dict:
    """Correlate the two views' out-of-fold errors on labelled negatives, per spatial block.

    ``err_*`` are out-of-fold predicted scores on the negative class; the error used is the rank
    error against the negative class, i.e. a high score on a negative is a false alarm.  Both the
    pixel-level and the block-level readings are reported, because ``knowledge/03`` N-1 records that
    the block-level reading alone was degenerate and so the test could not fire.
    """
    from scipy import stats
    a = err_a[neg]
    b = err_b[neg]
    pr = stats.pearsonr(a, b)
    sr = stats.spearmanr(a, b)
    per = []
    for k in np.unique(blocks[neg]):
        if k < 0:
            continue
        m = neg & (blocks == k)
        if m.sum() < 500:
            continue
        r = stats.pearsonr(err_a[m], err_b[m])
        per.append(dict(block=int(k), n=int(m.sum()), pearson_r=round(float(r.statistic), 4),
                        p=round(float(r.pvalue), 6)))
    rs = [p["pearson_r"] for p in per]
    block_mean = float(np.mean(rs)) if rs else None
    block_var = float(np.var(rs)) if rs else None
    verdict = ("ABANDON: errors strongly correlated" if abs(pr.statistic) > threshold
               else "proceed: errors not strongly correlated")
    return dict(pixel_pearson_r=round(float(pr.statistic), 4),
                pixel_pearson_p=float(pr.pvalue),
                pixel_spearman_r=round(float(sr.statistic), 4),
                block_mean_r=round(block_mean, 4) if block_mean is not None else None,
                block_var_r=round(block_var, 6) if block_var is not None else None,
                n_blocks=len(per), per_block=per, threshold=threshold, verdict=verdict,
                degenerate_block_variance=bool(block_var is not None and block_var < 1e-6))


def strata(pa: np.ndarray, pb: np.ndarray, allowed: np.ndarray, q: float = 0.90) -> dict:
    """Disagreement strata over the permitted set.

    ``A_only``  View A confident, View B abstains -> a fault possibly buried beneath cover.  These
                are the candidates the brief requires a written geological reason for.
    ``B_only``  View B confident, View A abstains -> suspect surface artifact (road, canal levee,
                quarry face, erosion line).  Suppressed, with the reason recorded.
    ``concordant`` both confident -- where the two views agree, which is also where the mapped
                catalogue already agrees with itself.
    ``abstain``  neither confident.
    """
    ta = float(np.quantile(pa[allowed], q))
    tb = float(np.quantile(pb[allowed], q))
    hi_a = allowed & (pa >= ta)
    hi_b = allowed & (pb >= tb)
    return dict(tau_a=ta, tau_b=tb, quantile=q,
                A_only=hi_a & ~hi_b, B_only=hi_b & ~hi_a,
                concordant=hi_a & hi_b, abstain=allowed & ~hi_a & ~hi_b)
