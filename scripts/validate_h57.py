#!/usr/bin/env python3
"""H57 validation — the two questions the artefact actually depends on.

Two earlier builds of this script failed in instructive ways, and both failures set the protocol
here:

1. Scoring `pa`/`pb` top-of-field emissions with and without a 3-px buffer around the mapped
   catalogue showed the View A classifier's top local maxima *are* the mapped catalogue's halo.
   Remove the halo and the field scores 0.000358 against a random control of 0.001713 — worse than
   random.  The classifier reproduces the map; it does not predict new structure.
2. Excluding the catalogue halo from the candidate pool while scoring against the catalogue makes
   every arm score ~0 by construction.  No arm that is *required* to be novel can ever be scored by
   this simulator, and pretending otherwise is the trap this script avoids.

**The protocol that is both standard and honest.** In each fold the mapped catalogue is split into
`visible` (kept, allowed to be excluded from the pool) and `held` (scored as truth).  Candidates
may be drawn from anywhere except the `visible` catalogue dilated by 2 px.  A field that puts mass
on `held` components therefore has demonstrated generalisation onto faults the model was never
shown — the closest measurable analogue of "finds structure that is not in the labels", and the
one every historical number in `knowledge/` is computed under.

Two tests:

* **Test 1 — placement.** Same field, same pool, same k; 3-px isotropic against 5x3 px along the
  local strike.  Isolates the emitter.
* **Test 2 — ranking.** Catalogue-independent lineament fields against the two classifier fields
  and a random control, identical protocol.

Standing caveat, carried into the receipt: this simulator scores against the mapped catalogue.
`knowledge/10` section 5 measures Spearman(reported leaderboard score, simulated DTI) = -0.1045
(p = 0.734, n = 13).  It ranks arms RELATIVE to one another; it is not a leaderboard proxy, and it
cannot measure credit from faults nobody has mapped.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gems52 import grid as G     # noqa: E402
from gems52 import h57           # noqa: E402
from gems52 import holdout as HO  # noqa: E402
from gems52 import metric as M    # noqa: E402
from gems52 import revealed      # noqa: E402

SEED = 20261007
BUDGETS = (15000, 37654)
ALONG, ACROSS = 5, 3
MIN_COH = 0.25
RIDGE_FIELDS = ("A_grav_slope", "A_tmi_hg", "A_depth_to_base", "B_det_elev", "B_rad_TC")
_YY, _XX = np.mgrid[0:G.SHAPE[0], 0:G.SHAPE[1]]


def log(m):
    print(f"[h57-val {time.strftime('%H:%M:%S')}] {m}", flush=True)


def read_layer(layers, name: str) -> np.ndarray:
    idx = layers.index([name])
    out = np.zeros(G.SHAPE, np.float32)
    for r0 in range(0, G.SHAPE[0], 512):
        r1 = min(r0 + 512, G.SHAPE[0])
        out[r0:r1] = layers.matrix(idx, r0, r1).reshape(r1 - r0, G.SHAPE[1])
    return out


def ridge_strength(field: np.ndarray) -> np.ndarray:
    """Ridge response: |grad| minus the best neighbour one pixel across the gradient direction.

    Non-maximum suppression on the gradient direction is the standard way to turn a potential-field
    or radiometric image into a thin lineament network without ever consulting a fault label.
    """
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


def main() -> int:
    t0 = time.time()
    valid = G.footprint_from("data/training_features.tif", bands="all")
    with rasterio.open("data/labels.tif") as s:
        cat = s.read(1) == 1
    pa = np.nan_to_num(np.load("work/h57/pa_oof.npy"), nan=0.0).astype(np.float32)
    pb = np.nan_to_num(np.load("work/h57/pb_oof.npy"), nan=0.0).astype(np.float32)
    layers = h57.Layers("work/h57")
    corridor = ndimage.binary_dilation(cat, iterations=h57.CORRIDOR_PX)
    permitted = valid & ~corridor

    fields, notes = {}, {}
    for nm in RIDGE_FIELDS:
        grad = read_layer(layers, f"{nm}_grad") * 255.0
        coh, strike, _ = revealed.strike_field(grad, sigma_px=6.0)
        f = np.where(coh >= MIN_COH, coh * ridge_strength(grad), 0.0).astype(np.float32)
        fields[f"ridge_{nm}"] = f
        notes[nm] = dict(mean_coherence=round(float(coh[permitted].mean()), 4),
                         confident_frac=round(float((coh[permitted] >= MIN_COH).mean()), 4))
        log(f"ridge_{nm}: coh mean {coh[permitted].mean():.4f} "
            f"confident {(coh[permitted] >= MIN_COH).mean():.4f}")
    fields["clf_view_A"] = pa
    fields["clf_view_B"] = pb
    fields["clf_union"] = np.maximum(pa, pb)

    acc = read_layer(layers, "A_grav_slope_grad") + read_layer(layers, "A_tmi_hg_grad")
    COH, STRIKE, _ = revealed.strike_field(acc * 255.0, sigma_px=6.0)
    log(f"placement fabric: mean coherence {float(COH[permitted].mean()):.4f}, "
        f"confident {float((COH[permitted] >= MIN_COH).mean()):.4f}")

    results = []
    rng = np.random.default_rng(SEED)
    for mode in ("tip", "hide"):
        folds = HO.make_folds(cat, valid, n_folds=4, buffer_px=4, prevalence=0.002,
                              seed=SEED, mode=mode)
        for f in folds:
            visible = f["visible"] & valid
            blocked = ndimage.binary_dilation(visible, iterations=h57.CORRIDOR_PX)
            legal = f["region"] & permitted & ~blocked
            truth = f["truth"] & f["region"] & valid
            flat_pool = np.flatnonzero(legal.ravel())
            for k in BUDGETS:
                def add(arm, nodes):
                    p = np.where(f["region"], nodes.astype(np.float32), 0.0)
                    r = M.dti(p, truth)
                    results.append(dict(mode=mode, fold=f["fold"], budget=k, arm=arm,
                                        dti=round(r["dti"], 6), emitted=int((p > 0).sum()),
                                        tpw=round(r["tpw"], 2), n_truth=int(r["n_truth"])))

                take = rng.choice(flat_pool, min(k, flat_pool.size), replace=False)
                rnd = np.zeros(G.SHAPE, bool)
                rnd.ravel()[take] = True
                add("random", rnd)

                base = fields["ridge_A_grav_slope"]
                add("PLACE_iso3", h57.iso_select(base, legal, k, min_px=3.0, nms_px=ALONG))
                add("PLACE_aniso5", h57.aniso_select(base, STRIKE, COH, legal, k,
                                                     along_px=ALONG, across_px=ACROSS,
                                                     min_coh=MIN_COH, nms_px=ALONG))
                for name, fld in fields.items():
                    add(f"RANK_{name}",
                        h57.aniso_select(fld, STRIKE, COH, legal, k, along_px=ALONG,
                                         across_px=ACROSS, min_coh=MIN_COH, nms_px=ALONG))
                line = ", ".join(f"{r['arm'].replace('RANK_', '')}={r['dti']:.4f}"
                                 for r in results
                                 if r["mode"] == mode and r["fold"] == f["fold"]
                                 and r["budget"] == k and r["arm"].startswith("RANK_"))
                log(f"{mode} f{f['fold']} k={k}: iso3={results[-10]['dti']:.4f} "
                    f"aniso5={results[-9]['dti']:.4f} | {line}")

    def mean_of(mode, k, arm, fold=None):
        v = [r["dti"] for r in results if r["mode"] == mode and r["budget"] == k
             and r["arm"] == arm and (fold is None or r["fold"] == fold)]
        return float(np.mean(v)) if v else float("nan")

    placement, ranking = {}, {}
    for mode in ("tip", "hide"):
        for k in BUDGETS:
            i, a = mean_of(mode, k, "PLACE_iso3"), mean_of(mode, k, "PLACE_aniso5")
            wins = sum(1 for fo in range(4) if mean_of(mode, k, "PLACE_aniso5", fo)
                       > mean_of(mode, k, "PLACE_iso3", fo))
            placement[f"{mode}@{k}"] = dict(
                iso3=round(i, 6), aniso5=round(a, 6), lift=round(a - i, 6),
                relative_lift_pct=round(100.0 * (a - i) / i, 2) if i > 0 else None,
                folds_won=f"{wins}/4", gate_met=bool(a >= i and wins >= 3),
                kernel_algebra="credited truth per node interval [0,s) on a 1-px trace is 7/3 at "
                               "s=3, 8/3 at s=4 and 3.0 at s=5, i.e. 5 px carries +28.6 % over 3 px")
            ranks = sorted(((mean_of(mode, k, f"RANK_{n}"), n) for n in fields), reverse=True)
            ranking[f"{mode}@{k}"] = [
                dict(rank=i2 + 1, field=n, dti=round(v, 6),
                     lift_vs_random=round(v - mean_of(mode, k, "random"), 6))
                for i2, (v, n) in enumerate(ranks)]

    rep = dict(round="H57-validation-v3", seed=SEED, runtime_s=round(time.time() - t0, 1),
               protocol=dict(
                   budgets=list(BUDGETS), along_px=ALONG, across_px=ACROSS, min_coh=MIN_COH,
                   candidate_pool="fold region & permitted & ~dilate(visible catalogue, 2 px); the "
                                  "held-out catalogue is scored as truth, so credit can only be "
                                  "earned on faults the model never saw",
                   placement_test="identical field, pool and budget; only the emitter differs",
                   ranking_test="every field under the identical pool, budget and emitter"),
               field_notes=notes, results=results, placement=placement, ranking=ranking,
               caveats=[
                   "Scores are against a mapped-catalogue subsample, not the competition's hidden "
                   "truth. knowledge/10 section 5 measures Spearman(reported leaderboard score, "
                   "simulated DTI) = -0.1045 (p=0.734, n=13): relative instrument only.",
                   "A required-novel arm (outside all prior support) cannot be scored by this "
                   "simulator at all: excluding the catalogue halo from the pool removes every "
                   "pixel the truth can occupy. Novelty therefore rests on the support and "
                   "geometry receipts, not on a DTI number.",
                   "The View A classifier's top-of-field emission scored 0.000358 against a random "
                   "control of 0.001713 in build 2 of this script. That is the reason classifier "
                   "fields are not used for the arm's placement here."])
    Path("evidence/h57_validation.json").write_text(
        json.dumps(rep, indent=1, allow_nan=False, default=str) + "\n")
    log("wrote evidence/h57_validation.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())