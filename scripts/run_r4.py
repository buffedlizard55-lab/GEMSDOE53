#!/usr/bin/env python3
"""Round-4 pipeline driver.

Stages
------
    stack       build the 74 declared layers into work/cache/stack.f32
    rank        rank-encode every layer to [0,1] inside the footprint
    model       blocked out-of-fold AUC per view, and the independence verdict
    instrument  pseudo-truth assay, budget-confound test, uniform-random control
    arms        matched-budget hide-and-recover over 18 arms plus a random control
    bias        distance-to-catalogue histograms (the halo read-out)
    emit        build the submission raster from the winning arm
    gates       format, uniqueness and non-duplication checks
    reason      per-structure geological reasoning table

Two habits here are load-bearing and were learned by losing work to them:

* **Masks are written before the receipt.**  ``json.dumps(allow_nan=False)`` raises on
  the first NaN it meets, and an eight-minute run once died at the very last step with
  nothing on disk.  Every stage writes its arrays first and its receipt second.
* **Receipts go through ``jsonable``.**  A single NaN anywhere in a nested result becomes
  ``null`` rather than an exception.

``--reuse-oof`` and ``--reuse-cotrain`` skip refitting, because a full re-fit is tens of
minutes and the crash that used to follow it was usually a one-line bug in the code
*after* the fit.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from gems52.grid import PIXEL_M, write_geotiff          # noqa: E402
from gems52_r4 import arms as A                          # noqa: E402
from gems52_r4 import bias as B                          # noqa: E402
from gems52_r4 import cotraining as C                    # noqa: E402
from gems52_r4 import instrument as I                    # noqa: E402
from gems52_r4 import layers as L                        # noqa: E402
from gems52_r4 import model as M                         # noqa: E402
from gems52_r4 import reasoning as R                     # noqa: E402

CACHE = REPO / "work" / "cache"
EVID = REPO / "evidence"
LABELS = REPO / "data" / "labels.tif"
BUDGETS = (20_000, 37_654, 70_000)


def log(*a, **kw):
    print(*a, flush=True)


# --------------------------------------------------------------------------------------
# receipt hygiene
# --------------------------------------------------------------------------------------

def jsonable(o):
    """Recursively replace NaN/Inf with None and numpy scalars with Python ones."""
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if np.isfinite(f) else None
    if isinstance(o, (np.integer, int)) and not isinstance(o, bool):
        return int(o)
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if o is None or isinstance(o, str):
        return o
    return str(o)


def write_receipt(name: str, obj: dict) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / name
    p.write_text(json.dumps(jsonable(obj), indent=1, allow_nan=False, sort_keys=False) + "\n")
    log(f"  receipt -> {p}")
    return p


def _load_labels():
    import rasterio
    with rasterio.open(LABELS) as s:
        a = s.read(1)
    return a


def _catalogue(valid):
    lab = _load_labels()
    return (lab == 1) & valid


def _edt_to(mask: np.ndarray) -> np.ndarray:
    """Distance in metres to the nearest True pixel, NaN outside the footprint."""
    from scipy import ndimage
    d = ndimage.distance_transform_edt(~np.asarray(mask, dtype=bool))
    return (d * PIXEL_M).astype(np.float32)


# --------------------------------------------------------------------------------------
# stages
# --------------------------------------------------------------------------------------

def stage_stack(args):
    t0 = time.time()
    CACHE.mkdir(parents=True, exist_ok=True)
    meta = L.build_stack(out_dir=str(CACHE), log=log)
    write_receipt("r4_stack.json", {
        "stage": "stack",
        "n_layers": meta["n_layers"],
        "n_view_A": sum(1 for v in meta["view"] if v == "A"),
        "n_view_B": sum(1 for v in meta["view"] if v == "B"),
        "footprint_px": meta["footprint_px"],
        "layers": meta["layers"],
        "view": meta["view"],
        "seconds": round(time.time() - t0, 1),
    })


def stage_rank(args):
    t0 = time.time()
    stats = M.rank_stack(str(CACHE), log=log)
    (CACHE / "rank_stats.json").write_text(json.dumps(jsonable(stats), indent=1))
    write_receipt("r4_rank.json", {
        "stage": "rank", "n_layers": len(stats),
        "layers_with_nans": [k for k, v in stats.items() if v["finite_frac"] < 0.999],
        "seconds": round(time.time() - t0, 1),
    })


def _sample(valid, catalogue, exclude=None, seed=20261008, max_pos=60_000, neg_per_pos=4):
    pos = catalogue.copy()
    neg = valid & ~catalogue
    if exclude is not None:
        pos &= ~exclude
        neg &= ~exclude
    return M.sample_training(pos, neg, max_pos=max_pos, neg_per_pos=neg_per_pos, seed=seed)


def stage_model(args):
    t0 = time.time()
    stack, meta = M.open_stack(str(CACHE), ranked=True)
    valid = np.load(CACHE / "footprint.npy")
    cat = _catalogue(valid)
    bid = M.block_ids(valid.shape, valid, 20_000.0)
    np.save(CACHE / "bid.npy", bid)
    fold = M.make_block_folds(bid, 5)
    np.save(CACHE / "fold.npy", fold)
    idxA = L.view_indices(meta, "A")
    idxB = L.view_indices(meta, "B")
    sample = _sample(valid, cat)
    np.save(CACHE / "sample_rows.npy", sample["rows"])
    np.save(CACHE / "sample_cols.npy", sample["cols"])
    np.save(CACHE / "sample_y.npy", sample["y"])

    res = {"stage": "model", "n_blocks": int(bid.max()) + 1,
           "footprint_px": int(valid.sum()), "catalogue_px": int(cat.sum()),
           "n_train": int(sample["y"].size), "n_pos": sample["n_pos"],
           "n_neg": sample["n_neg"], "n_layers_A": len(idxA), "n_layers_B": len(idxB)}
    oof = {}
    for tag, idx in (("A", idxA), ("B", idxB)):
        log(f"  fitting view {tag} ({len(idx)} layers)")
        r = M.fit_view(stack, idx, sample, bid, fold, log=log)
        oof[tag] = r["oof"]
        np.save(CACHE / f"oof_{tag}.npy", r["oof"])
        np.save(CACHE / f"oof_{tag}_rows.npy", r["oof_rows"])
        np.save(CACHE / f"oof_{tag}_cols.npy", r["oof_cols"])
        np.save(CACHE / f"full_{tag}.npy",
                M.full_fit_predict(stack, idx, r["model"], valid, log=log))
        res[f"view_{tag}"] = {"blocked_auc": r["blocked_auc"]["mean_auc"],
                              "median_block_auc": r["blocked_auc"]["median_auc"],
                              "n_blocks_scored": r["blocked_auc"]["n_blocks_scored"],
                              "n_blocks_skipped": r["blocked_auc"]["n_blocks_skipped"]}
        log(f"    view {tag} blocked OOF AUC = {r['blocked_auc']['mean_auc']:.4f}")

    ind = C.independence_verdict(oof["A"], oof["B"], np.asarray(bid)[sample["rows"], sample["cols"]])
    res["independence"] = ind
    log(f"  independence: max|rho|={ind.get('max_abs_rho')} -> {ind.get('verdict')}")

    ra = C._rank_within(oof["A"], np.ones_like(oof["A"], dtype=bool))
    rb = C._rank_within(oof["B"], np.ones_like(oof["B"], dtype=bool))
    res["strata_px"] = {
        "A_only": int(((ra >= 0.9) & (rb < 0.9)).sum()),
        "B_only": int(((rb >= 0.9) & (ra < 0.9)).sum()),
        "both": int(((ra >= 0.9) & (rb >= 0.9)).sum()),
        "neither": int(((ra < 0.9) & (rb < 0.9)).sum()),
    }
    res["seconds"] = round(time.time() - t0, 1)
    write_receipt("r4_model.json", res)


def stage_instrument(args):
    """Pseudo-truth assay, budget confound, and the random control that judges it all."""
    t0 = time.time()
    valid = np.load(CACHE / "footprint.npy")
    cat = _catalogue(valid)
    out = {"stage": "instrument", "catalogue_px": int(cat.sum())}
    for mode in ("dispersed", "clustered"):
        t = I.build_pseudo_truth(cat, valid, seed=52008, mode=mode)
        np.save(CACHE / f"pseudotruth_{mode}.npy", t["G"])
        out[mode] = {k: v for k, v in t.items() if k != "G"}
        log(f"  {mode}: |G*|={t['size_px']} hidden={t['n_hidden']} kept={t['n_kept']}")

    # score the incumbent and a uniform-random control against the dispersed G*
    g = np.load(CACHE / "pseudotruth_dispersed.npy")
    rows = []
    champ = REPO / "data" / "reference" / "h33-2-b2-zeros.tif"
    if champ.exists():
        e = I.load_emission(str(champ))
        r = I.score_against(e["field"], g)
        rows.append({"name": "h33-2-b2", "score": r["dti"], "board": 0.2778,
                     "budget": r["budget"], "kind": "incumbent"})
        log(f"  incumbent on G*: dti={r['dti']:.6f} budget={r['budget']}")
    for k in BUDGETS:
        rng = np.random.default_rng(20261008)
        idx = np.flatnonzero(valid.ravel())
        pick = rng.choice(idx, size=min(k, idx.size), replace=False)
        f = np.zeros(valid.shape, dtype=np.float32)
        f.ravel()[pick] = 1.0
        r = I.score_against(f, g)
        rows.append({"name": f"random_{k}", "score": r["dti"], "board": 0.0,
                     "budget": r["budget"], "kind": "random"})
        log(f"  random@{k}: dti={r['dti']:.6f}")
    val = I.validate(rows) if len(rows) >= 3 else {"n": len(rows), "ok": False}
    out["validation"] = val
    out["rows"] = rows
    out["seconds"] = round(time.time() - t0, 1)
    write_receipt("r4_instrument.json", out)


def stage_arms(args):
    """Matched-budget hide-and-recover for 18 arms plus a uniform-random control."""
    t0 = time.time()
    stack, meta = M.open_stack(str(CACHE), ranked=True)
    valid = np.load(CACHE / "footprint.npy")
    cat = _catalogue(valid)
    idxA = L.view_indices(meta, "A")
    idxB = L.view_indices(meta, "B")
    folds = C.whole_segment_folds(cat, valid, buffer_px=20, k=4)
    log(f"  {len(folds)} whole-segment folds")
    res = {"stage": "arms", "n_folds": len(folds), "budgets": list(BUDGETS),
           "per_fold": [], "arms": {}}

    for f in folds:
        held = f["truth"]
        cat_visible = cat & ~held
        # the held segment is removed from the catalogue used to build the 200 m
        # exclusion, otherwise the holdout asks the emitter to place pixels it is
        # forbidden to place and survival is zero by construction
        edt_vis = _edt_to(cat_visible)
        allowed = valid & (edt_vis >= 200.0)
        surv = float(allowed[held].mean())
        log(f"  fold {f['fold']}: truth={f['n_truth']} survival={surv:.4f}")
        if surv < 0.9:
            raise RuntimeError(f"fold {f['fold']} truth survival {surv:.4f} < 0.9")
        sample = _sample(valid, cat_visible, exclude=f["train_exclude"],
                         seed=20261008 + f["fold"])
        bid = np.load(CACHE / "bid.npy")
        flat_fold = np.zeros(valid.shape, dtype=np.int8)   # no inner CV here
        pa = M.fit_view(stack, idxA, sample, bid, flat_fold, log=lambda *a, **kw: None, cv=False)
        pb = M.fit_view(stack, idxB, sample, bid, flat_fold, log=lambda *a, **kw: None, cv=False)
        fa = M.full_fit_predict(stack, idxA, pa["model"], valid, log=lambda *a, **kw: None)
        fb = M.full_fit_predict(stack, idxB, pb["model"], valid, log=lambda *a, **kw: None)
        np.save(CACHE / f"fold{f['fold']}_A.npy", fa)
        np.save(CACHE / f"fold{f['fold']}_B.npy", fb)
        res["per_fold"].append({"fold": f["fold"], "n_truth": f["n_truth"],
                                "truth_survival": surv,
                                "n_allowed": int(allowed.sum()),
                                "n_train": int(sample["y"].size)})

        for name in A.arm_names() + ["random"]:
            if name == "random":
                # ONE field of iid uniform scores over every allowed pixel: its top-k
                # is then a uniform random subset of size k for every k at once.
                # Generating the control at a single fixed budget made it understate
                # random at budgets above that size.
                field = A.random_control(valid.shape, allowed, int(allowed.sum()),
                                         seed=20261008 + f["fold"])
            else:
                field = A.build_arm(name, fa, fb)
            field = np.where(allowed, field, np.nan)
            rec = _recovery(field, held, allowed, BUDGETS)
            res["arms"].setdefault(name, []).append(rec)
        del fa, fb, pa, pb
        log(f"    fold {f['fold']} done")

    summary = {}
    for name, per in res["arms"].items():
        means = []
        for b in BUDGETS:
            vals = [p[b]["capture"] for p in per if p[b]["capture"] is not None]
            means.append(float(np.mean(vals)) if vals else None)
        summary[name] = {"mean_capture_by_budget": means,
                         "overall_mean": float(np.nanmean([m for m in means if m is not None]))}
    res["summary"] = summary
    ranked = sorted(summary.items(), key=lambda kv: -(kv[1]["overall_mean"] or -1))
    log("  arm ranking by mean capture:")
    for n, s in ranked:
        log(f"    {n:24s} {s['overall_mean']:.5f}")
    res["seconds"] = round(time.time() - t0, 1)
    write_receipt("r4_arms.json", res)


def _recovery(field, truth, allowed, budgets):
    """Fraction of held-out truth recovered at each matched budget."""
    r = C._rank_within(field, allowed)
    n_truth = int(truth.sum())
    out = {}
    for k in budgets:
        picked = C.topk_mask(r, allowed, int(k))
        if n_truth == 0 or not picked.any():
            out[k] = {"capture": None, "picked": 0}
            continue
        out[k] = {"capture": float((picked & truth).sum()) / n_truth,
                  "picked": int(picked.sum())}
    return out


def stage_bias(args):
    t0 = time.time()
    valid = np.load(CACHE / "footprint.npy")
    cat = _catalogue(valid)
    edt = _edt_to(cat)
    np.save(CACHE / "edt_cat.npy", edt)
    res = {"stage": "bias", "catalogue_px": int(cat.sum())}
    res["champion"] = None
    champ = REPO / "data" / "reference" / "h33-2-b2-zeros.tif"
    if champ.exists():
        e = I.load_emission(str(champ))
        res["champion"] = {"budget": e["budget"],
                           "hist": B.distance_histogram(e["mask"], edt)}
    fa = CACHE / "full_A.npy"
    fb = CACHE / "full_B.npy"
    for tag, p in (("A", fa), ("B", fb)):
        if not p.exists():
            continue
        f = np.load(p)
        for k in BUDGETS:
            r = C._rank_within(f, valid)
            thr = C._threshold_for_topk(r, valid, int(k))
            if thr is None:
                continue
            m = valid & (r >= thr)
            res[f"view_{tag}@{k}"] = B.distance_histogram(m, edt)
    res["seconds"] = round(time.time() - t0, 1)
    write_receipt("r4_bias.json", res)


def stage_emit(args):
    """Emit the winning arm at the target budget."""
    t0 = time.time()
    valid = np.load(CACHE / "footprint.npy")
    cat = _catalogue(valid)
    edt = _edt_to(cat)
    arms_receipt = EVID / "r4_arms.json"
    if not arms_receipt.exists():
        raise RuntimeError("run --stage arms first")
    ar = json.loads(arms_receipt.read_text())
    ranked = sorted(ar["summary"].items(), key=lambda kv: -(kv[1]["overall_mean"] or -1))
    best = ranked[0][0]
    log(f"  winning arm: {best}")
    stack, meta = M.open_stack(str(CACHE), ranked=True)
    idxA = L.view_indices(meta, "A")
    idxB = L.view_indices(meta, "B")
    sample = _sample(valid, cat)
    bid = np.load(CACHE / "bid.npy")
    flat = np.zeros(valid.shape, dtype=np.int8)
    pa = M.fit_view(stack, idxA, sample, bid, flat, log=lambda *a, **kw: None, cv=False)
    fa = M.full_fit_predict(stack, idxA, pa["model"], valid, log=lambda *a, **kw: None)
    pb = M.fit_view(stack, idxB, sample, bid, flat, log=lambda *a, **kw: None, cv=False)
    fb = M.full_fit_predict(stack, idxB, pb["model"], valid, log=lambda *a, **kw: None)
    field = A.random_control(valid.shape, valid, args.budget) if best == "random" \
        else A.build_arm(best, fa, fb)
    allowed = valid & (edt >= 200.0)
    field = np.where(allowed, field, np.nan)
    r = C._rank_within(field, allowed)
    mask = C.topk_mask(r, allowed, args.budget)
    out = np.where(mask, 1.0, 0.0).astype(np.float32)
    name = f"gems52-r4-{best}-{args.budget}px-{args.tag}.tif"
    dest = REPO / "submission" / name
    info = write_geotiff(str(dest), out, nodata=0.0)
    res = {"stage": "emit", "arm": best, "budget": args.budget,
           "n_px": int(mask.sum()), "raster": name, "sha256": info.get("sha256"),
           "bytes": info.get("bytes") if isinstance(info, dict) else None,
           "arm_mean_capture": ar["summary"][best]["overall_mean"],
           "random_mean_capture": ar["summary"].get("random", {}).get("overall_mean"),
           "beats_random": bool(ar["summary"][best]["overall_mean"] >
                                (ar["summary"].get("random", {}).get("overall_mean") or 0)),
           "seconds": round(time.time() - t0, 1)}
    write_receipt("r4_emit.json", res)
    log(f"  wrote {dest} ({int(mask.sum())} px)")


def stage_gates(args):
    t0 = time.time()
    import rasterio
    er = json.loads((EVID / "r4_emit.json").read_text())
    p = REPO / "submission" / er["raster"]
    with rasterio.open(p) as s:
        a = s.read(1)
        prof = {"count": s.count, "dtype": s.dtypes[0], "crs": str(s.crs),
                "shape": list(s.shape), "nodata": s.nodatavals[0]}
    valid = np.load(CACHE / "footprint.npy")
    cat = _catalogue(valid)
    edt = _edt_to(cat)
    vals = np.unique(a)
    finite = bool(np.isfinite(a).all())
    binary = bool(set(np.unique(a)).issubset({0.0, 1.0}))
    m = a > 0
    min_d = float(edt[m].min()) if m.any() else None
    res = {"stage": "gates", "raster": er["raster"], "profile": prof,
           "checks": {
               "single_band": prof["count"] == 1,
               "all_finite": finite,
               "binary_0_1": binary,
               "shape_matches_grid": list(s.shape) == list(valid.shape),
               "crs_is_32611": "32611" in prof["crs"],
               "no_pixel_within_200m_of_catalogue": bool(min_d is None or min_d >= 200.0),
               "budget_matches": int(m.sum()) == int(er["n_px"]),
           },
           "n_px": int(m.sum()), "min_distance_to_catalogue_m": min_d,
           "unique_values": [float(v) for v in vals]}
    res["passes"] = all(res["checks"].values())
    res["seconds"] = round(time.time() - t0, 1)
    write_receipt("r4_gates.json", res)
    log(f"  gates pass={res['passes']}")
    if not res["passes"]:
        for k, v in res["checks"].items():
            if not v:
                log(f"    FAILED: {k}")


def stage_reason(args):
    t0 = time.time()
    er = json.loads((EVID / "r4_emit.json").read_text())
    import rasterio
    with rasterio.open(REPO / "submission" / er["raster"]) as s:
        a = s.read(1)
    mask = a > 0
    valid = np.load(CACHE / "footprint.npy")
    stack, meta = M.open_stack(str(CACHE), ranked=True)
    edt = np.load(CACHE / "edt_cat.npy") if (CACHE / "edt_cat.npy").exists() \
        else _edt_to(_catalogue(valid))
    fullB = np.load(CACHE / "full_B.npy") if (CACHE / "full_B.npy").exists() else None
    rows = R.reason_table(mask, stack, meta, edt, valid, score=fullB)
    csv_path = R.write_csv(str(EVID / "r4_reason.csv"), rows)
    res = {"stage": "reason", "n_structures": len(rows), "csv": str(Path(csv_path).name),
           "rows": rows[:50], "seconds": round(time.time() - t0, 1)}
    write_receipt("r4_reason.json", res)
    log(f"  {len(rows)} structures -> {csv_path}")


STAGES = {
    "stack": stage_stack, "rank": stage_rank, "model": stage_model,
    "instrument": stage_instrument, "arms": stage_arms, "bias": stage_bias,
    "emit": stage_emit, "gates": stage_gates, "reason": stage_reason,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", required=True, choices=sorted(STAGES))
    ap.add_argument("--budget", type=int, default=37_654)
    ap.add_argument("--tag", default="r4")
    args = ap.parse_args()
    log(f"=== R4 stage: {args.stage} ===")
    STAGES[args.stage](args)
    log(f"=== done: {args.stage} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
