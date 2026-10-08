"""Publication regressions for archived H55 claims under the current H56 site state."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import make_h55_page, publish_site_r3, verify_h55

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/data"
EVIDENCE = ROOT / "evidence"
H55_STEM = "gems52-h55-btherm-greedy-37654px-20261007T0150Z-zeros"
H55_TAG = "20261007T0150Z"


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _h55_archive() -> dict:
    return _json(EVIDENCE / f"submission_{H55_STEM}.json")


def _h55_verification() -> dict:
    return _json(EVIDENCE / f"h55_verification_{H55_TAG}.json")


def _h55_sweep() -> dict:
    return _json(EVIDENCE / "h55_sweep_hardcore.json")


def test_h55_archive_a_only_prose_matches_receipt_and_reports_mixed_means() -> None:
    page = (ROOT / "docs/h55.html").read_text()
    summary = verify_h55.a_only_promotion_summary()
    sweep = _h55_sweep()

    def mean(mode: str, arm: str, emitter: str) -> float:
        row = next(r for r in sweep[mode]["summary"]["ranked"]
                   if r["arm"] == arm and r["emitter"] == emitter)
        return float(row["mean_dti"])

    assert f"{mean('hide', 'A_only', 'hc4|37654'):.5f} vs 0.03948" in page
    assert f"{mean('tip', 'A_only', 'hc4|37654'):.5f} vs 0.02477" in page
    assert "below matched random on <code>hide</code>" in page
    assert "above matched random on <code>tip</code>" in page
    assert "wins 1/4" in page and "2/4" in page
    assert "failing the required &ge;3/4 wins on each instrument" in page
    assert "below matched random on both" not in page
    assert "0.02979 vs matched random 0.03948 on hide" in summary
    assert "0.02894 vs 0.02477 on tip" in summary
    assert "1/4 and 2/4" in summary and "does not pass" in summary


def test_h55_verification_keeps_a_only_gate_separate_from_independence() -> None:
    verification = _h55_verification()
    assert verification["tag"] == H55_TAG
    assert verification["all_ok"] is True
    assert "above on tip (0.02894 vs 0.02477)" in verification["review_note"]
    assert "1/4 and 2/4 fold wins" in verification["review_note"]
    assert "These are separate findings" in verification["union_audit"]["verdict"]
    assert "below matched random on both" not in verification["union_audit"]["verdict"]


def test_h55_archive_review_is_idempotent_and_carries_h56_status(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(publish_site_r3, "DOCS", tmp_path)
    page = tmp_path / "irregularities.html"
    page.write_text(
        '<main id="main"><li><strong>No radiometric bands in the available stack.</strong> '
        'No invented data layers, LiDAR-only hidden-label claims or local microseismic locations.</li>'
        '<li><strong>Geophysical view is weaker here.</strong> Low negative-error correlation did not make co-training win. '
        'Strong surface-only control prevented a false promotion.</li><h2>Next session, in order</h2></main>'
    )

    publish_site_r3.insert_h55_review(
        _h55_archive(), _h55_verification(), _h55_sweep(), _json(DATA / "submission.json")
    )
    publish_site_r3.insert_h55_review(
        _h55_archive(), _h55_verification(), _h55_sweep(), _json(DATA / "submission.json")
    )
    result = page.read_text()

    assert result.count("<!--H55-ARCHIVE-REVIEW-->") == 1
    assert "Historical H55 evidence review" in result
    assert "H55 is superseded" in result
    current = _json(DATA / "submission.json")
    assert current["file"] in result
    # The status block must name the round that is actually current and link to *its* audit page.
    # It used to assert a hard-coded "synthetic methodology demo" and an h56-cotrain.html link, which
    # silently went stale when a later round became current.
    assert f"current {str(current.get('round') or 'H56').upper()} status" in result, (
        "the H55 archive review must name the current round, read from the receipt")
    round_pages = {"H59": "h59.html", "H58": "h58.html", "H57": "h57.html"}
    expected_href = round_pages.get(str(current.get("round") or "").upper(), "h56-cotrain.html")
    assert f'href="{expected_href}"' in result
    # case-insensitive: which sentence casing the status block uses depends on which branch the
    # current round's receipt selects, and the instruction itself is what must be present
    assert "weekly-slot gate" in result
    assert "do not upload or spend a slot" in result.casefold()
    assert "0.02979" in result and "0.02894" in result
    assert "below random on hide and above random on tip" in result
    assert "H55-JUNCTION remains untested" in result
    assert "No radiometric bands in the available stack" not in result
    assert "Historical R2 next-session plan" in result


def test_r3_remains_a_separate_research_only_result() -> None:
    receipt = _json(DATA / "submission_r3.json")
    page = (ROOT / "docs/r3.html").read_text()

    assert receipt["approved_for_weekly_slot"] is False
    assert receipt["weekly_submission_slots_used"] == 0
    assert "Result: local gate failed; no weekly-slot approval" in page
    assert "published only as a research artifact" in page
    assert "NOT APPROVED FOR UPLOAD" in page


def test_legacy_h55_renderer_cannot_replace_the_current_h56_pages(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(make_h55_page, "DOCS", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data/submission.json").write_text(json.dumps({
        "file": "gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif",
        "approved_for_weekly_slot": False,
    }))
    (tmp_path / "index.html").write_text("H56 home and download bar")
    (tmp_path / "h55.html").write_text("H55 historical archive snapshot")

    assert make_h55_page.main() == 0
    assert (tmp_path / "index.html").read_text() == "H56 home and download bar"
    assert (tmp_path / "h55.html").read_text() == "H55 historical archive snapshot"
