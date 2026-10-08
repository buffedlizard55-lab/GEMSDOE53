"""Gates: the format checker must fail every illegality it names, and the uniqueness audit must tell
apart "new", "identical", "subset" and "the union"."""
from __future__ import annotations

import numpy as np
import rasterio
from rasterio.transform import from_origin

from gems52 import gates
from gems52.grid import SHAPE


def write_tif(dirpath, name, arr, *, crs="EPSG:32611", nodata=None):
    """A tiny self-consistent raster: 1 m cells, origin (0, nrows), so bounds are unambiguous."""
    p = dirpath / name
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype="float32",
                crs=crs, transform=from_origin(0.0, float(arr.shape[0]), 1.0, 1.0))
    if nodata is not None:
        prof["nodata"] = nodata
    with rasterio.open(p, "w", **prof) as d:
        d.write(arr, 1)
    return p


def test_value_range_is_checked(tmp_path):
    ref = np.ones((6, 6), dtype=np.float32)
    sample = write_tif(tmp_path, "sample.tif", ref)
    bad = np.full((6, 6), 1.5, dtype=np.float32)
    r = gates.format_report(write_tif(tmp_path, "bad.tif", bad), sample)
    assert not r["ok"]
    assert any("[0,1]" in p for p in r["problems"])


def test_nan_pixels_are_flagged_as_the_portal_failure_they_cause(tmp_path):
    """NaN is the mechanism behind 'Predicted values must be in range [0, 1]', so it must be caught."""
    ref = np.ones((6, 6), dtype=np.float32)
    sample = write_tif(tmp_path, "sample.tif", ref)
    r = gates.format_report(write_tif(tmp_path, "n.tif", np.full((6, 6), np.nan, np.float32)), sample)
    assert r["nan_pixels"] == 36
    assert any("NaN" in p for p in r["problems"])


def test_all_nan_file_fails_even_though_minmax_cannot_see_it(tmp_path):
    sample = write_tif(tmp_path, "sample.tif", np.ones((6, 6), np.float32))
    r = gates.format_report(write_tif(tmp_path, "n.tif", np.full((6, 6), np.nan, np.float32)), sample)
    assert not r["ok"]


def test_shape_must_match_the_reference_when_not_on_the_official_grid(tmp_path):
    sample = write_tif(tmp_path, "sample.tif", np.ones((6, 6), np.float32))
    other = write_tif(tmp_path, "other.tif", np.ones((4, 4), np.float32))
    r = gates.format_report(other, sample)
    assert any("shape" in p for p in r["problems"])


def test_mass_outside_the_footprint_is_caught(tmp_path):
    sample = write_tif(tmp_path, "sample.tif", np.ones((6, 6), np.float32))
    a = np.zeros((6, 6), np.float32)
    a[0, 0] = 1.0
    footprint = np.zeros((6, 6), bool)
    footprint[3:, 3:] = True                       # the emitted pixel is outside it
    r = gates.format_report(write_tif(tmp_path, "m.tif", a), sample, footprint=footprint)
    assert r["mass_outside_footprint"] == 1
    assert any("outside the valid footprint" in p for p in r["problems"])


def test_a_clean_file_on_the_fixture_grid_passes(tmp_path):
    ref = np.ones((6, 6), np.float32)
    ref[5, :] = 0.0                                # zero, not NaN: the encodable "no data"
    sample = write_tif(tmp_path, "sample.tif", ref)
    a = np.zeros((6, 6), np.float32)
    a[1, 1] = 1.0
    fp = np.ones((6, 6), bool)
    fp[5, :] = False
    r = gates.format_report(write_tif(tmp_path, "ok.tif", a), sample, footprint=fp)
    assert r["ok"], r["problems"]


def test_uniqueness_distinguishes_identical_subset_and_novel(tmp_path):
    e = np.zeros((6, 6), np.float32)
    e[1, 1:3] = 1.0
    ident = write_tif(tmp_path, "a.tif", e.copy())
    sub = np.zeros((6, 6), np.float32)
    sub[1, 1] = 1.0
    subf = write_tif(tmp_path, "b.tif", sub)
    novel = np.zeros((6, 6), np.float32)
    novel[4, 4] = 1.0
    novf = write_tif(tmp_path, "c.tif", novel)

    same = gates.uniqueness_report(e, [ident])
    assert any(r["identical"] for r in same["per_prior"])
    assert same["ok"] is False                      # identical to a prior is never shippable

    subset = gates.uniqueness_report(sub, [ident])   # strictly inside a prior: "the union", miniature
    assert any(r["subset_of_prior"] for r in subset["per_prior"])
    assert subset["ok"] is False

    fresh = gates.uniqueness_report(novel, [ident, subf])
    assert fresh["novel_vs_all_priors"] == 1        # the one pixel no prior touched
    assert fresh["union_px"] == 2                   # priors cover (1,1) and (1,2)
    assert fresh["prior_px_dropped"] == 2
    assert fresh["relation_to_union"] == "strictly-novel-and-selective"


def test_find_priors_skips_reference_rasters(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "labels.tif").write_bytes(b"x" * 5000)
    (tmp_path / "out").mkdir()
    real = write_tif(tmp_path / "out", "real.tif", np.ones((6, 6), np.float32))
    found = gates.find_priors([tmp_path], min_bytes=100)
    assert real in found
    assert not any("labels.tif" in str(p) for p in found)


def test_accept_bar_matches_the_derived_rule():
    from gems52.emit import accept_bar
    for dti in (0.05, 0.2778, 0.3774):
        assert abs(accept_bar(dti) - 0.2 * dti / (1 - 0.2 * dti)) < 1e-12


def test_official_grid_constants_are_pinned():
    assert SHAPE == (3730, 3292)


def test_find_priors_never_returns_a_copy_of_the_candidate(tmp_path):
    """refresh_feed.py stages built rasters into docs/downloads/, which find_priors also scans.
    Without a basename check the candidate is compared against itself and the gate reports
    identical-to-a-prior / novel = 0 -- the one false verdict that would block a real submission."""
    sub = tmp_path / "submission"
    dl = tmp_path / "docs" / "downloads"
    sub.mkdir(parents=True)
    dl.mkdir(parents=True)
    arr = (np.random.default_rng(0).random((40, 40)) > 0.9).astype(np.float32)
    out = write_tif(sub, "candidate-x.tif", arr)
    write_tif(dl, "candidate-x.tif", arr)                      # the staged copy
    write_tif(dl, "some-earlier-file.tif", arr * 0.0)          # a genuine prior
    found = gates.find_priors([sub, dl], exclude=out, min_bytes=1)
    names = [q.name for q in found]
    assert "candidate-x.tif" not in names
    assert "some-earlier-file.tif" in names
    uni = gates.uniqueness_report(arr > 0, found)
    assert not any(r.get("identical") for r in uni["per_prior"])


def test_find_priors_skips_competition_inputs(tmp_path):
    """A feature stack or an external layer is an input, not somebody's answer.

    Regression: sweeping a root that contains `training_features.tif` read band 1 as a prior
    submission and produced a "prior union" of 5,363,764 px against a 5,167,373 px footprint, which
    destroyed both the novelty count and the not-the-union test.
    """
    (tmp_path / "data" / "external").mkdir(parents=True)
    (tmp_path / "out").mkdir()
    real = write_tif(tmp_path / "out", "real.tif", np.ones((6, 6), np.float32))
    feats = write_tif(tmp_path / "data", "training_features.tif", np.ones((6, 6), np.float32))
    ext = write_tif(tmp_path / "data" / "external", "layer.tif", np.ones((6, 6), np.float32))
    sample = write_tif(tmp_path / "data", "sample_submission.tif", np.ones((6, 6), np.float32))
    found = gates.find_priors([tmp_path], min_bytes=100)
    assert real in found
    for bad in (feats, ext, sample):
        assert bad not in found, bad
