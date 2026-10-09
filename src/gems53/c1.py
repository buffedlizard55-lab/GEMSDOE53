"""C1 (session 2, 2026-10-09): conductivity-magnetic cross-scale edge coherence.

Lane method (pre-registered in docs/research/preregistration-2026-10-09-session2.md, section 3):
a buried/covered fault that juxtaposes magnetic units and hosts a conductive damage zone should
express itself as a LINEAR edge in reduced-to-pole magnetics (stack band 2) AND a co-located,
co-oriented linear edge in the conductivity surface (stack band 17). The features are computed
entirely from label-free bands; no catalogue information enters anywhere in this module.

Structure-tensor convention (per scale sigma, Gaussian smoothing of the quadratic terms):
    Jxx = G_s * Ix^2,  Jxy = G_s * Ix Iy,  Jyy = G_s * Iy^2
    lambda1 >= lambda2 are the eigenvalues of [[Jxx, Jxy], [Jxy, Jyy]]
    line energy      E = sqrt(lambda1)
    orientation coh. c = (lambda1 - lambda2) / (lambda1 + lambda2)   in [0, 1]
    orientation      theta = 0.5 * atan2(2 Jxy, Jxx - Jyy)           (mod pi)

Orientation agreement between two fields at the same scale (DEV-C1-1, energy-gated):
    u_x = E_x / (E_x + median_fp(E_x))                                in [0, 1)
    A = cos(2 (theta_a - theta_b)) * min(c_a*u_a, c_b*u_b)            in [-1, 1]
cos(2.) makes the score pi-periodic (a fault strike is an undirected axis); the min() weight
means agreement is only credited where BOTH fields are locally line-like. The u gates (added by
DEV-C1-1 after the synthetic test showed rank-1 coherence in energy-free noise regions) suppress
orientations where gradient energy is negligible, so noise cannot score as "agreement".
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

SIGMAS = (1.0, 2.0, 4.0)
COND_BAND_INDEX = 16   # band 17 (0-based 16) = "Conductivity surface"
RTP_BAND_INDEX = 1     # band 2  (0-based 1)  = "Reduced to pole magnetic data"


def robust_zscore(x: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Median/IQR z-score on mask pixels; returns (z, median, iqr). IQR<=0 falls back to MAD*1.4826."""
    v = x[mask]
    med = float(np.median(v))
    q75, q25 = np.percentile(v, [75, 25])
    iqr = float(q75 - q25)
    if not np.isfinite(iqr) or iqr <= 0:
        iqr = float(np.median(np.abs(v - med))) * 1.4826 or 1.0
    z = (x - med) / iqr
    return np.clip(z, -5.0, 5.0), med, iqr


def impute_median(band: np.ndarray, footprint: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sentinel/NaN -> footprint median; returns (imputed, finite_mask). Outside footprint -> 0."""
    finite = np.isfinite(band) & footprint
    med = float(np.median(band[finite])) if finite.any() else 0.0
    out = np.where(finite, band, 0.0).astype(np.float32)
    out[~finite & footprint] = med
    return out, finite


def structure_tensor(z: np.ndarray, sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Returns (E, c, theta, lam1) for a 2-D z-scored image, at Gaussian scale sigma (pixels)."""
    iy, ix = np.gradient(z.astype(np.float64))  # central differences, unit pixel spacing
    jxx = ndimage.gaussian_filter(ix * ix, sigma)
    jxy = ndimage.gaussian_filter(ix * iy, sigma)
    jyy = ndimage.gaussian_filter(iy * iy, sigma)
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    lam1 = tr / 2.0 + disc
    lam2 = np.maximum(tr / 2.0 - disc, 0.0)
    energy = np.sqrt(np.maximum(lam1, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        coh = np.where(tr > 0, (lam1 - lam2) / np.maximum(tr, 1e-30), 0.0)
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    return energy.astype(np.float32), coh.astype(np.float32), theta.astype(np.float32), lam1.astype(np.float32)


def energy_gate(energy: np.ndarray, fp: np.ndarray) -> np.ndarray:
    """u = E / (E + median_fp(E)), in [0, 1). Returns 0 where the footprint is False."""
    med = float(np.median(energy[fp])) if fp.any() else 0.0
    u = energy.astype(np.float64) / (energy.astype(np.float64) + max(med, 1e-30))
    u[~fp] = 0.0
    return u


def orientation_agreement(theta_a, coh_a, energy_a, theta_b, coh_b, energy_b, fp) -> np.ndarray:
    """Energy-gated orientation agreement (DEV-C1-1): A = cos(2 dtheta) * min(c_a u_a, c_b u_b)."""
    ua = energy_gate(energy_a, fp)
    ub = energy_gate(energy_b, fp)
    a = np.cos(2.0 * (theta_a.astype(np.float64) - theta_b.astype(np.float64)))
    w = np.minimum(coh_a.astype(np.float64) * ua, coh_b.astype(np.float64) * ub)
    return (a * w).astype(np.float32)


def build_c1_features(feats: np.ndarray, fp: np.ndarray, fp_idx: np.ndarray,
                      sigmas=SIGMAS) -> tuple[np.ndarray, list]:
    """Build the 14 C1 feature columns for footprint pixels.

    feats: (N_fp, F) float32 footprint-pixel feature matrix (NaN where sentinel).
    fp:    (H, W) bool footprint. fp_idx: (H, W) int32 index into feats or -1.
    Returns (X_c1 (N_fp, 14) float32, names). Per scale sigma in {1,2,4} the four columns
    condE, rtpE, agree, joint (12 columns) plus fin17 and fin2 = 14.
    """
    H, W = fp.shape
    n_fp = int(fp.sum())
    # Reconstruct full grids for the two bands.
    grid17 = np.zeros((H, W), dtype=np.float32)
    grid2 = np.zeros((H, W), dtype=np.float32)
    grid17[fp] = feats[:, COND_BAND_INDEX]
    grid2[fp] = feats[:, RTP_BAND_INDEX]
    imp17, fin17 = impute_median(grid17, fp)
    imp2, fin2 = impute_median(grid2, fp)
    z17, med17, iqr17 = robust_zscore(imp17, fp)
    z2, med2, iqr2 = robust_zscore(imp2, fp)
    def _z(e: np.ndarray) -> np.ndarray:
        med = float(np.median(e[fp]))
        iqr = float(np.percentile(e[fp], 75) - np.percentile(e[fp], 25))
        return np.clip((e - med) / max(iqr, 1e-12), -5.0, 5.0).astype(np.float32)

    cols, names = [], []
    for sigma in sigmas:
        e17, c17, t17, _ = structure_tensor(z17, sigma)
        e2, c2, t2, _ = structure_tensor(z2, sigma)
        agree = orientation_agreement(t17, c17, e17, t2, c2, e2, fp)
        joint = np.clip(_z(e17) * _z(e2), -5.0, 5.0).astype(np.float32)
        sfx = f"s{int(sigma)}"
        cols += [e17, e2, agree, joint]
        names += [f"c1_condE_{sfx}", f"c1_rtpE_{sfx}", f"c1_agree_{sfx}", f"c1_joint_{sfx}"]
    # finiteness indicators
    cols += [fin17.astype(np.float32), fin2.astype(np.float32)]
    names += ["c1_fin17", "c1_fin2"]
    X = np.zeros((n_fp, len(cols)), dtype=np.float32)
    for j, g in enumerate(cols):
        X[:, j] = g[fp]
    X[~np.isfinite(X)] = np.nan  # HGB handles NaN natively; no silent imputation
    assert len(names) == 14, names
    return X, names


def c1_surface_grid(feats: np.ndarray, fp: np.ndarray, fp_idx: np.ndarray, sigmas=SIGMAS) -> dict:
    """Full-grid C1 diagnostic surfaces (for the pre-placement uniqueness check and figures)."""
    H, W = fp.shape
    grid17 = np.zeros((H, W), dtype=np.float32)
    grid2 = np.zeros((H, W), dtype=np.float32)
    grid17[fp] = feats[:, COND_BAND_INDEX]
    grid2[fp] = feats[:, RTP_BAND_INDEX]
    imp17, _ = impute_median(grid17, fp)
    imp2, _ = impute_median(grid2, fp)
    z17, _, _ = robust_zscore(imp17, fp)
    z2, _, _ = robust_zscore(imp2, fp)
    out = {}
    for sigma in sigmas:
        e17, c17, t17, _ = structure_tensor(z17, sigma)
        e2, c2, t2, _ = structure_tensor(z2, sigma)
        out[f"agree_s{int(sigma)}"] = orientation_agreement(t17, c17, e17, t2, c2, e2, fp)
        out[f"condE_s{int(sigma)}"] = e17
        out[f"rtpE_s{int(sigma)}"] = e2
    return out
