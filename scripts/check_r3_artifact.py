#!/usr/bin/env python3
"""Independently reopen the R3 TIFF and compare it with template and receipts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    marker = ROOT / "submission/R3_LATEST.txt"
    if not marker.exists():
        raise FileNotFoundError("R3_LATEST.txt not found")
    name = marker.read_text().strip()
    path = ROOT / "submission" / name
    published = ROOT / "docs/downloads" / name
    receipt_path = ROOT / "evidence/submission_r3.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("file") != name:
        raise ValueError("R3 marker and artifact receipt name differ")
    if not path.exists() or not published.exists():
        raise FileNotFoundError("submission TIFF or published download is missing")
    if receipt.get("approved_for_weekly_slot") is not False or receipt.get("weekly_submission_slots_used") != 0:
        raise ValueError("artifact receipt must remain no-slot research-only")
    if not str(receipt.get("artifact_status", "")).startswith("RESEARCH ONLY"):
        raise ValueError("artifact is not visibly research-only")
    note = str(receipt.get("submission_note") or receipt.get("note") or "")
    if len(note) > 200:
        raise ValueError("submission note exceeds the competition limit")

    with rasterio.open(path) as src, rasterio.open(ROOT / "data/sample_submission.tif") as sample:
        arr = src.read(1)
        mask_equal = bool(np.array_equal(src.dataset_mask() > 0, sample.dataset_mask() > 0))
        metadata = {
            "driver": src.driver,
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": src.dtypes[0],
            "crs": src.crs.to_string() if src.crs else None,
            "transform": list(src.transform)[:6],
            "transform_matches_sample": src.transform == sample.transform,
            "crs_matches_sample": src.crs == sample.crs,
            "bounds_match_sample": src.bounds == sample.bounds,
            "internal_mask_matches_sample": mask_equal,
            "finite": bool(np.isfinite(arr).all()),
            "minimum": float(arr.min()),
            "maximum": float(arr.max()),
            "values": [float(x) for x in np.unique(arr)],
            "positive_pixels": int(np.count_nonzero(arr)),
            "decoded_sha256": hashlib.sha256(arr.astype("<f4").tobytes()).hexdigest(),
        }
    byte_hash = sha256(path)
    checks = {
        "tiff": metadata["driver"] == "GTiff",
        "one_float32_band": metadata["count"] == 1 and metadata["dtype"] == "float32",
        "sample_grid": (metadata["width"] == 3292 and metadata["height"] == 3730
                        and metadata["crs"] == "EPSG:32611"
                        and metadata["transform_matches_sample"]
                        and metadata["crs_matches_sample"]
                        and metadata["bounds_match_sample"]),
        "finite_[0,1]": (metadata["finite"] and 0 <= metadata["minimum"]
                         and metadata["maximum"] <= 1),
        "binary_pattern_and_budget": (metadata["values"] == [0.0, 1.0]
                                      and metadata["positive_pixels"] == 37654),
        "mask_matches_sample": metadata["internal_mask_matches_sample"],
        "receipt_byte_hash": byte_hash == receipt.get("sha256"),
        "receipt_decoded_hash": metadata["decoded_sha256"] == receipt.get("decoded_sha256"),
        "published_copy_identical": path.read_bytes() == published.read_bytes(),
        "note_limit": len(note) <= 200,
        "research_only_no_slot": receipt.get("approved_for_weekly_slot") is False
                                  and receipt.get("weekly_submission_slots_used") == 0,
    }
    result = {
        "checked_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "file": name,
        "submission_sha256": byte_hash,
        "published_bytes": published.stat().st_size,
        "metadata": metadata,
        "checks": checks,
        "ok": all(checks.values()),
        "scope": "Independent post-build readback against the local sample template and current receipts; not an organizer portal test or geological truth check.",
    }
    out = ROOT / "evidence/independent_tiff_check_r3.json"
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
