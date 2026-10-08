#!/usr/bin/env python3
"""Fail-closed H55 input/protocol gate; this script never fits a model."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "registry/h55_paired_shoulders_preregistration.json"
PARENT = ROOT / "registry/r2_preregistration.json"
PIN_MANIFEST = ROOT / "registry/data_manifest.json"
RESTORE_RECEIPT = ROOT / "data/restore_receipt.json"
OUT = ROOT / "evidence/h55_paired_shoulders_protocol_gate.json"
ASSETS = {
    "training_features": ROOT / "data/training_features.tif",
    "labels": ROOT / "data/labels.tif",
    "sample_submission": ROOT / "data/sample_submission.tif",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check_registration(registration: dict, parent: dict, problems: list[str]) -> None:
    hp = registration.get("holdout_protocol", {})
    comparisons = {
        "seed": (hp.get("seed"), parent.get("seed")),
        "outer_folds": (hp.get("outer_folds"), parent.get("outer_folds")),
        "buffer_px": (hp.get("buffer_px"), parent.get("buffer_px")),
        "feature_support_px": (hp.get("feature_support_px"), parent.get("max_feature_support_px")),
        "primary_budget_global_pixels": (hp.get("primary_budget_global_pixels"), parent.get("primary_budget_global_pixels")),
        "max_training_negatives": (hp.get("max_training_negatives"), parent.get("max_training_negatives")),
        "negative_collar_px": (hp.get("negative_collar_px"), parent.get("negative_collar_px")),
    }
    for key, (actual, expected) in comparisons.items():
        if actual != expected:
            problems.append(f"H55 {key}={actual!r} does not inherit parent value {expected!r}")
    if hp.get("learner_settings") != parent.get("learner"):
        problems.append("H55 learner hyperparameters do not exactly inherit the parent registration")
    if hp.get("learner") != "HistGradientBoostingClassifier with parent registration settings; identical train/test rows, sample weights and random seeds for candidate and control":
        problems.append("H55 learner description changed; matched-control protocol review required")
    if hp.get("primary_control") != "view_B refit on the identical folds, training rows, learner settings and random seeds":
        problems.append("H55 primary control must be a fresh, matched view_B refit")
    gate = registration.get("decision_gate", {})
    if gate.get("minimum_mean_dti_lift_over_matched_view_B") != 0.005 or gate.get("minimum_positive_outer_folds") != 3:
        problems.append("H55 decision thresholds differ from the frozen 0.005 / 3-of-4 gate")
    if registration.get("portal_upload_performed") is not False:
        problems.append("preregistration must record that no portal upload was performed")
    if registration.get("numerical_public_score_forecast") is not None:
        problems.append("public-score forecast must remain null")
    if registration.get("primary_hypothesis") != "H55-1 paired DEM shoulders":
        problems.append("unexpected H55 primary candidate")
    hypotheses = registration.get("ranked_hypotheses", [])
    if len(hypotheses) < 3 or [h.get("rank") for h in hypotheses] != list(range(1, len(hypotheses) + 1)):
        problems.append("H55 requires at least 3 consecutively ranked hypotheses")
    if len({h.get("id") for h in hypotheses}) != len(hypotheses):
        problems.append("H55 hypothesis IDs must be unique")


def check_data(assets: dict[str, Path], pins: dict[str, dict], problems: list[str], missing: list[str]) -> dict:
    try:
        import numpy as np
        import rasterio
        from rasterio.windows import Window
    except Exception as exc:  # pragma: no cover - environment-specific
        problems.append(f"raster validation dependencies unavailable: {type(exc).__name__}: {exc}")
        return {}

    for name, path in assets.items():
        if not path.is_file():
            missing.append(str(path.relative_to(ROOT)))
    if not assets["sample_submission"].is_file():
        return {}

    reports: dict[str, dict] = {}
    with rasterio.open(assets["sample_submission"]) as ref:
        if ref.count != 1 or ref.width <= 0 or ref.height <= 0 or ref.crs is None:
            problems.append("sample_submission must be one band with a positive shape and defined CRS")
        ref_sig = (ref.width, ref.height, ref.crs, ref.transform)
        w, h = min(256, ref.width), min(256, ref.height)
        origins = ((0, 0), ((ref.width - w) // 2, (ref.height - h) // 2), (ref.width - w, ref.height - h))
        ref_valid_sample = 0
        for col, row in origins:
            block = ref.read(1, window=Window(col, row, w, h), masked=True)
            ref_valid_sample += int((~np.ma.getmaskarray(block) & np.isfinite(block.data)).sum())
        if ref_valid_sample == 0:
            problems.append("sample_submission has no valid cells in deterministic grid samples")
        template_pin = pins.get("sample_submission", {})
        template_sha = file_hash(assets["sample_submission"])
        template_bytes = assets["sample_submission"].stat().st_size
        if template_bytes != template_pin.get("bytes") or template_sha != template_pin.get("sha256"):
            problems.append("sample_submission byte count/SHA-256 differs from the integrity pin")
        reports["sample_submission"] = {
            "width": ref.width,
            "height": ref.height,
            "crs": str(ref.crs),
            "transform": list(ref.transform)[:6],
            "valid_cells_in_three_sample_windows": ref_valid_sample,
            "bytes": template_bytes,
            "sha256": template_sha,
            "matches_manifest_pin": template_sha == template_pin.get("sha256"),
        }

    for name in ("training_features", "labels"):
        path = assets[name]
        if not path.is_file():
            continue
        with rasterio.open(path) as src:
            sig = (src.width, src.height, src.crs, src.transform)
            if sig != ref_sig:
                problems.append(f"{name} grid/CRS/transform does not match sample_submission.tif")
            expected_bands = 19 if name == "training_features" else 1
            if src.count != expected_bands:
                problems.append(f"{name} has {src.count} bands; expected {expected_bands}")
            valid_samples = 0
            label_values: set = set()
            for col, row in origins:
                window = Window(col, row, w, h)
                band = src.read(1, window=window, masked=True)
                usable = ~np.ma.getmaskarray(band) & np.isfinite(band.data)
                valid_samples += int(usable.sum())
                if name == "labels":
                    label_values.update(np.unique(band.data[usable]).tolist())
            if valid_samples == 0:
                problems.append(f"{name} has no valid data in deterministic template-grid samples")
            if name == "labels" and (not label_values.issubset({0, 1, False, True}) or not {0, 1}.issubset(label_values)):
                problems.append(f"labels must contain both binary classes 0 and 1 in deterministic samples; found {sorted(map(str, label_values))[:12]}")
            if name == "training_features":
                for band_i in range(2, src.count + 1):
                    band_valid = False
                    for col, row in origins:
                        band = src.read(band_i, window=Window(col, row, w, h), masked=True)
                        if (~np.ma.getmaskarray(band) & np.isfinite(band.data)).any():
                            band_valid = True
                            break
                    if not band_valid:
                        problems.append(f"training_features band {band_i} has no valid values in deterministic sample windows")
            digest = file_hash(path)
            pin = pins.get(name, {})
            byte_count = path.stat().st_size
            if byte_count != pin.get("bytes") or digest != pin.get("sha256"):
                problems.append(f"{name} byte count/SHA-256 differs from the integrity pin")
            reports[name] = {
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "crs": str(src.crs),
                "transform": list(src.transform)[:6],
                "valid_cells_in_three_sample_windows_band1": valid_samples,
                "sampled_label_values": sorted(map(int, label_values)) if name == "labels" else None,
                "bytes": byte_count,
                "sha256": digest,
                "matches_manifest_pin": digest == pin.get("sha256"),
            }
    return reports


def check_restore_receipt(pins: dict[str, dict], problems: list[str]) -> dict:
    if not RESTORE_RECEIPT.is_file():
        problems.append("data/restore_receipt.json is missing; core input provenance receipt is required")
        return {"exists": False}
    receipt = json.loads(RESTORE_RECEIPT.read_text())
    by_id = {item.get("id"): item for item in receipt.get("files", [])}
    if receipt.get("all_ok") is not True:
        problems.append("data/restore_receipt.json does not report all_ok=true")
    for name in ASSETS:
        row = by_id.get(name)
        pin = pins.get(name, {})
        if not row or row.get("matches_pin") is not True or row.get("sha256") != pin.get("sha256") or row.get("bytes") != pin.get("bytes"):
            problems.append(f"restore receipt for {name} does not attest the current manifest pin")
    return {
        "path": str(RESTORE_RECEIPT.relative_to(ROOT)),
        "all_ok": receipt.get("all_ok"),
        "verified_against": receipt.get("verified_against"),
        "core_file_count": len(by_id),
    }


def main() -> int:
    problems: list[str] = []
    missing: list[str] = []
    registration = json.loads(REG.read_text())
    parent = json.loads(PARENT.read_text())
    manifest = json.loads(PIN_MANIFEST.read_text())
    pins = {item["id"]: item for item in manifest.get("files", [])}
    check_registration(registration, parent, problems)

    sys.path.insert(0, str(ROOT / "src"))
    try:
        from gems52.h55_paired_shoulders import paired_shoulder_features
        if not callable(paired_shoulder_features):
            problems.append("H55 paired-shoulder implementation is not callable")
    except Exception as exc:
        problems.append(f"cannot import H55 feature implementation: {type(exc).__name__}: {exc}")
    for path in (ROOT / "scripts/run_h55_paired_shoulders_holdout.py", ROOT / "tests/test_h55_paired_shoulders.py"):
        if not path.is_file():
            problems.append(f"required H55 implementation/test file is missing: {path.relative_to(ROOT)}")
    structural_source = (ROOT / "src/gems52/structural.py").read_text()
    for token in ("include_h55_shoulders=False", "view_B_h55_paired_shoulders", "paired_shoulder_features"):
        if token not in structural_source:
            problems.append(f"feature builder is missing H55 integration token: {token}")

    restore = check_restore_receipt(pins, problems)
    data_reports = check_data(ASSETS, pins, problems, missing)
    if problems:
        status = "BLOCKED_PROTOCOL_OR_INTEGRITY"
    elif missing:
        status = "BLOCKED_MISSING_REQUIRED_INPUTS"
    else:
        status = "READY_FOR_PREREGISTERED_HOLDOUT_ONLY"
    holdout_path = ROOT / "evidence/h55_paired_shoulders_holdout.json"
    existing_holdout = None
    if holdout_path.is_file():
        try:
            old = json.loads(holdout_path.read_text())
            expected_inputs = {name: report.get("sha256") for name, report in data_reports.items()}
            if (old.get("status") == "COMPLETED_RESEARCH_HOLDOUT"
                    and old.get("preregistration_sha256") == file_hash(REG)
                    and old.get("parent_preregistration_sha256") == file_hash(PARENT)
                    and old.get("input_sha256") == expected_inputs):
                existing_holdout = {
                    "path": str(holdout_path.relative_to(ROOT)),
                    "sha256": file_hash(holdout_path),
                    "scientific_holdout_gate_pass": old.get("scientific_holdout_gate_pass"),
                    "mean_dti_lift": old.get("arms", {}).get("mean_dti_lift"),
                    "positive_outer_folds": old.get("positive_outer_folds"),
                    "total_outer_folds": old.get("total_outer_folds"),
                    "same_registration_and_core_input_hashes": True,
                }
        except (OSError, ValueError, TypeError):
            existing_holdout = None
    if status == "READY_FOR_PREREGISTERED_HOLDOUT_ONLY" and existing_holdout:
        next_action = "Matching H55-1 holdout already completed; do not refit/retest under the same registration and input hashes. A new experiment needs a new preregistration."
    elif status == "READY_FOR_PREREGISTERED_HOLDOUT_ONLY":
        next_action = "Run scripts/run_h55_paired_shoulders_holdout.py; it performs only the preregistered matched holdout and never builds/uploads a TIFF."
    else:
        next_action = "Restore/repair the listed core inputs and rerun this fail-closed gate before any H55 fit or holdout."
    result = {
        "generated_utc": utc_now(),
        "status": status,
        "holdout_run": False,
        "model_fit": False,
        "portal_upload_performed": False,
        "preregistration": str(REG.relative_to(ROOT)),
        "preregistration_sha256": file_hash(REG),
        "parent_preregistration_sha256": file_hash(PARENT),
        "data_manifest_sha256": file_hash(PIN_MANIFEST),
        "data_restore_receipt": restore,
        "input_provenance": "SHA-pinned owner-supplied sibling-repository mirrors; pins do not authenticate organizer portal bytes",
        "organizer_input_bytes_authenticated": False,
        "missing_inputs": missing,
        "protocol_or_integrity_problems": problems,
        "input_reports": data_reports,
        "existing_matching_holdout": existing_holdout,
        "score_mapping_authenticated": False,
        "next_action": next_action,
        "interpretation": "READY authorizes only the preregistered local holdout; it is not a successful validation, submission uniqueness, weekly-slot approval, organizer acceptance, or public-score forecast."
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    if status == "BLOCKED_PROTOCOL_OR_INTEGRITY":
        return 1
    if status == "BLOCKED_MISSING_REQUIRED_INPUTS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
