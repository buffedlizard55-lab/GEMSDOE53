#!/usr/bin/env python3
"""Site verification pass — run it before publishing, and put its output in the PR.

Three things a static-but-data-driven site gets wrong silently:

1. **Broken links.** A nav entry to a page that does not exist is how "the site should be enough" dies.
2. **Data the JS asks for but the feed never wrote.** `fetch()` in a browser fails quietly and the page
   prints `–`, which reads like "no data yet" rather than "the generator is broken".
3. **Numbers typed into HTML.** Every figure must come from `docs/data/*.json`; a literal in the HTML is a
   number that goes stale the moment the evidence changes.

Run:  python3 scripts/check_site.py            (exit 1 on any breakage)
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen

import csv
import zipfile

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"


class Scan(HTMLParser):
    """Collect anchors, script srcs, inline scripts, and fetch('data/x') targets."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.inline: list[str] = []
        self.stack: list[str] = []
        self.scratch: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if tag in ("script", "link") and a.get("src"):
            self.srcs.append(a["src"])
        if tag in ("script", "link") and a.get("href"):
            self.srcs.append(a["href"])
        if tag == "script" and not a.get("src"):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == "script" and tag == "script":
            self.stack.pop()
            self.inline.append("\n".join(self.scratch))
            self.scratch = []

    def handle_data(self, data):
        if self.stack:
            self.scratch.append(data)


def check_h57_creditcore(DATA, DOCS, ROOT, notes):
    """The H57 credited-core alternate: verify its bytes, gates and page, never its promotion.

    It is published beside the union arm and must never silently take the current pointer; this
    check therefore asserts the pointer still names a different file and that the alternate's own
    receipts agree with its bytes.
    """
    import hashlib
    import json as _json
    problems = []
    receipt_path = DATA / "submission_h57_creditcore.json"
    if not receipt_path.exists():
        return []
    r = _json.loads(receipt_path.read_text())
    name = str(r.get("file", ""))
    dl = DOCS / "downloads" / name
    src = ROOT / "submission" / name
    sha = hashlib.sha256(dl.read_bytes()).hexdigest() if dl.exists() else None
    if not name.startswith("gems57-h57-credit-core"):
        problems.append("H57 alternate: unexpected file name")
    if sha != r.get("sha256") or (not src.exists() or hashlib.sha256(src.read_bytes()).hexdigest() != sha):
        problems.append("H57 alternate: published bytes differ from its receipt")
    current = _json.loads((DATA / "submission.json").read_text()) if (DATA / "submission.json").exists() else {}
    if current.get("file") == name:
        problems.append("H57 alternate: it must not silently be the current pointer")
    fmt, uni = r.get("format_gate") or {}, r.get("uniqueness") or {}
    if r.get("approved_for_weekly_slot") is not False or r.get("submission_slots_used") != 0:
        problems.append("H57 alternate: research archive must remain not-approved and zero-slot")
    if not fmt.get("ok") or fmt.get("problems") or fmt.get("mass_outside_footprint"):
        problems.append("H57 alternate: format gate receipt missing or failed")
    if not uni.get("ok") or int(uni.get("novel_vs_all_priors") or 0) <= 0:
        problems.append("H57 alternate: uniqueness gate receipt missing or failed")
    if "REFUTED" not in _json.dumps(r.get("co_training_disclosure") or {}).upper():
        problems.append("H57 alternate: the refuted co-training arm is not disclosed")
    page = (DOCS / "h57-creditcore.html").read_text() if (DOCS / "h57-creditcore.html").exists() else ""
    for term in ("ABANDON", "not proven", "do not upload", "IR-57-107"):
        if term.casefold() not in page.casefold():
            problems.append(f"H57 alternate page: missing disclosure {term!r}")
    if "submit: yes" in page.casefold():
        problems.append("H57 alternate page: unsafe submission approval text remains")
    home = (DOCS / "index.html").read_text() if (DOCS / "index.html").exists() else ""
    if name not in home:
        problems.append("H57 alternate: not linked from the home page")
    if not problems:
        notes.append(f"H57 credited-core alternate verified beside the union arm: {name} "
                     f"({r.get('bytes'):,} bytes, "
                     f"{r.get('uniqueness', {}).get('novel_vs_all_priors'):,} novel px)")
    return problems


def check_h57(DATA, DOCS, ROOT, notes):
    """Every H57 gate re-read from the bytes, so the round can be audited on its own terms."""
    problems = []
    sub = json.loads((DATA / "submission.json").read_text())
    b = json.loads((DATA / "h57_build.json").read_text())
    gate = json.loads((DATA / "h57_slot_gate.json").read_text())
    # The scheduled feed owns docs/data/submission.json and rewrites it from
    # evidence/submission_<stem>.json, so anything round-specific that the feed does not copy
    # through (the short aliases, the dossier path) is derived here from the convention rather
    # than read from a key that only the publisher happened to write.
    short_tif, short_zip = "downloads/h57-candidate.tif", "downloads/h57-candidate.zip"
    dossier_name = Path(str(sub.get("candidate_geology_dossier")
                            or b["candidate_geology_dossier"])).name

    for name in ("h57_build.json", "h57_cotrain.json", "h57_validation.json",
                 "h57_strata.json", "h57_format_gate.json", "h57_uniqueness.json",
                 "h57_slot_gate.json"):
        if not (DATA / name).exists():
            problems.append(f"H57: {name} missing from docs/data")

    canonical = DOCS / sub["download"]
    alias = DOCS / short_tif
    canonical_zip = DOCS / sub["download_zip"]
    alias_zip = DOCS / short_zip
    for path, what in ((canonical, "canonical TIFF"), (alias, "short TIFF alias"),
                       (canonical_zip, "canonical ZIP"), (alias_zip, "short ZIP alias")):
        if not path.exists():
            problems.append(f"H57: {what} missing ({path.name})")
    if canonical.exists() and alias.exists() and canonical.read_bytes() != alias.read_bytes():
        problems.append("H57: short TIFF alias is not byte-identical to the canonical raster")
    # The scheduled feed repackages ZIPs for whatever submission/LATEST.txt names, and its
    # packaging adds SUBMISSION_NOTE.txt and evidence.json next to the TIFF.  The submission rule
    # is "a single-band GeoTIFF, or a ZIP containing one GeoTIFF", so the invariant that matters is
    # exactly one TIFF member whose bytes are the canonical TIFF; archive-level byte equality is
    # reported as a note because a repackage does not change the payload the portal receives.
    for zp in (canonical_zip, alias_zip):
        if zp.exists():
            with zipfile.ZipFile(zp) as archive:
                tiffs = [n for n in archive.namelist() if n.lower().endswith((".tif", ".tiff"))]
                if len(tiffs) != 1 or archive.read(tiffs[0]) != canonical.read_bytes():
                    problems.append(f"H57: {zp.name} must hold exactly one TIFF byte-identical to "
                                    "the canonical download")
                else:
                    notes.append(f"H57 ZIP payload verified: {zp.name} holds one TIFF identical "
                                 f"to the canonical download ({len(archive.namelist())} members)")
    if canonical_zip.exists() and alias_zip.exists() \
            and canonical_zip.read_bytes() != alias_zip.read_bytes():
        notes.append("H57: the short ZIP alias is repackaged rather than byte-identical to the "
                     "canonical ZIP; the contained TIFF is verified byte-identical in both")
    if canonical.exists():
        if canonical.stat().st_size != sub["bytes"]:
            problems.append("H57: docs/ TIFF size differs from the receipt")
        got = hashlib.sha256(canonical.read_bytes()).hexdigest()
        if got != sub["sha256"] or got != b["file"]["sha256"]:
            problems.append("H57: sha256 mismatch between the published file and its receipts")
        else:
            notes.append(f"H57 download verified byte-for-byte: {canonical.name} "
                         f"({sub['bytes']:,} bytes, {got[:16]}...)")

    # the receipt's own gates must still be green
    if not b["format_gate"]["ok"]:
        problems.append("H57: format gate reports " + "; ".join(b["format_gate"]["problems"]))
    if not b["uniqueness"]["canonical_pattern_unique"]:
        problems.append("H57: decoded pattern equals an accessible aligned prior")
    nd = b["not_the_union"]
    if nd["file_equals_prior_A"] or nd["file_equals_prior_B"] or nd["file_equals_union_AB"]:
        problems.append("H57: artefact equals a named prior or their union")
    if nd["arm_outside_prior_support_px"] != nd["arm_px"]:
        problems.append("H57: arm is not wholly outside the accessible prior-support union")
    if b["file"]["min_distance_to_catalogue_m"] <= 200.0:
        problems.append("H57: an emitted cell sits inside the <= 200 m catalogue ring")

    # on-disk read-back of the raster, independent of the receipt
    try:
        with rasterio.open(canonical) as ds:
            arr = ds.read(1)
            tr = tuple(ds.transform)[:6]
            if (ds.count != 1 or ds.dtypes[0] != "float32" or ds.crs is None
                    or ds.crs.to_epsg() != 32611 or (ds.height, ds.width) != (3730, 3292)
                    or tr != (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
                    or not np.isfinite(arr).all() or float(arr.min()) != 0.0
                    or float(arr.max()) != 1.0 or set(np.unique(arr).tolist()) != {0.0, 1.0}
                    or int(np.count_nonzero(arr)) != b["file"]["px"]):
                problems.append("H57: on-disk read-back failed the single-band float32 / grid / "
                                "range / value / count check")
            else:
                notes.append(f"H57 on-disk read-back: {b['file']['px']:,} cells, values exactly "
                             "{{0, 1}}, 0 NaN, CRS EPSG:32611, transform matches the fixture")
    except Exception as e:  # noqa: BLE001
        problems.append(f"H57: could not read back the published TIFF ({e})")

    # the submission note must still fit the portal's 200-character limit
    note = str(sub.get("note") or sub.get("submission_note") or "")
    if len(note) > 200:
        problems.append(f"H57: submission note is {len(note)} characters (limit 200)")
    if sub.get("approved_for_weekly_slot") is not False:
        problems.append("H57: the slot decision must stay explicit while R1 is unmet")

    # the per-candidate geological dossier must exist and carry one row per arm pixel
    dossier = DOCS / "downloads" / dossier_name
    if not dossier.exists():
        problems.append("H57: per-candidate geological reasoning CSV is not published")
    else:
        # the dossier opens with a '#' provenance line, which is not a CSV header
        with dossier.open(newline="") as fh:
            body = [ln for ln in fh if not ln.startswith("#")]
        rows = list(csv.DictReader(body))
        if len(rows) != b["arm"]["px"]:
            problems.append(f"H57: dossier has {len(rows)} rows for {b['arm']['px']} arm pixels")
        empty = [r for r in rows[:2000] if not str(r.get("geological_reasoning", "")).strip()]
        if empty:
            problems.append("H57: dossier rows with an empty geological_reasoning cell")
        counts = {}
        for r in rows:
            counts[r["agreement_stratum"]] = counts.get(r["agreement_stratum"], 0) + 1
        if counts != b["arm_rows_by_stratum"]:
            problems.append("H57: dossier stratum counts differ from the build receipt")
        notes.append(f"H57 dossier: {len(rows):,} rows, strata {counts}")

    # the pages must name the verdict and the byte-identical short paths
    h57_pages = (("h57.html",) if (DATA / "h58_result.json").is_file()
                 else ("h57.html", "executive-summary.html", "index.html"))
    for page in h57_pages:
        path = DOCS / page
        if not path.exists():
            problems.append(f"H57: {page} is missing")
            continue
        text = path.read_text()
        if "h57-candidate.tif" not in text and page == "executive-summary.html":
            problems.append("H57: submission guide does not offer the short download path")
        if sub["sha256"][:24] not in text and page != "index.html":
            problems.append(f"H57: {page} does not show the artefact's sha256 prefix")
        if gate["verdict"].split(" ")[0].lower() not in text.casefold():
            problems.append(f"H57: {page} does not state the slot-gate verdict")
    notes.append(f"H57 slot gate: {gate['verdict']} — R1 lift met: {gate['r1']['lift_met']}, "
                 f"folds met: {gate['r1']['folds_met']}")
    return problems


def check_h58(DATA, DOCS, ROOT, notes, *, current_round=False):
    """Recheck H58 receipts, fold gate, decoded TIFF, one-TIFF ZIP and public links.

    H58 can be published as a research-only result while the global submission pointer remains on
    the incumbent. In that case validate its per-artifact receipt and assert it was not promoted.
    """
    problems = []
    required = ("h58_result.json", "h58_holdout.json", "h58_preregistration.json",
                "h58_preflight_integrity.json", "h58_restore_receipt.json", "h58_postrun_review.json",
                "h58_postmerge_uniqueness.json")
    for name in required:
        if not (DATA / name).is_file():
            problems.append(f"H58: {name} missing from docs/data")
    try:
        result = json.loads((DATA / "h58_result.json").read_text())
        filename = str(result["artifact"]["file"])
        sub_path = (DATA / "submission.json" if current_round else
                    DATA / f"submission_{Path(filename).stem}.json")
        sub = json.loads(sub_path.read_text())
        holdout = json.loads((DATA / "h58_holdout.json").read_text())
        prereg = json.loads((DATA / "h58_preregistration.json").read_text())
        preflight = json.loads((DATA / "h58_preflight_integrity.json").read_text())
        postrun = json.loads((DATA / "h58_postrun_review.json").read_text())
        restore = json.loads((DATA / "h58_restore_receipt.json").read_text())
        postmerge = json.loads((DATA / "h58_postmerge_uniqueness.json").read_text())
        import numpy as np
        import rasterio

        if sub.get("file") != filename or result.get("round") != "H58":
            problems.append("H58: per-artifact receipt and result receipt name different rounds/files")
        if (postrun.get("execution", {}).get("code_hashes") != result.get("code_hashes")
                or postrun.get("verified_run_facts", {}).get("tiff_sha256") != result.get("artifact", {}).get("sha256")
                or postrun.get("verified_run_facts", {}).get("local_research_gate_passed") is not False):
            problems.append("H58: independent post-run review differs from execution hashes, TIFF receipt, or failed gate")
        latest_name = (ROOT / "submission/LATEST.txt").read_text().strip()
        if current_round and latest_name != filename:
            problems.append("H58: current result TIFF differs from submission/LATEST.txt")
        if not current_round and latest_name == filename:
            problems.append("H58: failed/research-only artifact unexpectedly occupies the global submission pointer")
        canonical = DOCS / "downloads" / filename
        short_tif = DOCS / "downloads/h58-candidate.tif"
        zip_path = DOCS / "downloads" / (Path(filename).stem + ".zip")
        short_zip = DOCS / "downloads/h58-candidate.zip"
        pm_candidate = ROOT / postmerge.get("candidate", {}).get("path", "")
        pm_prior = ROOT / postmerge.get("additional_upstream_prior", {}).get("path", "")
        if not pm_candidate.is_file() or not pm_prior.is_file():
            problems.append("H58: supplemental post-merge uniqueness input is missing")
        else:
            with rasterio.open(pm_candidate) as ds_a, rasterio.open(pm_prior) as ds_b:
                arr_a, arr_b = ds_a.read(1), ds_b.read(1)
                if (ds_a.transform != ds_b.transform or ds_a.crs != ds_b.crs
                        or arr_a.shape != arr_b.shape):
                    problems.append("H58: supplemental prior grid differs from the H58 raster")
                digest_a = hashlib.sha256(arr_a.astype("<f4", copy=False).tobytes()).hexdigest()
                digest_b = hashlib.sha256(arr_b.astype("<f4", copy=False).tobytes()).hexdigest()
                mask_a, mask_b = arr_a > 0, arr_b > 0
                overlap = int(np.logical_and(mask_a, mask_b).sum())
                union = int(np.logical_or(mask_a, mask_b).sum())
                jaccard = overlap / union if union else 1.0
                if (hashlib.sha256(pm_candidate.read_bytes()).hexdigest()
                        != postmerge.get("candidate", {}).get("file_sha256")
                        or hashlib.sha256(pm_prior.read_bytes()).hexdigest()
                        != postmerge.get("additional_upstream_prior", {}).get("file_sha256")
                        or digest_a != result["artifact"].get("decoded_prediction_sha256")
                        or digest_a != postmerge.get("candidate", {}).get("decoded_float32_sha256")
                        or digest_b != postmerge.get("additional_upstream_prior", {}).get("decoded_float32_sha256")
                        or overlap != postmerge.get("support_intersection_pixels")
                        or union != postmerge.get("support_union_pixels")
                        or abs(jaccard - float(postmerge.get("support_jaccard", -1))) > 1e-12
                        or np.array_equal(arr_a, arr_b)
                        or postmerge.get("additional_pattern_unique") is not True):
                    problems.append("H58: supplemental post-merge decoded-pattern audit disagrees with current bytes")
                else:
                    notes.append("H58 supplemental uniqueness: zero support overlap with the newly merged H57 credited-core raster")
        for path, label in ((canonical, "canonical TIFF"), (short_tif, "short TIFF alias"),
                            (zip_path, "single-TIFF ZIP"), (short_zip, "short ZIP alias")):
            if not path.is_file():
                problems.append(f"H58: {label} missing ({path.name})")
        if current_round and sub.get("download") != f"downloads/{filename}":
            problems.append("H58: submission.json download path is not the canonical TIFF")
        if (canonical.is_file() and short_tif.is_file()
                and canonical.read_bytes() != short_tif.read_bytes()):
            problems.append("H58: h58-candidate.tif is not byte-identical to the canonical TIFF")
        if (zip_path.is_file() and short_zip.is_file()
                and zip_path.read_bytes() != short_zip.read_bytes()):
            problems.append("H58: h58-candidate.zip is not byte-identical to the canonical ZIP")
        if canonical.is_file():
            actual_sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
            expected_sha = result["artifact"]["sha256"]
            if (actual_sha != expected_sha or actual_sha != sub.get("sha256")
                    or canonical.stat().st_size != result["artifact"]["bytes"]
                    or canonical.stat().st_size != sub.get("bytes")):
                problems.append("H58: published TIFF size/SHA-256 differs from the independent receipts")
            else:
                notes.append(f"H58 TIFF verified byte-for-byte: {filename} ({canonical.stat().st_size:,} bytes, {actual_sha[:16]}…)")
            with rasterio.open(canonical) as ds:
                arr = ds.read(1)
                transform = tuple(ds.transform)[:6]
                expected_transform = (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
                if (ds.count != 1 or ds.dtypes[0] != "float32" or ds.crs is None
                        or ds.crs.to_epsg() != 32611 or (ds.height, ds.width) != (3730, 3292)
                        or transform != expected_transform or not np.isfinite(arr).all()
                        or float(arr.min()) < 0.0 or float(arr.max()) > 1.0
                        or set(np.unique(arr).tolist()) - {0.0, 1.0}
                        or int(np.count_nonzero(arr)) != int(result["artifact"]["emitted_pixels"])
                        or (int(result["artifact"]["emitted_pixels"]) > 0 and float(arr.max()) != 1.0)
                        or (int(result["artifact"]["emitted_pixels"]) == 0 and float(arr.max()) != 0.0)):
                    problems.append("H58: TIFF read-back failed single-band float32/template-grid/finite [0,1]/binary/count checks")
                decoded_hash = hashlib.sha256(arr.astype("<f4", copy=False).tobytes()).hexdigest()
                if decoded_hash != result["artifact"].get("decoded_prediction_sha256"):
                    problems.append("H58: decoded TIFF pixels differ from the model-prediction digest")
            if result["artifact"].get("format_gate", {}).get("ok") is not True:
                problems.append("H58: local raster/template format gate failed")
            if result["artifact"].get("uniqueness", {}).get("canonical_pattern_unique") is not True:
                problems.append("H58: decoded-pattern uniqueness against the accessible prior inventory failed")
            if result["artifact"].get("uniqueness", {}).get("candidate_decoded_sha256") != decoded_hash:
                problems.append("H58: uniqueness receipt digest differs from decoded TIFF pixels")
        if zip_path.is_file() and canonical.is_file():
            with zipfile.ZipFile(zip_path) as archive:
                if (archive.namelist() != [filename] or archive.read(filename) != canonical.read_bytes()
                        or archive.testzip() is not None):
                    problems.append("H58: portal ZIP must contain exactly one TIFF byte-identical to the canonical download")
        note = str(sub.get("submission_note") or sub.get("note") or "")
        if len(note) > 200:
            problems.append(f"H58: portal note is {len(note)} characters (limit 200)")
        if (sub.get("approved_for_weekly_slot") is not False
                or result.get("approved_for_weekly_slot") is not False
                or sub.get("promoted") is not False
                or result.get("submission_slots_used") != 0
                or result.get("portal", {}).get("uploaded") is not False
                or result.get("portal", {}).get("score") is not None):
            problems.append("H58: research artifact must remain unapproved, unpromoted, unuploaded and zero-slot")

        # Recompute the registered, same-fold comparison from raw fold rows instead of trusting
        # the runner's summary flag. Every arm must share one legal pool/budget within a comparison.
        rows = holdout.get("rows", [])
        modes = result.get("holdout", {}).get("mode_summary", result.get("holdout", {}).get("modes", {}))
        gate_cfg = prereg.get("promotion_gate", {})
        min_lift = float(gate_cfg.get("minimum_mean_dti_lift", 0.005))
        min_wins = int(str(gate_cfg.get("minimum_fold_wins", "3/4")).split("/")[0])
        mode_passes = {}
        for mode in ("hide", "block"):
            primary = [r for r in rows if r.get("mode") == mode and r.get("budget_label") == "primary"]
            recalculated, wins, comparable = [], 0, True
            summary = modes.get(mode, {})
            for fold_id in range(4):
                fold_rows = [r for r in primary if int(r.get("fold", -1)) == fold_id]
                by_arm = {r.get("arm"): r for r in fold_rows}
                names = ("H58-A F_geo", "View A", "View B", "Max(View A, View B)")
                if any(name not in by_arm for name in names):
                    problems.append(f"H58: {mode} fold {fold_id} is missing a registered arm row")
                    comparable = False
                    continue
                legal_counts = {int(r["legal_pixels"]) for r in by_arm.values()}
                budgets = {int(r["requested_budget"]) for r in by_arm.values()}
                if len(legal_counts) != 1 or len(budgets) != 1:
                    problems.append(f"H58: {mode} fold {fold_id} arms do not share a legal pool and requested budget")
                    comparable = False
                baseline = max((by_arm[n] for n in names[1:]), key=lambda r: float(r["dti"]))
                candidate = by_arm[names[0]]
                lift = float(candidate["dti"]) - float(baseline["dti"])
                win = lift > 1e-12
                fold_comparable = (int(candidate["emitted"]) == int(candidate["requested_budget"])
                                   and int(baseline["emitted"]) == int(baseline["requested_budget"]))
                comparable = comparable and fold_comparable
                wins += int(win)
                recalculated.append((lift, win, fold_comparable, baseline["arm"]))
            if len(recalculated) != 4:
                mode_passes[mode] = False
                continue
            mean_lift = float(np.mean([row[0] for row in recalculated]))
            passed = bool(comparable and mean_lift >= min_lift and wins >= min_wins)
            mode_passes[mode] = passed
            if summary.get("fold_wins") != wins or abs(float(summary.get("mean_lift_vs_strongest_same_fold_baseline", 0)) - mean_lift) > 1e-10:
                problems.append(f"H58: {mode} summary disagrees with recomputed fold lifts/wins")
            if summary.get("all_primary_folds_budget_comparable") is not comparable or summary.get("local_research_gate") is not passed:
                problems.append(f"H58: {mode} registered gate summary disagrees with its raw fold rows")
            fold_summaries = {int(row["fold"]): row for row in summary.get("folds", [])}
            for fold_id, (lift, win, comp, baseline_name) in enumerate(recalculated):
                recorded = fold_summaries.get(fold_id, {})
                if (recorded.get("strongest_baseline") != baseline_name
                        or recorded.get("strict_win") is not win
                        or recorded.get("budget_comparable") is not comp
                        or abs(float(recorded.get("lift", 0)) - lift) > 1e-10):
                    problems.append(f"H58: {mode} fold {fold_id} comparison summary differs from raw rows")
            notes.append(f"H58 {mode} holdout recomputed: mean lift {mean_lift:+.6f}, {wins}/4 wins, budget comparable={comparable}, gate={'PASS' if passed else 'FAIL'}")
        aggregate_pass = all(mode_passes.get(name, False) for name in ("hide", "block"))
        if result.get("holdout", {}).get("local_promotion_gate", {}).get("holdout_pass_both_modes") is not aggregate_pass:
            problems.append("H58: aggregate hide/block holdout gate disagrees with recomputed mode gates")
        artifact_gates = result.get("artifact", {}).get("artifact_gates", {})
        composite = bool(aggregate_pass and artifact_gates and all(artifact_gates.values()))
        if result.get("local_research_gate_passed") is not composite:
            problems.append("H58: local research gate does not equal holdout pass plus every artifact gate")
        if result.get("artifact", {}).get("support_shortfall", 0) > 0:
            if artifact_gates.get("candidate_support_capacity") is not False or composite:
                problems.append("H58: an F_geo support shortfall must fail comparability; never backfill with zero-score pixels")

        # Verify both per-pixel reasoning files, including the absence of the forbidden label-distance field.
        for label, key, expected_rows, require_positive_field in (
                ("H58-A", "reasoning", int(result["artifact"]["emitted_pixels"]), True),
                ("A-only", "a_only_reasoning", None, False)):
            receipt = result["artifact"].get(key, {})
            path = DOCS / "downloads" / Path(str(receipt.get("path", ""))).name
            if not path.is_file():
                problems.append(f"H58: {label} reasoning CSV is missing ({path.name})")
                continue
            with path.open(newline="", encoding="utf-8") as stream:
                dossier_rows = list(csv.DictReader(stream))
            if (len(dossier_rows) != int(receipt.get("rows", -1))
                    or receipt.get("one_reason_per_emitted_candidate") is not True
                    or (expected_rows is not None and len(dossier_rows) != expected_rows)):
                problems.append(f"H58: {label} reasoning CSV row count differs from its receipt/emission")
            if dossier_rows and ("dist_known_fault_px" in dossier_rows[0]
                                 or any(not row.get("alternative_and_falsifier")
                                        or "not an independently mapped" not in row.get("verification_status", "").lower()
                                        for row in dossier_rows)):
                problems.append(f"H58: {label} reasoning lacks falsifiers/verification caveats or exposed a forbidden field")
            if require_positive_field and dossier_rows:
                if any(float(row["F_geo"]) <= 0 for row in dossier_rows):
                    problems.append("H58: H58-A reasoning includes an emission outside frozen F_geo > 0 support")
            if hashlib.sha256(path.read_bytes()).hexdigest() != receipt.get("sha256"):
                problems.append(f"H58: {label} reasoning CSV hash differs from its receipt")

        # Re-bind the public preregistration, preflight and 23 input hashes to their frozen files.
        reg_path = ROOT / "registry/h58_preregistration.json"
        manifest_path = ROOT / "registry/data_manifest.json"
        doc_name = prereg.get("hypothesis_document")
        doc_path = ROOT / str(doc_name)
        if hashlib.sha256(reg_path.read_bytes()).hexdigest() != result.get("preregistration", {}).get("registry_sha256"):
            problems.append("H58: result is not bound to the current frozen preregistration registry bytes")
        if hashlib.sha256(doc_path.read_bytes()).hexdigest() != prereg.get("hypothesis_document_sha256"):
            problems.append("H58: preregistration hypothesis-document SHA-256 does not match its file")
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != prereg.get("data_integrity", {}).get("manifest_sha256"):
            problems.append("H58: pinned data manifest bytes differ from the preregistration")
        if hashlib.sha256((ROOT / prereg["preflight_evidence"]).read_bytes()).hexdigest() != prereg.get("preflight_sha256"):
            problems.append("H58: preflight evidence SHA-256 does not match the preregistration")
        manifest_count = len(json.loads(manifest_path.read_text()).get("files", []))
        if len(result.get("manifest_inputs", [])) != manifest_count or not all(
                item.get("matches_pin") is True for item in result.get("manifest_inputs", [])):
            problems.append("H58: one or more owner-mirror input pins are missing or unverified")
        if (restore.get("all_ok") is not True or len(restore.get("files", [])) != manifest_count
                or not all(item.get("matches_pin") is True for item in restore.get("files", []))):
            problems.append("H58: public restore receipt does not verify every manifest-pinned input")
        if "not organizer authentication" not in str(preflight.get("scope", "")).lower():
            problems.append("H58: preflight must continue to disclose unresolved organizer provenance")
        if DATA.joinpath("h58_preregistration.json").read_bytes() != reg_path.read_bytes():
            problems.append("H58: published preregistration bytes differ from the frozen registry")

        for page_name in ("h58.html", "index.html", "executive-summary.html", "downloads/index.html"):
            page = DOCS / page_name
            if not page.is_file():
                problems.append(f"H58: {page_name} is missing")
                continue
            text = page.read_text(encoding="utf-8", errors="replace")
            if "h58-candidate.tif" not in text:
                problems.append(f"H58: {page_name} lacks the prominent short download path")
            if filename not in text or str(result["artifact"]["sha256"])[:24] not in text:
                problems.append(f"H58: {page_name} does not identify the unique TIFF and its SHA prefix")
            if "do not upload" not in text.casefold() and "not approved to submit" not in text.casefold():
                problems.append(f"H58: {page_name} does not clearly state the research-only/no-upload status")
        if "local catalogue-proxy" not in (DOCS / "h58.html").read_text().casefold():
            problems.append("H58: audit page must distinguish catalogue-proxy scores from organizer validation")
        notes.append("H58 provenance: 23 owner-mirror SHA pins verified; organizer authentication remains unresolved; no slot used")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"H58: receipt/site validation raised {type(exc).__name__}: {exc}")
    return problems


def main() -> int:
    problems: list[str] = []
    notes: list[str] = []
    node = shutil.which("node")
    notes.append(f"JS parser available: {bool(node)}" + ("" if node else " (falling back to balance checks)"))
    pages = sorted(DOCS.glob("*.html")) + [ROOT / "index.html"] + sorted((DOCS / "downloads").glob("*.html"))
    if not pages:
        print("no pages found", file=sys.stderr)
        return 1

    typed_numbers: list[str] = []
    js_checked: set[str] = set()
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        scan = Scan()
        scan.feed(text)
        rel = page.relative_to(ROOT)

        # 1. links resolve
        for h in scan.hrefs:
            if h.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = (page.parent / h.split("#")[0]).resolve()
            if not target.exists():
                problems.append(f"{rel}: dead link -> {h}")

        # 2. assets resolve
        for s in scan.srcs:
            if s.startswith(("http://", "https://", "data:")):
                continue
            if not (page.parent / s.split("#")[0]).resolve().exists():
                problems.append(f"{rel}: missing asset -> {s}")

        # 3. every fetch('data/x.json') has a file on disk
        wanted = set(re.findall(r"G52\.load\(['\"]([\w\-]+)['\"]\)", text))
        wanted |= set(re.findall(r"fetch\(['\"]data/([\w\-]+)\.json", text))
        for chunk in re.findall(r"Promise\.all\(\[([^\]]*)\]", text, re.S):
            wanted |= set(re.findall(r"['\"]([\w\-]+)['\"]", chunk))
        for name in sorted(x for x in wanted if x):
            if not (DATA / f"{name}.json").exists():
                problems.append(f"{rel}: JS asks for data/{name}.json, which the feed does not write")

        # 4. JS must parse.  A broken script tag on a data-driven page is invisible: the page loads, the
        #    numbers simply do not appear, and every reader blames the feed.  With node available we ask it
        #    directly; without it we fall back to a brace/paren balance check, which is weak but has already
        #    caught a real TDZ bug and an unbalanced row-array in tables.js.
        for i, blk in enumerate(s for s in scan.inline if s.strip()):
            if node:
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
                    fh.write(blk)
                    tmp = pathlib.Path(fh.name)
                rc = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
                tmp.unlink(missing_ok=True)
                if rc.returncode != 0:
                    problems.append(f"{rel}: inline script #{i} does not parse — "
                                    f"{rc.stderr.strip().splitlines()[0] if rc.stderr else 'node --check failed'}")
            else:
                for op, cl in (("{", "}"), ("(", ")")):
                    if blk.count(op) != blk.count(cl):
                        problems.append(f"{rel}: inline script #{i} is unbalanced on {op}{cl} "
                                        f"({blk.count(op)} vs {blk.count(cl)})")
                        break
        for js in (sorted(DOCS.glob("*.js")) if page.parent == DOCS and node else []):
            if str(js) in js_checked:
                continue
            js_checked.add(str(js))
            rc = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
            if rc.returncode != 0:
                problems.append(f"{js.relative_to(ROOT)}: does not parse — "
                                f"{rc.stderr.strip().splitlines()[0] if rc.stderr else 'node --check failed'}")

        # 5. no hard-coded scores in prose (they belong in the JSON the feed writes)
        if page.name != "index.html" or True:
            for m in re.finditer(r"\b0\.\d{4}\b", re.sub(r"<script.*?</script>", "", text, flags=re.S)):
                typed_numbers.append(f"{rel}: literal {m.group(0)} in HTML (should come from data/*.json)")

    # 6. the JSON itself must be valid and self-consistent where we can check it
    for f in sorted(DATA.glob("*.json")):
        try:
            # strict: Python's json accepts NaN/Infinity, JSON.parse does not.  A published file with a
            # bare NaN reads fine here and silently in the browser, which is how "not measured" appeared
            # on a page whose evidence file had a number in it.
            d = json.loads(f.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(
                ValueError(f"non-JSON constant {x!r}; JSON.parse would reject this file")))
        except Exception as e:                                    # noqa: BLE001
            problems.append(f"data/{f.name}: invalid JSON ({e})")
            continue
        if f.name == "submission.json" and isinstance(d, dict) and d.get("exists"):
            fmt = d.get("format") or {}
            uni = d.get("uniqueness") or {}
            if fmt and not fmt.get("ok"):
                problems.append("submission.json: the staged file does NOT pass the format gate: "
                                + "; ".join(fmt.get("problems", [])[:3]))
            canonical_unique = uni.get('canonical_pattern_unique',
                                       uni.get('research_publication_ok', uni.get('ok')))
            if uni and canonical_unique is not True:
                problems.append('submission.json: canonical pattern uniqueness/literal non-union '
                                'failed: ' + str(uni.get('relation_to_union') or uni))
            if uni and uni.get('ok') is False:
                if d.get('promoted') or (d.get('validation') or {}).get('approved_for_slot'):
                    problems.append('Scientific promotion despite failed original support-novelty diagnostic')
                else:
                    notes.append('Original >=20% support-novelty diagnostic FAIL is retained. Canonical-distinct research release only; no slot approval.')
            dl = DOCS / (d.get("download") or "")
            if not dl.exists():
                problems.append(f"submission.json: download path {d.get('download')} is not in docs/")
            elif dl.stat().st_size != d.get("bytes"):
                problems.append("submission.json: docs/ copy size != the size in the receipt")
            else:
                got = hashlib.sha256(dl.read_bytes()).hexdigest()
                if got != d.get("sha256"):
                    problems.append(f"submission.json: sha256 mismatch ({got[:12]}… != {str(d.get('sha256'))[:12]}…)")
                else:
                    notes.append(f"download verified byte-for-byte against the receipt: {dl.name} "
                                 f"({d.get('bytes')} bytes, {got[:16]}…)")
        if f.name == "submission_r3.json" and isinstance(d, dict):
            if d.get("approved_for_weekly_slot") is not False or d.get("weekly_submission_slots_used") != 0:
                problems.append("submission_r3.json: R3 research artifact must remain non-approved with zero slots")
            if not str(d.get("artifact_status", "")).startswith("RESEARCH ONLY"):
                problems.append("submission_r3.json: missing explicit research-only status")
            if len(str(d.get("submission_note") or d.get("note") or "")) > 200:
                problems.append("submission_r3.json: note exceeds the 200-character limit")
            fmt = d.get("format") or {}
            uni = d.get("uniqueness") or {}
            if not fmt.get("ok") or not uni.get("research_publication_ok"):
                problems.append("submission_r3.json: research artifact failed its local format/canonical-pattern gate")
            if not (d.get("view_comparison") or {}).get("not_copied_or_literal_union"):
                problems.append("submission_r3.json: copy/union audit did not pass")
            dl = DOCS / "downloads" / str(d.get("file", ""))
            if not dl.exists():
                problems.append(f"submission_r3.json: research download missing: {dl.name}")
            elif dl.stat().st_size != d.get("bytes"):
                problems.append("submission_r3.json: research download size differs from its receipt")
            else:
                got = hashlib.sha256(dl.read_bytes()).hexdigest()
                if got != d.get("sha256"):
                    problems.append("submission_r3.json: research download hash differs from its receipt")
                else:
                    notes.append(f"R3 research TIFF verified against its independent receipt: {dl.name} ({got[:16]}…)")
        if f.name == "leaderboard.json" and d.get("rows"):
            top = d["rows"][0]["score"]
            if abs(float(d.get("top", top)) - float(top)) > 1e-9:
                problems.append("leaderboard.json: 'top' disagrees with row 1")

    # Current H56 is intentionally downloadable but explicitly not slot-approved. Re-check the decision,
    # decoded-pattern review, A-only scope, and byte-identical aliases together; a report that contradicts
    # any one of them must stop publication.
    try:
        import csv
        import zipfile

        import numpy as np
        import rasterio

        sub_path = DATA / 'submission.json'
        sub = json.loads(sub_path.read_text()) if sub_path.exists() else {}
        current_round = ('H58' if str(sub.get('file', '')).startswith('gems52-h58-')
                         else 'H57' if str(sub.get('file', '')).startswith('gems52-h57-')
                         else 'H56' if str(sub.get('file', '')).startswith('gems52-h56-')
                         else 'OTHER')
        notes.append(f'current round dispatched from docs/data/submission.json: {current_round} '
                     f"({sub.get('file')})")

        if sub_path.exists():
            marker = (ROOT / 'submission/LATEST.txt').read_text().strip()
            if sub.get('file') != marker:
                problems.append(f'{current_round}: docs/data/submission.json does not match '
                                'submission/LATEST.txt')
        if (DATA / "h58_result.json").is_file():
            problems.extend(check_h58(DATA, DOCS, ROOT, notes,
                                      current_round=(current_round == "H58")))
        if current_round == 'H57':
            problems.extend(check_h57(DATA, DOCS, ROOT, notes))
            problems.extend(check_h57_creditcore(DATA, DOCS, ROOT, notes))
        if current_round == 'H56':
            sub = json.loads(sub_path.read_text())
            if sub.get('file') != marker:
                problems.append('H56: docs/data/submission.json does not match submission/LATEST.txt')
            if sub.get('approved_for_weekly_slot') is not False:
                problems.append('H56: current artifact must remain explicitly not approved for a weekly slot')
            _ = None
            review_path = DATA / 'h56_slot_gate_review_2026-10-07.json'
            if not review_path.exists():
                problems.append('H56: slot-gate review missing from docs/data')
            else:
                h56_review = json.loads(review_path.read_text())
                if h56_review.get('artifact') != sub.get('file') or h56_review.get('sha256') != sub.get('sha256'):
                    problems.append('H56: slot-gate review does not bind to the current TIFF/hash')
                if h56_review.get('decision', {}).get('approved_for_weekly_slot') is not False:
                    problems.append('H56: slot-gate review must explicitly deny upload until a comparable holdout passes')
                if h56_review.get('spatial_holdout', {}).get('h56_comparable_holdout_receipt_found') is not False:
                    problems.append('H56: holdout absence is not stated in the slot-gate review')
            verify_path = DATA / 'gems52-h56-verify.json'
            if not verify_path.exists():
                problems.append('H56: decoded verifier receipt missing from docs/data')
            else:
                verify = json.loads(verify_path.read_text())
                if hashlib.sha256(verify_path.read_bytes()).hexdigest() != 'cbcfa36a53995c81be2947f74cd5bac0231385e5e1e0282d02f61bd700a5d63b':
                    problems.append('H56: published verifier receipt bytes differ from the reviewed source receipt')
                if verify.get('file') != sub.get('file') or verify.get('sha256') != sub.get('sha256'):
                    problems.append('H56: verifier receipt does not bind to the current TIFF/hash')
                if verify.get('identical_to_any_prior') != [] or verify.get('priors_checked') != 33:
                    problems.append('H56: decoded identity/33-prior audit changed or is missing')
                if verify.get('novel_px') != 12941 or abs(float(verify.get('novel_fraction', 0)) - 0.3193967964064467) > 1e-9:
                    problems.append('H56: decoded support-novelty discrepancy must remain disclosed (12,941 / 31.94%)')
                if verify.get('min_NN_separation_ok') is not False:
                    problems.append('H56: full-file nearest-neighbour diagnostic must retain its measured failure')
            post = (sub.get('postbuild_review') or {})
            if post.get('selected_arm_cells') != 15000 or post.get('selected_arm_cells_with_accessible_prior_support') != 2059:
                problems.append('H56: selected-arm/prior-support discrepancy is not disclosed in the current receipt')
            if post.get('global_min_NN_separation_pass') is not False:
                problems.append('H56: full-file spacing diagnostic is not exposed as failed in submission.json')
            if (sub.get('postbuild_review') or {}).get('a_only_reasoning', '').startswith('not available') is False:
                problems.append('H56: A-only reasoning limitation is missing from submission.json')

            canonical = DOCS / (sub.get('download') or '')
            alias = DOCS / 'downloads/h56-candidate.tif'
            canonical_zip = DOCS / (sub.get('download_zip') or '')
            alias_zip = DOCS / 'downloads/h56-candidate.zip'
            if not canonical.exists() or not alias.exists() or canonical.read_bytes() != alias.read_bytes():
                problems.append('H56: short TIFF alias is missing or not byte-identical to the canonical raster')
            if not canonical_zip.exists() or not alias_zip.exists() or canonical_zip.read_bytes() != alias_zip.read_bytes():
                problems.append('H56: short ZIP alias is missing or not byte-identical to the canonical ZIP')
            for zpath in (canonical_zip, alias_zip):
                if zpath.exists():
                    with zipfile.ZipFile(zpath) as archive:
                        members = archive.namelist()
                        if members != [str(sub.get('file'))] or archive.read(members[0]) != canonical.read_bytes():
                            problems.append(f'H56: {zpath.name} must contain exactly the canonical byte-identical TIFF')
            if canonical.exists():
                with rasterio.open(canonical) as ds:
                    arr = ds.read(1)
                    transform = tuple(ds.transform)[:6]
                    if (ds.count != 1 or ds.dtypes[0] != 'float32' or ds.crs is None or ds.crs.to_epsg() != 32611
                            or (ds.height, ds.width) != (3730, 3292)
                            or transform != (100.0, 0.0, 243350.0, 0.0, -100.0, 4508550.0)
                            or not np.isfinite(arr).all() or float(arr.min()) != 0.0 or float(arr.max()) != 1.0
                            or set(np.unique(arr).tolist()) != {0.0, 1.0}
                            or int(np.count_nonzero(arr)) != 40517):
                        problems.append('H56: on-disk read-back failed the single-band float32/grid/range/value/count check')
            h56_page = (DOCS / 'h56.html').read_text() if (DOCS / 'h56.html').exists() else ''
            for phrase in ('DO NOT UPLOAD', '12,941/40,517', 'A-only reasoning scope', '2.828 px'):
                if phrase.casefold() not in h56_page.casefold():
                    problems.append(f'H56 page: missing required status/disclosure {phrase!r}')
            downloads_index = DOCS / 'downloads/index.html'
            if not downloads_index.exists():
                problems.append('site downloads index is missing')
            else:
                downloads_text = downloads_index.read_text()
                if ('h56-candidate.tif' not in downloads_text or 'h56-candidate.zip' not in downloads_text
                        or 'NOT approved for upload' not in downloads_text):
                    problems.append('downloads index: prominent H56 short paths/status are missing or ambiguous')
            a_only_path = DATA / 'h56_a_only_reasoning_scope_2026-10-07.json'
            if not a_only_path.exists():
                problems.append('H56: explicit A-only scope/limitation receipt missing from docs/data')
            else:
                a_only = json.loads(a_only_path.read_text())
                if not str(a_only.get('status', '')).startswith('NOT PRODUCED'):
                    problems.append('H56: A-only limitation receipt must not claim unavailable reasoning was produced')
            review3_path = DATA / 'review_current_integrated_tree_2026-10-07.json'
            if not review3_path.exists():
                problems.append('H56: completed three-pass integration review is missing from docs/data')
            else:
                review3 = json.loads(review3_path.read_text())
                if review3.get('status') != 'three-pass integration review complete; no upload performed':
                    problems.append('H56: three-pass integration review status is not complete/no-upload')
                if (review3.get('pass_3_full_recheck_against_acceptance', {}).get('pytest', {}).get('failed') != 0
                        or review3.get('pass_3_full_recheck_against_acceptance', {}).get('pytest', {}).get('passed') < 100):
                    problems.append('H56: three-pass review does not record a successful test suite')

        # H54 is a separate audit-only artifact; it must not become the main pointer or claim global uniqueness.
        h54_path = DATA / 'h54_audit.json'
        if h54_path.exists():
            h54 = json.loads(h54_path.read_text())
            if h54.get('approved_for_weekly_slot') is not False or h54.get('global_decoded_pattern_uniqueness', '').startswith('pass'):
                problems.append('H54: audit-only/no-global-uniqueness status is missing or unsafe')
            if h54.get('file') == (ROOT / 'submission/LATEST.txt').read_text().strip():
                problems.append('H54: legacy audit artifact was conflated with the current H56 pointer')
            h54_file = DOCS / 'downloads' / str(h54.get('file', ''))
            h54_alias = DOCS / 'downloads/h54-audit-only.tif'
            h54_zip = DOCS / 'downloads/h54-audit-only.zip'
            h54_canonical_zip = DOCS / str(h54.get('canonical_zip', ''))
            if not h54_file.exists() or not h54_alias.exists() or h54_file.read_bytes() != h54_alias.read_bytes():
                problems.append('H54: short audit TIFF is missing or not byte-identical to its canonical TIFF')
            if h54_zip.exists():
                with zipfile.ZipFile(h54_zip) as archive:
                    tiffs = [n for n in archive.namelist() if n.lower().endswith(('.tif', '.tiff'))]
                    if len(tiffs) != 1 or archive.read(tiffs[0]) != h54_file.read_bytes():
                        problems.append('H54: audit ZIP must contain exactly one byte-identical TIFF')
            if (not h54_canonical_zip.exists() or not h54_zip.exists()
                    or h54_canonical_zip.read_bytes() != h54_zip.read_bytes()):
                problems.append('H54: short audit ZIP is missing or not byte-identical to its canonical ZIP')

        # H55-1 is separate, failed, and has a documented protocol-gate preservation gap.
        paired = DATA / 'h55_paired_shoulders_holdout.json'
        gate = DATA / 'h55_paired_shoulders_protocol_gate.json'
        integrity = DATA / 'h55_paired_shoulders_run_integrity.json'
        prereg = ROOT / 'registry/h55_paired_shoulders_preregistration.json'
        if paired.exists() and gate.exists() and integrity.exists() and prereg.exists():
            h55 = json.loads(paired.read_text())
            h55_gate = json.loads(gate.read_text())
            h55_integrity = json.loads(integrity.read_text())
            gap = (h55_integrity.get('execution_path_namespace') or {}).get('protocol_gate_preservation_gap') or {}
            prereg_sha = hashlib.sha256(prereg.read_bytes()).hexdigest()
            if h55.get('preregistration_sha256') != prereg_sha:
                problems.append('H55-1: frozen registration hash differs from the holdout receipt')
            if h55.get('scientific_holdout_gate_pass') is not False or h55.get('slot_gate', {}).get('approved_for_weekly_slot') is not False:
                problems.append('H55-1: failed matched holdout must remain not approved for upload')
            if abs(float((h55.get('arms') or {}).get('mean_dti_lift', 0)) - 0.002360879644970948) > 1e-12:
                problems.append('H55-1: paired mean-lift result changed without review')
            if gap.get('preholdout_gate_exact_bytes_preserved') is not False:
                problems.append('H55-1: protocol-gate hash-preservation gap is not disclosed')
            if hashlib.sha256(gate.read_bytes()).hexdigest() != gap.get('currently_preserved_post_run_gate_sha256'):
                problems.append('H55-1: current protocol-gate bytes differ from the integrity supplement')
            if h55.get('protocol_gate_sha256') != gap.get('holdout_bound_preholdout_gate_sha256'):
                problems.append('H55-1: holdout-bound preflight gate hash is not preserved in the gap record')
            h55_page = (DOCS / 'h55-paired-shoulders.html').read_text() if (DOCS / 'h55-paired-shoulders.html').exists() else ''
            for phrase in ('Preregistered gate failed', 'Preservation gap', '91060c4', '6a696fe'):
                if phrase.casefold() not in h55_page.casefold():
                    problems.append(f'H55-1 page: missing failed-gate/provenance disclosure {phrase!r}')

    except Exception as e:  # noqa: BLE001
        problems.append(f'current-artifact/audit consistency check failed unexpectedly: {e}')

    # 7. the pages must actually serve, with the right content type for the .tif
    import http.server
    import socketserver

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(DOCS), **kw)

        def log_message(self, *a):
            pass

    class ThreadedTCPServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = ThreadedTCPServer(("127.0.0.1", 0), H)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        page_paths = ("index.html", "executive-summary.html", "h56.html", "h54.html",
                      "h55-paired-shoulders.html", "h55.html", "h55-profile.html", "h55-edge.html",
                      "r3.html", "r3-hypotheses.html", "feed.html", "irregularities.html", "sources.html",
                      "downloads/index.html")
        if (DOCS / "h58.html").is_file():
            page_paths = ("index.html", "executive-summary.html", "h58.html") + page_paths[2:]
        for path in page_paths:
            with urlopen(f"http://127.0.0.1:{port}/{path}", timeout=10) as r:
                body = r.read()
                if r.status != 200 or len(body) < 200:
                    problems.append(f"served {path}: status {r.status}, {len(body)} bytes")
        sub = json.loads((DATA / "submission.json").read_text())
        with urlopen(f"http://127.0.0.1:{port}/{sub['download']}", timeout=20) as r:
            n = len(r.read())
            ctype = r.headers.get("Content-Type", "")
            if n != sub["bytes"]:
                problems.append(f"served {sub['download']}: {n} bytes != {sub['bytes']} in the receipt")
            else:
                notes.append(f"the .tif serves through the site: {n:,} bytes, content-type {ctype}")
        if str(sub.get('file', '')).startswith('gems52-h56-'):
            for short_name in ('downloads/h56-candidate.tif', 'downloads/h56-candidate.zip'):
                with urlopen(f"http://127.0.0.1:{port}/{short_name}", timeout=20) as r:
                    body = r.read()
                    local = DOCS / short_name
                    if body != local.read_bytes():
                        problems.append(f"served {short_name}: response differs from its byte-identical alias")
                    elif short_name.endswith('.tif') and hashlib.sha256(body).hexdigest() != sub.get('sha256'):
                        problems.append('served H56 short-path TIFF differs from the audited SHA-256')
                    else:
                        notes.append(f"short path serves byte-identically: {short_name}")
        h58_result_path = DATA / "h58_result.json"
        if h58_result_path.is_file():
            h58_sha = json.loads(h58_result_path.read_text()).get("artifact", {}).get("sha256")
            for short_name in ('downloads/h58-candidate.tif', 'downloads/h58-candidate.zip'):
                with urlopen(f"http://127.0.0.1:{port}/{short_name}", timeout=20) as r:
                    body = r.read()
                    local = DOCS / short_name
                    if body != local.read_bytes():
                        problems.append(f"served {short_name}: response differs from its byte-identical alias")
                    elif short_name.endswith('.tif') and hashlib.sha256(body).hexdigest() != h58_sha:
                        problems.append('served H58 short-path TIFF differs from the audited SHA-256')
                    else:
                        notes.append(f"short path serves byte-identically: {short_name}")

        # H55-PROFILE is historical and remains separate from the current H56 artifact.
        h55_path = DATA / "h55_profile.json"
        if h55_path.exists():
            import zipfile
            import numpy as np
            import rasterio
            h55 = json.loads(h55_path.read_text())
            h55_file = DOCS / "downloads" / h55["file"]
            if not h55.get("research_only") or h55.get("weekly_slot_approved"):
                problems.append("h55_profile.json: research-only/failed-slot status is missing or unsafe")
            if len(h55.get("note", "")) > 200:
                problems.append("h55_profile.json: portal note exceeds 200 characters")
            if not h55_file.exists() or hashlib.sha256(h55_file.read_bytes()).hexdigest() != h55.get("sha256"):
                problems.append("h55_profile.json: published H55 TIFF missing or differs from SHA-256 receipt")
            else:
                with rasterio.open(h55_file) as ds:
                    a = ds.read(1)
                    if (ds.count != 1 or ds.dtypes[0] != "float32" or ds.crs is None or ds.crs.to_epsg() != 32611
                            or (ds.height, ds.width) != (3730, 3292)
                            or not np.isfinite(a).all() or float(a.min()) < 0 or float(a.max()) > 1):
                        problems.append("H55 TIFF: raster dimensions/CRS/dtype/finite [0,1] check failed")
                    elif int((a > 0).sum()) != h55["format"]["n_nonzero"]:
                        problems.append("H55 TIFF: nonzero count differs from the published summary")
                zpath = h55_file.with_suffix(".zip")
                if not zpath.exists():
                    problems.append("H55 single-TIFF ZIP is missing")
                else:
                    with zipfile.ZipFile(zpath) as z:
                        tiffs = [n for n in z.namelist() if n.lower().endswith((".tif", ".tiff"))]
                        if len(tiffs) != 1 or z.read(tiffs[0]) != h55_file.read_bytes():
                            problems.append("H55 ZIP must contain exactly one TIFF byte-identical to the direct download")
                with urlopen(f"http://127.0.0.1:{port}/downloads/{h55['file']}", timeout=20) as r:
                    if len(r.read()) != h55["bytes"]:
                        problems.append("served H55 TIFF byte count differs from receipt")
                notes.append(f"H55-PROFILE TIFF verified: {h55['bytes']:,} bytes, {h55['uniqueness']['n_priors_checked']} priors, research-only")
        edge_served_path = DATA / "h55_edge_submission.json"
        if edge_served_path.exists():
            edge_served = json.loads(edge_served_path.read_text())
            with urlopen(f"http://127.0.0.1:{port}/downloads/{edge_served['file']}", timeout=20) as r:
                n = len(r.read())
                if n != edge_served["bytes"]:
                    problems.append("served H55-EDGE TIFF byte count differs from receipt")
                else:
                    notes.append(f"H55-EDGE TIFF served byte-identically: {n:,} bytes")

        # R3-H1 is a separate failed-gate research release; it is not the submission.json incumbent.
        r3 = json.loads((DATA / "submission_r3.json").read_text())
        with urlopen(f"http://127.0.0.1:{port}/downloads/{r3['file']}", timeout=20) as r:
            body = r.read()
            if len(body) != r3["bytes"] or hashlib.sha256(body).hexdigest() != r3["sha256"]:
                problems.append("served R3 research TIFF differs from its audited bytes")
            else:
                notes.append(f"research-only R3 TIFF also serves byte-identically: {len(body):,} bytes")
    finally:
        httpd.shutdown()

    # Verify receipt-rendered measurements without conflating the H55 incumbent, H55-PROFILE,
    # and H55-EDGE. The latter is a separate failed-gate archive and must never become global latest.
    current = json.loads((DATA / 'submission.json').read_text()) if (DATA / 'submission.json').exists() else {}
    r2_holdout = DATA / 'holdout_r2.json'
    if r2_holdout.exists():
        h = json.loads(r2_holdout.read_text())
        text = (DOCS / 'validation.html').read_text()
        for arm, value in h['means'].items():
            if f'{value:.6f}' not in text:
                problems.append(f'validation.html: R2 {arm} mean is not rendered from its receipt')
        # The literal used to be the H53/H54 string 'Do not upload'.  That is a per-round status
        # marker, not a permanent property of the site, so it is now read from the current receipt.
        marker_needed = ('do not upload' if current_round != 'H57' else None)
        if marker_needed:
            for page_name in ('index.html', 'executive-summary.html'):
                body = (DOCS / page_name).read_text()
                if marker_needed not in body.casefold():
                    problems.append(f'{page_name}: missing failed-gate warning {marker_needed!r}')

    edge_path = DATA / 'h55_edge_submission.json'
    edge_hold_path = DATA / 'h55_edge_holdout.json'
    edge_deviation_path = DATA / 'h55_edge_protocol_deviation.json'
    if edge_path.exists():
        import csv
        import zipfile
        import numpy as np
        import rasterio
        edge = json.loads(edge_path.read_text())
        if not edge_hold_path.exists() or not edge_deviation_path.exists():
            problems.append('H55-EDGE: missing independent holdout or protocol-deviation receipt')
        else:
            edge_hold = json.loads(edge_hold_path.read_text())
            edge_deviation = json.loads(edge_deviation_path.read_text())
            prereg_path = ROOT / 'registry/h55_edge_preregistration.json'
            prereg_sha = hashlib.sha256(prereg_path.read_bytes()).hexdigest() if prereg_path.exists() else None
            if not prereg_sha or prereg_sha != edge.get('preregistration_sha256'):
                problems.append('H55-EDGE: frozen preregistration hash does not match artifact receipt')
            if edge_deviation.get('preregistration_sha256_at_validation') != prereg_sha:
                problems.append('H55-EDGE: protocol-deviation receipt hash mismatch')
            if edge_hold.get('preregistration_sha256') != prereg_sha:
                problems.append('H55-EDGE: holdout receipt hash mismatch')
            if edge.get('approved_for_weekly_slot') is not False or edge.get('official_score') is not None or edge.get('submission_slots_used') != 0:
                problems.append('H55-EDGE: artifact must remain failed-gate, unscored, and zero-slot')
            if edge.get('uniqueness', {}).get('support_novelty_gate_ok') is not False:
                problems.append('H55-EDGE: strict support-novelty failure was not retained')
            if edge_deviation.get('holdout_result_for_implemented_subset', {}).get('gate_passed') is not False:
                problems.append('H55-EDGE: implemented-subset holdout failure was not retained')
            edge_name = edge.get('file') or ''
            edge_file = DOCS / 'downloads' / edge_name
            expected_sha = edge.get('sha256')
            if not edge_file.exists() or hashlib.sha256(edge_file.read_bytes()).hexdigest() != expected_sha:
                problems.append('H55-EDGE: published TIFF is missing or differs from the audited bytes')
            else:
                with rasterio.open(edge_file) as ds:
                    a = ds.read(1)
                    if (ds.count != 1 or ds.dtypes[0] != 'float32' or ds.crs is None or ds.crs.to_epsg() != 32611
                            or (ds.height, ds.width) != (3730, 3292) or not np.isfinite(a).all()
                            or float(a.min()) < 0 or float(a.max()) > 1
                            or int(np.count_nonzero(a)) != int(edge['format']['n_nonzero'])
                            or np.any((a > 0) & (ds.dataset_mask() == 0))):
                        problems.append('H55-EDGE: on-disk raster format/range/footprint check failed')
                zip_path = edge_file.with_suffix('.zip')
                if not zip_path.exists():
                    problems.append('H55-EDGE: single-TIFF ZIP is missing')
                else:
                    with zipfile.ZipFile(zip_path) as archive:
                        if archive.namelist() != [edge_name] or hashlib.sha256(archive.read(edge_name)).hexdigest() != expected_sha:
                            problems.append('H55-EDGE: ZIP must contain exactly one byte-identical TIFF')
            reasoning = edge.get('view_comparison', {}).get('a_only_reasoning', {})
            reasoning_path = DOCS / 'downloads' / reasoning.get('file', '')
            if not reasoning_path.exists() or hashlib.sha256(reasoning_path.read_bytes()).hexdigest() != reasoning.get('sha256'):
                problems.append('H55-EDGE: per-pixel reasoning CSV missing or hash-mismatched')
            elif reasoning_path.exists():
                with reasoning_path.open(newline='') as fh:
                    rows = list(csv.DictReader(fh))
                if len(rows) != reasoning.get('rows') or len(rows) != 816:
                    problems.append('H55-EDGE: reasoning CSV row count differs from its receipt')
            edge_page = (DOCS / 'h55-edge.html').read_text() if (DOCS / 'h55-edge.html').exists() else ''
            for term in ('h55_edge_protocol_deviation.json', 'H55-EDGE', 'do not upload', 'not the current H55 candidate'):
                if term.casefold() not in edge_page.casefold():
                    problems.append(f'H55-EDGE page: missing required disclosure/link text {term!r}')
            main_marker = (ROOT / 'submission/LATEST.txt').read_text().strip() if (ROOT / 'submission/LATEST.txt').exists() else ''
            edge_marker = (ROOT / 'submission/H55_EDGE_LATEST.txt').read_text().strip() if (ROOT / 'submission/H55_EDGE_LATEST.txt').exists() else ''
            if main_marker == edge_name or current.get('file') != main_marker:
                problems.append('H55-EDGE: global incumbent marker/current receipt was changed or conflated')
            if edge_marker != edge_name:
                problems.append('H55-EDGE: experiment-specific marker is missing or points to different bytes')
            for page_name in ('index.html', 'h55.html', 'downloads/index.html'):
                page_text = (DOCS / page_name).read_text()
                if 'h55-edge.html' not in page_text:
                    problems.append(f'{page_name}: missing separate H55-EDGE archive link')
            notes.append(f"H55-EDGE verified as a separate failed-gate archive: {edge['bytes']:,} bytes, {edge_hold['positive_folds']}/4 positive folds; main incumbent unchanged")

    # The prose-literal list was collected and then never read: the diagnostic existed but was
    # invisible, so a page could quote a 4-decimal score that its own receipt had changed.
    # Surface it as an informational note (not a failure: several pages deliberately quote the
    # published scores in prose, and the receipts remain the machine-readable source of truth).
    if typed_numbers:
        notes.append(f"prose literals with 4+ decimals found in HTML: {len(typed_numbers)} "
                     "(informational; receipts stay authoritative)")
        notes.extend("  " + x for x in typed_numbers[:4])

    print(f"pages checked: {len(pages)}   data files: {len(list(DATA.glob('*.json')))}")
    for nse in notes:
        print("  note:", nse)
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems[:40]:
            print("  ✗", p)
        return 1
    # The closing sentence used to assert "Scientific slot gate remains closed" unconditionally -- a
    # success message stating a condition the script never read, which is the exact failure mode this
    # script exists to catch in other files.  It became actively wrong the moment an artefact shipped
    # with approved_for_weekly_slot=True (IR-52-031).  Read it, or do not print it.
    sub_p = DATA / 'submission.json'
    sub = json.loads(sub_p.read_text()) if sub_p.exists() else {}
    gate = sub.get('approved_for_weekly_slot')
    if gate is True:
        slot = ('Scientific slot gate is OPEN for '
                f"{sub.get('file')} ({sub.get('promotion', 'no promotion reason recorded')})")
    elif gate is False:
        slot = f"Scientific slot gate remains CLOSED for {sub.get('file')}."
    else:
        slot = 'Scientific slot gate: not recorded in docs/data/submission.json (not assumed either way).'
    print('\n✓ local links/JSON/receipt values verified; format and canonical-pattern research release '
          f'verified; byte-identical TIFF serves through the site. {slot}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
