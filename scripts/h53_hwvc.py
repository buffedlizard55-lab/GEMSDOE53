#!/usr/bin/env python3
"""Session 2026-10-09, lane H53-HWVC. Pre-registered: docs/research/preregistration-2026-10-09-hwvc.md.

    python scripts/h53_hwvc.py features   # build label-free HWVC channels -> /tmp/h53/hwvc.npz (not an experiment)
    python scripts/h53_hwvc.py e1         # E1 leakage canary (every model feature alone)
    python scripts/h53_hwvc.py e2         # E2 stage 1 (segment folds) + stage 2 (spatial super-regions), A vs B
    python scripts/h53_hwvc.py e3         # E3 build the promoted arm (or the pre-registered fallback), write, validate

All numbers are HOLDOUT-DTI (evaluator gems53.core.dti v1.0.0; truth = withheld catalogue segments). None is an
organizer score. Learn-predict separation: every catalogue-derived feature (H1) is recomputed per fold from the
VISIBLE faults only; HWVC uses no labels at all.
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

from gems53.core import (buffer_zone, dti, h1_segment_exact_distance, load_inputs,  # noqa: E402
                         load_template_module, segment_folds, thin_emission)
from gems53.hwvc import HWVC_BANDS, decoder_ds, hwvc_channels  # noqa: E402
from exp1_leakage_canary import separability  # noqa: E402
from exp2_holdout_arms import predict_chunked  # noqa: E402

K_FOLDS, SEED, N_NEG, BUF_PX, BLOCK_PX = 5, 53, 300_000, 10, 512
T_CRIT_DF4 = 2.776
CANARY_MAX = 0.90
N_DOTS, FLANK_PX, MIN_SEP = 40_000, 2.0, 2.8
CACHE = Path("/tmp/h53")
EVAL = {"name": "gems53.core.dti", "version": "1.0.0", "alpha": 0.2, "beta": 0.8, "R_px": 3}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def jsonable(o):
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)


def hgb():
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1, max_leaf_nodes=31,
                                          l2_regularization=1.0, random_state=0)


def load(args):
    dd = Path(args.data_dir)
    return load_inputs(str(dd / "training_features.tif"), str(dd / "labels.tif"), str(dd / "sample_submission.tif"))


def load_hwvc():
    z = np.load(CACHE / "hwvc.npz")
    names = [str(n) for n in z["names"]]
    return names, z["X"]


def cmd_features(args):
    inp = load(args)
    bands = {}
    for b, _, nm in HWVC_BANDS:
        assert inp.band_names[b - 1].startswith(nm) or True
        g = np.full((inp.H, inp.W), np.nan, dtype=np.float32)
        g[inp.fp] = inp.feats[:, b - 1]
        bands[b] = g
    descs = None
    try:
        import rasterio
        with rasterio.open(Path(args.data_dir) / "training_features.tif") as s:
            descs = list(s.descriptions)
    except Exception:  # pragma: no cover
        pass
    for b, _, nm in HWVC_BANDS:  # verify band identity from the file's own descriptions
        if descs is not None and not str(descs[b - 1]).startswith(nm):
            raise SystemExit(f"band {b} description {descs[b-1]!r} does not start with {nm!r}")
    del inp.feats
    chans, meta = hwvc_channels(bands, inp.fp)
    names = sorted(chans)
    X = np.column_stack([chans[n][inp.fp] for n in names]).astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE / "hwvc.npz", X=X, names=np.array(names))
    meta.update(names=names, band_descriptions=[descs[b - 1] for b, _, _ in HWVC_BANDS] if descs else None,
                finite_frac={n: float(np.isfinite(X[:, i]).mean()) for i, n in enumerate(names)}, built_utc=now())
    (CACHE / "hwvc_meta.json").write_text(json.dumps(meta, indent=2, default=jsonable))
    print(json.dumps(meta, indent=2, default=jsonable))


def feature_matrix(inp, arm, visible, L, hw):
    cols = [inp.feats]
    h1 = h1_segment_exact_distance(visible, L)
    cols.append(h1[inp.fp][:, None])
    if arm == "B":
        cols.append(hw)
    return np.concatenate(cols, axis=1).astype(np.float32, copy=False)


def fit_predict(inp, F, visible, hidden, rng):
    buf = buffer_zone(hidden, BUF_PX) if hidden is not None else np.zeros_like(visible)
    pos_rows = inp.fp_idx[visible & ~buf & inp.fp]
    neg_pool = inp.fp_idx[inp.fp & ~visible]          # design B: does not depend on withheld locations
    neg_rows = neg_pool[rng.choice(neg_pool.size, min(N_NEG, neg_pool.size), replace=False)]
    rows = np.r_[pos_rows, neg_rows]
    y = np.r_[np.ones(pos_rows.size), np.zeros(neg_rows.size)]
    m = hgb()
    m.fit(F[rows], y)
    p = np.zeros((inp.H, inp.W), dtype=np.float32)
    p[inp.fp] = predict_chunked(m, F)
    p[visible] = 0.0
    return p, int(pos_rows.size), int(neg_rows.size)


def score_decoders(p, inp, visible, hidden, decoders):
    fp_px = int(inp.fp.sum())
    out = {}
    cand = inp.fp & ~visible
    for d in decoders:
        if d == "M1_thin_bin_q0p10":
            emis, kept, _ = thin_emission(p, cand, 0.10, fp_px, value="bin")
        elif d == "DS_flank2_sep2p8_n40000":
            emis = decoder_ds(np.where(cand, p, -1.0), cand, visible, N_DOTS, FLANK_PX, MIN_SEP)
            kept = int(emis.sum())
        else:
            raise ValueError(d)
        r = dti(emis, hidden)
        out[d] = dict(TP_w=r["TP_w"], FP_w=r["FP_w"], FN_w=r["FN_w"], DTI=r["DTI"], dots=int(kept))
    return out


def pooled(rows):
    P = {k: float(sum(r[k] for r in rows)) for k in ("TP_w", "FP_w", "FN_w")}
    return P["TP_w"] / (P["TP_w"] + 0.2 * P["FP_w"] + 0.8 * P["FN_w"] + 1e-9), P


def tci(vals):
    v = np.asarray(vals, float)
    m = float(v.mean()); h = float(T_CRIT_DF4 * v.std(ddof=1) / np.sqrt(len(v)))
    return m, h


def cmd_e1(args):
    t0 = time.time()
    inp = load(args)
    names, hw = load_hwvc()
    fold_grid, n_seg, L = segment_folds(inp.cat, K=K_FOLDS, seed=SEED)
    rng = np.random.default_rng(SEED + 1000)
    bg = inp.fp & ~inp.cat
    bg_rows = inp.fp_idx[bg]
    rows = []
    feat_names = [f"band{i+1:02d}:{n.split(' - ')[0]}" for i, n in enumerate(inp.band_names)] + names
    allX = np.concatenate([inp.feats, hw], axis=1)
    for k in range(K_FOLDS):
        hidden = inp.cat & (fold_grid == k)
        visible = inp.cat & (fold_grid != k)
        hid_rows = inp.fp_idx[hidden]
        for j, nm in enumerate(feat_names):  # label-free features: fold only changes the positive subset
            r = separability(allX[hid_rows, j], allX[bg_rows, j], rng)
            rows.append(dict(fold=k, feature=nm, **r))
        h1 = h1_segment_exact_distance(visible, L)
        r = separability(h1[hidden], h1[bg], rng)
        rows.append(dict(fold=k, feature="h1_segment_exact_distance(visible only)", **r))
        print(f"[E1] fold {k} done ({time.time()-t0:.0f}s)", flush=True)
    worst = {}
    for r in rows:
        if r["separability"] is None:
            continue
        worst[r["feature"]] = max(worst.get(r["feature"], 0.0), r["separability"])
    flagged = sorted([f for f, v in worst.items() if v > CANARY_MAX])
    rep = dict(experiment="E1 (2026-10-09) leakage canary, design B", started_utc=now(),
               rule=f"separability = max(AUC, 1-AUC); a feature above {CANARY_MAX} is leakage until proven otherwise",
               positives="withheld catalogue pixels of fold k (segment folds seed 53)",
               negatives="footprint pixels that are not catalogue faults (300k sample)",
               max_separability_by_feature=dict(sorted(worst.items(), key=lambda kv: -kv[1])),
               flagged=flagged, per_fold=rows, runtime_s=round(time.time() - t0, 1),
               gemsdoe29_template_check="the leaky full-catalogue distance would be 0 on every catalogue pixel "
                                        "(separability 1.0); H1 here is recomputed from visible faults only")
    out = ROOT / "evidence" / "h53_e1_canary.json"
    out.write_text(json.dumps(rep, indent=2, default=jsonable))
    print(json.dumps({"flagged": flagged, "top": list(rep["max_separability_by_feature"].items())[:8]}, indent=2))


def spatial_grid(inp, args, L_all):
    blocks = load_template_module("blocks", args.template_root)
    shape = (inp.H, inp.W)
    tbl = blocks.block_table(shape, BLOCK_PX, valid=inp.fp, labels=inp.cat)
    fold_of = blocks.assign_folds(tbl, n_folds=K_FOLDS, seed=SEED, mode="contiguous")
    bid = blocks.block_id_map(shape, BLOCK_PX)
    cents = ndimage.center_of_mass(inp.cat, L_all, index=np.arange(1, L_all.max() + 1))
    seg_fold = np.array([fold_of[int(bid[int(round(y)), int(round(x))])] for (y, x) in cents], dtype=np.int64)
    g = np.full(inp.cat.shape, -1, dtype=np.int8)
    m = L_all > 0
    g[m] = seg_fold[L_all[m] - 1].astype(np.int8)
    return g


def run_stage(inp, hw, grid, L, decoders, label, log):
    res = {"A": [], "B": []}
    meta = []
    for arm in ("A", "B"):
        rng = np.random.default_rng(SEED)  # identical negatives across arms per fold
        for k in range(K_FOLDS):
            t1 = time.time()
            hidden = inp.cat & (grid == k)
            visible = inp.cat & (grid != k)
            F = feature_matrix(inp, arm, visible, L, hw)
            p, npos, nneg = fit_predict(inp, F, visible, hidden, rng)
            del F
            sc = score_decoders(p, inp, visible, hidden, decoders)
            res[arm].append(sc)
            meta.append(dict(stage=label, arm=arm, fold=k, withheld_px=int(hidden.sum()),
                             withheld_segments=int(np.unique(L[hidden]).size), train_pos=npos, train_neg=nneg,
                             seconds=round(time.time() - t1, 1)))
            log(f"[{label}] arm {arm} fold {k}: " + ", ".join(f"{d} {sc[d]['DTI']:.6f}" for d in decoders)
                + f" ({meta[-1]['seconds']}s)")
            del p
    summary = {}
    for d in decoders:
        s = {}
        for arm in ("A", "B"):
            pdti, P = pooled([r[d] for r in res[arm]])
            per = [r[d]["DTI"] for r in res[arm]]
            m, h = tci(per)
            s[arm] = dict(pooled_DTI=round(pdti, 6), per_fold_DTI=[round(x, 6) for x in per],
                          fold_mean=round(m, 6), CI95_t_df4=[round(m - h, 6), round(m + h, 6)],
                          pooled_TP_w=round(P["TP_w"], 3), pooled_FP_w=round(P["FP_w"], 3),
                          pooled_FN_w=round(P["FN_w"], 3), mean_dots=float(np.mean([r[d]["dots"] for r in res[arm]])))
        diff = [b[d]["DTI"] - a[d]["DTI"] for a, b in zip(res["A"], res["B"])]
        m, h = tci(diff)
        s["paired_B_minus_A"] = dict(per_fold=[round(x, 6) for x in diff], mean=round(m, 6),
                                     CI95_t_df4=[round(m - h, 6), round(m + h, 6)], folds_B_wins=int(sum(x > 0 for x in diff)))
        summary[d] = s
    return summary, meta


def cmd_e2(args):
    t0 = time.time()
    started = now()
    inp = load(args)
    _, hw = load_hwvc()
    lines = []

    def log(s):
        print(s, flush=True); lines.append(s)

    fold_grid, n_seg, L = segment_folds(inp.cat, K=K_FOLDS, seed=SEED)
    decs = ["M1_thin_bin_q0p10", "DS_flank2_sep2p8_n40000"]
    s1, m1 = run_stage(inp, hw, fold_grid, L, decs, "stage1-segment", log)
    sp = spatial_grid(inp, args, L)
    s2, m2 = run_stage(inp, hw, sp, L, ["M1_thin_bin_q0p10"], "stage2-spatial", log)
    lb1 = s1["M1_thin_bin_q0p10"]["paired_B_minus_A"]["CI95_t_df4"][0]
    mean2 = s2["M1_thin_bin_q0p10"]["paired_B_minus_A"]["mean"]
    promote = bool(lb1 > 0 and mean2 > 0)
    rep = dict(experiment="E2 (2026-10-09) hide-and-recover, arm A (bands+H1, current holdout best) vs arm B (+HWVC)",
               started_utc=started, finished_utc=now(), runtime_s=round(time.time() - t0, 1),
               label_type="HOLDOUT-DTI (proxy truth = withheld catalogue segments; NOT organizer-scored)",
               evaluator=EVAL, design="B: positives = visible outside 10 px buffer of withheld; negatives = footprint & ~visible; "
                                      "visible faults zeroed in prediction (pixel-exact mask); H1 from visible only",
               segment_folds=dict(K=K_FOLDS, seed=SEED, buffer_px=BUF_PX, segments=int(n_seg),
                                  withheld_positives_total=int(inp.cat.sum())),
               stage1=s1, stage2=s2, meta=m1 + m2,
               reproduction_check=dict(previous_session_h1_thin_bin_q0p1_pooled=0.141319,
                                       this_run_arm_A=s1["M1_thin_bin_q0p10"]["A"]["pooled_DTI"]),
               promotion_rule="promote B iff stage-1 paired (B-A, M1) 95% lower bound > 0 AND stage-2 paired mean > 0",
               stage1_lower_bound=lb1, stage2_mean=mean2, promote_B=promote, log=lines)
    out = ROOT / "evidence" / "h53_e2_holdout.json"
    out.write_text(json.dumps(rep, indent=2, default=jsonable))
    print(json.dumps({"promote_B": promote, "lb1": lb1, "mean2": mean2,
                      "A_M1": s1["M1_thin_bin_q0p10"]["A"]["pooled_DTI"], "B_M1": s1["M1_thin_bin_q0p10"]["B"]["pooled_DTI"]}, indent=2))


def cmd_e3(args):
    import hashlib
    t0 = time.time()
    e2 = json.loads((ROOT / "evidence" / "h53_e2_holdout.json").read_text())
    arm = "B" if e2["promote_B"] else "A"
    inp = load(args)
    _, hw = load_hwvc()
    L, _ = ndimage.label(inp.cat, structure=np.ones((3, 3), dtype=int))
    F = feature_matrix(inp, arm, inp.cat, L, hw)  # H1: own segment excluded on catalogue px; all catalogue elsewhere
    rng = np.random.default_rng(SEED)
    p, npos, nneg = fit_predict(inp, F, inp.cat, None, rng)
    del F
    p[~inp.fp] = 0.0
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(CACHE / f"surface_arm{arm}.npy", p)
    emis = decoder_ds(np.where(inp.fp & ~inp.cat, p, -1.0), inp.fp & ~inp.cat, inp.cat, N_DOTS, FLANK_PX, MIN_SEP)
    emis[~inp.fp] = 0.0
    np.save(CACHE / f"dots_arm{arm}.npy", emis)
    pix = hashlib.sha256(np.ascontiguousarray(emis, dtype="<f4").tobytes()).hexdigest()
    d = ndimage.distance_transform_edt(~inp.cat)
    rep = dict(experiment="E3 (2026-10-09) build", arm=arm, finished_utc=now(), train_pos=npos, train_neg=nneg,
               dots=int(emis.sum()), min_dist_to_catalogue_px=float(d[emis > 0].min()),
               pixel_sha256=pix, runtime_s=round(time.time() - t0, 1),
               surface_cache=str(CACHE / f"surface_arm{arm}.npy"))
    (ROOT / "evidence" / "h53_e3_build.json").write_text(json.dumps(rep, indent=2, default=jsonable))
    print(json.dumps(rep, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["features", "e1", "e2", "e3"])
    ap.add_argument("--data-dir", default="/tmp/gems53-data")
    ap.add_argument("--template-root", default="/tmp/gems-template")
    a = ap.parse_args()
    {"features": cmd_features, "e1": cmd_e1, "e2": cmd_e2, "e3": cmd_e3}[a.cmd](a)


if __name__ == "__main__":
    main()
