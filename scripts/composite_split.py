#!/usr/bin/env python3
"""Composite emission: corridor mass ranked one way, far-field mass ranked another, judged on both
instruments at once.

Why this script exists.  The two validation instruments measure two different populations, and each is
structurally blind to the other's mechanism:

* the ``tip`` instrument (hide the along-strike ends of traces, leave the bodies visible) puts 88.5 % of
  its held truth within 5 px of a still-visible trace, so it is the only fold set that can score corridor
  mass at all;
* the ``hide`` instrument (hide whole components) puts 0.5 % of its truth there, and corridor-restricted
  arms score ~0.0001 on it — not because corridors are worthless on the real test set, but because that
  instrument cannot see them.

"P pick the arm that maximises one instrument" is therefore wrong in both directions, and the naive fix
— take the max-min — throws the corridor away. The right object is a *two-regime* emitter: mass inside
the near-trace corridor ranked by whatever wins on ``tip``, mass outside ranked by whatever wins on
``hide``, with the split between the two a measured parameter rather than a taste.

Selection rules, all three applied and reported:
  1. the configuration must beat uniform-random emission at the same total budget on **both** instruments;
  2. among those, maximise the sum of the two instruments' mean DTI — both are prevalence-matched to the
     same inferred |G| bracket, which is what makes adding them meaningful at all;
  3. ties break toward the **smaller** total mass, because DTI's false-positive term is linear in emitted
     mass and every unproven pixel is a liability on a test set we cannot see.
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

# regime rankings: name -> (field mode, co-training round, corridor-restricted?)
FAR = {"B_only": ("b_only", 1, False), "union": ("union", 1, False),
       "B_only_lc": ("b_only_lc", 1, False), "wt_A20B80": ("wt:0.20:0.80", 1, False),
       "cotrain": ("cotrain", 1, False), "random": ("random", 1, False)}
COR = {"union_cor": ("union", 1, True), "B_only_cor": ("b_only", 1, True),
       "cotrain_cor": ("cotrain", 1, True), "blanket": ("blanket", 0, True),
       "random": ("random", 1, True)}


def log(m: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def build_field(spec, a0, b0, a1, b1, strata, corr, valid, seed) -> np.ndarray:
    """One arm's field, optionally confined to the corridor by multiplication."""
    mode, rnd, in_corridor = spec
    if mode == "random":
        f = np.random.default_rng(seed).random(valid.shape).astype(np.float32)
    elif mode == "blanket":          # the corridor alone: no detector, uniform inside it
        return corr.astype(np.float32)
    else:
        pa, pb = (a0, b0) if rnd == 0 else (a1, b1)
        f = R.field_from_probs(pa, pb, strata, valid, mode=mode)[0]
    return f * corr if in_corridor else f


def aggregate(res: dict, modes: list[str]):
    """Fold means -> the ranked table, under the selection rule in `selection_rules`.

    Kept separate from scoring so that a *rule* change can be re-applied to an existing sweep
    without re-running a single fold (see scripts/composite_recount.py).  That is not a
    convenience: the first version of the control here was `max` over every random variant, which
    handed the corridor arm's own score to the bar it had to beat.
    """
    common = set.intersection(*[set(res[m]) for m in modes])
    table: dict[str, dict] = {}
    for k in sorted(common):
        means = {m: float(np.mean(res[m][k])) for m in modes}
        # The control has to be random *in the same regime and at the same split*, otherwise the bar is
        # not "better than chance" but "better than the best of every random variant", which silently
        # promotes the strongest arm in the sweep to being the control.  The first version of this script
        # used max(...) and failed exactly that way - it handed the tip control to the corridor arm it was
        # supposed to be tested against.  C_far isolates the far-field ranking; C_all, when it exists,
        # also isolates the corridor choice.
        rand, rand_all = {}, {}
        head, tot_s, sp_s = k.split("|")[0], k.split("|")[1], k.split("|")[2]
        for m in modes:
            cor = head.split("+")[1]
            c_far = f"random+{cor}|{tot_s}|{sp_s}"
            cand = [float(np.mean(res[m][j])) for j in res[m] if j == c_far]
            if not cand:                              # no random far-field run at this split: fall back
                cand = [float(np.mean(res[m][j])) for j in res[m]
                        if j.split("|")[0].startswith("random+") and j.split("|")[2] == sp_s]
            rand[m] = max(cand) if cand else 0.0
            c_all = f"random+random|{tot_s}|{sp_s}"
            rand_all[m] = float(np.mean(res[m][c_all])) if c_all in res[m] else None
        table[k] = dict({f"mean_{m}": round(means[m], 5) for m in modes},
                        sum=round(float(sum(means.values())), 5),
                        worst=round(float(min(means.values())), 5),
                        rand={m: round(rand[m], 5) for m in modes},
                        rand_all={m: (round(rand_all[m], 5) if rand_all[m] is not None else None)
                                  for m in modes},
                        beats_random_all=bool(all(means[m] >= rand[m] - 1e-9 for m in modes)))
    # The pre-registration also requires +0.010 over the naive union on every instrument.  Report it; do
    # not silently substitute the composite bar for the registered one.
    for k, v in table.items():
        for m in modes:
            u = f"union+{k.split('|')[0].split('+')[1]}|{k.split('|')[1]}|{k.split('|')[2]}"
            v[f"vs_union_{m}"] = round(v[f"mean_{m}"] - float(np.mean(res[m].get(u, [0.0]))), 5) \
                if u in res[m] else None
        pr = [x for x in modes if v.get(f"vs_union_{x}") is not None]
        v["beats_union_bar"] = bool(pr and all(v[f"vs_union_{x}"] >= 0.010 for x in pr))
        v["promoted"] = bool(v["beats_random_all"] and v["beats_union_bar"])
    ok = {k: v for k, v in table.items() if v["beats_random_all"]}
    ranked = sorted((ok or table).items(), key=lambda kv: (-kv[1]["sum"], int(kv[0].split("|")[1])))
    sel = ranked[0] if ranked else (None, None)
    if sel[0]:
        fn, cn = sel[0].split("|")[0].split("+")
        tot, sp = sel[0].split("|")[1], sel[0].split("|")[2][1:]
        sel_payload = dict(key=sel[0], far_ranker=fn, corridor_ranker=cn, total_px=int(tot),
                           corridor_share=float(sp), corridor_px=int(round(float(sp) * int(tot))),
                           far_px=int(tot) - int(round(float(sp) * int(tot))), **sel[1])
    else:
        sel_payload = None
    return table, ranked, sel_payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="tip,hide")
    ap.add_argument("--total", default="25000,37654")
    ap.add_argument("--splits", default="0.0,0.25,0.5,0.75,1.0")
    ap.add_argument("--n-folds", type=int, default=4)
    ap.add_argument("--far", default="")
    ap.add_argument("--cor", default="")
    a = ap.parse_args()
    modes = a.modes.split(",")
    totals = [int(x) for x in a.total.split(",")]
    splits = [float(x) for x in a.splits.split(",")]
    far = {k: v for k, v in FAR.items() if not a.far or k in a.far.split(",")}
    cor = {k: v for k, v in COR.items() if not a.cor or k in a.cor.split(",")}
    valid, cat = R.load_valid_cat()

    res: dict[str, dict[str, list[float]]] = {}
    if not a.recount:
        for mode in modes:
            folds = HO.make_folds(cat, valid, n_folds=a.n_folds, buffer_px=4,
                              prevalence=R.PREREG["prevalence_used"], seed=0, mode=mode)
        acc: dict[str, list[float]] = {}
        for f in folds:
            pf = PRED / f"{mode}_fold{f['fold']}.npz"
            if not pf.exists():
                log(f"missing {pf}; run: python3 scripts/run_pipeline.py --stage fit --mode {mode}")
                return 2
            with np.load(pf) as z:
                def grid(key, _z=z):
                    g = _z[key].astype(np.float32) / 65535.0
                    return g if g.ndim == 2 else g.reshape(valid.shape)
                a0, b0, a1, b1 = grid("a0"), grid("b0"), grid("a1"), grid("b1")
            strata = CT.strata(a1.ravel(), b1.ravel(), f["region"] & valid, q_conf=0.98,
                               q_abstain_hi=R.PREREG["abstain_q"])["mask"]
            corr = V.corridor_of(f, valid)
            allowed = valid & ~f["visible"] & f["region"]
            fields = {}
            for nm, spec in {**{f"far:{k}": v for k, v in far.items()},
                             **{f"cor:{k}": v for k, v in cor.items()}}.items():
                fields[nm] = build_field(spec, a0, b0, a1, b1, strata, corr, valid,
                                         7 + f["fold"] + len(nm))
            for tot in totals:
                for sp in splits:
                    k_cor = int(round(sp * tot))
                    k_far = tot - k_cor
                    for cn in cor:
                        for fn in far:
                            em_c = HO.emit_topk(fields[f"cor:{cn}"], allowed, k_cor) if k_cor else None
                            em_f = HO.emit_topk(fields[f"far:{fn}"], allowed, k_far) if k_far else None
                            if em_c is not None and em_f is not None:
                                em = np.maximum(em_c, em_f)
                            else:
                                em = np.asarray(em_c if em_f is None else em_f, dtype=np.float32)
                            sc = HO.score(em, f, valid, extra=False)
                            acc.setdefault(f"{fn}+{cn}|{tot}|s{sp:g}", []).append(sc["dti"])
            log(f"  {mode} fold {f['fold']}: {len(acc)} configs, running best "
                f"{max((float(np.mean(v)) for v in acc.values()), default=0.0):.4f}")
        res[mode] = {k: [round(x, 5) for x in v] for k, v in acc.items()}

    table, ranked, sel_payload = aggregate(res, modes)
    out = dict(generated=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), modes=modes,
               totals=totals, splits=splits, far=list(far), corridor=list(cor),
               n_folds=a.n_folds, prevalence=R.PREREG["prevalence_used"],
               selection_rules=["beat random on both instruments",
                                "maximise the sum of the two instruments' mean DTI",
                                "tie-break toward smaller total mass"],
               per_fold={m: res[m] for m in modes}, table=table,
               ranked=[[k, v] for k, v in ranked[:40]], selected=sel_payload)
    EV.mkdir(parents=True, exist_ok=True)
    (EV / "composite.json").write_text(json.dumps(out, indent=1) + "\n")
    log("top configurations (sum across instruments; must beat random on both):")
    for k, v in ranked[:16]:
        log(f"  {k:44s} " + " ".join(f"{m}={v['mean_' + m]:.4f}" for m in modes)
            + f"  sum={v['sum']:.4f} rand=" + ",".join(f"{v['rand'][m]:.4f}" for m in modes))
    log(f"selected: {json.dumps(sel_payload)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
