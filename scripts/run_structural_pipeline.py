#!/usr/bin/env python3
"""R2 train -> spatial OOF tests -> metric placement -> unique GeoTIFF -> receipts.

CPU-only, deterministic configuration; no competition portal submission. The
preregistered candidate is structural_contrast, never the post-hoc best arm.
Raw/fitted prior submission rasters are ONLY integrity/uniqueness comparisons,
never training features, model targets or a prediction base.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time
import zipfile

# Set before NumPy/sklearn import. The sandbox has two cores, not a GPU requirement.
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import joblib
import numpy as np
import rasterio
from scipy import ndimage as ndi
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits

from gems52 import emit, gates, metric, spatial, structural

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work/r2"
EV = ROOT / "evidence"
PREREG_PATH = ROOT / "registry/r2_preregistration.json"
H55_PREREG_PATH = ROOT / "registry/h55_preregistration.json"
CFG = json.loads(PREREG_PATH.read_text())
H55_CFG = json.loads(H55_PREREG_PATH.read_text())
SEED = CFG["seed"]
ARMS = CFG["arms"]
CACHE_CODE_HASH = structural.digest(__file__)


def cache_signature(store, names, rows, domain):
    return hashlib.sha256(json.dumps(dict(
        pipeline=CACHE_CODE_HASH, prereg=structural.digest(PREREG_PATH),
        h55_prereg=structural.digest(H55_PREREG_PATH),
        feature_manifest=structural.digest(store.directory / 'manifest.json'),
        structural_source=structural.digest(ROOT / 'src/gems52/structural.py'),
        spatial_source=structural.digest(ROOT / 'src/gems52/spatial.py'),
        features=names, training_rows=hashlib.sha256(np.asarray(rows, dtype='<i8').tobytes()).hexdigest(),
        domain=hashlib.sha256(np.packbits(domain).tobytes()).hexdigest(),
        software=__import__('sklearn').__version__), sort_keys=True).encode()).hexdigest()


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def load_data():
    store = structural.FeatureStore(WORK / "features")
    with rasterio.open(ROOT / "data/labels.tif") as src:
        if src.count != 1 or src.shape != store.valid.shape:
            raise ValueError("label/template mismatch")
        cat = src.read(1) == 1
    return store, cat


def training_rows(cat, valid, train, visible, seed):
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero((cat & train & valid).ravel())
    negative = train & valid & (ndi.distance_transform_edt(~visible) > CFG["negative_collar_px"])
    pool = np.flatnonzero(negative.ravel())
    neg = rng.choice(pool, min(len(pool), CFG["max_training_negatives"]), replace=False)
    rows = np.concatenate([pos, neg])
    y = np.concatenate([np.ones(len(pos), np.int8), np.zeros(len(neg), np.int8)])
    order = rng.permutation(len(rows))
    if not len(pos) or not len(neg):
        raise ValueError("training split has only one proxy class")
    return rows[order], y[order], dict(n_positive=len(pos), n_negative=len(neg),
                catalogue_prior=float((cat & train).sum() / max(train.sum(), 1)),
                positive_index_sha256=hashlib.sha256(np.sort(pos).astype('<i8').tobytes()).hexdigest(),
                negative_index_sha256=hashlib.sha256(np.sort(neg).astype('<i8').tobytes()).hexdigest())


def fit(store, rows, y, names, seed, pseudo=None):
    kwargs = {k: v for k, v in CFG["learner"].items() if k != "class"}
    model = HistGradientBoostingClassifier(random_state=seed, **kwargs)
    weights = np.ones(len(y), float)
    if pseudo is not None and len(pseudo):
        rows = np.concatenate([rows, pseudo])
        y = np.concatenate([y, np.ones(len(pseudo), np.int8)])
        weights = np.concatenate([weights, np.full(len(pseudo), CFG["co_training_gate"]["pseudo_weight"])])
    X = store.gather(rows, names)
    with threadpool_limits(limits=2):
        model.fit(X, y, sample_weight=weights)
    return model


def predict(store, model, names, domain, chunk=120000):
    out = np.full(store.valid.size, np.nan, np.float32)
    ids = np.flatnonzero((domain & store.valid).ravel())
    with threadpool_limits(limits=2):
        for a in range(0, len(ids), chunk):
            part = ids[a:a + chunk]
            out[part] = model.predict_proba(store.gather(part, names))[:, 1]
    return out.reshape(store.valid.shape)


def prior_adjust(p, pi):
    """Undo balanced training's 50:50 prior to a catalogue-prevalence PROXY.

    This is not calibration to the hidden new-fault prevalence. We do not infer
    that prevalence from participant scores; it is not identifiable from them.
    """
    p = np.clip(np.nan_to_num(p, nan=0.0), 1e-7, 1 - 1e-7)
    return (p * pi / (p * pi + (1 - p) * (1 - pi))).astype(np.float32)


def quantiles(store, model, names, rows):
    # These are training-only operating ranks, not certified fault probabilities.
    sample = rows[:min(len(rows), 50000)]
    with threadpool_limits(limits=2):
        p = model.predict_proba(store.gather(sample, names))[:, 1]
    return dict(confident=float(np.quantile(p, 0.99)), abstain_lo=float(np.quantile(p, 0.4)),
                abstain_hi=float(np.quantile(p, 0.8)), n_reference=len(sample),
                reference="training sample only; relative confidence, not calibrated fault probability")


def strata(pa, pb, qa, qb, domain):
    ca, cb = pa >= qa["confident"], pb >= qb["confident"]
    aa = (pa >= qa["abstain_lo"]) & (pa <= qa["abstain_hi"])
    ab = (pb >= qb["abstain_lo"]) & (pb <= qb["abstain_hi"])
    out = np.zeros(pa.shape, np.uint8)
    out[ca & cb & domain] = 1
    out[ca & ab & domain] = 2
    out[cb & aa & domain] = 3
    return out


def router(pa, pb, classes, cover):
    # Explicitly asymmetric, not maximum or union. Burial is a soft hypothesis.
    out = np.sqrt(np.maximum(pa, 0) * np.maximum(pb, 0))
    buried = np.clip(np.log1p(np.maximum(cover, 0)) / 8, 0, 1)
    m = classes == 2
    out[m] = pa[m] * (0.35 + 0.40 * buried[m])
    m = classes == 3
    out[m] = 0.25 * pb[m]
    return out


def place(field, region, visible, valid, global_budget):
    allowed = region & valid & ~visible
    k = int(round(global_budget * region.sum() / valid.sum()))
    density = np.where(region & valid & ~visible, np.nan_to_num(field, nan=0.0), 0).astype(np.float32)
    pred, stats = emit.greedy_emit(density, allowed, 0.0, k, pool=min(400000, max(k * 16, 10000)), log=lambda m: None)
    return pred, stats


def score_fold(pred, truth, region, visible):
    pred = np.where(region & ~visible, pred, 0).astype(np.float32)
    result = metric.dti(pred, truth & region)
    result["emitted"] = int((pred > 0).sum())
    return result


def validate():
    store, cat = load_data()
    valid = store.valid
    cover = store.feature_grid("raw_band_15")
    fold_rows, negative_rows, training = [], [], []
    for f in spatial.folds(cat, valid, CFG["buffer_px"]):
        fi = f["fold"]
        fold_dir = WORK / f"fold_{fi}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        log(f"fold {fi}: {f['receipt']}")
        rows, y, sample_receipt = training_rows(cat, valid, f["train"], f["visible"], SEED + fi)
        np.savez(fold_dir / "training_indices.npz", rows=rows, y=y)
        training.append(dict(**f["receipt"], **sample_receipt))
        predictions, models, qs = {}, {}, {}
        for name in ("raw_fusion", "view_A", "view_B", "structural_contrast",
                     "view_B_h55", "structural_contrast_h55"):
            names = store.manifest[name]
            path = fold_dir / (name + ".npy")
            mp = fold_dir / (name + ".joblib")
            cp = fold_dir / (name + '_cache.json')
            signature = cache_signature(store, names, rows, f['region'])
            if path.exists() and mp.exists() and cp.exists() and json.loads(cp.read_text()).get('signature') == signature:
                model = joblib.load(mp)
                pred = np.load(path)
                log(f"fold {fi} cached {name}")
            else:
                log(f"fold {fi} fitting {name}, {len(names)} features, {len(rows)} sampled rows")
                model = fit(store, rows, y, names, SEED + fi)
                joblib.dump(model, mp)
                pred = predict(store, model, names, f["region"])
                np.save(path, pred)
                write_json(cp, dict(signature=signature))
            models[name], predictions[name] = model, pred
            if name in ("view_A", "view_B"):
                qs[name] = quantiles(store, model, names, rows)
        pa, pb = predictions["view_A"], predictions["view_B"]
        classes = strata(pa, pb, qs["view_A"], qs["view_B"], f["region"])
        predictions["naive_union"] = np.maximum(pa, pb)
        predictions["disagreement_router"] = router(pa, pb, classes, cover)
        write_json(fold_dir / "quantiles.json", qs)
        # Negatives truly have held-out predictions; no zero-filled missing-grid fallback.
        neg_eval = valid & f["quadrant"] & f["region"] & (ndi.distance_transform_edt(~cat) > 3)
        negative_rows.extend(spatial.negative_block_errors(pa, pb, neg_eval, fi,
                             (qs["view_A"]["confident"], qs["view_B"]["confident"]),
                             side=CFG["co_training_gate"]["block_side_px"]))
        auc_ids = np.flatnonzero((f["region"] & valid & ~f["visible"]).ravel())
        rng = np.random.default_rng(SEED + fi)
        auc_ids = rng.choice(auc_ids, min(len(auc_ids), 100000), replace=False)
        auc_y = (cat & f["truth"]).ravel()[auc_ids]
        arms = {}
        for name in ARMS:
            field = prior_adjust(predictions[name], sample_receipt["catalogue_prior"])
            pred, placement = place(field, f["region"], f["visible"], valid, CFG["primary_budget_global_pixels"])
            np.save(fold_dir / (name + "_emitted.npy"), pred > 0)
            sc = score_fold(pred, f["truth"], f["region"], f["visible"])
            sc["placement"] = placement
            sc["auc_proxy"] = float(roc_auc_score(auc_y, np.nan_to_num(predictions[name].ravel()[auc_ids]))) if len(np.unique(auc_y)) == 2 else None
            arms[name] = sc
            log(f"fold {fi} {name}: DTI {sc['dti']:.6f}, {sc['emitted']} px")
        for name in ("view_B_h55", "structural_contrast_h55"):
            field = prior_adjust(predictions[name], sample_receipt["catalogue_prior"])
            pred, placement = place(field, f["region"], f["visible"], valid,
                                    CFG["primary_budget_global_pixels"])
            sc = score_fold(pred, f["truth"], f["region"], f["visible"])
            sc["placement"] = placement
            arms[name] = sc
            log(f"fold {fi} {name}: DTI {sc['dti']:.6f}, {sc['emitted']} px")
        fold_rows.append(dict(fold=fi, receipt=f["receipt"], arms=arms))
        del predictions, models

    independence = spatial.independence(negative_rows, CFG["co_training_gate"]["maximum_abs_correlation"],
                                        CFG["co_training_gate"]["minimum_negative_blocks"])
    write_json(EV / "independence_h55.json", independence)
    write_json(EV / "folds_h55.json", training)
    pseudo_report = run_optional_exchange(store, cat, independence)
    write_json(EV / "pseudo_exchange_h55.json", pseudo_report)
    means = {a: float(np.mean([f["arms"][a]["dti"] for f in fold_rows]))
             for a in fold_rows[0]["arms"]}
    primary = "structural_contrast_h55"
    controls = [name for name in means if name != primary]
    best = max(controls, key=lambda a: means[a])
    diffs = [f["arms"][primary]["dti"] - f["arms"][best]["dti"] for f in fold_rows]
    # A small 4-fold proxy is not a reliable prediction of an organizer score.
    lift = float(np.mean(diffs))
    support = sum(d > 0 for d in diffs)
    # The inherited holdout best used a different, defective protocol. No numeric
    # comparison to it is legitimate. Approval remains false until a comparable
    # incumbent refit or a frozen independent confirmation set is available.
    gate = dict(primary=primary, best_comparable_baseline=best, mean_dti_lift=lift,
                positive_folds=support, total_folds=4,
                meets_mean_lift=lift >= CFG["slot_gate"]["minimum_mean_dti_lift"],
                meets_fold_support=support >= CFG["slot_gate"]["minimum_positive_outer_folds"],
                legacy_best_comparable=False, approved_for_slot=False, submission_slots_used=0,
                reason="no comparable frozen incumbent confirmation: legacy whole-hide/tip scores used different protocols and invalid independence diagnostics; do not spend a weekly slot")
    if not gate["meets_mean_lift"] or not gate["meets_fold_support"]:
        gate["reason"] = "preregistered candidate did not beat the strongest comparable baseline by the required lift/fold support; do not spend a weekly slot"
    report = dict(generated_utc=now(), preregistration_sha256=structural.digest(PREREG_PATH),
                  h55_preregistration_sha256=structural.digest(H55_PREREG_PATH),
                  registered_candidate=H55_CFG["primary_hypothesis"],
                  protocol="spatial-quadrant, whole original 8-connected component hide-and-recover, 80-pixel Euclidean training buffer",
                  feature_support_px=store.manifest["support_px"], external_data_used=False,
                  primary_budget_global_pixels=CFG["primary_budget_global_pixels"], means=means,
                  folds=fold_rows, paired_differences_vs_best=diffs, slot_gate=gate,
                  independence_summary={k: v for k, v in independence.items() if k != "blocks"},
                  no_public_score_prediction=True,
                  caveats=["Catalogue-zero negatives can contain unknown faults.", "Spatial catalogue recovery is not organizer new-fault validation.",
                           "Original connected raster components are segment proxies, not authenticated geological fault IDs.",
                           "Four large folds have low inferential power; candidate and controls were fixed before scoring.",
                           "Historical scored fields already used the complete catalogue and cannot be a clean OOF comparator."])
    write_json(EV / "h55_profile_holdout.json", report)
    log(f"H55 primary lift {lift:+.6f} vs {best}; fold support {support}/4; slot approval FALSE")
    return report


def run_optional_exchange(store, cat, independence):
    result = dict(generated_utc=now(), enabled=bool(independence["allow_exchange"]),
                  reason=independence["reason"], rounds=[], used_in_primary=False)
    if not independence["allow_exchange"]:
        return result
    # If the global proxy gate passes, do one separate monitored experiment.
    for f in spatial.folds(cat, store.valid, CFG["buffer_px"]):
        fi, directory = f["fold"], WORK / f"fold_{f['fold']}"
        data = np.load(directory / "training_indices.npz")
        rows, y = data["rows"], data["y"]
        qa = json.loads((directory / "quantiles.json").read_text())["view_A"]
        qb = json.loads((directory / "quantiles.json").read_text())["view_B"]
        pa = predict(store, joblib.load(directory / "view_A.joblib"), store.manifest["view_A"], store.valid)
        pb = predict(store, joblib.load(directory / "view_B.joblib"), store.manifest["view_B"], store.valid)
        forbidden = ndi.binary_dilation(f["visible"], structure=spatial.disk(3))
        forbidden.ravel()[rows] = True
        pseudos = {}
        for donor, receiver, qd, qr, target in ((pa, pb, qa, qb, "view_B"), (pb, pa, qb, qa, "view_A")):
            idx, receipts = spatial.whole_pseudo_segments(donor, receiver, f["train"], forbidden,
                                qd["confident"], qr["abstain_lo"], qr["abstain_hi"],
                                min_pixels=5, cap=2000)
            pseudos[target] = dict(pixels=len(idx), segments=receipts, train_only=bool(f["train"].ravel()[idx].all()),
                                   evaluation_pixels=int(f["region"].ravel()[idx].sum()))
            if len(idx):
                model = fit(store, rows, y, store.manifest[target], SEED + fi, pseudo=idx)
                pred = predict(store, model, store.manifest[target], f["region"])
                pi = float((cat & f["train"]).sum() / f["train"].sum())
                em, _ = place(prior_adjust(pred, pi), f["region"], f["visible"], store.valid, CFG["primary_budget_global_pixels"])
                pseudos[target]["dti_after_exchange"] = score_fold(em, f["truth"], f["region"], f["visible"])["dti"]
        result["rounds"].append(dict(fold=fi, views=pseudos))
    result["reason"] += "; pseudo-label arm is separate and cannot replace the preregistered primary after looking at outer results"
    return result


def prior_paths():
    candidates = []
    inv = EV / "prior_inventory_r2.json"
    if inv.exists():
        candidates += [ROOT / r["local_path"] for r in json.loads(inv.read_text())["entries"] if r.get("eligible_prior")]
    for directory in (ROOT / "data/scored", ROOT / "data/reference", ROOT / "docs/downloads", ROOT / "submission"):
        candidates += sorted(directory.glob("*.tif"))
    return list(dict.fromkeys(p.resolve() for p in candidates if p.exists()))


def reasoning(store, cat, prediction, classes, pa, pb, quantile_values, name):
    """One explicit, falsifiable geological reasoning row per emitted A-only pixel."""
    yy, xx = np.nonzero((prediction > 0) & (classes == 2))
    cover = store.feature_grid("raw_band_15")
    slope = store.feature_grid("raw_band_19")
    anti = store.feature_grid("A_gravity_cover_signed_3")
    persist = store.feature_grid("A_gravity_persistence_3_8")
    coh = store.feature_grid("A_gravity_coherence")
    distance = ndi.distance_transform_edt(~cat) * 100
    from pyproj import Transformer
    convert = Transformer.from_crs(32611, 4326, always_xy=True)
    with rasterio.open(ROOT / "data/sample_submission.tif") as ref:
        east, north = rasterio.transform.xy(ref.transform, yy, xx)
    longitude, latitude = convert.transform(east, north)
    cover_median = float(np.median(cover[store.valid]))
    output = EV / (name + "-candidates.csv")
    columns = ["candidate_id", "row", "col", "easting", "northing", "longitude", "latitude", "view_A_score", "view_B_score",
               "basement_depth_band_value", "slope_band_value", "signed_gravity_cover_alignment", "gravity_scale_persistence", "gravity_coherence",
               "distance_to_catalogue_m", "geological_reasoning", "alternative_explanations", "verification_status"]
    with output.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for i, (y, x) in enumerate(zip(yy, xx)):
            supported = cover[y, x] >= cover_median and anti[y, x] > 0.3 and persist[y, x] > 0.5
            text = ("Potential-field view is in its training-reference confident tail while the surface view abstains. "
                    + ("Deeper-than-median modelled cover, anti-aligned gravity/cover normals and cross-scale gravity persistence are consistent with a covered basin-margin discontinuity. " if supported else
                       "Signed normal/cover support is incomplete; do not interpret this discrepancy as proof of a buried fault. ")
                    + "No fault displacement, geothermal fluid flow or vent has been verified at this pixel.")
            writer.writerow(dict(candidate_id=f"H55-A-{i + 1:05d}", row=int(y), col=int(x), easting=round(float(east[i]), 2), northing=round(float(north[i]), 2),
                                 longitude=round(float(longitude[i]), 7), latitude=round(float(latitude[i]), 7),
                                 view_A_score=round(float(pa[y, x]), 7), view_B_score=round(float(pb[y, x]), 7),
                                 basement_depth_band_value=round(float(cover[y, x]), 5), slope_band_value=round(float(slope[y, x]), 5),
                                 signed_gravity_cover_alignment=round(float(anti[y, x]), 5), gravity_scale_persistence=round(float(persist[y, x]), 5),
                                 gravity_coherence=round(float(coh[y, x]), 5), distance_to_catalogue_m=round(float(distance[y, x]), 2),
                                 geological_reasoning=text, alternative_explanations="Lithologic contact; basin-fill model dependence on gravity; intrusive/dike boundary; processing or coverage effects. Surface-only features may instead be roads or erosion.",
                                 verification_status="MODEL HYPOTHESIS ONLY — requires expert/field review"))
    receipts = dict(rows=len(yy), expected_emitted_A_only_pixels=int(((prediction > 0) & (classes == 2)).sum()),
                    complete=True, file=output.name, sha256=structural.digest(output), thresholds=quantile_values,
                    units_note="Raw band native units have not been authenticated against organizer metadata; gradient-direction and persistence values are dimensionless.",
                    candidate_scope="every emitted A-only pixel; raster components are not claimed to be geologically verified segments",
                    geological_support_url="https://www.usgs.gov/publications/discovering-blind-geothermal-systems-great-basin-region-integrated-geologic-and")
    write_json(EV / "a_only_reasoning_h55.json", receipts)
    shutil.copy2(output, ROOT / "docs/downloads" / output.name)
    return receipts


def build_submission():
    holdout = json.loads((EV / "h55_profile_holdout.json").read_text())
    if (holdout["preregistration_sha256"] != structural.digest(PREREG_PATH) or
            holdout.get("h55_preregistration_sha256") != structural.digest(H55_PREREG_PATH)):
        raise ValueError("R2/H55 preregistration changed after validation; rerun from a clean work directory")
    store, cat = load_data()
    valid = store.valid
    rows, y, train_receipt = training_rows(cat, valid, valid, cat, SEED + 100)
    directory = WORK / "final"
    directory.mkdir(parents=True, exist_ok=True)
    fields, quantile_values = {}, {}
    for arm in ("view_A", "view_B", "structural_contrast_h55"):
        mp, pp = directory / (arm + ".joblib"), directory / (arm + ".npy")
        cp = directory / (arm + '_cache.json')
        signature = cache_signature(store, store.manifest[arm], rows, valid)
        if mp.exists() and pp.exists() and cp.exists() and json.loads(cp.read_text()).get('signature') == signature:
            model, pred = joblib.load(mp), np.load(pp)
        else:
            log(f"full fit {arm}, {len(rows)} rows")
            model = fit(store, rows, y, store.manifest[arm], SEED + 100)
            joblib.dump(model, mp)
            pred = predict(store, model, store.manifest[arm], valid)
            np.save(pp, pred)
            write_json(cp, dict(signature=signature))
        fields[arm] = pred
        if arm in ("view_A", "view_B"):
            quantile_values[arm] = quantiles(store, model, store.manifest[arm], rows)
    classes = strata(fields["view_A"], fields["view_B"], quantile_values["view_A"], quantile_values["view_B"], valid)
    primary = holdout["slot_gate"]["primary"]
    density = prior_adjust(fields[primary], train_receipt["catalogue_prior"])
    prediction, placement = place(density, valid, cat, valid, CFG["primary_budget_global_pixels"])
    decoded_sha = hashlib.sha256(prediction.astype('<f4').tobytes()).hexdigest()
    name = f"gems52-h55-profile-{placement['emitted']}-{decoded_sha[:12]}-research"
    destination = ROOT / "submission" / (name + ".tif")
    download = ROOT / "docs/downloads" / destination.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    download.parent.mkdir(parents=True, exist_ok=True)
    if not np.isfinite(prediction).all() or prediction.min() < 0 or prediction.max() > 1:
        raise ValueError("prediction range/finite gate failed before writing")
    with rasterio.open(ROOT / "data/sample_submission.tif") as sample:
        template = sample.read(1, masked=True)
        sample_valid = ~np.ma.getmaskarray(template) & np.isfinite(template.data) & (template.data > -1e38)
        profile = dict(driver="GTiff", width=sample.width, height=sample.height, count=1,
                       dtype="float32", crs=sample.crs, transform=sample.transform,
                       tiled=True, blockxsize=256, blockysize=256, compress="deflate", zlevel=9,
                       predictor=2, nodata=None)
        # Internal mask gives null outside the sample footprint while all raw values
        # stay in [0,1]. No external .msk companion is needed in a one-file upload.
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
            with rasterio.open(destination, "w", **profile) as dst:
                dst.write(prediction, 1)
                dst.write_mask(sample_valid.astype(np.uint8) * 255)
                dst.update_tags(model="GEMSDOE52 H55 paired-normal profile research model",
                                status="research only; failed spatial holdout gate; not approved for weekly slot",
                                decoded_sha256=decoded_sha)
    fmt = gates.format_report(destination, ROOT / "data/sample_submission.tif", footprint=valid)
    if not fmt["ok"]:
        raise ValueError(f"written GeoTIFF format gate failed: {fmt['problems']}")
    priors = [p for p in prior_paths() if p not in (destination.resolve(), download.resolve())]
    uniqueness = gates.uniqueness_report(prediction, priors, top=None)
    uniqueness["inventory"] = "evidence/prior_inventory_r2.json"
    # Compare against each view's metric-placed output, not just prior submissions.
    comparisons = {}
    masks = []
    for arm in ("view_A", "view_B"):
        p, _ = place(prior_adjust(fields[arm], train_receipt["catalogue_prior"]), valid, cat, valid, CFG["primary_budget_global_pixels"])
        masks.append(p > 0)
        comparisons[arm] = dict(equal=bool(np.array_equal(prediction, p)), intersection=int(((prediction > 0) & (p > 0)).sum()))
    view_union = masks[0] | masks[1]
    comparisons["union"] = dict(equal=bool(np.array_equal(prediction > 0, view_union)),
                               union_pixels=int(view_union.sum()), novel_vs_view_union=int(((prediction > 0) & ~view_union).sum()),
                               view_union_pixels_dropped=int((view_union & ~(prediction > 0)).sum()))
    max_union_prediction, max_union_placement = place(prior_adjust(np.maximum(fields['view_A'], fields['view_B']), train_receipt['catalogue_prior']), valid, cat, valid, CFG['primary_budget_global_pixels'])
    comparisons['matched_budget_max_union'] = dict(equal=bool(np.array_equal(prediction, max_union_prediction)), emitted=int(max_union_prediction.sum()),
        intersection=int(((prediction > 0) & (max_union_prediction > 0)).sum()),
        novel_vs_matched_max_union=int(((prediction > 0) & ~(max_union_prediction > 0)).sum()),
        matched_max_union_pixels_dropped=int(((max_union_prediction > 0) & ~(prediction > 0)).sum()), placement=max_union_placement)
    comparisons["not_merely_union"] = not comparisons["union"]["equal"] and comparisons["union"]["view_union_pixels_dropped"] > 0 and not comparisons['matched_budget_max_union']['equal']
    if not uniqueness['research_publication_ok'] or not comparisons["not_merely_union"]:
        write_json(EV / 'uniqueness_h55.json', uniqueness)
        write_json(EV / 'not_union_h55.json', comparisons)
        raise ValueError("canonical prediction uniqueness/literal-union gate failed; do not publish a renamed prior")
    # Preserve the original saturated-support failure; this is research release,
    # not post-hoc scientific promotion or a change to the registered model.
    if not uniqueness['ok']:
        log('Original >=20% all-prior support-novelty diagnostic FAIL; dense control saturates footprint. Canonical-distinct research release only; no slot approval.')
    shutil.copy2(destination, download)
    with zipfile.ZipFile(download.with_suffix(".zip"), "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(download, arcname=download.name)
    why = reasoning(store, cat, prediction, classes, fields["view_A"], fields["view_B"], quantile_values, name)
    note = f"H55 paired-normal profile | {placement['emitted']:,} metric-placed pixels | spatial holdout failed | research only; not approved for upload."
    with rasterio.open(destination) as src:
        mask_agreement = bool(np.array_equal(src.dataset_mask() > 0, sample_valid))
        written_equal = bool(np.array_equal(src.read(1), prediction))
    if not mask_agreement or not written_equal:
        raise ValueError("internal mask or written prediction bytes disagree with intended output")
    receipt = dict(generated_utc=now(), file=destination.name,
                   submission_name="GEMSDOE52-H55-PairedProfile-" + decoded_sha[:8],
                   note=note, bytes=destination.stat().st_size, sha256=structural.digest(destination), decoded_sha256=decoded_sha,
                   format=fmt, uniqueness=uniqueness, view_comparison=comparisons, stats=placement,
                   model="supervised structural contrast with preregistered H55 DEM profile features; NOT co-trained", pseudo_exchange_used=False,
                   validation=holdout["slot_gate"], promoted=False, forced=False,
                   artifact_status="EXPERIMENTAL — FORMAT CHECKED; DO NOT SPEND A WEEKLY SLOT",
                   official_score=None, source_authentication="owner-mirrored rasters, SHA-pinned but not organizer-authenticated",
                   stats_by_stratum={n: int(((prediction > 0) & (classes == c)).sum()) for c, n in ((0, "other"), (1, "concordant"), (2, "A_only"), (3, "B_only"))},
                   a_only_reasoning=why, internal_mask_matches_sample=mask_agreement,
                   normalization="binary [0,1], all raw cells finite; internal validity mask exactly matches sample footprint",
                   preregistration_sha256=structural.digest(PREREG_PATH),
                   h55_preregistration_sha256=structural.digest(H55_PREREG_PATH),
                   feature_manifest_sha256=structural.digest(WORK / "features/manifest.json"),
                   training=train_receipt, software={"python": platform.python_version(), "numpy": np.__version__, "rasterio": rasterio.__version__,
                                                   "sklearn": __import__('sklearn').__version__})
    write_json(EV / ("submission_" + name + ".json"), receipt)
    write_json(EV / "submission_h55.json", receipt)
    write_json(EV / "uniqueness_h55.json", uniqueness)
    write_json(EV / "not_union_h55.json", comparisons)
    write_json(ROOT / "docs/downloads" / (name + "-audit.json"), receipt)
    # Intentionally do not modify submission/LATEST.txt or R2_LATEST.txt: this
    # candidate failed the registered gate and must not displace an incumbent.
    log(f"WROTE {destination.name} ({receipt['bytes']} bytes); format/canonical-pattern pass; research-only, no slot used")
    return receipt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["features", "validate", "build", "all"], default="all")
    a = ap.parse_args()
    os.chdir(ROOT)
    if a.stage in ("features", "all"):
        manifest_path = WORK / "features/manifest.json"
        rebuild = True
        if manifest_path.exists():
            try:
                cached = json.loads(manifest_path.read_text())
                rebuild = (cached.get("version") != "h55-profile-v1" or
                           "structural_contrast_h55" not in cached or
                           len(cached.get("h55_profile_features", [])) != 20)
            except (OSError, json.JSONDecodeError):
                rebuild = True
        if rebuild:
            structural.build(dest=WORK / "features", log=print)
        write_json(EV / "features_h55.json", json.loads(manifest_path.read_text()))
    if a.stage in ("validate", "all"):
        validate()
    if a.stage in ("build", "all"):
        build_submission()
        from publish_h55_profile_site import publish as publish_h55_profile
        publish_h55_profile()


if __name__ == "__main__":
    main()
