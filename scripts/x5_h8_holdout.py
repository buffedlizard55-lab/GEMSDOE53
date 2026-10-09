#!/usr/bin/env python3
"""X5 - hide-and-recover holdout of four H8-lane placement arms (pre-registration-h8-2026-10-09.md, X5).

Design (identical folds as E2/X2: whole segments, K=5, seed 53):
  visible  = catalogue segments outside fold k  (the only catalogue information fold k may use)
  withheld = catalogue segments inside fold k   (HOLDOUT-DTI truth)
  every catalogue-derived feature (tip, relay) is computed from `visible` only

Arms (all emission = binary dots at 2.8 px Poisson spacing; ALL pruned strictly >2 px off `visible`,
matching H33-2-B2's 'b2' step, except the un-pruned reproduction control):
  null_pr    : uniform random order over the allowed pixels
  halo_pr    : proximity-first (ascending distance to visible faults)
  ridge_pr   : magnetic lineament centrelines (band 2, Hessian/NMS), descending line strength
  h8_pr      : tip+relay corridors with ridge concordance (src/gems53/corridors.py), descending surface
  ridge_nopr : reproduction control at N=44090 only: x2's ridge_pack arm (cand = ~visible, no prune)

Scorer: GtContext from the SHARED template evaluator (src/metrics.py at the pinned commit).
Pooled DTI = sum of fold TP_w/FP_w/FN_w, then one DTI; CI = t interval on the 5 fold values (df 4).

Selection rule (pre-registered): candidate arm = highest pooled DTI at N=44,090 among ridge_pr/h8_pr/
halo_pr; submission budget = the candidate's N with higher pooled DTI (44,090 vs 80,000).

Writes evidence/x5_h8_holdout.json.
Usage: python scripts/x5_h8_holdout.py --data-dir /tmp/gems53-data --template /tmp/gems-template
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
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems53.core import dist_to, segment_folds  # noqa: E402
from gems53.corridors import (  # noqa: E402
    corridor_surface,
    prune_mask,
    relay_surface,
    tip_continuation_surface,
)
from gems53.ridge import nms_centrelines, poisson_pack, ridge_fields  # noqa: E402

K_FOLDS = 5
SEED = 53
BAND_RTP = 2
N_GRID = [44090, 80000]
N_PRIMARY = 44090
R_PACK_PX = 2.8
T_CRIT_DF4 = 2.776
X2_REFERENCE_RIDGE_PACK_44090 = 0.050097  # evidence/x2_ridge_holdout.json (same folds/scorer/pack)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_shared_metric(template: Path):
    sys.path.insert(0, str(template / "src"))
    import metrics as shared  # the template's shared evaluator (not a copy)
    return shared


def pack_from_order(order_rc: np.ndarray, n_target: int) -> np.ndarray:
    """Greedy Poisson-disk prefix (same rule as gems53.ridge.poisson_pack, early-stopped at n_target)."""
    return poisson_pack(order_rc, n_target, r_px=R_PACK_PX)


def emit(rows_cols: np.ndarray, shape) -> np.ndarray:
    e = np.zeros(shape, dtype=np.float32)
    if len(rows_cols):
        e[rows_cols[:, 0], rows_cols[:, 1]] = 1.0
    return e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template", default="/tmp/gems-template")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "x5_h8_holdout.json"))
    args = ap.parse_args()
    t0 = time.time()
    dd = Path(args.data_dir)
    shared = load_shared_metric(Path(args.template))

    with rasterio.open(dd / "sample_submission.tif") as src:
        fp = np.isfinite(src.read(1))
    with rasterio.open(dd / "labels.tif") as src:
        lab = src.read(1)
    cat = (lab == 1) & fp
    with rasterio.open(dd / "training_features.tif") as src:
        rtp = src.read(BAND_RTP).astype(np.float64)
    rtp[rtp < -1e30] = np.nan
    rtp_ok = fp & np.isfinite(rtp)

    fold_grid, n_seg, _ = segment_folds(cat, K=K_FOLDS, seed=SEED)
    L, th, pol, _det = ridge_fields(rtp, fp)
    centre = nms_centrelines(L, th)
    ridge_ok = rtp_ok & centre & (L > 0)

    rng = np.random.default_rng(SEED)
    arms = ["null_pr", "halo_pr", "ridge_pr", "h8_pr"]
    budgets = {a: list(N_GRID) for a in arms}
    budgets["ridge_nopr"] = [N_PRIMARY]
    fold_rows = []
    pooled = {a: {n: {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0} for n in budgets[a]} for a in budgets}

    for k in range(K_FOLDS):
        tk = time.time()
        visible = cat & (fold_grid != k)
        hidden = cat & (fold_grid == k)
        ctx = shared.GtContext(hidden, R_pixels=3)
        pr = prune_mask(visible, px=2)
        d_vis = dist_to(visible)

        tip = tip_continuation_surface(visible)
        rel = relay_surface(visible)
        comb = corridor_surface(visible, L, fp)

        allowed = fp & pr
        rr, cc = np.nonzero(allowed)
        tiebreak = rng.random(rr.size)          # seeded tie-break so equal-surface pixels are not row-major
        order_defs = {
            "null_pr": np.stack([rr, cc, rng.random(rr.size)], axis=1),
            "halo_pr": np.stack([rr, cc, -d_vis[rr, cc] + 1e-9 * tiebreak], axis=1),
            "h8_pr": np.stack([rr, cc, comb[rr, cc] + 1e-9 * tiebreak], axis=1),
        }
        # ridge_pr emits ONLY on magnetic centrelines (an arm is its method; no fallback pixels)
        rrr, rcc = np.nonzero(allowed & ridge_ok)
        order_defs["ridge_pr"] = np.stack([rrr, rcc, L[rrr, rcc] + 1e-9 * rng.random(rrr.size)], axis=1)
        # sort each candidate list best-first (desc on column 2, stable)
        for name in order_defs:
            o = order_defs[name]
            order_defs[name] = o[np.argsort(-o[:, 2], kind="stable")][:, :2].astype(np.int64)

        # reproduction control: x2's exact candidates (no prune)
        rr2, cc2 = np.nonzero(ridge_ok & ~visible)
        o2 = np.stack([rr2, cc2], axis=1)
        o2 = o2[np.argsort(-L[rr2, cc2], kind="stable")].astype(np.int64)

        for name in arms:
            packed = pack_from_order(order_defs[name], max(budgets[name]))
            for n in budgets[name]:
                sel = packed[:n]
                emis = emit(sel, cat.shape)
                d, (tp, fpw, fn) = ctx.score(emis, return_components=True)
                pooled[name][n]["TP_w"] += tp
                pooled[name][n]["FP_w"] += fpw
                pooled[name][n]["FN_w"] += fn
                fold_rows.append({"arm": name, "fold": k, "N": n, "DTI": float(d),
                                  "TP_w": float(tp), "FP_w": float(fpw), "FN_w": float(fn),
                                  "emitted_px": int(len(sel)), "packed_available": int(len(packed))})
        packed2 = pack_from_order(o2, N_PRIMARY)
        sel = packed2[:N_PRIMARY]
        emis = emit(sel, cat.shape)
        d, (tp, fpw, fn) = ctx.score(emis, return_components=True)
        pooled["ridge_nopr"][N_PRIMARY]["TP_w"] += tp
        pooled["ridge_nopr"][N_PRIMARY]["FP_w"] += fpw
        pooled["ridge_nopr"][N_PRIMARY]["FN_w"] += fn
        fold_rows.append({"arm": "ridge_nopr", "fold": k, "N": N_PRIMARY, "DTI": float(d),
                          "TP_w": float(tp), "FP_w": float(fpw), "FN_w": float(fn),
                          "emitted_px": int(len(sel)), "packed_available": int(len(packed2))})
        print(f"fold {k} done in {time.time() - tk:.1f}s; withheld px={int(hidden.sum())}", flush=True)

    def pooled_dti(P):
        return P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9)

    summary = {}
    for a in budgets:
        summary[a] = {}
        for n in budgets[a]:
            per_fold = [r["DTI"] for r in fold_rows if r["arm"] == a and r["N"] == n]
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

    def paired(a, b, n):
        da = np.array([r["DTI"] for r in fold_rows if r["arm"] == a and r["N"] == n])
        db = np.array([r["DTI"] for r in fold_rows if r["arm"] == b and r["N"] == n])
        diff = da - db
        m = float(diff.mean())
        half = float(T_CRIT_DF4 * diff.std(ddof=1) / np.sqrt(len(diff)))
        return {"mean": round(m, 6), "CI95_t_df4": [round(m - half, 6), round(m + half, 6)],
                "per_fold": [round(float(x), 6) for x in diff]}

    compare = {}
    for a in ("h8_pr", "halo_pr", "null_pr"):
        compare[f"{a}_minus_ridge_pr@{N_PRIMARY}"] = paired(a, "ridge_pr", N_PRIMARY)
        compare[f"{a}_minus_ridge_pr@80000"] = paired(a, "ridge_pr", 80000)
    compare["h8_pr_minus_halo_pr@44090"] = paired("h8_pr", "halo_pr", N_PRIMARY)
    compare["h8_pr_minus_halo_pr@80000"] = paired("h8_pr", "halo_pr", 80000)

    # pre-registered selection
    cands = ["ridge_pr", "h8_pr", "halo_pr"]
    best_arm = max(cands, key=lambda a: summary[a][str(N_PRIMARY)]["pooled_DTI"])
    best_budget = max(N_GRID, key=lambda n: summary[best_arm][str(n)]["pooled_DTI"])
    repro_delta = summary["ridge_nopr"][str(N_PRIMARY)]["pooled_DTI"] - X2_REFERENCE_RIDGE_PACK_44090

    report = {
        "experiment": "X5 pre-registered hide-and-recover holdout of H8-lane placement arms",
        "label_type": "HOLDOUT-DTI (proxy: withheld catalogue segments; NOT the competition's new-fault truth)",
        "scorer": {"name": "shared template src/metrics.py GtContext (pinned template commit)",
                   "R_pixels": 3, "alpha": 0.2, "beta": 0.8},
        "preregistration": "docs/research/preregistration-h8-2026-10-09.md",
        "inputs": {
            "training_features.tif": sha256(dd / "training_features.tif"),
            "labels.tif": sha256(dd / "labels.tif"),
            "sample_submission.tif": sha256(dd / "sample_submission.tif"),
        },
        "folds": {"K": K_FOLDS, "seed": SEED, "segments": int(n_seg),
                  "withheld_px_per_fold": [int((cat & (fold_grid == k)).sum()) for k in range(K_FOLDS)]},
        "pack": {"r_px": R_PACK_PX, "prune_strictly_gt_px": 2},
        "arms": {
            "null_pr": "uniform random order over footprint pruned >2 px off visible",
            "halo_pr": "ascending distance to visible faults (proximity-first; ring 3-8 px fills first)",
            "ridge_pr": "band-2 Hessian/NMS centrelines, descending line strength, pruned",
            "h8_pr": "tip+relay corridors + ridge concordance (corridors.py), pruned",
            "ridge_nopr": "x2 reproduction control: ridge centrelines, no prune (candidates = ridge_ok & ~visible)",
        },
        "summary": summary,
        "paired": compare,
        "reproduction_check_ridge_nopr_vs_x2": {
            "x2_reference_pooled_DTI": X2_REFERENCE_RIDGE_PACK_44090,
            "this_run_pooled_DTI": summary["ridge_nopr"][str(N_PRIMARY)]["pooled_DTI"],
            "delta": round(repro_delta, 6),
            "pass_abs_delta_lt_1e-3": bool(abs(repro_delta) < 1e-3),
        },
        "selection": {
            "rule": "highest pooled DTI at N=44090 among ridge_pr/h8_pr/halo_pr; budget = that arm's better N",
            "best_arm": best_arm,
            "best_budget": best_budget,
            "best_pooled_DTI": summary[best_arm][str(best_budget)]["pooled_DTI"],
            "gate_paired_vs_ridge_pr": compare[f"{best_arm}_minus_ridge_pr@{N_PRIMARY}"],
        },
        "folds_detail": fold_rows,
        "runtime_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    print("wrote", args.out)
    print(json.dumps(report["selection"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
