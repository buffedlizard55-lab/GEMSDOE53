#!/usr/bin/env python3
"""Session-2 experiments S2-E1 (leakage canary) + S2-E2 (design-B holdout) for lane C1.

Pre-registration: docs/research/preregistration-2026-10-09-session2.md (sections 3-4, DEV-C1-1).
Design B (identical to session-1 E2, DEV-1): positives = visible faults outside the 10 px buffer;
negatives = every footprint pixel that is NOT a visible fault (300k sampled per fold, seed 53,
identical across arms per fold). Visible faults are masked pixel-exactly in every emission.

Arms:
  bands : the 19 label-free stack bands (baseline re-run in the same run)
  bc1   : 19 bands + 14 C1 conductivity-magnetic coherence features (NO catalogue feature)

S2-E1 canary: each of the 14 C1 features alone, design B, per fold, separability = max(AUC, 1-AUC);
flag >= 0.90. Background = full non-fault footprint (fp and not any known fault).
S2-E2 stage 1: pooled DTI + 95% t CI (df 4) for 11 variants per arm; selection = highest pooled DTI
among bc1 variants above the SAME-RUN bands:top_q0p02 pooled DTI.
S2-E2 stage 2: spatial contiguous super-regions (template src/blocks.py), paired per-fold difference
of selected vs baseline, accept iff the 95% t-interval lower bound > 0.

Writes evidence/s2_c1_holdout.json (never touches session-1 receipts).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from gems53.core import (  # noqa: E402
    buffer_zone,
    dti,
    load_inputs,
    load_template_module,
    segment_folds,
    thin_emission,
)
from gems53.c1 import build_c1_features  # noqa: E402
from exp2_holdout_arms import predict_chunked, top_q_emission  # noqa: E402
from e2_leakfree_holdouts import hgb, pooled_from, ci, T_CRIT_DF4, _jsonable  # noqa: E402
from exp1_leakage_canary import separability  # noqa: E402

K_FOLDS = 5
SEED = 53
N_NEG = 300_000
TOPQ = [0.005, 0.01, 0.02, 0.03, 0.05]
THIN_Q = [0.02, 0.05, 0.10]
BASE_KEY = "top_q0p02"
BLOCK_PX = 512


def all_variants():
    v = [(f"top_q{str(q).replace('.', 'p')}", "top", q) for q in TOPQ]
    for q in THIN_Q:
        v.append((f"thin_p_q{str(q).replace('.', 'p')}", "thin_p", q))
        v.append((f"thin_bin_q{str(q).replace('.', 'p')}", "thin_bin", q))
    return v


def variants_for(p_full, cand, hidden, fp_px, want):
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


def fold_features(inp, Xc1, arm):
    if arm == "bands":
        return inp.feats
    return np.ascontiguousarray(np.column_stack([inp.feats, Xc1]).astype(np.float32))


def fit_predict_fold(inp, Xc1, visible, hidden, arm, rng):
    buf = buffer_zone(hidden, 10)
    pos_mask = visible & ~buf & inp.fp
    neg_mask = inp.fp & ~visible
    F = fold_features(inp, Xc1, arm)
    pos_rows = inp.fp_idx[pos_mask]
    neg_pool = inp.fp_idx[neg_mask]
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows_tr = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    model = hgb()
    model.fit(F[rows_tr], y)
    p_full = np.zeros((inp.H, inp.W), dtype=np.float32)
    p_full[inp.fp] = predict_chunked(model, F)
    p_full[visible] = 0.0
    return p_full, dict(pos=int(pos_rows.size), neg=int(neg_rows.size))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template-root", default="/tmp/gems-template")
    ap.add_argument("--out", default=str(ROOT / "evidence" / "s2_c1_holdout.json"))
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    fold_list = [0] if args.smoke else list(range(K_FOLDS))
    t0 = time.time()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    dd = Path(args.data_dir)
    inp = load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))
    fp_px = int(inp.fp.sum())

    tc1 = time.time()
    Xc1, c1_names = build_c1_features(inp.feats, inp.fp, inp.fp_idx)
    t_c1 = round(time.time() - tc1, 1)

    report = {
        "experiment": "S2-E1 canary + S2-E2 design-B holdout for lane C1 (bc1 arm)",
        "started_utc": started,
        "label_type": "HOLDOUT-DTI (proxy: withheld known-fault segments; NOT organizer-scored)",
        "evaluator": {"name": "gems53.core.dti", "version": "1.0.0",
                      "template_parity": "verified in session-1 E1 (abs diff 1.3e-13 vs template src/metrics.py)"},
        "design": "B: positives = visible outside 10 px buffer; negatives = footprint and not visible",
        "preregistration": "docs/research/preregistration-2026-10-09-session2.md",
        "deviation": "DEV-C1-1 (energy-gated agreement)",
        "c1_features": c1_names,
        "c1_build_seconds": t_c1,
        "footprint_px": fp_px,
    }
    L_all, _ = ndimage.label(inp.cat, structure=np.ones((3, 3), dtype=int))

    # ------------------------------------------------------------------ S2-E1 canary (design B)
    fold_grid, n_seg, L = segment_folds(inp.cat, K=K_FOLDS, seed=SEED)
    canary_rng = np.random.default_rng(SEED + 1000)
    bgB = inp.fp & ~inp.cat
    canary_rows = []
    for k in fold_list:
        hidden = inp.cat & (fold_grid == k)
        pos_idx = inp.fp_idx[hidden & inp.fp]
        neg_idx = inp.fp_idx[bgB]
        for j, nm in enumerate(c1_names):
            col = Xc1[:, j]
            row = separability(col[pos_idx], col[neg_idx], canary_rng)
            canary_rows.append({"fold": k, "feature": nm, **row})
        print(f"[canary] fold {k} done ({len(c1_names)} features)", flush=True)
    sep_by_feat = {}
    for nm in c1_names:
        vals = [r["separability"] for r in canary_rows if r["feature"] == nm and r["separability"] is not None]
        sep_by_feat[nm] = round(float(np.max(vals)), 6) if vals else None
    max_sep = max(v for v in sep_by_feat.values() if v is not None)
    report["canary_S2_E1"] = {
        "gate": 0.90,
        "background": "full non-fault footprint (fp and not any known fault)",
        "positives": "withheld fold segments (visible masked out)",
        "max_separability_per_feature": sep_by_feat,
        "max_over_all_features": round(max_sep, 6),
        "flag": "pass" if max_sep <= 0.90 else "LEAK_SUSPECT",
        "n_folds": len(fold_list),
    }
    if args.smoke:
        report["smoke"] = True

    # ------------------------------------------------------------------ S2-E2 stage 1 (segment folds)
    variants = all_variants()
    per_variant_folds = {(arm, name): [] for arm in ("bands", "bc1") for name, _, _ in variants}
    seg_meta = []
    for arm in ("bands", "bc1"):
        rng = np.random.default_rng(SEED)  # identical negatives across arms per fold
        for k in fold_list:
            t1 = time.time()
            hidden = inp.cat & (fold_grid == k)
            visible = inp.cat & (fold_grid != k)
            p_full, counts = fit_predict_fold(inp, Xc1, visible, hidden, arm, rng)
            cand = inp.fp & ~visible
            res = variants_for(p_full, cand, hidden, fp_px, variants)
            for name in res:
                per_variant_folds[(arm, name)].append(res[name])
            seg_meta.append(dict(arm=arm, fold=k, withheld_px=int(hidden.sum()),
                                 train_pos=counts["pos"], train_neg=counts["neg"],
                                 seconds=round(time.time() - t1, 1)))
            print(f"[stage1 {arm}] fold {k}: {BASE_KEY} DTI {res[BASE_KEY]['DTI']:.6f} "
                  f"({seg_meta[-1]['seconds']}s)", flush=True)
            del p_full
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
    report["segment_folds"] = {"K": K_FOLDS, "seed": SEED, "buffer_px": 10, "segments": int(n_seg),
                               "per_fold_meta": seg_meta, "variants": table}
    base = table[f"bands:{BASE_KEY}"]
    report["baseline_same_run"] = {"arm": "bands", "variant": BASE_KEY, "pooled_DTI": base["pooled_DTI"],
                                   "CI95": base["CI95_t_df4_on_fold_mean"],
                                   "withheld_positives": int(sum(m["withheld_px"] for m in seg_meta[:K_FOLDS]))}
    qualifying = [{"key": k, "pooled_DTI": v["pooled_DTI"]} for k, v in table.items()
                  if v["arm"] == "bc1" and v["pooled_DTI"] > base["pooled_DTI"]]
    selected = None
    if qualifying:
        best = max(qualifying, key=lambda d: d["pooled_DTI"])
        selected = table[best["key"]]
    report["segment_selection"] = {
        "rule": "highest pooled DTI among bc1 variants above the same-run bands:top_q0p02",
        "qualifying": qualifying, "n_variants_scored": len(table),
        "selected": (None if selected is None else dict(arm=selected["arm"], variant=selected["variant"],
                                                        pooled_DTI=selected["pooled_DTI"])),
        "warning": "selection on the same folds; stage 2 is the fair test",
    }

    # ------------------------------------------------------------------ S2-E2 stage 2 (spatial)
    if selected is None:
        report["spatial_confirmation"] = {"status": "NOT RUN: no bc1 variant qualified in stage 1"}
    else:
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
        sel_kind = ("top" if sel_name.startswith("top_q") else
                    ("thin_p" if sel_name.startswith("thin_p") else "thin_bin"))
        sel_q = float(sel_name.rsplit("_q", 1)[1].replace("p", "."))
        rows = []
        rng_b = np.random.default_rng(SEED)
        rng_s = np.random.default_rng(SEED)
        for k in fold_list:
            t1 = time.time()
            hidden = inp.cat & (sp_grid == k)
            visible = inp.cat & (sp_grid != k)
            p_b, _ = fit_predict_fold(inp, Xc1, visible, hidden, "bands", rng_b)
            res_b = variants_for(p_b, inp.fp & ~visible, hidden, fp_px, [("baseline", "top", 0.02)])
            p_s, n_s = fit_predict_fold(inp, Xc1, visible, hidden, sel_arm, rng_s)
            res_s = variants_for(p_s, inp.fp & ~visible, hidden, fp_px, [("selected", sel_kind, sel_q)])
            rows.append(dict(fold=k, withheld_px=int(hidden.sum()),
                             withheld_segments=int(len(np.unique(L_all[hidden]))),
                             baseline=res_b["baseline"], selected=res_s["selected"]))
            print(f"[stage2] fold {k}: baseline {res_b['baseline']['DTI']:.6f} "
                  f"selected({sel_arm} {sel_name}) {res_s['selected']['DTI']:.6f} "
                  f"({round(time.time() - t1, 1)}s)", flush=True)
            del p_b, p_s
        pb, Pb = pooled_from([r["baseline"] for r in rows])
        ps, Ps = pooled_from([r["selected"] for r in rows])
        d = np.array([r["selected"]["DTI"] - r["baseline"]["DTI"] for r in rows])
        m = float(d.mean())
        half = float(T_CRIT_DF4 * d.std(ddof=1) / np.sqrt(len(d)))
        lower = m - half
        report["spatial_confirmation"] = dict(
            status="COMPLETED",
            partition={k: part[k] for k in part if k != "per_fold_blocks"} if isinstance(part, dict) else str(part),
            selected=dict(arm=sel_arm, variant=sel_name),
            baseline=dict(name="bands top_q0p02 (design B, bands model, same run)", pooled_DTI=round(float(pb), 6),
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
        )
    report["status"] = "COMPLETED"
    report["runtime_s"] = round(time.time() - t0, 1)
    report["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    Path(args.out).write_text(json.dumps(report, indent=2, default=_jsonable))
    print("wrote", args.out)
    print(json.dumps({"canary": report["canary_S2_E1"]["flag"],
                      "baseline": report["baseline_same_run"],
                      "selection": report["segment_selection"]["selected"],
                      "spatial": report["spatial_confirmation"].get("acceptance")}, indent=2, default=_jsonable))
    return 0


if __name__ == "__main__":
    sys.exit(main())
