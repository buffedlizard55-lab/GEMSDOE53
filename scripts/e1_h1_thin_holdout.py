#!/usr/bin/env python3
"""Experiment E1 (pre-registered in docs/research/preregistration-2026-10-08.md, section 4).

Exploration on the segment folds of exp2 (seed 53, 5 folds, 1 km buffer, pooled DTI).

Arms        : bands (19 label-free bands), h1 (bands + H1 segment-exact distance).
Variants    : top-q (q in 0.005..0.05), M1 thinned with value p or bin (q in 0.02, 0.05, 0.10).
Reproduction: the bands top-q values must equal evidence/exp2_holdout_arms.json; a mismatch stops the run.
Canary      : the H1 feature alone on withheld positives vs buffered background (separability gate 0.90).
Parity      : core.dti vs the shared template metric (src/metrics.py) on fold 0, bands top-q 0.02.

Writes evidence/e1_h1_thin_holdout.json. Usage:
    python scripts/e1_h1_thin_holdout.py --data-dir /tmp/gems53-data --template-root /tmp/gems-template
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import (  # noqa: E402
    buffer_zone,
    dti,
    load_inputs,
    load_template_module,
    segment_exact_distance_grid,
    segment_folds,
    thin_emission,
)
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402
from exp1_leakage_canary import separability  # noqa: E402

K_FOLDS = 5
SEED = 53
T_CRIT_DF4 = 2.776
N_NEG = 300_000
TOPQ = [0.005, 0.0073, 0.01, 0.02, 0.03, 0.05]
THIN_Q = [0.02, 0.05, 0.10]
EXP2_EXPECTED = {"0.005": 0.021681, "0.0073": 0.025063, "0.01": 0.027919, "0.02": 0.035233}  # evidence/exp2
CURRENT_BEST_KEY = ("bands", "top", 0.02)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ci_from_folds(per_fold):
    m = float(np.mean(per_fold))
    half = float(T_CRIT_DF4 * np.std(per_fold, ddof=1) / np.sqrt(len(per_fold)))
    return [round(m - half, 6), round(m + half, 6)], round(m, 6), round(half, 6)


parity_hook: dict = {}


def run_arm(arm, inp, fold_grid, L, rng, canary_rng):
    """Fit one model per fold and return {variant_key: {"TP_w","FP_w","FN_w","DTI","emitted","kept"}} per fold."""
    per_fold = []
    canary_rows = []
    for k in range(K_FOLDS):
        t1 = time.time()
        hidden = inp.cat & (fold_grid == k)
        visible = inp.cat & (fold_grid != k)
        buf = buffer_zone(hidden, 10)
        if arm == "bands":
            F_all = inp.feats
        else:
            h1 = segment_exact_distance_grid(visible, L)
            F_all = np.column_stack([inp.feats, h1[inp.fp]]).astype(np.float32)
            # canary: H1 feature alone, withheld positives vs buffered background (never trained on)
            bg = inp.fp & ~inp.cat & ~buf
            canary_rows.append({"fold": k, **separability(h1[hidden & inp.fp], h1[bg], canary_rng),
                                "median_pos": float(np.median(h1[hidden & inp.fp])),
                                "median_bg": float(np.median(h1[bg]))})
            del h1
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
        p_full[visible] = 0.0                       # pixel-exact mask of visible faults (as in exp2)
        cand = inp.fp & ~visible
        fold_res = {}
        for q in TOPQ:
            emis = top_q_emission(p_full, cand, q, inp.fp.sum())
            r = dti(emis, hidden)
            fold_res[("top", q)] = dict(TP_w=r["TP_w"], FP_w=r["FP_w"], FN_w=r["FN_w"], DTI=r["DTI"],
                                        emitted=int(np.count_nonzero(emis)), kept=None)
        for q in THIN_Q:
            for value in ("p", "bin"):
                emis, kept, nsel = thin_emission(p_full, cand, q, int(inp.fp.sum()), value=value)
                r = dti(emis, hidden)
                fold_res[("thin_" + value, q)] = dict(TP_w=r["TP_w"], FP_w=r["FP_w"], FN_w=r["FN_w"],
                                                      DTI=r["DTI"], emitted=int(np.count_nonzero(emis)),
                                                      kept=kept, selected=nsel)
        fold_res["_meta"] = dict(fold=k, withheld_px=int(hidden.sum()),
                                 withheld_segments=int(len(np.unique(L[hidden]))), train_pos=int(pos_rows.size),
                                 train_neg=int(neg_rows.size), seconds=round(time.time() - t1, 1))
        per_fold.append(fold_res)
        print(f"[{arm}] fold {k} done in {fold_res['_meta']['seconds']}s: top-0.02 DTI="
              f"{fold_res[('top', 0.02)]['DTI']:.4f}", flush=True)
        if arm == "bands" and k == 0:
            parity_hook["emission"] = top_q_emission(p_full, cand, 0.02, inp.fp.sum())
            parity_hook["hidden"] = hidden
        del p_full, model
    return per_fold, canary_rows


def summarise(per_fold):
    out = {}
    keys = [k for k in per_fold[0].keys() if k != "_meta"]
    for key in keys:
        P = {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0}
        ds = []
        emitted, kept = [], []
        for fr in per_fold:
            r = fr[key]
            for kk in P:
                P[kk] += r[kk]
            ds.append(r["DTI"])
            emitted.append(r["emitted"])
            if r.get("kept") is not None:
                kept.append(r["kept"])
        pooled = P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9)
        ci, m, half = ci_from_folds(ds)
        name = f"{key[0]}_q{str(key[1]).replace('.', 'p')}"
        out[name] = dict(variant=key[0], q=key[1], pooled_DTI=round(float(pooled), 6),
                         per_fold_DTI=[round(float(x), 6) for x in ds], per_fold_mean=m,
                         CI95_t_df4_on_fold_mean=ci, half_width=half,
                         pooled_TP_w=round(P["TP_w"], 4), pooled_FP_w=round(P["FP_w"], 4),
                         pooled_FN_w=round(P["FN_w"], 4),
                         mean_emitted_px=int(np.mean(emitted)),
                         mean_kept_dots=(int(np.mean(kept)) if kept else None))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template-root", default="/tmp/gems-template")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "e1_h1_thin_holdout.json"))
    args = ap.parse_args()
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fold_grid, n_seg, L = segment_folds(inp.cat, K=K_FOLDS, seed=SEED)
    report = {
        "experiment": "E1 (pre-registered): H1 segment-exact + M1 thinning, segment folds seed 53",
        "started_utc": started,
        "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments; NOT organizer-scored)",
        "evaluator": {"name": "gems53.core.dti", "version": "1.0.0",
                      "formula": "TI = TPw/(TPw + 0.2 FPw + 0.8 FNw + eps); triangular kernel R=3 px (300 m)"},
        "inputs": {"training_features.tif": sha256(dd / "training_features.tif"),
                   "labels.tif": sha256(dd / "labels.tif"),
                   "sample_submission.tif": sha256(dd / "sample_submission.tif")},
        "footprint_px": int(inp.fp.sum()), "known_fault_px": int(inp.cat.sum()), "segments": int(n_seg),
        "folds": {"K": K_FOLDS, "seed": SEED, "buffer_px": 10},
        "grid": {"topq": TOPQ, "thin_q": THIN_Q, "thin_values": ["p", "bin"]},
        "arms": {},
    }
    rng = np.random.default_rng(SEED)              # fresh generator per arm -> identical negatives per fold
    canary_rng = np.random.default_rng(SEED + 1000)  # separate: canary sampling must not shift negative draws
    # ---- arm 1: bands (reproduction gate first) ----
    per_fold_b, _ = run_arm("bands", inp, fold_grid, L, rng, canary_rng)
    summ_b = summarise(per_fold_b)
    report["arms"]["bands"] = summ_b
    repro = {}
    ok = True
    for q_str, expect in EXP2_EXPECTED.items():
        got = summ_b[f"top_q{q_str.replace('.', 'p')}"]["pooled_DTI"]
        repro[q_str] = {"expected_exp2": expect, "got": got, "match": abs(got - expect) < 1e-6}
        ok = ok and repro[q_str]["match"]
    report["reproduction_check_vs_exp2"] = {"pass": ok, "values": repro}
    if not ok:
        report["status"] = "STOPPED: reproduction check failed (pre-registered stop rule)"
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
        print("REPRODUCTION FAILED", json.dumps(repro, indent=2))
        return 2
    # ---- metric parity with the shared template (fold 0, bands top-q 0.02 emission) ----
    try:
        tm = load_template_module("metrics", args.template_root)
        em0, hid0 = parity_hook["emission"], parity_hook["hidden"]
        mine = dti(em0, hid0)["DTI"]
        theirs = tm.compute_distance_weighted_tversky(em0, hid0)
        theirs = float(theirs["DTI"]) if isinstance(theirs, dict) else float(theirs)
        report["metric_parity_vs_template"] = {"template_file": "src/metrics.py", "fold": 0,
                                               "core_dti": round(mine, 9), "template_dti": round(theirs, 9),
                                               "abs_diff": abs(mine - theirs), "pass": abs(mine - theirs) < 1e-6}
        print("parity", report["metric_parity_vs_template"], flush=True)
    except FileNotFoundError as exc:
        report["metric_parity_vs_template"] = {"pass": None, "note": str(exc)}
    # ---- arm 2: H1 ----
    rng = np.random.default_rng(SEED)
    per_fold_h, canary_rows = run_arm("h1", inp, fold_grid, L, rng, canary_rng)
    report["arms"]["h1"] = summarise(per_fold_h)
    report["canary_H1_feature_alone"] = {
        "description": "H1 distance (segment-exact, visible faults only) on withheld positives vs buffered background",
        "per_fold": canary_rows,
        "separability_mean": round(float(np.mean([r["separability"] for r in canary_rows])), 6),
        "separability_max": round(float(np.max([r["separability"] for r in canary_rows])), 6),
        "gate": 0.90,
        "flag": "LEAK_SUSPECT" if max(r["separability"] for r in canary_rows) > 0.90 else "pass",
    }
    # ---- pre-registered selection (section 4 of the pre-registration) ----
    best_key = None
    best_val = -1.0
    baseline = report["arms"]["bands"]["top_q0p02"]["pooled_DTI"]
    qualifying = []
    for arm in ("bands", "h1"):
        for name, row in report["arms"][arm].items():
            if row["pooled_DTI"] > baseline:
                qualifying.append({"arm": arm, "variant": name, "pooled_DTI": row["pooled_DTI"]})
            if row["pooled_DTI"] > best_val:
                best_val, best_key = row["pooled_DTI"], (arm, name)
    report["selection"] = {
        "rule": "highest pooled DTI among variants above the current holdout best (bands top q=0.02)",
        "current_holdout_best": {"arm": "bands", "variant": "top_q0p02", "pooled_DTI": baseline},
        "qualifying_variants": qualifying,
        "selected_for_E2": (None if not qualifying else
                            {"arm": best_key[0], "variant": best_key[1], "pooled_DTI": best_val}),
        "n_variants_scored": len(report["arms"]["bands"]) + len(report["arms"]["h1"]),
        "warning": "selection is on the same folds, so the E1 gain is optimistic; E2 is the fair test",
    }
    report["runtime_s"] = round(time.time() - t0, 1)
    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["status"] = "COMPLETED"
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2))
    print("wrote", args.out)
    print(json.dumps(report["selection"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
