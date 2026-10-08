#!/usr/bin/env python3
"""H57 stratification test — which agreement stratum should carry the novel arm?

`knowledge/17` split the unlabelled footprint into four agreement strata (A confident / B
abstains, and its mirror image, the concordant stratum, and the neither stratum) and proposed the
A-only stratum as the candidate population for a buried-fault arm.  `evidence/h57_validation.json`
ranks the *fields*; it does not answer this question.  This script does, under the same honest
protocol: candidates may not sit on the **visible** catalogue dilated by 2 px, the **held-out**
catalogue is the truth, so every credit number is credit earned on faults the model never saw.

It also re-measures the View A / View B / union fields at the artefact's own node budget, so the
arm population can be chosen from evidence rather than from the brief's hypothesis.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems52 import grid as G     # noqa: E402
from gems52 import h57           # noqa: E402
from gems52 import holdout as HO  # noqa: E402
from gems52 import metric as M    # noqa: E402

SEED = 20261007
BUDGETS = (15000,)
Q_CONF, Q_ABSTAIN = 0.60, 0.40


def log(m):
    print(f"[h57-strata {time.strftime('%H:%M:%S')}] {m}", flush=True)


def main() -> int:
    t0 = time.time()
    valid = G.footprint_from("data/training_features.tif", bands="all")
    with rasterio.open("data/labels.tif") as s:
        cat = s.read(1) == 1
    pa = np.nan_to_num(np.load("work/h57/pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load("work/h57/pb_oof.npy"), nan=0.0).astype(np.float32)
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor
    m = h57.disagreement(pa, pb, permitted)
    strata = m["masks"]

    results = []
    rng = np.random.default_rng(SEED)
    arms = {
        "random": None,
        "view_A": pa,
        "view_B": pb,
        "union": np.maximum(pa, pb),
        "S_a_only": np.where(strata["a_only"], pa, 0.0),
        "S_b_only": np.where(strata["b_only"], pb, 0.0),
        "S_concordant": np.where(strata["concordant"], np.maximum(pa, pb), 0.0),
        "S_neither": np.where(strata["neither"], np.maximum(pa, pb), 0.0),
    }
    for mode in ("tip", "hide"):
        folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                              seed=SEED, mode=mode)
        for f in folds:
            blocked = ndimage.binary_dilation(f["visible"] & valid,
                                              iterations=h57.CORRIDOR_PX)
            legal = f["region"] & permitted & ~blocked
            truth = f["truth"] & f["region"] & valid
            flat_pool = np.flatnonzero(legal.ravel())
            for k in BUDGETS:
                for name, fld in arms.items():
                    if fld is None:
                        take = rng.choice(flat_pool, min(k, flat_pool.size), replace=False)
                        nodes = np.zeros(G.SHAPE, bool)
                        nodes.ravel()[take] = True
                    else:
                        nodes = h57.iso_select(fld, legal & (fld > 0), k, min_px=3.0, nms_px=5)
                    p = np.where(f["region"], nodes.astype(np.float32), 0.0)
                    r = M.dti(p, truth)
                    results.append(dict(mode=mode, fold=f["fold"], budget=k, arm=name,
                                        dti=round(r["dti"], 6), emitted=int((p > 0).sum()),
                                        n_truth=int(r["n_truth"])))
                log(f"{mode} f{f['fold']} k={k}: " + ", ".join(
                    f"{r['arm']}={r['dti']:.4f}" for r in results
                    if r["mode"] == mode and r["fold"] == f["fold"] and r["budget"] == k))

    summary = {}
    for mode in ("tip", "hide"):
        summary[mode] = {}
        for name in arms:
            v = [r["dti"] for r in results if r["mode"] == mode and r["arm"] == name]
            summary[mode][name] = round(float(np.mean(v)), 6)

    combined = {name: round(float(np.mean([summary[m][name] for m in ("tip", "hide")])), 6)
                for name in arms}
    fold_support = {
        name: sum(1 for mo in ("tip", "hide") for fo in range(4)
                  if next(r["dti"] for r in results if r["mode"] == mo and r["fold"] == fo
                          and r["arm"] == name)
                  > next(r["dti"] for r in results if r["mode"] == mo and r["fold"] == fo
                         and r["arm"] == "random"))
        for name in arms}

    rep = dict(round="H57-strata", seed=SEED, runtime_s=round(time.time() - t0, 1),
               protocol=dict(budgets=list(BUDGETS), q_conf=Q_CONF, q_abstain=Q_ABSTAIN,
                             emitter="iso_select, min_px=3, nms_px=5",
                             candidate_pool="fold region & permitted & ~dilate(visible catalogue, "
                                            "2 px); truth is the held-out catalogue",
                             strata_definition="h57.disagreement on the out-of-fold View A and "
                                               "View B probabilities"),
               strata_px=m["counts"],
               results=results, summary=summary, combined=combined,
               folds_better_than_random={k: f"{v}/8" for k, v in fold_support.items()},
               caveats=[
                   "Held-out-catalogue credit is not unmapped-fault credit. A stratum can win here "
                   "and still be the wrong arm population for faults nobody has mapped.",
                   "knowledge/10 section 5: Spearman(reported score, simulated DTI) = -0.1045 "
                   "(p=0.734, n=13). Relative instrument only.",
               ])
    Path("evidence/h57_strata.json").write_text(
        json.dumps(rep, indent=1, allow_nan=False, default=str) + "\n")
    log("combined " + ", ".join(f"{k}={v}" for k, v in
                                sorted(combined.items(), key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())