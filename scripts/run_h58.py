#!/usr/bin/env python3
"""Execute the frozen H58-A research protocol on the exact manifest-pinned mirror.

This runner never reads the label-derived CSV distance column, never touches tracked ``data/``
rasters, never queries the competition portal, and never authorizes a competition slot. It writes a
new inference only after input pins, preregistration hashes, holdout receipts, format, and decoded
pattern checks are recorded. The owner-mirror hashes do not authenticate organizer provenance.
"""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import gates, grid as G, h57, h58, metric as M, spatial  # noqa: E402

SEED = 20261007
BUDGETS = {"primary": 37_654, "secondary": 15_000}
Q_CONF = 0.60
Q_ABSTAIN = 0.40
BLOCK_PX = 50
MIN_NEGATIVES_PER_ERROR_BLOCK = 300
N_NEG_TRAIN = 60_000
BUFFER_PX = 80
PREVALENCE = 0.002
PORTAL_NOTE = ("GEMSDOE52 H58-A cold, agreeing geothermometers; research only. "
               "Owner-mirror provenance unresolved; NOT upload-approved.")


def log(message: str) -> None:
    print(f"[h58 {time.strftime('%H:%M:%S')}] {message}", flush=True)


def root_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def file_sha256(path: str | Path) -> str:
    return h58.sha256_file(path)


def write_json(path: str | Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _native(value):
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _gather(layers: h57.Layers, indices: np.ndarray, flat_indices: np.ndarray,
            width: int) -> np.ndarray:
    """Stream selected row-major pixel indices from the layer-major uint8 memmap."""
    flat_indices = np.asarray(flat_indices, dtype=np.int64)
    if not flat_indices.size:
        return np.empty((0, len(indices)), dtype=np.float32)
    rows = flat_indices // width
    order = np.argsort(rows, kind="stable")
    sorted_rows = rows[order]
    out = np.empty((flat_indices.size, len(indices)), dtype=np.float32)
    mm = layers.mm
    unique_rows = np.unique(sorted_rows)
    starts = np.searchsorted(sorted_rows, unique_rows, side="left")
    ends = np.searchsorted(sorted_rows, unique_rows, side="right")
    for row, start, end in zip(unique_rows, starts, ends):
        destinations = order[start:end]
        cols = flat_indices[destinations] - int(row) * width
        block = np.asarray(mm[indices, int(row), :], dtype=np.uint8)
        out[destinations] = block[:, cols].T.astype(np.float32) / 255.0
    return out


def _training_ids(catalogue: np.ndarray, valid: np.ndarray, fit: np.ndarray, seed: int):
    pos, neg = h58.training_pixels(catalogue, valid, fit, seed=seed,
                                   n_neg=N_NEG_TRAIN, clear_px=h57.NEG_CLEAR_PX)
    if pos.size == 0 or neg.size == 0:
        raise RuntimeError(f"empty training sample ({pos.size} positive, {neg.size} negative)")
    return pos, neg


def _fit_predict(layers: h57.Layers, indices: np.ndarray, catalogue: np.ndarray,
                 valid: np.ndarray, fit: np.ndarray, seed: int, tag: str,
                 *, prediction_chunk: int = 500, return_ids: bool = False):
    pos, neg = _training_ids(catalogue, valid, fit, seed)
    width = catalogue.shape[1]
    X = np.vstack([_gather(layers, indices, pos, width),
                   _gather(layers, indices, neg, width)])
    y = np.concatenate([np.ones(pos.size, dtype=np.int8), np.zeros(neg.size, dtype=np.int8)])
    model = h57.fit_view(X, y)
    prediction = h57.predict_grid(model, layers, indices, chunk=prediction_chunk)
    receipt = dict(tag=tag, positive_training_pixels=int(pos.size), negative_training_pixels=int(neg.size),
                   n_features=int(X.shape[1]), coefficient_l2=float(np.linalg.norm(model.coef_)),
                   intercept=float(model.intercept_[0]))
    log(f"{tag}: fit {pos.size:,} positive / {neg.size:,} negative; "
        f"{X.shape[1]} features, |coef|={receipt['coefficient_l2']:.4f}")
    del X, y
    if return_ids:
        return model, prediction, receipt, pos, neg
    return model, prediction, receipt


def _fit_weighted_with_pseudo(layers: h57.Layers, indices: np.ndarray,
                              pos: np.ndarray, neg: np.ndarray, pseudo: np.ndarray):
    """Fit the registered logistic view with pseudo-positive sample weight 0.25."""
    from sklearn.linear_model import LogisticRegression

    width = G.SHAPE[1]
    X = np.vstack([_gather(layers, indices, pos, width),
                   _gather(layers, indices, neg, width),
                   _gather(layers, indices, pseudo, width)])
    y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8),
                        np.ones(pseudo.size, np.int8)])
    weights = np.ones(y.size, dtype=np.float64)
    weights[-pseudo.size:] = 0.25
    model = LogisticRegression(C=1.0, max_iter=400, solver="lbfgs", class_weight="balanced")
    model.fit(X, y, sample_weight=weights)
    del X, y, weights
    return model


def _predict_model(model, layers: h57.Layers, indices: np.ndarray, chunk: int) -> np.ndarray:
    return h57.predict_grid(model, layers, indices, chunk=chunk)


def _dti_crop(prediction: np.ndarray, truth: np.ndarray, region: np.ndarray) -> dict:
    """Exact DTI on the scored region, cropped with a full 300 m halo to reduce block-fold work."""
    rows = np.flatnonzero(region.any(axis=1))
    cols = np.flatnonzero(region.any(axis=0))
    if not rows.size or not cols.size:
        return M.dti(np.zeros((1, 1), np.float32), np.zeros((1, 1), bool))
    pad = int(M.R_PX) + 1
    r0, r1 = max(0, int(rows[0]) - pad), min(region.shape[0], int(rows[-1]) + pad + 1)
    c0, c1 = max(0, int(cols[0]) - pad), min(region.shape[1], int(cols[-1]) + pad + 1)
    return M.dti(prediction[r0:r1, c0:c1], truth[r0:r1, c0:c1])


def _fold_budgets(mode: str, legal: np.ndarray, valid: np.ndarray) -> dict:
    if mode == "hide":
        return dict(BUDGETS)
    share = float(legal.sum()) / max(float(valid.sum()), 1.0)
    return {key: int(math.floor(value * share + 0.5)) for key, value in BUDGETS.items()}


def _score_fold(fold: dict, pa: np.ndarray, pb: np.ndarray, geo: np.ndarray,
                random_field: np.ndarray, valid: np.ndarray, sample_mask: np.ndarray) -> tuple[list[dict], dict]:
    mode, number = fold["mode"], int(fold["fold"])
    region = fold["region"] & valid
    visible = fold["visible"] & valid
    visible_collar = ndimage.binary_dilation(visible, iterations=h57.CORRIDOR_PX)
    legal = region & sample_mask & ~visible_collar
    a_only = h58.a_only_mask(pa, pb, legal, Q_CONF, Q_ABSTAIN)
    fields = {
        "H58-A F_geo": geo,
        "View A": pa,
        "View B": pb,
        "Max(View A, View B)": np.maximum(pa, pb),
        "A-only diagnostic": np.where(a_only, pa, 0.0).astype(np.float32),
        "Seeded random": random_field,
    }
    budgets = _fold_budgets(mode, legal, valid)
    rows = []
    for budget_label in ("primary", "secondary"):
        budget = budgets[budget_label]
        for arm, field in fields.items():
            support = legal & np.isfinite(field) & (field > 0)
            nodes = h57.iso_select(np.nan_to_num(field, nan=0.0, posinf=0.0, neginf=0.0),
                                   support, budget, min_px=3.0, nms_px=5)
            if np.any(nodes & ~legal) or np.any(nodes & visible_collar):
                raise AssertionError(f"{mode}/fold{number}/{arm}: emitted outside common legal pool")
            prediction = nodes.astype(np.float32)
            prediction[visible] = 0.0
            score = _dti_crop(prediction, fold["truth"] & region, region)
            rows.append(dict(
                mode=mode, fold=number, budget_label=budget_label,
                global_budget=int(BUDGETS[budget_label]), requested_budget=int(budget), arm=arm,
                legal_pixels=int(legal.sum()), field_support_pixels=int(support.sum()),
                emitted=int(nodes.sum()), support_shortfall=int(max(budget - int(nodes.sum()), 0)),
                dti=float(score["dti"]), tpw=float(score["tpw"]), fpw=float(score["fpw"]),
                fnw=float(score["fnw"]), n_truth=int(score["n_truth"]),
                actual_truth_prevalence=float(score["n_truth"] / max(int(region.sum()), 1)),
            ))
    fold_receipt = dict(
        fold=number, mode=mode, legal_pixels=int(legal.sum()), region_pixels=int(region.sum()),
        visible_pixels=int(visible.sum()), visible_collar_pixels=int(visible_collar.sum()),
        budget_primary=budgets["primary"], budget_secondary=budgets["secondary"],
        truth_pixels=int((fold["truth"] & region).sum()),
        held_all_pixels=int(fold["held_all"].sum()), fold_split=fold["receipt"],
    )
    return rows, fold_receipt


def _summarize_holdout(rows: list[dict], mode: str) -> dict:
    primary = [r for r in rows if r["mode"] == mode and r["budget_label"] == "primary"]
    fold_results = []
    arm_means = {}
    for arm in sorted({row["arm"] for row in primary}):
        vals = [row["dti"] for row in primary if row["arm"] == arm]
        arm_means[arm] = float(np.mean(vals)) if vals else None
    for fold_id in range(4):
        current = [row for row in primary if row["fold"] == fold_id]
        by_arm = {row["arm"]: row for row in current}
        candidate = by_arm["H58-A F_geo"]
        baselines = [by_arm[name] for name in ("View A", "View B", "Max(View A, View B)")]
        strongest = max(baselines, key=lambda row: row["dti"])
        fold_results.append(dict(
            fold=fold_id, candidate_dti=candidate["dti"], candidate_emitted=candidate["emitted"],
            requested_budget=candidate["requested_budget"], strongest_baseline=strongest["arm"],
            strongest_baseline_dti=strongest["dti"],
            lift=float(candidate["dti"] - strongest["dti"]),
            strict_win=bool(candidate["dti"] > strongest["dti"] + 1e-12),
            budget_comparable=bool(candidate["emitted"] == candidate["requested_budget"]
                                   and strongest["emitted"] == strongest["requested_budget"]),
        ))
    mean_lift = float(np.mean([row["lift"] for row in fold_results]))
    wins = sum(row["strict_win"] for row in fold_results)
    comparable = all(row["budget_comparable"] for row in fold_results)
    gate = bool(comparable and mean_lift >= 0.005 and wins >= 3)
    return dict(
        mode=mode, primary_arm_means=arm_means,
        strongest_same_fold_baseline_mean=float(np.mean(
            [row["strongest_baseline_dti"] for row in fold_results])),
        candidate_mean=float(np.mean([row["candidate_dti"] for row in fold_results])),
        mean_lift_vs_strongest_same_fold_baseline=mean_lift,
        fold_wins=int(wins), fold_count=4, folds=fold_results,
        all_primary_folds_budget_comparable=bool(comparable),
        local_research_gate=gate,
        gate_rule="mean lift >= +0.005, strict win in >=3/4 folds, and full same-budget emission in every primary fold",
    )


def _run_pseudo_diagnostics(folds: list[dict], layers: h57.Layers,
                            idx_a: np.ndarray, idx_b: np.ndarray,
                            catalogue: np.ndarray, valid: np.ndarray, sample_mask: np.ndarray,
                            *, allowed: bool, seed: int, prediction_chunk: int) -> dict:
    """At most one registered whole-segment exchange per outer quadrant, only after the OOF gate."""
    report = dict(ran=False, reason=None, folds=[])
    if not allowed:
        report["reason"] = "fail-closed OOF negative-error independence gate; no pseudo-label model was fitted"
        return report
    components, assigned, quad = h58.component_assignment(catalogue, valid)
    edge_clear = ndimage.distance_transform_edt(valid) > BUFFER_PX
    cat_clearance = ndimage.binary_dilation(catalogue, iterations=5)
    for outer in folds:
        f = int(outer["fold"])
        pseudo_quadrant = (f + 1) % 4
        eval_region = outer["region"] & valid
        eval_distance = ndimage.distance_transform_edt(~eval_region)
        eval_clear = eval_distance > BUFFER_PX
        pseudo_base = valid & (quad == pseudo_quadrant) & eval_clear & edge_clear
        pseudo_distance = ndimage.distance_transform_edt(~pseudo_base)
        base_domain = (valid & (quad != f) & (quad != pseudo_quadrant)
                       & eval_clear & (pseudo_distance > BUFFER_PX) & edge_clear)
        reserved_ids = np.unique(components[((quad == f) | (quad == pseudo_quadrant)) & catalogue])
        reserved_ids = reserved_ids[reserved_ids > 0]
        base_fit = base_domain & ~np.isin(components, reserved_ids)
        receipt = dict(fold=f, pseudo_quadrant=int(pseudo_quadrant),
                       base_fit_pixels=int(base_fit.sum()), pseudo_region_pixels=int(pseudo_base.sum()),
                       evaluation_region_pixels=int(eval_region.sum()), receivers=[])
        try:
            model_a, teacher_a, train_a, pos, neg = _fit_predict(
                layers, idx_a, catalogue, valid, base_fit, seed + 500 + f,
                f"pseudo-teacher-A/outer{f}", prediction_chunk=prediction_chunk, return_ids=True)
            model_b, teacher_b, train_b = _fit_predict(
                layers, idx_b, catalogue, valid, base_fit, seed + 500 + f,
                f"pseudo-teacher-B/outer{f}", prediction_chunk=prediction_chunk)
        except RuntimeError as exc:
            receipt["skipped"] = f"no stable two-quadrant teacher fit: {exc}"
            report["folds"].append(receipt)
            continue
        forbidden = (catalogue | cat_clearance | ~pseudo_base | ~sample_mask | ~edge_clear
                     | ~eval_clear)
        exchanges = (
            ("View A", teacher_b, teacher_a, idx_a),
            ("View B", teacher_a, teacher_b, idx_b),
        )
        auc_mask, auc_positive = h58.pseudo_auc_masks(
            outer["primary_held"], eval_region, valid, edge_clear, cat_clearance)
        auc_values = np.unique(auc_positive[auc_mask])
        for receiver, donor_p, receiver_p, indices in exchanges:
            pseudo_ids, segment_rows = spatial.whole_pseudo_segments(
                donor_p, receiver_p, pseudo_base, forbidden, Q_CONF, Q_ABSTAIN, Q_CONF,
                side=BLOCK_PX, min_pixels=5, cap=2_000)
            item = dict(receiver_view=receiver, donor_threshold=Q_CONF,
                        receiver_abstention_interval=[Q_ABSTAIN, Q_CONF],
                        pseudo_pixels=int(pseudo_ids.size), segment_count=len(segment_rows),
                        segments=segment_rows, sample_weight=0.25,
                        used_in_h58_a_rank_field=False)
            if not pseudo_ids.size:
                item["skipped"] = "no whole 8-connected segment satisfied the registered masks and thresholds"
                receipt["receivers"].append(item)
                continue
            augmented = _fit_weighted_with_pseudo(layers, indices, pos, neg, pseudo_ids)
            after = _predict_model(augmented, layers, indices, prediction_chunk)
            before = teacher_a if receiver == "View A" else teacher_b
            auc_before = auc_after = None
            if auc_mask.any() and len(auc_values) == 2:
                from sklearn.metrics import roc_auc_score
                auc_before = float(roc_auc_score(auc_positive[auc_mask], before[auc_mask]))
                auc_after = float(roc_auc_score(auc_positive[auc_mask], after[auc_mask]))
            legal = eval_region & valid & sample_mask & ~ndimage.binary_dilation(
                outer["visible"] & valid, iterations=h57.CORRIDOR_PX)
            budget = _fold_budgets("block", legal, valid)["primary"]
            before_nodes = h57.iso_select(before, legal & (before > 0), budget, min_px=3.0, nms_px=5)
            after_nodes = h57.iso_select(after, legal & (after > 0), budget, min_px=3.0, nms_px=5)
            before_score = _dti_crop(before_nodes.astype(np.float32),
                                     outer["truth"] & eval_region, eval_region)
            after_score = _dti_crop(after_nodes.astype(np.float32),
                                    outer["truth"] & eval_region, eval_region)
            item.update(requested_budget=budget,
                        before_dti=float(before_score["dti"]), after_dti=float(after_score["dti"]),
                        delta_dti=float(after_score["dti"] - before_score["dti"]),
                        auc_before=auc_before, auc_after=auc_after,
                        delta_auc=(None if auc_before is None or auc_after is None
                                   else float(auc_after - auc_before)),
                        evaluation_positive_pixels=int(auc_positive[auc_mask].sum()),
                        evaluation_pixels=int(auc_mask.sum()))
            receipt["receivers"].append(item)
            del augmented, after, before_nodes, after_nodes
            gc.collect()
        report["folds"].append(receipt)
        del model_a, model_b, teacher_a, teacher_b, pos, neg
        gc.collect()
    report["ran"] = True
    report["reason"] = "one registered whole-segment diagnostic exchange was attempted per outer fold; pseudo labels never alter H58-A"
    report["settings"] = dict(folds=4, pseudo_quadrant="next quadrant cyclically",
                               base_quadrants=2, buffer_px=BUFFER_PX, block_px=BLOCK_PX,
                               minimum_segment_pixels=5, max_pixels_per_receiver_fold=2_000,
                               pseudo_weight=0.25)
    return report


def _xy(row: int, col: int) -> tuple[float, float]:
    xres, _, x0, _, yres, y0 = G.TRANSFORM
    return x0 + (col + 0.5) * xres, y0 + (row + 0.5) * yres


def _write_reasoning_csv(path: Path, nodes: np.ndarray, *, sites,
                         geo_field: np.ndarray, pa: np.ndarray, pb: np.ndarray,
                         depth: np.ndarray, slope: np.ndarray, kind: str) -> dict:
    """Write one coordinate-specific, falsifiable geological note per emitted candidate pixel."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows, cols = np.nonzero(nodes)
    if rows.size:
        distance_m, nearest = h58.nearest_site_rows(sites, rows, cols)
    else:
        distance_m, nearest = np.empty(0), np.empty(0, dtype=np.int64)
    columns = [
        "candidate_id", "candidate_kind", "row", "col", "x_utm_m", "y_utm_m",
        "p_A_block_oof", "p_B_block_oof", "F_geo", "nearest_site_distance_m",
        "nearest_site_row", "nearest_site_col", "measured_temp_c",
        "geothermquartz_c", "geothermcat_c", "geothermometer_difference_c",
        "modelled_depth_to_basement_band15", "detrended_elevation_slope_band19",
        "geological_reasoning", "alternative_and_falsifier", "verification_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for i, (row, col) in enumerate(zip(rows.tolist(), cols.tolist())):
            site = sites.iloc[int(nearest[i])]
            distance = float(distance_m[i])
            geo = float(geo_field[row, col])
            temp = float(site["temp_c"])
            quartz = float(site["geothermquartz_c"])
            cation = float(site["geothermcat_c"])
            gap = abs(quartz - cation)
            if kind == "H58-A output":
                reason = (f"Within {distance:.0f} m of a qualifying cold discharge; quartz and cation "
                          f"reservoir estimates are {quartz:.1f} C and {cation:.1f} C (gap {gap:.1f} C). "
                          f"The frozen H58-A field value is {geo:.3f}; this is a thermal/geochemical "
                          "permeability hypothesis, not a mapped fault.")
            elif distance <= h58.FIELD_RADIUS_M:
                reason = (f"A-only block-OOF diagnostic (p_A={pa[row, col]:.3f}, p_B={pb[row, col]:.3f}) "
                          f"is within {distance:.0f} m of a qualified cold discharge (F_geo={geo:.3f}); "
                          f"modelled basement depth is {depth[row, col]:.1f} and band-19 surface slope "
                          f"is {slope[row, col]:.3f}. A concealed permeable structure is one interpretation.")
            else:
                reason = (f"A-only block-OOF diagnostic (p_A={pa[row, col]:.3f}, p_B={pb[row, col]:.3f}); "
                          "no qualifying H58-A site lies within 5 km, so this pixel is not supported by "
                          "the registered geochemical field. Treat as a separate model-only diagnostic.")
            alternative = ("An apparent anomaly may instead be a lithologic/contact response, geophysical "
                           "inversion or interpolation artifact, or (for surface context) drainage/cover "
                           "contrast. Falsifier: independent mapping or field evidence finds no fault-related "
                           "offset/permeability, or the source-water chemistry/geothermometer assumptions fail.")
            x, y = _xy(row, col)
            writer.writerow(dict(
                candidate_id=f"{kind.replace(' ', '-')}-{i + 1:06d}", candidate_kind=kind,
                row=row, col=col, x_utm_m=f"{x:.1f}", y_utm_m=f"{y:.1f}",
                p_A_block_oof=f"{float(pa[row, col]):.6f}", p_B_block_oof=f"{float(pb[row, col]):.6f}",
                F_geo=f"{geo:.6f}", nearest_site_distance_m=f"{distance:.1f}",
                nearest_site_row=int(site["row"]), nearest_site_col=int(site["col"]),
                measured_temp_c=f"{temp:.3f}", geothermquartz_c=f"{quartz:.3f}",
                geothermcat_c=f"{cation:.3f}", geothermometer_difference_c=f"{gap:.3f}",
                modelled_depth_to_basement_band15=f"{float(depth[row, col]):.3f}",
                detrended_elevation_slope_band19=f"{float(slope[row, col]):.6f}",
                geological_reasoning=reason, alternative_and_falsifier=alternative,
                verification_status="Hypothesis only; not an independently mapped or verified fault.",
            ))
    return dict(path=str(path), rows=int(rows.size), columns=columns,
                sha256=file_sha256(path), bytes=path.stat().st_size,
                one_reason_per_emitted_candidate=(int(rows.size) == int(nodes.sum())))


def _verify_raster_grids(data_root: Path) -> dict:
    sources = {
        "training_features.tif": data_root / "training_features.tif",
        "labels.tif": data_root / "labels.tif",
        "sample_submission.tif": data_root / "sample_submission.tif",
    }
    for p, _, _ in h57.FEATURE_BANDS + h57.EXTERNAL_BANDS:
        rel = Path(p).relative_to("data")
        sources[rel.as_posix()] = h57.data_root_path(p, data_root)
    profiles, failures, visited = {}, [], set()
    for key, path in sources.items():
        identity = path.resolve()
        if identity in visited:
            continue
        visited.add(identity)
        with rasterio.open(path) as src:
            transform = tuple(float(v) for v in src.transform)[:6]
            profile = dict(path=str(path), bands=int(src.count), dtype=src.dtypes[0],
                           shape=[int(src.height), int(src.width)], crs=str(src.crs),
                           transform=list(transform), resolution=[float(v) for v in src.res])
        ok = (tuple(profile["shape"]) == G.SHAPE and profile["crs"] == G.CRS_EPSG
              and tuple(profile["transform"]) == tuple(G.TRANSFORM)
              and tuple(profile["resolution"]) == (G.CELL_M, G.CELL_M))
        profile["matches_pinned_competition_grid"] = bool(ok)
        profiles[key] = profile
        if not ok:
            failures.append(key)
    if failures:
        raise RuntimeError(f"pinned raster grid mismatch: {failures}")
    return profiles


def _primary_emission_gate(modes: dict) -> dict:
    return dict(
        holdout_pass_both_modes=all(modes[name]["local_research_gate"] for name in ("hide", "block")),
        modes={name: dict(passed=modes[name]["local_research_gate"],
                          mean_lift=modes[name]["mean_lift_vs_strongest_same_fold_baseline"],
                          wins=modes[name]["fold_wins"],
                          budgets_comparable=modes[name]["all_primary_folds_budget_comparable"])
               for name in ("hide", "block")},
    )


def _run(args) -> int:
    t0 = time.time()
    data_root = root_path(args.data_root)
    work_dir = root_path(args.work_dir)
    registry_path = ROOT / "registry/h58_preregistration.json"
    manifest_path = ROOT / "registry/data_manifest.json"
    receipt_path = data_root / "restore_receipt.json"
    prereg = h58.verify_preregistration(registry_path)
    prereg_registry = prereg["registry"]
    restore = json.loads(receipt_path.read_text())
    if restore.get("all_ok") is not True:
        raise RuntimeError("staged restore receipt is not all_ok; refusing to run")
    input_receipts = h58.verify_manifest(manifest_path, data_root)
    log(f"verified {len(input_receipts)} input SHA/byte pins in {data_root}; "
        "these are owner-mirror pins, not organizer authentication")
    grid_receipts = _verify_raster_grids(data_root)
    work_dir.mkdir(parents=True, exist_ok=True)

    feature_path = data_root / "training_features.tif"
    labels_path = data_root / "labels.tif"
    sample_path = data_root / "sample_submission.tif"
    valid = G.footprint_from(feature_path, bands="all")
    sample_mask = G.footprint_from(sample_path, bands="all")
    with rasterio.open(labels_path) as src:
        label_values = src.read(1)
    catalogue = (label_values == 1) & valid
    log(f"all-band-valid pixels={int(valid.sum()):,}; sample finite-domain pixels="
        f"{int(sample_mask.sum()):,}; visible catalogue pixels={int(catalogue.sum()):,}")

    csv_declared = Path(prereg_registry["h58_a"]["source_csv"])
    data_root_declared = Path(prereg_registry["data_integrity"]["data_root"])
    csv_rel = csv_declared.relative_to(data_root_declared)
    csv_path = data_root / csv_rel
    sites, site_audit = h58.qualify_sites(csv_path, valid)
    if site_audit["threshold_qualifying_rows"] != 22 or site_audit["unique_qualified_sites"] != 20:
        raise RuntimeError("qualifying-site coverage differs from the frozen pre-holdout audit: "
                           f"{site_audit['threshold_qualifying_rows']} rows / "
                           f"{site_audit['unique_qualified_sites']} cells")
    geo_field, site_mask, site_distance = h58.geothermometer_field(valid, sites)
    log(f"H58-A qualified sites={len(sites)}; positive field support="
        f"{int((geo_field > 0).sum()):,} valid pixels; distance scale=5 km")
    del site_mask, site_distance

    layers_dir = work_dir / "layers"
    build_t0 = time.time()
    layer_meta = h57.build_layers(work=str(layers_dir), chunk=args.layer_chunk,
                                  data_dir=str(data_root))
    layers = h57.Layers(str(layers_dir))
    idx_a = layers.index([f"{name}_{suffix}" for name in h57.VIEW_A_LAYERS
                          for suffix in ("val", "grad", "range")])
    idx_b = layers.index([f"{name}_{suffix}" for name in h57.VIEW_B_LAYERS
                          for suffix in ("val", "grad", "range")])
    if len(idx_a) == 0 or len(idx_b) == 0:
        raise RuntimeError("H57 view specification resolved to an empty feature matrix")
    log(f"feature stack ready ({time.time() - build_t0:.1f}s); "
        f"View A={len(idx_a)} columns, View B={len(idx_b)} columns")

    holdout_rows, fold_receipts = [], {"hide": [], "block": []}
    block_folds = h58.make_folds(catalogue, valid, buffer_px=BUFFER_PX,
                                 prevalence=PREVALENCE, seed=SEED, mode="block")
    pa_oof = np.full(G.SHAPE, np.nan, dtype=np.float32)
    pb_oof = np.full(G.SHAPE, np.nan, dtype=np.float32)
    error_negative = valid & ~ndimage.binary_dilation(catalogue, iterations=h57.NEG_CLEAR_PX)
    for fold in block_folds:
        f = int(fold["fold"])
        model_a, pa, train_a = _fit_predict(
            layers, idx_a, catalogue, valid, fold["fit"], SEED + f,
            f"block-A/f{f}", prediction_chunk=args.prediction_chunk)
        model_b, pb, train_b = _fit_predict(
            layers, idx_b, catalogue, valid, fold["fit"], SEED + f,
            f"block-B/f{f}", prediction_chunk=args.prediction_chunk)
        quadrant = fold["quadrant_mask"]
        pa_oof[quadrant] = pa[quadrant]
        pb_oof[quadrant] = pb[quadrant]
        rows, fold_receipt = _score_fold(
            fold, pa, pb, geo_field,
            np.random.default_rng(SEED + 10_000 + f).random(G.SHAPE, dtype=np.float32),
            valid, sample_mask)
        holdout_rows.extend(rows)
        fold_receipt["model_A"] = train_a
        fold_receipt["model_B"] = train_b
        fold_receipts["block"].append(fold_receipt)
        log(f"block fold {f}: {len(rows)} arm/budget scores, held truth="
            f"{fold_receipt['truth_pixels']:,}, train labels="
            f"{train_a['positive_training_pixels']:,}")
        del model_a, model_b, pa, pb
        gc.collect()

    if not np.isfinite(pa_oof[valid]).all() or not np.isfinite(pb_oof[valid]).all():
        raise RuntimeError("block OOF probabilities do not cover the full all-band-valid footprint")
    np.save(work_dir / "pa_oof_block.npy", pa_oof)
    np.save(work_dir / "pb_oof_block.npy", pb_oof)
    error_rows = spatial.negative_block_errors(
        pa_oof, pb_oof, error_negative & valid, fold=-1, thresholds=(Q_CONF, Q_CONF),
        side=BLOCK_PX, minimum=MIN_NEGATIVES_PER_ERROR_BLOCK)
    independence = spatial.independence(error_rows, threshold=0.60, min_blocks=20)
    independence.update(block_px=BLOCK_PX, minimum_negative_pixels_per_block=MIN_NEGATIVES_PER_ERROR_BLOCK,
                        error_metrics=["negative MSE", "false-positive rate at 0.60"],
                        correlations=["Pearson", "tie-aware Spearman"],
                        oof_fold_map="four contiguous quadrants; whole majority-assigned labels held out; block-crossing components quarantined from fit/visible masks")
    log(f"OOF dependence: {independence['n_blocks']} usable spatial error blocks, "
        f"max |r|={independence['max_abs_correlation']}; allow_exchange={independence['allow_exchange']}")

    hide_folds = h58.make_folds(catalogue, valid, buffer_px=BUFFER_PX,
                                prevalence=PREVALENCE, seed=SEED, mode="hide")
    for fold in hide_folds:
        f = int(fold["fold"])
        model_a, pa, train_a = _fit_predict(
            layers, idx_a, catalogue, valid, fold["fit"], SEED + f,
            f"hide-A/f{f}", prediction_chunk=args.prediction_chunk)
        model_b, pb, train_b = _fit_predict(
            layers, idx_b, catalogue, valid, fold["fit"], SEED + f,
            f"hide-B/f{f}", prediction_chunk=args.prediction_chunk)
        rows, fold_receipt = _score_fold(
            fold, pa, pb, geo_field,
            np.random.default_rng(SEED + 20_000 + f).random(G.SHAPE, dtype=np.float32),
            valid, sample_mask)
        holdout_rows.extend(rows)
        fold_receipt["model_A"] = train_a
        fold_receipt["model_B"] = train_b
        fold_receipts["hide"].append(fold_receipt)
        log(f"hide fold {f}: {len(rows)} arm/budget scores, held truth="
            f"{fold_receipt['truth_pixels']:,}, train labels="
            f"{train_a['positive_training_pixels']:,}")
        del model_a, model_b, pa, pb
        gc.collect()

    modes = {name: _summarize_holdout(holdout_rows, name) for name in ("hide", "block")}
    local_holdout_gate = _primary_emission_gate(modes)
    pseudo = _run_pseudo_diagnostics(
        block_folds, layers, idx_a, idx_b, catalogue, valid, sample_mask,
        allowed=bool(independence["allow_exchange"]), seed=SEED,
        prediction_chunk=args.prediction_chunk)
    del hide_folds
    gc.collect()

    # Per-candidate A-only reasons use only the four-quadrant block-OOF fields.
    a_only_legal = valid & sample_mask & ~ndimage.binary_dilation(
        catalogue, iterations=h57.CORRIDOR_PX)
    a_only_candidates = h58.a_only_mask(pa_oof, pb_oof, a_only_legal, Q_CONF, Q_ABSTAIN)
    a_only_nodes = h57.iso_select(pa_oof, a_only_candidates, BUDGETS["primary"],
                                  min_px=3.0, nms_px=5)
    depth = G.read_band(feature_path, 15)
    slope = G.read_band(feature_path, 19)

    submissions_dir = ROOT / "submission"
    downloads_dir = ROOT / "docs/downloads"
    submissions_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    final_legal = valid & sample_mask & ~ndimage.binary_dilation(
        catalogue, iterations=h57.CORRIDOR_PX)
    final_candidates = final_legal & (geo_field > 0)
    nodes = h57.iso_select(geo_field, final_candidates, BUDGETS["primary"],
                           min_px=3.0, nms_px=5)
    prediction = nodes.astype(np.float32)
    prediction[~sample_mask] = 0.0
    prediction[~valid] = 0.0
    actual_pixels = int((prediction > 0).sum())
    pixel_sha = hashlib.sha256(prediction.astype("<f4", copy=False).tobytes()).hexdigest()
    stem = f"gems52-h58-coldgeo-consensus-{actual_pixels}px-{pixel_sha[:10]}-research"
    filename = stem + ".tif"
    output_path = submissions_dir / filename
    download_path = downloads_dir / filename
    writer_receipt = G.write_geotiff(output_path, prediction)
    with rasterio.open(output_path) as src:
        decoded = src.read(1)
    if not np.array_equal(decoded, prediction):
        raise RuntimeError("written H58 TIFF does not decode to the generated prediction array")
    if np.any((decoded > 0) & ~final_legal):
        raise RuntimeError("H58 artifact contains an emission outside the frozen final legal pool")
    if np.any((decoded > 0) & ~sample_mask):
        raise RuntimeError("H58 artifact has nonzero values outside the sample finite domain")
    if not np.isfinite(decoded).all() or float(decoded.min()) < 0.0 or float(decoded.max()) > 1.0:
        raise RuntimeError("H58 artifact failed the raw [0,1] finite-pixel check")
    if actual_pixels:
        from scipy.spatial import cKDTree
        points = np.argwhere(decoded > 0).astype(np.float64)
        nearest_sep = float(cKDTree(points).query(points, k=2)[0][:, 1].min())
    else:
        nearest_sep = None

    # Scan accessible prior rasters before staging this new filename into docs/downloads.
    prior_roots = [submissions_dir, downloads_dir, ROOT / "docs", ROOT / "data/scored", ROOT / "data/reference"]
    priors = gates.find_priors(prior_roots, exclude=output_path)
    uniqueness = gates.uniqueness_report(decoded, priors)
    format_report = gates.format_report(output_path, sample_path, footprint=sample_mask)
    if download_path != output_path:
        shutil.copy2(output_path, download_path)
    if file_sha256(download_path) != writer_receipt["sha256"]:
        raise RuntimeError("GitHub Pages copy differs from the audited submission TIFF")

    # Same-budget decoded comparisons against the four-quadrant OOF baselines.
    baseline_fields = {
        "View A": pa_oof,
        "View B": pb_oof,
        "Max(View A, View B)": np.maximum(pa_oof, pb_oof),
        "A-only diagnostic": np.where(a_only_legal & (pa_oof >= Q_CONF) & (pb_oof <= Q_ABSTAIN),
                                       pa_oof, 0.0).astype(np.float32),
    }
    set_relations = {}
    for name, field in baseline_fields.items():
        field_allowed = final_legal & np.isfinite(field) & (field > 0)
        baseline_nodes = h57.iso_select(np.nan_to_num(field, nan=0.0), field_allowed,
                                        BUDGETS["primary"], min_px=3.0, nms_px=5)
        intersection = int((nodes & baseline_nodes).sum())
        union = int((nodes | baseline_nodes).sum())
        set_relations[name] = dict(
            baseline_emitted=int(baseline_nodes.sum()),
            exact_decoded_match=bool(np.array_equal(decoded, baseline_nodes.astype(np.float32))),
            intersection=int(intersection),
            jaccard=float(intersection / max(union, 1)),
            candidate_only_pixels=int((nodes & ~baseline_nodes).sum()),
            baseline_only_pixels=int((baseline_nodes & ~nodes).sum()),
        )
        del baseline_nodes
        gc.collect()

    # One coordinate-specific geology/falsifier row for every H58-A output and A-only proposal.
    h58_reasoning = _write_reasoning_csv(
        downloads_dir / f"{stem}-reasoning.csv", nodes, sites=sites,
        geo_field=geo_field, pa=pa_oof, pb=pb_oof, depth=depth, slope=slope,
        kind="H58-A output")
    a_only_reasoning = _write_reasoning_csv(
        downloads_dir / f"{stem}-a-only-reasoning.csv", a_only_nodes, sites=sites,
        geo_field=geo_field, pa=pa_oof, pb=pb_oof, depth=depth, slope=slope,
        kind="A-only diagnostic")
    log(f"artifact {filename}: {actual_pixels:,}/{BUDGETS['primary']:,} requested nodes; "
        f"format={format_report['ok']}, decoded-pattern={uniqueness['canonical_pattern_unique']}, "
        f"min NN={nearest_sep}")

    integrity_ok = all(row["matches_pin"] for row in input_receipts)
    format_ok = bool(format_report["ok"] and writer_receipt["bands"] == 1
                     and writer_receipt["dtype"] == "float32")
    unique_ok = bool(uniqueness["canonical_pattern_unique"] and uniqueness["research_publication_ok"])
    reasoning_ok = bool(h58_reasoning["one_reason_per_emitted_candidate"]
                        and a_only_reasoning["one_reason_per_emitted_candidate"])
    artifact_gates = dict(input_integrity=integrity_ok, format=format_ok,
                          decoded_pattern_uniqueness=unique_ok, per_candidate_reasoning=reasoning_ok,
                          candidate_support_capacity=(actual_pixels == BUDGETS["primary"]),
                          nearest_neighbor_separation=(nearest_sep is None or nearest_sep >= 3.0 - 1e-9),
                          no_catalogue_corridor_emissions=not bool((nodes & ~final_legal).any()),
                          sample_domain_only=not bool((nodes & ~sample_mask).any()))
    critical_ir_open = False
    irregularities = json.loads((ROOT / "registry/irregularities.json").read_text())
    entries = irregularities.get("entries", irregularities if isinstance(irregularities, list) else [])
    for entry in entries:
        if entry.get("id") == "IR-H58-001":
            status = str(entry.get("status", "")).lower()
            critical_ir_open = "open" in status and "critical" in status
            break
    local_slot_gate = bool(local_holdout_gate["holdout_pass_both_modes"]
                           and all(artifact_gates.values()))
    upload_approved = False  # no organizer-authenticated input/performance evidence exists in this run
    promotion_reason = (
        "NOT approved: owner-mirror versus tracked/organizer input provenance is unresolved (IR-H58-001); "
        "local catalogue holdout is not an organizer score and cannot authorize a weekly slot."
        if critical_ir_open else
        "NOT approved: this execution has no organizer-authenticated input and performance receipt.")
    result = dict(
        schema_version=1, round="H58", candidate="H58-A", version=prereg_registry["version"],
        run_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        status="research_only_not_upload_approved",
        preregistration=dict(path="registry/h58_preregistration.json",
                             hypothesis_document=prereg_registry["hypothesis_document"],
                             hypothesis_document_sha256=prereg_registry["hypothesis_document_sha256"],
                             registry_sha256=file_sha256(registry_path), checks=prereg["checks"],
                             protocol_amendment=prereg_registry.get("protocol_amendment"),
                             additional_pre_score_clarification=prereg_registry.get(
                                 "additional_pre_score_clarification")),
        code_hashes={str(path.relative_to(ROOT)): file_sha256(path) for path in (
            ROOT / "scripts/run_h58.py", ROOT / "src/gems52/h58.py", ROOT / "src/gems52/h57.py",
            ROOT / "src/gems52/spatial.py", ROOT / "src/gems52/metric.py")},
        data_root=str(data_root.relative_to(ROOT) if data_root.is_relative_to(ROOT) else data_root),
        data_provenance="owner-supplied manifest-pinned mirror; organizer authentication unresolved",
        manifest_sha256=file_sha256(manifest_path), manifest_inputs=input_receipts,
        staged_restore_receipt=dict(path=str(receipt_path.relative_to(ROOT)), all_ok=restore["all_ok"]),
        grid_profiles=grid_receipts,
        grid_counts=dict(all_band_valid=int(valid.sum()), sample_finite_domain=int(sample_mask.sum()),
                         catalogue_positive_within_valid=int(catalogue.sum())),
        h58_a=dict(source_csv=str(csv_path.relative_to(ROOT)), csv_sha256=file_sha256(csv_path),
                   site_audit=site_audit,
                   selected_sites=[{key: _native(value) for key, value in row.items()}
                                   for row in sites.to_dict(orient="records")],
                   field=dict(radius_m=h58.FIELD_RADIUS_M, support_pixels=int((geo_field > 0).sum()),
                              formula=prereg_registry["h58_a"]["field"], sole_rank_field=True,
                              no_forbidden_label_distance_read=True)),
        layer_stack=dict(cache_dir=str(layers_dir.relative_to(ROOT)),
                         feature_count=int(len(layer_meta["names"])),
                         view_a_features=int(len(idx_a)), view_b_features=int(len(idx_b)),
                         build_seconds=round(time.time() - build_t0, 2),
                         source_data_root=str(data_root)),
        holdout=dict(seed=SEED, prevalence=PREVALENCE, buffer_px=BUFFER_PX,
                     folds=fold_receipts, mode_summary=modes, rows=holdout_rows,
                     local_promotion_gate=local_holdout_gate,
                     local_holdout_is_not_organizer_validation=True),
        independence=independence, pseudo_label_diagnostic=pseudo,
        artifact=dict(file=filename, submission_name=f"GEMSDOE52-H58-A-ColdGeo-{pixel_sha[:10]}",
                      sha256=writer_receipt["sha256"], decoded_prediction_sha256=uniqueness["candidate_decoded_sha256"],
                      bytes=writer_receipt["bytes"], path=str(output_path.relative_to(ROOT)),
                      pages_path=str(download_path.relative_to(ROOT)), emitted_pixels=actual_pixels,
                      requested_pixels=BUDGETS["primary"], support_shortfall=max(BUDGETS["primary"] - actual_pixels, 0),
                      min_nearest_neighbor_px=nearest_sep, writer_receipt=writer_receipt,
                      format_gate=format_report, uniqueness=uniqueness,
                      same_budget_oof_comparisons=set_relations,
                      reasoning=h58_reasoning, a_only_reasoning=a_only_reasoning,
                      artifact_gates=artifact_gates, all_artifact_gates_pass=all(artifact_gates.values()),
                      status="research only — NOT approved to submit"),
        local_research_gate_passed=local_slot_gate,
        critical_integrity_ir_open=critical_ir_open,
        organizer_authenticated_performance=False,
        approved_for_weekly_slot=upload_approved,
        submission_slots_used=0,
        promotion_decision=promotion_reason,
        portal=dict(uploaded=False, score=None, note=PORTAL_NOTE, note_characters=len(PORTAL_NOTE),
                    note_limit=200, approval="NOT approved to submit; do not use this candidate for a slot"),
        elapsed_seconds=round(time.time() - t0, 2),
    )
    write_json(ROOT / "evidence/h58_holdout.json", dict(
        schema_version=1, round="H58", candidate="H58-A", seed=SEED,
        modes=modes, folds=fold_receipts, rows=holdout_rows,
        independence=independence, pseudo_label_diagnostic=pseudo,
        local_holdout_gate=local_holdout_gate,
        caution="These are catalogue-proxy holdout scores on an owner-supplied mirror; they are not organizer-authenticated validation."))
    write_json(ROOT / "evidence/h58_result.json", result)
    write_json(ROOT / f"evidence/submission_{stem}.json", dict(
        schema_version=1, round="H58", file=filename, stem=stem,
        file_path=str(output_path.relative_to(ROOT)), pages_path=str(download_path.relative_to(ROOT)),
        bytes=writer_receipt["bytes"], sha256=writer_receipt["sha256"],
        decoded_prediction_sha256=uniqueness["candidate_decoded_sha256"],
        submission_name=result["artifact"]["submission_name"], submission_note=PORTAL_NOTE,
        note=PORTAL_NOTE, submission_note_chars=len(PORTAL_NOTE),
        nonzero_px=actual_pixels, emitted_pixels=actual_pixels, promoted=False,
        short_tif="h58-candidate.tif", short_zip="h58-candidate.zip",
        format=format_report, format_gate=format_report,
        uniqueness=uniqueness, holdout_gate=local_holdout_gate,
        approved_for_weekly_slot=False, promotion=promotion_reason,
        artifact_status="RESEARCH ONLY — NOT APPROVED TO SUBMIT",
        official_score_status="No portal upload or organizer score is recorded.",
        submission_slots_used=0, reasoning=h58_reasoning, a_only_reasoning=a_only_reasoning,
        local_research_gate_passed=local_slot_gate, artifact_gates=artifact_gates,
        source_provenance="owner-supplied pinned mirror; not organizer-authenticated"))
    (submissions_dir / "LATEST.txt").write_text(filename + "\n")
    log(f"wrote evidence/h58_result.json and evidence/h58_holdout.json; "
        f"local research gate={local_slot_gate}; weekly slot approval={upload_approved}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="work/h58_pinned")
    parser.add_argument("--work-dir", default="work/h58")
    parser.add_argument("--layer-chunk", type=int, default=600)
    parser.add_argument("--prediction-chunk", type=int, default=500)
    args = parser.parse_args()
    if args.layer_chunk <= 0 or args.prediction_chunk <= 0:
        parser.error("chunk sizes must be positive")
    with threadpool_limits(limits=1):
        return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
