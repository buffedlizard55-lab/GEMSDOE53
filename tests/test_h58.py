from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import ndimage

from gems52 import h58


def test_qualify_sites_uses_only_registered_columns_and_frozen_thresholds(tmp_path):
    table = pd.DataFrame([
        # Exact boundary values all qualify; this is the representative retained duplicate.
        dict(row=10, col=10, temp_c=30.0, geothermquartz_c=100.0,
             geothermcat_c=120.0, dist_known_fault_px=0),
        # Same cell also qualifies, but stable first-row deduplication keeps the row above.
        dict(row=10, col=10, temp_c=25.0, geothermquartz_c=110.0,
             geothermcat_c=120.0, dist_known_fault_px=999999),
        dict(row=20, col=21, temp_c=29.0, geothermquartz_c=110.0,
             geothermcat_c=100.0, dist_known_fault_px=1),
        dict(row=11, col=11, temp_c=30.01, geothermquartz_c=120.0,
             geothermcat_c=120.0, dist_known_fault_px=1),
        dict(row=12, col=12, temp_c=20.0, geothermquartz_c=99.99,
             geothermcat_c=120.0, dist_known_fault_px=1),
        dict(row=13, col=13, temp_c=20.0, geothermquartz_c=120.0,
             geothermcat_c=99.99, dist_known_fault_px=1),
        dict(row=14, col=14, temp_c=20.0, geothermquartz_c=100.0,
             geothermcat_c=120.01, dist_known_fault_px=1),
        dict(row=50, col=50, temp_c=20.0, geothermquartz_c=110.0,
             geothermcat_c=110.0, dist_known_fault_px=1),
        dict(row=15.5, col=15, temp_c=20.0, geothermquartz_c=110.0,
             geothermcat_c=110.0, dist_known_fault_px=1),
    ])
    path = tmp_path / "sites.csv"
    table.to_csv(path, index=False)
    valid = np.ones((40, 40), dtype=bool)
    valid[20, 21] = False

    sites, audit = h58.qualify_sites(path, valid)

    assert list(sites.columns) == list(h58.SITE_COLUMNS)
    assert set(sites[["row", "col"]].itertuples(index=False, name=None)) == {(10, 10)}
    assert sites.iloc[0]["temp_c"] == pytest.approx(30.0)
    assert audit["threshold_qualifying_rows"] == 4
    assert audit["qualifying_in_grid_and_valid_rows"] == 2
    assert audit["unique_qualified_sites"] == 1
    assert audit["duplicate_rows_removed"] == 1
    assert audit["forbidden_column_read"] is False


def test_geothermometer_field_has_frozen_linear_five_kilometre_support():
    valid = np.ones((40, 80), dtype=bool)
    valid[0, 0] = False
    sites = pd.DataFrame([dict(row=20, col=20, temp_c=20.0,
                               geothermquartz_c=110.0, geothermcat_c=115.0)])
    field, site_mask, distance = h58.geothermometer_field(valid, sites)

    assert field[20, 20] == pytest.approx(1.0)
    assert field[20, 45] == pytest.approx(0.5)
    assert field[20, 70] == pytest.approx(0.0)
    assert field[0, 0] == 0.0
    assert np.isinf(distance[0, 0])
    assert site_mask.sum() == 1


def test_component_assignment_and_block_folds_preserve_whole_segments():
    shape = (80, 80)
    valid = np.ones(shape, dtype=bool)
    catalogue = np.zeros(shape, dtype=bool)
    catalogue[10:13, 10:13] = True
    catalogue[10:13, 65:68] = True
    catalogue[65:68, 10:13] = True
    catalogue[65:68, 65:68] = True
    # This 8-connected component straddles the center; majority/tie policy assigns the whole object.
    catalogue[39:42, 39:42] = True

    components, assigned, quad = h58.component_assignment(catalogue, valid)
    folds = h58.make_folds(catalogue, valid, buffer_px=4, prevalence=0.002,
                           seed=20261007, mode="block")

    for component_id in range(1, int(components.max()) + 1):
        owner_values = np.unique(assigned[components == component_id])
        assert owner_values.size == 1
        owner = int(owner_values[0])
        fold = folds[owner]
        assert np.all(fold["held_all"][components == component_id])
        assert not np.any(fold["fit"] & (components == component_id))
        assert np.all(fold["truth"][components == component_id]) or \
            not np.any(fold["truth"][components == component_id])

    crossing_id = int(components[40, 40])
    assert int(assigned[40, 40]) == 3  # majority is SE, but the object crosses every quadrant
    crossing = components == crossing_id
    north_west = folds[0]
    assert np.all(north_west["held_all"][crossing])
    assert not np.any(north_west["visible"][crossing])
    assert not np.any(north_west["fit"] & crossing)
    assert not np.any(north_west["truth"] & crossing)  # quarantined, not misattributed as truth

    for fold in folds:
        assert not np.any(fold["fit"] & fold["region"])
        assert fold["receipt"]["shared_train_truth_components"] == 0
        assert fold["receipt"]["min_train_distance_to_region_px"] > 4
    assert set(np.unique(quad)) == {0, 1, 2, 3}


def test_hide_and_block_prevalence_targets_are_scored_region_based():
    shape = (120, 120)
    valid = np.ones(shape, dtype=bool)
    catalogue = np.zeros(shape, dtype=bool)
    for r, c in ((10, 10), (10, 90), (90, 10), (90, 90), (55, 55), (57, 57)):
        catalogue[r:r + 3, c:c + 3] = True

    hide = h58.make_folds(catalogue, valid, buffer_px=5, prevalence=0.002,
                          seed=23, mode="hide")
    block = h58.make_folds(catalogue, valid, buffer_px=5, prevalence=0.002,
                           seed=23, mode="block")
    for fold in hide + block:
        receipt = fold["receipt"]
        assert receipt["target_truth_pixels"] == pytest.approx(0.002 * receipt["region_pixels"])
        assert receipt["actual_truth_prevalence"] == pytest.approx(
            receipt["truth_pixels"] / receipt["region_pixels"])
        assert np.all(fold["truth"] <= fold["held_all"])


def test_preregistration_pins_manifest_bytes_before_input_verification(tmp_path):
    import shutil

    repo = Path(__file__).resolve().parents[1]
    target = tmp_path / "repo"
    (target / "registry").mkdir(parents=True)
    (target / "knowledge").mkdir()
    (target / "evidence").mkdir()
    for rel in ("registry/h58_preregistration.json", "registry/data_manifest.json",
                "knowledge/19_hypotheses_H58_preregistered.md",
                "evidence/h58_preflight_integrity.json"):
        shutil.copy2(repo / rel, target / rel)
    registry = target / "registry/h58_preregistration.json"

    checked = h58.verify_preregistration(registry)
    assert len(checked["checks"]) == 3
    assert all(row["matches"] for row in checked["checks"])
    (target / "registry/data_manifest.json").write_text("{}\n")
    with pytest.raises(RuntimeError, match="preregistration hash mismatch"):
        h58.verify_preregistration(registry)


def test_manifest_verification_fails_closed_on_changed_bytes(tmp_path):
    data_root = tmp_path / "pinned"
    data_root.mkdir()
    source = data_root / "tiny.bin"
    source.write_bytes(b"pinned")
    manifest = tmp_path / "manifest.json"
    record = dict(files=[dict(id="tiny", dest="tiny.bin", bytes=6,
                              sha256=h58.sha256_file(source), provenance="test-only")])
    manifest.write_text(json.dumps(record))

    ok = h58.verify_manifest(manifest, data_root)
    assert ok[0]["matches_pin"]
    source.write_bytes(b"altered")
    with pytest.raises(RuntimeError, match="verification failed"):
        h58.verify_manifest(manifest, data_root)


def test_training_samples_are_fold_local_and_do_not_inspect_held_labels():
    shape = (60, 60)
    valid = np.ones(shape, dtype=bool)
    fit = np.ones(shape, dtype=bool)
    fit[25:36, 25:36] = False
    catalogue_a = np.zeros(shape, dtype=bool)
    catalogue_a[10, 10] = True
    catalogue_b = catalogue_a.copy()
    catalogue_b[30, 30] = True  # held positive: its location must not alter the train sample

    pos_a, neg_a = h58.training_pixels(catalogue_a, valid, fit, seed=5, n_neg=500)
    pos_b, neg_b = h58.training_pixels(catalogue_b, valid, fit, seed=5, n_neg=500)

    assert np.array_equal(pos_a, pos_b)
    assert np.array_equal(neg_a, neg_b)
    assert np.all(fit.ravel()[pos_a]) and np.all(fit.ravel()[neg_a])
    visible_positive = catalogue_a & fit
    clear = ndimage.binary_dilation(visible_positive, iterations=5)
    assert not clear.ravel()[neg_a].any()
    assert pos_a.size == 1


def test_pseudo_auc_mask_keeps_evaluation_region_and_excludes_nearby_proxy_negatives():
    shape = (30, 30)
    valid = np.ones(shape, bool)
    region = np.zeros(shape, bool)
    region[5:25, 5:25] = True
    edge_clear = valid.copy()
    edge_clear[:2] = False
    catalogue = np.zeros(shape, bool)
    catalogue[10, 10] = True  # component owned by this fold
    catalogue[12, 12] = True  # another held/quarantined component, not scored positive here
    primary_held = np.zeros(shape, bool)
    primary_held[10, 10] = True
    clearance = ndimage.binary_dilation(catalogue, iterations=5)

    mask, positive = h58.pseudo_auc_masks(primary_held, region, valid, edge_clear, clearance)

    assert positive[10, 10] and mask[10, 10]
    assert not positive[12, 12] and not mask[12, 12]
    assert mask[20, 20] and not positive[20, 20]  # catalogue-zero proxy negative
    assert not mask[1, 20] and not mask[28, 28]  # outside edge-cleared scored region
    assert set(np.unique(positive[mask])) == {False, True}


def test_a_only_mask_uses_confident_a_and_abstaining_b_only():
    pa = np.array([[0.60, 0.60, 0.59, 0.9]], dtype=np.float32)
    pb = np.array([[0.40, 0.41, 0.2, 0.39]], dtype=np.float32)
    allowed = np.array([[True, True, True, False]])
    mask = h58.a_only_mask(pa, pb, allowed)
    assert np.array_equal(mask, np.array([[True, False, False, False]]))
