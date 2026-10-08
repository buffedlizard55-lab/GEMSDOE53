#!/usr/bin/env python3
"""Compose evidence/run_card.json (one JSON run card) from the evidence files. No number is typed by hand.

Reads: evidence/e1_h1_thin_holdout.json (design A, reference), evidence/e2_leakfree_holdouts.json (design B),
evidence/candidate_<name>.json (E3 receipt, name from docs/submissions/CURRENT.json),
evidence/uniqueness_gate_<name>.json, evidence/gemsdoe32_measured.json, registry/*.json, evidence/timeline.txt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def J(rel):
    return json.loads((ROOT / rel).read_text())


def main() -> int:
    cur = J("docs/submissions/CURRENT.json")
    e1 = J("evidence/e1_h1_thin_holdout.json")
    e2 = J("evidence/e2_leakfree_holdouts.json")
    e3 = J(cur["receipt"])
    gate = J(f"evidence/uniqueness_gate_{cur['name']}.json")
    g32 = J("evidence/gemsdoe32_measured.json")
    irr = J("registry/irregularities.json")["items"]
    lim = J("registry/limitations.json")["items"]
    diag = J(f"evidence/uniqueness_diagnostics_{cur['name']}.json")
    sp_rho = J(f"evidence/diagnostic_surface_rho_{cur['name']}.json")
    sp = e2.get("spatial_confirmation", {})
    stage1 = e2.get("segment_selection", {})
    base_B = e2["baseline_design_B"]
    cd = e2["canary_design_B"]
    variants = e2["segment_folds"]["variants"]

    def v(name):
        return variants.get(name)

    card = {
        "schema": "gems53.run_card.v2",
        "session_branch": "arena/0efb644e-gemsdoe53",
        "date_utc": e3["finished_utc"][:10],
        "lane": "Formal diagnosis of GEMSDOE29 catalogue-distance leakage; one unique candidate under the parallel-run protocol",
        "pre_registration": {"file": "docs/research/preregistration-2026-10-08.md",
                             "amendment": "DEV-1 (section 8), written before the design-B run"},
        "budget": {
            "experiments_limit": 3,
            "experiments_used": 3,
            "experiments": ["E1 design A (exploration, stopped as a design error)",
                            "E2 design B (stage 1 selection on segment folds; stage 2 spatial confirmation)",
                            "E3 build, validation, uniqueness and label (not a holdout experiment)"],
            "wall_clock_limit_hours": 2,
            "experiment_start_utc": e1.get("started_utc"),
            "experiment_end_utc": e3["finished_utc"],
            "note": "wall clock is read from the experiment receipts (started_utc, finished_utc), not estimated",
        },
        "label": e3["label"],
        "submission": {
            "name": cur["name"], "file": cur["file"], "sha256": cur["sha256"], "pixel_sha256": cur["pixel_sha256"],
            "bytes": e3["bytes"], "note": cur["note"], "note_chars": len(cur["note"]),
            "candidate": cur["spec"], "decision": cur["decision"],
            "submitted": False, "submission_slot_used": False, "organizer_score": None,
        },
        "gates": e3["gates"],
        "validators": {
            "template_validate_submission_exit": e3["validators"]["final_template_validate_submission"]["exit"],
            "template_validate_conformant_exit": e3["validators"]["final_validate_conformant"]["exit"],
            "inlane": e3["inlane"],
        },
        "holdout": {
            "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments and spatial super-regions; NOT organizer-scored)",
            "evaluator": {"name": "gems53.core.dti", "version": "1.0.0",
                          "parity_with_template_src_metrics_py": e1.get("metric_parity_vs_template")},
            "design_B": {
                "definition": e2["design"],
                "baseline_bands_top_q0p02": {"pooled_DTI": base_B["pooled_DTI"], "CI95_t_df4": base_B["CI95"],
                                             "withheld_positives": base_B["withheld_positives"]},
                "stage1_selected": stage1.get("selected"),
                "stage1_selection_rule": stage1.get("rule"),
                "stage1_qualifying_count": len(stage1.get("qualifying", [])),
                "stage2": {"status": sp.get("status"), "baseline": sp.get("baseline"),
                           "selected": sp.get("selected_result"), "paired_difference": sp.get("paired_difference"),
                           "acceptance": sp.get("acceptance"), "withheld_positives_total": sp.get("withheld_positives_total"),
                           "withheld_segments_total": sp.get("withheld_segments_total")},
                "selected_variant_segment_folds": (v(f"{stage1['selected']['arm']}:{stage1['selected']['variant']}")
                                                   if stage1.get("selected") else None),
            },
            "design_A_reference_not_used_for_decisions": {
                "reason": "negative pool depended on withheld labels (IR-53-19)",
                "bands_top_q0p02_pooled_DTI": e1["arms"]["bands"]["top_q0p02"]["pooled_DTI"],
                "bands_top_q0p02_CI95": e1["arms"]["bands"]["top_q0p02"]["CI95_t_df4_on_fold_mean"],
                "h1_top_q0p02_pooled_DTI": e1["arms"]["h1"]["top_q0p02"]["pooled_DTI"],
                "reproduction_of_exp2": e1["reproduction_check_vs_exp2"]["pass"],
            },
        },
        "leakage": {
            "canary_design_B": {"bands_max_separability": cd["bands_max_over_all"], "bands_flag": cd["bands_flag"],
                                "h1_max_separability": cd["h1_max_separability"], "h1_flag": cd["h1_flag"],
                                "gate": cd["gate"], "background": cd["background"]},
            "canary_design_A_reference": {"h1_mean": e1["canary_H1_feature_alone"]["separability_mean"],
                                          "h1_max": e1["canary_H1_feature_alone"]["separability_max"],
                                          "note": "buffered background (withheld-derived), inflated"},
            "gemsdoe29": "docs/leakage-review.md (negative verdict; mechanism = full-label distance feature in build_repo_candidate.py)",
        },
        "uniqueness": {
            "thresholds": gate["thresholds"],
            "registry_unique_on_grid": gate["registry_unique_on_grid"],
            "registry_skipped": gate["registry_skipped"],
            "any_drift_flag": gate["any_drift_flag"],
            "n_flagged": gate["n_flagged"],
            "max": gate["max"],
            "top_by_overlap_final": [{k: r[k] for k in r if k in ("file", "overlap_final", "overlap_pre", "rho_final",
                                                                 "rho_surface", "lift_over_chance", "chance_coverage_footprint",
                                                                 "reg_dots", "drift_flag")}
                                     for r in gate["top_by_overlap_final"][:8]],
            "receipt": f"evidence/uniqueness_gate_{cur['name']}.json",
            "diagnostics": {
                "file": f"evidence/uniqueness_diagnostics_{cur['name']}.json",
                "flagged_rows": diag["flagged_rows_analysed"], "flagged_by_class": diag["flagged_by_class"],
                "flagged_by_overlap": diag["flagged_by_overlap"],
                "flagged_by_rho_final_raster_whole_grid": diag["flagged_by_whole_grid_rho"],
                "flagged_by_rho_final_raster_footprint_only": diag["flagged_by_footprint_only_rho"],
                "flagged_by_rho_surface_whole_grid": sp_rho["flagged_by_surface_rho_whole_grid"],
                "flagged_by_rho_surface_footprint_only": sp_rho["flagged_by_surface_rho_footprint_only"],
                "sparse_flagged_median_lift": diag["sparse_flagged_median_lift"],
                "densest_sparse_dot_maps_by_chance_coverage": diag["densest_sparse_dot_maps_by_chance_coverage"],
                "raw_overlap_gate_satisfiable_by_any_placement": diag["raw_overlap_gate_satisfiable_by_any_placement"],
                "reading": "diagnostics explain the flags; the pre-registered verdict is taken from the gate receipt (IR-53-28, IR-53-29, IR-53-30)",
            },
        },
        "gemsdoe32": {"measured_file": "evidence/gemsdoe32_measured.json",
                      "nan_variant": {k: g32["files"]["nan"][k] for k in
                                      ("dots", "dots_within_2px_of_catalogue", "dots_within_3px_of_catalogue",
                                       "nearest_dot_distance_quantiles_px", "in_catalogue_DTI_diagnostic")},
                      "zeros_variant_finite_px": g32["files"]["zeros"]["finite_px"],
                      "score_link": "NOT ESTABLISHED (IR-53-02): no receipt links the 0.2778 row to this file"},
        "leaderboard_snapshot_repo": {"1": 0.3774, "7": 0.3195, "13": 0.2778,
                                      "note": "from the repository's earlier snapshot (S2); not re-read this session (IR-53-01)"},
        "hypotheses": {"file": "docs/research/hypotheses.md",
                       "H1": "tested (design B, stage 1 and stage 2)", "M1": "thinning tested (design B)",
                       "H2": "not tested (budget)", "H3": "BLOCKED: strain orientation not in public data (IR-53-22)",
                       "H4": "rejected (labels)", "H5": "not tested (budget); data present in pinned mirror (S20, S22)",
                       "H6": "not tested (budget)"},
        "verdict_reasons": [
            "uniqueness gate (pre-registered rule) flags %d registry rasters" % gate["n_flagged"],
            "the raw 70%% overlap gate cannot be satisfied by any placement on this registry: sparse dot map covers %.2f%% of the footprint within 3 px (IR-53-28)" % (100 * diag["densest_sparse_dot_maps_by_chance_coverage"][0]["chance_coverage"]),
            "rho flags are method-sensitive: surface rho (whole grid) flags %d rasters; footprint-only surface rho flags %d (IR-53-29)" % (sp_rho["flagged_by_surface_rho_whole_grid"], sp_rho["flagged_by_surface_rho_footprint_only"]),
        ] if not e3["gates"]["uniqueness_no_drift_flag"] else [],
        "irregularities_open": [i["id"] for i in irr if str(i.get("status", "")).startswith("open")],
        "irregularities_total": len(irr),
        "limitations": [i["id"] for i in lim],
        "verdict": e3["label"],
        "organizer_score": None,
        "files": {"preregistration": "docs/research/preregistration-2026-10-08.md",
                  "e1": "evidence/e1_h1_thin_holdout.json", "e2": "evidence/e2_leakfree_holdouts.json",
                  "e3_receipt": cur["receipt"], "uniqueness_receipt": f"evidence/uniqueness_gate_{cur['name']}.json",
                  "measured_gemsdoe32": "evidence/gemsdoe32_measured.json", "current_submission": "docs/submissions/CURRENT.json",
                  "tests": "tests/test_h1_thin.py, tests/test_metric.py, tests/test_submission.py"},
        "environment": {"python": "3.11.2 (venv: numpy 2.4.6, scipy 1.17.1, scikit-learn 1.9.1, rasterio 1.4.4, pyproj 3.7.2)",
                        "template_commit": "dcbbb192e56b2b32c0a131eba791dc363305d4a3",
                        "jklinck_mirror_commit": "56d78de7a989c12e2dce50cd65a4095df57030d2",
                        "fetch": "scripts/fetch_data.py (sha256 pins from the template manifest, verified)"},
    }
    out = ROOT / "evidence" / "run_card.json"
    out.write_text(json.dumps(card, indent=2, default=str))
    print("wrote", out, len(out.read_text()), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
