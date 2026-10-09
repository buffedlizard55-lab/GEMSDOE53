"""Session-2 consistency tests: CURRENT.json ↔ build receipt ↔ file bytes ↔ gates ↔ label ↔ site.

The label rule tested here is the pre-registered verdict matrix
(docs/research/preregistration-2026-10-09-session2.md section 1).
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = Path("/tmp/gems53-data/sample_submission.tif")


def _load(rel):
    return json.loads((ROOT / rel).read_text())


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def test_current_pointer_matches_build_receipt_and_file():
    cur = _load("docs/submissions/CURRENT.json")
    rec = _load("evidence/s3_c1_build_receipt.json")
    assert cur["name"] == rec["name"]
    assert cur["file"] == rec["file"]
    assert cur["sha256"] == rec["sha256_file"]
    assert cur["pixel_sha256"] == rec["pixel_sha256"]
    assert cur["bytes"] == rec["bytes"]
    tif = ROOT / cur["file"]
    assert tif.exists()
    assert _sha(tif) == cur["sha256"]
    assert tif.stat().st_size == cur["bytes"]
    assert len(cur["note"]) <= 140
    assert cur["submitted"] is False and cur["organizer_score"] is None
    assert "HOLDOUT-DTI" in cur["note"] or "RESEARCH-ONLY" in cur["note"]


def test_label_follows_the_session2_verdict_matrix():
    cur = _load("docs/submissions/CURRENT.json")
    s2 = _load("evidence/s2_c1_holdout.json")
    gate = _load("evidence/uniqueness_gate_v2_session2.json")
    val = _load("evidence/s2_validator_receipt.json")
    canary_ok = s2["canary_S2_E1"]["flag"] == "pass"
    stage2_ok = bool(s2.get("spatial_confirmation", {}).get("acceptance", {}).get("accepted"))
    gate_ok = bool(gate["corrected_pass"])
    validators_ok = bool(val["all_ok"])
    should_submit = canary_ok and stage2_ok and gate_ok and validators_ok
    assert bool(cur["submit_allowed"]) == should_submit, "label must follow the pre-registered verdict matrix"
    assert all(bool(v) for v in cur["gates"].values()) == should_submit
    if should_submit:
        assert cur["label"].startswith("OK TO DOWNLOAD AND SUBMIT")
        assert "CLEARED-UNDER-CORRECTED-GATE" in gate["verdict"]
        assert cur["note"].startswith("SUBMIT-CANDIDATE")
    else:
        assert cur["label"].startswith("RESEARCH-ONLY")
        assert cur["note"].startswith("RESEARCH-ONLY")


def test_session2_file_meets_the_official_format():
    cur = _load("docs/submissions/CURRENT.json")
    rasterio = pytest.importorskip("rasterio")
    if not SAMPLE.exists():
        pytest.skip("competition rasters not present")
    with rasterio.open(ROOT / cur["file"]) as s, rasterio.open(SAMPLE) as t:
        arr = s.read(1)
        assert s.count == 1 and s.dtypes[0] == "float32"
        assert s.crs.to_epsg() == 32611
        assert (s.height, s.width) == (t.height, t.width) == (3730, 3292)
        assert tuple(s.transform) == tuple(t.transform)
        assert s.res == (100.0, 100.0)
        assert s.nodata is not None and np.isnan(s.nodata)
        tmpl = t.read(1)
        # no NaN inside the scored region (the exact failure mode of the platform range error, IR-53-65)
        assert np.isfinite(arr[np.isfinite(tmpl)]).all()
        assert np.isnan(arr[~np.isfinite(tmpl)]).all()
        fin = arr[np.isfinite(arr)]
        assert float(fin.min()) >= 0.0 and float(fin.max()) <= 1.0
    val = _load("evidence/s2_validator_receipt.json")
    assert val["template_validate_submission_exit"] == 0
    assert val["all_ok"]


def test_uniqueness_gate_v2_receipt_is_complete_and_honest():
    gate = _load("evidence/uniqueness_gate_v2_session2.json")
    assert gate["registry_unique_on_grid"] >= 600
    assert gate["gate_rule"]["corrected_GD_1"].startswith("rho_surface_footprint")
    assert gate["final_dots"] > 0
    assert isinstance(gate["raw_flags_listed_for_transparency"], list)
    if gate["corrected_pass"]:
        assert gate["verdict"] == "CLEARED-UNDER-CORRECTED-GATE"
        assert gate["n_flagged_corrected"] == 0
    else:
        assert gate["verdict"] == "PROTOCOL DUPLICATE / STOP"
    for r in gate["top_by_rho_footprint"]:
        assert "rho_surface_footprint" in r and "rho_surface_whole_grid" in r
        assert "chance_coverage" in r and "lift_over_chance" in r


def test_holdout_receipt_labels_and_evaluator():
    s2 = _load("evidence/s2_c1_holdout.json")
    assert s2["label_type"].startswith("HOLDOUT-DTI")
    assert s2["evaluator"]["name"] == "gems53.core.dti"
    assert len(s2["c1_features"]) == 14
    sep = s2["canary_S2_E1"]["max_separability_per_feature"]
    assert len(sep) == 14
    assert s2["canary_S2_E1"]["max_over_all_features"] <= 0.90 or s2["canary_S2_E1"]["flag"] == "LEAK_SUSPECT"
    # baseline must be re-run in the same run (not copied from session 1)
    assert "baseline_same_run" in s2
    # no organizer-score claim anywhere
    txt = json.dumps(s2)
    assert "ORGANIZER-CONFIRMED" not in txt.replace("NOT organizer-scored", "")


def test_run_card_session2_exists_and_matches():
    card = _load("evidence/run_card_session2.json")
    cur = _load("docs/submissions/CURRENT.json")
    assert card["submission"]["name"] == cur["name"]
    assert card["submission"]["sha256_file"] == cur["sha256"]
    assert card["submission"]["organizer_score"] is None
    assert card["submission"]["submitted"] is False
    assert card["verdict"] in ("promote", "negative")
    if card["verdict"] == "promote":
        assert cur["submit_allowed"] is True
    else:
        assert cur["submit_allowed"] is False


def test_site_shows_the_label_and_download_up_front():
    idx = (ROOT / "docs/index.html").read_text()
    cur = _load("docs/submissions/CURRENT.json")
    assert cur["label"].upper() in idx.upper()
    assert Path(cur["file"]).name in idx
    assert cur["name"] in idx
    assert "Download" in idx
    # executive summary must explain how to submit
    assert "How to submit" in idx
    sub = (ROOT / "docs/submission.html").read_text()
    assert cur["label"].upper() in sub.upper()
