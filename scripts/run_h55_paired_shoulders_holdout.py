#!/usr/bin/env python3
"""Run only preregistered H55-1 vs matched View-B spatial holdout.

This research runner is not a submission builder. It fails closed through the
H55 input/protocol preflight and never writes a TIFF, changes a pointer, uploads,
or makes a public-score forecast.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import rasterio

import run_structural_pipeline as R2
from gems52 import spatial, structural

REG = ROOT / "registry/h55_paired_shoulders_preregistration.json"
PARENT = ROOT / "registry/r2_preregistration.json"
WORK = ROOT / "work/h55_paired_shoulders"
FEATURES = WORK / "features"
RECEIPT = ROOT / "evidence/h55_paired_shoulders_holdout.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    tmp.replace(path)


def current_feature_manifest_ok() -> bool:
    path = FEATURES / "manifest.json"
    if not path.is_file():
        return False
    try:
        manifest = json.loads(path.read_text())
        inputs = manifest["inputs"]
        return bool(
            manifest.get("h55_paired_shoulders_included") is True
            and len(manifest.get("h55_paired_shoulder_features", [])) == 9
            and len(manifest.get("view_B_h55_paired_shoulders", [])) == len(manifest.get("view_B", [])) + 9
            and inputs.get("features_sha256") == structural.digest(ROOT / "data/training_features.tif")
            and inputs.get("sample_sha256") == structural.digest(ROOT / "data/sample_submission.tif")
            and inputs.get("h55_paired_shoulders_source_sha256") == structural.digest(ROOT / "src/gems52/h55_paired_shoulders.py")
            and inputs.get("structural_source_sha256") == structural.digest(ROOT / "src/gems52/structural.py")
        )
    except (KeyError, OSError, ValueError, TypeError):
        return False


def load_catalogue(store) -> np.ndarray:
    with rasterio.open(ROOT / "data/labels.tif") as src:
        if src.count != 1 or (src.height, src.width) != store.valid.shape:
            raise ValueError("labels changed after protocol preflight")
        band = src.read(1, masked=True)
        return (~np.ma.getmaskarray(band)) & (band.data == 1)


def run() -> dict:
    checker = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_h55_paired_shoulders_protocol.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if checker.stdout:
        print(checker.stdout, end="")
    if checker.stderr:
        print(checker.stderr, file=sys.stderr, end="")
    gate_path = ROOT / "evidence/h55_paired_shoulders_protocol_gate.json"
    if not gate_path.is_file():
        raise RuntimeError("protocol checker did not write its receipt")
    preflight = json.loads(gate_path.read_text())
    if checker.returncode != 0 or preflight.get("status") != "READY_FOR_PREREGISTERED_HOLDOUT_ONLY":
        raise RuntimeError("H55 protocol gate blocked; no feature build/model/holdout was started")

    # Do not spend compute on an accidental duplicate. A new code/data experiment needs a
    # new preregistration; the frozen result remains immutable.
    if RECEIPT.is_file():
        existing = json.loads(RECEIPT.read_text())
        same_registration = existing.get("preregistration_sha256") == structural.digest(REG)
        same_parent = existing.get("parent_preregistration_sha256") == structural.digest(PARENT)
        expected_inputs = {name: report.get("sha256") for name, report in preflight.get("input_reports", {}).items()}
        if existing.get("status") == "COMPLETED_RESEARCH_HOLDOUT" and same_registration and same_parent:
            if existing.get("input_sha256") != expected_inputs:
                raise RuntimeError("core inputs changed since H55-1; new preregistration required, no fit started")
            log("matching H55-1 holdout already completed under this registration and input set; reusing receipt without refit")
            return existing

    if not current_feature_manifest_ok():
        log("building H55 feature store from integrity-checked core inputs")
        structural.build(dest=FEATURES, include_h55_shoulders=True, log=print)
    store = structural.FeatureStore(FEATURES)
    if (not store.manifest.get("h55_paired_shoulders_included")
            or len(store.manifest.get("h55_paired_shoulder_features", [])) != 9):
        raise ValueError("H55 paired-shoulder feature store does not match the preregistered arm")
    cat = load_catalogue(store)
    valid = store.valid
    candidate_names = store.manifest["view_B_h55_paired_shoulders"]
    control_names = store.manifest["view_B"]
    settings = json.loads(PARENT.read_text())
    registration = json.loads(REG.read_text())
    fold_rows = []

    for fold in spatial.folds(cat, valid, settings["buffer_px"]):
        fi = int(fold["fold"])
        log(f"fold {fi}: {fold['receipt']}")
        rows, y, sample = R2.training_rows(
            cat, valid, fold["train"], fold["visible"], settings["seed"] + fi
        )
        predictions = {}
        for arm, names in (("view_B", control_names), ("view_B_h55_paired_shoulders", candidate_names)):
            log(f"fold {fi}: fitting {arm} ({len(names)} features; {len(rows)} identical training rows)")
            model = R2.fit(store, rows, y, names, settings["seed"] + fi)
            predictions[arm] = R2.predict(store, model, names, fold["region"])
            del model
        scores = {}
        for arm in ("view_B", "view_B_h55_paired_shoulders"):
            field = R2.prior_adjust(predictions[arm], sample["catalogue_prior"])
            placed, placement = R2.place(
                field, fold["region"], fold["visible"], valid,
                settings["primary_budget_global_pixels"],
            )
            scores[arm] = R2.score_fold(
                placed, fold["truth"], fold["region"], fold["visible"]
            )
            scores[arm]["placement"] = placement
            del placed, field
        lift = float(scores["view_B_h55_paired_shoulders"]["dti"] - scores["view_B"]["dti"])
        fold_rows.append({
            "fold": fi,
            "receipt": fold["receipt"],
            "training_sample": sample,
            "scores": scores,
            "paired_dti_lift": lift,
            "same_training_rows_seed_and_learner": True,
        })
        log(f"fold {fi}: paired H55 lift {lift:+.6f}")
        del predictions

    if len(fold_rows) != registration["holdout_protocol"]["outer_folds"]:
        raise ValueError("completed fold count differs from preregistration")
    control_mean = float(np.mean([r["scores"]["view_B"]["dti"] for r in fold_rows]))
    candidate_mean = float(np.mean([r["scores"]["view_B_h55_paired_shoulders"]["dti"] for r in fold_rows]))
    mean_lift = candidate_mean - control_mean
    positive = sum(r["paired_dti_lift"] > 0 for r in fold_rows)
    thresholds = registration["decision_gate"]
    scientific_pass = (
        mean_lift >= thresholds["minimum_mean_dti_lift_over_matched_view_B"]
        and positive >= thresholds["minimum_positive_outer_folds"]
    )
    result = {
        "generated_utc": utc_now(),
        "status": "COMPLETED_RESEARCH_HOLDOUT",
        "holdout_run": True,
        "model_fit": True,
        "portal_upload_performed": False,
        "preregistration_sha256": structural.digest(REG),
        "parent_preregistration_sha256": structural.digest(PARENT),
        "protocol_gate_sha256": structural.digest(gate_path),
        "feature_manifest_sha256": structural.digest(FEATURES / "manifest.json"),
        "input_sha256": {name: report.get("sha256") for name, report in preflight.get("input_reports", {}).items()},
        "protocol": {
            "folds": registration["holdout_protocol"]["outer_folds"],
            "buffer_px": registration["holdout_protocol"]["buffer_px"],
            "feature_support_px": store.manifest["support_px"],
            "external_data_used": False,
            "same_rows_seed_and_learner_for_candidate_control": True,
            "primary_budget_global_pixels": settings["primary_budget_global_pixels"],
            "negative_class": settings["negative_class"],
        },
        "arms": {
            "matched_view_B_mean_dti": control_mean,
            "h55_paired_shoulders_mean_dti": candidate_mean,
            "mean_dti_lift": mean_lift,
        },
        "positive_outer_folds": positive,
        "total_outer_folds": len(fold_rows),
        "scientific_holdout_gate_pass": bool(scientific_pass),
        "slot_gate": {
            "approved_for_weekly_slot": False,
            "submission_slots_used": 0,
            "scientific_gate_pass": bool(scientific_pass),
            "minimum_mean_lift": thresholds["minimum_mean_dti_lift_over_matched_view_B"],
            "minimum_positive_folds": thresholds["minimum_positive_outer_folds"],
            "reason": "Research holdout only; even a pass does not establish full-inventory uniqueness, independent confirmation, organizer acceptance or slot approval." if scientific_pass else "H55-1 did not pass its preregistered matched-control gate; do not spend a weekly slot.",
        },
        "folds": fold_rows,
        "no_public_score_forecast": True,
        "score_mapping_authenticated": False,
        "organizer_input_bytes_authenticated": False,
        "caveats": [
            "Inputs are SHA-pinned owner-supplied mirrors, not organizer-authenticated bytes.",
            "Catalogue-zero is not verified geological absence.",
            "Original connected raster components are spatial proxies, not authenticated fault identities.",
            "This local catalogue-recovery instrument is not organizer new-fault evaluation.",
            "A passing four-fold proxy gate is not a public competition-score improvement.",
            "No submission TIFF was built and no portal slot was used.",
        ],
    }
    write_json(RECEIPT, result)
    log(f"H55-1 mean lift {mean_lift:+.6f}; positive folds {positive}/4; slot approval FALSE")
    return result


def main() -> int:
    os.chdir(ROOT)
    try:
        run()
    except Exception as exc:
        log(f"STOP: {type(exc).__name__}: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
