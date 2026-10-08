"""H59 — artifact integrity and receipt-consistency checks, re-read from bytes on disk.

Nothing here trusts prose: the TIFF is opened, the gates are recomputed where cheap, and the
approval state is only valid if it equals the mechanical slot-gate receipt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
EV = ROOT / "evidence"


def _build():
    p = EV / "h59_build.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def test_h59_receipts_exist_and_agree_with_bytes() -> None:
    b = _build()
    if b is None:
        return                          # round not built in this checkout; nothing to assert
    path = ROOT / "submission" / b["file"]
    assert path.exists()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == b["sha256"]
    assert path.stat().st_size == b["bytes"]
    with rasterio.open(path) as ds:
        assert ds.count == 1 and ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        assert ds.nodata is None, "a nodata sentinel is what reads back as NaN and trips [0,1]"
        a = ds.read(1)
    assert np.isfinite(a).all(), "all-finite is the portal range-error guard"
    assert set(np.unique(a).tolist()) == {0.0, 1.0}
    assert int(np.count_nonzero(a)) == b["nonzero_px"]
    assert b["core_px"] + b["arm_px"] == b["nonzero_px"]

    # The ring rule re-measured, not trusted.
    #
    # The staging directory is a restore_data.py target and is git-ignored, so it is
    # absent in a clean checkout. The guard below used to test only whether the catalogue
    # had any True pixel, which meant rasterio.open had already raised FileNotFoundError
    # before the guard could fire -- this test failed CI on every clean run. The
    # existence check has to come first; the intent of the original comment is unchanged.
    pinned = ROOT / "work/h59_pinned" / "labels.tif"
    if not pinned.exists():
        return                          # pinned staging absent in this checkout (CI keeps only core)
    with rasterio.open(pinned) as ds:
        cat = ds.read(1) == 1
    if not cat.any():
        return                          # staging present but carries no catalogue
    dcat = ndimage.distance_transform_edt(~cat, sampling=100.0)
    ys, xs = np.nonzero(a > 0)
    assert float(dcat[ys, xs].min()) >= 200.0


def test_h59_approval_state_must_equal_the_mechanical_gate() -> None:
    b = _build()
    if b is None:
        return
    slot = json.loads((EV / "h59_slot_gate.json").read_text())
    mechanical = bool(slot["slot_bar_met"] and slot["checks_pass"])
    assert b["approved_for_weekly_slot"] == mechanical, (
        "approval may only mirror the registered gate; it can never be asserted")
    if mechanical:
        assert all(slot["checks"].values())
    # the pointer invariant holds either way
    marker = (ROOT / "submission/LATEST.txt").read_text().strip()
    sub = json.loads((DOCS / "data/submission.json").read_text())
    assert sub["file"] == marker


def test_h59_site_copies_are_byte_identical() -> None:
    b = _build()
    if b is None:
        return
    canon = ROOT / "submission" / b["file"]
    alias = DOCS / "downloads/h59-candidate.tif"
    assert alias.exists() and alias.read_bytes() == canon.read_bytes()
    doc = DOCS / "downloads" / b["file"]
    assert doc.exists() and doc.read_bytes() == canon.read_bytes()
    for name in ("h59_build.json", "h59_format_gate.json", "h59_uniqueness.json",
                 "h59_slot_gate.json", "h59_cotrain.json", "h59_validation.json",
                 "h59_preflight_integrity.json", "submission_h59.json",
                 "h59_preregistration.json"):
        assert (DOCS / "data" / name).exists(), f"docs/data/{name} missing"
    fmt = json.loads((DOCS / "data/h59_format_gate.json").read_text())
    assert fmt["problems"] == []


def test_h59_prior_inventory_excludes_its_own_round(monkeypatch, tmp_path) -> None:
    """IR-H59-001 regression: a rebuild must be a fixed point, not self-contaminating."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "build_h59_submission", ROOT / "scripts" / "build_h59_submission.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    made = []
    for nm in ("gems52-h59-union-core25517px-arm14787px.tif", "h59-candidate.tif",
               "h59-candidate.zip", "gems52-h57-union-novel-core25517px-arm14804px.tif",
               "gems52-h59-edge-coh-cotrain-37654px-20261008T022050Z-0f0984928454.tif"):
        q = tmp_path / nm
        q.write_bytes(b"x")
        made.append(q)
    monkeypatch.setattr(m.gates, "find_priors", lambda roots: [str(q) for q in made])
    kept = [Path(str(q)).name for q in m.prior_inventory()]
    assert "gems52-h57-union-novel-core25517px-arm14804px.tif" in kept
    assert "gems52-h59-edge-coh-cotrain-37654px-20261008T022050Z-0f0984928454.tif" in kept
    assert not any(k.startswith(("gems52-h59-union", "h59-candidate")) for k in kept)
