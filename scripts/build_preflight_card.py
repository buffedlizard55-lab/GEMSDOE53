#!/usr/bin/env python3
"""Summarize the current stop and historic candidate from checked evidence only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def read(p):
    return json.loads((ROOT / p).read_text())


def main():
    proof = read("evidence/protocol_preflight_20261009.json")
    cur = read("docs/submissions/CURRENT.json")
    old_path = "evidence/candidate_gems53-h1-thin_bin_q0p1-20261008-aefc7582.json"
    old = read(old_path)
    current = read(cur["receipt"])
    gate_path = f"evidence/uniqueness_gate_{cur['name']}.json"
    gate = read(gate_path)
    assert proof["universal_overlap_blocker"] and gate["any_drift_flag"]
    assert proof["reference_sha256"] in {r["sha256"] for r in gate["all_rows"]}
    assert current["sha256"] == cur["sha256"]
    assert old["sha256"] == cur["previous_pointer"]["sha256"]
    card = {
        "session": "arena/2cc82f0e-gemsdoe53 (2026-10-09)",
        "hypothesis": "C1 preliminary screen: conductivity–magnetic phase coherence (untried; S3 ranks H12 ahead of C1)",
        "mechanism": "Matched, oriented cross-scale edges in conductivity band 17 and RTP magnetics band 2 could indicate buried fault damage/fluid pathways.",
        "named_non_fault_process_that_could_mimic_it": "Lithologic contact between units with different conductivity and magnetic susceptibility.",
        "experiment_status": "STOP at pixel-verified registry pre-placement feasibility gate; zero experiments this session; no new surface or dots placed",
        "holdout_DTI": {
            "new_candidate": None,
            "current_S3_control_pooled": current["holdout"]["s3b_stage2_pooled"]["bands_baseline"],
            "current_S3_pooled_CI95": None,
            "legacy_candidate_pooled": old["holdout"]["stage2_selected"]["pooled_DTI"],
            "legacy_pooled_CI95": None,
            "legacy_paired_mean_gain_over_baseline": old["holdout"]["stage2_paired_difference"]["mean_fold_diff"],
            "legacy_paired_gain_CI95": old["holdout"]["stage2_paired_difference"]["CI95"],
            "evaluator": old["holdout"]["evaluator"],
            "withheld_positives": old["holdout"]["withheld_positives_total"],
            "note": "HOLDOUT-DTI catalogue proxy: current S3 control and prior H1. The interval is for H1 paired fold-mean GAIN vs baseline, not either pooled DTI or a new candidate.",
        },
        "registry": {
            "reference_url": proof["reference_url"],
            "reference_sha256": proof["reference_sha256"],
            "sample_sha256": proof["sample_sha256"],
            "footprint_px": proof["footprint_px"],
            "reference_positive_footprint_px": proof["reference_positive_footprint_px"],
            "surface_correlation_new_candidate": None,
            "final_overlap_new_candidate": None,
            "overlap_for_any_nonempty_prediction": proof["overlap_for_any_nonempty_conformant_dot_map"],
            "threshold": proof["limit_strictly_greater_than"],
            "legacy_max_surface_rho": gate["max"]["max_rho_surface"],
            "legacy_max_final_dot_overlap": gate["max"]["max_overlap_final"],
            "legacy_registry_rasters": gate["registry_unique_on_grid"],
            "scope": "Full positive-footprint reference proves universal stop for any nonempty dot map under this literal registry definition; no C1-specific correlation was computed.",
        },
        "raster_sha256": {"new_candidate": None, "existing_research_only_H1": old["sha256"], "current_research_only_S3": cur["sha256"]},
        "validator_output": {
            "new_C1": "NOT RUN; no raster generated after stop",
            "current_research_only_S3": {
                "shared_template_submission_exit": current["validators"]["final_template_validate_submission"]["exit"],
                "shared_template_conformant_exit": current["validators"]["final_validate_conformant"]["exit"],
                "no_NaN_inside_footprint": current["inlane"]["nan_inside_footprint"] == 0,
                "values_in_0_1": current["inlane"]["values_in_0_1_whole_array"],
                "CRS_match": current["inlane"]["crs_ok"],
                "shape_match": current["inlane"]["shape_ok"],
                "transform_match": current["inlane"]["transform_ok"],
            },
            "existing_research_only_H1": {
                "shared_template_submission_exit": old["validators"]["final_template_validate_submission"]["exit"],
                "shared_template_conformant_exit": old["validators"]["final_validate_conformant"]["exit"],
                "no_NaN_inside_footprint": old["inlane"]["nan_exact_outside_template"],
                "values_in_0_1": old["inlane"]["values_in_0_1_whole_array"],
                "CRS_match": old["inlane"]["crs_ok"],
                "shape_match": old["inlane"]["shape_ok"],
                "transform_match": old["inlane"]["transform_ok"],
            },
        },
        "submission_name": {"new_candidate": None, "existing_research_only_H1": old["name"], "current_research_only_S3": cur["name"]},
        "submission_note": "DO NOT SUBMIT: literal registry overlap=100%; no C1 candidate or organizer score.",
        "organizer_score": None,
        "weekly_submission_slot_used": False,
        "verdict": "negative",
        "reasons": ["literal >70% registry rule cannot clear any nonempty conformant prediction", "No new holdout run; no score improvement established"],
        "provenance": ["evidence/protocol_preflight_20261009.json", cur["receipt"], old_path, gate_path],
    }
    assert len(card["submission_note"]) <= 140
    out = ROOT / "evidence/run_card_20261009.json"
    out.write_text(json.dumps(card, indent=2) + "\n")
    print(out)

if __name__ == "__main__":
    main()
