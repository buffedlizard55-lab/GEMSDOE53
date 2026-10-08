#!/usr/bin/env python3
"""Budget × arm × instrument sweep, and a robustness rule for picking one configuration.

The tip instrument (hold out the ends of traces, leave the bodies visible) is the optimistic one: 88.5 %
of its held truth sits within 5 px of a trace the model can still see. The hide instrument (hold out
whole components) is the pessimistic one: 0.5 %. A budget that is optimal on the optimistic instrument
can over-emit on the real test set, and a budget optimal on the pessimistic one under-emits. So the
selection rule is **maximise the minimum of the two**, not the mean — we ship the configuration that is
not the worst on either instrument, and we report both numbers on the site rather than the flattering
one.

Both instruments are prevalence-matched to the mid-bracket |G| (0.2 % of the footprint = 10.3k px),
which is what makes the budgets comparable between them at all.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_pipeline as R                                   # noqa: E402
import validate_holdout as V                              # noqa: E402
from gems52 import cotrain as CT                          # noqa: E402
from gems52 import holdout as HO                          # noqa: E402

EV = ROOT / "evidence"
PRED = ROOT / "work/fold_preds"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def fields_for_fold(f, valid, cat, a0, b0, a1, b1, arms, rng):
    st = {0: CT.strata(a0.ravel(), b0.ravel(), f["region"] & valid, q_conf=0.98,
                       q_abstain_hi=R.PREREG["abstain_q"])["mask"],
          1: CT.strata(a1.ravel(), b1.ravel(), f["region"] & valid, q_conf=0.98,
                       q_abstain_hi=R.PREREG["abstain_q"])["mask"]}
    corr = V.corridor_of(f, valid)
    prefs = {}
    for arm in arms:
        key = arm[:-4] if arm.endswith("_cor") else arm
        mode, rnd = V.ARMS[key]
        pa, pb = (a0, b0) if rnd == 0 else (a1, b1)
        in_cor = arm.endswith("_cor")
        name = arm[:-4] if in_cor else arm
        if name == "corridor_blanket":
            prefs[arm] = corr.astype(np.float32)
            continue
        fld = (rng.random(valid.shape).astype(np.float32) if mode == "random"
               else R.field_from_probs(pa, pb, st[rnd], valid, mode=mode)[0])
        prefs[arm] = fld * corr if in_cor else fld
    return prefs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="tip,hide")
    ap.add_argument("--arms", default="union_cor,B_only,cotrain_cor,corridor_blanket,random,cotrain")
    ap.add_argument("--budgets", default="8000,20000,37654,60000,90000,140000,200000,300000")
    ap.add_argument("--emit", default="topk")
    ap.add_argument("--n-folds", type=int, default=4)
    a = ap.parse_args()
    budgets = [int(x) for x in a.budgets.split(",")]
    arms = a.arms.split(",")
    out = {}
    valid, cat = R.load_valid_cat()
    siblings = {nm: V.load_sibling(nm) for nm in V.SIBLINGS}
    siblings = {k: v for k, v in siblings.items() if v is not None}
    log(f"{len(siblings)} prior rasters as reference arms: {list(siblings)}")
    for mode in a.modes.split(","):
        folds = HO.make_folds(cat, valid, n_folds=a.n_folds, buffer_px=4,
                              prevalence=R.PREREG["prevalence_used"], seed=0, mode=mode)
        acc: dict[str, list[float]] = {}
        for f in folds:
            pf = PRED / f"{mode}_fold{f['fold']}.npz"
            if not pf.exists():
                log(f"  {mode} fold {f['fold']}: missing {pf}")
                return 2
            with np.load(pf) as z:
                def grid(k):
                    g = z[k].astype(np.float32) / 65535.0
                    return g if g.ndim == 2 else g.reshape(valid.shape)
                a0, b0, a1, b1 = grid("a0"), grid("b0"), grid("a1"), grid("b1")
            rng = np.random.default_rng(1000 + f["fold"])
            prefs = fields_for_fold(f, valid, cat, a0, b0, a1, b1, arms, rng)
            for nm, fld in siblings.items():
                prefs[f"sibling:{nm}"] = fld
            sc = HO.arm_scores(prefs, f, valid, budgets=budgets, emit=a.emit,
                               as_is=tuple(k for k in prefs if k.startswith("sibling:")))
            for k, v in sc.items():
                acc.setdefault(k, []).append(v["dti"])
            log(f"  {mode} fold {f['fold']}: best {max(sc.items(), key=lambda kv: kv[1]['dti'])[0]}"
                f" = {max(v['dti'] for v in sc.values()):.4f}")
        out[mode] = {k: dict(mean=round(float(np.mean(v)), 5), sd=round(float(np.std(v)), 5),
                             per_fold=[round(x, 5) for x in v]) for k, v in acc.items()}

    keys = set.intersection(*[set(out[m]) for m in out]) if out else set()
    keys = {k for k in keys if not k.endswith("|full")}     # reference arms have no budget
    combined = {}
    for k in keys:
        means = {m: out[m][k]["mean"] for m in out}
        combined[k] = dict(**means, worst=min(means.values()), mean_all=round(float(np.mean(list(means.values()))), 5))
    rank = sorted(combined.items(), key=lambda kv: -kv[1]["worst"])
    if rank:
        best = rank[0][0]
        arm, budget = best.rsplit("|", 1)
        combined["__selection__"] = dict(
            rule="maximise min(tip, hide) — the configuration must not be the worst on either instrument",
            key=best, arm=arm, budget=int(budget),
            tip=out["tip"][best]["mean"] if "tip" in out else None,
            hide=out["hide"][best]["mean"] if "hide" in out else None,
            random_worst=min(out[m][f"random|{budget}"]["mean"] for m in out if f"random|{budget}" in out[m])
            if any(f"random|{budget}" in out[m] for m in out) else None)
    (EV / "budget_sweep.json").write_text(json.dumps(
        dict(generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), emit=a.emit,
             budgets=budgets, arms=arms, by_mode=out, combined=combined), indent=1) + "\n")
    log("ranking by worst-instrument mean:")
    for k, v in rank[:12]:
        log(f"  {k:30s} " + "  ".join(f"{m}={v[m]:.4f}" for m in out) + f"  worst={v['worst']:.4f}")
    if "__selection__" in combined:
        log("selected: " + json.dumps(combined["__selection__"]))
    sib = {m: {k: v["mean"] for k, v in out[m].items() if k.startswith("sibling")} for m in out}
    log("prior rasters on the same folds: " + json.dumps(sib))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
