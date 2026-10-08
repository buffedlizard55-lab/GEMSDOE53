from __future__ import annotations

import csv
import importlib.util
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, file: str):
    path = ROOT / "scripts" / file
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load_script("h58_runner_for_tests", "run_h58.py")


def test_crop_scoring_matches_full_grid_dti():
    from gems52 import metric

    shape = (100, 120)
    region = np.zeros(shape, bool)
    region[20:75, 30:90] = True
    truth = np.zeros(shape, bool)
    truth[40, 45:55] = True
    truth[70, 80] = True
    prediction = np.zeros(shape, np.float32)
    prediction[40, 45] = 1.0
    prediction[70, 83] = 1.0
    full = metric.dti(prediction, truth & region)
    cropped = RUNNER._dti_crop(prediction, truth & region, region)
    assert cropped["dti"] == full["dti"]
    assert cropped["tpw"] == full["tpw"]
    assert cropped["fpw"] == full["fpw"]
    assert cropped["fnw"] == full["fnw"]


def test_candidate_reasoning_csv_has_one_falsifiable_row_per_pixel(tmp_path):
    from gems52 import h58

    valid = np.ones((60, 60), bool)
    sites = pd.DataFrame([dict(row=20, col=20, temp_c=22.0,
                               geothermquartz_c=115.0, geothermcat_c=120.0)])
    geo, _, _ = h58.geothermometer_field(valid, sites)
    nodes = np.zeros(valid.shape, bool)
    nodes[20, 20] = True
    nodes[30, 30] = True
    pa = np.full(valid.shape, 0.8, np.float32)
    pb = np.full(valid.shape, 0.2, np.float32)
    depth = np.full(valid.shape, 500.0, np.float32)
    slope = np.full(valid.shape, 0.01, np.float32)
    path = tmp_path / "reasons.csv"

    receipt = RUNNER._write_reasoning_csv(path, nodes, sites=sites, geo_field=geo,
                                          pa=pa, pb=pb, depth=depth, slope=slope,
                                          kind="A-only diagnostic")
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert receipt["rows"] == 2
    assert receipt["one_reason_per_emitted_candidate"] is True
    assert len(rows) == int(nodes.sum())
    assert all("falsifier" in row["alternative_and_falsifier"].lower() for row in rows)
    assert all("not an independently mapped" in row["verification_status"].lower() for row in rows)
    assert "dist_known_fault_px" not in rows[0]


def test_h58_feed_stages_exact_registration_and_round_receipt(tmp_path):
    feed = _load_script("refresh_feed_h58_receipt_test", "refresh_feed.py")
    feed.ROOT = tmp_path
    feed.EV = tmp_path / "evidence"
    feed.DOCS = tmp_path / "docs"
    feed.DATA = feed.DOCS / "data"
    feed.DL = feed.DOCS / "downloads"
    (tmp_path / "registry").mkdir()
    (tmp_path / "submission").mkdir()
    feed.EV.mkdir()
    registry_bytes = b'{\n  "round": "H58",\n  "frozen": true\n}\n'
    (tmp_path / "registry/h58_preregistration.json").write_bytes(registry_bytes)
    for name in ("h58_result.json", "h58_holdout.json", "h58_preflight_integrity.json"):
        (feed.EV / name).write_text("{}\n")
    marker_name = "gems52-h58-coldgeo-consensus-37654px-acde123456-research.tif"
    (tmp_path / "submission/LATEST.txt").write_text(marker_name + "\n")
    receipt_name = "submission_" + Path(marker_name).stem + ".json"
    (feed.EV / receipt_name).write_text("{}\n")

    feed.copy_evidence()

    assert (feed.DATA / "h58_preregistration.json").read_bytes() == registry_bytes
    for name in ("h58_result.json", "h58_holdout.json", "h58_preflight_integrity.json", receipt_name):
        assert (feed.DATA / name).is_file()


def test_h58_zip_publisher_archives_only_the_tiff(tmp_path):
    feed = _load_script("refresh_feed_h58_test", "refresh_feed.py")
    feed.ROOT = tmp_path
    feed.DL = tmp_path / "docs" / "downloads"
    feed.EV = tmp_path / "evidence"
    (tmp_path / "submission").mkdir()
    feed.DL.mkdir(parents=True)
    name = "gems52-h58-coldgeo-consensus-1px-acde123456-research.tif"
    payload = b"new H58 TIFF bytes for ZIP unit test"
    (tmp_path / "submission" / name).write_bytes(payload)

    result = Path(feed.make_zip(name))
    with zipfile.ZipFile(result) as archive:
        assert archive.namelist() == [name]
        assert archive.read(name) == payload
        assert archive.testzip() is None
