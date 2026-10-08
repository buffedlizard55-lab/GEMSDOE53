"""Tests for the H57 two-view instrument and the anisotropic emitter.

The anisotropy test is the important one: it checks the hand derivation in
``knowledge/17_hypotheses_H57_preregistered.md`` (H57-A) against this repo's own literal metric
transcription, so the "+20 % of credited truth per node at 4-5 px along-strike" claim is a
measurement here, not an assertion in prose.
"""
from __future__ import annotations

import numpy as np
import pytest

from gems52 import h57
from gems52 import metric as M


def _periodic_trace(sep: int, n_nodes: int = 6):
    """A 1-px truth trace over ``n_nodes`` node intervals, with guard nodes on **both** sides so
    every scored pixel has two-sided coverage and the credit is exactly periodic -- which is what
    makes the closed form checkable rather than an end-effect artefact."""
    span = sep * n_nodes
    pad = 2 * sep + 4
    shape = (21, span + 2 * pad)
    truth = np.zeros(shape, bool)
    truth[10, pad:pad + span] = True
    p = np.zeros(shape, np.float32)
    for i in range(-2, n_nodes + 2):
        x = pad + i * sep
        if 0 <= x < shape[1]:
            p[10, x] = 1.0
    return p, truth, n_nodes


# Closed form, derived by hand from k(0)=1, k(1)=2/3, k(2)=1/3, k(3)=0 over one node interval
# [0, s):  s=3 -> 1 + 2/3 + 2/3 = 7/3 ;  s=4 -> 1 + 2/3 + 1/3 + 2/3 = 8/3 ;  s=5 -> 3.
PER_NODE_CREDIT = {3: 7.0 / 3.0, 4: 8.0 / 3.0, 5: 3.0}


@pytest.mark.parametrize("sep", [3, 4, 5])
def test_along_strike_spacing_credit_matches_closed_form(sep):
    """TPw per node on a 1-px trace, straight out of the metric code -- not an assertion."""
    p, truth, n = _periodic_trace(sep)
    m, _q, _ed = M.max_cover(p, truth)
    assert m.sum() / n == pytest.approx(PER_NODE_CREDIT[sep], abs=1e-9)


def test_four_or_five_px_along_strike_beats_three():
    """The load-bearing H57-A claim: at equal node budget, 3 px leaves credit on the table."""
    per_node = {}
    for sep in (3, 4, 5):
        p, truth, n = _periodic_trace(sep)
        m, _q, _ed = M.max_cover(p, truth)
        per_node[sep] = m.sum() / n
    assert per_node[5] > per_node[4] > per_node[3]
    assert per_node[5] / per_node[3] == pytest.approx(3.0 / (7.0 / 3.0), rel=1e-9)


def test_gain_survives_one_pixel_placement_error():
    """With every node displaced by a random +/-1 px offset, 5 px still beats 3 px.  The emitter
    must be robust to the trace not being exactly where we think it is."""
    rng = np.random.default_rng(11)
    per_node = {3: [], 4: [], 5: []}
    for trial in range(20):
        for sep in (3, 4, 5):
            p, truth, n = _periodic_trace(sep)
            p[:] = 0.0
            for i in range(n):
                x = 2 + i * sep + int(rng.integers(-1, 2))
                y = 10 + int(rng.integers(-1, 2))
                p[y, x] = 1.0
            m, _q, _ed = M.max_cover(p, truth)
            per_node[sep].append(m.sum() / n)
    assert np.mean(per_node[5]) > np.mean(per_node[4]) > np.mean(per_node[3])


def test_across_strike_nodes_are_not_redundant():
    """Two nodes 3 px apart across a trace sit on different lines; the metric keeps only one."""
    p = np.zeros((21, 21), np.float32)
    p[10, 10] = 1.0
    truth = np.zeros((21, 21), bool)
    truth[10, 10] = True
    truth[13, 10] = True
    m, _q, _ed = M.max_cover(p, truth)
    assert m.sum() == pytest.approx(1.0, abs=1e-9)   # 3 px away -> k = 0


def _synthetic_trace(shape=(140, 320), row=70, span=(10, 310), band=8):
    truth = np.zeros(shape, bool)
    truth[row, span[0]:span[1]] = True
    score = np.zeros(shape, np.float32)
    score[row, span[0]:span[1]] = 1.0
    allowed = np.zeros(shape, bool)
    allowed[row - band:row + band + 1, :] = True
    return truth, score, allowed


def test_aniso_respects_the_directed_separation():
    """Along a confident strike of 0 rad (the +x / column direction, array convention) nodes must
    be >= 5 px apart along it; across it only >= 3 px."""
    shape = (60, 200)
    score = np.zeros(shape, np.float32)
    score[30, 5:195] = 1.0
    strike = np.zeros(shape, np.float32)
    coh = np.ones(shape, np.float32)
    allowed = np.zeros(shape, bool)
    allowed[25:36, :] = True
    out = h57.aniso_select(score, strike, coh, allowed, 60, along_px=5, across_px=3, nms_px=5)
    cols = np.nonzero(out[30])[0]
    assert cols.size >= 3
    assert np.all(np.diff(cols) >= 5 - 1e-9)


def test_aniso_beats_iso_on_a_synthetic_linear_truth_at_equal_node_count():
    """The load-bearing end-to-end check: same k, same allowed set, same greedy order, one
    straight trace to recover.  The metric is the only judge."""
    truth, score, allowed = _synthetic_trace()
    strike = np.zeros(truth.shape, np.float32)
    coh = np.ones(truth.shape, np.float32)
    rows = {}
    for name, arr in (("iso3", h57.iso_select(score, allowed, 40, min_px=3.0, nms_px=5)),
                      ("aniso5", h57.aniso_select(score, strike, coh, allowed, 40,
                                                  along_px=5, across_px=3, nms_px=5))):
        rows[name] = M.dti(arr.astype(np.float32), truth)
    assert rows["iso3"]["tpw"] < rows["aniso5"]["tpw"], rows
    assert rows["iso3"]["mass"] == rows["aniso5"]["mass"] == 40.0
    assert rows["aniso5"]["dti"] > rows["iso3"]["dti"]


def test_orientation_quality_controls_the_gain():
    """Negative control, kept as a test so the limitation can never be quietly removed: the 5 px
    allowance is only worth anything when the strike points along the structure.  A strike
    rotated onto the wrong axis gives the isotropic result, not more.  This is exactly why
    ``min_coh`` is a registered, fold-gated parameter rather than a tuned one."""
    truth, score, allowed = _synthetic_trace()
    right = h57.aniso_select(score, np.zeros(truth.shape, np.float32),
                             np.ones(truth.shape, np.float32), allowed, 40,
                             along_px=5, across_px=3, nms_px=5).astype(np.float32)
    wrong = h57.aniso_select(score, np.full(truth.shape, np.pi / 2, np.float32),
                             np.ones(truth.shape, np.float32), allowed, 40,
                             along_px=5, across_px=3, nms_px=5).astype(np.float32)
    base = h57.iso_select(score, allowed, 40, min_px=3.0, nms_px=5).astype(np.float32)
    assert M.dti(right, truth)["tpw"] > M.dti(wrong, truth)["tpw"]
    assert M.dti(wrong, truth)["tpw"] <= M.dti(base, truth)["tpw"] + 1e-9
    # abstaining from the orientation entirely recovers the isotropic result exactly
    abstain = h57.aniso_select(score, np.zeros(truth.shape, np.float32),
                              np.zeros(truth.shape, np.float32), allowed, 40,
                              along_px=5, across_px=3, nms_px=5)
    assert np.array_equal(abstain, h57.iso_select(score, allowed, 40, min_px=3.0, nms_px=5))


def test_aniso_degrades_to_isotropic_when_the_tensor_is_collapsed():
    """With along == across the anisotropic emitter *is* the isotropic one, bit for bit."""
    shape = (120, 120)
    rng = np.random.default_rng(1)
    score = rng.random(shape).astype(np.float32)
    strike = np.full(shape, 0.37, np.float32)
    coh = np.ones(shape, np.float32)
    allowed = np.ones(shape, bool)
    a = h57.aniso_select(score, strike, coh, allowed, 150, along_px=3, across_px=3)
    b = h57.iso_select(score, allowed, 150, min_px=3.0)
    assert np.array_equal(a, b)


def test_disagreement_strata_are_mutually_exclusive():
    shape = (40, 40)
    rng = np.random.default_rng(2)
    pa = rng.random(shape).astype(np.float32)
    pb = rng.random(shape).astype(np.float32)
    allowed = np.ones(shape, bool)
    d = h57.disagreement(pa, pb, allowed, q_conf=0.6, q_abstain=0.4)
    m = d["masks"]
    tot = m["a_only"] | m["b_only"] | m["concordant"] | m["neither"]
    assert np.array_equal(tot, allowed)
    assert not (m["a_only"] & m["b_only"]).any()
    assert not (m["a_only"] & m["concordant"]).any()


def test_marginal_acceptance_rule_reduces_to_k_above_alpha_dti():
    """The metric module's rule ``c(1-aD) > aD f`` with c = k, f = 1 - k reduces to k > aD."""
    from scipy.optimize import brentq

    alpha, dti = M.ALPHA, 0.2778
    bar = alpha * dti

    def f(k):
        return k * (1 - alpha * dti) - alpha * dti * (1 - k)

    assert f(bar) == pytest.approx(0.0, abs=1e-12)
    assert brentq(f, 0.0, 0.5) == pytest.approx(bar, abs=1e-12)


def test_component_folds_never_split_a_component():
    from scipy import ndimage
    rng = np.random.default_rng(3)
    cat = np.zeros((80, 80), bool)
    for _ in range(12):
        y, x = rng.integers(5, 70, 2)
        cat[y, x] = True
        cat[y:y + 4, x:x + 4] = True
    valid = np.ones((80, 80), bool)
    fid = h57.component_folds(cat, valid, 4)
    lab, n = ndimage.label(cat, np.ones((3, 3), bool))
    for i in range(1, n + 1):
        assert len(set(np.unique(fid[lab == i]))) == 1


def test_layer_split_matches_the_brief():
    """View A is potential-field/subsurface; View B is surface + the radiometric band the brief
    names explicitly.  Band 6 is radiometric total count per evidence/h53_band6_identity.json."""
    assert "B_rad_tc" in h57.VIEW_B_LAYERS
    assert not any(n.startswith("A_rad") for n in h57.VIEW_A_LAYERS)
    for must in ("A_mag_anom", "A_grav_anom", "A_depth_to_base", "A_eq_density", "A_cond_surf"):
        assert must in h57.VIEW_A_LAYERS
    for must in ("B_det_elev", "B_det_elev_slope"):
        assert must in h57.VIEW_B_LAYERS

def test_layers_matrix_is_pixel_major(tmp_path):
    """Layer-major memmap in, pixel-major matrix out -- the axis order the model is fitted on."""
    import json
    import numpy as np

    from gems52 import h57 as H

    names = ["a_val", "a_grad", "b_val", "b_grad"]
    arr = np.zeros((4, 5, 6), np.uint8)
    for i in range(4):
        arr[i] = i * 60
    mm = np.lib.format.open_memmap(tmp_path / "layers.u8", mode="w+", dtype=np.uint8,
                                   shape=arr.shape)
    mm[:] = arr
    mm.flush()
    del mm
    (tmp_path / "layers.json").write_text(json.dumps({"names": names}))
    L = H.Layers(str(tmp_path))
    m = L.matrix(L.index(["a_val", "b_val"]), 1, 3)
    assert m.shape == (2 * 6, 2)
    assert np.allclose(m[:, 0], 0.0)          # a_val is layer 0
    assert np.allclose(m[:, 1], 120 / 255.0)  # b_val is layer 2


def test_data_root_path_redirects_data_sources_without_touching_the_default():
    from pathlib import Path

    assert h57.data_root_path("data/training_features.tif") == Path("data/training_features.tif")
    assert h57.data_root_path("data/external/geodawn_rad_u8.tif", "work/h58_pinned") == \
        Path("work/h58_pinned/external/geodawn_rad_u8.tif")
    absolute = Path("/tmp/pinned/training_features.tif")
    assert h57.data_root_path(absolute, "ignored") == absolute
