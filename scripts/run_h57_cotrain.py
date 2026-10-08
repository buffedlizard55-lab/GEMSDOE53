#!/usr/bin/env python3
"""H57 -- the brief's co-training round, measured.

Fold structure (one structure, used for everything, so nothing is ever scored in-sample):

* **Whole segments.** A catalogue component goes entirely to the quadrant holding most of its
  pixels; it is never cut.  The held-out truth is a prevalence-matched, shuffled subset of those
  *whole* components.
* **A 4 px buffer.** The collar around the held quadrant and around the footprint edge is excluded
  from both fitting and scoring, so a trace running along the cut cannot be handed to the model on
  one side and graded on the other.
* **Out-of-fold everywhere.** View A and View B are fitted on ``fit`` and their probability fields
  are only *kept* inside the held quadrant.  Because the four quadrants tile the grid, the union of
  the four kept regions is the whole footprint and every pixel carries a genuine out-of-fold score.

What is measured:

1. the two views;
2. the brief's **independence test** -- per-spatial-block out-of-fold error of each view on labelled
   negatives, plus a pixel-level cross-check at far higher power.  Fail-closed: a degenerate or
   under-powered statistic forbids the exchange, and that is reported as a failure of the *test*;
3. the **pseudo-label exchange** on whole connected segments inside the unlabelled quadrant, never
   crossing the block edge, a training pixel or the catalogue buffer, donor confident and receiver
   in a middle abstention band (never confidently negative);
4. the **disagreement strata** the brief asks for -- A-only = buried structure, B-only = suspect
   surface artefact;
5. matched-budget **single-view baselines** and a uniform-random control at the same budget in the
   same legal set.

Nothing here reads a leaderboard score.  Write `evidence/h57_cotrain.json` and the out-of-fold
probability rasters the build script needs.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems52 import grid as G                      # noqa: E402
from gems52 import h57                            # noqa: E402
from gems52 import holdout as HO                  # noqa: E402
from gems52 import metric as M                    # noqa: E402
from gems52 import spatial                        # noqa: E402

OUT = Path("evidence/h57_cotrain.json")
WORK = Path("work/h57")
SEED = 20261007
BLOCK = 50          # spatial block edge for the negative-error diagnostic, px (5 km)
MIN_NEG = 300       # labelled negatives a block must carry before it counts
Q_CONF = 0.60       # the brief's "this view is confident"
Q_ABSTAIN = 0.40    # ... and "this view abstains"; q_conf > q_abstain, so A-only and B-only
#                    cannot overlap.
N_NEG_TRAIN = 60000
BUDGETS = (15000, 37654)


def log(msg: str) -> None:
    print(f"[h57 {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _gather(layers, idx, flat_idx, width):
    """Stream a set of flat pixel indices out of the memmap, one grid row at a time."""
    flat_idx = np.asarray(flat_idx, np.int64)
    rows = flat_idx // width
    order = np.argsort(rows, kind="stable")
    rows_sorted = rows[order]
    out = np.empty((flat_idx.size, len(idx)), np.float32)
    mm = layers.mm
    uniq = np.unique(rows_sorted)
    for r, s0, e0 in zip(uniq, np.searchsorted(rows_sorted, uniq, side="left"),
                         np.searchsorted(rows_sorted, uniq, side="right")):
        sel = order[s0:e0]
        cols = flat_idx[sel] - int(r) * width
        block = np.asarray(mm[idx, int(r), :], dtype=np.uint8)      # (n_layers, n_cols)
        out[sel] = block[:, cols].T.astype(np.float32) / 255.0
    return out


def fit_and_predict(layers, idx, cat, valid, fit, seed, tag):
    pos, neg = h57.labelled_pixels(cat, valid, fit, seed=seed, n_neg=N_NEG_TRAIN)
    if pos.size == 0 or neg.size == 0:
        raise RuntimeError(f"{tag}: empty training sample ({pos.size} pos, {neg.size} neg)")
    w = cat.shape[1]
    X = np.vstack([_gather(layers, idx, pos, w), _gather(layers, idx, neg, w)])
    y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)])
    clf = h57.fit_view(X, y)
    grid = h57.predict_grid(clf, layers, idx)
    log(f"{tag}: {pos.size} pos / {neg.size} neg, {X.shape[1]} features, "
        f"|w|={np.linalg.norm(clf.coef_):.4f}")
    del X, y
    return clf, grid


def block_error_rows(pa, pb, neg_mask, fold):
    h, w = neg_mask.shape
    rows = []
    for y in range(0, h, BLOCK):
        for x in range(0, w, BLOCK):
            sl = np.s_[y:min(y + BLOCK, h), x:min(x + BLOCK, w)]
            good = neg_mask[sl]
            if int(good.sum()) < MIN_NEG:
                continue
            a = pa[sl][good].astype(float)
            b = pb[sl][good].astype(float)
            rows.append(dict(fold=int(fold), block_row=y // BLOCK, block_col=x // BLOCK,
                             n_negatives=int(good.sum()),
                             mse_A=float(np.mean(a * a)), mse_B=float(np.mean(b * b)),
                             fpr_A=float(np.mean(a >= Q_CONF)), fpr_B=float(np.mean(b >= Q_CONF))))
    return rows


def pixel_corr(pa, pb, mask):
    from scipy import stats
    good = mask & np.isfinite(pa) & np.isfinite(pb)
    a, b = pa[good].astype(float), pb[good].astype(float)
    out = dict(n=int(good.sum()))
    if out["n"] >= 3 and np.ptp(a) > 1e-12 and np.ptp(b) > 1e-12:
        out["pearson"] = float(stats.pearsonr(a, b).statistic)
        out["spearman"] = float(stats.spearmanr(a, b).statistic)
    else:
        out.update(pearson=None, spearman=None, reason="too few observations or a constant column")
    return out


def main() -> int:
    t0 = time.time()
    WORK.mkdir(parents=True, exist_ok=True)
    valid = G.footprint_from("data/training_features.tif", bands="all")
    with rasterio.open("data/labels.tif") as src:
        cat = src.read(1) == 1
    log(f"footprint {int(valid.sum())} px, catalogue {int(cat.sum())} px")

    meta = h57.build_layers()
    layers = h57.Layers()
    idx_a = layers.index([f"{n}_{s}" for n in h57.VIEW_A_LAYERS for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in h57.VIEW_B_LAYERS for s in ("val", "grad", "range")])
    log(f"layer stack {len(meta['names'])}; View A {len(idx_a)} features, View B {len(idx_b)}")

    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=SEED,
                          mode="block")
    cat_dil = ndimage.binary_dilation(cat, iterations=h57.NEG_CLEAR_PX)
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    pa_oof = np.full(G.SHAPE, np.nan, np.float32)
    pb_oof = np.full(G.SHAPE, np.nan, np.float32)
    neg_rows, fold_receipts = [], []
    models = {}
    for f in folds:
        fit, reg = f["fit"], f["region"]
        clf_a, pa = fit_and_predict(layers, idx_a, cat, valid, fit, SEED + f["fold"],
                                    f"A/f{f['fold']}")
        clf_b, pb = fit_and_predict(layers, idx_b, cat, valid, fit, SEED + f["fold"],
                                    f"B/f{f['fold']}")
        models[f["fold"]] = (clf_a, clf_b, pa, pb)
        pa_oof[reg] = pa[reg]
        pb_oof[reg] = pb[reg]
        neg_mask = reg & ~cat_dil
        rows = block_error_rows(pa, pb, neg_mask, f["fold"])
        neg_rows.extend(rows)
        fold_receipts.append(dict(
            fold=f["fold"], n_fit=int(fit.sum()), n_region=int(reg.sum()),
            n_boundary=int(f["boundary"].sum()), n_truth=int(f["n_truth"]),
            n_held_components_px=int(f["n_held"]), cat_in_fit=int((cat & fit).sum()),
            cat_in_region=int((cat & reg).sum()), n_negatives=int(neg_mask.sum()),
            n_blocks=len(rows)))
        log(f"fold {f['fold']}: {int(fit.sum())} fit px, {int(reg.sum())} region px, "
            f"{len(rows)} blocks")
    del models

    ind = spatial.independence(neg_rows, threshold=0.60, min_blocks=20)
    ind["pixel_level"] = pixel_corr(pa_oof, pb_oof, valid & ~cat_dil)
    ind["q_conf"] = Q_CONF
    ind["block_px"] = BLOCK
    ind["min_negatives_per_block"] = MIN_NEG
    log(f"independence: measured={ind['measured']} allow_exchange={ind['allow_exchange']} "
        f"max|r|={ind['max_abs_correlation']} pixel-level r={ind['pixel_level']['pearson']}")

    pa0 = np.nan_to_num(pa_oof, nan=0.0)
    pb0 = np.nan_to_num(pb_oof, nan=0.0)
    strata = h57.disagreement(pa0, pb0, permitted, q_conf=Q_CONF, q_abstain=Q_ABSTAIN)
    depth = G.read_band("data/training_features.tif", 15)
    strata["median_depth_to_basement_m"] = {
        k: float(np.median(depth[m])) for k, m in
        (("a_only", strata["masks"]["a_only"]), ("b_only", strata["masks"]["b_only"]),
         ("concordant", strata["masks"]["concordant"]), ("permitted", permitted)) if m.any()}
    strata["evaluated_px"] = int(np.isfinite(pa_oof).sum())
    log(f"strata {strata['counts']}")

    # ---- pseudo-label exchange inside the fold-0 unlabelled quadrant -------------------------
    pseudo = {"ran": False, "reason": None}
    f0 = folds[0]
    if ind["allow_exchange"]:
        reg0 = f0["region"]
        fit0 = f0["fit"]
        forbidden = cat | corridor | ~reg0 | f0["boundary"]
        idx, receipt = spatial.whole_pseudo_segments(pa0, pb0, reg0, forbidden, Q_CONF,
                                                    Q_ABSTAIN, Q_CONF, side=BLOCK)
        n_pseudo = 0
        after_grid = None
        before = after = None
        if idx.size:
            pseudo["ran"] = True
            n_pseudo = int(idx.size)
            w = G.SHAPE[1]
            pos, neg = h57.labelled_pixels(cat, valid, fit0, seed=SEED + 99,
                                           n_neg=N_NEG_TRAIN)
            X = np.vstack([_gather(layers, idx_a, pos, w), _gather(layers, idx_a, neg, w),
                           _gather(layers, idx_a, idx, w)])
            y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8),
                                np.ones(idx.size, np.int8)])
            clf = h57.fit_view(X, y)
            del X, y
            from sklearn.metrics import roc_auc_score
            # held-out catalogue in the unlabelled quadrant -- the model never saw these pixels
            # Both classes, and none of it trained on.  The <=200 m corridor is an *emission* rule,
            # never an evaluation one: excluding it here would delete every catalogue pixel.
            m = reg0 & ~f0["boundary"]
            if int(cat[m].sum()) < 100 or int((~cat[m]).sum()) < 100:
                n_pseudo = int(idx.size)
                pseudo.update(ran=True, n_pseudo_px=n_pseudo, n_segments=len(receipt),
                              donor_threshold=Q_CONF, receiver_band=[Q_ABSTAIN, Q_CONF],
                              auc_view_A_before=None, auc_view_A_after=None, delta_auc=None,
                              n_eval_px=int(m.sum()),
                              skipped="the fold-0 quadrant holds too few held-out catalogue "
                                      "pixels to score an AUC; the exchange is still reported as "
                                      "executed",
                              rule="whole 8-connected segments inside the fold-0 unlabelled "
                                   "quadrant, one 50x50 block each")
                log(f"pseudo-label exchange: {idx.size} px / {len(receipt)} segments; AUC skipped "
                    f"({int(cat[m].sum())} held-out catalogue px in the quadrant)")
                idx = np.empty(0, np.int64)
            before = after = after_grid = None
            if idx.size:
                before = float(roc_auc_score(cat[m], pa0[m]))
                after_grid = np.zeros(G.SHAPE, np.float32)
                for r0 in range(0, G.SHAPE[0], 500):
                    r1 = min(r0 + 500, G.SHAPE[0])
                    Xq = layers.matrix(idx_a, r0, r1)
                    after_grid[r0:r1] = clf.predict_proba(Xq)[:, 1].astype(np.float32).reshape(
                        r1 - r0, G.SHAPE[1])
                after = float(roc_auc_score(cat[m], after_grid[m]))
            pseudo.update(n_pseudo_px=int(n_pseudo), n_segments=len(receipt),
                          donor_threshold=Q_CONF, receiver_band=[Q_ABSTAIN, Q_CONF],
                          auc_view_A_before=before, auc_view_A_after=after,
                          delta_auc=(None if before is None else after - before),
                          n_eval_px=int(m.sum()),
                          rule="whole 8-connected segments inside the fold-0 unlabelled quadrant, "
                               "one 50x50 block each, no catalogue/corridor pixel, donor confident "
                               "and receiver in the abstention band")
            log(f"pseudo-label exchange: {int(n_pseudo)} px / {len(receipt)} segments, "
                + (f"AUC {before:.4f} -> {after:.4f} (d={after - before:+.4f})"
                   if before is not None else "AUC skipped"))
            if after_grid is not None:
                np.save(WORK / "pa_pseudo.npy", after_grid)
        else:
            pseudo["reason"] = "no whole segment satisfied donor-confident / receiver-abstains"
    else:
        pseudo["reason"] = ("independence test did not license the exchange: " + ind["reason"])
    if not pseudo.get("ran"):
        pseudo["reason"] = pseudo.get("reason") or "not attempted"
        log("pseudo-label exchange NOT run: " + str(pseudo["reason"]))

    # ---- matched-budget arms on both instruments --------------------------------------------
    fields = {
        "A_only": pa0,
        "B_only": pb0,
        "union": np.maximum(pa0, pb0),
        "A_only_stratum": (pa0 * strata["masks"]["a_only"]).astype(np.float32),
        "B_only_suppressed": (pa0 * (~strata["masks"]["b_only"])).astype(np.float32),
        "random": None,
    }
    arms = {}
    summary = {}
    for mode in ("hide", "tip"):
        mf = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                           seed=SEED, mode=mode)
        rows = []
        for f in mf:
            region, visible = f["region"], f["visible"] & valid
            legal = region & ~corridor      # emission-legal set. `visible` is the catalogue mask,
            #                                # not the grid: ANDing it here restricted every arm
            #                                # to still-mapped faults, which `mask_visible` then
            #        deleted -- every arm scored exactly 0.0000 on every fold.
            rng = np.random.default_rng(SEED + f["fold"])
            flat = np.flatnonzero(legal.ravel())
            # The random control is rebuilt at *each* budget: a single 37,654-cell draw scored
            # under a 15,000 label would not be a budget-matched control.
            for bud in BUDGETS:
                take = rng.choice(flat, min(bud, flat.size), replace=False)
                rnd = np.zeros(G.SHAPE, np.float32)
                rnd.ravel()[take] = 1.0
                for name, field in fields.items():
                    nodes = (rnd.astype(bool) if field is None else
                             h57.iso_select(field, legal & (field > 0), bud, min_px=3.0,
                                            nms_px=5))
                    p = HO.mask_visible(nodes.astype(np.float32), visible)
                    p = np.where(region, p, 0.0)
                    r = M.dti(p, f["truth"] & region & valid)
                    rows.append(dict(mode=mode, fold=f["fold"], budget=bud, arm=name,
                                     dti=round(r["dti"], 6), emitted=int((p > 0).sum()),
                                     tpw=round(r["tpw"], 2), fpw=round(r["fpw"], 2),
                                     fnw=round(r["fnw"], 2), n_truth=int(r["n_truth"])))
            log(f"{mode} fold {f['fold']}: " + ", ".join(
                f"{x['arm']}@37654={x['dti']:.4f}" for x in rows
                if x["fold"] == f["fold"] and x["budget"] == 37654))
        arms[mode] = rows
        summary[mode] = {}
        for name in sorted({x["arm"] for x in rows}):
            for bud in BUDGETS:
                v = [x["dti"] for x in rows if x["arm"] == name and x["budget"] == bud]
                if v:
                    summary[mode][f"{name}@{bud}"] = round(float(np.mean(v)), 6)
        # fold support of the best arm over the random control
        for bud in BUDGETS:
            base = {x["fold"]: x["dti"] for x in rows
                    if x["arm"] == "random" and x["budget"] == bud}
            for name in sorted({x["arm"] for x in rows}):
                if name == "random":
                    continue
                v = {x["fold"]: x["dti"] for x in rows
                     if x["arm"] == name and x["budget"] == bud}
                if v and base:
                    wins = sum(1 for fk in v if v[fk] > base.get(fk, -1))
                    summary[mode][f"folds_won_{name}@{bud}"] = f"{wins}/{len(v)}"

    np.save(WORK / "pa_oof.npy", pa_oof)
    np.save(WORK / "pb_oof.npy", pb_oof)
    EV = Path("evidence")
    EV.joinpath("h57_strata_masks_summary.json").write_text(json.dumps(
        dict(counts=strata["counts"], q_conf=Q_CONF, q_abstain=Q_ABSTAIN,
             median_depth_to_basement_m=strata["median_depth_to_basement_m"]), indent=1) + "\n")

    rep = dict(
        round="H57", seed=SEED, runtime_s=round(time.time() - t0, 1),
        fold_structure=dict(
            mode="whole 8-connected catalogue components assigned to the quadrant holding most "
                 "of their pixels; 4 px collar around the held quadrant and the footprint edge "
                 "excluded from fitting and from scoring; prevalence-matched whole-component truth",
            block_px=BLOCK, buffer_px=4, min_negatives_per_block=MIN_NEG),
        grid=dict(footprint_px=int(valid.sum()), catalogue_px=int(cat.sum()),
                  permitted_px=int(permitted.sum()),
                  corridor_m=h57.CORRIDOR_PX * G.PIXEL_M),
        view_a_layers=h57.VIEW_A_LAYERS, view_b_layers=h57.VIEW_B_LAYERS,
        layer_count=len(meta["names"]),
        folds=fold_receipts,
        independence=ind,
        strata={k: v for k, v in strata.items() if k != "masks"},
        pseudo_label=pseudo,
        arms=arms, arm_summary=summary,
        caveats=[
            "Both instruments score against a *proxy* truth (the mapped catalogue). knowledge/10 "
            "section 5 measures Spearman(reported score, simulated DTI) = -0.1045 (p=0.734, "
            "n=13): the simulator is NOT a proxy for the leaderboard and is used here only for "
            "RELATIVE comparisons between arms on identical rows and identical node budgets.",
            "No leaderboard score is read anywhere in this script.",
            "Catalogue-zero pixels are proxies for absence, not verified geological absence.",
        ])
    EV.joinpath("h57_cotrain.json").write_text(
        json.dumps(rep, indent=1, allow_nan=False, default=str) + "\n")
    log(f"wrote {OUT} in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())