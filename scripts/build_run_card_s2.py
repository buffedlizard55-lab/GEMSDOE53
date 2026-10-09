#!/usr/bin/env python3
"""Build the session-2 run card (one JSON) from the evidence files. Protocol item 5.

Verdict logic (pre-registered verdict matrix, preregistration-2026-10-09-session2.md section 1):
  promote       <- corrected gate PASS AND stage-2 acceptance AND validators AND canary clean
  negative      <- otherwise (negative results are deliverables)
The card never claims an organizer score.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def J(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def main() -> int:
    cur = J("docs/submissions/CURRENT.json")
    s2 = J("evidence/s2_c1_holdout.json")
    s3 = J("evidence/s3_c1_build_receipt.json")
    gate = J("evidence/uniqueness_gate_v2_session2.json")
    val = J("evidence/s2_validator_receipt.json")
    assert cur and s2 and s3, "missing evidence"

    canary_ok = s2.get("canary_S2_E1", {}).get("flag") == "pass"
    sp = s2.get("spatial_confirmation", {})
    stage2_ok = bool(sp.get("acceptance", {}).get("accepted")) if sp.get("status") == "COMPLETED" else False
    gate_ok = bool(gate and gate.get("corrected_pass"))
    validators_ok = bool(val and val.get("all_ok"))
    verdict = "promote" if (canary_ok and stage2_ok and gate_ok and validators_ok) else "negative"

    base = s2.get("baseline_same_run", {})
    sel = (s2.get("segment_selection") or {}).get("selected") or {}
    d = sp.get("paired_difference", {}) if sp.get("status") == "COMPLETED" else {}
    card = {
        "schema": "gems53.run_card.session2.v1",
        "session": "2026-10-09 session 2, branch arena/dc236d07-gemsdoe53",
        "preregistration": "docs/research/preregistration-2026-10-09-session2.md",
        "lane": "C1 conductivity-magnetic cross-scale edge coherence (bc1 arm; no catalogue feature)",
        "hypothesis": {
            "id": "C1",
            "statement": "Co-located, co-oriented linear edges in the conductivity surface (band 17) and reduced-to-pole "
                         "magnetics (band 2), measured by energy-gated multi-scale structure-tensor agreement, rank buried/"
                         "covered faults that are absent from the USGS/INGENIOUS catalogue.",
            "mechanism": "A concealed fault juxtaposes magnetic units (linear RTP edge) and hosts a conductive damage zone "
                         "(linear conductivity edge). Requiring both fields to agree at the same place and orientation rejects "
                         "single-field artifacts. Fourteen label-free features; HGB trained with design-B leak-free sampling.",
            "named_non_fault_mimic": "Volcanic dikes/sills and lithologic contacts produce co-located magnetic + conductivity "
                                     "edges; pluvial-lake paleoshorelines can align conductivity gradients. A catalogue holdout "
                                     "cannot distinguish these; the mimics are named here as required.",
            "scope_note": "Holdout truth is the withheld known-fault catalogue (IR-53-42, L-31): catalogue recovery is an upper "
                          "bound for performance on the competition's unmapped targets.",
        },
        "budget": {"experiments_limit": 3, "experiments_used": 3,
                   "experiments": ["S2-E1 canary (14 C1 features, design B)",
                                    "S2-E2 design-B holdout (stage-1 segment folds + stage-2 spatial confirmation)",
                                    "S2-E3 build + validators + uniqueness gate v2 (not a holdout experiment)"],
                   "wall_clock_limit_hours": 2},
        "holdout_headline": {
            "label_type": "HOLDOUT-DTI (proxy; NOT organizer-scored)",
            "evaluator": "gems53.core.dti v1.0.0 (template-metric parity abs diff 1.3e-13, session-1 E1)",
            "canary_max_separability": s2.get("canary_S2_E1", {}).get("max_over_all_features"),
            "canary_flag": s2.get("canary_S2_E1", {}).get("flag"),
            "withheld_positives": base.get("withheld_positives"),
            "baseline_same_run_bands_top_q0p02": {"pooled_DTI": base.get("pooled_DTI"), "CI95": base.get("CI95")},
            "selected_stage1": sel,
            "stage2": (None if sp.get("status") != "COMPLETED" else {
                "baseline_pooled_DTI": sp["baseline"]["pooled_DTI"],
                "selected_pooled_DTI": sp["selected_result"]["pooled_DTI"],
                "paired_mean_diff": d.get("mean_fold_diff"),
                "paired_CI95": d.get("CI95"),
                "accepted": sp["acceptance"]["accepted"],
                "withheld_positives_total": sp.get("withheld_positives_total"),
                "withheld_segments_total": sp.get("withheld_segments_total"),
            }),
        },
        "uniqueness_headline": (None if gate is None else {
            "gate_version": "v2 (GD-1: raw literal values archived + corrected reading decides)",
            "verdict": gate["verdict"],
            "registry_unique_on_grid": gate["registry_unique_on_grid"],
            "n_flagged_corrected": gate["n_flagged_corrected"],
            "n_flagged_raw_archived": gate["n_flagged_raw"],
            "max_rho_surface_footprint": gate["max"]["rho_surface_footprint"],
            "max_rho_surface_whole_grid_raw": gate["max"]["rho_surface_whole_grid"],
            "max_overlap_final": gate["max"]["overlap_final"],
            "max_lift_over_chance": gate["max"]["lift_over_chance"],
        }),
        "submission": {
            "name": cur["name"],
            "file": cur["file"],
            "note": cur["note"],
            "note_chars": cur.get("note_chars"),
            "sha256_file": cur.get("sha256"),
            "sha256_pixels": cur.get("pixel_sha256"),
            "bytes": cur.get("bytes"),
            "label": cur["label"],
            "download_ok": cur.get("download_allowed_for_research", True),
            "submit_ok": cur.get("submit_allowed", False),
            "organizer_score": None,
            "submitted": False,
            "submission_slot_used": False,
        },
        "validators": val,
        "gates": cur.get("gates", {}),
        "verdict": verdict,
        "verdict_reasons": [
            f"canary_clean={canary_ok}", f"stage2_spatial_accept={stage2_ok}",
            f"uniqueness_corrected_gate={gate_ok}", f"validators={validators_ok}",
            "no organizer score exists for any GEMSDOE53 file; nothing submitted",
        ],
        "irregularities_session2": ["IR-53-50 (GD-1 gate interpretation, open)",
                                    "IR-53-51 (user-reported rejection unreproducible from shipped files, open)",
                                    "IR-53-52 (prompt-injection content observed in fetched web page, logged)"],
    }
    out = ROOT / "evidence" / "run_card_session2.json"
    out.write_text(json.dumps(card, indent=1))
    print(json.dumps({"verdict": verdict, "label": cur["label"]}, indent=1))
    print("wrote", out)
    return 0


if __name__ == "__main__":
    main()
