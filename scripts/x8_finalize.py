#!/usr/bin/env python3
"""X8 - finalize: write CURRENT.json from the X6 receipt, build the run card and the site.

Usage: python scripts/x8_finalize.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    receipts = sorted((ROOT / "evidence").glob("x6_candidate_receipt_gems53-h8-*.json"))
    if not receipts:
        raise SystemExit("no x6 receipt found")
    rec = json.loads(receipts[-1].read_text())
    name = rec["name"]
    x9_files = sorted((ROOT / "evidence").glob("x9_verify_gems53-h8-*.json"))
    x9 = json.loads(x9_files[-1].read_text()) if x9_files else None
    final_label = x9["final_label"] if x9 else rec["label"]
    validators_ok = x9["validators_as_expected"] if x9 else rec["format_validators_ok"]
    uniq_pass = x9["uniqueness_scopecheck"]["pass"] if x9 else rec["uniqueness"]["pass"]
    zeros_rel = "docs/downloads/" + Path(rec["files"]["primary_zeros"]["path"]).name
    nan_rel = "docs/downloads/" + Path(rec["files"]["twin_nan_outside"]["path"]).name
    cur = {
        "name": name,
        "file": zeros_rel,
        "twin_file": nan_rel,
        "sha256": rec["files"]["primary_zeros"]["sha256"],
        "twin_sha256": rec["files"]["twin_nan_outside"]["sha256"],
        "pixel_sha256": rec["files"]["primary_zeros"]["pixel_sha256"],
        "label": final_label,
        "note": rec["note"],
        "gates": {
            "holdout_gate_X5_paired_vs_ridge_CI_lower_gt_0": None,  # filled below
            "format_validators_all": validators_ok,
            "uniqueness_DEV2_no_drift_flag": uniq_pass,
            "canary_clean_for_features_in_model": None,  # filled below
        },
        "spec": {"arm": rec["selection_used"]["arm"], "variant": f"pr2_n{rec['selection_used']['N']}",
                 "N": rec["selection_used"]["N"], "kind": "poisson_dots_2.8px_pruned_gt2px_off_catalogue"},
        "decision": ("X5 pre-registered rule: highest pooled DTI at N=44090 among ridge_pr/h8_pr/halo_pr, "
                     "budget = that arm's better N; labelled by X6 gates (pre-registration-h8-2026-10-09.md)"),
        "receipt": "evidence/" + receipts[-1].name,
        "verify_receipt": ("evidence/" + x9_files[-1].name) if x9_files else None,
        "holdout": {"label": "HOLDOUT-DTI (proxy: withheld catalogue segments)",
                    "pooled_DTI": None, "organizer_score": None},
        "organizer_score": None,
        "submitted": False,
    }
    # attach the holdout numbers from x5 for the site
    x5 = json.loads((ROOT / "evidence" / "x5_h8_holdout.json").read_text())
    x4 = json.loads((ROOT / "evidence" / "x4_h8_canary.json").read_text())
    sel = x5["selection"]
    s = x5["summary"][sel["best_arm"]][str(sel["best_budget"])]
    cur["gates"]["holdout_gate_X5_paired_vs_ridge_CI_lower_gt_0"] = bool(sel["gate_paired_vs_ridge_pr"]["CI95_t_df4"][0] > 0)
    cur["gates"]["canary_clean_for_features_in_model"] = bool(not any(
        v["gate_flag_above_0p90"] for k, v in x4["summary"].items() if k.startswith("H8") or k.startswith("R_")))
    cur["holdout"] = {"label": "HOLDOUT-DTI (proxy: withheld catalogue segments; evaluator shared template GtContext R=3)",
                      "arm": sel["best_arm"], "N": sel["best_budget"],
                      "pooled_DTI": s["pooled_DTI"], "CI95_t_df4_on_fold_mean": s["CI95_t_df4_on_fold_mean"],
                      "withheld_positives_total": sum(x5["folds"]["withheld_px_per_fold"]),
                      "folds": x5["folds"]}
    for rel in ("docs/submissions/CURRENT.json", "docs/data/CURRENT.json"):
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cur, indent=1))
        print("wrote", rel)
    for script in ("scripts/x7_run_card.py", "scripts/build_site.py"):
        r = subprocess.run([sys.executable, str(ROOT / script)], capture_output=True, text=True)
        print(script, "exit", r.returncode)
        print(r.stdout[-800:], r.stderr[-800:])
        if r.returncode != 0:
            return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
