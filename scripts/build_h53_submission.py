#!/usr/bin/env python3
"""H53-1 submission builder: the coincidence-gated field, emitted as separated single-pixel nodes.

Refuses to write anything unless ``evidence/h53_holdout.json`` carries a **passed** verdict for the arm
it is about to build, in both blocked instruments.  That refusal is the standing instruction ("do not
spend a submission slot on an idea that has not beaten the current holdout best") expressed in code
rather than in prose; ``--force`` exists for research runs and is recorded in the audit.

Emission geometry is the arm's own measured choice: greedy top-`budget` under a **minimum separation**
(`gems52.nodes.emit_nodes`), because the incumbent's geometry -- 37,654 isolated single pixels, median
nearest-neighbour distance 3.0 px -- is a separation constraint, and the plain top-k emitter has no
notion of separation.  The coincidence gate decides *which* pixels; the separation decides *how they are
spaced* against the 300 m kernel.
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

from gems52 import dicoincidence as DC      # noqa: E402
from gems52 import gates                    # noqa: E402
from gems52 import grid as GR               # noqa: E402
from gems52 import nodes as N                # noqa: E402

EV = ROOT / "evidence"
WORK = ROOT / "work" / "dicoincidence"
OUT = ROOT / "docs" / "downloads"
NAME = "gems52-h53-coincidence-gated-singles-37654px-r1"
CANDIDATE = "B_corr:spaced|37654"
COMPARATORS = ("union:spaced|37654", "B_only:spaced|37654", "B_corr_rolled|37654")


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def verdict_from(evidence: Path, candidate: str = CANDIDATE,
                 comparators: tuple[str, ...] = COMPARATORS) -> dict:
    """Promotion decision, computed from the artifact rather than asserted next to it.

    A pass needs, on **both** instruments: a higher fold-mean than every comparator, and a positive
    margin in at least 3 of 4 folds against the strongest comparator.  Both are stated here so a later
    session can see exactly what was required before the slot was spent, and can re-run this function.
    """
    d = json.loads(evidence.read_text())
    checks, ok = {}, True
    for mode, m in d["modes"].items():
        s = m["summary"]
        base = {k: s[k]["mean"] for k in comparators}
        wins = {k: int(sum(r["scores"][candidate]["dti"] > r["scores"][k]["dti"]
                           for r in m["per_fold"])) for k in comparators}
        c = {"candidate_mean": round(s[candidate]["mean"], 5), "comparator_means": base,
             "fold_wins_of_4": wins, "emit": m.get("emit")}
        c["beats_all"] = bool(s[candidate]["mean"] > max(base.values()))
        c["beats_strongest_3of4"] = bool(wins[max(base, key=base.get)] >= 3)
        checks[mode] = c
        ok = ok and c["beats_all"] and c["beats_strongest_3of4"]
    # a second, independent requirement: the ordering must be the same in both modes (sign consistency)
    order = {mode: sorted(checks[mode]["comparator_means"], key=lambda k: -checks[mode][
        "comparator_means"][k]) for mode in checks}
    same_order = len({tuple(v) for v in order.values()}) == 1
    verdict = {"candidate": candidate, "comparators": list(comparators), "checks": checks,
               "comparator_order_identical_across_modes": same_order,
               "promoted": bool(ok and same_order),
               "rule": "fold-mean strictly greater than every comparator on both instruments AND >=3/4 "
                       "fold wins against the strongest comparator AND identical comparator ordering",
               "note": "the comparator ordering being identical in tip and hide is the part that makes "
                       "this a mechanism rather than a lucky fold set"}
    return verdict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--min-px", type=float, default=3.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    ev = EV / "h53_holdout.json"
    verdict = verdict_from(ev)
    d = json.loads(ev.read_text())
    d["verdict"] = verdict
    ev.write_text(json.dumps(d, indent=1) + "\n")
    log(f"verdict.promoted = {verdict['promoted']} "
        f"({ {m: round(c['candidate_mean'], 4) for m, c in verdict['checks'].items()} })")
    if not verdict["promoted"] and not a.force:
        raise SystemExit("holdout verdict is not promoted; refusing to build (use --force for research)")

    valid, cat = (np.load(ROOT / "work/derived/valid_footprint.npy"),
                  (rasterio.open(ROOT / "data/labels.tif").read(1) == 1))
    z = np.load(WORK / "nodes.npz")
    arms = np.load(WORK / "arms.npz")
    node = {k: z[k] for k in ("row", "col")}
    shape = valid.shape

    def dense(values):
        g = np.zeros(shape, dtype=np.float32)
        g[node["row"], node["col"]] = values.astype(np.float32)
        return g

    field = dense(arms["B_corr"])
    field_union = dense(arms["union"])
    allowed = valid & ~cat
    em = N.emit_nodes(field, allowed, a.budget, min_px=a.min_px, log=log)
    em_u = N.emit_nodes(field_union, allowed, a.budget, min_px=a.min_px)
    log(f"emitted {int(em.sum())} single pixels at min separation {a.min_px} px")

    tif = OUT / f"{NAME}.tif"
    receipt = GR.write_geotiff(tif, em.astype(np.float32))
    log(f"wrote {tif} ({receipt})")

    fmt = gates.format_report(tif, ROOT / "data/sample_submission.tif")
    priors = gates.find_priors([ROOT / "docs/downloads", ROOT / "data/scored",
                                ROOT / "data/reference", ROOT / "submission"], exclude=tif)
    uni = gates.uniqueness_report(em > 0, priors)
    shared = int(((em > 0) & (em_u > 0)).sum())
    novel = int(((em > 0) & ~(em_u > 0)).sum())
    nonunion = {"coincidence_gated_px": int(em.sum()), "ungated_union_px_at_same_budget": int(em_u.sum()),
                "shared_px": shared, "coincidence_only_px": novel,
                "jaccard_vs_ungated_union": round(shared / max(int(em.sum()) + int(em_u.sum()) - shared, 1), 5),
                "confirmed_not_mere_union": bool(novel > 0 and shared / max(int(em.sum()), 1) < 0.9)}
    from scipy import ndimage as ND
    n_segments = int(ND.label(em > 0, structure=np.ones((3, 3), bool))[1])
    note = ("H53-1: surface lineaments kept only where an independent geophysical family agrees on "
            "strike in the same 1.6 km tile (permutation-calibrated, top 10%); 37,654 spaced single "
            "pixels.")
    if len(note) > 200:
        note = note[:197] + "..."
    # the site renders these keys; they are derived from the verdict rather than typed into HTML
    hg = {}
    for mode, chk in verdict["checks"].items():
        hg[mode] = {"vs_naive_union": round(chk["candidate_mean"] - chk["comparator_means"][
                        "union:spaced|37654"], 5),
                    "vs_surface_only": round(chk["candidate_mean"] - chk["comparator_means"][
                        "B_only:spaced|37654"], 5),
                    "vs_rolled_control": round(chk["candidate_mean"] - chk["comparator_means"][
                        "B_corr_rolled|37654"], 5)}
    holdout_gates = {"promoted": bool(verdict["promoted"]),
                     "composite_control_bar": bool(all(v["vs_rolled_control"] > 0
                                                       for v in hg.values())),
                     "registered_union_bar": bool(all(v["vs_naive_union"] > 0 for v in hg.values())),
                     "vs_naive_union": {m: hg[m]["vs_naive_union"] for m in hg},
                     "vs_rolled_control": {m: hg[m]["vs_rolled_control"] for m in hg},
                     "reason": ("fold-mean DTI above every comparator on both blocked instruments, "
                                "with identical comparator ordering; rule in "
                                "registry/preregistration_h53.json")}
    receipt.update({"holdout_gates": holdout_gates,
                    "file": tif.name, "budget": int(a.budget), "n_segments": n_segments, "note": note,
                    "submission_name": NAME,
                    "format": fmt, "uniqueness": uni, "non_union_verification": nonunion,
                    "emit_budget": a.budget, "min_px": a.min_px, "arm": CANDIDATE,
                    "verdict": verdict, "forced": bool(a.force and not verdict["promoted"]),
                    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    (EV / "submission_h53_audit.json").write_text(json.dumps(receipt, indent=1) + "\n")
    (EV / f"submission_{NAME}.json").write_text(json.dumps(receipt, indent=1) + "\n")
    assert len(receipt["note"]) <= 200, "the submission note must fit the form's 200-character box"
    (ROOT / "submission").mkdir(exist_ok=True)
    (ROOT / "submission" / "LATEST.txt").write_text(tif.name + "\n")
    log(f"format_ok={fmt.get('format_ok')} problems={fmt.get('problems')}")
    log(f"uniqueness: zero_sha256_collisions={uni.get('zero_sha256_collisions')} "
        f"max_jaccard_vs_prior={uni.get('max_jaccard_vs_prior_submissions')}")
    log(f"non-union: coincidence-only px {novel}, jaccard vs ungated union "
        f"{nonunion['jaccard_vs_ungated_union']}")
    log("wrote evidence/submission_h53_audit.json and submission/LATEST.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
