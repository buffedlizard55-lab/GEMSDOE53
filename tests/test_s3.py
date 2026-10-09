"""Consistency checks for the S3 lane (H8 holdout, S3-A canary, S3-C file). They read receipts; they do not re-run experiments."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel):
    return json.loads((ROOT / rel).read_text())


def test_run_card_branch_is_this_session():
    # The shared evidence/run_card.json now belongs to the merged deliverable; the
    # S3 session's card is archived beside it (merge resolution 2026-10-09).
    card = _load("evidence/archive/main-2026-10-09/run_card_s3.json")
    assert card["session_branch"] == "arena/7b60bcc7-gemsdoe53"


def test_s3b_verdict_follows_the_preregistered_rule():
    s3b = _load("evidence/s3b_h8_holdout.json")
    lower = s3b["stage2"]["b_selected_minus_current_best_H1"]["CI95"][0]
    accepted = lower > 0
    assert s3b["verdict"]["beats_holdout_best"] is accepted
    assert s3b["verdict"]["label"] == ("POSITIVE (holdout)" if accepted else "NEGATIVE (holdout)")


def test_s3a_canary_flags_the_leaky_feature_and_passes_h1():
    s3a = _load("evidence/s3a_leakage_repro.json")
    assert s3a["leaky_construction"]["design_B_canary_on_fold0"]["separability"] > 0.90
    assert s3a["h1_legitimate"]["design_B_canary_on_fold0"]["separability"] <= 0.90
    assert s3a["verdict"]["canary_detects_leaky_feature"] is True


def test_current_label_and_gate_agree_for_s3_file():
    # The S3 candidate pointer moved to its own file at the merge (shared CURRENT.json
    # is the merged deliverable's); everything below checks the S3 artifact itself.
    cur = _load("docs/submissions/CURRENT-s3-20261009.json")
    rec = _load(cur["receipt"])
    gate_ok = rec["gates"]["uniqueness_no_drift_flag"]
    assert gate_ok is False
    assert cur["label"] == "Research-only / DO NOT SUBMIT"
    assert cur["organizer_score"] is None and cur["submitted"] is False


def test_note_length_within_limit():
    cur = _load("docs/submissions/CURRENT-s3-20261009.json")
    assert len(cur["note"]) <= 140
    assert cur["name"] == "gems53-s3-bands-top_q0p02-20261009-e67cda00"


def test_gate_registry_count_matches_receipt():
    gate = _load(f"evidence/uniqueness_gate_{_load('docs/submissions/CURRENT-s3-20261009.json')['name']}.json")
    assert gate["registry_unique_on_grid"] == len(gate["all_rows"]) == 628
    assert gate["n_flagged"] == sum(1 for r in gate["all_rows"] if r["drift_flag"])


def test_shipped_s3_file_hashes_match_receipt():
    cur = _load("docs/submissions/CURRENT-s3-20261009.json")
    path = ROOT / cur["file"]
    if not path.exists():
        pytest.skip("shipped file not present")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == cur["sha256"]
    rasterio = pytest.importorskip("rasterio")
    with rasterio.open(path) as ds:
        arr = ds.read(1)
    pix = hashlib.sha256(np.ascontiguousarray(np.nan_to_num(arr, nan=-1.0), dtype="<f4").tobytes()).hexdigest()
    assert pix == cur["pixel_sha256"]
    fin = arr[np.isfinite(arr)]
    assert fin.min() >= 0.0 and fin.max() <= 1.0
