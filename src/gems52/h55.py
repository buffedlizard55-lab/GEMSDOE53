"""H55-1 scale-normalized LoG sign-change features, frozen in its preregistration.

These are label-free edge candidates from potential-field bands, not fault
labels or confirmation. A local LoG sign change is a classical edge cue; it
also responds to lithologic contacts, processing seams and model artifacts.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def _normalized_smooth(a: np.ndarray, valid: np.ndarray, sigma: float) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    if a.shape != valid.shape or a.ndim != 2:
        raise ValueError("field and valid mask must be same-shape 2D arrays")
    good = valid & np.isfinite(a) & (a > -1e38)
    num = ndi.gaussian_filter(np.where(good, a, 0.0), sigma, mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float32), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num, dtype=np.float32), where=den > 1e-8)


def signed_log_edge(a: np.ndarray, valid: np.ndarray, sigma: float,
                    pixel_size_m: float = 100.0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return `(signed_LoG, edge_response, nx, ny, zero_crossing)`.

    LoG is `-sigma**2 * gaussian_laplace(normalized_gaussian(a))`, with sigma
    measured in pixels. The crossing is true where the 3x3 neighbourhood has
    both negative and positive LoG values. Edge response is gradient magnitude
    per metre, retained only at that crossing. Flat gradients have zero normals.
    All returned channels are finite float32 except the boolean crossing mask.
    """
    if not np.isfinite(sigma) or sigma <= 0 or not np.isfinite(pixel_size_m) or pixel_size_m <= 0:
        raise ValueError("sigma and pixel_size_m must be finite and positive")
    good = np.asarray(valid, dtype=bool) & np.isfinite(a) & (np.asarray(a) > -1e38)
    smooth = _normalized_smooth(a, good, sigma)
    lap = (-float(sigma) ** 2 * ndi.gaussian_laplace(
        smooth, sigma=sigma, mode="reflect", truncate=4.0
    )).astype(np.float32, copy=False)
    lap[~good] = 0.0

    low = ndi.minimum_filter(lap, size=3, mode="reflect")
    high = ndi.maximum_filter(lap, size=3, mode="reflect")
    crossing = (low < 0.0) & (high > 0.0) & good

    gy, gx = np.gradient(smooth, pixel_size_m, pixel_size_m)
    gx = np.asarray(gx, dtype=np.float32)
    gy = np.asarray(gy, dtype=np.float32)
    magnitude = np.hypot(gx, gy).astype(np.float32, copy=False)
    response = np.where(crossing, magnitude, 0.0).astype(np.float32)
    nx = np.divide(gx, magnitude, out=np.zeros_like(gx), where=magnitude > 1e-12)
    ny = np.divide(gy, magnitude, out=np.zeros_like(gy), where=magnitude > 1e-12)

    for channel in (lap, response, nx, ny):
        channel[~good] = 0.0
    return lap, response, nx, ny, crossing


def compute_h55_features(gravity: np.ndarray, rtp: np.ndarray,
                          cover: np.ndarray, slope: np.ndarray,
                          valid: np.ndarray, sigmas=(1, 3),
                          pixel_size_m: float = 100.0) -> dict[str, np.ndarray]:
    """Build the preregistered H55-1 maps from bands 13, 2, 15 and 19.

    The cross-field normal agreement is axial (`abs(dot)`) because a gradient
    normal and its sign-reversed representation describe the same edge axis.
    The edge-pair response is nonzero only where both fields have a local LoG
    sign change. The final interaction conditions that pair on deeper modelled
    cover and lower slope; neither condition by itself confirms a fault.
    """
    arrays = [np.asarray(x, dtype=np.float32) for x in (gravity, rtp, cover, slope)]
    valid = np.asarray(valid, dtype=bool)
    if valid.ndim != 2 or any(x.shape != valid.shape for x in arrays):
        raise ValueError("all fields and valid must have the same 2D shape")
    if tuple(sigmas) != (1, 3):
        raise ValueError("H55-1 scales are frozen at sigma=(1, 3) pixels")

    grav, mag, depth, dem_slope = arrays
    maps: dict[str, np.ndarray] = {}
    edge_cache = {}
    for label, field in (("grav", grav), ("rtp", mag)):
        for sigma in sigmas:
            lap, edge, nx, ny, cross = signed_log_edge(field, valid, sigma, pixel_size_m)
            scale = f"s{sigma}"
            maps[f"h55_{label}_signed_log_{scale}"] = lap
            maps[f"h55_{label}_zc_edge_{scale}"] = edge
            if sigma == 3:
                edge_cache[label] = (edge, nx, ny, cross)

    g_edge, gx, gy, g_cross = edge_cache["grav"]
    m_edge, mx, my, m_cross = edge_cache["rtp"]
    normal_alignment = np.clip(np.abs(gx * mx + gy * my), 0.0, 1.0)
    paired = np.sqrt(np.maximum(g_edge, 0.0) * np.maximum(m_edge, 0.0)) * normal_alignment
    paired[~(g_cross & m_cross)] = 0.0
    maps["h55_grav_rtp_normal_agreement_s3"] = np.where(
        g_cross & m_cross, normal_alignment, 0.0
    ).astype(np.float32)
    maps["h55_grav_rtp_edge_pair_s3"] = paired.astype(np.float32)

    safe_depth = np.nan_to_num(depth, nan=0.0, posinf=0.0, neginf=0.0)
    safe_slope = np.nan_to_num(dem_slope, nan=0.0, posinf=0.0, neginf=0.0)
    cover_quiet = np.log1p(np.maximum(safe_depth, 0.0)) / (1.0 + np.maximum(safe_slope, 0.0) / 10.0)
    maps["h55_grav_rtp_edge_pair_cover_quiet_s3"] = (paired * cover_quiet).astype(np.float32)

    for name, values in maps.items():
        values = np.asarray(values, dtype=np.float32)
        if values.shape != valid.shape or not np.isfinite(values).all():
            raise ValueError(f"H55 feature {name} is nonfinite or has the wrong shape")
        values[~valid] = 0.0
        maps[name] = values
    return maps
