"""Format-validator tests on synthetic rasters: the checks must accept a good file and reject each defect."""
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems53.core import validate_submission, write_submission  # noqa: E402

CRS = rasterio.crs.CRS.from_epsg(32611)
TR = from_origin(243350.0, 4508550.0, 100.0, 100.0)


def _fp():
    fp = np.zeros((20, 30), bool)
    fp[5:15, 5:25] = True
    return fp


def _write(tmp, arr, nan_outside=True):
    p = str(tmp / "s.tif")
    write_submission(p, arr, TR, CRS, outside_nan=nan_outside)
    return p


def test_good_file_passes(tmp_path):
    fp = _fp()
    a = np.full((20, 30), np.nan, np.float32)
    a[fp] = np.random.default_rng(0).random(fp.sum()).astype(np.float32)
    r = validate_submission(_write(tmp_path, a), fp, TR, CRS, 20, 30)
    assert r["all_checks_passed"], r["checks"]


def test_nan_inside_footprint_is_rejected(tmp_path):
    fp = _fp()
    a = np.full((20, 30), np.nan, np.float32)
    a[fp] = 0.5
    a[7, 7] = np.nan
    r = validate_submission(_write(tmp_path, a), fp, TR, CRS, 20, 30)
    assert not r["checks"]["no_nan_or_inf_inside_footprint"]
    assert not r["all_checks_passed"]


def test_value_above_one_is_rejected(tmp_path):
    fp = _fp()
    a = np.zeros((20, 30), np.float32)
    a[fp] = 0.2
    a[6, 6] = 1.5
    r = validate_submission(_write(tmp_path, a), fp, TR, CRS, 20, 30)
    assert not r["checks"]["inside_footprint_in_0_1"]


def test_sentinel_value_is_rejected(tmp_path):
    fp = _fp()
    a = np.zeros((20, 30), np.float32)
    a[fp] = 0.2
    a[6, 6] = -3.4028234663852886e38  # the feature-stack nodata sentinel
    r = validate_submission(_write(tmp_path, a), fp, TR, CRS, 20, 30)
    assert not r["checks"]["inside_footprint_in_0_1"]


def test_wrong_crs_is_rejected(tmp_path):
    fp = _fp()
    a = np.zeros((20, 30), np.float32)
    p = str(tmp_path / "w.tif")
    with rasterio.open(p, "w", driver="GTiff", height=20, width=30, count=1, dtype="float32",
                       crs=rasterio.crs.CRS.from_epsg(4326), transform=TR) as d:
        d.write(a, 1)
    r = validate_submission(p, fp, TR, CRS, 20, 30)
    assert not r["checks"]["crs_is_EPSG_32611"]


def test_nan_variant_carries_nodata_nan(tmp_path):
    """Regression: the shared template validator rejected nodata=None (its sample tag is 'nan')."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from gems53.core import write_submission

    out = tmp_path / "t.tif"
    em = np.zeros((4, 5), dtype=np.float32)
    em[1, 2] = 0.5
    em[0, 0] = np.nan
    write_submission(str(out), em, from_origin(0, 0, 100, 100), "EPSG:32611", outside_nan=True)
    with rasterio.open(out) as src:
        assert src.nodata is not None and np.isnan(src.nodata)


def test_zero_outside_footprint_is_rejected(tmp_path):
    """Official rule: outside the bounds is null or NaN. Zeros outside must fail this validator."""
    fp = _fp()
    a = np.zeros((20, 30), np.float32)
    a[fp] = 0.2
    r = validate_submission(_write(tmp_path, a), fp, TR, CRS, 20, 30)
    assert not r["checks"]["outside_footprint_nan"]
    assert not r["all_checks_passed"]


def test_lzw_round_trip_keeps_values(tmp_path):
    """Compression is lossless: LZW output reads back bit-identical to the array that was written."""
    fp = _fp()
    a = np.full((20, 30), np.nan, np.float32)
    a[fp] = np.random.default_rng(1).random(fp.sum()).astype(np.float32)
    p = _write(tmp_path, a)
    with rasterio.open(p) as src:
        back = src.read(1)
        assert src.compression is not None and src.compression.name.lower() == "lzw"
    assert np.array_equal(np.isnan(back), np.isnan(a))
    assert np.array_equal(back[fp], a[fp])
