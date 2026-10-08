#!/usr/bin/env python3
"""Experiment E2 under design B (pre-registered amendment DEV-1, docs/research/preregistration-2026-10-08.md).

Design B (leak-free with respect to withheld labels):
  positives = visible faults outside the 10 px buffer (pixel-exact visible mask);
  negatives = every footprint pixel that is NOT a visible fault (withheld faults, buffer and background are all
              candidates, so the training pool does not depend on withheld locations).
  300k negatives per fold, default_rng(53) per arm (identical negatives across arms per fold), HGB as in exp2.

Stage 1  (segment folds, seed 53, 5 folds): all 24 variants for arms bands and h1 -> pooled DTI, CI.
         Selection: highest pooled DTI among variants above the design-B baseline (bands top-q 0.02).
Canary   (design B): each of the 19 bands and the H1 feature alone, withheld positives vs full non-fault background.
Stage 2  (spatial contiguous super-regions from the shared template src/blocks.py, 5 folds, 10 px buffer):
         baseline (bands top-q 0.02) vs the Stage-1 selection, paired per-fold differences, t-interval (df = 4).
         Accept iff the lower bound of the 95% interval is above 0.

Writes evidence/e2_leakfree_holdouts.json.
"""
from __future__ import annotations

import argparse
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
N_NEG = 300_000
T_CRIT_DF4 = 2.776
TOPQ = [0.005, 0.0073, 0.01, 0.02, 0.03, 0.05]
THIN_Q = [0.02, 0.05, 0.10]
BASE_KEY = "top_q0p02"
BLOCK_PX = 512
BAND_NAMES = None  # filled from inputs


def _jsonable(o):
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def hgb():
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                          l2_regularization=1.0, random_state=0)


def fold_inputs(inp, visible, hidden, L, arm):
    """Design-B training rows and feature matrix for one fold."""
    buf = buffer_zone(hidden, 10)
    pos_mask = visible & ~buf & inp.fp
    neg_mask = inp.fp & ~visible                     # design B: everything not visible
    if arm == "bands":
        F = inp.feats
    else:
        h1 = segment_exact_distance_grid(visible, L)
        F = np.column_stack([inp.feats, h1[inp.fp]]).astype(np.float32)
        del h1
    return F, inp.fp_idx[pos_mask], inp.fp_idx[neg_mask], buf


def variants_for(p_full, cand, hidden, inp, fp_px, want):
    """Score the requested variants on one fold. `want` is a list of (name, kind, q)."""
    out = {}
    for name, kind, q in want:
        if kind == "top":
            emis = top_q_emission(p_full, cand, q, fp_px)
            kept = None
        else:
            emis, kept, _ = thin_emission(p_full, cand, q, fp_px, value="p" if kind == "thin_p" else "bin")
        r = dti(emis, hidden)
        out[name] = dict(TP_w=r["TP_w"], FP_w=r["FP_w"], FN_w=r["FN_w"], DTI=r["DTI"],
                         emitted=int(np.count_nonzero(emis)), kept=kept)
    return out


def all_variants():
    v = [(f"top_q{str(q).replace('.', 'p')}", "top", q) for q in TOPQ]
    for q in THIN_Q:
        v.append((f"thin_p_q{str(q).replace('.', 'p')}", "thin_p", q))
        v.append((f"thin_bin_q{str(q).replace('.', 'p')}", "thin_bin", q))
    return v


def pooled_from(per_fold_dicts):
    P = {"TP_w": 0.0, "FP_w": 0.0, "FN_w": 0.0}
    for d in per_fold_dicts:
        for k in P:
            P[k] += d[k]
    return P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9), P


def ci(vals):
    vals = np.asarray(vals, dtype=float)
    m = float(vals.mean())
    half = float(T_CRIT_DF4 * vals.std(ddof=1) / np.sqrt(len(vals)))
    return m, half, [round(m - half, 6), round(m + half, 6)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template-root", default="/tmp/gems-template")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "e2_leakfree_holdouts.json"))
    ap.add_argument("--smoke", action="store_true", help="one fold per stage, few bands (code-path test only)")
    ap.add_argument("--stage2-only", action="store_true",
                    help="reuse stage-1 results already in --out and re-run stage 2 (used after the baseline fix)")
    args = ap.parse_args()
    fold_list = [0] if args.smoke else list(range(K_FOLDS))
    band_list = [1, 2] if args.smoke else list(range(1, 20))
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fp_px = int(inp.fp.sum())
    report = {
        "experiment": "E2 under design B (DEV-1): segment-fold selection + spatial-block confirmation",
        "started_utc": started,
        "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments; NOT organizer-scored)",
        "evaluator": {"name": "gems53.core.dti", "version": "1.0.0", "template_parity": "see E1 record"},
        "design": "B: positives = visible outside 10 px buffer; negatives = footprint and not visible",
        "footprint_px": fp_px,
    }
    L_all, _ = ndimage.label(inp.cat, structure=np.ones((3, 3), dtype=int))

    if args.stage2_only:
        prev = json.loads(Path(args.out).read_text())
        report = dict(prev)
        report["stage2_rerun_utc"] = started
        selected = report["segment_selection"]["selected"]
        base = report["segment_folds"]["variants"][f"bands:{BASE_KEY}"]
        fold_grid = None
        if selected is None:
            raise SystemExit("stage 1 selected nothing; nothing to confirm")
        fold_list = list(range(K_FOLDS))
        run_stage2(inp, L_all, selected, args, report, fold_list, started, t0)
        return 0

    # ----------------------------------------------------------- Stage 1: segment folds ------------
    fold_grid, n_seg, L = segment_folds(inp.cat, K=K_FOLDS, seed=SEED)
    report["segment_folds"] = {"K": K_FOLDS, "seed": SEED, "buffer_px": 10, "segments": int(n_seg)}
    variants = all_variants()
    per_variant_folds = {(arm, name): [] for arm in ("bands", "h1") for name, _, _ in variants}
    canary_rows = []
    canary_rng = np.random.default_rng(SEED + 1000)
    seg_meta = []
    for arm in ("bands", "h1"):
        rng = np.random.default_rng(SEED)            # fresh per arm -> identical negatives across arms
        for k in fold_list:
            t1 = time.time()
            hidden = inp.cat & (fold_grid == k)
            visible = inp.cat & (fold_grid != k)
            F, pos_rows, neg_pool_rows, buf = fold_inputs(inp, visible, hidden, L, arm)
            neg_rows = neg_pool_rows[rng.choice(neg_pool_rows.size, min(N_NEG, neg_pool_rows.size), replace=False)]
            rows = np.r_[pos_rows, neg_rows]
            y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
            model = hgb()
            model.fit(F[rows], y)
            p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
            p_full[inp.fp] = predict_chunked(model, F)
            p_full[visible] = 0.0
            cand = inp.fp & ~visible
            res = variants_for(p_full, cand, hidden, inp, fp_px, variants)
            for name in res:
                per_variant_folds[(arm, name)].append(res[name])
            seg_meta.append(dict(arm=arm, fold=k, withheld_px=int(hidden.sum()),
                                 withheld_segments=int(len(np.unique(L[hidden]))),
                                 train_pos=int(pos_rows.size), train_neg=int(neg_rows.size),
                                 seconds=round(time.time() - t1, 1)))
            print(f"[segB {arm}] fold {k}: top_q0p02 DTI {res['top_q0p02']['DTI']:.6f} "
                  f"({seg_meta[-1]['seconds']}s)", flush=True)
            del p_full, model, F
            if arm == "h1":
                # canary for H1 under design B, against the full non-fault background
                h1 = segment_exact_distance_grid(visible, L)
                bgB = inp.fp & ~inp.cat
                canary_rows.append({"fold": k, "feature": "h1_distance",
                                    **separability(h1[hidden & inp.fp], h1[bgB], canary_rng)})
                del h1
    # 19 label-free bands, design B, one canary per band per fold
    band_canary = []
    for k in fold_list:
        hidden = inp.cat & (fold_grid == k)
        bgB = inp.fp & ~inp.cat
        pos_idx = hidden[inp.fp]
        neg_idx = bgB[inp.fp]
        for j in [b - 1 for b in band_list]:
            col = inp.feats[:, j]
            row = separability(col[pos_idx], col[neg_idx], canary_rng)
            band_canary.append({"fold": k, "band": j + 1, **row})
    band_sep = {}
    for j in band_list:
        vals = [r["separability"] for r in band_canary if r["band"] == j and r["separability"] is not None]
        band_sep[j] = float(np.max(vals)) if vals else None
    if args.smoke:
        report["smoke"] = True
    report["canary_design_B"] = {
        "gate": 0.90,
        "bands_max_separability_per_band": band_sep,
        "bands_max_over_all": round(max(v for v in band_sep.values() if v is not None), 6),
        "bands_flag": "pass" if max(v for v in band_sep.values() if v is not None) <= 0.90 else "LEAK_SUSPECT",
        "h1_rows": canary_rows,
        "h1_max_separability": round(float(max(r["separability"] for r in canary_rows)), 6),
        "h1_flag": "pass" if max(r["separability"] for r in canary_rows) <= 0.90 else "LEAK_SUSPECT",
        "background": "full non-fault footprint (fp and not any known fault)",
    }
    # per-variant pooled table
    table = {}
    for (arm, name), folds in per_variant_folds.items():
        pooled, P = pooled_from(folds)
        m, half, ci_ = ci([f["DTI"] for f in folds])
        table[f"{arm}:{name}"] = dict(arm=arm, variant=name, pooled_DTI=round(float(pooled), 6),
                                      per_fold_DTI=[round(f["DTI"], 6) for f in folds],
                                      CI95_t_df4_on_fold_mean=ci_, half_width=round(half, 6),
                                      pooled_TP_w=round(P["TP_w"], 4), pooled_FP_w=round(P["FP_w"], 4),
                                      pooled_FN_w=round(P["FN_w"], 4),
                                      mean_emitted_px=int(np.mean([f["emitted"] for f in folds])),
                                      mean_kept_dots=(int(np.mean([f["kept"] for f in folds]))
                                                      if folds[0]["kept"] is not None else None))
    report["segment_folds"]["per_fold_meta"] = seg_meta
    report["segment_folds"]["variants"] = table
    base = table[f"bands:{BASE_KEY}"]
    report["baseline_design_B"] = {"arm": "bands", "variant": BASE_KEY, "pooled_DTI": base["pooled_DTI"],
                                   "CI95": base["CI95_t_df4_on_fold_mean"],
                                   "withheld_positives": int(sum(m["withheld_px"] for m in seg_meta[:K_FOLDS]))}
    qualifying = [{"key": k, "pooled_DTI": v["pooled_DTI"]} for k, v in table.items()
                  if v["pooled_DTI"] > base["pooled_DTI"]]
    selected = None
    if qualifying:
        best = max(qualifying, key=lambda d: d["pooled_DTI"])
        selected = table[best["key"]]
    report["segment_selection"] = {
        "rule": "highest pooled DTI among variants above the design-B baseline (bands top_q0p02)",
        "qualifying": qualifying, "n_variants_scored": len(table),
        "selected": (None if selected is None else dict(arm=selected["arm"], variant=selected["variant"],
                                                         pooled_DTI=selected["pooled_DTI"])),
        "warning": "selection on the same folds; the confirmation below is the fair test",
    }

    # ----------------------------------------------------------- Stage 2: spatial confirmation ------
    run_stage2(inp, L_all, selected, args, report, fold_list, started, t0)
    return 0


def run_stage2(inp, L_all, selected, args, report, fold_list, started, t0):
    """Stage 2 (pre-registered section 5, DEV-1): spatial contiguous super-regions.

    Baseline = bands top-q 0.02 from the BANDS model, always (not from the selected arm's model).
    Selected = the stage-1 variant from its own arm's model. Both models use the same design-B rules and
    the same negatives per fold (one generator per arm, advanced identically).
    """
    fp_px = int(inp.fp.sum())
    if selected is None:
        report["spatial_confirmation"] = {"status": "NOT RUN: no variant qualified in Stage 1"}
        return
    blocks = load_template_module("blocks", args.template_root)
    shape = (inp.H, inp.W)
    tbl = blocks.block_table(shape, BLOCK_PX, valid=inp.fp, labels=inp.cat)
    fold_of = blocks.assign_folds(tbl, n_folds=K_FOLDS, seed=SEED, mode="contiguous")
    bid = blocks.block_id_map(shape, BLOCK_PX)
    cents = ndimage.center_of_mass(inp.cat, L_all, index=np.arange(1, L_all.max() + 1))
    seg_fold = np.array([fold_of[int(bid[int(round(y)), int(round(x))])] for (y, x) in cents], dtype=np.int64)
    sp_grid = np.full(inp.cat.shape, -1, dtype=np.int8)
    m_ = L_all > 0
    sp_grid[m_] = seg_fold[L_all[m_] - 1].astype(np.int8)
    part = blocks.describe_partition(shape, BLOCK_PX, K_FOLDS, SEED, tbl, fold_of, buffer_px=10,
                                     labels=inp.cat, valid=inp.fp, mode="contiguous")
    sel_arm, sel_name = selected["arm"], selected["variant"]
    sel_kind = ("top" if sel_name.startswith("top_q") else ("thin_p" if sel_name.startswith("thin_p") else "thin_bin"))
    sel_q = float(sel_name.rsplit("_q", 1)[1].replace("p", "."))
    rows = []
    rng_b = np.random.default_rng(SEED)
    rng_s = np.random.default_rng(SEED)
    for k in fold_list:
        t1 = time.time()
        hidden = inp.cat & (sp_grid == k)
        visible = inp.cat & (sp_grid != k)
        p_b, n_b = fit_predict_fold(inp, visible, hidden, L_all, "bands", rng_b)
        res_b = variants_for(p_b, inp.fp & ~visible, hidden, inp, fp_px, [("baseline", "top", 0.02)])
        if sel_arm == "bands":
            p_s, n_s = p_b, n_b
        else:
            p_s, n_s = fit_predict_fold(inp, visible, hidden, L_all, sel_arm, rng_s)
        res_s = variants_for(p_s, inp.fp & ~visible, hidden, inp, fp_px, [("selected", sel_kind, sel_q)])
        rows.append(dict(fold=k, withheld_px=int(hidden.sum()),
                         withheld_segments=int(len(np.unique(L_all[hidden]))),
                         train_pos=int(n_s["pos"]), train_neg=int(n_s["neg"]),
                         baseline=res_b["baseline"], selected=res_s["selected"]))
        print(f"[spatial] fold {k}: baseline(bands top-0.02) {res_b['baseline']['DTI']:.6f} "
              f"selected({sel_arm} {sel_name}) {res_s['selected']['DTI']:.6f} ({round(time.time() - t1, 1)}s)", flush=True)
        del p_b, p_s
    pb, Pb = pooled_from([r["baseline"] for r in rows])
    ps, Ps = pooled_from([r["selected"] for r in rows])
    d = np.array([r["selected"]["DTI"] - r["baseline"]["DTI"] for r in rows])
    m = float(d.mean())
    half = float(T_CRIT_DF4 * d.std(ddof=1) / np.sqrt(len(d)))
    lower = m - half
    report["spatial_confirmation"] = dict(
        status="COMPLETED",
        partition={k: part[k] for k in part if k not in ("per_fold_blocks",)} if isinstance(part, dict) else str(part),
        selected=dict(arm=sel_arm, variant=sel_name),
        baseline=dict(name="bands top_q0p02 (design B, bands model)", pooled_DTI=round(float(pb), 6),
                      pooled_TP_w=round(Pb["TP_w"], 4), pooled_FP_w=round(Pb["FP_w"], 4),
                      pooled_FN_w=round(Pb["FN_w"], 4)),
        selected_result=dict(name=f"{sel_arm} {sel_name}", pooled_DTI=round(float(ps), 6),
                             pooled_TP_w=round(Ps["TP_w"], 4), pooled_FP_w=round(Ps["FP_w"], 4),
                             pooled_FN_w=round(Ps["FN_w"], 4)),
        per_fold=rows,
        paired_difference=dict(mean_fold_diff=round(m, 6), half_width_t_df4=round(half, 6),
                               CI95=[round(lower, 6), round(m + half, 6)]),
        acceptance=dict(rule="accept iff the 95% t-interval lower bound of the paired fold difference is above 0",
                        accepted=bool(lower > 0)),
        withheld_positives_total=int(sum(r["withheld_px"] for r in rows)),
        withheld_segments_total=int(sum(r["withheld_segments"] for r in rows)),
        stage2_code="baseline from bands model (fixed after the first run, see run card)",
    )
    report["status"] = "COMPLETED"
    report["runtime_s"] = round(time.time() - t0, 1)
    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, default=_jsonable))
    print("wrote", args.out, flush=True)
    print(json.dumps({"baseline_B": report["baseline_design_B"], "selection": report["segment_selection"]["selected"],
                      "spatial": report["spatial_confirmation"]["acceptance"]}, indent=2, default=_jsonable))


def fit_predict_fold(inp, visible, hidden, L, arm, rng):
    """Design-B model for one fold and arm. Returns (p_full with visible faults zeroed, counts)."""
    F, pos_rows, neg_pool_rows, buf = fold_inputs(inp, visible, hidden, L, arm)
    neg_rows = neg_pool_rows[rng.choice(neg_pool_rows.size, min(N_NEG, neg_pool_rows.size), replace=False)]
    rows_tr = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = hgb()
    model.fit(F[rows_tr], y)
    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, F)
    p_full[visible] = 0.0
    del F, model
    return p_full, {"pos": int(pos_rows.size), "neg": int(neg_rows.size)}


if __name__ == "__main__":
    sys.exit(main())
