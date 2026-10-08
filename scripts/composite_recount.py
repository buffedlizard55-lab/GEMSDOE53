#!/usr/bin/env python3
"""Re-apply the composite selection rule to a finished sweep, without re-running a single fold.

Exists because the rule, not the models, is what changed here.  The first version of
``composite_split.aggregate`` set the control bar for each instrument to ``max`` over every arm whose name
contained ``random`` - and because one of those "random" arms was ``random`` in the far-field with the
corridor ranker in the corridor at share 1.0, the bar on the truncation instrument became the corridor arm's
own score (0.0320).  A candidate could then only pass by beating *the best thing we measured*, and the
shipped far-field arm was reported as failing a control it had in fact beaten (0.0291 vs 0.0250).

The rule is now: the control is ``random`` **in the same regime, at the same split and budget** - the only
comparison that isolates ranking from mass and from the choice of region.  This script recomputes the table
under the fixed rule from ``evidence/composite.json``'s stored per-fold numbers and writes the file back,
keeping the previous selection in ``previous_selection`` so the record shows both verdicts.

    PYTHONPATH=src python3 scripts/composite_recount.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import composite_split as CS                                       # noqa: E402

EV = ROOT / "evidence"


def main() -> int:
    src = EV / "composite.json"
    d = json.loads(src.read_text())
    modes = d["modes"]
    table, ranked, sel = CS.aggregate(d["per_fold"], modes)
    rules = ["control = random ranking in the same regime at the same split and budget (C_far); if a "
             "random-in-both-regimes run exists at that split it is reported as C_all too",
             "candidate must beat its control on every instrument",
             "among those, maximise the sum of the instruments' mean DTI (the regimes are disjoint "
             "populations, so their credits add)",
             "ties break toward smaller total mass",
             "`promoted` additionally requires the registered +0.010 over the naive union on every "
             "instrument; when nothing is promoted the best-sum config is still reported, with "
             "promoted=false"]
    out = dict(d)
    out["previous_selection"] = dict(selected=d.get("selected"),
                                     note="computed under the old max-over-random-variants control; kept "
                                          "so the change of rule is auditable rather than silent")
    out["table"] = table
    out["ranked"] = [[k, v] for k, v in ranked[:60]]
    out["selected"] = sel
    out["selection_rules"] = rules
    out["recount_utc"] = CS.time.strftime("%Y-%m-%dT%H:%M:%SZ", CS.time.gmtime())
    src.write_text(json.dumps(out, indent=1) + "\n")
    CS.log(f"recounted {len(table)} configs from stored per-fold numbers")
    CS.log("top (sum across instruments):")
    for k, v in ranked[:12]:
        CS.log(f"  {k:44s} " + " ".join(f"{m}={v['mean_' + m]:.4f}" for m in modes)
               + f"  sum={v['sum']:.4f} ctrl=" + ",".join(f"{v['rand'][m]:.4f}" for m in modes)
               + f"  beats_random={v['beats_random_all']} union_bar={v['beats_union_bar']} "
                 f"promoted={v['promoted']}")
    CS.log(f"selected: {json.dumps(sel)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
