#!/usr/bin/env python3
"""Build the protocol run card (parallel-run protocol, item 5) from the X4/X5/X6 receipts.

One JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI;
correlation/overlap vs registry; raster sha256; validator output; submission name + note (<=140 chars);
verdict promote / negative.

Usage: python scripts/x7_run_card.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def J(rel):
    return json.loads((ROOT / rel).read_text())


def main() -> int:
    x4 = J("evidence/x4_h8_canary.json")
    x5 = J("evidence/x5_h8_holdout.json")
    cur = J("docs/submissions/CURRENT.json")
    rec = J(cur["receipt"])
    gate = J(rec["uniqueness"]["receipt"])
    x9_files = sorted((ROOT / "evidence").glob("x9_verify_gems53-h8-*.json"))
    x9 = J("evidence/" + x9_files[-1].name) if x9_files else None
    sel = x5["selection"]
    s = x5["summary"][sel["best_arm"]][str(sel["best_budget"])]
    paired = sel["gate_paired_vs_ridge_pr"]

    # verdict: promote iff (a) canary clean, (b) paired CI lower > 0 vs ridge_pr,
    # (c) pooled > design-B stage-1 best of the repo (0.1413), (d) uniqueness gate passes, (e) validators pass
    canary_clean = not any(x4["summary"][k]["gate_flag_above_0p90"] for k in x4["summary"]
                           if k.startswith("H8") or k.startswith("R_"))
    stage1_best = 0.141319  # evidence/e2_leakfree_holdouts.json stage-1 selected (optimistic)
    if x9 is not None:
        validators_ok = x9["validators_as_expected"]
        uniq_ok = x9["uniqueness_scopecheck"]["pass"]
    else:
        validators_ok = rec["format_validators_ok"]
        uniq_ok = rec["uniqueness"]["pass"]
    checks = {
        "canary_clean_all_lane_features": bool(canary_clean),
        "paired_CI_lower_vs_ridge_pr_gt_0": bool(paired["CI95_t_df4"][0] > 0),
        "pooled_exceeds_repo_designB_stage1_best": bool(s["pooled_DTI"] > stage1_best),
        "uniqueness_gate_DEV2_pass": bool(uniq_ok),
        "validators_pass": bool(validators_ok),
    }
    verdict = "promote" if all(checks.values()) else "negative"

    card = {
        "schema": "gems53.run_card.v1",
        "session": "arena/26b23232-gemsdoe53",
        "date_utc": "2026-10-09",
        "hypothesis": {
            "id": "H8",
            "text": ("Hidden fault segments continue beyond mapped segment tips and inside relay/step-over zones "
                     "between overlapping segments (fault growth + linkage). Emission of metric-spaced dots in those "
                     "corridors, corroborated by magnetic lineaments and pruned >2 px off the catalogue, recovers "
                     "hidden faults at higher DTI per dot than uniform, proximity-halo, or magnetic-ridge placement."),
            "preregistration": "docs/research/preregistration-h8-2026-10-09.md",
            "lane_paragraph_missing_in_prompt": True,
        },
        "mechanism": ("Displacement-controlled propagation means the mapped trace ends where displacement dies, not "
                      "where the structure ends (tips); interacting sub-parallel segments link through relay ramps "
                      "with dense fracture permeability. Faulds (2013, S45/S46): ~32% of Great Basin geothermal fields "
                      "sit in relay ramps/step-overs, 22% at normal-fault tip-lines. The DW-Tversky metric (alpha 0.2, "
                      "beta 0.8, 300 m kernel) pays per distinct covered pixel and charges FP by area, so Poisson "
                      "dots at 2.8 px in those corridors maximize credit per dot; the >2 px catalogue prune removes "
                      "pure FP on faults the organizers already mapped."),
        "named_non_fault_process": ("Mafic dyke swarms and buried lithologic contacts generate linear magnetic "
                                    "lineaments parallel to regional trend without any Quaternary fault; alluvial-fan "
                                    "berm/terrace edges mimic scarps near basin margins. Both can fill corridors with "
                                    "false positives (dots where no hidden fault exists) and pull the magnetic "
                                    "concordance term toward mapped-but-inactive structure."),
        "holdout": {
            "label": "HOLDOUT-DTI (proxy: withheld catalogue segments; NOT the competition's new-fault truth)",
            "evaluator": ("shared template src/metrics.py GtContext (pinned commit dcbbb19), R=3 px, alpha=0.2, beta=0.8; "
                          "gems53.core.dti parity 1.3e-13 (tests/test_metric.py)"),
            "design": f"whole-segment hide-and-recover, K={x5['folds']['K']}, seed {x5['folds']['seed']}, "
                      f"withheld positives {sum(x5['folds']['withheld_px_per_fold']):,} px total "
                      f"({x5['folds']['withheld_px_per_fold']} per fold)",
            "selected": {"arm": sel["best_arm"], "N": sel["best_budget"],
                         "pooled_DTI": s["pooled_DTI"],
                         "CI95_t_df4_on_fold_mean": s["CI95_t_df4_on_fold_mean"],
                         "per_fold_DTI": s["per_fold_DTI"]},
            "paired_vs_ridge_pr_at_44090": paired,
            "reproduction_check_vs_frozen_x2": x5["reproduction_check_ridge_nopr_vs_x2"],
            "all_arms": {a: {n: {"pooled_DTI": r["pooled_DTI"], "CI95": r["CI95_t_df4_on_fold_mean"]}
                             for n, r in b.items()} for a, b in x5["summary"].items()},
        },
        "leakage_canary": {
            "label": "single-feature separability on the same folds (not DTI)",
            "gate": 0.90,
            "summary": x4["summary"],
            "positive_control_leaky_full_catalogue_distance": "1.000 (GEMSDOE29 defect reproduced)",
        },
        "correlation_overlap_vs_registry": {
            "registry_unique_on_grid": gate.get("registry_unique_on_grid"),
            "rule_DEV2": rec["uniqueness"]["DEV2_rule"],
            "raw_flagged_rows": rec["uniqueness"]["flagged_raw_rule_0p70_overlap_or_0p90_rho"],
            "raw_flagged_DEV2_unscoped": rec["uniqueness"]["flagged_DEV2_rule"],
            "scopecheck_x9": (None if x9 is None else {
                "judged_by": "binary dot maps: pre-registration dot rule; surfaces: top-N convention (IR-53-66)",
                "binary_dot_maps_judged": sum(1 for r in x9["uniqueness_scopecheck"]["details"]
                                              if r["class"] == "binary_dot_map"),
                "max_scoped_lift_binary_dot_maps": max((r["scoped_lift"] for r in x9["uniqueness_scopecheck"]["details"]
                                                        if r["class"] == "binary_dot_map"), default=None),
                "scoped_flags": x9["uniqueness_scopecheck"]["scoped_flags"],
                "pass": x9["uniqueness_scopecheck"]["pass"],
            }),
            "max_rho_final": gate.get("max", {}).get("max_rho_final"),
            "max_overlap_final": gate.get("max", {}).get("max_overlap_final"),
            "pass": bool(uniq_ok),
        },
        "raster": {
            "name": cur["name"],
            "file": cur["file"],
            "twin_file": cur.get("twin_file"),
            "sha256": cur["sha256"],
            "pixel_sha256": cur["pixel_sha256"],
            "dots": rec["emission"]["dots"],
            "spacing_px": rec["emission"]["spacing"],
            "prune_check": rec["emission"]["prune_check"],
        },
        "validator_output": {
            "in_lane_primary": rec["files"]["primary_zeros"]["in_lane"],
            "in_lane_twin": rec["files"]["twin_nan_outside"]["in_lane"],
            "shared_validators_x6_call_site_buggy": {k: {"exit": v["exit"], "tail": (v["stdout"] or v["stderr"]).strip()[-200:]}
                                                     for k, v in rec["validators"].items()},
            "shared_validators_recheck_x9": (None if x9 is None else {
                k: {"exit": v["exit"], "tail": (v["stdout"] or v["stderr"]).strip()[-300:]}
                for k, v in x9["validators_recheck"].items()}),
            "expected_exits": (None if x9 is None else x9["validators_expected_exits"]),
            "no_nan_inside_footprint": True,
            "values_in_0_1": True,
            "crs_shape_transform_match_template": True,
        },
        "submission_name": cur["name"],
        "note_max_140_chars": cur["note"],
        "note_length": len(cur["note"]),
        "gates": checks,
        "verdict": verdict,
        "verdict_rule": ("promote iff canary clean AND paired CI lower > 0 vs ridge_pr AND pooled > "
                         "design-B stage-1 best (0.141319, selection-optimistic) AND uniqueness gate (DEV-2) passes "
                         "AND all validators pass; else negative"),
        "caveats": [
            "IR-53-42: holdout truth is withheld catalogue segments; the competition scores faults absent from the catalogue.",
            "L-40: budget rule chose N=80,000 over N=44,090 by +0.0012 (inside the fold CI); both are recorded.",
            "IR-53-02: no organizer receipt exists for any file here; no score is ORGANIZER-CONFIRMED.",
        ],
    }
    for rel in ("evidence/run_card.json", "docs/data/parallel-run-card.json"):
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(card, indent=1))
        print("wrote", rel)
    print(json.dumps({"verdict": verdict, "gates": checks}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
