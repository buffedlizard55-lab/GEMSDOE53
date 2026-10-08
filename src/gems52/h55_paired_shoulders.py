"""Finite-distance paired-shoulder feature prototype for preregistered H55-1.

This transform does not train a model, inspect labels, or claim geological truth.
It uses only the detrended DEM and a validity mask. The model arm is separately
integrated into structural.build(include_h55=True) and evaluated by the frozen
spatial runner; support/buffer rules still apply.
"""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from scipy import ndimage as ndi

from .structural import smooth


def paired_shoulder_features(
    elevation: np.ndarray,
    valid: np.ndarray,
    offsets_px: Iterable[int] = (2, 4, 6),
    sigma_px: float = 1.0,
    pixel_size_m: float = 100.0,
    flat_gradient_epsilon: float = 1e-12,
) -> dict[str, np.ndarray]:
    """Build signed bilateral DEM features using bilinear samples along a local normal.

    At each offset ``d``, sample normalized-convolution elevation at ``(row, col)
    plus and minus ``d * unit_gradient``. Return three finite float32 rasters:
    signed second difference, balanced shoulder relief, and normalized asymmetry.
    A flat or invalid center has zero direction/features. The caller must use only
    the feature-support-eroded domain; nearest-edge interpolation makes the array
    operation defined outside that eligible domain but does not make edge cells
    valid for modeling.
    """
    z = np.asarray(elevation, dtype=np.float32)
    mask = np.asarray(valid, dtype=bool)
    if z.ndim != 2 or mask.shape != z.shape:
        raise ValueError("elevation and valid must be same-shape 2D arrays")
    if not np.isfinite(pixel_size_m) or pixel_size_m <= 0:
        raise ValueError("pixel_size_m must be finite and positive")
    if not np.isfinite(sigma_px) or sigma_px < 0:
        raise ValueError("sigma_px must be finite and nonnegative")
    if not np.isfinite(flat_gradient_epsilon) or flat_gradient_epsilon < 0:
        raise ValueError("flat_gradient_epsilon must be finite and nonnegative")
    raw_offsets = tuple(offsets_px)
    if not raw_offsets or any(int(d) != d or int(d) <= 0 for d in raw_offsets):
        raise ValueError("offsets_px must contain one or more positive integers")
    offsets = tuple(int(d) for d in raw_offsets)

    good = mask & np.isfinite(z) & (z > -1e38)
    if sigma_px:
        smoothed = smooth(z, good, sigma_px)
    else:
        smoothed = np.where(good, z, 0).astype(np.float32)
    gy, gx = np.gradient(smoothed, pixel_size_m, pixel_size_m)
    magnitude = np.hypot(gx, gy)
    directed = good & np.isfinite(magnitude) & (magnitude > flat_gradient_epsilon)
    nx = np.divide(gx, magnitude, out=np.zeros_like(gx), where=directed)
    ny = np.divide(gy, magnitude, out=np.zeros_like(gy), where=directed)

    rows, cols = np.indices(z.shape, dtype=np.float32)
    center = smoothed.astype(np.float32, copy=False)
    output: dict[str, np.ndarray] = {}
    for distance in offsets:
        plus = ndi.map_coordinates(
            center,
            [rows + np.float32(distance) * ny, cols + np.float32(distance) * nx],
            order=1, mode="nearest", prefilter=False,
        )
        minus = ndi.map_coordinates(
            center,
            [rows - np.float32(distance) * ny, cols - np.float32(distance) * nx],
            order=1, mode="nearest", prefilter=False,
        )
        plus_relief = np.abs(plus - center)
        minus_relief = np.abs(minus - center)
        asymmetry = np.divide(
            np.abs(plus_relief - minus_relief),
            plus_relief + minus_relief + np.float32(1e-6),
            out=np.zeros_like(center),
            where=directed,
        )
        channels = {
            f"B_h55_paired_second_difference_{distance}": plus + minus - 2.0 * center,
            f"B_h55_paired_balanced_relief_{distance}": np.minimum(plus_relief, minus_relief),
            f"B_h55_paired_asymmetry_{distance}": asymmetry,
        }
        for name, values in channels.items():
            arr = np.asarray(values, dtype=np.float32)
            arr[~directed] = 0.0
            if not np.isfinite(arr).all():
                raise ValueError(f"nonfinite paired-shoulder values in {name}")
            output[name] = arr
    return output
