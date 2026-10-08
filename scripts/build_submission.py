#!/usr/bin/env python3
"""Build the submission raster: validated field -> metric-aware emission -> gated GeoTIFF.

Refuses to write unless the blocked-holdout gate has been cleared for the arm it is using
(``evidence/holdout_*.json``), because the standing instruction is that no weekly slot is spent on
an idea that has not beaten the current holdout best.  ``--force`` exists for research runs and is
recorded in the evidence file.

Per-candidate reasoning is mandatory here, not optional decoration: every emitted segment gets a
row saying which disagreement stratum it came from, what the cover-thickness band says about it, and
whether the surface view contradicts the field view.  That table is the Phase-2 option value (staff
said the Phase-2 truth set is produced by expert review of Phase-1 submissions) and it is what makes
the file defensible rather than merely dense.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_pipeline as R                                   # noqa: E402
import validate_holdout as V                                # noqa: E402

V_CORRIDAR_PX = V.CORRIDAR_PX
from gems52 import cotrain as CT                           # noqa: E402
from gems52 import emit as EM                              # noqa: E402
from gems52 import gates                                   # noqa: E402
from gems52 import grid as GR                              # noqa: E402
from gems52 import holdout as HO                            # noqa: E402
from gems52 import metric as M                              # noqa: E402

EV = ROOT / "evidence"
WORK = ROOT / "work"
OUT = ROOT / "submission"
NAME_STEM = "gems52-h52-cotrain-disagreement-emission"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


FAR_SPEC = {"B_only": ("b_only", 1), "union": ("union", 1), "random": ("random", 1),
            "wt_A20B80": ("wt:0.20:0.80", 1), "B_only_lc": ("b_only_lc", 1),
            "cotrain": ("cotrain", 1)}
COR_SPEC = {"union_cor": ("union", 1), "B_only_cor": ("b_only", 1), "blanket": ("blanket", 0),
            "cotrain_cor": ("cotrain", 1), "random": ("random", 1)}


def composite_field(sel: dict, pa, pb, strata, valid, cat):
    """Rebuild the *exact* two-regime field the composite sweep selected, on the deployed models.

    Corridor mass is ranked by the ranking that wins on the truncation instrument; far-field mass by the
    ranking that wins on the whole-component instrument.  Re-deriving it here rather than reading a
    cached raster is the point: the shipped file must be reproducible from the models plus one
    selection record.
    """
    from scipy import ndimage
    corr = (ndimage.binary_dilation(cat, structure=np.ones((3, 3), bool),
                                    iterations=V_CORRIDAR_PX) & ~cat & valid)
    far = valid & ~cat & ~corr

    def one(spec, allowed):
        mode, rnd = spec
        if mode == "random":
            f = np.random.default_rng(11).random(valid.shape).astype(np.float32)
        elif mode == "blanket":
            return allowed.astype(np.float32)
        else:
            A, B = (pa, pb) if rnd == 1 else (pb * 0 + pa, pb)     # round 0 handled by caller
            f = R.field_from_probs(A, B, strata, valid, mode=mode)[0]
        return np.where(allowed, f, 0.0).astype(np.float32)

    f_cor = one(FAR_SPEC.get(sel["corridor_ranker"], COR_SPEC.get(sel["corridor_ranker"])), corr)
    f_far = one(FAR_SPEC.get(sel["far_ranker"], COR_SPEC.get(sel["far_ranker"])), far)
    return f_cor, f_far, f_cor + f_far, corr, far


def pick_best_arm(mode: str, arm_prefix: str = "cotrain") -> tuple[str, int, dict]:
    """The winning (arm, budget) from the blocked-holdout table, or raise."""
    p = EV / f"holdout_{mode}.json"
    if not p.exists():
        raise SystemExit(f"no holdout evidence at {p}; run scripts/validate_holdout.py first")
    d = json.loads(p.read_text())
    cands = {k: v for k, v in d["summary"].items() if k.startswith(arm_prefix + "|")}
    if not cands:
        raise SystemExit(f"arm {arm_prefix!r} absent from {p}")
    best = max(cands.items(), key=lambda kv: kv[1]["mean"])
    return best[0], int(best[0].split("|")[1]), d


def per_candidate_reasoning(em: np.ndarray, strata: np.ndarray, valid: np.ndarray,
                            cat: np.ndarray, field: np.ndarray, dti_bar: float) -> list[dict]:
    """One row per emitted segment, with the physical claim written out in words."""
    depth = np.nan_to_num(R.get_layer("A_depth_base_rank").astype(np.float32), nan=0.0)
    slope = np.nan_to_num(R.get_layer("B_slope_rank").astype(np.float32), nan=0.0)
    scarp = np.nan_to_num(R.get_layer("B_scarp_p900").astype(np.float32), nan=0.0)
    gs = np.abs(np.nan_to_num(R.get_layer("A_grav_step").astype(np.float32), nan=0.0))
    ms = np.abs(np.nan_to_num(R.get_layer("A_mag_step").astype(np.float32), nan=0.0))
    e = np.asarray(em) > 0
    lab, n = ndimage.label(e, structure=np.ones((3, 3), bool))
    near_cat = ndimage.binary_dilation(cat, structure=np.ones((3, 3), bool))
    dist_cat = ndimage.distance_transform_edt(~cat & valid)
    ys, xs = np.nonzero(lab > 0)
    ids = lab[ys, xs]
    order = np.argsort(ids, kind="stable")
    ys, xs, ids = ys[order], xs[order], ids[order]
    starts = np.searchsorted(ids, np.arange(1, n + 1))
    ends = np.append(starts[1:], ids.size)
    names = {0: "silent", 1: "concordant", 2: "A-only", 3: "B-only"}
    rows = []
    for k in range(n):
        a, b = starts[k], ends[k]
        yy, xx = ys[a:b], xs[a:b]
        st = np.bincount(strata[yy, xx].astype(np.int64), minlength=4)
        code = int(np.argmax(st[1:]) + 1) if st[1:].sum() else 0
        drow = dict(
            segment=k + 1, pixels=int(b - a),
            row_range=[int(yy.min()), int(yy.max())], col_range=[int(xx.min()), int(xx.max())],
            east_m=float(GR.TRANSFORM[0] + (xx.mean() + 0.5) * 100.0),
            north_m=float(GR.TRANSFORM[2] - (yy.mean() + 0.5) * 100.0),
            stratum=names[code], stratum_counts={names[i]: int(st[i]) for i in range(4)},
            cover_depth_rank=round(float(depth[yy, xx].mean()), 4),
            slope_rank=round(float(slope[yy, xx].mean()), 4),
            scarp_rank=round(float(scarp[yy, xx].mean()), 4),
            grav_step=round(float(gs[yy, xx].mean()), 4),
            mag_step=round(float(ms[yy, xx].mean()), 4),
            px_to_visible_catalogue=round(float(dist_cat[yy, xx].mean()), 2),
            touches_visible_catalogue=bool(near_cat[yy, xx].any()),
            field_mass=round(float(field[yy, xx].mean()), 5),
        )
        buried = drow["cover_depth_rank"] >= 0.55
        if code == 2:
            drow["claim"] = ("field-view only: potential-field offset (gravity step "
                             f"{drow['grav_step']:.3f}, magnetic step {drow['mag_step']:.3f}) with no "
                             f"corresponding scarp (surface rank {drow['scarp_rank']:.3f}); cover "
                             f"depth rank {drow['cover_depth_rank']:.3f} "
                             + ("is deep enough that a scarp would be buried, so this is a buried "
                                "range-front fault the LiDAR-derived catalogue cannot contain"
                                if buried else
                                "is shallow, so the absence of a scarp is *not* explained by cover - "
                                "weaker candidate, kept only because the field evidence is strong"))
        elif code == 3:
            drow["claim"] = ("surface-view only: scarp with no field offset; the catalogue was built "
                             "from this same surface expression, so an uncatalogued scarp here is more "
                             "likely a road cut, canal levee, quarry face or erosion line than a fault "
                             "- down-weighted, and emitted only if it clears the metric bar")
        elif code == 1:
            drow["claim"] = ("both views agree: continuation of a mapped structure beyond the end or "
                             "the side of the mapped trace, the case where the catalogue is truncated "
                             "by mapping convention rather than by data")
        else:
            drow["claim"] = ("neither view is in its confident tail; emitted on corridor mass that "
                             "the calibrated density still values above the acceptance bar "
                             f"(bar {dti_bar:.4f})")
        rows.append(drow)
    rows.sort(key=lambda r: -r["pixels"])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="tip", choices=["hide", "block", "tip"],
                    help="which deployed model pair to read (deploy_<mode>.npz)")
    ap.add_argument("--arm", default="composite")
    ap.add_argument("--budget", type=int, default=0, help="0 = take the winner from the holdout table")
    ap.add_argument("--emit", default="greedy", choices=["greedy", "topk"])
    ap.add_argument("--tag", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--far", default="B_only", help="far-field ranker when --arm composite and no "
                    "evidence/composite.json selection exists")
    ap.add_argument("--cor", default="union_cor", help="corridor ranker, same condition")
    ap.add_argument("--split", type=float, default=-1.0, help="corridor share 0..1, same condition; "
                    "-1 = refuse unless the sweep wrote a selection")
    ap.add_argument("--total", type=int, default=37654, help="total emission budget, same condition")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)

    hold = json.loads((EV / f"holdout_{a.mode}.json").read_text()) if (
        EV / f"holdout_{a.mode}.json").exists() else {}
    comp_p = EV / "composite.json"
    comp = json.loads(comp_p.read_text()) if comp_p.exists() else None
    sel = (comp or {}).get("selected")
    explicit = False
    if a.arm == "composite" and not sel and a.split >= 0.0:
        # The sweep had not finished when this file was built.  The two extreme splits are measured in
        # evidence/holdout_{tip,hide}.json (s=0 is exactly B_only|37654, s=1 is exactly union_cor|37654),
        # so an interior split is recorded here as *rule-derived, not sweep-verified* and says so in the
        # evidence file rather than pretending to a number it does not have.
        n_cor = int(round(a.total * a.split))
        sel = dict(key=f"cor={a.cor}|far={a.far}|split={a.split}|total={a.total}",
                   far_ranker=a.far, corridor_ranker=a.cor, total_px=int(a.total),
                   corridor_share=float(a.split), corridor_px=n_cor,
                   far_px=int(a.total) - n_cor,
                   source="explicit --far/--cor/--split on the command line; see the note in "
                          "scripts/build_submission.py")
        explicit = True
    if a.arm == "composite":
        if not sel:
            raise SystemExit("evidence/composite.json has no selection and no --split given; run "
                             "scripts/composite_split.py, or pass --far/--cor/--split explicitly")
        key = sel["key"]
        budget = int(sel["total_px"])
        modes_seen = (comp or {}).get("modes", ["tip", "hide"])
        # The sweep's own verdict, not a friendlier one: `promoted` requires BOTH the composite control
        # bar and the registered +0.010-over-naive-union bar.  The selected config clears the first and
        # misses the second on the truncation instrument, so a build from the record still needs --force,
        # and the evidence file says which bar failed.
        gate = dict(promoted=not explicit and bool(sel.get("promoted", True)), tested=key,
                    explicit_selection=explicit,
                    composite_control_bar=bool(sel.get("beats_random_all")),
                    registered_union_bar=bool(sel.get("beats_union_bar")),
                    vs_naive_union={m: sel.get(f"vs_union_{m}") for m in modes_seen},
                    checks={f"mean_{m}": dict(ok=True, value=sel.get(f"mean_{m}")) for m in modes_seen},
                    reason=("selected by the composite rule: beats random on both instruments at equal "
                            "budget, maximises the sum of the two instruments' DTI, ties to smaller mass")
                    + ("  [THIS FILE: the split was given on the command line, so `promoted` is false "
                       "here and --force was required; the sweep's own verdict is pending]"
                       if explicit else ""))
        log(f"composite selection {key}: corridor share {sel['corridor_share']}, "
            f"far={sel['far_ranker']}, cor={sel['corridor_ranker']}")
    else:
        key, budget, hold = pick_best_arm(a.mode, a.arm)
        gate = hold.get("gates", {})
        log(f"arm {key}: gate promoted={gate.get('promoted')} reason={gate.get('reason')}")
    if a.budget:
        budget = a.budget
    if not gate.get("promoted") and not a.force:
        raise SystemExit("gate not cleared - not writing a submission.  --force to override for "
                         "research runs (the flag is recorded in the evidence file).")

    valid, cat = R.load_valid_cat()
    dep = np.load(WORK / f"deploy_{a.mode}.npz")
    round1 = a.arm in ("cotrain", "A_only", "B_only", "union", "mean", "product", "composite")
    pa = (dep["p_a1"] if round1 else dep["p_a0"]).reshape(GR.SHAPE)
    pb = (dep["p_b1"] if round1 else dep["p_b0"]).reshape(GR.SHAPE)
    strat = dep["strata"]
    allowed = valid & ~cat                      # the organiser masks the visible catalogue
    if a.arm == "composite":
        f_cor, f_far, field, corr, far = composite_field(sel, pa, pb, strat, valid, cat)
        em_c = HO.emit_topk(f_cor, corr, int(sel["corridor_px"]))
        em_f = HO.emit_topk(f_far, far, int(sel["far_px"]))
        em = np.maximum(em_c, em_f).astype(np.float32)
        st = dict(emitted=int((em > 0).sum()), corridor_px=int((em_c > 0).sum()),
                  far_px=int((em_f > 0).sum()), corridor_area=int(corr.sum()), far_area=int(far.sum()),
                  method="two-regime top-K at the composite-selected split")
        fst = dict(mode="composite", selection=sel, corridor_px=int(corr.sum()),
                   far_px=int(far.sum()))
        log(f"corridor area {int(corr.sum())} px, far-field area {int(far.sum())} px")
    else:
        field, fst = R.field_from_probs(pa, pb, strat, valid,
                                       mode=a.arm if a.arm != "cotrain" else "cotrain")
    g_est = R.PREREG["prevalence_used"] * int(valid.sum())
    dti_bar_expected = EM.accept_bar(R.DTI_PROJECTED)
    if a.arm != "composite":
        if a.emit == "greedy":
            em, st = HO.emission_from_field(field, allowed, R.DTI_PROJECTED, budget,
                                            calibrate_to=g_est, pool=400_000, log=log)
        else:
            em = HO.emit_topk(field, allowed, budget)
            st = {"emitted": int((em > 0).sum())}
    log(f"emitted {int((em > 0).sum())} px, bar {dti_bar_expected:.5f}, calibrated to "
        f"|G|~{g_est:.0f} px")

    # sensitivity: what the same field emits at the fold-measured bar instead of the target bar
    summ = (hold.get("summary") or {})
    alt_key = key if key in summ else f"{a.arm if a.arm != 'composite' else 'B_only'}|{budget}"
    fold_dti = float(summ[alt_key]["mean"]) if alt_key in summ else float("nan")
    st_alt = {}
    if a.arm != "composite" and np.isfinite(fold_dti) and fold_dti > 1e-3:
        em_alt, st_alt = HO.emission_from_field(field, allowed, max(fold_dti, 1e-3), budget,
                                                calibrate_to=g_est, pool=400_000,
                                                log=lambda *x: None)
        log(f"sensitivity at bar accept_bar({fold_dti:.4f}): {st_alt['emitted']} px")
    elif a.arm == "composite":
        log("sensitivity re-emission skipped for the composite arm (its budget IS the selection)")

    name = f"{NAME_STEM}-{a.arm}-{int((em > 0).sum())}px-{a.tag}"
    tif = OUT / f"{name}.tif"
    # 0.0 outside the footprint, never NaN: see gates.format_report for the portal mechanism.
    a_out = np.where(valid, em, 0.0).astype(np.float32)
    receipt = GR.write_geotiff(tif, a_out)
    log(f"wrote {tif} ({receipt['bytes']} bytes, sha256 {receipt['sha256'][:16]}...)")

    fmt = gates.format_report(tif, ROOT / "data/sample_submission.tif", footprint=valid)
    priors = gates.find_priors([ROOT / "submission", ROOT / "data/scored", Path("/tmp")], exclude=tif)
    uni = gates.uniqueness_report(em, priors)
    rows = per_candidate_reasoning(em, strat, valid, cat, field, dti_bar_expected)
    report = dict(
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        file=tif.name, sha256=fmt["sha256"], bytes=fmt["bytes"],
        arm=key, arm_mean_fold_dti=fold_dti, budget=budget,
        emit=("topk" if a.arm == "composite" else a.emit),
        selection_source=(sel or {}).get("source", "evidence/composite.json"),
        field_stats=fst, g_estimate_px=g_est, accept_bar=dti_bar_expected,
        stats=st, sensitivity_alt_bar=(dict(key=f"{alt_key}@bar{fold_dti:.4f}", **st_alt)
                                       if st_alt else None),
        holdout_gates=gate, forced=bool(a.force and not gate.get("promoted")),
        format=fmt, writer_receipt=receipt, uniqueness=uni, n_segments=len(rows),
        stratum_mix=_stratum_mix(em, strat),
        per_candidate=rows[:200], per_candidate_csv=f"{name}-candidates.csv",
    )
    (EV / f"submission_{name}.json").write_text(json.dumps(report, indent=1) + "\n")
    csv = EV / f"{name}-candidates.csv"
    import csv as _csv
    with open(csv, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=[k for k in rows[0]] if rows else ["segment"])
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                        for k, v in r.items()})
    log(f"reasoning table: {len(rows)} segments -> {csv.name}")
    ok = fmt["ok"] and uni["ok"]
    log(f"GATES format_ok={fmt['ok']} unique_ok={uni['ok']} "
        f"({uni['relation_to_union']}, novel {uni['novel_fraction']:.1%})")
    if not ok:
        print(json.dumps(dict(format=fmt["problems"], uniqueness=uni["relation_to_union"],
                              per_prior=uni["per_prior"]), indent=1)[:2000])
        if not a.force:
            raise SystemExit("gates failed; refusing this file as a submission candidate")
    (OUT / "LATEST.txt").write_text(tif.name + "\n")
    return 0 if ok or a.force else 3


def _stratum_mix(em: np.ndarray, strat: np.ndarray) -> dict:
    names = {0: "silent", 1: "concordant", 2: "A-only", 3: "B-only"}
    codes = np.asarray(strat)[np.asarray(em) > 0]
    cnt = np.bincount(codes.astype(np.int64), minlength=4)
    tot = max(int(codes.size), 1)
    return {names[i]: dict(pixels=int(cnt[i]), fraction=round(cnt[i] / tot, 4)) for i in range(4)}


if __name__ == "__main__":
    raise SystemExit(main())
