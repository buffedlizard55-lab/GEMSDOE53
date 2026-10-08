"""H58 preregistration helpers: pinned inputs, cold-geothermometer field and whole-segment folds.

This module deliberately contains no organizer score logic. The CSV reader selects only the five
registered columns; input pins are verified before the runner builds any feature stack.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy import ndimage

SITE_COLUMNS = ("row", "col", "temp_c", "geothermquartz_c", "geothermcat_c")
FIELD_RADIUS_M = 5_000.0
PIXEL_M = 100.0


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(manifest_path: str | Path, data_root: str | Path) -> list[dict]:
    """Verify every manifest member against its owner-mirror SHA and byte count; never repairs it."""
    manifest_path, data_root = Path(manifest_path), Path(data_root)
    manifest = json.loads(manifest_path.read_text())
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("data manifest has no files list")
    receipts = []
    failures = []
    for entry in files:
        rel = Path(entry["dest"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"unsafe manifest destination: {rel}")
        path = data_root / rel
        if not path.is_file():
            receipt = dict(id=entry.get("id"), dest=str(rel), exists=False,
                           matches_pin=False, error="missing pinned input")
            receipts.append(receipt)
            failures.append(receipt)
            continue
        actual_bytes = path.stat().st_size
        actual_hash = sha256_file(path)
        expected_bytes = int(entry["bytes"])
        expected_hash = str(entry["sha256"]).lower()
        matches = actual_bytes == expected_bytes and actual_hash == expected_hash
        receipt = dict(id=entry.get("id"), dest=str(rel), bytes=actual_bytes,
                       sha256=actual_hash, expected_bytes=expected_bytes,
                       expected_sha256=expected_hash, matches_pin=bool(matches),
                       provenance=entry.get("provenance"))
        receipts.append(receipt)
        if not matches:
            failures.append(receipt)
    if failures:
        ids = ", ".join(str(row.get("id")) for row in failures)
        raise RuntimeError(f"pinned input verification failed for: {ids}")
    return receipts


def verify_preregistration(registry_path: str | Path) -> dict:
    """Verify the registry's frozen hypothesis/preflight hashes before starting H58."""
    registry_path = Path(registry_path)
    registry = json.loads(registry_path.read_text())
    base = registry_path.parent.parent
    checks = []
    for hash_key, path_key in (("hypothesis_document_sha256", "hypothesis_document"),
                               ("preflight_sha256", "preflight_evidence")):
        path = base / registry[path_key]
        actual = sha256_file(path)
        expected = registry[hash_key]
        checks.append(dict(file=registry[path_key], expected_sha256=expected,
                           actual_sha256=actual, matches=actual == expected))
    manifest_path = base / registry["data_integrity"]["manifest"]
    manifest_actual = sha256_file(manifest_path)
    manifest_expected = registry["data_integrity"]["manifest_sha256"]
    checks.append(dict(file=registry["data_integrity"]["manifest"],
                       expected_sha256=manifest_expected, actual_sha256=manifest_actual,
                       matches=manifest_actual == manifest_expected))
    if not all(row["matches"] for row in checks):
        raise RuntimeError("H58 preregistration hash mismatch; refusing to execute")
    if registry.get("status") != "amended_frozen_preregistration_before_scored_execution":
        raise RuntimeError("H58 registry is not in the expected amended frozen preregistration state")
    amendments = [registry.get("protocol_amendment", {}),
                  registry.get("additional_pre_score_clarification", {})]
    if any(amendment.get("result_informed") is not False for amendment in amendments):
        raise RuntimeError("H58 protocol amendment lacks a no-results attestation")
    return dict(registry=registry, checks=checks)


def qualify_sites(csv_path: str | Path, valid: np.ndarray) -> tuple[object, dict]:
    """Read only registered columns and select one cold, agreeing high-estimate row per grid cell.

    Rows with missing values, non-integral/out-of-grid coordinates, non-finite values or cells
    outside the all-band-valid footprint fail closed. `dist_known_fault_px` is never loaded.
    """
    import pandas as pd

    valid = np.asarray(valid, bool)
    frame = pd.read_csv(csv_path, usecols=list(SITE_COLUMNS))
    if set(frame.columns) != set(SITE_COLUMNS):
        raise ValueError(f"site table lacks registered columns: {SITE_COLUMNS}")
    frame = frame.loc[:, list(SITE_COLUMNS)].copy()
    raw_rows = len(frame)
    numeric = {}
    for name in SITE_COLUMNS:
        numeric[name] = pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=np.float64)
    coords_ok = (np.isfinite(numeric["row"]) & np.isfinite(numeric["col"])
                 & (numeric["row"] == np.floor(numeric["row"]))
                 & (numeric["col"] == np.floor(numeric["col"])))
    finite_values = np.logical_and.reduce([np.isfinite(numeric[name]) for name in SITE_COLUMNS])
    quartz = numeric["geothermquartz_c"]
    cation = numeric["geothermcat_c"]
    temperature = numeric["temp_c"]
    numeric_qualifies = (coords_ok & finite_values & (temperature <= 30.0)
                         & (quartz >= 100.0) & (cation >= 100.0)
                         & (np.abs(quartz - cation) <= 20.0))
    idx = np.flatnonzero(numeric_qualifies)
    qualified = frame.iloc[idx].copy()
    qualified["row"] = numeric["row"][idx].astype(np.int64)
    qualified["col"] = numeric["col"][idx].astype(np.int64)
    h, w = valid.shape
    in_bounds = ((qualified["row"].to_numpy() >= 0) & (qualified["row"].to_numpy() < h)
                 & (qualified["col"].to_numpy() >= 0) & (qualified["col"].to_numpy() < w))
    qualified = qualified.loc[in_bounds].copy()
    on_valid = np.zeros(len(qualified), dtype=bool)
    if len(qualified):
        rr = qualified["row"].to_numpy(dtype=np.int64)
        cc = qualified["col"].to_numpy(dtype=np.int64)
        on_valid = valid[rr, cc]
        qualified = qualified.loc[on_valid].copy()
    before_dedup = len(qualified)
    qualified = qualified.drop_duplicates(subset=["row", "col"], keep="first").reset_index(drop=True)
    audit = dict(
        raw_rows=int(raw_rows),
        allowed_columns=list(SITE_COLUMNS),
        forbidden_column_read=False,
        threshold_qualifying_rows=int(len(idx)),
        qualifying_in_grid_and_valid_rows=int(before_dedup),
        unique_qualified_sites=int(len(qualified)),
        duplicate_rows_removed=int(before_dedup - len(qualified)),
        discarded_nonfinite_or_threshold_rows=int(raw_rows - len(idx)),
        discarded_out_of_grid_or_invalid_rows=int(len(idx) - before_dedup),
        rule=dict(temp_c_max=30.0, geothermquartz_c_min=100.0,
                  geothermcat_c_min=100.0, max_abs_difference_c=20.0),
        deduplication="first qualifying CSV row per integer row/col; selection is independent of labels and model scores",
    )
    return qualified, audit


def geothermometer_field(valid: np.ndarray, sites) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return the frozen linear 5 km nearest-site field, site mask, and nearest distance in metres."""
    valid = np.asarray(valid, bool)
    site_mask = np.zeros(valid.shape, bool)
    if len(sites):
        rr = np.asarray(sites["row"], dtype=np.int64)
        cc = np.asarray(sites["col"], dtype=np.int64)
        site_mask[rr, cc] = True
    if not site_mask.any():
        raise ValueError("no qualifying H58-A sites on the valid footprint")
    distance = ndimage.distance_transform_edt(~site_mask, sampling=(PIXEL_M, PIXEL_M)).astype(np.float32)
    field = np.maximum(1.0 - distance / FIELD_RADIUS_M, 0.0).astype(np.float32)
    field[~valid] = 0.0
    distance[~valid] = np.inf
    return field, site_mask, distance


def training_pixels(catalogue: np.ndarray, valid: np.ndarray, fit: np.ndarray, *,
                    seed: int, n_neg: int = 60_000, clear_px: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Sample only inside ``fit`` and derive negative clearance from training-visible labels.

    Unlike the legacy H57 helper, neither negative samples nor their exclusion mask may inspect the
    held region. Fold construction explicitly excludes held/quarantined components from ``fit``;
    this sampler does not consult any hidden-label geometry.
    """
    catalogue, valid, fit = np.asarray(catalogue, bool), np.asarray(valid, bool), np.asarray(fit, bool)
    if catalogue.shape != valid.shape or valid.shape != fit.shape:
        raise ValueError("catalogue, valid and fit masks must share one grid")
    visible_positive = catalogue & fit
    pos = np.flatnonzero(visible_positive.ravel())
    negative_clearance = ndimage.binary_dilation(visible_positive, iterations=int(clear_px))
    neg_pool = valid & fit & ~negative_clearance
    neg = np.flatnonzero(neg_pool.ravel())
    rng = np.random.default_rng(seed)
    if pos.size > n_neg:
        pos = rng.choice(pos, size=n_neg, replace=False)
    if neg.size > n_neg:
        neg = rng.choice(neg, size=n_neg, replace=False)
    return pos, neg


def pseudo_auc_masks(primary_held: np.ndarray, region: np.ndarray, valid: np.ndarray,
                    edge_clear: np.ndarray, catalogue_clearance: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """AUC classes for one held fold: owned held components and remote catalogue-zero proxies.

    The model's training collar is intentionally absent from this evaluation mask; the scored region
    itself must not be removed along with the pixels excluded from fitting.
    """
    primary_held, region, valid, edge_clear, catalogue_clearance = (
        np.asarray(x, bool) for x in (primary_held, region, valid, edge_clear, catalogue_clearance))
    if any(x.shape != primary_held.shape for x in
           (region, valid, edge_clear, catalogue_clearance)):
        raise ValueError("pseudo AUC masks must share one grid")
    positive = primary_held & region & valid & edge_clear
    negative = region & valid & edge_clear & ~catalogue_clearance
    mask = positive | negative
    return mask, positive


def nearest_site_rows(sites, rows: np.ndarray, cols: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Nearest qualifying-site distance (metres) and dataframe row indices for candidate pixels."""
    from scipy.spatial import cKDTree

    site_rc = np.column_stack([np.asarray(sites["row"], float), np.asarray(sites["col"], float)])
    if not len(site_rc):
        raise ValueError("cannot query nearest site from an empty site table")
    query_rc = np.column_stack([np.asarray(rows, float), np.asarray(cols, float)])
    distances_px, nearest = cKDTree(site_rc).query(query_rc, k=1)
    return distances_px.astype(np.float64) * PIXEL_M, nearest.astype(np.int64)


def quadrants(shape: tuple[int, int]) -> np.ndarray:
    """Four contiguous NW/NE/SW/SE quadrant IDs, with stable row-major tie handling."""
    h, w = shape
    yy, xx = np.indices(shape, sparse=True)
    return ((yy >= h // 2).astype(np.int8) * 2 + (xx >= w // 2).astype(np.int8)).astype(np.int8)


def component_assignment(catalogue: np.ndarray, valid: np.ndarray):
    """Assign every original 8-connected component to its majority valid-data quadrant."""
    catalogue = np.asarray(catalogue, bool) & np.asarray(valid, bool)
    quad = quadrants(catalogue.shape)
    components, n_components = ndimage.label(catalogue, structure=np.ones((3, 3), dtype=bool))
    votes = np.zeros((n_components + 1, 4), dtype=np.int64)
    yy, xx = np.nonzero(catalogue)
    if yy.size:
        np.add.at(votes, (components[yy, xx], quad[yy, xx]), 1)
    owners = votes.argmax(axis=1).astype(np.int8)
    assigned = owners[components]
    assigned[components == 0] = -1
    return components, assigned, quad


def _thin_whole_components(held: np.ndarray, target_pixels: float, rng: np.random.Generator) -> np.ndarray:
    """Seeded component sampling that never clips a connected labelled segment."""
    components, n_components = ndimage.label(held, structure=np.ones((3, 3), dtype=bool))
    truth = np.zeros(held.shape, bool)
    if n_components == 0 or target_pixels <= 0:
        return truth
    ids = np.arange(1, n_components + 1)
    sizes = np.bincount(components.ravel(), minlength=n_components + 1)[1:]
    selected, total = [], 0
    for index in rng.permutation(ids.size):
        if total >= target_pixels:
            break
        selected.append(int(ids[index]))
        total += int(sizes[index])
    if selected:
        truth = np.isin(components, np.asarray(selected, dtype=components.dtype))
    return truth


def make_folds(catalogue: np.ndarray, valid: np.ndarray, *, buffer_px: int = 80,
               prevalence: float = 0.002, seed: int = 20261007,
               mode: str = "block") -> list[dict]:
    """Build four whole-component `hide` or buffered-quadrant `block` folds.

    The prevalence target is 0.2% of each fold's actual scored region. For hide folds that is the
    full eligible footprint; for block folds it is the held quadrant plus the 3-pixel kernel halo.
    Training never contains any pixel from a held connected component. In a block fold, any
    component crossing into the scored quadrant from another majority-assigned fold is also
    quarantined whole from fit/visible labels, but is not added to that fold's truth. A block holdout
    excludes an 80-pixel Euclidean collar around its full evaluation region and the footprint edge.
    """
    if mode not in {"hide", "block"}:
        raise ValueError(f"unknown H58 holdout mode {mode!r}")
    catalogue, valid = np.asarray(catalogue, bool), np.asarray(valid, bool)
    if catalogue.shape != valid.shape:
        raise ValueError("catalogue and feature-valid masks must have identical shapes")
    components, assigned, quad = component_assignment(catalogue, valid)
    edge_distance = ndimage.distance_transform_edt(valid)
    edge_clear = edge_distance > buffer_px
    out = []
    for fold in range(4):
        primary_held = (assigned == fold) & catalogue & valid
        if mode == "hide":
            held_all = primary_held
            region = valid.copy()
            holdout_distance = ndimage.distance_transform_edt(~held_all)
            fit = valid & (holdout_distance > buffer_px) & edge_clear
            crossing_components = 0
        else:
            quadrant_mask = (quad == fold) & valid
            halo = ndimage.binary_dilation(primary_held, structure=_disk(3))
            region = valid & (quadrant_mask | halo)
            # A component assigned to another quadrant can still cross into this held region. Keep
            # its *whole* label out of this fold's fit and visible mask; it is not scored truth here.
            touching_ids = np.unique(components[quadrant_mask & catalogue])
            touching_ids = touching_ids[touching_ids > 0]
            touching = np.isin(components, touching_ids) if touching_ids.size else np.zeros_like(catalogue)
            held_all = primary_held | touching
            primary_ids = np.unique(components[primary_held])
            primary_ids = primary_ids[primary_ids > 0]
            crossing_components = int(max(touching_ids.size - np.intersect1d(touching_ids, primary_ids).size, 0))
            holdout_distance = ndimage.distance_transform_edt(~region)
            fit = valid & (holdout_distance > buffer_px) & edge_clear & ~held_all
        visible = catalogue & valid & ~held_all
        target = float(prevalence) * float(region.sum())
        truth = _thin_whole_components(primary_held, target, np.random.default_rng(seed + fold))
        shared_components = np.intersect1d(
            np.unique(components[fit & catalogue]), np.unique(components[truth]))
        shared_components = shared_components[shared_components > 0]
        if shared_components.size:
            raise AssertionError("an original 8-connected truth component leaked into training")
        if np.any(fit & held_all):
            raise AssertionError("held component pixels leaked into the fit set")
        if mode == "block" and np.any(fit & region):
            raise AssertionError("buffered block fit overlaps the evaluation region")
        boundary = valid & ((holdout_distance <= buffer_px) | ~edge_clear)
        primary_component_ids = np.unique(components[primary_held])
        primary_component_ids = primary_component_ids[primary_component_ids > 0]
        held_component_ids = np.unique(components[held_all])
        held_component_ids = held_component_ids[held_component_ids > 0]
        receipt = dict(
            fold=int(fold), mode=mode,
            primary_held_components=int(primary_component_ids.size),
            crossing_components_quarantined=int(crossing_components),
            total_quarantined_components=int(held_component_ids.size),
            primary_held_pixels=int(primary_held.sum()),
            held_all_pixels=int(held_all.sum()), truth_pixels=int(truth.sum()),
            region_pixels=int(region.sum()), fit_pixels=int(fit.sum()),
            fit_catalogue_pixels=int((catalogue & fit).sum()), visible_pixels=int(visible.sum()),
            buffered_pixels=int(boundary.sum()), target_truth_pixels=target,
            actual_truth_prevalence=float(truth.sum() / max(int(region.sum()), 1)),
            shared_train_truth_components=int(shared_components.size),
            min_train_distance_to_region_px=(float(holdout_distance[fit].min())
                                             if mode == "block" and fit.any() else None),
            seed=int(seed + fold),
        )
        out.append(dict(fold=fold, mode=mode, region=region, fit=fit, truth=truth,
                        visible=visible, held_all=held_all, primary_held=primary_held,
                        components=components,
                        assigned=assigned, quadrant=quad, quadrant_mask=(quad == fold) & valid,
                        boundary=boundary, receipt=receipt))
    return out


def _disk(radius: int) -> np.ndarray:
    yy, xx = np.mgrid[-radius:radius + 1, -radius:radius + 1]
    return (yy * yy + xx * xx) <= radius * radius


def a_only_mask(pa: np.ndarray, pb: np.ndarray, allowed: np.ndarray,
                q_conf: float = 0.60, q_abstain: float = 0.40) -> np.ndarray:
    """Registered buried-view diagnostic: A confident and B abstains, never a fault certification."""
    return (np.asarray(allowed, bool) & (np.asarray(pa) >= q_conf)
            & (np.asarray(pb) <= q_abstain))
