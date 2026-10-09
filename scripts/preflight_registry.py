#!/usr/bin/env python3
"""Fail-closed pre-placement audit of the literal 3-pixel registry-dot rule.

This does not reinterpret the user's >70% threshold. If a registry raster has a
positive value in EVERY competition-footprint pixel, every nonempty conformant
prediction overlaps that raster at distance 0, hence the overlap is 100% for
*any* placement, independently of the model. An empty prediction is not a
competitive submission. Inspect actual raster pixels, not a dot count alone.

Reproduce (paths to the pinned mirror and the public GEMSDOE17 repo):
  python scripts/fetch_data.py --data-dir /tmp/gems53-data
  git clone --depth 1 --filter=blob:none --no-checkout \
    https://github.com/buffedlizard55-lab/17GEMSDOE.git /tmp/g53-17
  cd /tmp/g53-17 && git sparse-checkout init --no-cone && \
    git sparse-checkout set 'docs/downloads/17GEMSDOE_E-proba-multiscale_20260930T044527Z.tif' && git checkout
  cd -
  python scripts/preflight_registry.py --sample /tmp/gems53-data/sample_submission.tif \
    --reference /tmp/g53-17/docs/downloads/17GEMSDOE_E-proba-multiscale_20260930T044527Z.tif \
    --out evidence/protocol_preflight_20261009.json

Exit 2 for a blocker, 1 for an unverified input, 0 only when this particular
reference does not create a universal blocker (NOT an overall uniqueness pass).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REFERENCE_SHA256 = "ab0a0a62eecf066a82713b09dd49f0f638a91fa3dd81f54cc34ae89afa3872be"
SAMPLE_SHA256 = "2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"
REFERENCE_URL = "https://github.com/buffedlizard55-lab/17GEMSDOE/blob/main/docs/downloads/17GEMSDOE_E-proba-multiscale_20260930T044527Z.tif"
SAMPLE_URL = "https://github.com/buffedlizard55-lab/GEMSDOE/blob/main/data/bridge/manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def measure(sample: Path, reference: Path, expected_sample: str = SAMPLE_SHA256,
            expected_reference: str = REFERENCE_SHA256) -> dict:
    import numpy as np
    import rasterio

    sample_hash, ref_hash = sha256(sample), sha256(reference)
    if sample_hash != expected_sample or ref_hash != expected_reference:
        raise ValueError("SHA256 mismatch: sample/reference provenance cannot be established")
    with rasterio.open(sample) as s, rasterio.open(reference) as r:
        if (s.shape != r.shape or s.transform != r.transform or s.crs != r.crs or
                s.count != 1 or r.count != 1):
            raise ValueError("sample/reference grid mismatch")
        fp = np.isfinite(s.read(1))
        a = r.read(1)
        if not fp.any():
            raise ValueError("empty sample footprint")
        positive = np.isfinite(a) & (a > 0)
        n = int(fp.sum())
        covered = int((fp & positive).sum())
        return {
            "sample_sha256": sample_hash,
            "reference_sha256": ref_hash,
            "reference_url": REFERENCE_URL,
            "sample_manifest_url": SAMPLE_URL,
            "crs": str(s.crs),
            "shape": list(s.shape),
            "transform": list(s.transform),
            "grid_matches": True,
            "footprint_px": n,
            "reference_positive_footprint_px": covered,
            "reference_nonpositive_or_nonfinite_footprint_px": n - covered,
            "universal_overlap_blocker": covered == n,
            "overlap_for_any_nonempty_conformant_dot_map": 1.0 if covered == n else None,
            "limit_strictly_greater_than": 0.70,
            "verdict": "STOP: literal registry rule impossible for nonempty prediction" if covered == n
                       else "UNKNOWN: this raster does not establish a universal blocker",
            "scope": "one public registry raster; does not prove that all future registry rasters are checked",
        }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sample", required=True, type=Path)
    p.add_argument("--reference", required=True, type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    try:
        receipt = measure(a.sample, a.reference)
    except (OSError, ValueError) as exc:
        print(f"UNVERIFIED / STOP: {exc}")
        return 1
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 2 if receipt["universal_overlap_blocker"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
