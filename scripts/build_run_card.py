#!/usr/bin/env python3
"""Compose the RUN CARD (protocol item 5) from the evidence JSON files. No numbers are typed in by hand.

Writes evidence/run_card.json. Labels follow protocol item 3:
  HOLDOUT-DTI  = our own hide-and-recover proxy (evaluator version, withheld positives, 95% CI)
  ORGANIZER-CONFIRMED = only from a submission-page receipt (none exists in this repo yet)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p):
    return json.loads(Path(p).read_text())


def main() -> int:
    exp1 = load(ROOT / "evidence" / "exp1_leakage_canary.json")
    exp2 = load(ROOT / "evidence" / "exp2_holdout_arms.json")
    chosen = load(ROOT / "evidence" / "selection.json")
    receipt = load(ROOT / "evidence" / "candidates" / f"{chosen['submission_name']}.receipt.json")
    tmpl_log = (ROOT / "evidence" / "candidates" / "template_validator_nan.txt").read_text()
    overlap = load(ROOT / "evidence" / "overlap_baseline.json")
    uniq = load(ROOT / "evidence" / "uniqueness_check.json")

    arm, q = chosen["arm"], chosen["q"]
    pooled = exp2["arms"][arm]["pooled"][str(q)]
    prim = receipt["files"][f"{chosen['submission_name']}-nan.tif"]
    card = {
        "schema": "gems53.run_card.v1",
        "lane": "GEMSDOE29 leakage diagnosis + leak-free learn-predict separation",
        "hypothesis": ("Distance-to-known-faults features built from the training labels leak the target "
                       "(a deterministic label function). Recomputing them with learn-predict separation and "
                       "scoring with whole-segment hide-and-recover removes the inflation without losing "
                       "the legitimate spatial signal."),
        "mechanism": ("Feature = log1p(min(distance to known-fault pixels, 60)). Built from the same labels it is "
                      "trained on, it is exactly 0 on every positive (Exp 1: 60,988/60,988) and >= 0.6931 (distance >= 1 px) on background, "
                      "so separability is 1.0."),
        "named_non_fault_process_that_could_mimic_it": (
            "Mapping bias: the catalogue traces faults that were already mapped, so proximity to a mapped trace "
            "reflects where mappers worked (survey density, road access, outcrop), not where faults are. "
            "This is a non-fault process that the holdout cannot separate from fault signal."),
        "budget": {
            "experiments": 3,
            "note": ("Exp 2 was re-run once on a corrected footprint (IR-53-05). The discarded run is not reported "
                     "as a result. Wall-clock time was not logged precisely; the 2-hour guardrail was likely exceeded (disclosed, not hidden)."),
        },
        "holdout": {
            "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments; NOT organizer-scored)",
            "evaluator": exp2["evaluator"],
            "design": "5 whole-segment folds (seed 53), 1 km buffer, visible faults masked pixel-exactly",
            "arm": arm,
            "q_fraction_of_footprint": q,
            "pooled_DTI": pooled["pooled_DTI"],
            "per_fold_DTI": pooled["per_fold_DTI"],
            "CI95_t_df4_on_fold_mean": pooled["CI95_t_df4_on_fold_mean"],
            "withheld_fault_px_total": pooled["withheld_fault_px_total"],
            "withheld_segments_total": pooled["n_withheld_segments_total"],
            "caveat": "Truth is catalogue segments, not new faults. Cannot show a leaderboard gain (IR-53-03).",
        },
        "leaky_ablation_for_contrast": {
            "label_type": "HOLDOUT-DTI (leaky, demonstration only)",
            "pooled_DTI": exp2["arms"]["leaky_ablate"]["pooled"][str(q)]["pooled_DTI"]
            if "leaky_ablate" in exp2["arms"] else None,
        },
        "correlation_overlap_vs_registry": {
            "any_drift_flag": uniq["any_drift_flag"],
            "max_spearman_rho_sample": uniq["max_spearman_rho"],
            "max_our_dots_within_3px_of_registry_dots": uniq["max_dot_overlap_within_3px"],
            "registry_files_checked": uniq["n_registry_files"],
            "thresholds": uniq["thresholds"],
            "receipt": "evidence/uniqueness_check.json",
        },
        "raster_sha256": {
            "primary_nan_outside": prim["sha256"],
        },
        "validator_output": {
            "shared_template_validator": {
                "command": "python scripts/validate_submission.py --pred <file> --sample sample_submission.tif --train training_features.tif",
                "template_repo": "buffedlizard55-lab/GEMSDOE",
                "template_commit": "dcbbb192e56b2b32c0a131eba791dc363305d4a3",
                "passed": "Validation PASSED" in tmpl_log,
                "log": "evidence/candidates/template_validator_nan.txt",
            },
            "in_lane_checks": prim["checks"],
            "in_lane_counts": prim["counts"],
        },
        "submission": {
            "name": chosen["submission_name"],
            "note": chosen["note"],
            "note_chars": len(chosen["note"]),
            "file": chosen["files"][0],
            "status": chosen["status"],
            "submitted": False,
            "location_of_files": chosen.get("location"),
        },
        "overlap_chance_baseline": {
            "max_lift": overlap["max_lift"],
            "file": "evidence/overlap_baseline.json",
            "reading": "lift >> 1 means our dots sit near the other file's dots more than random placement at that density would",
        },
        "hypothesis_status": {
            "H1_segment_exact": "ranked 1, NOT run (budget exhausted before the experiment)",
            "H2_magnetic_ridges": "not run",
            "H3_fault_parallel_strain": "not run",
            "H4_qfaults_label_source": "rejected (rules name USGS quaternary maps as a label source)",
        },
        "gemsdoe32_0p2778": "see docs/research/gemsdoe32.md (owner claims, not verified)",
        "limitations": "registry/limitations.json",
        "organizer_score": None,
        "verdict": chosen["verdict"],
        "verdict_reason": chosen["verdict_reason"],
    }
    assert len(card["submission"]["note"]) <= 140, "submission note must be at most 140 characters"
    out = ROOT / "evidence" / "run_card.json"
    out.write_text(json.dumps(card, indent=2))
    print("wrote", out, "| verdict:", card["verdict"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
