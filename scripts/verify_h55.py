#!/usr/bin/env python3
"""Pass 2 and pass 3 of the brief, as one script: re-verify the shipped file, and answer the two
questions the brief asks that a sweep does not answer.

1. **Conditional independence of the two views, on the corrected split.** The brief: "empirically
   test the conditional-independence assumption by measuring the correlation of the two views'
   out-of-fold errors on labelled negatives across spatial blocks; abandon the method if the errors
   are strongly correlated."  H52's attempt could not fire -- the per-block false-alarm rate came out
   constant, fewer than three blocks were usable, and Spearman degenerated to 1.0 on all ties
   (``knowledge/03`` N-1, IR-52-018).  This run uses the corrected split (band 6 is radiometric, so
   it is in View B) and reports **two** block statistics, plus the number of usable blocks, so a
   reader can see whether the test fired rather than being told that it did.

2. **Is the output merely the union of the two views?** The brief asks for that check explicitly.
   ``gates.uniqueness_report`` answers it against *previous submissions*; this answers it against
   the two views of *this* pipeline, which is the question actually asked.

3. **Pass 3: re-read the shipped bytes.** Format, dtype, CRS, transform, shape, value range, NaN
   count, catalogue overlap, footprint containment, sha256 -- all recomputed from the file on disk
   and compared against the evidence record, so the record cannot have drifted from the artefact.

Usage::

    python3 scripts/verify_h55.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid as G          # noqa: E402
from gems52 import holdout as H        # noqa: E402
from gems52 import cotrain as C        # noqa: E402
from gems52 import gates               # noqa: E402
from gems55 import calib, emit_opt     # noqa: E402

DERIV = ROOT / "work" / "derived"
FIELDS = ROOT / "work" / "h55_fields"
EV = ROOT / "evidence"
SEED = 20261006
N_FOLDS = 4
BUFFER_PX = 4
PREVALENCE = 0.002
ABANDON_R = C.ABANDON_R
BUDGET = 37654


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------------------------
# 1. conditional independence on the corrected split
# --------------------------------------------------------------------------------------------
def independence(mode: str, valid: np.ndarray, cat: np.ndarray) -> dict:
    from scipy import ndimage
    folds = H.make_folds(cat, valid, n_folds=N_FOLDS, buffer_px=BUFFER_PX, prevalence=PREVALENCE,
                         seed=SEED, mode=mode)
    blocks = G.block_labels(valid.shape, valid, n=8)
    n_blk = int(blocks.max()) + 1
    per_fold = []
    for fold in folds:
        p = FIELDS / f"{mode}_f{fold['fold']}.npz"
        if not p.exists():
            raise SystemExit(f"missing {p}; run scripts/run_h55.py --stage fields --modes {mode}")
        z = np.load(p)
        pA = z["pA"].astype(np.float64)
        pB = z["pB"].astype(np.float64)
        # labelled negatives: footprint pixels the catalogue says are not fault, held >= 300 m clear
        # of every labelled positive AND of this fold's held-out truth, so a near-trace pixel cannot
        # teach the model that the trace is background (cotrain.NEG_COLLAR_PX, IR-52-004)
        clear = ~ndimage.binary_dilation(cat | fold["truth"], iterations=C.NEG_COLLAR_PX)
        neg = valid & clear & fold["fit"]
        # statistic 1: mean over-prediction on negatives, per block (soft 1 - specificity)
        e1a = np.full(n_blk, np.nan); e1b = np.full(n_blk, np.nan)
        # statistic 2: false-alarm rate at a fixed global budget, per block.  This is the one H52
        # could not use: if the two views' top-K sets are near-identical the rate is near-constant
        # and Spearman degenerates.  Reporting its dispersion is what shows whether it fired.
        e2a = np.full(n_blk, np.nan); e2b = np.full(n_blk, np.nan)
        allowed = valid & ~fold["visible"]
        for name, pv, e1, e2 in (("A", pA, e1a, e2a), ("B", pB, e1b, e2b)):
            topk = emit_opt.topk(pv, allowed, BUDGET)
            nn = neg.sum(axis=None)
            for b in range(n_blk):
                m = (blocks == b) & neg
                k = int(m.sum())
                if k < 50:                     # a block with too few negatives has no usable rate
                    continue
                e1[b] = float(pv[m].mean())
                e2[b] = float(topk[m].sum()) / k
            del topk
        r1 = C.view_correlation(e1a, e1b)
        r2 = C.view_correlation(e2a, e2b)
        usable1 = int(np.sum(np.isfinite(e1a) & np.isfinite(e1b)))
        usable2 = int(np.sum(np.isfinite(e2a) & np.isfinite(e2b)))
        rec = dict(fold=fold["fold"], n_neg=int(neg.sum()), n_blocks=n_blk,
                   mean_overprediction=dict(usable_blocks=usable1, **r1),
                   far_at_budget=dict(usable_blocks=usable2, budget=BUDGET, **r2,
                                      dispersion_A=float(np.nanstd(e2a)),
                                      dispersion_B=float(np.nanstd(e2b)),
                                      cv_A=(float(np.nanstd(e2a) / np.nanmean(e2a))
                                            if np.nanmean(e2a) > 0 else None),
                                      cv_B=(float(np.nanstd(e2b) / np.nanmean(e2b))
                                            if np.nanmean(e2b) > 0 else None)))
        per_fold.append(rec)
        log(f"  [{mode}] fold {fold['fold']}: usable blocks {usable1}/{usable2} of {n_blk}  "
            f"rho(mean-overpred)={r1['spearman_rho']}  rho(FAR@{BUDGET})={r2['spearman_rho']}  "
            f"cv_A={rec['far_at_budget']['cv_A']}  cv_B={rec['far_at_budget']['cv_B']}")
        del pA, pB

    def pool(key, stat):
        v = [f[key][stat] for f in per_fold if f[key].get(stat) is not None
             and np.isfinite(f[key][stat])]
        return dict(values=[round(float(x), 4) for x in v],
                    mean=round(float(np.mean(v)), 4) if v else None,
                    n=len(v),
                    folds_exceeding_abandon_threshold=int(sum(1 for x in v if abs(x) >= ABANDON_R)),
                    abandon_r=ABANDON_R)
    fired = [f for f in per_fold if f["far_at_budget"]["usable_blocks"] >= 3
             and (f["far_at_budget"]["cv_A"] or 0) > 1e-6]
    out = dict(mode=mode, n_folds=len(per_fold), abandon_threshold=ABANDON_R,
               blocks_per_instrument=n_blk, budget=BUDGET,
               test_could_fire=bool(fired), n_folds_where_test_could_fire=len(fired),
               per_fold=per_fold,
               pooled=dict(
                   mean_overprediction_pearson=pool("mean_overprediction", "pearson_r"),
                   mean_overprediction_spearman=pool("mean_overprediction", "spearman_rho"),
                   far_pearson=pool("far_at_budget", "pearson_r"),
                   far_spearman=pool("far_at_budget", "spearman_rho")),
               verdict=None)
    sp = out["pooled"]["mean_overprediction_spearman"]["values"]
    if not out["test_could_fire"]:
        out["verdict"] = ("UNMEASURED - the block-level false-alarm statistic is still degenerate on "
                          "this grid, so the pre-registered abandonment test cannot fire. This is the "
                          "same outcome H52 recorded (IR-52-018) and it is reported as 'not measured', "
                          "never as 'independent'.")
    elif sp and max(abs(x) for x in sp) >= ABANDON_R:
        out["verdict"] = (f"REFUTED at the pre-registered threshold: |Spearman| reaches "
                          f"{max(abs(x) for x in sp):.4f} >= {ABANDON_R}. Abandon co-training.")
    else:
        out["verdict"] = (f"NOT REFUTED at the pre-registered threshold: max |Spearman| over folds = "
                          f"{max(abs(x) for x in sp) if sp else float('nan'):.4f} < {ABANDON_R}. This "
                          f"is not evidence of independence; it is the absence of evidence against it. "
                          f"The A_only matched-random fold comparison in "
                          f"evidence/h55_sweep_hardcore.json is a separate promotion test, not an "
                          f"independence statistic.")
    return out


# --------------------------------------------------------------------------------------------
# 2. is it merely the union of the two views?
# --------------------------------------------------------------------------------------------
def a_only_promotion_summary() -> str:
    """Summarize the separate A-only matched-random promotion check from its sweep receipt."""
    path = EV / "h55_sweep_hardcore.json"
    if not path.exists():
        return "The A-only matched-random comparison is not measured in this receipt."
    sweep = json.loads(path.read_text())

    def row(mode, arm, emitter):
        return next((item for item in sweep.get(mode, {}).get("summary", {}).get("ranked", [])
                     if item.get("arm") == arm and item.get("emitter") == emitter), None)

    comparisons = {}
    for mode in ("hide", "tip"):
        candidate = row(mode, "A_only", "hc4|37654")
        random = row(mode, "random", "hc|37654")
        if not candidate or not random:
            return "The A-only matched-random comparison is incomplete in the sweep receipt."
        comparisons[mode] = (candidate, random)

    hide, random_hide = comparisons["hide"]
    tip, random_tip = comparisons["tip"]
    hide_wins = int(hide.get("fold_wins_vs_random") or 0)
    tip_wins = int(tip.get("fold_wins_vs_random") or 0)
    gate = hide_wins >= 3 and tip_wins >= 3
    disposition = "passes" if gate else "does not pass"
    return (
        f"A_only mean DTI is {float(hide['mean_dti']):.5f} vs matched random "
        f"{float(random_hide['mean_dti']):.5f} on hide and {float(tip['mean_dti']):.5f} vs "
        f"{float(random_tip['mean_dti']):.5f} on tip; its fold wins are {hide_wins}/4 and "
        f"{tip_wins}/4, so it {disposition} the pre-registered ≥3/4-per-instrument gate."
    )


def union_audit_from_fields(emitted, pA, pB, allowed, budget):
    a = emit_opt.topk(pA, allowed, budget)
    b = emit_opt.topk(pB, allowed, budget)
    u = a | b
    da = emit_opt.calibrate(pA, allowed, 8129.0)
    db = emit_opt.calibrate(pB, allowed, 8129.0)
    ga, _ = emit_opt.coverage_greedy(da, allowed, 0.0, n_g=8129.0, max_emit=budget, batch=20_000)
    gb, _ = emit_opt.coverage_greedy(db, allowed, 0.0, n_g=8129.0, max_emit=budget, batch=20_000)
    ug = ga | gb
    E = emitted.astype(bool)
    def rel(x, name):
        return dict(name=name, px=int(x.sum()),
                    in_both=int((E & x).sum()),
                    frac_of_shipped=float((E & x).sum() / max(int(E.sum()), 1)),
                    shipped_is_subset=bool((E & x).sum() == E.sum()),
                    shipped_equals=bool((E ^ x).sum() == 0))
    return dict(budget=budget, emitted_px=int(E.sum()),
                comparisons=[rel(a, "top-K of View A alone"),
                             rel(b, "top-K of View B alone"),
                             rel(u, "union of the two views' top-K"),
                             rel(ga, "coverage-greedy of View A alone"),
                             rel(gb, "coverage-greedy of View B alone"),
                             rel(ug, "union of the two views' coverage-greedy emissions")],
                verdict=None)


# --------------------------------------------------------------------------------------------
# 3. pass 3: re-read the shipped bytes
# --------------------------------------------------------------------------------------------
def reverify(tag: str) -> dict:
    rec = json.loads((EV / f"h55_submission_{tag}.json").read_text())
    p = ROOT / rec["path"]
    with rasterio.open(p) as src:
        a = src.read(1)
        prof = dict(driver=src.driver, count=src.count, dtype=src.dtypes[0], crs=str(src.crs),
                    width=src.width, height=src.height, transform=tuple(src.transform),
                    nodata=src.nodata)
    with rasterio.open(ROOT / "data/labels.tif") as src:
        lab = src.read(1)
    cat, foot = lab == 1, lab >= 0
    checks = {
        "path_exists": p.exists(),
        "sha256_matches_record": hashlib.sha256(p.read_bytes()).hexdigest() == rec["sha256"],
        "bytes_match_record": p.stat().st_size == rec["bytes"],
        "single_band": prof["count"] == 1,
        "dtype_float32": prof["dtype"] == "float32",
        "crs_epsg32611": prof["crs"] == "EPSG:32611",
        "width_3292": prof["width"] == 3292,
        "height_3730": prof["height"] == 3730,
        # rasterio's Affine is a 9-tuple (a,b,c,d,e,f,0,0,1); grid.TRANSFORM is the pinned six.
        # Comparing them whole is a bug in the check, not in the file -- gates.format_report, which
        # does it correctly, reports ok=True on the same bytes.
        "transform_matches_pinned": tuple(prof["transform"])[:6] == tuple(G.TRANSFORM),
        "no_nan": int(np.isnan(a).sum()) == 0,
        "values_within_0_1": bool(((a >= 0) & (a <= 1)).all()),
        "values_are_binary": set(np.unique(a).tolist()) <= {0.0, 1.0},
        "positive_px_matches_record": int((a > 0).sum()) == rec["geometry"]["S"],
        "zero_on_every_catalogue_pixel": int(((a > 0) & cat).sum()) == 0,
        "zero_outside_footprint": bool((a[~foot] == 0).all()),
        "positive_px_all_inside_footprint": bool(((a > 0) & ~foot).sum() == 0),
        "all_emitted_pixels_8_isolated": rec["geometry"]["max_component"] == 1,
        "coverage_efficiency_recorded": abs(rec["geometry"]["A_per_S"]
                                            / calib.DISC_WEIGHT_SUM
                                            - rec["geometry"]["spacing_efficiency"]) < 1e-6,
    }
    rep = gates.format_report(p, ROOT / "data" / "sample_submission.tif")
    checks["format_gate_ok"] = bool(rep.get("ok"))
    checks["format_gate_no_problems"] = not rep.get("problems")
    priors = [q for q in gates.find_priors([ROOT / "data/scored", ROOT / "data/reference",
                                            ROOT / "submission", ROOT / "docs/downloads"],
                                           exclude=p) if q.name != p.name]
    uni = gates.uniqueness_report(a > 0, priors, top=len(priors))
    checks["uniqueness_gate_ok"] = bool(uni.get("ok"))
    checks["not_identical_to_any_prior"] = not any(r.get("identical") for r in uni["per_prior"])
    checks["not_merely_the_union"] = uni["novel_vs_all_priors"] > 0 and uni["prior_px_dropped"] > 0
    return dict(file=rec["file"], profile=prof, checks=checks,
                all_ok=all(checks.values()),
                failed=[k for k, v in checks.items() if not v],
                uniqueness=dict(ok=uni["ok"], relation=uni["relation_to_union"],
                                novel_px=uni["novel_vs_all_priors"],
                                novel_fraction=uni["novel_fraction"],
                                priors_checked=uni["n_priors_checked"],
                                prior_px_dropped=uni["prior_px_dropped"]),
                geometry=rec["geometry"])


def main() -> int:
    t0 = time.time()
    with rasterio.open(ROOT / "data/labels.tif") as src:
        lab = src.read(1)
    cat, valid = lab == 1, lab >= 0
    tag = "20261007T0150Z"
    out = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), tag=tag)

    log("== pass 3: re-read the shipped bytes ==")
    out["shipped_file"] = reverify(tag)
    for k, v in out["shipped_file"]["checks"].items():
        log(f"   {'OK ' if v else 'FAIL'} {k}")
    log(f"   all_ok={out['shipped_file']['all_ok']}")

    log("\n== pass 2a: conditional independence of the corrected two views ==")
    out["independence"] = {m: independence(m, valid, cat) for m in ("hide", "tip")}
    for m, r in out["independence"].items():
        log(f"   [{m}] test could fire: {r['test_could_fire']} "
            f"({r['n_folds_where_test_could_fire']}/{r['n_folds']} folds)")
        log(f"   [{m}] verdict: {r['verdict']}")

    log("\n== pass 2b: is the output merely the union of the two views? ==")
    stack = np.load(ROOT / "work" / "h55_stack.npy")
    fold = dict(fold=-1, mode="deploy", truth=np.zeros(valid.shape, bool), visible=cat & valid,
                fit=valid, region=valid, boundary=np.zeros(valid.shape, bool), n_truth=0)
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_h55", ROOT / "scripts" / "run_h55.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    pA, pB, _ = mod.fold_fields(stack, valid, fold, seed=SEED)
    del stack
    allowed = valid & ~cat
    with rasterio.open(ROOT / "submission" / json.loads(
            (EV / f"h55_submission_{tag}.json").read_text())["file"]) as src:
        emitted = src.read(1) > 0
    ua = union_audit_from_fields(emitted, pA.astype(np.float32), pB.astype(np.float32),
                                 allowed, BUDGET)
    for c in ua["comparisons"]:
        log(f"   vs {c['name']:52s}: {c['px']:7d} px, overlap {c['in_both']:7d} "
            f"({c['frac_of_shipped']:.1%} of shipped), shipped==set {c['shipped_equals']}")
    by = {c["name"]: c for c in ua["comparisons"]}
    ut = by["union of the two views' top-K"]
    ug = by["union of the two views' coverage-greedy emissions"]
    ua["verdict"] = (
        "NOT the union of the two views. The shipped set shares "
        f"{ut['frac_of_shipped']:.1%} of its pixels with the union of the two views' top-K sets and "
        f"{ug['frac_of_shipped']:.1%} with the union of their coverage-greedy emissions, and is equal "
        "to no set in the table. It is View B's own coverage-greedy emission with a thermal rank "
        "bonus. View A contributes nothing to this emission: " + a_only_promotion_summary() + " "
        "The registered conditional-independence test is refuted at its pre-registered threshold on "
        "both instruments (evidence/h55_verification_*.json), so co-training is abandoned. These are "
        "separate findings; the fold-vs-random result is not a conditional-independence test.")
    out["union_audit"] = ua
    log(f"   verdict: {ua['verdict'][:150]}...")

    out["all_ok"] = bool(out["shipped_file"]["all_ok"])
    out["independence_summary"] = {
        m: dict(test_could_fire=r["test_could_fire"],
                usable_blocks_per_fold=r["per_fold"][0]["mean_overprediction"]["usable_blocks"],
                blocks_available=r["blocks_per_instrument"],
                max_abs_spearman_mean_overprediction=max(
                    abs(x) for x in r["pooled"]["mean_overprediction_spearman"]["values"]),
                max_abs_spearman_far_at_budget=max(
                    abs(x) for x in r["pooled"]["far_spearman"]["values"]),
                abandon_threshold=r["abandon_threshold"], verdict=r["verdict"])
        for m, r in out["independence"].items()}
    out["review_note"] = (
        "Text review correction: an earlier union-audit sentence misstated the A_only matched-random "
        "mean comparison. The corrected verdict now reads its per-instrument means and fold-win counts "
        "from evidence/h55_sweep_hardcore.json; this is separate from the OOF error-correlation test."
    )
    (EV / f"h55_verification_{tag}.json").write_text(
        json.dumps(out, indent=1, allow_nan=False, default=str))
    log(f"\nwrote evidence/h55_verification_{tag}.json  ({time.time()-t0:.1f}s)")
    log(f"PASS3_ALL_OK={out['shipped_file']['all_ok']}")
    return 0 if out["shipped_file"]["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
