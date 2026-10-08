#!/usr/bin/env python3
"""GEMSDOE52 pipeline: two-view co-training, disagreement strata, metric-aware emission.

Stages
------
``fit``      build the uint8 feature stack, make blocked folds, fit each view and one co-training
             round, write out-of-fold scores, run the conditional-independence test, measure the
             physical meaning of the disagreement strata.
``validate`` score arms on the blocked folds (co-train vs A-only vs B-only vs combinations vs random)
             and the emission budget grid.  Nothing is promoted here that does not beat the
             holdout best.
``emit``     fit on everything, build the field, emit under the metric's own acceptance rule,
             write the candidate raster + its evidence record.

Run:  PYTHONPATH=src python3 -u scripts/run_pipeline.py --stage fit --rounds 1
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

from gems52 import cotrain as CT                      # noqa: E402
from gems52 import emit as EM                         # noqa: E402
from gems52 import grid as GR                         # noqa: E402
from gems52 import holdout as HO                      # noqa: E402
from gems52 import metric as M                        # noqa: E402

DER = ROOT / "work/derived"
WORK = ROOT / "work"
EV = ROOT / "evidence"
PRED = WORK / "fold_preds"
G_LO, G_HI = 5764, 15179                 # |G| bracket implied by the organiser's published scores
DTI_PROJECTED = 0.28                     # what we expect the submission to score; sets the bar
MODE = "tip"          # which holdout instrument; see gems52.holdout for hide/block/tip
N_FOLDS = 4

# The 27 layers that scripts/prepare_data.py + src/gems52/features.py actually wrote to
# work/derived (19 geophysical = View A, 8 surface = View B).  Names are the file stems; build_stack
# rank-transforms each one, so double-ranked layers (``*_rank``) are harmless.
A_FEATS = ["A_mag_edge_vg", "A_mag_step", "A_mag_strike", "A_grav_step", "A_grav_edge",
           "A_grav_strike", "A_strain_inv_reg", "A_shear_rank", "A_strain_inv_rank",
           "A_grav_vg_rank", "A_grav_hg_rank", "A_rtp_rank", "A_cond_rank", "A_depth_base_rank",
           "A_eqdens_rank", "A_eqdist_negrank", "A_grav_slope_band", "A_mag_tilt_abs",
           "A_dilate_rank"]
B_FEATS = ["B_scarp_p900", "B_scarp_p300", "B_scarp_fine", "B_scarp_strike", "B_slope_rank",
           "B_elev_grad", "B_line_resp", "B_elev_rank"]

# -----------------------------------------------------------------------------------------------
# pre-registration: written to disk before any fold is scored, so the decision rule cannot drift
# -----------------------------------------------------------------------------------------------
PREREG = {
    "version": "GEMSDOE52-prereg-1",
    "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "hypotheses": [
        "H1 A-only stratum = range-front fault buried under fan/gravel cover: recoverable from "
        "potential fields, invisible to LiDAR, therefore absent from the catalogue",
        "H2 concordant stratum (both views agree) is precision mass already mostly catalogued; "
        "its value is off-trace continuation, not the trace itself",
        "H3 B-only stratum = surface artefact (roads, canal levees, erosion, quarry scarps); "
        "down-weighted, not deleted, because its measured precision is the evidence",
        "H4 co-training gain requires conditional independence of the two views' errors given the "
        "catalogue label; if |r| >= 0.60 on blocked out-of-fold errors the whole method is void",
        "H5 emission must obey the metric's marginal acceptance rule k > alpha*DTI, so the budget is "
        "chosen on prevalence-matched folds and never inherited from a sibling project",
    ],
    "primary_metric": "official DTI (gems52.metric.official_dti) on blocked folds, catalogue-masked",
    "acceptance_rule": "emission accept iff gain(x) > alpha*DTI/(1-alpha*DTI) * (1 - wmax(x))",
    "gates": {
        "independence_abs_pearson_max": 0.60,
        "fold_dti_must_beat_union_baseline_by": 0.010,
        "pooled_dti_must_beat_sibling_best": 0.05,
        "min_fold_uplift_pct": 25,
        "fold_support_min": 3,
    },
    "abstain_q": 0.60,          # "withholds" threshold: view score at or below the 60th pct
    "conf_quantile": 0.995,     # "confident" tail used for pseudo-labels
    "w_b_only": 0.25,           # B-only mass kept, not deleted (H3)
    "prevalence_used": 0.002,   # mid-bracket |G|/footprint for fold thinning
    "budget_grid": [8000, 15000, 25000, 37654],
    "field_weights": {"A": 0.55, "B": 0.20, "concordance": 0.25, "A_only_bonus": 0.30},
}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# -----------------------------------------------------------------------------------------------
# data loading
# -----------------------------------------------------------------------------------------------
def get_layer(name: str) -> np.ndarray:
    return np.load(DER / f"{name}.npy", mmap_mode="r")[:]


def load_valid_cat() -> tuple[np.ndarray, np.ndarray]:
    valid = np.load(DER / "valid_footprint.npy")
    with rasterio.open(ROOT / "data/labels.tif") as src:
        cat = (src.read(1) == 1) & valid
    return valid, cat


# -----------------------------------------------------------------------------------------------
# the field: ranks of both views, disagreement-stratum aware, monotone, scale-free
# -----------------------------------------------------------------------------------------------
def rank_pct(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Percentile rank inside the footprint, float32 in [0,1]."""
    v = np.asarray(a, dtype=np.float32)[valid]
    order = np.argsort(v, kind="stable")
    r = np.empty(v.size, dtype=np.float32)
    r[order] = np.arange(v.size, dtype=np.float32) / max(v.size - 1, 1)
    out = np.zeros(a.shape, dtype=np.float32)
    out[valid] = r
    return out


def local_centre(f: np.ndarray, valid: np.ndarray, box_px: int = 30) -> np.ndarray:
    """Subtract the smoothed regional background.  This is the single biggest lever we found.

    A global rank field has its maximum wherever the *terrain style* matches the catalogue average,
    which for a potential-field survey means the big anomaly high, not the next fault: GEMSDOE45 hit
    this as "off-catalogue selection measures is-this-a-mountain", and our first fold table reproduced
    it (top-K of the unfused field scored *below* uniform-random emission at the same budget, because
    all the mass landed in one cluster).  Subtracting a 3 km box mean keeps the *local* contrast -
    which is what a 100 m fault step is - and removes the regional term that carries no fault
    information at 300 m scale.
    """
    from scipy import ndimage
    a = np.where(valid, np.nan_to_num(f, nan=0.0), np.nan)
    bg = ndimage.uniform_filter(np.nan_to_num(a, nan=0.0), size=box_px, mode="nearest")
    cnt = ndimage.uniform_filter(valid.astype(np.float32), size=box_px, mode="nearest")
    bg = np.where(cnt > 0.02, bg / np.maximum(cnt, 1e-6), 0.0)
    return np.where(valid, a - bg, 0.0).astype(np.float32)


def field_from_probs(pA: np.ndarray, pB: np.ndarray, strata: np.ndarray, valid: np.ndarray,
                     mode: str = "cotrain") -> tuple[np.ndarray, dict]:
    """Combine the two views into a discovery field.  Everything happens in percentile-rank space, so
    no arm depends on either view's calibration, and every arm is a stated function of the same two
    ranked grids — which is what makes the arm table an apples-to-apples comparison.

    ``mode``
      a_only / b_only             single-view baselines: the hide-and-recover control the brief asks for
      union / mean / product      naive "agree more" combinations, i.e. the same information with no
                                  disagreement term; if the stratum field does not beat these, the
                                  disagreement is decoration
      wt:<wA>:<wB>[:<wmin>]       an explicit linear combination, so the blend weights become a swept,
                                  *measured* parameter instead of an assertion
      cotrain                     concordant base + A-only discovery bonus, B-only mass down-weighted
      any name + "_lc"            the same thing after regional-background removal (see local_centre)
    """
    fw = PREREG["field_weights"]
    lc = mode.endswith("_lc")
    base = mode[:-3] if lc else mode
    rA = rank_pct(pA, valid)
    rB = rank_pct(pB, valid)
    if lc:                       # local-centre *before* combining, so a blend is not driven by both
        rA = local_centre(rA, valid)   # views sitting on the same regional anomaly high
        rB = local_centre(rB, valid)
    if base.startswith("wt:"):
        parts = [float(x) for x in base.split(":")[1:]]
        while len(parts) < 3:
            parts.append(0.0)
        wa, wb, wm = parts[:3]
        f = wa * rA + wb * rB + wm * np.minimum(rA, rB)
        weights = (wa, wb, wm)
    elif base == "a_only":
        f, weights = rA, (1.0, 0.0, 0.0)
    elif base == "b_only":
        f, weights = rB, (0.0, 1.0, 0.0)
    elif base == "union":
        f, weights = np.maximum(rA, rB), ("max", 0, 0)
    elif base == "mean":
        f, weights = 0.5 * (rA + rB), (0.5, 0.5, 0.0)
    elif base == "product":
        f, weights = rA * rB, ("prod", 0, 0)
    elif base == "cotrain":
        f = (fw["A"] * rA + fw["B"] * rB + fw["concordance"] * np.minimum(rA, rB)
             + (strata == 2) * (fw["A_only_bonus"] * rA))          # buried-corridor arm (H52-1)
        f = np.where(strata == 3, f * PREREG["w_b_only"], f)        # suspect surface arm (H52-3)
        weights = (fw["A"], fw["B"], fw["concordance"])
    else:
        raise ValueError(mode)
    f = np.where(valid, np.nan_to_num(f, nan=0.0, neginf=0.0, posinf=0.0), 0.0).astype(np.float32)
    return f, dict(mode=mode, weights=[w for w in weights], lc=bool(lc), lc_box_px=30 if lc else None,
                   sum=float(f.sum()), max=float(f.max()), min=float(f.min()),
                   n_positive=int((f > 0).sum()))


# -----------------------------------------------------------------------------------------------
# stage: fit
# -----------------------------------------------------------------------------------------------
def stage_fit(rounds: int, n_folds: int) -> dict:
    EV.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    (ROOT / "registry").mkdir(parents=True, exist_ok=True)
    (ROOT / "registry/preregistration.json").write_text(json.dumps(PREREG, indent=1) + "\n")
    log("pre-registration written: registry/preregistration.json")

    valid, cat = load_valid_cat()
    n = valid.size
    log(f"footprint {int(valid.sum())} px; catalogue {int(cat.sum())} px "
        f"({100.0 * cat.sum() / valid.sum():.4f} % of footprint)")

    stack = CT.build_stack_from_dir(DER, A_FEATS + B_FEATS, valid)
    np.save(WORK / "stack.npy", stack)
    log(f"stack {stack.shape} cols={A_FEATS + B_FEATS}")

    cols_a = list(range(len(A_FEATS)))
    cols_b = list(range(len(A_FEATS), len(A_FEATS) + len(B_FEATS)))

    folds = HO.make_folds(cat, valid, n_folds=n_folds, buffer_px=4,
                          prevalence=PREREG["prevalence_used"], seed=0, mode=MODE)
    (EV / f"folds_{MODE}.json").write_text(json.dumps(
        [{k: v for k, v in f.items() if not isinstance(v, np.ndarray)} for f in folds], indent=1))
    for f in folds:
        log(f"  fold {f['fold']} [{f['mode']}]: held {f['n_held']} px, truth {f['n_truth']} px, "
            f"fit {int(f['fit'].sum())} px")

    oof = {k: np.zeros(n, dtype=np.float32) for k in ("a0", "b0", "a1", "b1")}
    strat_oof = np.full(n, -1, dtype=np.int8)          # -1 = not out-of-fold, else stratum code
    held_mask = np.zeros(n, dtype=bool)
    rng = np.random.default_rng(0)
    from scipy import ndimage as _nd
    near_cat = _nd.binary_dilation(cat, structure=np.ones((3, 3), bool), iterations=CT.NEG_COLLAR_PX)
    per_fold = []
    for f in folds:
        fit = f["fit"]
        rows_pos = np.flatnonzero((cat & fit).ravel())
        pool = np.flatnonzero((fit & ~cat & ~near_cat).ravel())
        neg = rng.choice(pool, size=min(20 * rows_pos.size, pool.size), replace=False)
        va = CT.View("A", cols_a)
        vb = CT.View("B", cols_b)
        res = CT.co_train(stack, (va, vb), rows_pos, neg, fit, cat, valid, rounds=rounds,
                          conf_q=PREREG["conf_quantile"], seed=f["fold"], log=lambda *a: None)
        reg = (f["region"] & valid).ravel()
        held = (f["truth"] & f["region"] & valid).ravel()
        for k, src in (("a0", res.p_a0), ("b0", res.p_b0), ("a1", res.p_a), ("b1", res.p_b)):
            oof[k][held] = src[held]
        # Persist this fold's *whole-grid* predictions so arms/budgets can be re-scored without
        # refitting.  uint16 quantisation: 49 MB -> 24 MB per grid, and a 65536-level score
        # resolution is finer than any decision the emission rule can make.
        PRED.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(PRED / f"{MODE}_fold{f['fold']}.npz",
                            **{k: (np.clip(src.reshape(valid.shape), 0.0, 1.0) * 65535.0
                                  ).astype(np.uint16)
                               for k, src in (("a0", res.p_a0), ("b0", res.p_b0),
                                              ("a1", res.p_a), ("b1", res.p_b))})
        st_o = CT.strata(res.p_a0, res.p_b0, f["region"] & valid,
                         q_conf=0.98, q_abstain_hi=PREREG["abstain_q"])
        sm = st_o["mask"].ravel()
        strat_oof[held] = sm[held]
        held_mask[held] = True
        entry = dict(fold=f["fold"], mode=f["mode"], n_truth=int(f["n_truth"]),
                     n_held=int(f["n_held"]), n_pos=int(rows_pos.size), n_neg=int(neg.size),
                     auc_a0=CT.view_auc(res.p_a0[reg], cat.ravel()[reg]),
                     auc_b0=CT.view_auc(res.p_b0[reg], cat.ravel()[reg]),
                     auc_a1=CT.view_auc(res.p_a[reg], cat.ravel()[reg]),
                     auc_b1=CT.view_auc(res.p_b[reg], cat.ravel()[reg]),
                     n_pseudo_a=int(res.pseudo_a.size), n_pseudo_b=int(res.pseudo_b.size),
                     rounds_log=res.rounds, notes=res.notes,
                     coef_A=va.coef_report(), coef_B=vb.coef_report())
        log(f"  fold {f['fold']}: AUC A {entry['auc_a0']:.4f}->{entry['auc_a1']:.4f}  "
            f"B {entry['auc_b0']:.4f}->{entry['auc_b1']:.4f}  pseudo "
            f"{entry['n_pseudo_a']}/{entry['n_pseudo_b']}"
            + ("  " + ";".join(res.notes) if res.notes else ""))
        per_fold.append(entry)

    for k, v in oof.items():
        np.save(WORK / f"oof_{k}.npy", v)
    np.save(WORK / "strata.npy", strat_oof)
    np.save(WORK / "held_mask.npy", held_mask)

    ind = independence_report(oof, strat_oof, held_mask, cat, valid)
    verdict = _independence_verdict(ind, per_fold)
    ind["decision"] = verdict
    (EV / f"independence_{MODE}.json").write_text(json.dumps(ind, indent=1) + "\n")
    log(f"lift gate: {verdict['reading'][:120]}")
    log(f"  held-positive logit corr {ind['pearson_logit_held_positives']}, "
        f"block-level (needs fold grids; see holdout_{MODE}.json)")

    dep = deploy(stack, cat, valid, rounds=rounds, cols=(cols_a, cols_b))
    so = strat_oof.reshape(valid.shape)
    meas = measure_strata(dep["strata"]["mask"], cat, valid)
    (EV / f"strata_{MODE}.json").write_text(json.dumps(
        {**meas, "oof_strata_n_held": int(held_mask.sum()),
         "A_only_is_buried": _buried_evidence(dep["strata"]["mask"], valid, cat),
         "B_only_is_artifact": _artifact_evidence(dep["strata"]["mask"], valid, cat)},
        indent=1) + "\n")
    (WORK / f"meta_{MODE}.json").write_text(json.dumps(
        dict(mode=MODE, n_folds=n_folds, rounds=rounds, cols=A_FEATS + B_FEATS,
             footprint=int(valid.sum()), catalogue=int(cat.sum()),
             prereg=PREREG["version"]), indent=1) + "\n")
    (EV / f"co_train_folds_{MODE}.json").write_text(json.dumps(per_fold, indent=1) + "\n")
    return dict(per_fold=per_fold, independence=ind, strata=meas)


def deploy(stack: np.ndarray, cat: np.ndarray, valid: np.ndarray, rounds: int = 1,
           cols: tuple[list[int], list[int]] | None = None) -> dict:
    """Fit on *everything* the way the submission must be fitted, and keep the parts.

    The fold loop answers "does the method generalise"; it cannot also measure what the strata mean
    physically, because an out-of-fold pixel is by construction a pixel the model was not shown.
    Those measurements need the deployed model, so this is the one fit that uses every catalogue
    pixel and every footprint pixel.  Its predictions are never scored - the fold numbers are.
    """
    cols_a, cols_b = cols or (list(range(19)), list(range(19, 27)))
    rng = np.random.default_rng(1)
    pos, neg = CT.labelled_sets(cat, valid, rng, neg_per_pos=20)
    va = CT.View("A", cols_a).fit(stack, np.concatenate([pos, neg]),
                                 np.concatenate([np.ones(pos.size, np.int8),
                                                 np.zeros(neg.size, np.int8)]), 1)
    vb = CT.View("B", cols_b).fit(stack, np.concatenate([pos, neg]),
                                 np.concatenate([np.ones(pos.size, np.int8),
                                                 np.zeros(neg.size, np.int8)]), 1)
    res = CT.co_train(stack, (va, vb), pos, neg, valid, cat, valid, rounds=rounds,
                      conf_q=PREREG["conf_quantile"], seed=1, log=lambda *a: None)
    st = CT.strata(res.p_a0, res.p_b0, valid, q_conf=0.98, q_abstain_hi=PREREG["abstain_q"])
    np.savez_compressed(WORK / f"deploy_{MODE}.npz", p_a0=res.p_a0, p_b0=res.p_b0, p_a1=res.p_a,
                        p_b1=res.p_b, strata=st["mask"],
                        coef_a=np.array(va.coef_report()["coef"], dtype=np.float32),
                        coef_b=np.array(vb.coef_report()["coef"], dtype=np.float32),
                        cols_a=np.array(cols_a), cols_b=np.array(cols_b))
    log(f"deploy: AUC A {res.rounds[0]['auc_a']:.4f}->"
        f"{res.rounds[-1]['auc_a']:.4f}  B {res.rounds[0]['auc_b']:.4f}->"
        f"{res.rounds[-1]['auc_b']:.4f}  pseudo {res.pseudo_a.size}/{res.pseudo_b.size}")
    return dict(strata=st, res=res, va=va, vb=vb, thresholds=st["thresholds"])


def _odds(p: np.ndarray, eps: float) -> np.ndarray:
    p = np.clip(p, eps, 1 - eps)
    return p / (1 - p)


def _corr(x: np.ndarray, y: np.ndarray) -> float:
    if x.size < 10:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def measure_strata(strata: np.ndarray, cat: np.ndarray, valid: np.ndarray) -> dict:
    """Class-mean precision of each disagreement stratum, and its off-catalogue precision."""
    near = np.zeros_like(valid, dtype=bool)
    with np.errstate(invalid="ignore"):
        from scipy import ndimage
        near = ndimage.binary_dilation(cat, structure=np.ones((3, 3), bool), iterations=3)
    halo = near & ~cat & valid
    isolated = cat & ~ndimage.binary_dilation(cat, structure=np.ones((7, 7), bool))
    out = {}
    for code, nm in ((1, "concordant"), (2, "A_only"), (3, "B_only"), (0, "silent")):
        m = strata == code
        n = int((m & valid).sum())
        out[nm] = dict(
            n_px=n,
            frac_of_footprint=round(n / max(int(valid.sum()), 1), 5),
            precision_on_catalogue=round(float((m & cat).sum()) / max(n, 1), 5),
            precision_in_3px_halo=round(float((m & halo).sum()) / max(n, 1), 5),
            precision_on_isolated=round(float((m & isolated).sum()) / max(n, 1), 5),
        )
    out["_definitions"] = dict(halo="3 px dilation of catalogue, off-trace",
                               isolated="catalogue px >3 px from any other catalogue px (7x7)")
    return out


def _buried_evidence(strata: np.ndarray, valid: np.ndarray, cat: np.ndarray) -> dict:
    """Does the A-only class look buried?  Measured on the official depth-to-basement surface."""
    from scipy import ndimage
    d = np.nan_to_num(get_layer("A_depth_base_rank").astype(np.float32), nan=0.0)
    band = ndimage.binary_dilation(cat, structure=np.ones((3, 3), bool),
                                   iterations=15) & ~cat & valid
    near = ndimage.binary_dilation(cat, structure=np.ones((3, 3), bool),
                                   iterations=3) & valid
    out = {"metric": "band 15 depth-to-basement rank, mean over the stratum inside a 15 px "
                     "corridor off the visible catalogue (high = deeper cover = plausibly buried)"}
    for code, nm in ((1, "concordant"), (2, "A_only"), (3, "B_only"), (0, "silent")):
        m = (strata == code) & band
        if m.sum() < 50:
            out[nm] = dict(n=int(m.sum()), mean_depth_rank=None)
            continue
        v = d[m]
        out[nm] = dict(n=int(m.sum()), mean_depth_rank=round(float(np.mean(v)), 4),
                       median_depth_rank=round(float(np.median(v)), 4))
    out["corridor_px"] = int(band.sum())
    out["catalogue_px"] = int(cat.sum())
    out["near_px"] = int(near.sum())
    return out


def _artifact_evidence(strata: np.ndarray, valid: np.ndarray, cat: np.ndarray) -> dict:
    """Does the B-only class look like a surface artefact?  Slope/step with no field offset."""
    from scipy import ndimage
    sl = np.nan_to_num(get_layer("B_slope_rank").astype(np.float32), nan=0.0)
    gs = np.abs(np.nan_to_num(get_layer("A_grav_step").astype(np.float32), nan=0.0))
    ms = np.abs(np.nan_to_num(get_layer("A_mag_step").astype(np.float32), nan=0.0))
    band = ndimage.binary_dilation(cat, structure=np.ones((3, 3), bool),
                                   iterations=15) & ~cat & valid
    out = {"metric": "mean slope rank and |gravity/magnetic step| per stratum inside the 15 px "
                     "off-trace corridor; an artefact has slope without a field offset"}
    for code, nm in ((1, "concordant"), (2, "A_only"), (3, "B_only"), (0, "silent")):
        m = (strata == code) & band
        if m.sum() < 50:
            out[nm] = dict(n=int(m.sum()))
            continue
        out[nm] = dict(n=int(m.sum()), slope=round(float(sl[m].mean()), 4),
                       grav_step=round(float(gs[m].mean()), 4), mag_step=round(float(ms[m].mean()), 4))
    return out


# -----------------------------------------------------------------------------------------------
# stage: validate  (delegated to scripts/validate_holdout.py logic)
# -----------------------------------------------------------------------------------------------
def stage_validate(n_folds: int) -> None:
    import subprocess
    cmd = [sys.executable, str(ROOT / "scripts/validate_holdout.py"), "--mode", MODE,
           "--n-folds", str(n_folds)]
    raise SystemExit(subprocess.call(cmd))


def independence_report(oof: dict, strat_oof: np.ndarray, held_mask: np.ndarray,
                        cat: np.ndarray, valid: np.ndarray, n_blocks: int = 4) -> dict:
    """The premise of the whole method, measured.

    Co-training pays off only if the two views make *different* mistakes given the label, so the
    one pixel a view is wrong about carries information the other does not.  We test it the way the
    brief says to: aggregate per-view error to spatial blocks (16 contiguous rectangles) and
    correlate across blocks, because pixel-level correlation of two logistic scores is dominated by
    the shared "this is a fault" signal rather than by the error structure we care about.

    Reported per block: false-alarm level on non-catalogue pixels (mean score) and miss level on
    catalogue pixels (1 - mean score).  Also reported: pixel-level correlation of the two views'
    logits on the held-out pixels, split by class, which is the same question at maximum resolution.
    """
    from scipy import ndimage as _nd
    lab = HO.block_ids(valid.shape, valid, n=n_blocks)
    cm = cat.ravel()
    vm = valid.ravel()
    out = {}
    for tag in ("a0", "a1", "b0", "b1"):
        out[tag] = oof[tag]
    fa = np.full(n_blocks * n_blocks, np.nan)
    ms = np.full(n_blocks * n_blocks, np.nan)
    fa_b = np.full(n_blocks * n_blocks, np.nan)
    ms_b = np.full(n_blocks * n_blocks, np.nan)
    for k in range(n_blocks * n_blocks):
        blk = (lab == k).ravel() & vm
        if blk.sum() < 5000:
            continue
        negb = blk & (cm == 0)
        posb = blk & (cm == 1)
        fa[k] = float(out["a0"][negb].mean())
        fa_b[k] = float(out["b0"][negb].mean())
        ms[k] = 1.0 - float(out["a0"][posb].mean()) if posb.sum() > 20 else np.nan
        ms_b[k] = 1.0 - float(out["b0"][posb].mean()) if posb.sum() > 20 else np.nan
    dfa = CT.view_correlation(fa, fa_b)
    dms = CT.view_correlation(ms, ms_b)
    ind = dict(n_blocks=int(np.isfinite(fa).sum()),
               pearson=dfa["pearson_r"], pearson_misses=dms["pearson_r"],
               spearman=dfa["spearman_rho"], spearman_misses=dms["spearman_rho"],
               false_alarm_a=[round(float(x), 4) for x in fa if np.isfinite(x)],
               false_alarm_b=[round(float(x), 4) for x in fa_b if np.isfinite(x)],
               miss_a=[round(float(x), 4) for x in ms if np.isfinite(x)],
               miss_b=[round(float(x), 4) for x in ms_b if np.isfinite(x)])
    sel = held_mask
    la, lb = np.log(_odds(out["a1"], 1e-6)), np.log(_odds(out["b1"], 1e-6))
    ind["pearson_logit_held_all"] = round(_corr(la[sel], lb[sel]), 4)
    ind["pearson_logit_held_negatives"] = round(_corr(la[sel & (cm == 0)], lb[sel & (cm == 0)]), 4)
    ind["pearson_logit_held_positives"] = round(_corr(la[sel & (cm == 1)], lb[sel & (cm == 1)]), 4)
    ind["n_held"] = int(sel.sum())
    # the disagreement rate itself: how much mass each confident-disagreement class holds
    for code, nm in ((1, "concordant"), (2, "A_only"), (3, "B_only")):
        ind[f"frac_held_{nm}"] = round(float((strat_oof[sel] == code).mean()), 4)
    return ind


def _independence_verdict(ind: dict, per_fold: list[dict]) -> dict:
    pix = float(ind.get("pearson_logit_held_all") or float("nan"))
    blk = float(ind.get("pearson") or float("nan"))
    if not np.isfinite(blk):
        ind["note"] = ("block-level correlation undefined: fewer than 3 usable blocks "
                       f"({ind.get('n_blocks')}); the pixel-level logit correlation is the only "
                       "available reading at this grid size")
    if not np.isfinite(pix):
        ind["note"] = "no out-of-fold pixels; independence test not runnable at this grid size"
        return dict(passed=False, abs_pearson=None, threshold=PREREG["gates"]["independence_abs_pearson_max"],
                    mean_auc_delta_a=None, fold_support="0/0",
                    reading="NOT MEASURED: empty held set (crop or degenerate fold layout)")
    r = max(abs(blk) if np.isfinite(blk) else 0.0, abs(pix))
    need = PREREG["gates"]["independence_abs_pearson_max"]
    deltas = [f["auc_a1"] - f["auc_a0"] for f in per_fold]
    sup = sum(1 for d in deltas if d > 0)
    ok = (r < need) and sup >= PREREG["gates"]["fold_support_min"] and np.mean(deltas) > 0
    lift = np.mean(deltas) > 0 and sup >= PREREG["gates"]["fold_support_min"]
    indep = r < need
    return dict(passed=bool(ok), independence_ok=bool(indep), co_train_lift_ok=bool(lift),
                abs_pearson=round(r, 4), threshold=need,
                mean_auc_delta_a=round(float(np.mean(deltas)), 4),
                fold_support=f"{sup}/{len(deltas)}",
                reading=("PASS: errors weakly coupled and the round lifted AUC on the blocked folds"
                         if ok else
                         f"{'FAIL' if not lift else 'PARTIAL'}: co-training lift {'ok' if lift else 'absent'} "
                         f"(mean AUC delta {np.mean(deltas):+.4f} on {sup}/{len(deltas)} folds), "
                         f"independence {'ok' if indep else 'refuted'} (|r|={r:.3f} vs {need}) - "
                         "see holdout_" + MODE + ".json for the block-level reading and the arm table, "
                         "which is where the decision is actually made"))


# -----------------------------------------------------------------------------------------------
def field_and_emit(field: np.ndarray, valid: np.ndarray, dti_projected: float, budget: int,
                   g_estimate: float, logf=log) -> tuple[np.ndarray, dict]:
    em, st = HO.emission_from_field(field, valid, dti_projected, budget,
                                    calibrate_to=g_estimate, pool=400_000, log=logf)
    return em, st


NS_ARGS = argparse.Namespace(stage="validate", rounds=1, n_folds=4, mode="hide")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="fit", choices=["fit", "validate"])
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--n-folds", type=int, default=4)
    ap.add_argument("--mode", default="hide", choices=["hide", "block", "tip"])
    a = ap.parse_args()
    MODE = a.mode
    N_FOLDS = a.n_folds
    NS_ARGS = a
    EV.mkdir(parents=True, exist_ok=True)
    if a.stage == "fit":
        stage_fit(rounds=a.rounds, n_folds=a.n_folds)
    else:
        stage_validate(a.n_folds)
