#!/usr/bin/env python3
"""S3-B (pre-registration S3, sections 2 to 4): holdout test of H8 (gravity horizontal-gradient ridges).

Arm h8 = 19 bands + [R, S, log1p D] from src/gems53/h8.py (label-free). Everything else is E2's design B.

  Canary   each H8 feature alone, design B, 5 segment folds (gate 0.90, halt on exceedance).
  Stage 1  5 segment folds, the 24 E2 variants on arm h8. Selection: highest pooled DTI above the E2 design-B
           baseline (bands top-q 0.02, 0.010562).
  Stage 2  the 5 E2 spatial folds (template src/blocks.py, seed 53). Reproduces E2's per-fold withheld-pixel counts
           (stop if they differ) and E2's bands baseline per fold (stop if they differ beyond 1e-6).
           Paired per-fold differences of the selected h8 variant against
           (a) the bands baseline and (b) the current holdout best = E2 stage-2 H1 thin_bin_q0p1 (read from JSON).
           Acceptance for (b): lower 95% bound (t, df 4) > 0.

Writes evidence/s3b_h8_holdout.json. Labels: HOLDOUT-DTI (evaluator gems53.core.dti v1.0.0), never organizer scores.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import (  # noqa: E402
    buffer_zone,
    load_inputs,
    load_template_module,
    segment_folds,
)
from gems53.h8 import h8_feature_matrix  # noqa: E402
from exp1_leakage_canary import separability  # noqa: E402
from exp2_holdout_arms import predict_chunked  # noqa: E402
from e2_leakfree_holdouts import (  # noqa: E402
    BASE_KEY, BLOCK_PX, K_FOLDS, N_NEG, SEED, T_CRIT_DF4, all_variants, ci, hgb, pooled_from, variants_for,
)

E2 = ROOT / "evidence" / "e2_leakfree_holdouts.json"
BASE_DTI = 0.010562
MAX_CANARY = 0.90


def fold_matrix(inp, h8_fp):
    return np.column_stack([inp.feats, h8_fp]).astype(np.float32)


def fit_predict(F, inp, visible, hidden, rng):
    """Design-B fit for one fold: positives = visible outside 10 px buffer; negatives = footprint not visible."""
    buf = buffer_zone(hidden, 10)
    pos_rows = inp.fp_idx[visible & ~buf & inp.fp]
    neg_pool = inp.fp_idx[inp.fp & ~visible]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = hgb()
    model.fit(F[rows], y)
    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, F)
    p_full[visible] = 0.0
    return p_full, {"pos": int(pos_rows.size), "neg": int(neg_rows.size)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "s3b_h8_holdout.json"))
    args = ap.parse_args()
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fp_px = int(inp.fp.sum())
    with rasterio.open(dd / "training_features.tif") as src:
        raw13 = src.read(13)                          # band 13 = isostatic gravity anomaly (label-free)
    h8_fp, R_full, thr = h8_feature_matrix(raw13, inp.fp)
    del raw13
    F = fold_matrix(inp, h8_fp)
    print(f"H8 ridge threshold |grad g| (90th pct, footprint) = {thr:.6g}; ridge px in footprint = {int(R_full[inp.fp].sum())}",
          flush=True)
    report = {
        "experiment": "S3-B H8 gravity-gradient ridge holdout (pre-registration S3, sections 2-4)",
        "started_utc": started,
        "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments and spatial blocks; NOT organizer-scored)",
        "evaluator": {"name": "gems53.core.dti", "version": "1.0.0"},
        "design": "B (DEV-1): positives = visible outside 10 px buffer; negatives = footprint and not visible",
        "h8": {"band": 13, "threshold_abs_grad": thr, "ridge_px_footprint": int(R_full[inp.fp].sum()),
               "features": ["R ridge 0/1", "S |grad g| on ridge", "log1p(min(D,60))"], "pct": 90, "border_px": 3},
    }

    # ---------------- canary on the H8 features alone (design B, 5 segment folds)
    fold_grid, n_seg, L = segment_folds(inp.cat, K=K_FOLDS, seed=SEED)
    bg = inp.fp & ~inp.cat
    crng = np.random.default_rng(SEED + 1000)
    canary = []
    names = ["R", "S", "log1pD"]
    for k in range(K_FOLDS):
        hidden = inp.cat & (fold_grid == k)
        for j, nm in enumerate(names):
            col = h8_fp[:, j]
            row = separability(col[hidden[inp.fp]], col[bg[inp.fp]], crng)
            canary.append({"fold": k, "feature": nm, **row})
    sep = {nm: max(r["separability"] for r in canary if r["feature"] == nm) for nm in names}
    flag = {nm: ("pass" if sep[nm] <= MAX_CANARY else "LEAK_SUSPECT") for nm in names}
    report["canary_h8_design_B"] = {"gate": MAX_CANARY, "rows": canary, "max_separability": sep, "flag": flag}
    print("canary max separability:", sep, flush=True)
    if any(v != "pass" for v in flag.values()):
        report["status"] = "HALTED: LEAK_SUSPECT on an H8 feature (pre-registered halt)"
        Path(args.out).write_text(json.dumps(report, indent=2, default=str))
        print(report["status"], flush=True)
        return 2

    # ---------------- stage 1: segment folds, arm h8, 24 variants
    variants = all_variants()
    per_variant = {name: [] for name, _, _ in variants}
    rng = np.random.default_rng(SEED)              # same generator start as E2's arm loop
    seg_meta = []
    for k in range(K_FOLDS):
        t1 = time.time()
        hidden = inp.cat & (fold_grid == k)
        visible = inp.cat & (fold_grid != k)
        p_full, cnt = fit_predict(F, inp, visible, hidden, rng)
        res = variants_for(p_full, inp.fp & ~visible, hidden, inp, fp_px, variants)
        for name in res:
            per_variant[name].append(res[name])
        seg_meta.append(dict(fold=k, withheld_px=int(hidden.sum()), **cnt, seconds=round(time.time() - t1, 1)))
        print(f"[s1 h8] fold {k}: top_q0p02 {res['top_q0p02']['DTI']:.6f}  thin_bin_q0p1 {res['thin_bin_q0p1']['DTI']:.6f} "
              f"({seg_meta[-1]['seconds']}s)", flush=True)
        del p_full
    table = {}
    for name, folds in per_variant.items():
        pooled, P = pooled_from(folds)
        m, half, ci_ = ci([f["DTI"] for f in folds])
        table[name] = dict(pooled_DTI=round(float(pooled), 6), per_fold_DTI=[round(f["DTI"], 6) for f in folds],
                           CI95_t_df4_on_fold_mean=ci_, pooled_TP_w=round(P["TP_w"], 4),
                           pooled_FP_w=round(P["FP_w"], 4), pooled_FN_w=round(P["FN_w"], 4))
    qualifying = sorted(([n, v["pooled_DTI"]] for n, v in table.items() if v["pooled_DTI"] > BASE_DTI),
                        key=lambda t: -t[1])
    sel_name = qualifying[0][0] if qualifying else None
    report["stage1"] = {"folds": seg_meta, "variants_h8": table, "baseline_E2_design_B": BASE_DTI,
                        "qualifying": qualifying, "selected": sel_name,
                        "warning": "stage-1 selection on the same folds; optimistic by construction"}
    print("stage 1 selected:", sel_name, flush=True)
    if sel_name is None:
        report["status"] = "STAGE 1: no h8 variant above the E2 baseline; stage 2 not run (negative)"
        Path(args.out).write_text(json.dumps(report, indent=2, default=str))
        return 0

    # ---------------- stage 2: spatial folds (E2 partition, E2 baseline reproduced)
    e2 = json.loads(E2.read_text())
    e2_sp = e2["spatial_confirmation"]
    blocks = load_template_module("blocks", "/tmp/gems-template")
    shape = (inp.H, inp.W)
    tbl = blocks.block_table(shape, BLOCK_PX, valid=inp.fp, labels=inp.cat)
    fold_of = blocks.assign_folds(tbl, n_folds=K_FOLDS, seed=SEED, mode="contiguous")
    bid = blocks.block_id_map(shape, BLOCK_PX)
    cents = ndimage.center_of_mass(inp.cat, L, index=np.arange(1, L.max() + 1))
    seg_fold = np.array([fold_of[int(bid[int(round(y)), int(round(x))])] for (y, x) in cents], dtype=np.int64)
    sp_grid = np.full(inp.cat.shape, -1, dtype=np.int8)
    m_ = L > 0
    sp_grid[m_] = seg_fold[L[m_] - 1].astype(np.int8)
    kind = "top" if sel_name.startswith("top_q") else ("thin_p" if sel_name.startswith("thin_p") else "thin_bin")
    sel_q = float(sel_name.rsplit("_q", 1)[1].replace("p", "."))
    rng_b = np.random.default_rng(SEED)
    rng_s = np.random.default_rng(SEED)
    Fb = inp.feats
    rows = []
    for k in range(K_FOLDS):
        hidden = inp.cat & (sp_grid == k)
        visible = inp.cat & (sp_grid != k)
        e2_row = e2_sp["per_fold"][k]
        if int(hidden.sum()) != int(e2_row["withheld_px"]):
            raise SystemExit(f"partition mismatch on spatial fold {k}: {int(hidden.sum())} vs E2 {e2_row['withheld_px']}")
        p_b, _ = fit_predict(Fb, inp, visible, hidden, rng_b)
        res_b = variants_for(p_b, inp.fp & ~visible, hidden, inp, fp_px, [("baseline", "top", 0.02)])
        del p_b
        p_s, _ = fit_predict(F, inp, visible, hidden, rng_s)
        res_s = variants_for(p_s, inp.fp & ~visible, hidden, inp, fp_px, [("selected", kind, sel_q)])
        del p_s
        if abs(res_b["baseline"]["DTI"] - e2_row["baseline"]["DTI"]) > 1e-6:
            raise SystemExit(f"E2 baseline not reproduced on spatial fold {k}: "
                             f"{res_b['baseline']['DTI']} vs {e2_row['baseline']['DTI']}")
        rows.append(dict(fold=k, withheld_px=int(hidden.sum()), baseline=res_b["baseline"], selected=res_s["selected"],
                         h1_best_E2=e2_row["selected"]["DTI"]))
        print(f"[s2] fold {k}: baseline {res_b['baseline']['DTI']:.6f} (E2 {e2_row['baseline']['DTI']:.6f}) | "
              f"h8 {sel_name} {res_s['selected']['DTI']:.6f} | H1 best (E2) {e2_row['selected']['DTI']:.6f}", flush=True)

    def paired(a_key, b_key):
        d = np.array([r[a_key]["DTI"] - r[b_key]["DTI"] for r in rows]) if b_key != "h1_best_E2" else \
            np.array([r["selected"]["DTI"] - r["h1_best_E2"] for r in rows])
        m = float(d.mean())
        half = float(T_CRIT_DF4 * d.std(ddof=1) / np.sqrt(len(d)))
        return {"mean_fold_diff": round(m, 6), "CI95": [round(m - half, 6), round(m + half, 6)],
                "per_fold_diff": [round(float(x), 6) for x in d], "lower_bound_above_0": bool(m - half > 0)}

    pooled_sel, Ps = pooled_from([r["selected"] for r in rows])
    pooled_base, Pb = pooled_from([r["baseline"] for r in rows])
    pooled_h1 = float(e2_sp["selected_result"]["pooled_DTI"])
    pooled_h1_base = float(e2_sp["baseline"]["pooled_DTI"])
    report["stage2"] = {
        "folds": rows,
        "pooled_DTI": {"h8_selected": round(float(pooled_sel), 6), "bands_baseline": round(float(pooled_base), 6),
                       "E2_H1_thin_bin_q0p1_best": round(pooled_h1, 6), "E2_bands_baseline": round(pooled_h1_base, 6)},
        "withheld_positives_total": int(sum(r["withheld_px"] for r in rows)),
        "a_selected_minus_bands_baseline": paired("selected", "baseline"),
        "b_selected_minus_current_best_H1": paired("selected", "h1_best_E2"),
    }
    b_ok = report["stage2"]["b_selected_minus_current_best_H1"]["lower_bound_above_0"]
    report["verdict"] = {
        "rule": "accept as beating the holdout best iff the 95% lower bound of (b) > 0 (pre-registration section 4)",
        "beats_holdout_best": bool(b_ok),
        "label": "POSITIVE (holdout)" if b_ok else "NEGATIVE (holdout)",
    }
    report["status"] = "COMPLETED"
    report["runtime_s"] = round(time.time() - t0, 1)
    Path(args.out).write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({"stage1_selected": sel_name, "pooled": report["stage2"]["pooled_DTI"],
                      "b": report["stage2"]["b_selected_minus_current_best_H1"], "verdict": report["verdict"]},
                     indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
