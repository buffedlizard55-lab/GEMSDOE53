#!/usr/bin/env python3
"""Validate the preregistered R3-H1 profile feature on fixed spatial folds.

This runs before any R3 TIFF is built. It compares surface view B against the
same view plus two paired-scarp-profile features on identical training rows,
whole-component folds, buffers, metric placement and per-fold emission budgets.
An optional, separate co-training experiment runs only if the frozen proxy-error
independence gate permits it; it can never replace the primary after results are
seen. No competition portal is contacted.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import joblib
import numpy as np
import rasterio
from scipy import ndimage as ndi
from threadpoolctl import threadpool_limits

from gems52 import spatial, structural
import run_structural_pipeline as r2

PREREG = ROOT / "registry/r3_preregistration.json"
WORK = ROOT / "work/r3"
FEATURES = WORK / "features"
EVIDENCE = ROOT / "evidence"
_PREREG = json.loads((ROOT / "registry/r3_preregistration.json").read_text())
SEED = int(_PREREG["seed"])
BUDGET = int(_PREREG["placement"]["budget_global_pixels"])
BUFFER_PX = int(r2.CFG["buffer_px"])


def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def log(message: str, **kwargs) -> None:
    kwargs.setdefault("flush", True)
    print(f"[{time.strftime('%H:%M:%S')}] {message}", **kwargs)


def sha256(path: Path) -> str:
    return structural.digest(path)


def ensure_features() -> dict:
    manifest_path = FEATURES / "manifest.json"
    if manifest_path.exists():
        current = json.loads(manifest_path.read_text())
        actual_features = sha256(ROOT / "data/training_features.tif")
        # The shared feature builder now carries both the R3-H1 and H55 profile
        # channels. Reuse any cache that explicitly contains the R3 feature group,
        # rather than demanding an R3-only manifest version and rebuilding away
        # the other preregistered channels.
        if (current.get("r3_h1_profile")
                and current.get("view_B_paired_shoulder")
                and current.get("h2_features")
                and current.get("inputs", {}).get("features_sha256") == actual_features):
            log("verified existing R3 feature cache")
            write_json(EVIDENCE / "features_r3.json", current)
            return current
    log("building label-free R3 feature cache")
    manifest = structural.build(dest=FEATURES, log=log)
    write_json(EVIDENCE / "features_r3.json", manifest)
    return manifest


def load_inputs():
    store = structural.FeatureStore(FEATURES)
    with rasterio.open(ROOT / "data/labels.tif") as src:
        if src.count != 1 or src.shape != store.valid.shape:
            raise ValueError("labels do not match the R3 eligible feature grid")
        cat = src.read(1) == 1
    return store, cat


def digest_indices(rows: np.ndarray) -> str:
    return hashlib.sha256(np.asarray(rows, dtype="<i8").tobytes()).hexdigest()


def cache_signature(store, names, rows, region, seed) -> str:
    payload = dict(
        seed=int(seed),
        code_sha256=sha256(Path(__file__)),
        pipeline_sha256=sha256(ROOT / "scripts/run_structural_pipeline.py"),
        spatial_sha256=sha256(ROOT / "src/gems52/spatial.py"),
        structural_sha256=sha256(ROOT / "src/gems52/structural.py"),
        preregistration_sha256=sha256(PREREG),
        feature_manifest_sha256=sha256(FEATURES / "manifest.json"),
        feature_names=list(names),
        training_indices_sha256=digest_indices(rows),
        evaluation_region_sha256=hashlib.sha256(np.packbits(region).tobytes()).hexdigest(),
        sklearn_version=__import__("sklearn").__version__,
    )
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def fit_predict_cached(store, rows, y, names, seed, region, fold_dir, arm):
    fold_dir.mkdir(parents=True, exist_ok=True)
    model_path = fold_dir / f"{arm}.joblib"
    pred_path = fold_dir / f"{arm}.npy"
    receipt_path = fold_dir / f"{arm}.cache.json"
    signature = cache_signature(store, names, rows, region, seed)
    if model_path.exists() and pred_path.exists() and receipt_path.exists():
        try:
            if json.loads(receipt_path.read_text()).get("signature") == signature:
                model = joblib.load(model_path)
                pred = np.load(pred_path, allow_pickle=False)
                if pred.shape == store.valid.shape:
                    log(f"fold cache hit: {arm}")
                    return model, pred
        except Exception as exc:
            log(f"ignoring invalid cache {arm}: {exc}")
    log(f"fold fit: {arm} ({len(names)} features)")
    model = r2.fit(store, rows, y, names, seed)
    joblib.dump(model, model_path)
    pred = r2.predict(store, model, names, region)
    np.save(pred_path, pred)
    write_json(receipt_path, dict(signature=signature, arm=arm, features=list(names)))
    return model, pred


def emitted_arm(field, fold, valid, catalogue_prior):
    p = r2.prior_adjust(field, catalogue_prior)
    pred, placement = r2.place(p, fold["region"], fold["visible"], valid, BUDGET)
    score = r2.score_fold(pred, fold["truth"], fold["region"], fold["visible"])
    score["placement"] = placement
    return pred, score


def explain_a_only_components(donor, receiver, train, forbidden, donor_threshold,
                              receiver_lo, receiver_hi, receipts, fold_index,
                              context_grids, transform, distance_to_catalogue):
    """Attach measured, cautious geological context to every exchanged A-only component."""
    candidate = (np.isfinite(donor) & np.isfinite(receiver)
                 & (donor >= donor_threshold)
                 & (receiver >= receiver_lo) & (receiver <= receiver_hi))
    labels, _ = ndi.label(candidate, np.ones((3, 3), bool))
    objects = ndi.find_objects(labels)
    explanations = []
    for receipt in receipts:
        component_id = int(receipt["component"])
        sl = objects[component_id - 1]
        if sl is None:
            continue
        local = labels[sl] == component_id
        yy0, xx0 = np.nonzero(local)
        yy, xx = yy0 + sl[0].start, xx0 + sl[1].start
        if not len(yy) or not train[yy, xx].all() or forbidden[yy, xx].any():
            raise AssertionError("A-only reasoning component escaped the train/forbidden gate")
        pixel_x, pixel_y = xx + 0.5, yy + 0.5
        map_x = transform.a * pixel_x + transform.b * pixel_y + transform.c
        map_y = transform.d * pixel_x + transform.e * pixel_y + transform.f
        centroid_x, centroid_y = float(map_x.mean()), float(map_y.mean())
        if len(yy) > 1:
            covariance = np.cov(np.column_stack((map_x, map_y)), rowvar=False)
            eig = np.linalg.eigvalsh(covariance)
            elongation = float(np.sqrt(max(eig[-1], 0.0) / max(eig[0], 1e-9)))
            vector = np.linalg.eigh(covariance)[1][:, -1]
            axis_deg = float(np.degrees(np.arctan2(vector[1], vector[0])) % 180.0)
        else:
            elongation, axis_deg = 0.0, None
        band_means = {f"band_{number:02d}_mean_raw": float(context_grids[number][yy, xx].mean())
                      for number in (2, 13, 15)}
        explanation = (
            "A-only here means View A exceeded its training-only 99th-percentile score while the "
            "surface-view receiver lay in its training-only 40th–80th percentile abstention interval. "
            "This is a candidate for a structure ranked highly by potential-field/subsurface inputs but "
            "not highly ranked by the combined 100 m surface view, which is physically compatible with a buried fault "
            "beneath sedimentary cover. The component's recorded magnetic/gravity/basement-band means "
            "and line-shape statistics are context for review, not proof that any one layer caused the "
            "score. Intrusions, lithologic contacts, acquisition artifacts, strain/seismic backgrounds, "
            "and DEM generalization remain competing explanations; verify a coherent cross-band edge "
            "and independent geology before calling it a fault."
        )
        explanations.append(dict(
            fold=int(fold_index), component_id=component_id, pixels=int(len(yy)),
            projected_centroid_x_m=centroid_x, projected_centroid_y_m=centroid_y,
            mean_view_A_score=float(donor[yy, xx].mean()),
            mean_view_B_paired_shoulder_score=float(receiver[yy, xx].mean()),
            donor_threshold=float(donor_threshold), receiver_abstain_lo=float(receiver_lo),
            receiver_abstain_hi=float(receiver_hi),
            mean_nearest_catalogue_distance_px=float(distance_to_catalogue[yy, xx].mean()),
            pixel_shape_elongation=elongation, principal_axis_degrees_from_easting=axis_deg,
            **band_means,
            geology_reasoning=explanation,
            candidate_status="research diagnostic only; not independently geologically verified",
        ))
    return explanations


def write_a_only_reasoning_csv(rows: list[dict]) -> Path:
    path = EVIDENCE / "a_only_reasoning_r3.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["fold", "component_id", "pixels", "projected_centroid_x_m",
                  "projected_centroid_y_m", "mean_view_A_score",
                  "mean_view_B_paired_shoulder_score", "donor_threshold",
                  "receiver_abstain_lo", "receiver_abstain_hi",
                  "mean_nearest_catalogue_distance_px", "pixel_shape_elongation",
                  "principal_axis_degrees_from_easting", "band_02_mean_raw",
                  "band_13_mean_raw", "band_15_mean_raw", "geology_reasoning",
                  "candidate_status"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def run_validation() -> dict:
    prereg = json.loads(PREREG.read_text())
    if prereg.get("primary_hypothesis") != "R3-H1 paired DEM-normal scarp profile; band 12 detrended elevation and band 19 slope":
        raise ValueError("R3 preregistration changed; inspect and register a new experiment")
    if SEED != r2.SEED or BUFFER_PX != 80 or "80 px" not in prereg.get("spatial_layout", ""):
        raise ValueError("seed or spatial buffer no longer matches the frozen R3/R2 protocol")
    if BUDGET != prereg["placement"]["budget_global_pixels"]:
        raise ValueError("emission budget disagrees with the frozen R3 protocol")
    if prereg["folds"] != 4 or prereg["learner"]["configuration_source"] != "registry/r2_preregistration.json":
        raise ValueError("fold or learner configuration differs from preregistration")
    manifest = ensure_features()
    if not manifest.get("h2_features") or len(manifest["h2_features"]) != 2:
        raise ValueError("the feature cache does not contain exactly the two registered R3-H1 features")
    store, cat = load_inputs()
    valid = store.valid
    view_a = store.manifest["view_A"]
    view_b = store.manifest["view_B"]
    view_b_h2 = store.manifest["view_B_paired_shoulder"]
    if view_b_h2[:len(view_b)] != view_b or view_b_h2[len(view_b):] != store.manifest["h2_features"]:
        raise ValueError("paired-profile arm must be baseline B plus only the two preregistered features")

    folds, baseline_negative_rows, candidate_negative_rows, cached_fold_receipts = [], [], [], []
    prior_holdout_path = EVIDENCE / "holdout_r2.json"
    historical = json.loads(prior_holdout_path.read_text()) if prior_holdout_path.exists() else {}
    historical_means = historical.get("means", {})
    for f in spatial.folds(cat, valid, buffer_px=BUFFER_PX):
        i = f["fold"]
        fold_dir = WORK / f"fold_{i}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        rows, y, train_receipt = r2.training_rows(cat, valid, f["train"], f["visible"], SEED + i)
        np.savez(fold_dir / "training_indices.npz", rows=rows, y=y)

        # Refit every historical R2 comparator plus the preregistered candidate
        # on the identical fold rows. This verifies that B is still the incumbent
        # rather than merely assuming the old table remains comparable.
        arm_names = ("raw_fusion", "view_A", "view_B", "structural_contrast", "view_B_paired_shoulder")
        models, predictions = {}, {}
        for name in arm_names:
            names = store.manifest[name]
            models[name], predictions[name] = fit_predict_cached(
                store, rows, y, names, SEED + i, f["region"], fold_dir, name)
        pa = predictions["view_A"]
        pb = predictions["view_B"]
        ph2 = predictions["view_B_paired_shoulder"]
        qa = r2.quantiles(store, models["view_A"], view_a, rows)
        qb = r2.quantiles(store, models["view_B"], view_b, rows)
        qh2 = r2.quantiles(store, models["view_B_paired_shoulder"], view_b_h2, rows)

        distance_from_catalogue = ndi.distance_transform_edt(~cat)
        neg_eval = valid & f["quadrant"] & f["region"] & (distance_from_catalogue > 3)
        block_args = dict(side=prereg["independence_gate"]["block_side_px"],
                          minimum=prereg["independence_gate"]["minimum_negative_pixels_per_block"])
        baseline_blocks = spatial.negative_block_errors(
            pa, pb, neg_eval, i, (qa["confident"], qb["confident"]), **block_args)
        candidate_blocks = spatial.negative_block_errors(
            pa, ph2, neg_eval, i, (qa["confident"], qh2["confident"]), **block_args)
        baseline_negative_rows.extend(baseline_blocks)
        candidate_negative_rows.extend(candidate_blocks)

        classes = r2.strata(pa, pb, qa, qb, f["region"])
        cover = store.feature_grid("raw_band_15")
        fields = {
            "raw_fusion": predictions["raw_fusion"],
            "view_A": pa,
            "view_B": pb,
            "naive_union": np.maximum(pa, pb),
            "structural_contrast": predictions["structural_contrast"],
            "disagreement_router": r2.router(pa, pb, classes, cover),
            "view_B_paired_shoulder": ph2,
        }
        arms = {}
        for name, field in fields.items():
            _, score = emitted_arm(field, f, valid, train_receipt["catalogue_prior"])
            arms[name] = score
            log(f"fold {i} {name}: DTI={score['dti']:.6f}, emitted={score['emitted']}")
        receipt = dict(fold=i, spatial=f["receipt"], training=train_receipt,
                       quantiles={"view_A": qa, "view_B": qb, "view_B_paired_shoulder": qh2},
                       n_negative_blocks={"view_A_vs_view_B": len(baseline_blocks),
                                          "view_A_vs_view_B_paired_shoulder": len(candidate_blocks)},
                       arms=arms)
        folds.append(receipt)
        cached_fold_receipts.append(dict(fold=i, train_receipt=train_receipt))
        del models, predictions, fields, classes, cover, distance_from_catalogue

    # The human-readable threshold is frozen in the preregistration; parse it
    # once and pass a numeric value to both view-pair diagnostics.
    gate_threshold = float(prereg["independence_gate"]["abandon_exchange_if"].split(">=")[-1].strip())
    baseline_independence = spatial.independence(
        baseline_negative_rows, threshold=gate_threshold,
        min_blocks=prereg["independence_gate"]["minimum_blocks"])
    candidate_independence = spatial.independence(
        candidate_negative_rows, threshold=gate_threshold,
        min_blocks=prereg["independence_gate"]["minimum_blocks"])
    if baseline_independence["threshold"] != gate_threshold or candidate_independence["threshold"] != gate_threshold:
        raise AssertionError("independence threshold disagrees with preregistration")
    independence = dict(candidate_independence)
    independence["primary_pair"] = "view_A vs view_B_paired_shoulder"
    independence["baseline_view_pair"] = baseline_independence
    write_json(EVIDENCE / "independence_r3.json", independence)

    historical_names = ("raw_fusion", "view_A", "view_B", "naive_union",
                        "structural_contrast", "disagreement_router")
    refit_means = {name: float(np.mean([f["arms"][name]["dti"] for f in folds]))
                   for name in historical_names}
    historical_deltas = {name: refit_means[name] - float(historical_means[name])
                         for name in historical_names if name in historical_means}
    history_refit_confirmed = (len(historical_deltas) == len(historical_names)
                               and all(abs(delta) <= 1e-6 for delta in historical_deltas.values()))
    incumbent = max(refit_means, key=refit_means.get)
    incumbent_mean = refit_means[incumbent]
    baseline_mean = float(np.mean([f["arms"]["view_B"]["dti"] for f in folds]))
    candidate_mean = float(np.mean([f["arms"]["view_B_paired_shoulder"]["dti"] for f in folds]))
    differences = [f["arms"]["view_B_paired_shoulder"]["dti"] - f["arms"]["view_B"]["dti"] for f in folds]
    positive = sum(d > 0 for d in differences)
    lift = candidate_mean - baseline_mean
    incumbent_lift = candidate_mean - incumbent_mean
    minimum_lift = prereg["promotion_gate"]["minimum_mean_dti_lift_over_view_B"]
    minimum_positive = prereg["promotion_gate"]["minimum_positive_paired_folds"]
    local_gate_passed = bool(lift >= minimum_lift and positive >= minimum_positive)
    beats_refit_incumbent = bool(incumbent_lift > 0)
    independent_confirmation = False
    holdout_gate = dict(
        baseline="view_B",
        candidate="view_B_paired_shoulder",
        baseline_mean_dti=baseline_mean,
        candidate_mean_dti=candidate_mean,
        mean_dti_lift=lift,
        paired_fold_lifts=differences,
        positive_folds=positive,
        total_folds=len(folds),
        required_mean_lift=minimum_lift,
        required_positive_folds=minimum_positive,
        refitted_historical_baseline_means=refit_means,
        published_r2_baseline_means=historical_means,
        historical_refit_deltas=historical_deltas,
        same_protocol_historical_refit_matches=history_refit_confirmed,
        refitted_incumbent=incumbent,
        refitted_incumbent_mean_dti=incumbent_mean,
        candidate_lift_over_refitted_incumbent=incumbent_lift,
        local_candidate_gate_passed=local_gate_passed,
        beats_current_comparable_holdout_best=bool(local_gate_passed and beats_refit_incumbent),
        independent_confirmation=independent_confirmation,
        approved_for_weekly_slot=False,
        weekly_submission_slots_used=0,
        reason=("candidate did not clear registered local lift/fold-support gate; do not spend a slot"
                if not local_gate_passed else
                "candidate did not beat the refitted current local incumbent; do not spend a slot"
                if not beats_refit_incumbent else
                "refitted R2 comparators did not reproduce the published same-protocol baseline table; investigate before any promotion"
                if not history_refit_confirmed else
                "local gates passed, but independent expert-label confirmation is unavailable; no slot approval"),
    )

    cotraining = run_optional_exchange(store, cat, cached_fold_receipts, prereg, independence)
    report = dict(
        generated_utc=now(),
        preregistration_sha256=sha256(PREREG),
        feature_manifest_sha256=sha256(FEATURES / "manifest.json"),
        input_features_sha256=manifest["inputs"]["features_sha256"],
        label_sha256=sha256(ROOT / "data/labels.tif"),
        template_sha256=sha256(ROOT / "data/sample_submission.tif"),
        software={"python": platform.python_version(), "numpy": np.__version__,
                  "rasterio": rasterio.__version__, "sklearn": __import__("sklearn").__version__},
        protocol="four quadrant spatial folds; whole original 8-connected catalogue components; 80 px train/evaluation buffer; identical fold rows and metric-aware placement for every refitted R2 comparator and the B+H2 candidate",
        feature_support_px=manifest["support_px"],
        profile_feature_names=manifest["h2_features"],
        external_data_used=False,
        negative_class="held-out catalogue-zero proxies, not verified geological absence",
        fixed_global_emission_budget=BUDGET,
        folds=folds,
        summary=dict(baseline_mean_dti=baseline_mean, candidate_mean_dti=candidate_mean,
                     mean_dti_lift=lift, paired_fold_lifts=differences, positive_folds=positive,
                     refitted_baseline_arm_means=refit_means,
                     refitted_local_incumbent=incumbent,
                     refitted_local_incumbent_mean_dti=incumbent_mean,
                     candidate_lift_over_incumbent=incumbent_lift,
                     published_r2_means_match_refit=history_refit_confirmed),
        slot_gate=holdout_gate,
        independence_summary=dict(
            baseline={k: v for k, v in baseline_independence.items() if k != "blocks"},
            candidate={k: v for k, v in candidate_independence.items() if k != "blocks"}),
        cotraining=cotraining,
        caveats=[
            "Local catalogue-component recovery is not validation against the hidden expert-mapped new-fault labels.",
            "Catalogue-zero pixels are incomplete-map proxies, not verified fault absence.",
            "The 100 m DEM/slope can blur scarps and cannot resolve metre-scale geomorphology.",
            "A weak negative-error correlation does not prove conditional independence or sufficient views.",
            "No organizer score or portal acceptance is predicted or claimed.",
        ],
    )
    write_json(EVIDENCE / "holdout_r3_paired_profile.json", report)
    log(f"R3-H1 mean lift {lift:+.6f} over B; positive folds {positive}/{len(folds)}; slot approval FALSE")
    return report


def run_optional_exchange(store, cat, fold_receipts, prereg, independence) -> dict:
    enabled = bool(independence.get("allow_exchange"))
    reasoning_rows = []
    report = dict(generated_utc=now(), enabled=enabled, used_in_primary=False,
                  reason=independence.get("reason"), rounds=[],
                  a_only_reasoning_file="evidence/a_only_reasoning_r3.csv")
    if not enabled:
        write_a_only_reasoning_csv(reasoning_rows)
        report["reason"] = "disabled by frozen independence gate: " + str(report["reason"])
        report["a_only_candidates_reasoned"] = 0
        report["a_only_candidate_status"] = "none admitted; no A-only pseudo-labels or candidate map generated"
        return report

    conf = prereg["optional_cotraining_trial"]
    view_a = store.manifest["view_A"]
    view_b = store.manifest["view_B_paired_shoulder"]
    context_grids = {n: store.feature_grid(f"raw_band_{n:02d}") for n in (2, 13, 15)}
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        transform = ref.transform
    side = int(prereg["independence_gate"]["block_side_px"])
    for f in spatial.folds(cat, store.valid, buffer_px=BUFFER_PX):
        i, fold_dir = f["fold"], WORK / f"fold_{f['fold']}"
        data = np.load(fold_dir / "training_indices.npz", allow_pickle=False)
        rows, y = data["rows"], data["y"]
        train_receipt = fold_receipts[i]["train_receipt"]
        model_a = joblib.load(fold_dir / "view_A.joblib")
        model_b = joblib.load(fold_dir / "view_B_paired_shoulder.joblib")
        # Predictions cover the feature footprint, but pseudo-label selection is
        # constrained to f['train']; evaluation is never used to select labels.
        pa = r2.predict(store, model_a, view_a, store.valid)
        pb = r2.predict(store, model_b, view_b, store.valid)
        qa = r2.quantiles(store, model_a, view_a, rows)
        qb = r2.quantiles(store, model_b, view_b, rows)
        forbidden = ndi.binary_dilation(f["visible"], structure=spatial.disk(conf["forbidden_visible_catalogue_buffer_px"]))
        forbidden.ravel()[rows] = True
        distance_to_catalogue = ndi.distance_transform_edt(~cat)
        directions = []
        for donor, receiver, qd, qr, target, names, donor_name in (
            (pa, pb, qa, qb, "view_B_paired_shoulder", view_b, "view_A"),
            (pb, pa, qb, qa, "view_A", view_a, "view_B_paired_shoulder"),
        ):
            idx, receipts = spatial.whole_pseudo_segments(
                donor, receiver, f["train"], forbidden,
                qd["confident"], qr["abstain_lo"], qr["abstain_hi"],
                side=side,
                min_pixels=conf["minimum_component_pixels"],
                cap=conf["max_pseudo_pixels_per_view_per_fold"],
            )
            row = dict(donor_view=donor_name, target_view=target,
                       pixels=int(len(idx)), components=receipts,
                       pseudo_pixels_all_in_training=bool(f["train"].ravel()[idx].all()) if len(idx) else True,
                       evaluation_pixels=int(f["region"].ravel()[idx].sum()) if len(idx) else 0)
            if donor_name == "view_A":
                explanations = explain_a_only_components(
                    donor, receiver, f["train"], forbidden,
                    qd["confident"], qr["abstain_lo"], qr["abstain_hi"], receipts,
                    i, context_grids, transform, distance_to_catalogue)
                reasoning_rows.extend(explanations)
                row["geology_review"] = "see one evidence/a_only_reasoning_r3.csv row per accepted A-only component"
            else:
                row["geology_review"] = (
                    "B-only candidates are surface-view confident while the geophysical view abstains; "
                    "treat as suspect surface artifacts (roads, erosion, fan margins, levees, lithologic contacts)"
                )
            if len(idx):
                model = r2.fit(store, rows, y, names, SEED + i, pseudo=idx)
                pred = r2.predict(store, model, names, f["region"])
                emission, score = emitted_arm(pred, f, store.valid, train_receipt["catalogue_prior"])
                row["dti_after_exchange"] = score["dti"]
                row["emitted"] = score["emitted"]
                del model, pred, emission
            directions.append(row)
        report["rounds"].append(dict(fold=i, directions=directions))
        del model_a, model_b, pa, pb, distance_to_catalogue
    write_a_only_reasoning_csv(reasoning_rows)
    report["a_only_candidates_reasoned"] = len(reasoning_rows)
    report["a_only_candidate_status"] = "one row with measured spatial and raster context per accepted whole A-only component"
    report["reason"] = str(report.get("reason")) + "; exchange is a separate secondary diagnostic and does not modify the R3-H1 primary"
    return report


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("features", "validate", "all"), default="all")
    args = ap.parse_args()
    os.chdir(ROOT)
    if args.stage in ("features", "all"):
        ensure_features()
    if args.stage in ("validate", "all"):
        run_validation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
