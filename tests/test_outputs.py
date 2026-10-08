"""Re-check of the shipped submission and of the published outputs (the 'third pass' of the review).

Checks that the label, the receipt, the run card, the site and the bytes on disk all agree, and that the
GeoTIFF meets the format rules on the bytes that will be shipped. Format checks against the official sample
run only when the competition rasters are present (scripts/fetch_data.py); otherwise they are skipped with a reason.
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


def test_current_pointer_matches_receipt_and_file():
    cur = _load("docs/submissions/CURRENT.json")
    rec = _load(cur["receipt"])
    assert cur["label"] == rec["label"]
    assert cur["note"] == rec["note"]
    assert len(cur["note"]) <= 140
    tif = ROOT / cur["file"]
    assert tif.exists(), tif
    assert _sha(tif) == cur["sha256"] == rec["sha256"]
    assert cur["submitted"] is False and cur["organizer_score"] is None


def test_label_follows_the_pre_registered_rule():
    cur = _load("docs/submissions/CURRENT.json")
    g = cur["gates"]
    all_pass = all(bool(v) for v in g.values())
    if cur["label"].startswith("Validated"):
        assert all_pass, "a label cannot read OK to submit while a gate fails"
    else:
        assert cur["label"].startswith("Research-only")
        assert not all_pass, "research-only must have at least one failing gate"


def test_run_card_and_site_agree_with_the_label():
    cur = _load("docs/submissions/CURRENT.json")
    card = _load("evidence/run_card.json")
    assert card["label"] == cur["label"] == card["verdict"]
    assert card["submission"]["submitted"] is False
    assert card["submission"]["submission_slot_used"] is False
    assert card["organizer_score"] is None
    idx = (ROOT / "docs/index.html").read_text()
    sub = (ROOT / "docs/submission.html").read_text()
    assert cur["label"].upper() in idx.upper()
    assert cur["label"].upper() in sub.upper()
    assert cur["name"] in idx
    assert Path(cur["file"]).name in idx


def test_submitted_file_meets_the_format_rules():
    cur = _load("docs/submissions/CURRENT.json")
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
        assert s.nodata is not None and np.isnan(s.nodata)
        tmpl = t.read(1)
        assert np.array_equal(np.isfinite(arr), np.isfinite(tmpl)), "NaN must be exactly outside the template footprint"
        assert float(np.nanmin(arr)) >= 0.0 and float(np.nanmax(arr)) <= 1.0
        rec = _load(cur["receipt"])
        assert int(np.count_nonzero(np.nan_to_num(arr))) == rec["final_dots"]


def test_every_irregularity_reference_resolves():
    ids = {i["id"] for i in _load("registry/irregularities.json")["items"]}
    refs = set()
    for f in list((ROOT / "docs").rglob("*.md")) + list((ROOT / "docs").glob("*.html")) + \
            list((ROOT / "scripts").glob("*.py")) + [ROOT / "README.md"]:
        refs |= set(re.findall(r"IR-53-\d\d", f.read_text(errors="ignore")))
    assert not sorted(r for r in refs if r not in ids), "dangling IR references"
