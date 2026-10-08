"""Current artifact and archive integrity checks; local gates are not upload approval."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DOWNLOADS = DOCS / "downloads"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _current_round(sub: dict) -> str:
    """Which round owns `submission/LATEST.txt`, read from the receipt rather than hard-coded."""
    f = sub.get("file", "")
    for tag in ("h59", "h58", "h57", "h56", "h55", "h54"):
        if f"-{tag}-" in f:
            return tag.upper()
    return "UNKNOWN"


def test_current_artifact_is_downloadable_but_not_slot_approved() -> None:
    """Round-aware: whichever round owns the pointer, its own gates must hold.

    The H56 assertions below are kept verbatim in `test_h56_archive_stays_intact` so that H56's
    findings remain checked after it stops being the incumbent.
    """
    sub = json.loads((DOCS / "data/submission.json").read_text())
    rnd = _current_round(sub)

    assert (ROOT / "submission/LATEST.txt").read_text().strip() == sub["file"]
    if rnd == "H59":
        # approval may only mirror the mechanical registered gate (tests/test_h59.py re-verifies
        # that it cannot be asserted); the pointer test stays fully round-agnostic
        slot = json.loads((ROOT / "evidence/h59_slot_gate.json").read_text())
        mechanical = bool(slot["slot_bar_met"] and slot["checks_pass"])
        assert sub["approved_for_weekly_slot"] == mechanical
        assert sub.get("promoted_field") == slot["shipped_field"]
    else:
        assert sub["approved_for_weekly_slot"] is False, "the slot gate must never be asserted open"
        assert sub.get("promoted") is False

    canonical = DOWNLOADS / sub["file"]
    # the scheduled feed rewrites docs/data/submission.json from evidence/submission_<stem>.json,
    # so the short aliases follow the repository convention rather than a publisher-only key
    short = (DOWNLOADS / "h57-candidate.tif" if "-h57-" in sub["file"]
             else DOWNLOADS / "h59-candidate.tif" if "-h59-" in sub["file"]
             else DOWNLOADS / Path(sub["short_tif"]).name)
    assert canonical.exists(), f"{rnd}: canonical download missing"
    assert sha(canonical) == sub["sha256"]
    assert short.read_bytes() == canonical.read_bytes()

    # A ZIP is a valid submission payload when it holds exactly one GeoTIFF that is the canonical
    # download.  The scheduled feed repackages the canonical ZIP for whatever LATEST.txt names and
    # adds SUBMISSION_NOTE.txt / evidence.json beside the TIFF, so archive-level byte equality with
    # the short alias is reported by check_site as a note, not demanded here.
    canonical_zip = DOWNLOADS / (sub["file"][:-4] + ".zip")
    short_zip = (DOWNLOADS / "h57-candidate.zip" if "-h57-" in sub["file"]
                 else DOWNLOADS / "h59-candidate.zip" if "-h59-" in sub["file"]
                 else DOWNLOADS / Path(sub["short_zip"]).name)
    for zp in (canonical_zip, short_zip):
        with zipfile.ZipFile(zp) as archive:
            tiffs = [n for n in archive.namelist() if n.lower().endswith((".tif", ".tiff"))]
            assert len(tiffs) == 1, f"{zp.name} must hold exactly one GeoTIFF"
            assert archive.read(tiffs[0]) == canonical.read_bytes()

    with rasterio.open(canonical) as ds:
        data = ds.read(1)
        assert ds.count == 1
        assert ds.dtypes == ("float32",)
        assert ds.crs.to_epsg() == 32611
        assert (ds.height, ds.width) == (3730, 3292)
        assert tuple(ds.transform)[:6] == (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
        assert np.isfinite(data).all(), "NaN is the mechanism behind the historical [0,1] rejection"
        assert set(np.unique(data).tolist()) == {0.0, 1.0}
        assert int(np.count_nonzero(data)) == sub["nonzero_px"]

    if rnd == "H57":
        build = json.loads((DOCS / "data/h57_build.json").read_text())
        gate = json.loads((DOCS / "data/h57_slot_gate.json").read_text())
        assert build["format_gate"]["ok"], build["format_gate"]["problems"]
        assert build["uniqueness"]["canonical_pattern_unique"]
        assert build["not_the_union"]["arm_outside_prior_support_px"] == build["arm"]["px"]
        assert build["file"]["min_distance_to_catalogue_m"] > 200.0
        assert len(str(sub.get("note") or sub.get("submission_note") or "")) <= 200
        # R1 is registered as unmet for this round; if that ever changes it must change loudly
        assert gate["r1"]["met"] is False
        assert gate["checks"]["R4 format gate (single band, float32, EPSG:32611, 3730x3292, "
                             "transform, all finite, [0,1], no nodata)"] is True

    if rnd == "H59":
        # the H59 receipt carries its own gate report; the site's current-pointer file must agree
        result = json.loads((DOCS / "data/h59_result.json").read_text())
        assert result["artifact"]["format_gate"]["ok"], result["artifact"]["format_gate"]["problems"]
        assert result["artifact"]["uniqueness"]["canonical_pattern_unique"]
        assert result["artifact"]["ring_min_distance_m"] > 200.0
        assert (result["artifact"]["spacing"]["min_nn_px"] or 0) >= 3.0
        # amendment 3 gate semantics: the forbidden equalities are the set-union of the two views'
        # emissions and the union-field emission; equality with a constituent view's own emission
        # is reported and expected exactly when that view is the shipped field
        ntu = result["artifact"]["not_the_union"]
        assert not ntu["equals_set_union"]
        assert not ntu["equals_union_field"]
        shipped = result["holdout"]["decision"]["shipped_field"]
        assert ntu["equals_view_b"] is (shipped == "view_B")
        assert ntu["equals_view_a"] is (shipped == "view_A")
        assert result["reasoning_dossier"]["rows"] == sub["nonzero_px"]
        assert result["reasoning_dossier"]["a_only_rows"] >= 0
        assert len(str(sub.get("note") or sub.get("submission_note") or "")) <= 200
        # the repo's standing rule: the machine field never asserts an open slot gate
        assert result["artifact"]["emission_px"] == 37654


def test_h56_archive_stays_intact() -> None:
    """H56 stopped being the incumbent when H57 shipped; its own receipts must still verify."""
    gate = json.loads((DOCS / "data/h56_slot_gate_review_2026-10-07.json").read_text())
    verify = json.loads((DOCS / "data/gems52-h56-verify.json").read_text())
    scope = json.loads((DOCS / "data/h56_a_only_reasoning_scope_2026-10-07.json").read_text())

    assert gate["decision"]["approved_for_weekly_slot"] is False
    assert gate["spatial_holdout"]["h56_comparable_holdout_receipt_found"] is False
    assert gate["leaderboard_score_to_filename_mapping_authenticated"] is False
    assert verify["identical_to_any_prior"] == []
    assert verify["priors_checked"] == 33
    assert verify["novel_px"] == 12941
    assert verify["min_NN_separation_ok"] is False
    assert gate["postbuild_decoded_pattern_review"]["derived_arm_cells_with_accessible_prior_support"] == 2059
    assert scope["status"].startswith("NOT PRODUCED")

    canonical = DOWNLOADS / "gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif"
    short = DOWNLOADS / "h56-candidate.tif"
    assert canonical.exists() and short.exists()
    assert short.read_bytes() == canonical.read_bytes()
    assert sha(canonical) != json.loads(
        (DOCS / "data/submission.json").read_text())["sha256"], "H56 must not be the incumbent"
    with rasterio.open(canonical) as ds:
        assert int(np.count_nonzero(ds.read(1))) == 40517
    canonical_zip = DOWNLOADS / (canonical.stem + ".zip")
    short_zip = DOWNLOADS / "h56-candidate.zip"
    assert canonical_zip.read_bytes() == short_zip.read_bytes()
    with zipfile.ZipFile(short_zip) as archive:
        assert archive.namelist() == [canonical.name]
        assert archive.read(canonical.name) == canonical.read_bytes()


def test_h54_remains_a_separate_audit_only_archive() -> None:
    audit = json.loads((DOCS / "data/h54_audit.json").read_text())
    assert audit["approved_for_weekly_slot"] is False
    assert audit["global_decoded_pattern_uniqueness"].startswith("unknown")
    assert audit["file"] != (ROOT / "submission/LATEST.txt").read_text().strip()

    canonical = DOWNLOADS / audit["file"]
    short = DOWNLOADS / "h54-audit-only.tif"
    assert short.read_bytes() == canonical.read_bytes()
    with zipfile.ZipFile(DOWNLOADS / "h54-audit-only.zip") as archive:
        tiffs = [name for name in archive.namelist() if name.lower().endswith((".tif", ".tiff"))]
        assert len(tiffs) == 1
        assert archive.read(tiffs[0]) == canonical.read_bytes()
