"""GeoTIFF Writer, Independent Disk Re-Read Format Verifier, and Uniqueness Gate.

Permanently prevents the DrivenData portal error:
  "Predicted values must be in range [0, 1]"
by enforcing in primary mode (`zeros`):
  - single band float32, EPSG:32611, 3730 x 3292, 100 m
  - nodata = None
  - every one of the 12,279,160 cells strictly finite in [0.0, 1.0]
  - 0 NaN cells, 0 +/-Inf cells, 0 negative float32 sentinels (-3.4028235e+38)
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile
import numpy as np
import rasterio
from rasterio.transform import Affine
from scipy.ndimage import distance_transform_edt

from .spec import CRS_STRING, EPSG, FOOTPRINT_PIXELS, HEIGHT, SHAPE, TOTAL_PIXELS, TRANSFORM_TUPLE, WIDTH


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_submission_geotiff(
    values_in_01: np.ndarray,
    footprint: np.ndarray,
    out_tif_path: Path,
    mode: str = "zeros",
) -> dict:
    """Write a single-band float32 GeoTIFF normalized to [0, 1] and re-read it from disk to verify."""
    arr = np.asarray(values_in_01, dtype=np.float32)
    fp = np.asarray(footprint, dtype=bool)
    if arr.shape != SHAPE or fp.shape != SHAPE:
        raise ValueError(f"Expected shape {SHAPE}, got {arr.shape}")

    # Guarantee finite [0.0, 1.0] inside footprint
    clean_in = np.where(np.isfinite(arr), np.clip(arr, 0.0, 1.0), 0.0).astype(np.float32)
    if mode == "zeros":
        out_arr = np.where(fp, clean_in, np.float32(0.0)).astype(np.float32)
        nodata_val = None
    elif mode == "nan":
        out_arr = np.where(fp, clean_in, np.float32(np.nan)).astype(np.float32)
        nodata_val = float("nan")
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    out_tif_path.parent.mkdir(parents=True, exist_ok=True)
    transform = Affine(*TRANSFORM_TUPLE)
    profile = {
        "driver": "GTiff",
        "height": HEIGHT,
        "width": WIDTH,
        "count": 1,
        "dtype": "float32",
        "crs": CRS_STRING,
        "transform": transform,
        "nodata": nodata_val,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(out_tif_path, "w", **profile) as dst:
        dst.write(out_arr, 1)

    return verify_geotiff_on_disk(out_tif_path, footprint=fp, mode=mode)


def write_submission_zip(tif_path: Path, zip_path: Path) -> dict:
    """Package the single GeoTIFF into a .zip archive as accepted by DrivenData."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(tif_path, arcname=tif_path.name)
    return {
        "zip_filename": zip_path.name,
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "contained_tif": tif_path.name,
    }


def verify_geotiff_on_disk(
    tif_path: Path,
    footprint: np.ndarray,
    labels: np.ndarray | None = None,
    mode: str = "zeros",
) -> dict:
    """Re-open `tif_path` from disk and verify every competition format & range invariant."""
    with rasterio.open(tif_path) as src:
        band = src.read(1)
        count = src.count
        dtype = str(src.dtypes[0])
        shape = (src.height, src.width)
        crs_epsg = src.crs.to_epsg() if src.crs else None
        tr = tuple(src.transform)[:6]
        nodata = src.nodata

    in_fp = band[footprint]
    out_fp = band[~footprint]
    pos_mask = np.isfinite(band) & (band > 0.0)

    on_cat = 0
    flank_le_2 = 0
    if labels is not None:
        on_cat = int((pos_mask & labels).sum())
        d_cat = distance_transform_edt(~labels)
        flank_le_2 = int((pos_mask & (d_cat <= 2.0)).sum())

    if mode == "zeros":
        outside_ok = bool(np.isfinite(out_fp).all() and (out_fp == 0.0).all() and (nodata is None))
        full_grid_ok = bool(
            np.isfinite(band).all()
            and float(band.min()) >= 0.0
            and float(band.max()) <= 1.0
        )
    else:
        outside_ok = bool(np.isnan(out_fp).all())
        full_grid_ok = bool(
            np.isfinite(in_fp).all()
            and float(in_fp.min()) >= 0.0
            and float(in_fp.max()) <= 1.0
        )

    checks = {
        "single_band": count == 1,
        "dtype_float32": dtype == "float32",
        "dimensions_3730x3292": shape == SHAPE,
        "crs_epsg_32611": crs_epsg == EPSG,
        "transform_exact": np.allclose(tr, TRANSFORM_TUPLE),
        "in_footprint_all_finite": bool(np.isfinite(in_fp).all() and in_fp.size == FOOTPRINT_PIXELS),
        "in_footprint_zero_nan": int(np.isnan(in_fp).sum()) == 0,
        "in_footprint_zero_inf": int(np.isinf(in_fp).sum()) == 0,
        "in_footprint_zero_sentinel": int((in_fp < -1e30).sum()) == 0,
        "in_footprint_range_0_1": bool(float(np.nanmin(in_fp)) >= 0.0 and float(np.nanmax(in_fp)) <= 1.0),
        "outside_footprint_compliant": outside_ok,
        "validator_range_0_1_guaranteed": full_grid_ok,
        "zero_on_catalogue_leakage": on_cat == 0,
        "zero_within_200m_catalogue_flank": flank_le_2 == 0,
    }
    return {
        "filename": tif_path.name,
        "size_bytes": tif_path.stat().st_size,
        "sha256": sha256_file(tif_path),
        "mode": mode,
        "crs": f"EPSG:{crs_epsg}",
        "transform": [float(x) for x in tr],
        "shape": list(shape),
        "dtype": dtype,
        "nodata": None if nodata is None or np.isnan(nodata) else float(nodata),
        "nodata_repr": str(nodata),
        "emitted_positive_pixels": int(pos_mask.sum()),
        "total_emitted_mass": round(float(np.nansum(band[footprint])), 4),
        "footprint_fraction": round(float(pos_mask.sum() / FOOTPRINT_PIXELS), 6),
        "on_catalogue_positive_pixels": on_cat,
        "within_200m_flank_positive_pixels": flank_le_2,
        "in_footprint_finite_pixels": int(np.isfinite(in_fp).sum()),
        "in_footprint_min": float(np.nanmin(in_fp)),
        "in_footprint_max": float(np.nanmax(in_fp)),
        "full_grid_finite_pixels": int(np.isfinite(band).sum()),
        "checks": checks,
        "all_checks_passed": bool(all(checks.values())),
    }


def run_uniqueness_gate(
    candidate_tif: Path,
    reference_dir: Path,
    non_union_report: dict,
) -> dict:
    """Verify byte-level SHA-256 uniqueness and pixel-set Jaccard distinctness against all
    prior GEMSDOE submissions in `reference_dir`, plus verify non-union with View A U View B.
    """
    cand_sha = sha256_file(candidate_tif)
    with rasterio.open(candidate_tif) as src:
        cand_pos = np.isfinite(src.read(1)) & (src.read(1) > 0)

    comparisons: list[dict] = []
    max_jaccard = 0.0
    sha_collision = False

    for ref_path in sorted(reference_dir.glob("*.tif")):
        ref_sha = sha256_file(ref_path)
        if ref_sha == cand_sha:
            sha_collision = True
        with rasterio.open(ref_path) as rds:
            ref_pos = np.isfinite(rds.read(1)) & (rds.read(1) > 0)
        inter = int((cand_pos & ref_pos).sum())
        uni = int((cand_pos | ref_pos).sum())
        jac = float(inter / max(uni, 1))
        sym_diff = int((cand_pos ^ ref_pos).sum())
        max_jaccard = max(max_jaccard, jac)
        comparisons.append({
            "reference_file": ref_path.name,
            "reference_sha256": ref_sha,
            "reference_positive_pixels": int(ref_pos.sum()),
            "candidate_positive_pixels": int(cand_pos.sum()),
            "shared_positive_pixels": inter,
            "symmetric_difference_pixels": sym_diff,
            "jaccard_similarity": round(jac, 5),
            "sha256_distinct": ref_sha != cand_sha,
        })

    passed = (not sha_collision) and (max_jaccard < 0.96) and bool(non_union_report["confirmed_not_mere_union"])
    return {
        "candidate_file": candidate_tif.name,
        "candidate_sha256": cand_sha,
        "candidate_positive_pixels": int(cand_pos.sum()),
        "references_checked": len(comparisons),
        "zero_sha256_collisions": not sha_collision,
        "max_jaccard_vs_prior_submissions": round(max_jaccard, 5),
        "non_union_verification": non_union_report,
        "comparisons": comparisons,
        "uniqueness_gate_passed": passed,
    }
