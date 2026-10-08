"""Guard the recorded H55 decision against accidental post-hoc promotion."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_h55_result_misses_frozen_mean_lift_gate_and_stays_research_only():
    registration = json.loads((ROOT / "registry/h55_paired_shoulders_preregistration.json").read_text())
    result = json.loads((ROOT / "evidence/h55_paired_shoulders_holdout.json").read_text())
    gate = registration["decision_gate"]
    lift = result["arms"]["mean_dti_lift"]
    assert gate["minimum_mean_dti_lift_over_matched_view_B"] == 0.005
    assert gate["minimum_positive_outer_folds"] == 3
    assert lift == pytest_approx(0.002360879644970948)
    assert result["positive_outer_folds"] == 4
    assert result["total_outer_folds"] == 4
    assert result["scientific_holdout_gate_pass"] is False
    assert result["slot_gate"]["approved_for_weekly_slot"] is False
    assert result["slot_gate"]["submission_slots_used"] == 0
    assert result["portal_upload_performed"] is False
    assert result["score_mapping_authenticated"] is False
    assert result["organizer_input_bytes_authenticated"] is False


def test_each_registered_h55_fold_is_buffered_and_paired():
    result = json.loads((ROOT / "evidence/h55_paired_shoulders_holdout.json").read_text())
    folds = result["folds"]
    assert len(folds) == 4
    for fold in folds:
        receipt = fold["receipt"]
        assert receipt["shared_train_truth_components"] == 0
        assert receipt["buffer_px"] == 80
        assert receipt["nearest_training_to_region_px"] >= 80
        assert fold["same_training_rows_seed_and_learner"] is True
        assert fold["paired_dti_lift"] > 0


def test_no_h55_1_candidate_was_built_or_promoted():
    result = json.loads((ROOT / "evidence/h55_paired_shoulders_holdout.json").read_text())
    submission = ROOT / "submission"
    paired_outputs = [p for p in submission.glob("*.tif")
                      if "h55-1" in p.name.lower() or "paired-shoulders" in p.name.lower()]
    assert paired_outputs == []
    assert not (submission / "H55_PAIRED_SHOULDERS_LATEST.txt").exists()
    # The incumbent marker moved on when H57 shipped.  What this test actually asserts is that
    # the failed H55-1 round never became it, under any round.
    current = (submission / "LATEST.txt").read_text().strip()
    assert not current.startswith("gems52-h55-")
    assert "paired" not in current.lower()
    assert result["slot_gate"]["approved_for_weekly_slot"] is False
    assert "no h55-1 tiff was built" in (ROOT / "README.md").read_text().lower()


def test_preflight_recognizes_matching_completed_holdout_and_blocks_duplicate_fit():
    gate = json.loads((ROOT / "evidence/h55_paired_shoulders_protocol_gate.json").read_text())
    completed = gate["existing_matching_holdout"]
    assert gate["status"] == "READY_FOR_PREREGISTERED_HOLDOUT_ONLY"
    assert completed["same_registration_and_core_input_hashes"] is True
    assert completed["scientific_holdout_gate_pass"] is False
    assert "do not refit/retest" in gate["next_action"]


def pytest_approx(value, rel=1e-12, abs=1e-12):
    # Use pytest's comparator without importing pytest for this tiny metadata-only module.
    from pytest import approx
    return approx(value, rel=rel, abs=abs)
