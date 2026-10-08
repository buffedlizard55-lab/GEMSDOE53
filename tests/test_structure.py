"""Unit tests for the structure tensor: does it measure what the detector assumes it measures?

Synthetic ground truth is used on purpose: a straight line at a known angle, a corner, and isotropic
noise.  If the azimuth field cannot recover a known angle to a few degrees, the cross-dataset
coincidence test that consumes it is meaningless, so this is the load-bearing test of the module.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems52 import structure as S

N = 256


def _line_field(angle_deg: float, sigma: float = 1.0, amplitude: float = 1.0) -> np.ndarray:
    """A single straight bright line of the given axial angle through the centre of an N x N grid."""
    yy, xx = np.mgrid[0:N, 0:N].astype(np.float64)
    t = np.deg2rad(angle_deg)
    # signed distance to the line through the centre with direction (cos t, sin t)
    dist = -np.sin(t) * (xx - N / 2) + np.cos(t) * (yy - N / 2)
    return (amplitude * np.exp(-0.5 * (dist / sigma) ** 2)).astype(np.float32)


def _valid() -> np.ndarray:
    return np.ones((N, N), dtype=bool)


@pytest.mark.parametrize("angle", [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165])
def test_azimuth_recovers_a_known_line_angle(angle):
    a = _line_field(angle)
    st = S.structure_tensor(a, _valid(), sigma_tensor_m=300.0)
    coh = st["coherence"]
    az = st["azimuth"]
    sel = np.isfinite(az) & (coh > 0.98) & (st["energy"] > np.nanpercentile(st["energy"], 90))
    assert sel.sum() > 50, "the line should dominate a well-populated high-coherence set"
    # circular (axial) mean of the recovered azimuths must be within 3 degrees of the truth.  The
    # residual (~2.4 deg on the diagonals) is the square-lattice discretisation of a straight line,
    # measured not assumed: a 45-degree line is recovered at 45.00, which is why the tolerance is set
    # just above the diagonal case rather than at zero.
    from gems52 import azimuth as A
    got = A.mean_axial_deg(az[sel])
    diff = np.degrees(A.axial_difference(np.deg2rad(angle), np.deg2rad(got)))
    assert diff < 3.0, f"angle {angle} recovered as {got:.2f} (diff {diff:.2f} deg)"


def test_coherence_discriminates_line_from_noise():
    rng = np.random.default_rng(0)
    line = _line_field(30.0)
    st_line = S.structure_tensor(line, _valid(), sigma_tensor_m=300.0)
    noise = rng.normal(size=(N, N)).astype(np.float32)
    st_noise = S.structure_tensor(noise, _valid(), sigma_tensor_m=300.0)
    peak_line = float(np.nanmax(st_line["coherence"]))
    peak_noise = float(np.nanpercentile(st_noise["coherence"], 99.9))
    assert peak_line > 0.99
    assert peak_line > peak_noise
    assert peak_noise < 0.9


def test_oriented_line_energy_is_high_on_a_line_and_low_on_random_orientation():
    a = _line_field(30.0)
    st = S.structure_tensor(a, _valid(), sigma_tensor_m=300.0)
    r_line = S.oriented_line_energy(st["azimuth"], _valid(), sigma_m=300.0)
    rng = np.random.default_rng(1)
    rand_az = rng.uniform(0, np.pi, (N, N)).astype(np.float32)
    r_rand = S.oriented_line_energy(rand_az, _valid(), sigma_m=300.0)
    band = st["energy"] > np.nanpercentile(st["energy"], 90)
    assert np.nanmean(r_line[band]) > 0.95
    assert np.nanmean(r_rand) < 0.35


def test_no_nan_is_introduced_inside_the_footprint():
    """A denormal trace used to produce 0/0 -> NaN; the guard must keep the field finite."""
    import numpy as _np
    rng = _np.random.default_rng(4)
    fields = {"line": _line_field(60.0) * 1000.0,
              "tiny_noise": (_np.random.default_rng(5).normal(size=(N, N)) * 1e-40).astype(_np.float32),
              "flat": _np.zeros((N, N), dtype=_np.float32)}
    for name, f in fields.items():
        st = S.structure_tensor(f, _valid(), sigma_tensor_m=300.0)
        for k, g in st.items():
            assert _np.isfinite(g).all(), f"{name}: {k} has non-finite values"


def test_coherence_stays_inside_the_unit_interval():
    """A ratio of the tensor's eigenvalues cannot exceed 1; float32 can, so it is clipped."""
    rng = np.random.default_rng(11)
    for field in (_line_field(25.0), (rng.normal(size=(N, N)) * 1e-30).astype(np.float32),
                  (rng.normal(size=(N, N)) * 1e30).astype(np.float32)):
        coh = S.structure_tensor(field, _valid(), sigma_tensor_m=300.0)["coherence"]
        v = coh[np.isfinite(coh)]
        assert v.min() >= 0.0 and v.max() <= 1.0


def test_energy_is_scale_invariant_through_coherence():
    """Coherence is a ratio, so multiplying the field by 1000 must not change it."""
    a = _line_field(60.0)
    st1 = S.structure_tensor(a, _valid(), sigma_tensor_m=300.0)
    st2 = S.structure_tensor(a * 1000.0, _valid(), sigma_tensor_m=300.0)
    m = np.isfinite(st1["coherence"])
    # 1e-5, not 1e-9: float32 with a 1000x amplitude leaves ~2e-6 of rounding in the ratio
    assert np.all(np.abs(st1["coherence"][m] - st2["coherence"][m]) < 1e-5)
    assert not np.allclose(st1["energy"][m], st2["energy"][m])
