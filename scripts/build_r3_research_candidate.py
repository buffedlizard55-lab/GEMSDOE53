#!/usr/bin/env python3
"""Build and audit a unique R3-H1 research TIFF; never uploads or spends a slot.

The artifact is deliberately labelled research-only because R3-H1 failed its
registered spatial-holdout promotion gate. The file exists to meet the project's
reproducible GeoTIFF-delivery requirement, not as a recommendation to submit.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np
import rasterio

from gems52 import gates, structural
import run_structural_pipeline as r2

PREREG = ROOT / "registry/r3_preregistration.json"
HOLDOUT = ROOT / "evidence/holdout_r3_paired_profile.json"
WORK = ROOT / "work/r3"
FEATURES = WORK / "features"
EV = ROOT / "evidence"
SUBMISSION = ROOT / "submission"
DOWNLOADS = ROOT / "docs/downloads"
PREREG_DATA = json.loads(PREREG.read_text())
SEED = int(PREREG_DATA["seed"])
BUDGET = int(PREREG_DATA["placement"]["budget_global_pixels"])


def now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def file_sha(path: Path) -> str:
    return structural.digest(path)


def build() -> dict:
    if not HOLDOUT.exists():
        raise FileNotFoundError("run scripts/validate_r3_paired_profile.py before building the R3 artifact")
    holdout = json.loads(HOLDOUT.read_text())
    prereg_sha = file_sha(PREREG)
    if holdout.get("preregistration_sha256") != prereg_sha:
        raise ValueError("preregistration differs from the validation receipt; rerun validation first")
    gate = holdout.get("slot_gate", {})
    if gate.get("candidate") != "view_B_paired_shoulder" or gate.get("approved_for_weekly_slot") is not False:
        raise ValueError("unexpected R3-H1 validation receipt; this builder is research-only")
    manifest_path = FEATURES / "manifest.json"
    if not manifest_path.exists() or file_sha(manifest_path) != holdout.get("feature_manifest_sha256"):
        raise ValueError("R3 feature cache changed after holdout validation; rebuild/revalidate")
    if int(holdout.get("fixed_global_emission_budget", -1)) != BUDGET:
        raise ValueError("emission budget does not match the frozen protocol")

    store = structural.FeatureStore(FEATURES)
    with rasterio.open(ROOT / "data/labels.tif") as label_src:
        if label_src.count != 1 or label_src.shape != store.valid.shape:
            raise ValueError("label grid does not match the R3 feature cache")
        cat = label_src.read(1) == 1
    valid = store.valid
    if not np.array_equal(valid, np.load(FEATURES / "valid.npy", allow_pickle=False)):
        raise ValueError("feature eligibility mask changed after validation")
    rows, y, training = r2.training_rows(cat, valid, valid, cat, SEED + 100)
    fields, models = {}, {}
    arms = {
        "view_A": store.manifest["view_A"],
        "view_B": store.manifest["view_B"],
        "view_B_paired_shoulder": store.manifest["view_B_paired_shoulder"],
    }
    for arm, names in arms.items():
        log(f"full-data fit: {arm} ({len(names)} features; {len(rows)} labelled/proxy rows)")
        model = r2.fit(store, rows, y, names, SEED + 100)
        models[arm] = model
        fields[arm] = r2.predict(store, model, names, valid)

    prior = training["catalogue_prior"]
    candidate_density = r2.prior_adjust(fields["view_B_paired_shoulder"], prior)
    prediction, placement = r2.place(candidate_density, valid, cat, valid, BUDGET)
    prediction = np.asarray(prediction, dtype=np.float32)
    if (prediction.ndim != 2 or prediction.shape != valid.shape
            or not np.isfinite(prediction).all()
            or float(prediction.min()) < 0 or float(prediction.max()) > 1):
        raise ValueError("candidate failed the pre-write finite [0,1] prediction check")
    decoded_sha = hashlib.sha256(prediction.astype("<f4").tobytes()).hexdigest()
    stem = f"gems52-r3-h1-paired-profile-{placement['emitted']}-{decoded_sha[:12]}-research-only"
    filename = stem + ".tif"
    temp = WORK / "candidate_r3_h1.tif"
    destination = SUBMISSION / filename
    published = DOWNLOADS / filename
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)

    with rasterio.open(ROOT / "data/sample_submission.tif") as sample:
        reference = sample.read(1, masked=True)
        sample_valid = (~np.ma.getmaskarray(reference)
                        & np.isfinite(reference.data) & (reference.data > -1e38))
        profile = dict(driver="GTiff", width=sample.width, height=sample.height,
                       count=1, dtype="float32", crs=sample.crs,
                       transform=sample.transform, tiled=True,
                       blockxsize=256, blockysize=256, compress="deflate",
                       zlevel=9, predictor=2, nodata=None)
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
            with rasterio.open(temp, "w", **profile) as dst:
                dst.write(prediction, 1)
                dst.write_mask(sample_valid.astype(np.uint8) * 255)
                dst.update_tags(
                    model="GEMSDOE52 R3-H1 paired DEM-normal profile, surface view B",
                    status="research-only; preregistered holdout gate failed; do not upload",
                    decoded_sha256=decoded_sha,
                    preregistration_sha256=prereg_sha,
                )

    fmt = gates.format_report(temp, ROOT / "data/sample_submission.tif", footprint=valid)
    if not fmt.get("ok"):
        raise ValueError(f"written GeoTIFF failed the format gate: {fmt.get('problems')}")
    if not np.array_equal(valid, np.load(FEATURES / "valid.npy", allow_pickle=False)):
        raise AssertionError("feature validity changed during export")

    priors = [p for p in r2.prior_paths()
              if p.resolve() not in (destination.resolve(), published.resolve(), temp.resolve())]
    uniqueness = gates.uniqueness_report(prediction, priors)
    uniqueness["inventory"] = "scripts/run_structural_pipeline.py::prior_paths; evidence/prior_inventory_r2.json plus aligned prior rasters in data/scored, data/reference, docs/downloads and submission"
    uniqueness["research_only_due_to_holdout_failure"] = True

    comparisons = {}
    placed_views = {}
    for arm in ("view_A", "view_B"):
        field = r2.prior_adjust(fields[arm], prior)
        placed, stats = r2.place(field, valid, cat, valid, BUDGET)
        placed_views[arm] = placed > 0
        comparisons[arm] = dict(equal=bool(np.array_equal(prediction, placed)),
                                emitted=int(placed.sum()),
                                intersection=int(((prediction > 0) & (placed > 0)).sum()))
    view_union = placed_views["view_A"] | placed_views["view_B"]
    comparisons["view_union"] = dict(
        equal=bool(np.array_equal(prediction > 0, view_union)),
        pixels=int(view_union.sum()),
        candidate_only=int(((prediction > 0) & ~view_union).sum()),
        union_only=int((view_union & ~(prediction > 0)).sum()),
    )
    max_union_field = r2.prior_adjust(np.maximum(fields["view_A"], fields["view_B"]), prior)
    max_union, max_union_stats = r2.place(max_union_field, valid, cat, valid, BUDGET)
    comparisons["matched_budget_max_view_union"] = dict(
        equal=bool(np.array_equal(prediction, max_union)),
        emitted=int(max_union.sum()),
        intersection=int(((prediction > 0) & (max_union > 0)).sum()),
        candidate_only=int(((prediction > 0) & ~(max_union > 0)).sum()),
        union_only=int(((max_union > 0) & ~(prediction > 0)).sum()),
        placement=max_union_stats,
    )
    comparisons["not_merely_a_view_union"] = bool(
        not comparisons["view_union"]["equal"]
        and comparisons["view_union"]["union_only"] > 0
        and not comparisons["matched_budget_max_view_union"]["equal"]
    )
    comparisons["literally_copied_prior"] = any(row.get("identical") for row in uniqueness.get("per_prior", []))
    comparisons["not_copied_or_literal_union"] = bool(
        uniqueness.get("canonical_pattern_unique")
        and uniqueness.get("research_publication_ok")
        and not comparisons["view_union"]["equal"]
        and not comparisons["matched_budget_max_view_union"]["equal"]
        and not comparisons["literally_copied_prior"]
    )
    if not comparisons["not_copied_or_literal_union"]:
        write_json(EV / "uniqueness_r3.json", uniqueness)
        write_json(EV / "not_union_r3.json", comparisons)
        raise ValueError("candidate is copied/union-equivalent or the accessible prior audit is incomplete; refusing publication")

    # The frozen local gate did not pass: provide an audited research artifact,
    # but never set an approval flag or submit it to the organizer.
    local_note = (
        f"R3-H1 paired DEM profile | local lift {gate['mean_dti_lift']:+.6f} vs B "
        f"({gate['positive_folds']}/{gate['total_folds']} folds; gate FAIL) | "
        "research-only; NOT approved for upload."
    )
    if len(local_note) > 200:
        raise AssertionError("submission note exceeds the 200-character limit")

    shutil.copy2(temp, destination)
    shutil.copy2(destination, published)
    final_format = gates.format_report(destination, ROOT / "data/sample_submission.tif", footprint=valid)
    if not final_format.get("ok") or file_sha(destination) != file_sha(published):
        raise ValueError("final or published TIFF failed post-copy byte/format verification")
    with rasterio.open(destination) as src:
        written = src.read(1)
        internal_mask_matches = bool(np.array_equal(src.dataset_mask() > 0, sample_valid))
        prediction_round_trip_matches = bool(np.array_equal(written, prediction))
        values = np.unique(written)
    if not internal_mask_matches or not prediction_round_trip_matches:
        raise ValueError("post-write data or internal mask differs from the intended prediction/template")

    decoded_sha_final = hashlib.sha256(written.astype("<f4").tobytes()).hexdigest()
    if decoded_sha_final != decoded_sha:
        raise ValueError("decoded raster hash changed during GeoTIFF write/read")
    note = local_note
    receipt = dict(
        generated_utc=now(),
        file=filename,
        submission_name="GEMSDOE52-R3-H1-PairedProfile-" + decoded_sha[:8],
        note=note,
        submission_note=note,
        submission_note_chars=len(note),
        bytes=destination.stat().st_size,
        sha256=file_sha(destination),
        decoded_sha256=decoded_sha,
        format=final_format,
        uniqueness=uniqueness,
        view_comparison=comparisons,
        stats=placement,
        model="single-view B + the two preregistered R3-H1 paired DEM-profile features",
        pseudo_exchange_used=False,
        cotraining_diagnostic="evidence/holdout_r3_paired_profile.json; separately evaluated and not used in this artifact",
        validation=gate,
        promoted=False,
        forced=False,
        approved_for_weekly_slot=False,
        weekly_submission_slots_used=0,
        artifact_status="RESEARCH ONLY — R3-H1 spatial holdout failed the preregistered promotion gate; DO NOT UPLOAD",
        official_score=None,
        score_forecast=None,
        source_authentication="Competition input files are SHA-pinned owner mirrors; organizer portal acceptance and hidden-score attribution are not verified.",
        normalization="single-band float32 binary {0,1}; every raw cell finite and within [0,1]; internal mask equals the sample footprint",
        feature_support_px=store.manifest["support_px"],
        eligible_support_px=int(valid.sum()),
        external_data_used=False,
        preregistration_sha256=prereg_sha,
        feature_manifest_sha256=file_sha(manifest_path),
        label_sha256=file_sha(ROOT / "data/labels.tif"),
        template_sha256=file_sha(ROOT / "data/sample_submission.tif"),
        training=training,
        values=[float(x) for x in values],
        internal_mask_matches_sample=internal_mask_matches,
        decoded_pixels_match_prediction=prediction_round_trip_matches,
        prior_inventory=[dict(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                              bytes=p.stat().st_size, sha256=file_sha(p)) for p in priors],
        prior_inventory_count=len(priors),
        gate_reason=gate["reason"],
        independent_confirmation="not performed; no expert-mapped external holdout labels are available",
        software={"python": platform.python_version(), "numpy": np.__version__,
                  "rasterio": rasterio.__version__, "sklearn": __import__("sklearn").__version__},
    )
    write_json(EV / f"submission_{stem}.json", receipt)
    write_json(EV / "submission_r3.json", receipt)
    write_json(EV / "format_gate_r3.json", final_format)
    write_json(EV / "uniqueness_r3.json", uniqueness)
    write_json(EV / "not_union_r3.json", comparisons)
    write_json(DOWNLOADS / f"{stem}-audit.json", receipt)
    (SUBMISSION / "R3_LATEST.txt").write_text(filename + "\n")
    log(f"WROTE {filename}; format PASS, canonical pattern/non-union PASS; "
        f"support novelty {'PASS' if uniqueness.get('support_novelty_gate_ok') else 'FAIL'}; "
        "research-only, zero slots used, DO NOT UPLOAD")
    return receipt


def main() -> int:
    os.chdir(ROOT)
    receipt = build()
    print(json.dumps({k: receipt[k] for k in ("file", "submission_name", "submission_note",
          "bytes", "sha256", "approved_for_weekly_slot", "artifact_status")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
