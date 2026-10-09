"""The universal-overlap preflight checks pixels, not merely counts or filenames."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from preflight_registry import measure


def write(path, a):
    with rasterio.open(path, "w", driver="GTiff", height=a.shape[0], width=a.shape[1],
                       count=1, dtype="float32", crs="EPSG:32611",
                       transform=from_origin(0, 1000, 100, 100), nodata=np.nan) as d:
        d.write(a, 1)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_full_positive_reference_blocks_any_nonempty_dot_placement(tmp_path):
    s, r = tmp_path / "s.tif", tmp_path / "r.tif"
    sample = np.full((4, 5), np.nan, np.float32)
    sample[1:3, 1:4] = 0
    sample_hash = write(s, sample)
    ref = np.zeros_like(sample)
    ref[1:3, 1:4] = 0.001  # small but still a dot under the protocol's >0 rule
    ref_hash = write(r, ref)
    m = measure(s, r, sample_hash, ref_hash)
    assert m["footprint_px"] == m["reference_positive_footprint_px"] == 6
    assert m["universal_overlap_blocker"]
    assert m["overlap_for_any_nonempty_conformant_dot_map"] == 1


def test_count_equal_to_footprint_is_not_sufficient_without_mask(tmp_path):
    s, r = tmp_path / "s.tif", tmp_path / "r.tif"
    sample = np.full((4, 5), np.nan, np.float32)
    sample[1:3, 1:4] = 0
    sample_hash = write(s, sample)
    ref = np.zeros_like(sample)
    ref[1:3, 1:4] = 1
    ref[1, 2] = 0
    ref[0, 0] = 1  # overall dot count still six; footprint not completely positive
    m = measure(s, r, sample_hash, write(r, ref))
    assert m["reference_positive_footprint_px"] == 5
    assert m["universal_overlap_blocker"] is False
    assert m["overlap_for_any_nonempty_conformant_dot_map"] is None


def test_provenance_and_grid_are_fail_closed(tmp_path):
    s, r = tmp_path / "s.tif", tmp_path / "r.tif"
    sample = np.ones((4, 5), np.float32)
    sample_hash = write(s, sample)
    ref_hash = write(r, sample)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        measure(s, r, "wrong", ref_hash)
    with rasterio.open(r, "r+") as ds:
        ds.transform = from_origin(100, 1000, 100, 100)
    with pytest.raises(ValueError, match="grid mismatch"):
        measure(s, r, sample_hash, hashlib.sha256(r.read_bytes()).hexdigest())


def test_site_refuses_fake_ready_label(monkeypatch):
    import build_site

    original = build_site.J
    def forged(rel):
        result = original(rel)
        if rel == "docs/submissions/archive/CURRENT_2026-10-09-S3.json":
            result["label"] = "Validated / OK to submit"
        return result
    monkeypatch.setattr(build_site, "J", forged)
    with pytest.raises(ValueError, match="refusing a submission-ready label"):
        build_site.main()


def test_real_receipt_and_download_match():
    receipt = json.loads((ROOT / "evidence/protocol_preflight_20261009.json").read_text())
    assert receipt["universal_overlap_blocker"]
    assert receipt["reference_positive_footprint_px"] == receipt["footprint_px"] == 5167373
    assert receipt["reference_nonpositive_or_nonfinite_footprint_px"] == 0
    # Re-open the real inputs when available. CI need not download the 25 MB reference.
    s = Path("/tmp/gems53-data/sample_submission.tif")
    r = Path("/tmp/g53-17/docs/downloads/17GEMSDOE_E-proba-multiscale_20260930T044527Z.tif")
    if s.exists() and r.exists():
        assert measure(s, r) == receipt
    index = (ROOT / "docs/archive/main-2026-10-09-S3/index.html").read_text()
    assert "Pre-placement STOP" in index and "DO NOT SUBMIT" in index
    assert "data/protocol_preflight_20261009.json" in index
    assert (ROOT / "docs/data/protocol_preflight_20261009.json").exists()
