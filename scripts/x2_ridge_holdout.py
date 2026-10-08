#!/usr/bin/env python3
"""X2 - pre-registered hide-and-recover holdout of the ridge candidate against the frozen HGB baseline.

Pre-registration: evidence/preregistration_x2.json (written and hashed BEFORE this script was run).

Design (identical folds, buffer and visible-mask rule as E2):
  visible  = known faults outside fold k (the only catalogue information fold k may use)
  withheld = known faults inside fold k  (HOLDOUT-DTI proxy truth, scored with the shared template metric)
  buffer   = 10 px (1 km) around withheld pixels, excluded from HGB training
  emission = pixel-exact mask of visible faults; emitted dot budget N is the same for every arm

Arms:
  hgb_bands   : frozen baseline. HGB on the 19 label-free bands; top-N probability (replays E2's RNG
                sequence, so its q-grid numbers should reproduce evidence/exp2_holdout_arms.json)
  ridge_pack  : candidate. Ridge centrelines (band 2 only), Poisson-disk packed at 2.8 px, binary dots
  ridge_topn  : ablation. Same centrelines, top-N by line strength with NO spacing rule

Scoring: GtContext from the SHARED evaluator in the template (src/metrics.py, commit dcbbb19).
Pooled DTI = sum of fold TP_w, FP_w, FN_w, then one DTI. Per-fold paired differences give the CI.

Writes evidence/x2_ridge_holdout.json. Usage:
  python scripts/x2_ridge_holdout.py --data-dir /tmp/gems53-data --template /tmp/gems-template
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import buffer_zone, load_inputs, segment_folds  # noqa: E402
from gems53.ridge import nms_centrelines, poisson_pack, ridge_fields  # noqa: E402
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402  (frozen baseline code, reused)

N_GRID = [37654, 44090, 51674, 103348]
N_PRIMARY = 44090
Q_GRID = [0.005, 0.0073, 0.01, 0.02]  # E2 q-grid, replayed for the reproduction check
FROZEN_BEST = 0.035233  # evidence/exp2_holdout_arms.json: bands, q=0.02 pooled
T_CRIT_DF4 = 2.776
N_NEG = 300_000
K_FOLDS = 5
BAND_RTP = 2


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_shared_metric(template: Path):
    sys.path.insert(0, str(template / "src"))
    import metrics as shared  # the template's shared evaluator (not a copy)
    return shared


def exact_topn(p_full: np.ndarray, candidates: np.ndarray, n: int) -> np.ndarray:
    """Exact top-n by probability among candidate pixels (ties broken by array order)."""
    rr, cc = np.nonzero(candidates)
    vals = p_full[rr, cc]
    n = min(n, vals.size)
    order = np.argsort(-vals, kind="stable")[:n]
    out = np.zeros(p_full.shape, dtype=np.float32)
    out[rr[order], cc[order]] = vals[order]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template", default="/tmp/gems-template")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "x2_ridge_holdout.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    shared = load_shared_metric(Path(args.template))

    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fold_grid, n_seg, seg_lab = segment_folds(inp.cat, K=K_FOLDS, seed=53)
    footprint_px = int(inp.fp.sum())
    with rasterio.open(dd / "training_features.tif") as src:
        rtp = src.read(BAND_RTP).astype(np.float64)
    rtp[rtp < -1e30] = np.nan
    L, th, pol, _det = ridge_fields(rtp, inp.fp)
    centre = nms_centrelines(L, th)
    rtp_ok = inp.fp & np.isfinite(rtp)  # no-data RTP cells cannot be a line observation

    rng = np.random.default_rng(53)  # same seed and draw order as E2 (bands arm first)
    arms = {"hgb_bands": {}, "ridge_pack": {}, "ridge_topn": {}}
    fold_rows = {a: [] for a in arms}
    pooled = {a: {n: {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0} for n in N_GRID} for a in arms}
    hgb_q = {q: {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0} for q in Q_GRID}
    hgb_q_rows = []

    for k in range(K_FOLDS):
        tk = time.time()
        hidden = inp.cat & (fold_grid == k)
        visible = inp.cat & (fold_grid != k)
        buf = buffer_zone(hidden, 10)
        ctx = shared.GtContext(hidden, R_pixels=3)  # shared template scorer, built once per fold

        # ---- hgb_bands (frozen baseline) -------------------------------------------------------
        F_all = inp.feats
        pos_mask = visible & ~buf & inp.fp
        neg_mask = inp.fp & ~inp.cat & ~buf
        pos_rows = inp.fp_idx[pos_mask]
        neg_pool = inp.fp_idx[neg_mask]
        neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
        rows = np.r_[pos_rows, neg_rows]
        y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
        model = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                               l2_regularization=1.0, random_state=0)
        model.fit(F_all[rows], y)
        p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
        p_full[inp.fp] = predict_chunked(model, F_all)
        p_full[visible] = 0.0
        cand_hgb = inp.fp & ~visible
        row_q = {"fold": k, "per_q": {}}
        for q in Q_GRID:  # E2 reproduction check (same function as E2)
            emis = top_q_emission(p_full, cand_hgb, q, footprint_px)
            d, (tp, fp_, fn) = ctx.score(emis, return_components=True)
            row_q["per_q"][str(q)] = {"DTI": round(float(d), 6), "emitted_px": int(np.count_nonzero(emis))}
            hgb_q[q]["TP_w"] += tp
            hgb_q[q]["FP_w"] += fp_
            hgb_q[q]["FN_w"] += fn
        hgb_q_rows.append(row_q)
        for n in N_GRID:
            emis = exact_topn(p_full, cand_hgb, n)
            d, (tp, fp_, fn) = ctx.score(emis, return_components=True)
            pooled["hgb_bands"][n]["TP_w"] += tp
            pooled["hgb_bands"][n]["FP_w"] += fp_
            pooled["hgb_bands"][n]["FN_w"] += fn
            fold_rows["hgb_bands"].append({"fold": k, "N": n, "DTI": float(d), "TP_w": tp, "FP_w": fp_, "FN_w": fn,
                                           "emitted_px": int(np.count_nonzero(emis))})
        del p_full, F_all

        # ---- ridge arms ------------------------------------------------------------------------
        cand_ridge = rtp_ok & ~visible
        rr, cc = np.nonzero(centre & cand_ridge & (L > 0))
        order = np.argsort(-L[rr, cc], kind="stable")
        rc_sorted = np.stack([rr[order], cc[order]], axis=1)
        packed = poisson_pack(rc_sorted, max(N_GRID))  # greedy prefix property: first n == packing for n
        for n in N_GRID:
            emis = np.zeros(inp.fp.shape, dtype=np.float32)
            sel = packed[:n]
            emis[sel[:, 0], sel[:, 1]] = 1.0
            d, (tp, fp_, fn) = ctx.score(emis, return_components=True)
            pooled["ridge_pack"][n]["TP_w"] += tp
            pooled["ridge_pack"][n]["FP_w"] += fp_
            pooled["ridge_pack"][n]["FN_w"] += fn
            fold_rows["ridge_pack"].append({"fold": k, "N": n, "DTI": float(d), "TP_w": tp, "FP_w": fp_, "FN_w": fn,
                                            "emitted_px": int(np.count_nonzero(emis)),
                                            "packed_available": int(packed.shape[0])})
            top = rc_sorted[:n]
            emis2 = np.zeros(inp.fp.shape, dtype=np.float32)
            emis2[top[:, 0], top[:, 1]] = 1.0
            d2, (tp2, fp2, fn2) = ctx.score(emis2, return_components=True)
            pooled["ridge_topn"][n]["TP_w"] += tp2
            pooled["ridge_topn"][n]["FP_w"] += fp2
            pooled["ridge_topn"][n]["FN_w"] += fn2
            fold_rows["ridge_topn"].append({"fold": k, "N": n, "DTI": float(d2), "TP_w": tp2, "FP_w": fp2,
                                            "FN_w": fn2, "emitted_px": int(np.count_nonzero(emis2))})
        print(f"fold {k} done in {time.time() - tk:.1f}s; withheld px={int(hidden.sum())}", flush=True)

    def pooled_dti(P):
        return P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9)

    summary = {}
    for a in arms:
        summary[a] = {}
        for n in N_GRID:
            per_fold = [r["DTI"] for r in fold_rows[a] if r["N"] == n]
            m = float(np.mean(per_fold))
            half = float(T_CRIT_DF4 * np.std(per_fold, ddof=1) / np.sqrt(len(per_fold)))
            summary[a][str(n)] = {
                "pooled_DTI": round(float(pooled_dti(pooled[a][n])), 6),
                "pooled_TP_w": round(pooled[a][n]["TP_w"], 4),
                "pooled_FP_w": round(pooled[a][n]["FP_w"], 4),
                "pooled_FN_w": round(pooled[a][n]["FN_w"], 4),
                "per_fold_DTI": [round(x, 6) for x in per_fold],
                "per_fold_mean": round(m, 6),
                "CI95_t_df4_on_fold_mean": [round(m - half, 6), round(m + half, 6)],
            }
    # paired differences at each N (same folds, same budget)
    paired = {}
    for n in N_GRID:
        for a, b in (("ridge_pack", "hgb_bands"), ("ridge_pack", "ridge_topn")):
            da = np.array([r["DTI"] for r in fold_rows[a] if r["N"] == n])
            db = np.array([r["DTI"] for r in fold_rows[b] if r["N"] == n])
            diff = da - db
            m = float(diff.mean())
            half = float(T_CRIT_DF4 * diff.std(ddof=1) / np.sqrt(len(diff)))
            paired[f"{a}_minus_{b}@{n}"] = {"mean": round(m, 6), "CI95_t_df4": [round(m - half, 6), round(m + half, 6)],
                                             "per_fold": [round(float(x), 6) for x in diff]}
    # E2 reproduction check (HGB, top-q, using the shared scorer)
    repro = {str(q): {"DTI_shared_scorer": round(float(pooled_dti(hgb_q[q])), 6)} for q in Q_GRID}

    p_primary = summary["ridge_pack"][str(N_PRIMARY)]["pooled_DTI"]
    ci_lo = paired[f"ridge_pack_minus_hgb_bands@{N_PRIMARY}"]["CI95_t_df4"][0]
    gates = {
        "G1_holdout_best": {"rule": "pooled ridge_pack@44090 > 0.035233", "value": p_primary,
                            "pass": bool(p_primary > FROZEN_BEST)},
        "G2_equal_budget": {"rule": "paired ridge_pack - hgb_bands @44090: CI95 lower bound > 0",
                            "value": ci_lo, "pass": bool(ci_lo > 0)},
    }
    report = {
        "experiment": "X2 pre-registered holdout: ridge candidate vs frozen HGB baseline (equal dot budget)",
        "label_type": "HOLDOUT-DTI (proxy: withheld catalogue segments; NOT the competition's new-fault truth)",
        "scorer": {"name": "shared template src/metrics.py GtContext (commit dcbbb19)",
                   "R_pixels": 3, "alpha": 0.2, "beta": 0.8,
                   "source": "https://github.com/buffedlizard55-lab/GEMSDOE/blob/dcbbb19/src/metrics.py"},
        "preregistration": "evidence/preregistration_x2.json",
        "inputs": {"training_features.tif": sha256(dd / "training_features.tif"),
                   "labels.tif": sha256(dd / "labels.tif"),
                   "sample_submission.tif": sha256(dd / "sample_submission.tif"),
                   "ridge_module_sha256": sha256(ROOT / "src" / "gems53" / "ridge.py")},
        "footprint_px": footprint_px,
        "known_fault_px": int(inp.cat.sum()),
        "folds": {"K": K_FOLDS, "seed": 53, "buffer_px": 10, "segments": int(n_seg)},
        "ridge_centreline_candidates_all_folds_ref": int(centre.sum()),
        "N_grid": N_GRID, "N_primary": N_PRIMARY,
        "frozen_best_reference": {"value": FROZEN_BEST, "source": "evidence/exp2_holdout_arms.json bands q=0.02"},
        "arms": summary,
        "paired_differences": paired,
        "E2_reproduction_hgb_top_q": {"shared_scorer": repro,
                                      "E2_recorded_pooled": {"0.005": 0.021681, "0.0073": 0.025063,
                                                              "0.01": 0.027919, "0.02": 0.035233},
                                      "per_fold_q": hgb_q_rows},
        "gates": gates,
        "G1_G2_pass": bool(gates["G1_holdout_best"]["pass"] and gates["G2_equal_budget"]["pass"]),
        "runtime_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print(json.dumps({"ridge_pack": {n: summary["ridge_pack"][str(n)]["pooled_DTI"] for n in N_GRID},
                      "ridge_topn": {n: summary["ridge_topn"][str(n)]["pooled_DTI"] for n in N_GRID},
                      "hgb_bands": {n: summary["hgb_bands"][str(n)]["pooled_DTI"] for n in N_GRID},
                      "repro": repro, "gates": gates}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
