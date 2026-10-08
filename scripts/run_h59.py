#!/usr/bin/env python3
"""H59 — the brief's co-training round re-run on pinned bytes, plus four registered challengers.

Runs strictly under ``registry/h59_preregistration.json`` (frozen before this file executed); the
hypothesis text is ``knowledge/20_hypotheses_H59_preregistered.md``.

Stages (each checkpointed under work/h59 so an interrupted run resumes and never re-scores):

  preflight   verify every input against the registry/data_manifest.json pins; measure the tracked
              data/*.tif stubs and record that they are NOT the pinned bytes (fail closed on any
              pinned mismatch; the tracked-stub inequality is a recorded fact, not an error).
  layers      build the uint8 rank-encoded layer stack from work/h59_pinned (h57.build_layers with
              an explicit data_dir), plus three extra rank-encoded layers H59-C/E need (bands 7/8/10).
  cotrain     block-buffered four-fold fits of View A and View B; out-of-fold fields pa_oof/pb_oof;
              the brief's independence test; the confident-donor/abstain-receiver pseudo-label
              exchange with its AUC measurement; the agreement strata with depth-to-basement medians.
  validate    matched-budget arms on the tip and hide instruments for the incumbent fields, the
              challenger fields, the H59-D halo-pool population arm, and the per-budget random
              control; the registered promotion and slot gates are decided here, mechanically.

No leaderboard score enters any fit, field, fold, or arm here; revealed-preference arithmetic is
used only in the build script, for budget projection, and is labelled conditional there.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import grid as G                       # noqa: E402
from gems52 import h57                              # noqa: E402
from gems52 import h58                              # noqa: E402
from gems52 import holdout as HO                    # noqa: E402
from gems52 import metric as M                      # noqa: E402
from gems52 import spatial                          # noqa: E402
from gems52 import revealed                         # noqa: E402

DATA = ROOT / "work/h59_pinned"
WORK = ROOT / "work/h59"
EV = ROOT / "evidence"
PREREG = json.loads((ROOT / "registry/h59_preregistration.json").read_text())
SEED = int(PREREG["protocol"]["seed"])
Q_CONF = float(PREREG["protocol"]["thresholds"]["q_conf"])
Q_ABSTAIN = float(PREREG["protocol"]["thresholds"]["q_abstain"])
BLOCK = int(PREREG["protocol"]["thresholds"]["block_px"])
MIN_NEG = int(PREREG["protocol"]["thresholds"]["min_negatives_per_block"])
N_NEG_TRAIN = int(PREREG["protocol"]["thresholds"]["neg_train"])
BUDGETS = tuple(PREREG["protocol"]["budgets_px"])
LIFT_BAR = 0.005
FOLD_BAR = 3
MIN_COH = 0.25

EXTRA_LAYERS = [  # (pinned file, band, name) — needed by H59-C/E, absent from the H57 spec
    ("training_features.tif", 7, "A_geod_shear"),
    ("training_features.tif", 8, "A_geod_dilat"),
    ("training_features.tif", 10, "A_eq_distance"),
]


def log(m: str) -> None:
    print(f"[h59 {time.strftime('%H:%M:%S')}] {m}", flush=True)


def done(path: Path) -> bool:
    return path.exists()


def read_mask(path: Path, thresh: float = 0.5) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1)
    a[~np.isfinite(a)] = 0.0
    return a > thresh


def read_layer(layers: h57.Layers, name: str) -> np.ndarray:
    """Full-grid float32 in [0,1] from the cached uint8 rank stack (0..255 divided back)."""
    idx = layers.index([name])
    out = np.zeros(G.SHAPE, np.float32)
    for r0 in range(0, G.SHAPE[0], 512):
        r1 = min(r0 + 512, G.SHAPE[0])
        out[r0:r1] = layers.matrix(idx, r0, r1).reshape(r1 - r0, G.SHAPE[1])
    return out


def read_extra(name: str, suffix: str) -> np.ndarray:
    """Full-grid float32 [0,1] from an H59 extra rank-encoded layer."""
    return np.load(WORK / f"extra_{name}_{suffix}.npy").astype(np.float32) / 255.0


_YY, _XX = np.mgrid[0:G.SHAPE[0], 0:G.SHAPE[1]]


def ridge_strength(field: np.ndarray) -> np.ndarray:
    """Ridge response of a scalar field (same recipe as scripts/validate_h57.py, which took it
    from the standard lineament transform: |grad| minus the best neighbour one pixel across the
    gradient direction — non-maximum suppression across strike, never label-dependent)."""
    f = ndimage.gaussian_filter(np.asarray(field, np.float32), 2.0)
    gy, gx = np.gradient(f)
    mag = np.hypot(gy, gx)
    ang = np.arctan2(gy, gx)
    best = np.zeros_like(mag)
    for da in (-0.15, 0.15):
        sx = np.sin(ang + da)
        sy = -np.cos(ang + da)
        best = np.maximum(best, ndimage.map_coordinates(mag, [_YY + sy, _XX + sx],
                                                         order=1, mode="nearest"))
    return (np.clip(mag - best, 0.0, None) / np.maximum(mag, 1e-6)).astype(np.float32)


# ----------------------------------------------------------------------------------------------- preflight
def stage_preflight() -> None:
    out = EV / "h59_preflight_integrity.json"
    if done(out):
        log("preflight cached")
        return
    log("verifying pinned inputs against the manifest (fail closed)")
    try:
        receipts = h58.verify_manifest(ROOT / "registry/data_manifest.json", DATA)
        all_ok = len(receipts) == 23 and all(r["matches_pin"] for r in receipts)
    except Exception as exc:                      # record, then fail closed
        (EV / "h59_preflight_integrity.json").write_text(json.dumps(
            dict(round="H59-preflight", pinned_all_ok=False, error=str(exc)[:400]), indent=1) + "\n")
        raise
    tracked = {}
    for name in ("training_features.tif", "labels.tif", "sample_submission.tif"):
        p = ROOT / "data" / name
        pin = next(r for r in receipts if r["dest"] == name)
        d = h58.sha256_file(p)
        tracked[name] = dict(local_bytes=p.stat().st_size, local_sha256=d,
                             local_matches_manifest=bool(d == pin["expected_sha256"]))
    rec = dict(round="H59-preflight",
               observed_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               manifest="registry/data_manifest.json", data_root=str(DATA.relative_to(ROOT)),
               pinned_files_verified=len(receipts), pinned_all_ok=bool(all_ok),
               qualification=("SHA/byte verification of owner-mirror pins proves mirror integrity, "
                              "NOT organizer authentication; the DrivenData data tab is login-walled"),
               tracked_data_comparison=tracked,
               tracked_policy=("No H59 number is computed from tracked data/*.tif; the tracked "
                               "training_features.tif is a 19-band all-zero grid stub"),
               files=[r for r in receipts])
    if not all_ok:
        raise SystemExit("preflight FAILED: a pinned input does not match its manifest entry")
    out.write_text(json.dumps(rec, indent=1, allow_nan=False) + "\n")
    log(f"preflight OK: {len(receipts)}/23 pins match; tracked stubs recorded as not pinned")


# ----------------------------------------------------------------------------------------------- layers
def stage_layers() -> None:
    log("building the layer stack from the pinned root")
    meta = h57.build_layers(work=str(WORK), chunk=600, data_dir=DATA)
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    for i, (p, band, nm) in enumerate(EXTRA_LAYERS):
        arrs = h57.derived_layers(str(DATA / p), band, valid, 600)
        for suffix, arr in zip(("val", "grad", "range"), arrs):
            np.save(WORK / f"extra_{nm}_{suffix}.npy", h57._rank_u8(arr, valid))
            log(f"extra layer {nm}_{suffix} ({int(valid.sum())} px)")
    log(f"layer stack ready: {len(meta['names'])} cached layers + {3 * len(EXTRA_LAYERS)} extra")


# ----------------------------------------------------------------------------------------------- cotrain
def _gather(layers, idx, flat_idx, width):
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
        block = np.asarray(mm[idx, int(r), :], dtype=np.uint8)
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
    rows = []
    h, w = neg_mask.shape
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


def stage_cotrain() -> None:
    out = EV / "h59_cotrain.json"
    if done(out):
        log("cotrain cached")
        return
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    log(f"footprint {int(valid.sum())} px, catalogue {int(cat.sum())} px (pinned bytes)")
    layers = h57.Layers(str(WORK))
    idx_a = layers.index([f"{n}_{s}" for n in h57.VIEW_A_LAYERS for s in ("val", "grad", "range")])
    idx_b = layers.index([f"{n}_{s}" for n in h57.VIEW_B_LAYERS for s in ("val", "grad", "range")])
    folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002, seed=SEED,
                          mode="block")
    cat_dil = ndimage.binary_dilation(cat, iterations=h57.NEG_CLEAR_PX)
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor
    pa_oof = np.full(G.SHAPE, np.nan, np.float32)
    pb_oof = np.full(G.SHAPE, np.nan, np.float32)
    neg_rows, fold_receipts = [], []
    for f in folds:
        fit, reg = f["fit"], f["region"]
        _, pa = fit_and_predict(layers, idx_a, cat, valid, fit, SEED + f["fold"], f"A/f{f['fold']}")
        _, pb = fit_and_predict(layers, idx_b, cat, valid, fit, SEED + f["fold"], f"B/f{f['fold']}")
        pa_oof[reg] = pa[reg]
        pb_oof[reg] = pb[reg]
        neg_mask = reg & ~cat_dil
        rows = block_error_rows(pa, pb, neg_mask, f["fold"])
        neg_rows.extend(rows)
        fold_receipts.append(dict(fold=f["fold"], n_fit=int(fit.sum()), n_region=int(reg.sum()),
                                  n_boundary=int(f["boundary"].sum()), n_truth=int(f["n_truth"]),
                                  n_held_components_px=int(f["n_held"]),
                                  cat_in_fit=int((cat & fit).sum()),
                                  cat_in_region=int((cat & reg).sum()),
                                  n_negatives=int(neg_mask.sum()), n_blocks=len(rows)))
        log(f"fold {f['fold']}: {int(fit.sum())} fit px, {int(reg.sum())} region px, "
            f"{len(rows)} blocks, {int((cat & fit).sum())} cat px in fit")
    np.save(WORK / "pa_oof.npy", pa_oof)
    np.save(WORK / "pb_oof.npy", pb_oof)

    ind = spatial.independence(neg_rows, threshold=0.60, min_blocks=20)
    ind["pixel_level"] = pixel_corr(pa_oof, pb_oof, valid & ~cat_dil)
    ind.update(q_conf=Q_CONF, block_px=BLOCK, min_negatives_per_block=MIN_NEG)
    log(f"independence: measured={ind['measured']} allow_exchange={ind['allow_exchange']} "
        f"max|r|={ind['max_abs_correlation']}")

    pa0 = np.nan_to_num(pa_oof, nan=0.0)
    pb0 = np.nan_to_num(pb_oof, nan=0.0)
    strata = h57.disagreement(pa0, pb0, permitted, q_conf=Q_CONF, q_abstain=Q_ABSTAIN)
    depth = G.read_band(DATA / "training_features.tif", 15)
    strata["median_depth_to_basement_m"] = {
        k: float(np.median(depth[strata["masks"][k]]))
        for k in ("a_only", "b_only", "concordant") if strata["masks"][k].any()}
    strata["median_depth_to_basement_m"]["permitted"] = float(np.median(depth[permitted]))
    strata["evaluated_px"] = int(np.isfinite(pa_oof).sum())
    for k in ("a_only", "b_only", "concordant", "neither"):
        np.save(WORK / f"stratum_{k}.npy", strata["masks"][k])
    log(f"strata {strata['counts']}")

    # ---- pseudo-label exchange (brief's rule), fold-0 unlabelled quadrant ----------------------
    pseudo = {"ran": False, "reason": None}
    f0 = folds[0]
    if ind["allow_exchange"]:
        reg0, fit0 = f0["region"], f0["fit"]
        forbidden = cat | corridor | ~reg0 | f0["boundary"]
        idx, receipt = spatial.whole_pseudo_segments(pa0, pb0, reg0, forbidden, Q_CONF,
                                                     Q_ABSTAIN, Q_CONF, side=BLOCK)
        if idx.size:
            from sklearn.metrics import roc_auc_score
            m = reg0 & ~f0["boundary"]
            pos, neg = h57.labelled_pixels(cat, valid, fit0, seed=SEED + 99, n_neg=N_NEG_TRAIN)
            X = np.vstack([_gather(layers, idx_a, pos, G.SHAPE[1]),
                           _gather(layers, idx_a, neg, G.SHAPE[1]),
                           _gather(layers, idx_a, idx, G.SHAPE[1])])
            y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8),
                                np.ones(idx.size, np.int8)])
            clf = h57.fit_view(X, y)
            del X, y
            base = dict(ran=True, n_pseudo_px=int(idx.size), n_segments=len(receipt),
                        donor_threshold=Q_CONF, receiver_band=[Q_ABSTAIN, Q_CONF],
                        n_eval_px=int(m.sum()),
                        rule="whole 8-connected segments inside the fold-0 unlabelled quadrant, "
                             "one 50x50 block each, never on a catalogue or corridor pixel; donor "
                             "confident, receiver in the abstention band")
            if int(cat[m].sum()) < 100 or int((~cat[m]).sum()) < 100:
                base.update(auc_view_A_before=None, auc_view_A_after=None, delta_auc=None,
                            skipped="fold-0 quadrant holds too few held-out catalogue pixels for "
                                    "an AUC; exchange executed and reported, AUC skipped")
                log(f"pseudo-label exchange: {int(idx.size)} px / {len(receipt)} segments; "
                    "AUC skipped (degenerate quadrant)")
            else:
                before = float(roc_auc_score(cat[m], pa0[m]))
                after_grid = np.zeros(G.SHAPE, np.float32)
                for r0 in range(0, G.SHAPE[0], 500):
                    r1 = min(r0 + 500, G.SHAPE[0])
                    Xq = layers.matrix(idx_a, r0, r1)
                    after_grid[r0:r1] = clf.predict_proba(Xq)[:, 1].astype(np.float32).reshape(
                        r1 - r0, G.SHAPE[1])
                after = float(roc_auc_score(cat[m], after_grid[m]))
                np.save(WORK / "pa_pseudo.npy", after_grid)
                base.update(auc_view_A_before=before, auc_view_A_after=after,
                            delta_auc=after - before)
                log(f"pseudo-label exchange: {int(idx.size)} px / {len(receipt)} segments, "
                    f"AUC {before:.4f} -> {after:.4f} (d={after - before:+.4f})")
            pseudo = base
        else:
            pseudo["reason"] = "no whole segment satisfied donor-confident / receiver-abstains"
    else:
        pseudo["reason"] = ("independence test did not license the exchange: "
                            + str(ind.get("reason")))
    if not pseudo.get("ran"):
        log("pseudo-label exchange NOT run: " + str(pseudo.get("reason")))

    abandon = bool(ind["measured"] and ind["max_abs_correlation"] is not None
                  and ind["max_abs_correlation"] >= 0.60)
    rep = dict(round="H59-cotrain-v1", seed=SEED, runtime_s=round(time.time() - t0, 1),
               data_root=str(DATA.relative_to(ROOT)),
               qualification=("pinned owner-mirror bytes, SHA-verified; not organizer-authenticated"),
               footprint_px=int(valid.sum()), catalogue_px=int(cat.sum()),
               folds=fold_receipts, independence=ind,
               strata={k: v for k, v in strata.items() if k != "masks"},
               pseudo_label=pseudo,
               abandonment=("co-training abandoned by the registered independence rule"
                            if abandon else None))
    out.write_text(json.dumps(rep, indent=1, allow_nan=False, default=str) + "\n")
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")


# ----------------------------------------------------------------------------------------------- validate
def stage_validate() -> None:
    out = EV / "h59_validation.json"
    if done(out):
        log("validation cached")
        return
    t0 = time.time()
    valid = G.footprint_from(DATA / "training_features.tif", bands="all")
    with rasterio.open(DATA / "labels.tif") as src:
        cat = src.read(1) == 1
    pa = np.nan_to_num(np.load(WORK / "pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load(WORK / "pb_oof.npy"), nan=0.0).astype(np.float32)
    layers = h57.Layers(str(WORK))
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    # ------- challenger fields (definitions verbatim from the registered hypothesis doc) --------
    coh_l = read_layer(layers, "B_lidar_coh100_val")
    exp_l = read_layer(layers, "B_lidar_ex_max_val")
    lid = np.sqrt(np.maximum(coh_l, 0.0) * np.maximum(exp_l, 0.0)).astype(np.float32)
    lid = (lid / max(float(lid.max()), 1e-6)).astype(np.float32)
    lid_med = float(np.median(lid[permitted])) if permitted.any() else 0.0
    u = np.maximum(pa, pb)
    b_only = np.load(WORK / "stratum_b_only.npy")
    fields = {
        "clf_union": u,
        "clf_view_A": pa,
        "clf_view_B": pb,
        "H59A_corroborated": (u * (0.55 + 0.45 * lid)).astype(np.float32),
        "H59B_artifact_suppressed": np.maximum(
            pa, pb * (1.0 - 0.5 * (b_only & (lid < lid_med)))).astype(np.float32),
    }
    # H59-C: strain-gradient coherence-gated ridge x seismicity-proximity weight, label-free.
    # Stack grads are [0,1]; ridge/strike math runs on the uint8 scale like validate_h57's *255.
    s2 = ((read_layer(layers, "A_geod_2ndinv_grad") + read_extra("A_geod_shear", "grad")
           + read_extra("A_geod_dilat", "grad")) * 255.0).astype(np.float32)
    coh, strike, _ = revealed.strike_field(s2, sigma_px=6.0)
    eqd = read_extra("A_eq_distance", "val")            # rank uint8: larger = farther from events
    eqw = (1.0 - eqd).astype(np.float32)                 # near-event pixels weigh more
    fields["H59C_strain_lineament"] = np.where(
        coh >= MIN_COH, coh * ridge_strength(s2) * (0.5 + 0.5 * eqw), 0.0).astype(np.float32)
    # H59-E: conductivity plumb-line modifier under thick cover
    cond = read_layer(layers, "A_cond_surf_val").astype(np.float32)
    dep = G.read_band(DATA / "training_features.tif", 15)
    deep = np.zeros(G.SHAPE, bool)
    if permitted.any():
        deep = dep > float(np.median(dep[permitted]))
    cr = np.where(permitted & deep, cond, 0.0).astype(np.float32)
    hi = float(np.percentile(cr[cr > 0], 99.0)) if (cr > 0).any() else 1.0
    fields["H59E_geoconj"] = (u * (0.6 + 0.4 * np.clip(cr / max(hi, 1e-6), 0.0, 1.0))
                              ).astype(np.float32)
    log("fields built: " + ", ".join(fields))
    for nm, fv in fields.items():
        np.save(WORK / f"field_{nm}.npy", fv.astype(np.float32))   # byte-exact reuse by build

    # ------- H59-D: core-annulus pool (artifact core), tip instrument, registered rule ----------
    core = read_mask(DATA / "reference/h33-2-b2-zeros.tif") & \
        read_mask(DATA / "scored/gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif")
    halo = ndimage.binary_dilation(core, iterations=6) & ~ndimage.binary_dilation(core, iterations=2)
    log(f"H59-D core {int(core.sum())} px; halo {int(halo.sum())} px")

    results = []
    rng = np.random.default_rng(SEED)
    for mode in ("tip", "hide"):
        folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                              seed=SEED, mode=mode)
        for f in folds:
            blocked = ndimage.binary_dilation(f["visible"] & valid, iterations=h57.CORRIDOR_PX)
            legal = f["region"] & permitted & ~blocked
            truth = f["truth"] & f["region"] & valid
            flat_pool = np.flatnonzero(legal.ravel())

            for k in BUDGETS:
                def addk(arm, nodes):
                    p = np.where(f["region"], nodes.astype(np.float32), 0.0)
                    r = M.dti(p, truth)
                    results.append(dict(mode=mode, fold=f["fold"], budget=int(k), arm=arm,
                                        dti=round(float(r["dti"]), 6),
                                        emitted=int((p > 0).sum()), tpw=round(float(r["tpw"]), 2),
                                        n_truth=int(r["n_truth"])))

                take = rng.choice(flat_pool, min(k, flat_pool.size), replace=False)
                rnd = np.zeros(G.SHAPE, bool)
                rnd.ravel()[take] = True
                addk("random", rnd)
                for name, fld in fields.items():
                    score = np.where(legal, fld, 0.0).astype(np.float32)
                    addk(f"RANK_{name}", h57.iso_select(score, legal, k, min_px=3.0, nms_px=5))
                if mode == "tip":
                    hp = legal & halo
                    score = np.where(hp, fields["H59A_corroborated"], 0.0).astype(np.float32)
                    addk("POP_H59D_halo", h57.iso_select(score, hp, k, min_px=3.0, nms_px=5))
                    full = np.where(legal, fields["H59A_corroborated"], 0.0).astype(np.float32)
                    addk("POP_H59D_fullpool_control",
                         h57.iso_select(full, legal, k, min_px=3.0, nms_px=5))
            line = ", ".join(
                f"{r['arm'].replace('RANK_', '')}={r['dti']:.4f}"
                for r in results if r["mode"] == mode and r["fold"] == f["fold"]
                and r["budget"] == BUDGETS[-1] and r["arm"].startswith(("RANK_", "POP")))
            log(f"{mode} f{f['fold']} k={BUDGETS[-1]}: {line}")

    def vals(mode, k, arm):
        return [r["dti"] for r in results if r["mode"] == mode and r["budget"] == k
                and r["arm"] == arm]

    def mean_of(mode, k, arm):
        v = vals(mode, k, arm)
        return float(np.mean(v)) if v else float("nan")

    def folds_won(mode, k, arm, ref):
        w = 0
        for fo in range(4):
            a = [r["dti"] for r in results if r["mode"] == mode and r["budget"] == k
                 and r["arm"] == arm and r["fold"] == fo]
            b = [r["dti"] for r in results if r["mode"] == mode and r["budget"] == k
                 and r["arm"] == ref and r["fold"] == fo]
            w += bool(a and b and a[0] > b[0])
        return w

    table = {}
    names = list(fields)
    for mode in ("tip", "hide"):
        for k in BUDGETS:
            cell = {n: round(mean_of(mode, k, f"RANK_{n}"), 6) for n in names}
            cell["random"] = round(mean_of(mode, k, "random"), 6)
            table[f"{mode}@{k}"] = dict(sorted(cell.items(), key=lambda kv: -kv[1]))

    gates = {}
    for n in names:
        beats_union = all(mean_of(mo, k, f"RANK_{n}") > mean_of(mo, k, "RANK_clf_union")
                          for mo in ("tip", "hide") for k in BUDGETS)
        lifts = {mo: round(mean_of(mo, BUDGETS[-1], f"RANK_{n}")
                           - mean_of(mo, BUDGETS[-1], "random"), 6)
                 for mo in ("tip", "hide")}
        wins = {mo: folds_won(mo, BUDGETS[-1], f"RANK_{n}", "random") for mo in ("tip", "hide")}
        gates[n] = dict(promotes_over_union=bool(beats_union),
                        mean_lift_vs_random_at_37654=lifts,
                        folds_won_vs_random_at_37654=wins,
                        slot_bar_met=bool(min(lifts.values()) >= LIFT_BAR
                                         and min(wins.values()) >= FOLD_BAR))
    halo_mean = mean_of("tip", BUDGETS[-1], "POP_H59D_halo")
    full_mean = mean_of("tip", BUDGETS[-1], "POP_H59D_fullpool_control")
    gates["H59D_halo_pool"] = dict(
        tip_at_37654_halo=round(halo_mean, 6), tip_at_37654_fullpool=round(full_mean, 6),
        halo_wins=bool(halo_mean > full_mean),
        note=("H59-D promotes iff the core-annulus pool beats the same field's full legal pool on "
              "the tip instrument at the 37,654 budget (registered rule)"))
    incumbent = dict(
        frozen_union_tip37654_h57=0.005444,
        this_run_union_tip37654=round(mean_of("tip", BUDGETS[-1], "RANK_clf_union"), 6),
        frozen_union_hide37654_h57=0.006445,
        this_run_union_hide37654=round(mean_of("hide", BUDGETS[-1], "RANK_clf_union"), 6))

    rep = dict(round="H59-validation-v1", seed=SEED, runtime_s=round(time.time() - t0, 1),
               protocol="registry/h59_preregistration.json -> protocol", field_table=table,
               gates=gates, incumbent_reproduction=incumbent, results=results,
               caveats=[
                   "Simulator truth is the mapped catalogue minus visible; relative instrument only "
                   "(Spearman(reported, simulated DTI) = -0.1045, knowledge/10 s5).",
                   "A required-novel arm cannot be scored by this simulator at all (knowledge/18 "
                   "s6); the H59-D gate uses a pool statistic inside the tip instrument, stated here.",
                   "The pinned inputs are owner-mirror SHA-verified, not organizer-authenticated."])
    out.write_text(json.dumps(rep, indent=1, allow_nan=False, default=str) + "\n")
    log(f"wrote {out.name} in {time.time() - t0:.0f}s")
    promote = [n for n in names if gates[n]["promotes_over_union"]]
    best = max(promote, key=lambda n: mean_of("hide", BUDGETS[-1], f"RANK_{n}"), default=None)
    (WORK / "promoted_field.txt").write_text("clf_union" if best is None else best)
    (WORK / "halo_promoted.txt").write_text("1" if gates["H59D_halo_pool"]["halo_wins"] else "0")
    log(f"promoted field: {best or 'clf_union (incumbent retained)'}; "
        f"halo promoted: {gates['H59D_halo_pool']['halo_wins']}")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    EV.mkdir(exist_ok=True)
    stage_preflight()
    stage_layers()
    stage_cotrain()
    stage_validate()
    log("H59 fit/validation complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
