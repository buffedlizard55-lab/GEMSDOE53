#!/usr/bin/env python3
"""Derive the registered secondary exchange summary from the frozen R3 fold receipt."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/holdout_r3_paired_profile.json"
DEST = ROOT / "evidence/cotraining_summary_r3.json"


def main() -> int:
    report = json.loads(SOURCE.read_text())
    cotrain = report["cotraining"]
    folds = report["folds"]
    arms = {
        "view_A": "view_A",
        "view_B_paired_shoulder": "view_B_paired_shoulder",
    }
    rows = []
    for donor, target in (("view_A", "view_B_paired_shoulder"),
                          ("view_B_paired_shoulder", "view_A")):
        baseline_key = arms[target]
        fold_results = []
        for fold in folds:
            exchange_fold = next(r for r in cotrain["rounds"] if r["fold"] == fold["fold"])
            direction = next(d for d in exchange_fold["directions"] if d["donor_view"] == donor)
            baseline = float(fold["arms"][baseline_key]["dti"])
            # A zero-pseudo-pixel fold would be the unchanged baseline; preserve it rather than
            # dropping that fold from the paired summary.
            after = float(direction.get("dti_after_exchange", baseline))
            fold_results.append(dict(
                fold=int(fold["fold"]),
                pseudo_pixels=int(direction["pixels"]),
                baseline_dti=baseline,
                after_exchange_dti=after,
                paired_lift=after - baseline,
                positive=bool(after > baseline),
                all_pseudo_pixels_in_training=bool(direction["pseudo_pixels_all_in_training"]),
                evaluation_pixels=int(direction["evaluation_pixels"]),
            ))
        mean_lift = sum(row["paired_lift"] for row in fold_results) / len(fold_results)
        rows.append(dict(
            donor_view=donor,
            receiver_view=target,
            baseline_arm=baseline_key,
            mean_baseline_dti=sum(row["baseline_dti"] for row in fold_results) / len(fold_results),
            mean_after_exchange_dti=sum(row["after_exchange_dti"] for row in fold_results) / len(fold_results),
            mean_paired_lift=mean_lift,
            positive_folds=sum(row["positive"] for row in fold_results),
            total_folds=len(fold_results),
            pseudo_pixels=sum(row["pseudo_pixels"] for row in fold_results),
            all_pseudo_pixels_training_only=all(row["all_pseudo_pixels_in_training"] for row in fold_results),
            evaluation_pseudo_pixels=sum(row["evaluation_pixels"] for row in fold_results),
            folds=fold_results,
        ))
    out = dict(
        source_receipt="evidence/holdout_r3_paired_profile.json",
        preregistration_sha256=report["preregistration_sha256"],
        enabled=bool(cotrain["enabled"]),
        used_in_primary=False,
        independence_gate_reason=cotrain["reason"],
        directions=rows,
        interpretation="Secondary diagnostic only. Weak catalogue-zero proxy-error correlations allowed exchange under the registered numeric gate but do not prove conditional independence or view sufficiency. Neither direction is promoted into the primary artifact.",
        slots_used=0,
        public_score_forecast=None,
    )
    DEST.write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    print(json.dumps([{k: v for k, v in row.items() if k != "folds"} for row in rows], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
