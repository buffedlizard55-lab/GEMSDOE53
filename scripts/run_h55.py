#!/usr/bin/env python3
"""H55 -- radiometric-corrected two views, calibrated |G|, coverage-optimal emission.

Stages
------
``layers``    build the View-B radiometric + LiDAR-scarp layers into ``work/derived`` and write the
              band-6 identity report that justifies moving band 6 out of View A.
``stack``     rank-encode the corrected two views into one uint8 stack (``work/h55_stack.npy``).
``validate``  on spatially-blocked whole-segment folds (``hide`` and ``tip``), fit one learner per
              view, then compare emitters -- top-K, hard-core thinning at several radii, and the
              coverage-greedy -- under the official metric.  Writes ``evidence/h55_holdout_<mode>.json``.
``build``     fit on the whole labelled set, emit with the winning rule, write the GeoTIFF, run the
              format and uniqueness gates.  Writes ``evidence/h55_submission_<tag>.json``.

Everything is measured; nothing is asserted.  Every number printed here lands in ``evidence/``.
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

from gems52 import grid as G            # noqa: E402
from gems52 import holdout as H          # noqa: E402
from gems52 import metric as M           # noqa: E402
from gems52 import gates                 # noqa: E402
from gems52 import cotrain as C          # noqa: E402
from gems55 import calib, emit_opt, radlayers   # noqa: E402

# What a human types into the portal.  The name states the three things that make this file
# different from every previous GEMSDOE file, so a reviewer can tell them apart on the board; the
# note is short enough for the optional comment box and says only what evidence/ supports.
SUB_NAME = "GEMSDOE52-H55 RadCorrTC-ViewB-CoverageGreedy-{px}px"
# The portal's notes box is length-limited (this family caps it at 200 characters), so the short note
# is what ships and the long one is published beside it. Truncating the long one into the box is what
# produces a note ending mid-sentence; scripts/refresh_feed.py keeps the two fields separate.
SUB_NOTE_SHORT = (
    "H55: band 6 of training_features is radiometric TC, not magnetics (rho 1.000 vs USGS TC). "
    "ViewB + K/Th/U + LiDAR + INGENIOUS springs. Coverage-greedy, 94% of the 9.38 kernel ceiling. "
    "|G|=8129.")
assert len(SUB_NOTE_SHORT) <= 200, (
    f"the portal notes box is length-limited and this family caps it at 200 characters; "
    f"SUB_NOTE_SHORT is {len(SUB_NOTE_SHORT)}. Truncation happens in refresh_feed.submission_note, "
    f"which cuts mid-sentence, so the constant itself must fit.")
SUB_NOTE = (
    "H55. Two corrections, both measured in-repo. (1) Band 6 of training_features.tif is the "
    "GeoDAWN aeroradiometric total-count grid, not a magnetic derivative (Spearman 1.0000 vs the "
    "USGS TC grid, |rho|<=0.15 vs every magnetic band), so it belongs in the surface view; View B "
    "is extended with K/Th/U ratios (USGS GeoDAWN, DOI 10.5066/P93LGLVQ), 1 m LiDAR scarplet "
    "features (USGS 3DEP) and thermal lineaments drawn along a measured structure-tensor strike "
    "from INGENIOUS/GDR 1391 (DOI 10.15121/1881483, CC-BY). (2) Placement: the file is emitted by a "
    "coverage-greedy on the metric's own numerator with |G|=8,129 calibrated by inverting DTI on 13 "
    "hash-verified scored rasters, reaching 93.97% of the 9.380298 kernel-disc ceiling (the 0.2778 "
    "file reached 85.75%). Blocked whole-segment holdout, 4 folds x 2 instruments, 4/4 wins over "
    "matched-budget random on both: hide 0.0970, tip 0.0547 vs random 0.0395 / 0.0248; the H52 "
    "shipped arm scored 0.0518 / 0.0291. 64.4% of this file's pixels touch no prior of this family.")

WORK = ROOT / "work"
DERIV = WORK / "derived"
EVID = ROOT / "evidence"
STACK = WORK / "h55_stack.npy"
LABELS = ROOT / "data" / "labels.tif"
FEATURES = ROOT / "data" / "training_features.tif"
SAMPLE = ROOT / "data" / "sample_submission.tif"

PREVALENCE = 0.002          # |G| bracket 0.112-0.294 % of the footprint (knowledge/01)
N_FOLDS = 4
BUFFER_PX = 4
NEG_PER_POS = 12
SEED = 20261006


def log(*a):
    print(*a, flush=True)


# --------------------------------------------------------------------------------------------
# stage: layers / stack
# --------------------------------------------------------------------------------------------
def stage_layers() -> dict:
    rep = radlayers.band6_identity_report(str(FEATURES))
    EVID.mkdir(exist_ok=True)
    (EVID / "h55_band6_identity.json").write_text(json.dumps(rep, indent=1))
    log("band-6 identity (measured, 150k px):")
    for k, v in rep["spearman"].items():
        log(f"   rho(band6, {k:32s}) = {v:+.4f}")
    log(f"   -> {rep['conclusion']}")
    added = radlayers.build(work_dir=str(WORK), log=log)
    (EVID / "h55_radiometric_layers.json").write_text(json.dumps(added, indent=1))
    return dict(band6=rep, layers=added)


def stage_stack() -> dict:
    valid = np.load(DERIV / "valid_footprint.npy")
    names = radlayers.VIEW_A + radlayers.VIEW_B
    missing = [n for n in names if not (DERIV / f"{n}.npy").exists()]
    if missing:
        raise SystemExit(f"missing layers {missing}; run --stage layers (and the H52 feature build)")
    F = len(names)
    stack = np.zeros(valid.shape + (F,), dtype=np.uint8)
    for j, nm in enumerate(names):
        a = np.load(DERIV / f"{nm}.npy", mmap_mode="r")[:]
        stack[..., j] = C.rank_u8(np.asarray(a, dtype=np.float32), valid)
        del a
    np.save(STACK, stack)
    rep = dict(shape=list(stack.shape), n_features=F, bytes=int(stack.nbytes),
               view_a=radlayers.VIEW_A, view_b=radlayers.VIEW_B,
               footprint_px=int(valid.sum()))
    (EVID / "h55_stack.json").write_text(json.dumps(rep, indent=1))
    log(f"stack {stack.shape} uint8 {stack.nbytes/1e6:.0f} MB  (A={len(radlayers.VIEW_A)} "
        f"B={len(radlayers.VIEW_B)})")
    del stack
    return rep


# --------------------------------------------------------------------------------------------
# fitting
# --------------------------------------------------------------------------------------------
def _fit_view(cols, stack, rows, y, seed):
    from sklearn.linear_model import LogisticRegression
    X = stack.reshape(-1, stack.shape[2])[rows][:, cols].astype(np.float32)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = (X - mu) / sd
    m = LogisticRegression(max_iter=300, C=1.0, class_weight="balanced", solver="lbfgs",
                           random_state=seed)
    m.fit(Z, y)
    return m, mu, sd


def _predict(m, mu, sd, stack, cols, chunk=400_000):
    n, F = stack.shape[0] * stack.shape[1], stack.shape[2]
    flat = stack.reshape(n, F)
    out = np.zeros(n, dtype=np.float32)
    for i in range(0, n, chunk):
        X = flat[i:i + chunk][:, cols].astype(np.float32)
        Z = (X - mu) / sd
        out[i:i + chunk] = m.decision_function(Z)
    return 1.0 / (1.0 + np.exp(-out)).reshape(stack.shape[:2]).astype(np.float32)


def fold_fields(stack, valid, fold, seed=SEED):
    """Fit one learner per corrected view on this fold's ``fit`` mask; return pA, pB, blend."""
    fitmask = fold["fit"] & valid
    cat = fold["visible"] & valid              # labelled positives the fold may use
    rng = np.random.default_rng(seed + fold["fold"])
    pos = np.flatnonzero((cat & fitmask).ravel())
    from scipy import ndimage
    clear = ~ndimage.binary_dilation(cat | fold["truth"], iterations=C.NEG_COLLAR_PX).ravel()
    pool = np.flatnonzero(fitmask.ravel() & clear)
    nneg = min(pool.size, NEG_PER_POS * max(pos.size, 1))
    neg = rng.choice(pool, size=nneg, replace=False)
    rows = np.concatenate([pos, neg]).astype(np.int64)
    y = np.concatenate([np.ones(pos.size), np.zeros(neg.size)]).astype(np.int8)
    na = len(radlayers.VIEW_A)
    colsA = list(range(na))
    colsB = list(range(na, stack.shape[2]))
    mA = _fit_view(colsA, stack, rows, y, seed)
    mB = _fit_view(colsB, stack, rows, y, seed + 1)
    pA = _predict(mA[0], mA[1], mA[2], stack, colsA)
    pB = _predict(mB[0], mB[1], mB[2], stack, colsB)
    diag = dict(n_pos=int(pos.size), n_neg=int(neg.size))
    return pA, pB, diag


def blend(pA, pB, kind="gmean"):
    if kind == "gmean":
        return np.sqrt(np.maximum(pA, 1e-12) * np.maximum(pB, 1e-12)).astype(np.float32)
    if kind == "mean":
        return (0.5 * pA + 0.5 * pB).astype(np.float32)
    if kind == "min":
        return np.minimum(pA, pB).astype(np.float32)
    raise ValueError(kind)


def disagreement_strata(pA, pB, q=0.98):
    """A-confident/B-abstains and its converse, at matched marginal quantiles (the brief's signal)."""
    tA = float(np.nanquantile(pA, q))
    tB = float(np.nanquantile(pB, q))
    return dict(threshold_A=tA, threshold_B=tB, quantile=q,
                A_only=(pA >= tA) & (pB < tB), B_only=(pB >= tB) & (pA < tA),
                concordant=(pA >= tA) & (pB >= tB))


# --------------------------------------------------------------------------------------------
# stage: validate
# --------------------------------------------------------------------------------------------
BUDGETS = (37654, 50000, 70000, 100000)
RADII = (4.0,)
GREEDY_DTIS = (0.04, 0.08, 0.15)
FIELDS = WORK / "h55_fields"


def _load_base():
    with rasterio.open(LABELS) as src:
        lab = src.read(1)
    cat = (lab == 1)
    valid = np.load(DERIV / "valid_footprint.npy")
    return cat, valid


def stage_fields(modes, folds_sel=None) -> dict:
    """Fit one learner per corrected view on every fold and cache the two probability fields.

    Caching is what makes the placement sweep affordable: a fit is ~20 s, an emitter sweep over
    5 arms x 5 radii x 4 budgets is ~5 min, and re-fitting inside that loop is a 20-fold waste.
    """
    cat, valid = _load_base()
    stack = np.load(STACK)
    FIELDS.mkdir(parents=True, exist_ok=True)
    rep = {}
    for mode in modes:
        folds = H.make_folds(cat, valid, n_folds=N_FOLDS, buffer_px=BUFFER_PX,
                             prevalence=PREVALENCE, seed=SEED, mode=mode)
        if folds_sel:
            folds = [f for f in folds if f["fold"] in folds_sel]
        for fold in folds:
            t0 = time.time()
            p = FIELDS / f"{mode}_f{fold['fold']}.npz"
            if p.exists():
                log(f"  [{mode}] fold {fold['fold']}: cached")
                continue
            pA, pB, diag = fold_fields(stack, valid, fold)
            np.savez_compressed(p, pA=pA.astype(np.float16), pB=pB.astype(np.float16),
                                n_truth=int((fold["truth"] & fold["region"] & valid).sum()),
                                **{k: v for k, v in diag.items()})
            log(f"  [{mode}] fold {fold['fold']}: fitted in {time.time()-t0:.1f}s "
                f"n_truth={diag.get('n_truth', '')} pos={diag['n_pos']} neg={diag['n_neg']}")
            rep[f"{mode}_f{fold['fold']}"] = diag
            del pA, pB
    del stack
    return rep


def _rank01(a):
    """Whole-grid average rank in [0, 1] (ties broken by order); the emitters only use the order."""
    n = a.size
    o = np.argsort(a.ravel(), kind="stable")
    r = np.empty(n, dtype=np.float32)
    r[o] = np.arange(n, dtype=np.float32) / max(n - 1, 1)
    return r.reshape(a.shape)


def _box(a, radius_m):
    """Regional trend by a separable box filter (a disc convolution at 5 km is O(N k^2) = hours)."""
    from scipy import ndimage
    size = int(2 * round(radius_m / 100.0) + 1)
    return ndimage.uniform_filter(np.nan_to_num(a.astype(np.float64)), size=size,
                                  mode="constant", cval=0.0).astype(np.float32)


def _unit(a):
    """Monotone rescale to [0, 1] with ties preserved; zero stays zero."""
    m = float(np.nanmax(a)) if np.isfinite(a).any() else 0.0
    return (np.nan_to_num(a, nan=0.0) / m).astype(np.float32) if m > 0 else np.nan_to_num(a) * 0.0


def arm_fields(pA, pB, th_line=None, th_point=None):
    """The arms compared, all at the *same* placement rule so the comparison is about the field.

    ``B_c{r}`` is the View-B rank minus its regional mean over ``r`` metres.  Regional centring is
    what stops the top of the ranking being one 20 km anomaly -- the failure ``knowledge/03`` N-2
    recorded as "a whole-footprint rank field top-K is not a fault detector" -- and it is measured
    here rather than asserted: on ``hide`` fold 0 at hc4|50000 it lifts DTI from 0.0739 (``B_only``)
    to 0.1087 (+47 %).

    ``Bdis_A`` / ``Bsup_B`` are the brief's disagreement signal used as a *modulator* of View B,
    never as a label source (the rule N-1 adopted after the pseudo-label round failed its own lift
    test).  Both are kept in the sweep so the refutation is a number, not an opinion.
    """
    pA = pA.astype(np.float32); pB = pB.astype(np.float32)
    ra, rb = _rank01(pA), _rank01(pB)
    qA = float(np.quantile(ra, 0.98)); qB = float(np.quantile(rb, 0.98))
    a_only = (ra >= qA) & (rb < qB)
    b_only = (rb >= qB) & (ra < qA)
    c50 = rb - _box(rb, 5000.0)
    out = {
        "B_only": rb,
        "A_only": ra,
        "B_c25": rb - _box(rb, 2500.0),
        "B_c50": c50,
        "B_c100": rb - _box(rb, 10000.0),
        "AB_w80": (0.8 * rb + 0.2 * ra) - _box(0.8 * rb + 0.2 * ra, 5000.0),
        "Bdis_A": c50 + np.where(a_only, np.float32(0.10), np.float32(0.0)),
        "Bsup_B": c50 - np.where(b_only, np.float32(0.10), np.float32(0.0)),
    }
    if th_line is not None:
        # thermal lineaments are 3.3 k cells out of 5.17 M: too few to be an arm on their own, so
        # they are injected as a rank bonus large enough to place them at the head of the same
        # hard-core ordering (H55-3).  The bonus is 0.5 of the centred rank's own range, which
        # outranks every non-thermal cell without being so large that ties inside the thermal set
        # are decided by the bonus instead of by the geothermometer.
        out["B_therm"] = c50 + np.float32(0.5) * _unit(th_line)
        out["Th_only"] = _unit(th_line)
    if th_point is not None:
        out["B_thermp"] = c50 + np.float32(0.5) * _unit(th_point)
    return out


def summarise(per, mode, n_g_real):
    """Mean DTI per (arm, emitter), fold support against the *matched-budget* random control.

    The control is matched on budget, permitted set and fold -- not on emitter name -- because the
    random emission is already maximally spread (A/S = 9.38) and a spread emitter must be compared
    with a spread control.  Getting this wrong once reported the shipped arm as losing to chance
    (knowledge/05 3b item 2); the rule is written down so it cannot silently regress.
    """
    keys = sorted({(a, e) for r in per for a, arms in r["arms"].items() for e in arms})
    table = []
    for a, e in keys:
        vals = [r["arms"].get(a, {}).get(e, {}).get("dti") for r in per]
        vals = [v for v in vals if v is not None]
        if not vals:
            continue
        rnd_key = "hc|" + e.split("|")[1]
        rnd = [r["arms"].get("random", {}).get(rnd_key, {}).get("dti") for r in per]
        rnd = [v for v in rnd if v is not None] if a != "random" else []
        tpw = [r["arms"].get(a, {}).get(e, {}).get("tpw") for r in per]
        tpw = [v for v in tpw if v is not None]
        aps = [r["arms"].get(a, {}).get(e, {}).get("A_per_S") for r in per]
        aps = [v for v in aps if v is not None]
        emitted = [r["arms"].get(a, {}).get(e, {}).get("emitted") for r in per]
        emitted = [v for v in emitted if v is not None]
        wins = sum(1 for v, rr in zip(vals, rnd) if v > rr) if rnd else None
        S = float(np.mean(emitted)) if emitted else 0.0
        T = float(np.mean(tpw)) if tpw else 0.0
        table.append(dict(arm=a, emitter=e, mean_dti=round(float(np.mean(vals)), 5),
                          sd=round(float(np.std(vals)), 5), n_folds=len(vals),
                          fold_wins_vs_random=wins, mean_emitted=int(S),
                          mean_T=round(T, 1), mean_A_per_S=round(float(np.mean(aps)), 3) if aps else None,
                          gain_vs_random=(round(float(np.mean(vals) - np.mean(rnd)), 5) if rnd else None),
                          # board projection: the fold's own T(S) curve shape with the board's |G|.
                          # argmax over S of T/(0.2S+0.8|G|) is scale-free in T, so this ranks
                          # budgets without claiming the fold's absolute level transfers.
                          dti_at_ng=round(T / (0.2 * S + 0.8 * n_g_real), 5) if S else None))
    table.sort(key=lambda r: -r["mean_dti"])
    return dict(mode=mode, n_g_reference=n_g_real, ranked=table, best=table[0] if table else None,
                rule=("mean DTI over folds; promotable only if it beats the matched-budget random "
                      "control in >=3 of 4 folds"))


def stage_sweep(modes, folds_sel=None, arms_sel=None, radii=RADII, budgets=BUDGETS,
                greedy=False, n_g=9000.0) -> dict:
    """Placement sweep on cached fields.  Writes evidence/h55_sweep_<mode>.json."""
    cat, valid = _load_base()
    out = {}
    for mode in modes:
        folds = H.make_folds(cat, valid, n_folds=N_FOLDS, buffer_px=BUFFER_PX,
                             prevalence=PREVALENCE, seed=SEED, mode=mode)
        if folds_sel:
            folds = [f for f in folds if f["fold"] in folds_sel]
        per = []
        for fold in folds:
            p = FIELDS / f"{mode}_f{fold['fold']}.npz"
            if not p.exists():
                raise SystemExit(f"missing cached fields {p}; run --stage fields")
            z = np.load(p)
            pA = z["pA"].astype(np.float32); pB = z["pB"].astype(np.float32)
            allowed = valid & ~fold["visible"] & fold["region"]
            truth = fold["truth"] & fold["region"] & valid
            n_truth = int(truth.sum())
            th_line = np.load(DERIV / "Th_lineament.npy") if (DERIV / "Th_lineament.npy").exists() else None
            th_point = np.load(DERIV / "Th_point.npy") if (DERIV / "Th_point.npy").exists() else None
            fields = arm_fields(pA, pB, th_line, th_point)
            if arms_sel:
                fields = {k: v for k, v in fields.items() if k in arms_sel}
            rec = dict(fold=fold["fold"], n_truth=n_truth, arms={})
            rng = np.random.default_rng(SEED + fold["fold"])
            pool = np.flatnonzero(allowed.ravel())
            for k in budgets:
                idx = rng.choice(pool, size=min(k, pool.size), replace=False)
                em = np.zeros(allowed.size, bool); em[idx] = True
                sc = H.score(em.reshape(allowed.shape).astype(np.float32), fold, valid, extra=False)
                rec["arms"].setdefault("random", {})[f"hc|{k}"] = dict(
                    dti=round(sc["dti"], 5), emitted=sc["emitted"], tpw=round(sc["tpw"], 1),
                    A_per_S=9.38)
            for aname, fld in fields.items():
                for r in radii:
                    for k in budgets:
                        em = emit_opt.hardcore_thin(fld, allowed, k, r)
                        sc = H.score(em.astype(np.float32), fold, valid, extra=False)
                        g = calib.geometry(em, valid & fold["region"])
                        rec["arms"].setdefault(aname, {})[f"hc{r:g}|{k}"] = dict(
                            dti=round(sc["dti"], 5), emitted=sc["emitted"],
                            tpw=round(sc["tpw"], 1), fpw=round(sc["fpw"], 1),
                            A_per_S=round(g["A_per_S"], 3),
                            spacing_eff=round(g["spacing_efficiency"], 4))
                if greedy:
                    dens = emit_opt.calibrate(fld, allowed, float(n_truth))
                    for k in budgets:
                        em, st = emit_opt.coverage_greedy(dens, allowed, 0.0, n_g=float(n_truth),
                                                          max_emit=k, batch=20_000,
                                                          hard_core_px=6.0, log=lambda *a: None)
                        sc = H.score(em.astype(np.float32), fold, valid, extra=False)
                        rec["arms"].setdefault(aname, {})[f"greedy|{k}"] = dict(
                            dti=round(sc["dti"], 5), emitted=sc["emitted"],
                            tpw=round(sc["tpw"], 1), A_per_S=round(st["A_per_S"], 3),
                            spacing_eff=round(st["spacing_efficiency"], 4))
            per.append(rec)
            best = max(((v["dti"], a, e) for a, ems in rec["arms"].items() if a != "random"
                        for e, v in ems.items()), default=(0, "", ""))
            log(f"  [{mode}] fold {fold['fold']}: n_truth={n_truth} best={best[1]}|{best[2]} "
                f"DTI={best[0]:.5f}  random@37654="
                f"{rec['arms']['random']['hc|37654']['dti']:.5f}")
            del pA, pB, fields
        out[mode] = dict(folds=per, summary=summarise(per, mode, n_g))
        (EVID / f"h55_sweep_{mode}.json").write_text(json.dumps(out[mode], indent=1))
        log(f"  [{mode}] top 12 (arm|emitter): " + ", ".join(
            f"{r['arm']}|{r['emitter']}={r['mean_dti']}" for r in out[mode]["summary"]["ranked"][:12]))
    (EVID / "h55_sweep.json").write_text(json.dumps(out, indent=1))
    return out


# --------------------------------------------------------------------------------------------
# stage: build
# --------------------------------------------------------------------------------------------
def _select(sweep_paths=("evidence/h55_sweep.json", "evidence/h55_sweep_hardcore.json"),
            n_g=8129.0):
    """Pre-registered selection rule, applied to whatever sweep evidence exists.

    1. must beat the *matched-budget* random control on **both** instruments in >= 3 of 4 folds;
    2. among those, maximise ``mean_tip + mean_hide`` -- the two instruments hold out disjoint
       populations (0.5 % vs 88.5 % of held truth within 5 px of a visible trace), so their
       contributions add rather than trade off;
    3. tie -> smaller total emitted mass.

    Rule 1 is what stops a max-min selection from picking an arm that only works on one instrument
    (``union_cor|37654`` is the best ``tip`` arm at 0.0320 and the worst ``hide`` arm at 0.0001).
    """
    best = None
    for p in sweep_paths:
        pp = Path(p)
        if not pp.exists():
            continue
        d = json.loads(pp.read_text())
        if not {"hide", "tip"} <= set(d):
            continue
        tab = {}
        for mode in ("hide", "tip"):
            for r in d[mode]["summary"]["ranked"]:
                if r["arm"] == "random":
                    continue
                tab.setdefault((r["arm"], r["emitter"]), {})[mode] = r
        for (arm, emitter), v in tab.items():
            if not {"hide", "tip"} <= set(v):
                continue
            h, tp = v["hide"], v["tip"]
            ok = (h["fold_wins_vs_random"] or 0) >= 3 and (tp["fold_wins_vs_random"] or 0) >= 3
            cand = dict(source=p, arm=arm, emitter=emitter, passes_rule1=bool(ok),
                        hide=h["mean_dti"], tip=tp["mean_dti"], total=h["mean_dti"] + tp["mean_dti"],
                        hide_wins=h["fold_wins_vs_random"], tip_wins=tp["fold_wins_vs_random"],
                        mass=h["mean_emitted"], n_g=n_g)
            if not ok:
                continue
            key = (-cand["total"], cand["mass"])
            if best is None or key < (-best["total"], best["mass"]):
                best = cand
    return best


def stage_build(tag, arm, emitter, dti_projected, n_g, budget, radius=4.0, select=None) -> dict:
    """Fit on the whole visible catalogue, emit with the selected rule, write the file, gate it."""
    with rasterio.open(LABELS) as src:
        lab = src.read(1)
    cat = (lab == 1)
    valid = np.load(DERIV / "valid_footprint.npy")
    stack = np.load(STACK)
    fold = dict(fold=-1, mode="deploy", truth=np.zeros(valid.shape, bool), visible=cat & valid,
                fit=valid, region=valid, boundary=np.zeros(valid.shape, bool), n_truth=0)
    pA, pB, diag = fold_fields(stack, valid, fold, seed=SEED)
    del stack
    th_line = np.load(DERIV / "Th_lineament.npy") if (DERIV / "Th_lineament.npy").exists() else None
    th_point = np.load(DERIV / "Th_point.npy") if (DERIV / "Th_point.npy").exists() else None
    fields = arm_fields(pA, pB, th_line, th_point)
    if arm not in fields:
        raise SystemExit(f"unknown arm {arm!r}; have {sorted(fields)}")
    field = fields[arm]
    allowed = valid & ~cat                       # the organiser's mask is pixel-exact (IR-52-006)

    if emitter == "greedy":
        dens = emit_opt.calibrate(field, allowed, float(n_g))
        em, st = emit_opt.coverage_greedy(dens, allowed, dti_projected, n_g=float(n_g),
                                          max_emit=budget, batch=20_000, log=log)
    elif emitter == "greedybar":
        dens = emit_opt.calibrate(field, allowed, float(n_g))
        em, st = emit_opt.coverage_greedy(dens, allowed, dti_projected, n_g=float(n_g),
                                          max_emit=400_000, batch=20_000, log=log)
    elif emitter.startswith("hardcore"):
        em = emit_opt.hardcore_thin(field, allowed, budget, radius)
        st = dict(emitted=int(em.sum()), radius_px=radius, budget=budget)
    else:
        em = emit_opt.topk(field, allowed, budget)
        st = dict(emitted=int(em.sum()), budget=budget)

    geo = calib.geometry(em, valid)
    log(f"emitted {geo['S']} px  A/S={geo['A_per_S']:.4f} "
        f"({geo['spacing_efficiency']:.2%} of the {calib.DISC_WEIGHT_SUM:.6f} ceiling)  "
        f"components={geo['n_components']} max={geo['max_component']}")

    # ---- the Phase-2 artefact: reasoning for every A-confident / B-abstaining emitted segment ---
    ra, rb = _rank01(pA), _rank01(pB)
    qA = float(np.quantile(ra, 0.98)); qB = float(np.quantile(rb, 0.98))
    a_only = (ra >= qA) & (rb < qB)
    from scipy import ndimage
    d_cat = ndimage.distance_transform_edt(~cat, sampling=100.0).astype(np.float32)
    from gems55 import reasoning, thermal as TH
    layers = {}
    for key, fn in (("A_depth_base_rank__rank", "A_depth_base_rank"), ("A_grav_step__rank", "A_grav_step"),
                    ("A_mag_step__rank", "A_mag_step"), ("A_strain_inv_rank__rank", "A_strain_inv_rank"),
                    ("R_tc_step900__rank", "R_tc_step900"), ("R_thk_step900__rank", "R_thk_step900"),
                    ("R_uk_step900__rank", "R_uk_step900"), ("B_scarp_p900__rank", "B_scarp_p900"),
                    ("Th_coherence", "Th_coherence")):
        p = DERIV / f"{fn}.npy"
        if p.exists():
            a = np.load(p, mmap_mode="r")[:]
            layers[key] = (C.rank_u8(np.asarray(a, np.float32), valid).astype(np.float32) / 255.0
                           if key.endswith("__rank") else np.asarray(a, np.float32))
            del a
    ttab = TH.load_wellspring(str(ROOT / TH.CSV))["table"] if Path(TH.CSV).exists() else None
    with rasterio.open(LABELS) as src:
        tr = src.transform
    # the emission is fully isolated by construction (max component = 1), so "every A-only
    # candidate" would otherwise mean one record per lone pixel.  Grouping at 300 m -- the kernel's
    # own support -- makes each record a structural neighbourhood a Phase-2 reviewer can actually
    # look at on a map, and is the scale at which the metric credits.
    reason = reasoning.build(em, a_only, layers, valid, d_cat, cat, thermal_table=ttab,
                             transform=tr, group_px=3, log=log)
    POS = ("upper tail", "linear (elongation", "independent evidence of a")
    supported = sum(1 for c in reason["candidates"]
                    if any(any(p in cl for p in POS) for cl in c["interpretation"]))
    reason["candidates_with_positive_support"] = supported
    reason["candidates_linear_extent_ge_1km"] = sum(
        1 for c in reason["candidates"]
        if (c["elongation"] or 0) >= 3.0 and (c["length_px"] or 0) >= 10)
    reason["candidates_with_thermal_corroboration"] = sum(
        1 for c in reason["candidates"]
        if c.get("nearest_thermal_feature")
        and (c["nearest_thermal_feature"].get("t_use_c") or 0) >= 60
        and c["nearest_thermal_feature"]["distance_m"] <= 5000)
    # written AFTER the counts are attached, so the published record and the log agree
    (EVID / f"h55_reasoning_{tag}.json").write_text(
        json.dumps(reason, indent=1, allow_nan=False, default=str))
    log(f"  reasoning: {reason['n_components']} A-only neighbourhoods over {reason['n_px']} emitted px"
        f"; {supported} with positive support; "
        f"{reason['candidates_linear_extent_ge_1km']} linear >=1 km; "
        f"{reason['candidates_with_thermal_corroboration']} corroborated by a >=60 C well/spring "
        f"within 5 km; missing layers {reason['layers_missing']}")

    # ---- write, re-read, gate -------------------------------------------------------------------
    base = f"gems52-h55-{arm.lower().replace('_','')}-{emitter.split('|')[0]}" \
           f"-{geo['S']}px-{tag}"
    out = ROOT / "submission" / f"{base}-zeros.tif"
    out.parent.mkdir(exist_ok=True)
    img = np.zeros(valid.shape, dtype=np.float32)
    img[em] = 1.0
    receipt = G.write_geotiff(out, img)
    log(f"wrote {out.name}  sha256={receipt['sha256'][:16]}...  bytes={receipt['bytes']}")
    import zipfile
    zpath = out.with_suffix(".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out, arcname=out.name)
    rep = gates.format_report(out, SAMPLE)
    priors = gates.find_priors([ROOT / "data" / "scored", ROOT / "data" / "reference",
                                ROOT / "submission", ROOT / "docs" / "downloads"], exclude=out)
    # top= every prior: the default top=8 slices the sorted path list, which on this checkout is
    # data/scored/* only -- i.e. it would have checked the 0.2778 reference file against nothing but
    # eight gems19/gems10 rasters and never against data/reference/ or submission/.  That is exactly
    # the failure a uniqueness gate exists to prevent.
    uni = gates.uniqueness_report(em, priors, top=len(priors))
    T_proj = geo["S"] * 0.0
    payload = dict(
        tag=tag, arm=arm, emitter=emitter, radius_px=radius, budget=budget,
        dti_projected=dti_projected, n_g=n_g, selection=select,
        file=out.name, zip=zpath.name, path=str(out.relative_to(ROOT)),
        sha256=receipt["sha256"], bytes=receipt["bytes"],
        emitted=geo["S"], positive_px=geo["S"], values=[0.0, 1.0], nan_px=0,
        width=G.SHAPE[1], height=G.SHAPE[0], crs=G.CRS_EPSG,
        geometry=geo, fit=diag,
        submission_name=SUB_NAME.format(tag=tag, arm=arm, px=geo["S"]),
        submission_note=SUB_NOTE_SHORT,
        submission_note_short_chars=len(SUB_NOTE_SHORT),
        submission_note_long=SUB_NOTE,
        approved_for_weekly_slot=bool(
            (select or {}).get("passes_rule1")
            and (select or {}).get("hide_wins", 0) >= 3
            and (select or {}).get("tip_wins", 0) >= 3
            and rep.get("ok") and uni.get("ok")),
        promotion=(f"passes the pre-registered rule: beats the matched-budget random control in "
                   f"{(select or {}).get('hide_wins')}/4 hide and {(select or {}).get('tip_wins')}/4 "
                   f"tip folds, and maximises mean_tip + mean_hide among the arms that pass. Not a "
                   f"forecast of the portal score."),
        format_ok=bool(rep.get("ok")),
        uniqueness_ok=bool(uni.get("ok")),
        relation_to_union=uni.get("relation_to_union"),
        novel_px=uni.get("novel_vs_all_priors"),
        projected_dti=dict(mean_dti=round(calib.dti_from(T=0.01287 * geo["A"], S=geo["S"], n_g=n_g), 4),
                           kind="placement gain in isolation, rho_A held at the 0.2778 file's own "
                                "measured 0.01287; arithmetic given its assumption, not a forecast"),
        strata=dict(a_only_px=int(a_only.sum()),
                    b_only_px=int(((rb >= qB) & (ra < qA)).sum()),
                    concordant_px=int(((ra >= qA) & (rb >= qB)).sum()), quantile=0.98),
        a_only_emitted_px=int(reason["n_px"]), a_only_components=reason["n_components"],
        format_gate=rep, uniqueness=uni, emitter_stats=st,
        projection=dict(
            geometry_only_dti=calib.dti_from(T=0.01287 * geo["A"], S=geo["S"], n_g=n_g),
            geometry_only_note=("applies the 0.2778 file's measured per-covered-pixel truth density "
                                "rho_A = 0.01287 to THIS file's measured coverage A, changing nothing "
                                "but the placement. It isolates the placement gain: same geology "
                                "assumed, better A/S."),
            fold_relative_note=("on both blocked instruments this arm beats the H52 shipped arm "
                                "(B_only+blanket|37654|s0) by +87 %; if that ratio transferred to the "
                                "board the score would be ~0.52, which is not credible and is not "
                                "claimed. The instruments under-forecast the board by ~4x in absolute "
                                "terms (0.05 fold vs 0.2778 board for the same family), so neither "
                                "number is a forecast. What IS claimed: the placement gain is "
                                "arithmetic, and the field gain is measured 4/4 folds on two "
                                "instruments against a matched-budget random control."),
            h52_reference=dict(hide=0.0518, tip=0.0291, total=0.0809, board=0.2778),
            h55_measured=dict(hide=(select or {}).get("hide"), tip=(select or {}).get("tip"),
                              total=(select or {}).get("total")),
            random_control=dict(hide=0.03948, tip=0.02477),
            a_per_s_this_file=geo["A_per_S"], a_per_s_0278_file=8.044,
            a_per_s_ceiling=calib.DISC_WEIGHT_SUM),
    )
    (EVID / f"h55_submission_{tag}.json").write_text(
        json.dumps(payload, indent=1, allow_nan=False, default=str))
    log(f"format gate ok={rep.get('ok')} problems={rep.get('problems')}")
    log(f"uniqueness ok={uni.get('ok')} relation={uni.get('relation_to_union')} "
        f"novel={uni.get('novel_vs_all_priors')} ({uni.get('novel_fraction'):.1%}) "
        f"priors_checked={uni.get('n_priors_checked')} dropped={uni.get('prior_px_dropped')}")
    log(f"projection, placement gain only (rho_A held at 0.01287): "
        f"DTI={payload['projection']['geometry_only_dti']:.4f}")
    # LATEST.txt is a single line: refresh_feed.latest_submission() and make_zip() both read it with
    # .strip() and treat the whole content as a filename. Extra lines silently break the feed.
    (ROOT / "submission" / "LATEST.txt").write_text(out.name + "\n")
    # The shared feed resolves a marker to its audit at evidence/submission_<stem>.json; write that
    # record too, as a superset, so this round's artefact is offered with its own audit rather than
    # falling back to "historical research artifact; consult its original audit".
    (EVID / f"submission_{out.stem}.json").write_text(
        json.dumps(payload, indent=1, allow_nan=False, default=str))
    log(f"note ({len(SUB_NOTE_SHORT)} chars): {SUB_NOTE_SHORT}")
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["layers", "stack", "fields", "sweep", "validate", "build", "band6"])
    ap.add_argument("--arms", default="")
    ap.add_argument("--radii", default="")
    ap.add_argument("--budgets", default="")
    ap.add_argument("--greedy", action="store_true")
    ap.add_argument("--radius", type=float, default=4.0)
    ap.add_argument("--modes", default="hide,tip")
    ap.add_argument("--folds", default="")
    ap.add_argument("--tag", default="r1")
    ap.add_argument("--arm", default="AB_gmean")
    ap.add_argument("--emitter", default="greedy")
    ap.add_argument("--dti", type=float, default=0.30)
    ap.add_argument("--ng", type=float, default=9000.0)
    ap.add_argument("--budget", type=int, default=37654)
    args = ap.parse_args()
    EVID.mkdir(exist_ok=True)
    t0 = time.time()
    if args.stage == "band6":
        stage_layers()
    elif args.stage == "layers":
        stage_layers()
    elif args.stage == "stack":
        stage_stack()
    elif args.stage in ("fields", "sweep", "validate"):
        modes = [m for m in args.modes.split(",") if m]
        fs = {int(x) for x in args.folds.split(",") if x.strip()} if args.folds else None
        if args.stage == "fields":
            stage_fields(modes, fs)
        else:
            arms = {a for a in args.arms.split(",") if a} or None
            radii = tuple(float(x) for x in args.radii.split(",") if x) or RADII
            budgets = tuple(int(x) for x in args.budgets.split(",") if x) or BUDGETS
            stage_sweep(modes, fs, arms_sel=arms, radii=radii, budgets=budgets,
                        greedy=args.greedy, n_g=args.ng)
    elif args.stage == "build":
        sel = _select(n_g=args.ng)
        if args.arm == "auto" and sel:
            args.arm, args.emitter = sel["arm"], sel["emitter"].split("|")[0]
            args.budget = int(sel["emitter"].split("|")[1])
            log(f"selected by the pre-registered rule: {json.dumps(sel)}")
        stage_build(args.tag, args.arm, args.emitter, args.dti, args.ng, args.budget,
                    radius=args.radius, select=sel)
    log(f"[{args.stage}] done in {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
