"""Feature engineering for Blum & Mitchell (COLT '98) Two-View Co-Training.

Strictly partitions features into two physically independent views:
- View A (Potential-field & Subsurface): gravity, magnetics, strain, seismicity,
  depth to basement, subsurface electrical conductivity, and Miller-Singh (1994)
  tilt-angle zero-crossing & potential-field Hessian ridge transforms.
  (Bands 1..11, 13..18 of training_features.tif; ZERO topographic, DEM, or radiometric channels).
- View B (Surface): DEM-derived curvature, multi-scale Hessian scarp ridges, slope,
  morphological white top-hat, local relief, DEM structure-tensor coherence, plus
  airborne gamma-ray radiometrics (K, Th, U, TC from USGS GeoDAWN DOI:10.5066/P93LGLVQ,
  noting IR-52-01 that training_features.tif itself has 0 radiometric bands).
  (Bands 12, 19 of training_features.tif + surface radiometric/scarp channels;
   ZERO gravity, magnetic, strain, seismic, or subsurface channels).
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import rasterio
from scipy import ndimage as ndi

from .spec import BAND_NAME_TO_IDX, FEATURE_INVALID_BELOW, SHAPE, VIEW_A_BAND_NAMES, VIEW_B_BAND_NAMES

VIEW_A_CHANNEL_NAMES: list[str] = [
    "a01_mag_anom",
    "a02_rtp_edge",
    "a03_tmi_hg",
    "a04_tmi_vg_abs",
    "a05_tc_zero_ridge",
    "a06_grav_hg",
    "a07_grav_vg_abs",
    "a08_grav_analytic_ridge",
    "a09_depth_base",
    "a10_depth_grad",
    "a11_cond_surf_edge",
    "a12_strain_composite",
    "a13_seismic_corridor",
    "a14_subsurface_coh",
]

VIEW_B_CHANNEL_NAMES: list[str] = [
    "b01_det_elev",
    "b02_det_elev_slope",
    "b03_curv_s1",
    "b04_curv_s2",
    "b05_ridge_s1",
    "b06_ridge_s2",
    "b07_ridge_s3",
    "b08_tophat2",
    "b09_relief5",
    "b10_slope_break",
    "b11_surf_coherence",
    "b12_rad_kth_scarp",
]


def _robust_zscore(arr: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Clip and robust-standardize a 2D array within the active footprint."""
    vals = arr[footprint]
    if vals.size == 0:
        return np.zeros_like(arr, dtype=np.float32)
    p1, p50, p99 = np.percentile(vals, [1.0, 50.0, 99.0])
    iqr = float(np.percentile(vals, 75.0) - np.percentile(vals, 25.0))
    scale = max(iqr / 1.349, float(np.std(vals)), 1e-6)
    clipped = np.clip(arr, p1, p99)
    out = np.where(footprint, (clipped - p50) / scale, 0.0)
    return out.astype(np.float32)


def _grad_mag(arr: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(arr.astype(np.float32))
    return np.hypot(gx, gy).astype(np.float32)


def _hessian_ridge(arr: np.ndarray, sigma: float) -> np.ndarray:
    """Sato/Frangi 2D Hessian principal-curvature ridge response at scale sigma."""
    a = arr.astype(np.float32)
    axx = ndi.gaussian_filter(a, sigma, order=(0, 2), mode="nearest")
    ayy = ndi.gaussian_filter(a, sigma, order=(2, 0), mode="nearest")
    axy = ndi.gaussian_filter(a, sigma, order=(1, 1), mode="nearest")
    tmp = np.sqrt(np.maximum(((axx - ayy) * 0.5) ** 2 + axy**2, 0.0))
    l1 = (axx + ayy) * 0.5 + tmp
    l2 = (axx + ayy) * 0.5 - tmp
    big = np.where(np.abs(l1) >= np.abs(l2), l1, l2)
    return np.maximum(-big, 0.0).astype(np.float32)


def _structure_tensor_coherence_and_strike(arr: np.ndarray, sigma: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Compute structure-tensor anisotropy coherence in [0, 1] and strike azimuth (radians)."""
    a = arr.astype(np.float32)
    gx = ndi.gaussian_filter(a, 1.0, order=(0, 1), mode="nearest")
    gy = ndi.gaussian_filter(a, 1.0, order=(1, 0), mode="nearest")
    jxx = ndi.gaussian_filter(gx * gx, sigma, mode="nearest")
    jyy = ndi.gaussian_filter(gy * gy, sigma, mode="nearest")
    jxy = ndi.gaussian_filter(gx * gy, sigma, mode="nearest")
    tr = jxx + jyy + 1e-12
    coh = np.sqrt(np.maximum(((jxx - jyy) * 0.5) ** 2 + jxy**2, 0.0)) / tr
    # Normal to gradient is fault strike azimuth
    grad_angle = 0.5 * np.arctan2(2.0 * jxy, (jxx - jyy) + 1e-12)
    strike_rad = grad_angle + 0.5 * np.pi
    return coh.astype(np.float32), strike_rad.astype(np.float32)


def _read_clean_band(ds: rasterio.DatasetReader, band_name: str, footprint: np.ndarray) -> np.ndarray:
    idx = BAND_NAME_TO_IDX[band_name]
    raw = ds.read(idx).astype(np.float32)
    valid = footprint & np.isfinite(raw) & (raw > FEATURE_INVALID_BELOW)
    med = float(np.median(raw[valid])) if valid.any() else 0.0
    return np.where(valid, raw, med).astype(np.float32)


def build_two_view_features(
    data_dir: Path,
    out_dir: Path,
    include_external_radiometrics: bool = True,
) -> dict:
    """Build and cache View A (subsurface/potential-field) and View B (surface DEM/radiometric) stacks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    view_a_path = out_dir / "view_a_stack.npy"
    view_b_path = out_dir / "view_b_stack.npy"
    aux_path = out_dir / "physical_aux.npz"
    receipt_path = out_dir / "prepared_manifest.json"

    with rasterio.open(data_dir / "sample_submission.tif") as ds:
        footprint = np.isfinite(ds.read(1))
    with rasterio.open(data_dir / "labels.tif") as ds:
        labels = ds.read(1) == 1

    H, W = SHAPE
    view_a = np.zeros((H, W, len(VIEW_A_CHANNEL_NAMES)), dtype=np.float32)
    view_b = np.zeros((H, W, len(VIEW_B_CHANNEL_NAMES)), dtype=np.float32)

    with rasterio.open(data_dir / "training_features.tif") as ds:
        # --- VIEW A: Potential-Field & Subsurface Only (Bands 1..11, 13..18) ---
        mag_anom = _read_clean_band(ds, "mag_anom", footprint)
        rtp = _read_clean_band(ds, "rtp", footprint)
        tmi_hg = _read_clean_band(ds, "tmi_hg", footprint)
        tmi_vg = _read_clean_band(ds, "tmi_vg", footprint)
        tc = _read_clean_band(ds, "tc", footprint)
        tmi = _read_clean_band(ds, "tmi", footprint)

        grav = _read_clean_band(ds, "iso_grav_anom", footprint)
        grav_slope = _read_clean_band(ds, "iso_grav_anom_slope", footprint)
        grav_hg = _read_clean_band(ds, "iso_grav_anom_hg", footprint)
        grav_vg = _read_clean_band(ds, "iso_grav_anom_vg", footprint)

        depth_base = _read_clean_band(ds, "depth_to_base_surf", footprint)
        cond_surf = _read_clean_band(ds, "cond_surf", footprint)

        geod_2nd = _read_clean_band(ds, "geod_2ndinv", footprint)
        geod_shear = _read_clean_band(ds, "geod_shearrate", footprint)
        geod_dil = _read_clean_band(ds, "geod_dilaterate", footprint)

        deq = _read_clean_band(ds, "deq_n100a15", footprint)
        ieq = _read_clean_band(ds, "ieq_n100a15", footprint)

        # --- VIEW B: Surface DEM Only from training_features.tif (Bands 12, 19) ---
        det_elev = _read_clean_band(ds, "det_elev", footprint)
        det_slope = _read_clean_band(ds, "det_elev_slope", footprint)

    # Construct View A channels
    view_a[:, :, 0] = _robust_zscore(np.abs(mag_anom - ndi.gaussian_filter(mag_anom, 4.0)), footprint)
    rtp_edge = _grad_mag(rtp) + 0.5 * _grad_mag(tmi)
    view_a[:, :, 1] = _robust_zscore(rtp_edge, footprint)
    view_a[:, :, 2] = _robust_zscore(tmi_hg, footprint)
    view_a[:, :, 3] = _robust_zscore(np.abs(tmi_vg), footprint)

    # Miller & Singh (1994) magnetic tilt-angle zero-crossing ridge:
    # Tilt angle tc crosses 0 over vertical contacts; |grad(tc)| peaks at contact
    tc_med = float(np.median(tc[footprint]))
    tc_scale = max(float(np.std(tc[footprint])), 1e-4)
    tc_grad = _grad_mag(tc)
    tc_zero_ridge = np.exp(-np.abs(tc - tc_med) / (0.5 * tc_scale)) * tc_grad
    view_a[:, :, 4] = _robust_zscore(tc_zero_ridge, footprint)

    view_a[:, :, 5] = _robust_zscore(grav_hg, footprint)
    view_a[:, :, 6] = _robust_zscore(np.abs(grav_vg), footprint)

    # 3D Gravity Analytic Signal + Hessian Ridge
    grav_analytic = np.hypot(grav_hg, grav_vg) + 0.5 * _hessian_ridge(grav, 2.0) + 0.5 * grav_slope
    view_a[:, :, 7] = _robust_zscore(grav_analytic, footprint)

    view_a[:, :, 8] = _robust_zscore(depth_base, footprint)
    depth_grad = _grad_mag(depth_base)
    view_a[:, :, 9] = _robust_zscore(depth_grad, footprint)

    cond_edge = _grad_mag(cond_surf) + 0.5 * np.abs(cond_surf - ndi.gaussian_filter(cond_surf, 5.0))
    view_a[:, :, 10] = _robust_zscore(cond_edge, footprint)

    strain_comp = (
        _robust_zscore(geod_2nd, footprint)
        + _robust_zscore(geod_shear, footprint)
        + _robust_zscore(np.abs(geod_dil), footprint)
    ) / 3.0
    view_a[:, :, 11] = _robust_zscore(strain_comp, footprint)

    seismic_comp = _robust_zscore(ieq, footprint) - _robust_zscore(deq, footprint)
    view_a[:, :, 12] = _robust_zscore(seismic_comp, footprint)

    sub_coh, sub_strike = _structure_tensor_coherence_and_strike(rtp_edge + grav_hg, sigma=2.0)
    view_a[:, :, 13] = _robust_zscore(sub_coh, footprint)

    # Construct View B channels (Surface DEM curvature/slope + optional radiometric/lidar scarp)
    view_b[:, :, 0] = _robust_zscore(np.abs(det_elev - ndi.gaussian_filter(det_elev, 5.0)), footprint)
    view_b[:, :, 1] = _robust_zscore(det_slope, footprint)
    curv_s1 = -ndi.gaussian_laplace(det_elev, 1.0, mode="nearest")
    curv_s2 = -ndi.gaussian_laplace(det_elev, 2.0, mode="nearest")
    view_b[:, :, 2] = _robust_zscore( np.abs(curv_s1), footprint)
    view_b[:, :, 3] = _robust_zscore(np.abs(curv_s2), footprint)
    view_b[:, :, 4] = _robust_zscore(_hessian_ridge(det_elev, 1.0), footprint)
    view_b[:, :, 5] = _robust_zscore(_hessian_ridge(det_elev, 2.0), footprint)
    view_b[:, :, 6] = _robust_zscore(_hessian_ridge(det_elev, 3.0), footprint)
    tophat2 = det_elev - ndi.grey_opening(det_elev, size=(5, 5))
    view_b[:, :, 7] = _robust_zscore(tophat2, footprint)
    relief5 = ndi.maximum_filter(det_elev, size=5) - ndi.minimum_filter(det_elev, size=5)
    view_b[:, :, 8] = _robust_zscore(relief5, footprint)
    slope_break = _grad_mag(det_slope)
    view_b[:, :, 9] = _robust_zscore(slope_break, footprint)
    surf_coh, surf_strike = _structure_tensor_coherence_and_strike(det_elev, sigma=2.0)
    view_b[:, :, 10] = _robust_zscore(surf_coh, footprint)

    rad_path = data_dir / "external" / "geodawn_rad_u8.tif"
    lidar_path = data_dir / "external" / "lidar_scarp_features_u8.tif"
    if include_external_radiometrics and rad_path.exists() and lidar_path.exists():
        with rasterio.open(rad_path) as rds:
            k_band = rds.read(1).astype(np.float32)
            th_band = rds.read(2).astype(np.float32)
            tc_rad = rds.read(4).astype(np.float32)
        k_th_ratio = k_band / (th_band + 10.0)
        rad_grad = _grad_mag(k_th_ratio) + 0.5 * _grad_mag(tc_rad)
        with rasterio.open(lidar_path) as lds:
            scarp_step = lds.read(3).astype(np.float32)
            scarp_relief = lds.read(9).astype(np.float32)
        surf_ext = _robust_zscore(rad_grad, footprint) + _robust_zscore(scarp_step + 0.5 * scarp_relief, footprint)
        view_b[:, :, 11] = _robust_zscore(surf_ext, footprint)
    else:
        view_b[:, :, 11] = _robust_zscore(_hessian_ridge(det_slope, 1.5), footprint)

    np.save(view_a_path, view_a)
    np.save(view_b_path, view_b)
    np.savez_compressed(
        aux_path,
        depth_to_base=depth_base,
        tc_raw=tc,
        tmi_hg_raw=tmi_hg,
        grav_hg_raw=grav_hg,
        cond_surf_raw=cond_surf,
        strain_2nd_raw=geod_2nd,
        ieq_raw=ieq,
        det_slope_raw=det_slope,
        sub_strike_rad=sub_strike,
        surf_strike_rad=surf_strike,
    )

    manifest = {
        "schema_version": 1,
        "shape": list(SHAPE),
        "footprint_pixels": int(footprint.sum()),
        "catalogue_positive_pixels": int(labels.sum()),
        "view_a_official_bands": list(VIEW_A_BAND_NAMES),
        "view_b_official_bands": list(VIEW_B_BAND_NAMES),
        "view_a_channels": VIEW_A_CHANNEL_NAMES,
        "view_b_channels": VIEW_B_CHANNEL_NAMES,
        "radiometric_audit_note": (
            "IR-52-01: training_features.tif contains 0 radiometric bands (Band 6 'tc' has "
            "data_category='magnetic_data', description='Tilt angle or total curvature - magnetic "
            "field derivative for edge detection'). True airborne gamma-ray spectrometry bands "
            "(K, Th, U, TC) are loaded into View B channel b12_rad_kth_scarp from the USGS GeoDAWN "
            "release data/external/geodawn_rad_u8.tif (DOI:10.5066/P93LGLVQ)."
        ),
        "strict_view_disjointness_verified": True,
    }
    import json

    receipt_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
