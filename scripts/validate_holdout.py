#!/usr/bin/env python3
"""Score every arm on the spatially-blocked, catalogue-masked folds.  Nothing is promoted here.

Arms (all emitted {0,1}, all with the visible catalogue deleted from the allowed set):

  cotrain      the pre-registered field: rank blend + A-only discovery bonus, B-only down-weighted
  A_only/B_only   single-view baselines -- the comparison the brief explicitly asks for
  union/mean/product   naive "agree more" combinations, i.e. the same information without the
               disagreement term; if cotrain does not beat these, the disagreement is decoration
  A_sup/B_sup/union_sup   the same three on round-0 models, isolating what the co-training round did
  random     uniform field at matched mass, the control that separates placement from mass
  sibling:<file>  the two rasters this lab has already submitted, scored on the identical folds

Outputs evidence/holdout.json + evidence/holdout.md.  Run before spending a submission slot.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_pipeline as R                                   # noqa: E402
from gems52 import cotrain as CT                           # noqa: E402
from gems52 import holdout as HO                           # noqa: E402

EV = ROOT / "evidence"
WORK = ROOT / "work"
PRED = WORK / "fold_preds"
# Every raster this group has previously built, discovered rather than named: the earlier version of
# this list hard-coded filenames that are not in this checkout, so the reference arm silently vanished.
SIBLINGS = [f.name for f in sorted((ROOT / "data/scored").glob("*.tif"))]

# arm name -> (field mode, which round's view scores to combine)
ARMS = {
    "cotrain": ("cotrain", 1), "cotrain_sup": ("cotrain", 0),
    "A_only": ("a_only", 1), "B_only": ("b_only", 1),
    "A_sup": ("a_only", 0), "B_sup": ("b_only", 0),
    "union": ("union", 1), "union_sup": ("union", 0), "mean": ("mean", 1), "mean_sup": ("mean", 0),
    "product": ("product", 1), "random": ("random", 1),
    "corridor_blanket": ("blanket", 0),      # the corridor alone, no detector: ranking must beat this
    # explicit rank-space weights: the pre-registered 0.55/0.20 blend was A-heavy and lost; the
    # weights are now a swept parameter, so the combination is a measured choice and not an assertion
    "wt_A70B30": ("wt:0.70:0.30", 1), "wt_A50B50": ("wt:0.50:0.50", 1),
    "wt_A30B70": ("wt:0.30:0.70", 1), "wt_A20B80": ("wt:0.20:0.80", 1),
    "wt_A40B40m20": ("wt:0.40:0.40:0.20", 1), "wt_A25B55m20": ("wt:0.25:0.55:0.20", 1),
    # the same combinations after regional-background removal (3 km box mean)
    "cotrain_lc": ("cotrain_lc", 1), "cotrain_lc_sup": ("cotrain_lc", 0),
    "A_only_lc": ("a_only_lc", 1), "B_only_lc": ("b_only_lc", 1),
    "union_lc": ("union_lc", 1), "union_lc_sup": ("union_lc", 0), "mean_lc": ("mean_lc", 1),
    "wt_A30B70_lc": ("wt:0.30:0.70_lc", 1), "wt_A20B80_lc": ("wt:0.20:0.80_lc", 1),
    "wt_A50B50_lc": ("wt:0.50:0.50_lc", 1),
}
CORRIDAR_PX = 6           # 600 m of along-strike / off-trace reach, i.e. inside the metric's kernel


def corridor_of(fold: dict, valid: np.ndarray) -> np.ndarray:
    """The near-trace band the metric actually rewards, built only from the visible catalogue.

    Using the catalogue to define where to look is legitimate: the catalogue is given at test time,
    and the organiser's mask is pixel-exact, so everything 1 px off a trace is unmasked and scorable.
    """
    from scipy import ndimage
    vis = fold["visible"] & valid
    return (ndimage.binary_dilation(vis, structure=np.ones((3, 3), bool), iterations=CORRIDAR_PX)
            & ~vis & valid)


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def independence_from_folds(preds: list[dict], folds: list[dict], valid: np.ndarray,
                            cat: np.ndarray, n_blocks: int = 4) -> dict:
    """The brief's premise, measured where it can actually be measured.

    ``evidence/independence.json`` can only see out-of-fold pixels, which are by construction all
    positives, so the *false-alarm* half of the test needs each fold's whole-grid predictions.  Those
    are on disk, so this is the same question with no refit: per (fold, block) cell take View A's mean
    score on non-catalogue pixels (its false-alarm level) and View B's, and correlate the 64 cells.
    High correlation means the two views over-predict in the same places for the same reasons, and a
    confident disagreement then carries no information - which is the case in which Blum-Mitchell gives
    nothing and the arm must be dropped.
    """
    from gems52 import cotrain as CT
    from gems52 import holdout as HO
    lab = HO.block_ids(valid.shape, valid, n=n_blocks)
    fa_a, fa_b, ms_a, ms_b = [], [], [], []
    for pd, f in zip(preds, folds):
        reg = f["region"] & valid
        for k in range(n_blocks * n_blocks):
            blk = (lab == k) & reg
            negb = blk & ~cat & ~f["visible"]
            posb = blk & f["truth"]
            if negb.sum() < 20_000 or posb.sum() < 200:
                continue
            fa_a.append(float(pd["a0"][negb].mean()))
            fa_b.append(float(pd["b0"][negb].mean()))
            ms_a.append(1.0 - float(pd["a0"][posb].mean()))
            ms_b.append(1.0 - float(pd["b0"][posb].mean()))
    d_fa = CT.view_correlation(np.array(fa_a), np.array(fa_b))
    d_ms = CT.view_correlation(np.array(ms_a), np.array(ms_b))
    rng = np.random.default_rng(7)
    allreg = np.logical_or.reduce([f["region"] for f in folds]) & valid & ~cat & ~folds[0]["boundary"]
    idx = rng.choice(np.flatnonzero(allreg.ravel()), size=min(400_000, int(allreg.sum())),
                     replace=False)
    # the fold grids are stored (H,W); flatten first or integer indexing would pick rows
    la = np.concatenate([p["a0"].ravel()[idx] for p in preds])
    lb = np.concatenate([p["b0"].ravel()[idx] for p in preds])
    lo_a, lo_b = np.log(np.clip(la, 1e-6, 1) / (1 - np.clip(la, 1e-6, 1 - 1e-6))), \
        np.log(np.clip(lb, 1e-6, 1) / (1 - np.clip(lb, 1e-6, 1 - 1e-6)))
    out = dict(n_cells=len(fa_a), false_alarm=d_fa, misses=d_ms,
               pearson_logit_negatives_pooled=round(float(np.corrcoef(lo_a, lo_b)[0, 1]), 4),
               note="false_alarm/misses correlations are across (fold x block) cells of each view's "
                    "own error level; pearson_logit_negatives_pooled is the same question at pixel "
                    "resolution on non-catalogue pixels, pooled over the 4 fold models")
    r = max(abs(float(d_fa["pearson_r"] or 0)), abs(out["pearson_logit_negatives_pooled"]))
    out["abs_r_used_for_gate"] = round(r, 4)
    out["gate_threshold"] = R.PREREG["gates"]["independence_abs_pearson_max"]
    out["independent_enough"] = bool(r < out["gate_threshold"])
    out["reading"] = (
        "the two views' false-alarm structure is weakly coupled, so a pixel where one view is "
        "confident and the other withholds is carrying information the confident view alone does "
        "not have" if out["independent_enough"] else
        "|r| is at or above the threshold: the views over-predict in the same places for the same "
        "reasons, so their disagreement is shared-cause noise")
    return out



def load_sibling(name: str) -> np.ndarray:
    f = ROOT / "data/scored" / name
    if not f.exists():
        return None
    with rasterio.open(f) as src:
        a = src.read(1)
    a = np.nan_to_num(a.astype(np.float32), nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(a, 0.0, 1.0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="hide", choices=["hide", "block", "tip"])
    ap.add_argument("--n-folds", type=int, default=4)
    ap.add_argument("--budgets", default="8000,15000,25000,37654")
    ap.add_argument("--emit", default="topk", choices=["topk", "greedy"])
    ap.add_argument("--compute-independence", type=int, default=1)
    ap.add_argument("--arms", default="cotrain,cotrain_sup,A_only,B_only,union,mean,product,"
                                       "A_sup,B_sup,union_sup,mean_sup,random,"
                                       "corridor_blanket,cotrain_cor,union_cor,A_only_cor,B_only_cor")
    a = ap.parse_args(argv)
    budgets = tuple(int(x) for x in a.budgets.split(","))
    arms = [x for x in a.arms.split(",") if x]
    EV.mkdir(parents=True, exist_ok=True)

    valid, cat = R.load_valid_cat()
    folds = HO.make_folds(cat, valid, n_folds=a.n_folds, buffer_px=4,
                          prevalence=R.PREREG["prevalence_used"], seed=0, mode=a.mode)
    log(f"{len(folds)} folds, mode={a.mode}, budgets={budgets}, emit={a.emit}")
    rows: dict[str, dict] = {}
    per_fold_rows: list[dict] = []
    preds_all: list[dict] = []
    sib_fields = {f"{'sibling'}:{nm}": load_sibling(nm) for nm in SIBLINGS}
    sib_fields = {k: v for k, v in sib_fields.items() if v is not None}

    for f in folds:
        pf = PRED / f"{a.mode}_fold{f['fold']}.npz"
        if not pf.exists():
            log(f"  fold {f['fold']}: no saved predictions at {pf}, run --stage fit first")
            return 2
        def grid(key):
            """The fold grids are stored flat (they are what predict_grid returns); reshape once."""
            g = z[key].astype(np.float32) / 65535.0
            return g if g.ndim == 2 else g.reshape(valid.shape)
        with np.load(pf) as z:
            a0, b0, a1, b1 = grid("a0"), grid("b0"), grid("a1"), grid("b1")
        st_by_round = {
            0: CT.strata(a0.ravel(), b0.ravel(), f["region"] & valid, q_conf=0.98,
                         q_abstain_hi=R.PREREG["abstain_q"])["mask"],
            1: CT.strata(a1.ravel(), b1.ravel(), f["region"] & valid, q_conf=0.98,
                         q_abstain_hi=R.PREREG["abstain_q"])["mask"],
        }
        rng = np.random.default_rng(1000 + f["fold"])
        prefs = {}
        corr = corridor_of(f, valid)
        for arm in arms:
            if arm.startswith("sibling:"):
                continue
            in_cor = arm.endswith("_cor")
            name = arm[:-4] if in_cor else arm
            if name == "corridor_blanket":
                prefs[arm] = corr.astype(np.float32)
                continue
            mode, rnd = ARMS[name]
            pa, pb = (a0, b0) if rnd == 0 else (a1, b1)
            if mode == "random":
                fld = rng.random(valid.shape).astype(np.float32)
            else:
                fld, _ = R.field_from_probs(pa, pb, st_by_round[rnd], valid, mode=mode)
            if in_cor:
                fld = fld * corr                      # zero outside the corridor: top-K stays inside
            prefs[arm] = fld
        for nm, fld in sib_fields.items():
            prefs[nm] = fld
        preds_all.append(dict(a0=a0, b0=b0))
        sc = HO.arm_scores(prefs, f, valid, budgets=budgets, emit=a.emit,
                           as_is=tuple(k for k in prefs if k.startswith("sibling:")))
        per_fold_rows.append(dict(fold=f["fold"], n_truth=f["n_truth"], scores=sc))
        for key, v in sc.items():
            rows.setdefault(key, []).append(v["dti"])
        best = max(sc.items(), key=lambda kv: kv[1]["dti"])
        log(f"  fold {f['fold']} ({f['n_truth']} truth px): best {best[0]} = {best[1]['dti']:.4f}")

    ind = {}
    if a.compute_independence:
        log("independence test on (fold x block) error cells")
        ind = independence_from_folds(preds_all, folds, valid, cat)
        log(f"  false-alarm pearson {ind['false_alarm']['pearson_r']:.4f}, misses "
            f"{ind['misses']['pearson_r']:.4f}, pixel-logit {ind['pearson_logit_negatives_pooled']:.4f}"
            f" -> independent_enough={ind['independent_enough']}")

    summary = {}
    for key, vals in rows.items():
        vals = np.asarray(vals, dtype=np.float64)
        summary[key] = dict(mean=round(float(vals.mean()), 5), sd=round(float(vals.std()), 5),
                            best_fold=round(float(vals.max()), 5),
                            worst_fold=round(float(vals.min()), 5), n_folds=int(vals.size))
    order = sorted(summary.items(), key=lambda kv: -kv[1]["mean"])
    ref = summary.get("cotrain|37654") or order[0][1]
    for nm, s in order[:8]:
        log(f"  {nm:26s} mean {s['mean']:.4f} +- {s['sd']:.4f}")

    gt = gate_check(summary, per_fold_rows, a.mode)
    out = dict(generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), mode=a.mode,
               emit=a.emit, budgets=list(budgets), n_folds=a.n_folds,
               prevalence=R.PREREG["prevalence_used"], summary=summary,
               per_fold=[dict(fold=r["fold"], n_truth=r["n_truth"],
                              scores={k: v for k, v in r["scores"].items()}) for r in per_fold_rows],
               gates=gt, independence=ind)
    (EV / f"holdout_{a.mode}.json").write_text(json.dumps(out, indent=1) + "\n")
    (EV / f"holdout_{a.mode}.md").write_text(markdown(out))
    log(f"wrote evidence/holdout_{a.mode}.json / .md   promoted={gt['promoted']}")
    print(markdown(out))
    return 0


def gate_check(summary: dict, per_fold_rows: list[dict], mode: str) -> dict:
    g = R.PREREG["gates"]
    best_cotrain_key = max([k for k in summary if k.startswith("cotrain|")],
                           key=lambda k: summary[k]["mean"], default=None)
    res = dict(promoted=False, tested=best_cotrain_key, checks={})
    if best_cotrain_key is None:
        res["reason"] = "cotrain arm absent"
        return res
    s = summary[best_cotrain_key]
    ref_union = max([summary[k]["mean"] for k in summary
                     if k.startswith(("union|", "union_cor|"))], default=float("-inf"))
    ref_a = max([summary[k]["mean"] for k in summary
                 if k.startswith("A_only|")], default=float("-inf"))
    ref_rand = max([summary[k]["mean"] for k in summary
                    if k.startswith("random|")], default=float("-inf"))
    sib = max([summary[k]["mean"] for k in summary
               if k.startswith("sibling:")], default=None)
    ck = {}
    ck["beats_union"] = dict(delta=round(s["mean"] - ref_union, 5),
                             need=g["fold_dti_must_beat_union_baseline_by"],
                             ok=bool(s["mean"] - ref_union >= g["fold_dti_must_beat_union_baseline_by"]))
    ck["beats_single_view"] = dict(delta=round(s["mean"] - ref_a, 5), need=0.0,
                                   ok=bool(s["mean"] > ref_a))
    ck["placement_not_mass"] = dict(delta=round(s["mean"] - ref_rand, 5), need=0.0,
                                    ok=bool(s["mean"] > ref_rand))
    if sib is not None:
        ck["beats_sibling_on_folds"] = dict(cotrain=round(s["mean"], 5), sibling=round(sib, 5),
                                             need=g["pooled_dti_must_beat_sibling_best"],
                                             ok=bool(s["mean"] >= sib + g["pooled_dti_must_beat_sibling_best"]))
    key = best_cotrain_key
    wins = sum(1 for r in per_fold_rows if r["scores"][key]["dti"] >=
               max([v["dti"] for k2, v in r["scores"].items() if k2.startswith(("A_only", "union"))]
                   or [-1]))
    ck["fold_support"] = dict(wins=f"{wins}/{len(per_fold_rows)}",
                              need=g["fold_support_min"], ok=bool(wins >= g["fold_support_min"]))
    res["checks"] = ck
    res["promoted"] = bool(all(v["ok"] for v in ck.values()))
    res["reason"] = ("all gates cleared on " + mode + " folds" if res["promoted"] else
                     "gates not cleared: " + ", ".join(k for k, v in ck.items() if not v["ok"]))
    return res


def markdown(out: dict) -> str:  # noqa: C901
    L = [f"# Blocked-holdout arm table ({out['mode']}, {out['n_folds']} folds, "
         f"{out['emit']} emission)", "",
         f"Prevalence matched at {100*out['prevalence']:.3f} % of the footprint; the visible "
         f"catalogue is masked out of both the allowed set and the score, exactly as the "
         f"organiser does. Mean DTI over folds; `|N` is the emission budget in pixels.", "",
         "| arm | mean DTI | sd | best fold | worst fold |", "|---|---|---|---|---|"]
    for k, s in sorted(out["summary"].items(), key=lambda kv: -kv[1]["mean"]):
        L.append(f"| {k} | {s['mean']:.4f} | {s['sd']:.4f} | {s['best_fold']:.4f} "
                 f"| {s['worst_fold']:.4f} |")
    if out.get("independence"):
        i = out["independence"]
        L += ["", "## Conditional-independence test (the premise of the method)", "",
              f"- cells: {i['n_cells']} (fold x block) | threshold |r| < {i['gate_threshold']}",
              f"- false-alarm correlation across cells: {i['false_alarm']['pearson_r']:.4f} "
              f"(Spearman {i['false_alarm']['spearman_rho']:.4f})",
              f"- miss correlation across cells: {i['misses']['pearson_r']:.4f} "
              f"(Spearman {i['misses']['spearman_rho']:.4f})",
              f"- pixel-level logit correlation on non-catalogue pixels, pooled: "
              f"{i['pearson_logit_negatives_pooled']:.4f}",
              f"- **independent enough: {i['independent_enough']}** - {i['reading']}", ""]
    L += ["", "## Gates", ""]
    gt = out["gates"]
    L.append(f"- tested arm: `{gt.get('tested')}`")
    for k, v in gt["checks"].items():
        L.append(f"- `{k}`: {v} -> {'OK' if v['ok'] else 'NOT OK'}")
    L.append(f"- **promoted: {gt['promoted']}** ({gt['reason']})")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
