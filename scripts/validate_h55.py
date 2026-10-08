#!/usr/bin/env python3
"""Validate the frozen H55-1 edge-polarity hypothesis and build a research-only raster.

The script reuses the registered R2 spatial folds, learner, matched budget, and
metric-aware placement. It never reads prior submission pixels as model inputs.
No DrivenData upload or leaderboard request is made here.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import zipfile

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import joblib
import numpy as np
import rasterio
from scipy import ndimage as ndi

from gems52 import gates, h55, spatial, structural
import run_structural_pipeline as r2

WORK = ROOT / "work/h55"
EV = ROOT / "evidence"
FEATURE_WORK = WORK / "features"
PREREG = ROOT / "registry/h55_edge_preregistration.json"
CFG = json.loads(PREREG.read_text())
R2CFG = r2.CFG
A_EXTRA = [
    "h55_grav_signed_log_s1", "h55_grav_zc_edge_s1",
    "h55_grav_signed_log_s3", "h55_grav_zc_edge_s3",
    "h55_rtp_signed_log_s1", "h55_rtp_zc_edge_s1",
    "h55_rtp_signed_log_s3", "h55_rtp_zc_edge_s3",
    "h55_grav_rtp_normal_agreement_s3", "h55_grav_rtp_edge_pair_s3",
]
CROSS_EXTRA = ["h55_grav_rtp_edge_pair_cover_quiet_s3"]
H55_NAMES = A_EXTRA + CROSS_EXTRA


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def register_columns(store, build=True):
    """Build or verify H55 eligible-domain columns, then attach them to FeatureStore."""
    FEATURE_WORK.mkdir(parents=True, exist_ok=True)
    manifest_path = FEATURE_WORK / "manifest.json"
    sig = dict(
        hypothesis=CFG["version"], preregistration_sha256=structural.digest(PREREG),
        transform_sha256=structural.digest(ROOT / "src/gems52/h55.py"),
        features_sha256=structural.digest(ROOT / "data/training_features.tif"),
        sample_sha256=structural.digest(ROOT / "data/sample_submission.tif"),
        base_feature_manifest_sha256=structural.digest(store.directory / "manifest.json"),
        valid_index_sha256=sha_bytes(np.asarray(store.flat_idx, dtype="<i8").tobytes()),
    )
    cached = None
    if manifest_path.exists():
        cached = json.loads(manifest_path.read_text())
    if cached and all(cached.get(k) == v for k, v in sig.items()):
        good = True
        for name, digest in cached.get("feature_sha256", {}).items():
            p = FEATURE_WORK / f"{name}.npy"
            if not p.exists() or structural.digest(p) != digest:
                good = False
                break
        if good and set(cached.get("feature_names", [])) == set(H55_NAMES):
            log("verified cached H55 feature arrays")
            manifest = cached
        else:
            cached = None
    if cached is None:
        if not build:
            raise FileNotFoundError("H55 feature cache absent or stale; run with --stage validate/all")
        input_footprint = np.load(store.directory / "input_footprint.npy", allow_pickle=False)
        with rasterio.open(ROOT / "data/training_features.tif") as src, rasterio.open(ROOT / "data/sample_submission.tif") as ref:
            if (src.count != 19 or src.shape != ref.shape or src.crs != ref.crs
                    or src.transform != ref.transform or input_footprint.shape != ref.shape):
                raise ValueError("H55 band/template grid mismatch")
            raw = {}
            for name, band in (("gravity", 13), ("rtp", 2), ("cover", 15), ("slope", 19)):
                layer = src.read(band).astype(np.float32)
                layer[~input_footprint] = np.nan
                raw[name] = layer
        maps = h55.compute_h55_features(
            raw["gravity"], raw["rtp"], raw["cover"], raw["slope"],
            input_footprint,
            sigmas=tuple(CFG["candidate_features"]["scales_sigma_pixels"]),
            pixel_size_m=100.0,
        )
        if set(maps) != set(H55_NAMES):
            raise AssertionError(f"frozen feature-name mismatch: {sorted(set(maps) ^ set(H55_NAMES))}")
        hashes = {}
        for name in H55_NAMES:
            col = np.asarray(maps[name], dtype=np.float32).ravel()[store.flat_idx]
            path = FEATURE_WORK / f"{name}.npy"
            structural.save_array(path, col)
            hashes[name] = structural.digest(path)
            if len(col) != len(store.flat_idx) or not np.isfinite(col).all():
                raise ValueError(f"eligible-domain H55 feature failed finite/index check: {name}")
            log(f"wrote H55 feature {name}, {len(col):,} values")
        manifest = dict(**sig, version=CFG["version"], feature_names=H55_NAMES,
                        feature_sha256=hashes, eligible_px=int(store.valid.sum()),
                        support_px=int(store.manifest["support_px"]),
                        source_bands_1_based={"gravity": 13, "rtp": 2, "cover": 15, "slope": 19},
                        no_radiometric_bands=True,
                        note="Computed on core mirrored input rasters; hash pins are owner-side, not organizer authentication.")
        write_json(manifest_path, manifest)
        del maps, raw
    # Ordinary reads plus independent SHA/index validation; attach without changing R2 on-disk cache.
    for name in H55_NAMES:
        path = FEATURE_WORK / f"{name}.npy"
        if structural.digest(path) != manifest["feature_sha256"][name]:
            raise ValueError(f"H55 feature SHA-256 mismatch: {name}")
        col = np.load(path, allow_pickle=False)
        if col.dtype != np.float32 or col.shape != (len(store.flat_idx),) or not np.isfinite(col).all():
            raise ValueError(f"H55 feature array shape/dtype/finiteness mismatch: {name}")
        store.columns[name] = col
        store.manifest["feature_sha256"][name] = manifest["feature_sha256"][name]
    return store, manifest


def labels():
    with rasterio.open(ROOT / "data/labels.tif") as src:
        return src.read(1) == 1


def fold_training(fold, fold_dir, cat, valid):
    path = fold_dir / "training_indices.npz"
    if path.exists():
        data = np.load(path, allow_pickle=False)
        rows, y = data["rows"], data["y"]
        expected_rows, expected_y, receipt = r2.training_rows(
            cat, valid, fold["train"], fold["visible"], R2CFG["seed"] + fold["fold"]
        )
        if not np.array_equal(rows, expected_rows) or not np.array_equal(y, expected_y):
            raise ValueError(f"R2 cached training rows differ from the frozen seed in fold {fold['fold']}")
        return rows, y, receipt
    rows, y, receipt = r2.training_rows(cat, valid, fold["train"], fold["visible"], R2CFG["seed"] + fold["fold"])
    np.savez(path, rows=rows, y=y)
    return rows, y, receipt


def score_field(field, fold, valid, pi, budget):
    adjusted = r2.prior_adjust(field, pi)
    pred, placement = r2.place(adjusted, fold["region"], fold["visible"], valid, budget)
    score = r2.score_fold(pred, fold["truth"], fold["region"], fold["visible"])
    score["placement"] = placement
    return pred, score


def validate():
    store, _ = register_columns(structural.FeatureStore(ROOT / "work/r2/features"))
    cat = labels()
    valid = store.valid
    base_manifest = store.manifest
    a_names = base_manifest["view_A"] + A_EXTRA
    candidate_names = base_manifest["structural_contrast"] + H55_NAMES
    if not set(a_names + candidate_names).issubset(store.manifest["feature_sha256"]):
        raise ValueError("H55 feature-store manifest incomplete")
    fold_results, neg_rows, train_receipts = [], [], []

    for fold in spatial.folds(cat, valid, R2CFG["buffer_px"]):
        fi = fold["fold"]
        r2_dir = ROOT / f"work/r2/fold_{fi}"
        hdir = WORK / f"fold_{fi}"
        hdir.mkdir(parents=True, exist_ok=True)
        rows, y, sample_receipt = fold_training(fold, r2_dir, cat, valid)
        train_receipts.append(dict(**fold["receipt"], **sample_receipt))
        # The R2 baseline process must have completed its model and OOF receipts before comparison.
        required = [r2_dir / "view_A.npy", r2_dir / "view_B.npy", r2_dir / "structural_contrast.npy",
                    r2_dir / "view_B.joblib", r2_dir / "quantiles.json"]
        missing = [str(p) for p in required if not p.exists()]
        if missing:
            raise FileNotFoundError("R2 spatial baseline is incomplete; wait for its active run: " + ", ".join(missing))
        baseline_preds = {name: np.load(r2_dir / f"{name}.npy", allow_pickle=False)
                          for name in ("view_A", "view_B", "structural_contrast")}
        baseline_q = json.loads((r2_dir / "quantiles.json").read_text())
        model_paths = {"view_A_h55": hdir / "view_A_h55.joblib",
                       "structural_contrast_h55": hdir / "structural_contrast_h55.joblib"}
        fold_preds = {}
        models = {}
        for name, columns in (("view_A_h55", a_names), ("structural_contrast_h55", candidate_names)):
            mp = model_paths[name]
            model = r2.fit(store, rows, y, columns, R2CFG["seed"] + fi)
            joblib.dump(model, mp)
            pred = r2.predict(store, model, columns, fold["region"])
            np.save(hdir / f"{name}.npy", pred)
            fold_preds[name] = pred
            models[name] = model
            log(f"fold {fi} fitted {name}, {len(columns)} features")
        qa = r2.quantiles(store, models["view_A_h55"], a_names, rows)
        qb = baseline_q["view_B"]
        write_json(hdir / "quantiles.json", {"view_A_h55": qa, "view_B": qb})

        pa, pb = fold_preds["view_A_h55"], baseline_preds["view_B"]
        classes = r2.strata(pa, pb, qa, qb, fold["region"])
        h55_union = np.maximum(pa, pb)
        cover = store.feature_grid("raw_band_15")
        h55_router = r2.router(pa, pb, classes, cover)
        fields = {
            "view_A": baseline_preds["view_A"],
            "view_B": pb,
            "R2_structural_contrast": baseline_preds["structural_contrast"],
            "H55_view_A": pa,
            "H55_structural_contrast": fold_preds["structural_contrast_h55"],
            "H55_A_B_max_union_control": h55_union,
            "H55_disagreement_router_control": h55_router,
        }
        arms = {}
        for arm, field in fields.items():
            emitted, score = score_field(field, fold, valid, sample_receipt["catalogue_prior"],
                                         CFG["primary_budget_global_pixels"])
            score["emitted"] = int((emitted > 0).sum())
            np.save(hdir / f"{arm}_emitted.npy", emitted > 0)
            arms[arm] = score
            log(f"fold {fi} {arm}: DTI {score['dti']:.6f}, {score['emitted']} px")
        neg_eval = valid & fold["quadrant"] & fold["region"] & (ndi.distance_transform_edt(~cat) > 3)
        neg_rows.extend(spatial.negative_block_errors(
            pa, pb, neg_eval, fi, (qa["confident"], qb["confident"]),
            side=R2CFG["co_training_gate"]["block_side_px"],
        ))
        fold_results.append(dict(fold=fi, receipt=fold["receipt"], arms=arms))
        del models, fold_preds, baseline_preds

    independence = spatial.independence(
        neg_rows, CFG["co_training_diagnostic"]["maximum_absolute_error_correlation"],
        CFG["co_training_diagnostic"]["minimum_negative_blocks"],
    )
    independence.update(
        views={"A": "R2 potential/subsurface view plus preregistered H55 gravity/RTP edge channels",
               "B": "unchanged R2 surface-only control"},
        block_size_px=CFG["co_training_diagnostic"]["block_size_px"],
        fold_protocol="4 outer spatial quadrants; held-out catalogue components; 80-pixel buffer",
        data_note="Weak blockwise negative-error correlation is not proof of conditional independence; catalogue-zero cells can hide faults.",
    )
    write_json(EV / "h55_edge_independence.json", independence)
    exchange = run_exchange(store, cat, independence, fold_results)
    write_json(EV / "h55_edge_pseudo_exchange.json", exchange)

    arm_names = list(fold_results[0]["arms"])
    means = {name: float(np.mean([fold["arms"][name]["dti"] for fold in fold_results])) for name in arm_names}
    comparable = ["view_A", "view_B", "R2_structural_contrast"]
    best = max(comparable, key=lambda name: means[name])
    primary = "H55_structural_contrast"
    differences = [fold["arms"][primary]["dti"] - fold["arms"][best]["dti"] for fold in fold_results]
    lift = float(np.mean(differences))
    positive = sum(x > 0 for x in differences)
    meets_mean = lift >= CFG["promotion_gate"]["minimum_mean_dti_lift_over_best_comparable_baseline"]
    meets_folds = positive >= CFG["promotion_gate"]["minimum_positive_outer_folds"]
    report = dict(
        generated_utc=now(), preregistration_sha256=structural.digest(PREREG),
        feature_manifest_sha256=structural.digest(FEATURE_WORK / "manifest.json"),
        protocol="same R2 whole original 8-connected component, four quadrant, 80-pixel buffer folds; same 36-pixel feature-support erosion and metric-aware matched budget",
        candidate=primary, primary_budget_global_pixels=CFG["primary_budget_global_pixels"],
        folds=fold_results, means=means, best_comparable_baseline=best,
        paired_differences=differences, mean_dti_lift=lift, positive_folds=positive, total_folds=4,
        promotion_gate=dict(minimum_mean_lift=CFG["promotion_gate"]["minimum_mean_dti_lift_over_best_comparable_baseline"],
                            meets_mean_lift=meets_mean, minimum_positive_folds=CFG["promotion_gate"]["minimum_positive_outer_folds"],
                            meets_fold_support=meets_folds, holdout_promotion_eligible=bool(meets_mean and meets_folds),
                            format_uniqueness_pending=True, approved_for_weekly_slot=False,
                            failure_action="do not spend a weekly submission slot; any later TIFF remains research-only"),
        training= train_receipts,
        view_a_b_strata="View A confident/View B training-reference abstention is a research stratum, not fault verification.",
        independence_summary={k: v for k, v in independence.items() if k != "blocks"},
        source_integrity=dict(core_rasters_owner_sha256_pinned=True, organizer_byte_authentication=False,
                              external_data_used=False, training_cube_radiometric_bands=0),
        no_public_score_prediction=True, organizer_score=None, submission_slots_used=0,
        caveats=[
            "The negative class is catalogue-zero proxy, not verified geological absence.",
            "The spatial holdout tests recovery of withheld known catalogue components; it is not the organizer's hidden-new-fault validation.",
            "Whole 8-connected pixel components are segment proxies, not authenticated geological fault IDs.",
            "The four spatial folds have low inferential power and do not prove leaderboard lift.",
            "Gravity/RTP, modelled basement depth and slope are not fully independent geological observations.",
            "No data external to the pinned owner-mirrored 19-band cube were used; organizer authenticity of mirrored bytes is unverified.",
        ],
    )
    write_json(EV / "h55_edge_holdout.json", report)
    log(f"H55 slot holdout gate: mean lift {lift:+.6f} vs {best}; positive {positive}/4; eligible={meets_mean and meets_folds}; slot approval FALSE pending release checks")
    return report


def run_exchange(store, cat, independence, fold_results):
    result = dict(generated_utc=now(), enabled=bool(independence["allow_exchange"]),
                  reason=independence["reason"], rounds=[], used_in_primary=False,
                  premise_note="Error decorrelation on catalogue-zero proxies is diagnostic only, not a proof of conditional independence.")
    if not independence["allow_exchange"]:
        return result
    base_a_names = store.manifest["view_A"] + A_EXTRA
    base_b_names = store.manifest["view_B"]
    for fold in spatial.folds(cat, store.valid, R2CFG["buffer_px"]):
        fi = fold["fold"]
        r2_dir, hdir = ROOT / f"work/r2/fold_{fi}", WORK / f"fold_{fi}"
        data = np.load(r2_dir / "training_indices.npz", allow_pickle=False)
        rows, y = data["rows"], data["y"]
        qa_qb = json.loads((hdir / "quantiles.json").read_text())
        qa, qb = qa_qb["view_A_h55"], qa_qb["view_B"]
        model_a = joblib.load(hdir / "view_A_h55.joblib")
        model_b = joblib.load(r2_dir / "view_B.joblib")
        pa = r2.predict(store, model_a, base_a_names, fold["train"])
        pb = r2.predict(store, model_b, base_b_names, fold["train"])
        forbidden = ndi.binary_dilation(fold["visible"], structure=spatial.disk(3))
        forbidden.ravel()[rows] = True
        directions = []
        for donor, receiver, qd, qr, target, columns, seed_offset in (
            (pa, pb, qa, qb, "view_B_from_H55_A", base_b_names, 100),
            (pb, pa, qb, qa, "view_A_h55_from_B", base_a_names, 200),
        ):
            idx, segments = spatial.whole_pseudo_segments(
                donor, receiver, fold["train"], forbidden,
                qd["confident"], qr["abstain_lo"], qr["abstain_hi"],
                side=CFG["co_training_diagnostic"]["block_size_px"],
                min_pixels=CFG["co_training_diagnostic"]["whole_segment_minimum_pixels"],
                cap=CFG["co_training_diagnostic"]["pseudo_pixels_per_view_per_fold_cap"],
            )
            row = dict(target=target, pseudo_pixels=int(len(idx)), segments=segments,
                       train_only=bool(fold["train"].ravel()[idx].all()) if len(idx) else True,
                       evaluation_pixels=int(fold["region"].ravel()[idx].sum()) if len(idx) else 0,
                       minimum_eval_buffer_px=80)
            if len(idx):
                model = r2.fit(store, rows, y, columns, R2CFG["seed"] + fi + seed_offset, pseudo=idx)
                pred = r2.predict(store, model, columns, fold["region"])
                pi = float((cat & fold["train"]).sum() / max(fold["train"].sum(), 1))
                emitted, score = score_field(pred, fold, store.valid, pi, CFG["primary_budget_global_pixels"])
                row["dti_after_exchange"] = score["dti"]
                row["baseline_dti"] = fold_results[fi]["arms"]["H55_view_A" if "view_A" in target else "view_B"]["dti"]
                row["positive_lift_after_exchange"] = float(row["dti_after_exchange"] - row["baseline_dti"])
            else:
                row["dti_after_exchange"] = None
                row["baseline_dti"] = fold_results[fi]["arms"]["H55_view_A" if "view_A" in target else "view_B"]["dti"]
            directions.append(row)
        result["rounds"].append(dict(fold=fi, views=directions))
    result["reason"] += "; one-round whole-segment exchange is a separate research arm and never replaces the preregistered primary after outer outcomes are seen"
    return result


def prior_paths(exclude=()):
    excluded = {Path(p).resolve() for p in exclude}
    paths = r2.prior_paths()
    inv_path = EV / "prior_inventory_r2.json"
    missing = []
    expected = []
    if inv_path.exists():
        inv = json.loads(inv_path.read_text())
        for entry in inv.get("entries", []):
            if entry.get("eligible_prior"):
                p = ROOT / entry["local_path"]
                expected.append(p)
                if not p.exists():
                    missing.append(dict(url=entry.get("url"), local_path=entry.get("local_path")))
    # Existing local eligible prior list includes current linked rasters; preserve historical repo artefacts too.
    paths = list(dict.fromkeys(Path(p).resolve() for p in paths
                               if Path(p).exists() and Path(p).resolve() not in excluded))
    return paths, dict(inventory_entries=len(json.loads(inv_path.read_text()).get("entries", [])) if inv_path.exists() else 0,
                       eligible_prior_entries=len(expected), available_eligible_prior_entries=len(expected) - len(missing),
                       missing=missing, local_files_checked=len(paths), scope="retrievable aligned linked TIFFs plus local scored/released rasters; not unlinked/private/external files")


def build_reasoning(store, cat, emitted, pa, pb, qa, qb, candidate_name):
    classes = r2.strata(pa, pb, qa, qb, store.valid)
    yy, xx = np.nonzero((emitted > 0) & (classes == 2))
    cover = store.feature_grid("raw_band_15")
    slope = store.feature_grid("raw_band_19")
    pair = feature_grid(store, "h55_grav_rtp_edge_pair_s3")
    conditioned = feature_grid(store, "h55_grav_rtp_edge_pair_cover_quiet_s3")
    glog = feature_grid(store, "h55_grav_signed_log_s3")
    mlog = feature_grid(store, "h55_rtp_signed_log_s3")
    distance = ndi.distance_transform_edt(~cat) * 100.0
    from pyproj import Transformer
    convert = Transformer.from_crs(32611, 4326, always_xy=True)
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        east, north = rasterio.transform.xy(ref.transform, yy, xx)
    lon, lat = convert.transform(east, north)
    output = EV / f"{candidate_name}-a-only-reasoning.csv"
    cols = ["candidate_id", "row", "col", "easting_m", "northing_m", "longitude", "latitude",
            "view_A_H55_score", "view_B_surface_score", "basement_depth_band15_native", "slope_band19_native",
            "paired_gravity_RTP_edge_response", "cover_quiet_pair_response", "gravity_signed_LoG_s3",
            "RTP_signed_LoG_s3", "distance_to_catalogue_m", "geological_reasoning",
            "alternative_explanations", "verification_status"]
    with output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        writer.writeheader()
        cover_reference = float(np.median(cover[store.valid]))
        for i, (y, x) in enumerate(zip(yy, xx), 1):
            pair_value = float(pair[y, x])
            cover_value = float(cover[y, x])
            slope_value = float(slope[y, x])
            cover_relation = "above" if cover_value > cover_reference else "at or below"
            if pair_value > 0.0:
                edge_note = (
                    f"Both fields have a nonzero sigma-3 zero-crossing edge response with axial-normal agreement "
                    f"(paired response {pair_value:.8g}). This is consistent with a co-located subsurface edge "
                    "candidate, not proof of a fault."
                )
            else:
                edge_note = (
                    f"The paired sigma-3 gravity/RTP edge response is zero ({pair_value:.1f}) here, so this pixel "
                    "does not have a measured coincident edge pair. Its H55-A score may reflect the learned "
                    "combination of inherited R2 features and separate H55 edge/context channels; do not infer a "
                    "paired edge at this point."
                )
            reasoning = (
                "A-only model stratum: View A is in its training-reference confident tail while the surface-only "
                "View B is in its training-reference abstention band. " + edge_note + " "
                f"Band 15's modelled cover value is {cover_value:.5f} ({cover_relation} the eligible-footprint "
                f"median {cover_reference:.5f}); band 19's stored slope value is {slope_value:.5f}. "
                f"The sigma-3 signed LoG values are gravity {float(glog[y, x]):.8g} and RTP {float(mlog[y, x]):.8g}. "
                "These are input/learner measurements, not calibrated fault probabilities; a lithologic contact, "
                "intrusion, gravity-dependent basin model, magnetic alteration, survey seam, or other non-fault "
                "edge remains plausible. No displacement, geothermal flow, vent, or field confirmation is available."
            )
            writer.writerow(dict(
                candidate_id=f"H55-AONLY-{i:05d}", row=int(y), col=int(x),
                easting_m=round(float(east[i - 1]), 2), northing_m=round(float(north[i - 1]), 2),
                longitude=round(float(lon[i - 1]), 7), latitude=round(float(lat[i - 1]), 7),
                view_A_H55_score=round(float(pa[y, x]), 8), view_B_surface_score=round(float(pb[y, x]), 8),
                basement_depth_band15_native=round(cover_value, 5), slope_band19_native=round(slope_value, 5),
                paired_gravity_RTP_edge_response=round(pair_value, 8),
                cover_quiet_pair_response=round(float(conditioned[y, x]), 8),
                gravity_signed_LoG_s3=round(float(glog[y, x]), 8), RTP_signed_LoG_s3=round(float(mlog[y, x]), 8),
                distance_to_catalogue_m=round(float(distance[y, x]), 2), geological_reasoning=reasoning,
                alternative_explanations="Lithologic/density or susceptibility contact; intrusion/dike; alteration; gravity-dependent model construction; survey/processing seam; roads or erosion in surface layers.",
                verification_status="MODEL HYPOTHESIS ONLY — no independent geological or field validation"))
    return dict(file=output.name, path=str(output.relative_to(ROOT)), rows=len(yy),
                sha256=structural.digest(output), complete=True,
                candidate_scope="one row per emitted H55-candidate pixel in the A-confident/B-abstaining stratum; points are not verified fault segments",
                thresholds={"view_A_H55": qa, "view_B": qb},
                caution="Scores are relative learner outputs, not calibrated fault probabilities; grid-coordinate matches are not field verification.")


def feature_grid(store, name):
    if name not in store.columns:
        raise KeyError(name)
    out = np.zeros(store.valid.size, dtype=np.float32)
    out[store.flat_idx] = store.columns[name]
    return out.reshape(store.valid.shape)


def build_submission():
    holdout_path = EV / "h55_edge_holdout.json"
    if not holdout_path.exists():
        raise FileNotFoundError("H55 holdout is not complete; run --stage validate first")
    holdout = json.loads(holdout_path.read_text())
    if holdout.get("preregistration_sha256") != structural.digest(PREREG):
        raise ValueError("H55 preregistration changed after validation; do not reuse holdout")
    store, feature_manifest = register_columns(structural.FeatureStore(ROOT / "work/r2/features"), build=False)
    cat = labels()
    valid = store.valid
    rows, y, train_receipt = r2.training_rows(cat, valid, valid, cat, R2CFG["seed"] + 100)
    a_names = store.manifest["view_A"] + A_EXTRA
    candidate_names = store.manifest["structural_contrast"] + H55_NAMES
    final_dir = WORK / "final"
    final_dir.mkdir(parents=True, exist_ok=True)

    models, fields, quantiles = {}, {}, {}
    specs = (("view_A_h55", a_names), ("view_B", store.manifest["view_B"]),
             ("structural_contrast_h55", candidate_names))
    for name, columns in specs:
        path = final_dir / f"{name}.joblib"
        log(f"full-data fit {name}: {len(columns)} features, {len(rows):,} sampled rows")
        model = r2.fit(store, rows, y, columns, R2CFG["seed"] + 100)
        joblib.dump(model, path)
        pred = r2.predict(store, model, columns, valid)
        np.save(final_dir / f"{name}.npy", pred)
        models[name], fields[name] = model, pred
        if name in ("view_A_h55", "view_B"):
            quantiles[name] = r2.quantiles(store, model, columns, rows)

    candidate_field = r2.prior_adjust(fields["structural_contrast_h55"], train_receipt["catalogue_prior"])
    emitted, placement = r2.place(candidate_field, valid, cat, valid, CFG["primary_budget_global_pixels"])
    candidate = (emitted > 0).astype(np.float32)
    decoded_hash = sha_bytes(candidate.astype("<f4").tobytes())
    name = f"gems52-h55-grav-rtp-logedge-{int(candidate.sum())}-{decoded_hash[:12]}-zeros.tif"
    submission_path = ROOT / "submission" / name
    download_path = ROOT / "docs/downloads" / name
    submission_path.parent.mkdir(parents=True, exist_ok=True)
    download_path.parent.mkdir(parents=True, exist_ok=True)
    if submission_path.exists() and download_path.exists():
        with rasterio.open(submission_path) as src:
            if not np.array_equal(src.read(1), candidate):
                raise FileExistsError("same deterministic H55 filename has different decoded predictions")
    else:
        with rasterio.open(ROOT / "data/sample_submission.tif") as sample:
            template = sample.read(1, masked=True)
            sample_valid = ~np.ma.getmaskarray(template) & np.isfinite(template.data) & (template.data > -1e38)
            profile = dict(driver="GTiff", width=sample.width, height=sample.height, count=1,
                           dtype="float32", crs=sample.crs, transform=sample.transform,
                           tiled=True, blockxsize=256, blockysize=256, compress="deflate",
                           zlevel=9, predictor=2, nodata=None)
            with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
                with rasterio.open(submission_path, "w", **profile) as dst:
                    dst.write(candidate, 1)
                    dst.write_mask(sample_valid.astype(np.uint8) * 255)
        shutil.copy2(submission_path, download_path)

    fmt = gates.format_report(submission_path, ROOT / "data/sample_submission.tif", footprint=valid)
    if not fmt["ok"] or fmt["n_nonzero"] != int(candidate.sum()):
        raise ValueError(f"H55 on-disk format gate failed: {fmt}")
    with rasterio.open(submission_path) as src:
        readback = src.read(1)
        sample_mask = src.dataset_mask() > 0
    if not np.array_equal(readback, candidate) or not np.array_equal(sample_mask, sample_validity()):
        raise ValueError("H55 TIFF decoded values or internal footprint mask failed round-trip")

    union_field = np.maximum(fields["view_A_h55"], fields["view_B"])
    union_pred, union_placement = r2.place(
        r2.prior_adjust(union_field, train_receipt["catalogue_prior"]), valid, cat, valid,
        CFG["primary_budget_global_pixels"],
    )
    union_cmp = dict(equal=bool(np.array_equal(candidate, union_pred)),
                     candidate_pixels=int(candidate.sum()), union_control_pixels=int(union_pred.sum()),
                     intersection=int(((candidate > 0) & (union_pred > 0)).sum()),
                     candidate_only=int(((candidate > 0) & (union_pred == 0)).sum()),
                     union_only=int(((candidate == 0) & (union_pred > 0)).sum()),
                     placement=union_placement,
                     control="View-A-H55/View-B pointwise maximum, re-emitted by identical metric-aware placer at the same budget; diagnostic only")
    if union_cmp["equal"] or union_cmp["candidate_only"] == 0 or union_cmp["union_only"] == 0:
        raise ValueError("H55 candidate is indistinguishable from the matched-budget max/union control")

    priors, prior_scope = prior_paths(exclude=(submission_path, download_path))
    uniqueness = gates.uniqueness_report(candidate, priors)
    uniqueness["inventory_scope"] = prior_scope
    uniqueness["linked_inventory_all_eligible_files_present"] = not bool(prior_scope["missing"])
    uniqueness["slot_uniqueness_gate_ok"] = bool(uniqueness["ok"] and not prior_scope["missing"])
    uniqueness["research_canonical_distinct"] = bool(uniqueness["canonical_pattern_unique"] and not uniqueness["equals_literal_prior_union"] and not prior_scope["missing"])
    uniqueness["note"] = "Canonical decoded-pattern comparisons are not a proof against unlinked, private, inaccessible, or external-storage submissions. The registered >=20% all-prior support-novelty diagnostic remains fail-closed for slot use."
    if uniqueness["n_priors_checked"] == 0:
        raise ValueError("No prior TIFFs were available; refuse to label the H55 artifact unique")

    holdout_gate = holdout["promotion_gate"]
    format_ok = bool(fmt["ok"])
    uniqueness_ok = bool(uniqueness["slot_uniqueness_gate_ok"])
    score_gate = bool(holdout_gate["meets_mean_lift"] and holdout_gate["meets_fold_support"])
    approved = bool(score_gate and format_ok and uniqueness_ok and not union_cmp["equal"])
    note = (f"H55 paired gravity-RTP LoG edges; {int(candidate.sum()):,} metric-placed cells; "
            f"spatial holdout {'PASSED' if score_gate else 'FAILED'}; {'slot-eligible' if approved else 'research-only, unscored'}.")
    if len(note) > 200:
        raise ValueError("Portal note exceeds 200 characters")
    name_without_ext = Path(name).stem
    reasoning = build_reasoning(
        store, cat, candidate, fields["view_A_h55"], fields["view_B"],
        quantiles["view_A_h55"], quantiles["view_B"], name_without_ext,
    )
    shutil.copy2(EV / reasoning["file"], ROOT / "docs/downloads" / reasoning["file"])

    zip_path = ROOT / "submission" / f"{name_without_ext}.zip"
    zip_download = ROOT / "docs/downloads" / zip_path.name
    for zp in (zip_path, zip_download):
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(submission_path, arcname=name)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.namelist() != [name] or sha_bytes(archive.read(name)) != structural.digest(submission_path):
            raise ValueError("ZIP must contain exactly one GeoTIFF whose bytes match the release")

    receipt = dict(
        generated_utc=now(), hypothesis=CFG["primary_hypothesis"], preregistration="registry/h55_edge_preregistration.json",
        preregistration_sha256=structural.digest(PREREG), feature_manifest_sha256=structural.digest(FEATURE_WORK / "manifest.json"),
        file=name, path=str(submission_path.relative_to(ROOT)), sha256=structural.digest(submission_path),
        decoded_prediction_sha256=decoded_hash, bytes=submission_path.stat().st_size,
        decoded_values_identical_to_written=True, arm="H55-1 signed gravity/RTP LoG edge pair + R2 structural contrast",
        budget=int(candidate.sum()), requested_budget=CFG["primary_budget_global_pixels"],
        emit="metric-aware triangular-kernel expected-coverage greedy at matched global budget; coverage surrogate, not expected DTI",
        placement=placement, training=dict(**train_receipt, seed=R2CFG["seed"] + 100, learner=R2CFG["learner"],
                                           training_rows_sha256=sha_bytes(np.asarray(rows, dtype="<i8").tobytes())),
        format=fmt, uniqueness=uniqueness, view_comparison=dict(matched_budget_max_union=union_cmp,
                          candidate_is_max_or_union=False, a_only_reasoning=reasoning),
        slot_gate=dict(holdout_score_gate=score_gate, format_gate=format_ok, strict_uniqueness_gate=uniqueness_ok,
                       matched_budget_max_union_gate=not union_cmp["equal"], approved_for_weekly_slot=approved,
                       reason=("all registered local gates pass; still unscored/unuploaded" if approved else
                               "one or more preregistered holdout, format, or strict uniqueness gates failed; do not use a weekly slot")),
        approved_for_weekly_slot=approved, promoted=approved, official_score=None,
        official_score_status="no portal upload; no organizer evaluation received",
        submission_note=note, submission_note_chars=len(note), submission_slots_used=0,
        external_data_used=False, organizer_authentication_of_core_input_bytes=False,
        owner_claimed_score_0_2778_not_used_for_labels_or_selection=True,
        external_posterior_or_prior_submission_pixels_used=False,
        no_automatic_portal_upload=True,
        caveats=[
            "Catalogue-zero is a proxy negative; known catalogue faults may be incomplete or inaccurate.",
            "The spatial holdout is known-catalogue hide/recover, not a forecast of new-fault leaderboard performance.",
            "Potential-field edges can be lithologic contacts, intrusions, survey seams or processing/model artifacts; no candidate is fault-confirmed.",
            "The 19-band training cube contains no radiometric bands; none were fabricated or imputed.",
            "Input hashes match owner-pinned mirror values but have not been authenticated against organizer bytes.",
            "The public leaderboard score of 0.2778 is not authenticated to a specific file; this candidate has no official score.",
            "Global uniqueness cannot be established beyond the finite linked/retrievable raster inventory in the receipt.",
        ],
        generative_ai_disclosure="Generative AI was used to inspect the repository, preregister candidate hypotheses, draft and review code/documentation, and assist with analysis. All input data, feature computations, model fits, metric calculations, pixel comparisons, raster read-back checks, and reported local holdout scores were executed by the listed scripts; no hidden labels, portal scores, or prior-submission pixels were supplied as training targets. Human/domain review remains necessary; no geological truth is asserted.",
    )
    receipt_path = EV / "h55_edge_submission.json"
    write_json(receipt_path, receipt)
    write_json(EV / f"submission_{name_without_ext}.json", receipt)
    audit_path = EV / f"{name_without_ext}-audit.json"
    write_json(audit_path, receipt)
    shutil.copy2(audit_path, ROOT / "docs/downloads" / audit_path.name)
    write_json(EV / "h55_edge_uniqueness.json", uniqueness)
    write_json(EV / "h55_edge_release_verification.json", dict(
        generated_utc=now(), file=name, tiff_sha256=receipt["sha256"],
        format_ok=format_ok, decoded_readback_identical=True, exact_template_mask=True,
        zip_contains_exactly_one_tiff=True, zip_tiff_bytes_match=True,
        canonical_pattern_unique=uniqueness["canonical_pattern_unique"],
        strict_support_novelty_gate=uniqueness["support_novelty_gate_ok"],
        matched_budget_max_union_not_equal=not union_cmp["equal"],
        holdout_gate=holdout_gate, slot_approved=approved, official_score=None,
    ))
    # This is an archived H55-EDGE experiment, not the repository's current incumbent.
    # Never move the global LATEST pointer from a research-only follow-up.
    (ROOT / "submission/H55_EDGE_LATEST.txt").write_text(name + "\n")
    log(f"built {name}; format={format_ok}, canonical-pattern-unique={uniqueness['canonical_pattern_unique']}, strict uniqueness={uniqueness_ok}, slot-approved={approved}")
    return receipt


def sample_validity():
    with rasterio.open(ROOT / "data/sample_submission.tif") as src:
        a = src.read(1, masked=True)
        return ~np.ma.getmaskarray(a) & np.isfinite(a.data) & (a.data > -1e38)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("validate", "build", "all"), default="all")
    args = parser.parse_args()
    if args.stage in ("validate", "all"):
        validate()
    if args.stage in ("build", "all"):
        build_submission()


if __name__ == "__main__":
    main()
