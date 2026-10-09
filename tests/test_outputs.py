"""Re-check of the shipped submission and of the published outputs (the 'third pass' of the review).

Checks that the label, the receipts (X6 build + X9 verification), the run card, the site and the bytes on
disk all agree, and that BOTH shipped GeoTIFFs meet their container contracts:
  primary (…-zeros.tif)       every pixel finite in [0,1]; 0 outside the footprint; nodata None
                              (the portal-safe container, IR-53-65; organiser-scored zeros pattern)
  twin   (…-nan-outside.tif)  NaN exactly outside the template footprint; nodata nan (template-conformant)
Format checks against the official sample run only when the competition rasters are present
(scripts/fetch_data.py); otherwise they are skipped with a reason.
"""
import hashlib
import json
import re
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


def _verify():
    cur = _load("docs/submissions/CURRENT.json")
    rec = _load(cur["receipt"])
    x9 = _load(cur["verify_receipt"]) if cur.get("verify_receipt") else None
    return cur, rec, x9


def test_current_pointer_matches_receipt_and_file():
    cur, rec, x9 = _verify()
    final_label = x9["final_label"] if x9 else rec["label"]
    assert cur["label"] == final_label
    assert cur["note"] == rec["note"]
    assert len(cur["note"]) <= 140
    tif = ROOT / cur["file"]
    assert tif.exists(), tif
    assert _sha(tif) == cur["sha256"] == rec["files"]["primary_zeros"]["sha256"]
    twin = ROOT / cur["twin_file"]
    assert twin.exists(), twin
    assert _sha(twin) == cur["twin_sha256"] == rec["files"]["twin_nan_outside"]["sha256"]
    assert cur["submitted"] is False and cur["organizer_score"] is None


def test_label_follows_the_pre_registered_rule():
    cur, rec, x9 = _verify()
    g = cur["gates"]
    all_pass = all(bool(v) for v in g.values())
    if cur["label"].startswith("OK"):
        assert all_pass, "a label cannot read OK to submit while a gate fails"
    else:
        assert cur["label"].startswith("DO NOT SUBMIT")
        assert not all_pass, "DO NOT SUBMIT must have at least one failing gate"


def test_run_card_and_site_agree_with_the_label():
    cur, rec, x9 = _verify()
    card = _load("evidence/run_card.json")
    expected_verdict = "promote" if cur["label"].startswith("OK") else "negative"
    assert card["verdict"] == expected_verdict
    assert card["submission_name"] == cur["name"]
    assert card["note_max_140_chars"] == cur["note"] and card["note_length"] <= 140
    assert card["raster"]["sha256"] == cur["sha256"]
    assert card["raster"]["pixel_sha256"] == cur["pixel_sha256"]
    assert card["raster"]["dots"] == rec["emission"]["dots"]
    idx = (ROOT / "docs/index.html").read_text()
    sub = (ROOT / "docs/submission.html").read_text()
    assert cur["label"].upper() in idx.upper()
    assert cur["label"].upper() in sub.upper()
    assert cur["name"] in idx
    assert Path(cur["file"]).name in idx


def test_primary_file_meets_the_portal_safe_contract():
    """Primary = zeros-outside container: finite in [0,1] everywhere (IR-53-65)."""
    cur, rec, _ = _verify()
    rasterio = pytest.importorskip("rasterio")
    if not SAMPLE.exists():
        pytest.skip("competition rasters not present (run scripts/fetch_data.py)")
    with rasterio.open(ROOT / cur["file"]) as s, rasterio.open(SAMPLE) as t:
        arr = s.read(1)
        assert s.count == 1 and s.dtypes[0] == "float32"
        assert s.crs.to_epsg() == 32611
        assert (s.height, s.width) == (t.height, t.width) == (3730, 3292)
        assert tuple(s.transform) == tuple(t.transform)
        assert s.res == (100.0, 100.0)
        assert np.isfinite(arr).all(), "primary must contain no NaN anywhere (portal range check)"
        assert float(arr.min()) >= 0.0 and float(arr.max()) <= 1.0
        assert int(np.count_nonzero(arr)) == rec["emission"]["dots"]
        tmpl = t.read(1)
        fp = np.isfinite(tmpl)
        assert (arr[~fp] == 0).all(), "primary is 0 outside the footprint"
        assert (arr[fp] >= 0).all() and (arr[fp] <= 1).all()


def test_twin_file_is_template_conformant():
    """Twin = NaN exactly outside the template footprint, nodata nan (matches sample_submission)."""
    cur, rec, _ = _verify()
    rasterio = pytest.importorskip("rasterio")
    if not SAMPLE.exists():
        pytest.skip("competition rasters not present (run scripts/fetch_data.py)")
    with rasterio.open(ROOT / cur["twin_file"]) as s, rasterio.open(SAMPLE) as t:
        arr = s.read(1)
        assert s.nodata is not None and np.isnan(s.nodata)
        tmpl = t.read(1)
        assert np.array_equal(np.isfinite(arr), np.isfinite(tmpl)), "NaN must be exactly outside the template footprint"
        assert float(np.nanmin(arr)) >= 0.0 and float(np.nanmax(arr)) <= 1.0
        assert int(np.count_nonzero(np.nan_to_num(arr))) == rec["emission"]["dots"]


def test_emission_prune_and_spacing():
    cur, rec, _ = _verify()
    e = rec["emission"]
    assert e["prune_check"]["dots_on_catalogue"] == 0
    assert e["prune_check"]["dots_within_2px_of_catalogue"] == 0
    assert e["prune_check"]["min_dist_dot_to_catalogue_px"] > 2.0
    assert e["spacing"]["min_nearest_dot_px"] >= 2.8 - 1e-9


def test_every_irregularity_reference_resolves():
    ids = {i["id"] for i in _load("registry/irregularities.json")["items"]}
    refs = set()
    for f in list((ROOT / "docs").rglob("*.md")) + list((ROOT / "docs").glob("*.html")) + \
            list((ROOT / "scripts").glob("*.py")) + [ROOT / "README.md"]:
        refs |= set(re.findall(r"IR-53-\d\d", f.read_text(errors="ignore")))
    assert not sorted(r for r in refs if r not in ids), "dangling IR references"


def test_every_limitation_reference_resolves():
    ids = {i["id"] for i in _load("registry/limitations.json")["items"]}
    refs = set()
    for f in list((ROOT / "docs").rglob("*.md")) + list((ROOT / "docs").glob("*.html")) + [ROOT / "README.md"]:
        refs |= set(re.findall(r"L-\d\d", f.read_text(errors="ignore")))
    assert not sorted(r for r in refs if r not in ids), "dangling L references"
