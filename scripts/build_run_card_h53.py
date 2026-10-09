#!/usr/bin/env python3
"""Assemble the session's single JSON run card (protocol item 5) from the committed receipts only."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def J(rel):
    return json.loads((ROOT / rel).read_text())


def main():
    cur = J("docs/submissions/CURRENT.json")
    sub = J(cur["receipt"])
    gate = J(cur["gate_receipt"])
    e1 = J("evidence/h53_e1_canary.json")
    e2 = J("evidence/h53_e2_holdout.json")
    e3 = J("evidence/h53_e3_build.json")
    geo = J("evidence/h53_e3_geometry_vs_b2.json")
    s1 = e2["stage1"]; s2 = e2["stage2"]
    card = {
        "session": "2026-10-09",
        "lane": "H53-HWVC (hanging-wall vector concordance); fallback build = H1 lane (bands + segment-exact catalogue distance)",
        "preregistration": "docs/research/preregistration-2026-10-09-hwvc.md",
        "budget": {"experiments_used": 3, "experiments": ["E1 canary", "E2 two-stage holdout", "E3 build"],
                   "session_start_utc": "2026-10-09T00:36Z", "e2_started_utc": e2["started_utc"],
                   "e3_finished_utc": e3["finished_utc"]},
        "hypothesis": "Normal faults down-drop and fill the hanging wall, so -grad(det_elev), -grad(iso_grav_anom), +grad(cond_surf) and "
                      "+grad(depth_to_base_surf) point to the same side; a fault sits where they are strong and co-directional.",
        "mechanism": "hanging-wall subsidence and sediment fill juxtapose low topography, low density, high conductivity and deep basement across one line",
        "non_fault_mimic": "depositional (unfaulted) range-front onlap or an erosional pediment contact between dense resistive bedrock and conductive alluvium",
        "leakage_canary": {"rule": "separability = max(AUC,1-AUC) > 0.90 => leakage", "flagged": e1["flagged"],
                           "max": dict(list(e1["max_separability_by_feature"].items())[:4])},
        "holdout": {
            "label": "HOLDOUT-DTI",
            "evaluator": f"{e2['evaluator']['name']} v{e2['evaluator']['version']} (alpha 0.2, beta 0.8, R 3 px)",
            "withheld_positives": e2["segment_folds"]["withheld_positives_total"],
            "stage1_segment_folds_M1": {"A_bands_H1": s1["M1_thin_bin_q0p10"]["A"]["pooled_DTI"], "A_CI95": s1["M1_thin_bin_q0p10"]["A"]["CI95_t_df4"],
                                        "B_plus_HWVC": s1["M1_thin_bin_q0p10"]["B"]["pooled_DTI"], "B_CI95": s1["M1_thin_bin_q0p10"]["B"]["CI95_t_df4"],
                                        "paired_B_minus_A": s1["M1_thin_bin_q0p10"]["paired_B_minus_A"]},
            "stage1_segment_folds_DS": {"A": s1["DS_flank2_sep2p8_n40000"]["A"]["pooled_DTI"], "A_CI95": s1["DS_flank2_sep2p8_n40000"]["A"]["CI95_t_df4"],
                                        "B": s1["DS_flank2_sep2p8_n40000"]["B"]["pooled_DTI"],
                                        "paired_B_minus_A": s1["DS_flank2_sep2p8_n40000"]["paired_B_minus_A"]},
            "stage2_spatial_M1": {"A": s2["M1_thin_bin_q0p10"]["A"]["pooled_DTI"], "B": s2["M1_thin_bin_q0p10"]["B"]["pooled_DTI"],
                                  "paired_B_minus_A": s2["M1_thin_bin_q0p10"]["paired_B_minus_A"]},
            "reproduction": e2["reproduction_check"],
            "promotion_rule": e2["promotion_rule"], "promote_B": e2["promote_B"],
        },
        "hwvc_verdict": "negative" if not e2["promote_B"] else "promote",
        "shipped_build": {"arm": e3["arm"], "dots": e3["dots"], "min_dist_to_catalogue_px": e3["min_dist_to_catalogue_px"],
                          "geometry_vs_0p2778_file": geo,
                          "non_fault_mimic": "lithologic contacts and alluvial-fan / range-front slope breaks running parallel to mapped faults; the model learns 'near a mapped fault' sleeves, so it also fires on these unfaulted contacts"},
        "registry": {"gate": gate["gate"], "unique_on_grid": gate["unique_on_grid"], "verdict": gate["verdict"],
                     "duplicates_v2": gate["duplicates_v2"],
                     "duplicates_v2_by_kappa": [dict(file=r["file"], mode=r["mode"], overlap=round(r["overlap"], 4), chance=round(r["chance"], 4), kappa=round(r["kappa"], 4))
                                                for r in sorted([r for r in gate["rows"] if r["duplicate_v2"]], key=lambda r: -r["kappa"])], "raw_rule_flag_count": gate["raw_rule_flag_count"],
                     "max_overlap_v2": gate["max_overlap_v2"][:3], "max_kappa": gate["max_kappa"][:3],
                     "max_rho_surface": gate["max_rho_surface"][:3], "max_rho_final": gate["max_rho_final"][:3]},
        "raster": {"file": cur["file"], "sha256": sub["sha256"], "bytes": sub["bytes"]},
        "validator": {"explicit_checks": sub["explicit_checks"], "explicit_all_pass": sub["explicit_all_pass"],
                      "template_validate_submission_exit": sub["template_validate_submission"]["exit"],
                      "template_validate_conformant_exit": sub["template_validate_conformant"]["exit"],
                      "control_0p2778_validate_conformant_exit": sub["control_organizer_accepted_zeros_file"].get("template_validate_conformant", {}).get("exit")},
        "submission": {"name": cur["name"], "note": cur["note"], "note_chars": len(cur["note"])},
        "verdict": cur["verdict"],
        "label": cur["label"],
        "why_not": cur.get("why_not"),
        "next_step": cur.get("next_step"),
        "ok_to_submit": cur["ok_to_submit"],
        "organizer_score": cur.get("organizer_score"),
    }
    (ROOT / "evidence" / "h53_run_card.json").write_text(json.dumps(card, indent=2))
    print(json.dumps({k: card[k] for k in ("hwvc_verdict", "verdict", "ok_to_submit")}, indent=1))


if __name__ == "__main__":
    main()
