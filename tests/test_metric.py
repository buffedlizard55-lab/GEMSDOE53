"""Metric tests: the vectorised DTI must match a literal implementation of the official formulas,
and the rules' worked example (TP_w=3.00, FP_w=1.89, FN_w=2.00 -> TI=0.60) must reproduce."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems53.core import ALPHA, BETA, dti, dti_bruteforce  # noqa: E402


def test_worked_example_from_official_rules_arithmetic():
    # Official problem-description page, "Scoring example": TP=3.00, FP=1.89, FN=2.00 -> 0.60
    val = 3.00 / (3.00 + ALPHA * 1.89 + BETA * 2.00)
    assert round(val, 2) == 0.60
    assert (ALPHA, BETA) == (0.2, 0.8)


def test_single_pixel_exact_hit_is_one():
    gt = np.zeros((9, 9), bool)
    gt[4, 4] = True
    p = np.zeros((9, 9))
    p[4, 4] = 1.0
    r = dti(p, gt)
    assert abs(r["DTI"] - 1.0) < 1e-6 and r["FP_w"] < 1e-12 and r["FN_w"] < 1e-12


def test_one_pixel_offset_matches_hand_calculation():
    # GT at (4,4); prediction 1.0 at (4,5), i.e. 1 px = 100 m away. k(100 m) = 1 - 100/300 = 2/3.
    gt = np.zeros((9, 9), bool)
    gt[4, 4] = True
    p = np.zeros((9, 9))
    p[4, 5] = 1.0
    r = dti(p, gt)
    assert abs(r["TP_w"] - 2 / 3) < 1e-9
    assert abs(r["FN_w"] - 1 / 3) < 1e-9
    assert abs(r["FP_w"] - 1 / 3) < 1e-9
    assert abs(r["DTI"] - (2 / 3) / (2 / 3 + 0.2 / 3 + 0.8 / 3)) < 1e-9


def test_vectorised_matches_bruteforce_on_random_grids():
    rng = np.random.default_rng(0)
    for trial in range(6):
        H, W = 14, 13
        gt = rng.random((H, W)) < 0.04
        if not gt.any():
            gt[3, 3] = True
        p = np.where(rng.random((H, W)) < 0.3, rng.random((H, W)), 0.0)
        a = dti(p, gt)
        b = dti_bruteforce(p, gt)
        assert abs(a["TP_w"] - b["TP_w"]) < 1e-7, trial
        assert abs(a["FP_w"] - b["FP_w"]) < 1e-7, trial
        assert abs(a["FN_w"] - b["FN_w"]) < 1e-7, trial
        assert abs(a["DTI"] - b["DTI"]) < 1e-7, trial


def test_empty_prediction_scores_zero():
    gt = np.zeros((5, 5), bool)
    gt[2, 2] = True
    r = dti(np.zeros((5, 5)), gt)
    assert r["DTI"] == 0.0 and abs(r["FN_w"] - 1.0) < 1e-12
