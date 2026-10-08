#!/usr/bin/env python3
"""Screen every derived layer against the populations that actually matter.

This is the reproduction test the standing brief demands before trusting any number: GEMSDOE47
published precision-at-40k = 0.5049 for ``scarp(det_elev_slope, r=9 px)`` against the given
catalogue's 300 m halo, with a random baseline of 0.0861.  This script recomputes that number from
scratch on this repository's own transform code and reports the delta.  Agreement means the data
restore, the sentinel handling and the transform implementation are all right; a large delta means
one of them is not.  Either way it is recorded, because an unreproduced predecessor number is
worse than a refuted one.

Targets, all measured from the official rasters (no external truth exists locally):
  * ``cat_halo``   -- within 300 m of the given catalogue.
  * ``A1_isolated``-- catalogue components alone inside their own 300 m dilation.
  * ``A2_flanking``-- catalogue components sharing a 300 m dilation with another trace.
  * ``sgmc_offcat``-- within 300 m of SGMC traces that are themselves > 300 m from the catalogue
                      (a *sibling-derived* layer, not an organiser file -- labelled as such).

precision@N = fraction of the top-N footprint pixels inside the target; the random baseline is
the target prevalence.  AUC is tie-aware Mann-Whitney (0.5 credit for ties) on a fixed-seed
subsample, because plateaus of tied values are exactly where a careless AUC lies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

WORK = Path("work/derived")
R_PX = 3.0
DISC = [(dy, dx) for dy in range(-3, 4) for dx in range(-3, 4) if dy * dy + dx * dx <= 9]


def load(name: str) -> np.ndarray:
    return np.asarray(np.load(WORK / f"{name}.npy", mmap_mode="r"), dtype=np.float32)


def precision_at(score: np.ndarray, target: np.ndarray, valid: np.ndarray, n: int) -> float:
    s = np.where(valid, np.nan_to_num(score, nan=-np.inf, neginf=-np.inf, posinf=np.inf), -np.inf)
    t = target & valid
    if t.sum() == 0 or n <= 0:
        return float("nan")
    flat = s.ravel()
    idx = np.argpartition(-flat, n - 1)[:n]
    return float(t.ravel()[idx].mean())


def auc_tie_aware(score: np.ndarray, target: np.ndarray, valid: np.ndarray,
                  sample: int = 300_000, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    m = valid.ravel()
    pos = np.flatnonzero(m & target.ravel())
    neg = np.flatnonzero(m & ~target.ravel())
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    s = np.nan_to_num(score.ravel(), nan=0.0).astype(np.float64)
    p = s[rng.choice(pos, min(sample, pos.size), replace=False)]
    q = s[rng.choice(neg, min(sample, neg.size), replace=False)]
    qs = np.sort(q)
    lo = np.searchsorted(qs, p, side="left")
    hi = np.searchsorted(qs, p, side="right")
    return float(np.mean((hi + lo) / 2.0) / qs.size)


def shift(a: np.ndarray, dy: int, dx: int) -> np.ndarray:
    out = np.zeros_like(a)
    ys0, ys1 = max(0, dy), min(a.shape[0], a.shape[0] + dy)
    xs0, xs1 = max(0, dx), min(a.shape[1], a.shape[1] + dx)
    out[ys0:ys1, xs0:xs1] = a[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
    return out


def component_isolation(cat: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """(isolated_px, flanking_px, n_components) over 8-connected catalogue components.

    A component is *flanking* iff some pixel within its 3 px (300 m) disc belongs to a different
    component.  Vectorised over the disc, so it is exact and costs 29 shifts, not one loop per
    component.
    """
    comp, ncomp = ndimage.label(cat, structure=np.ones((3, 3), dtype=bool))
    other = np.zeros(cat.shape, dtype=bool)
    for dy, dx in DISC:
        sh = shift(comp, dy, dx)
        other |= (sh > 0) & (sh != comp)
    fl = np.zeros(cat.shape, dtype=bool)
    ids_flank = np.zeros(ncomp + 1, dtype=bool)
    ids_flank[np.unique(comp[other & cat])] = True
    flanking = ids_flank[comp] & cat
    return cat & ~flanking, flanking, int(ncomp)


def main() -> int:
    ev = Path("evidence")
    ev.mkdir(parents=True, exist_ok=True)
    valid = np.load(WORK / "valid_footprint.npy")
    with rasterio.open("data/labels.tif") as src:
        cat = src.read(1) == 1
    ed_cat = ndimage.distance_transform_edt(~cat)
    targets = {"cat_halo": (ed_cat <= R_PX) & valid}
    iso, flank, ncomp = component_isolation(cat & valid)
    targets["A1_isolated"], targets["A2_flanking"] = iso, flank
    print(f"catalogue px {int(cat.sum())} in {int(ncomp)} components; "
          f"isolated {int(iso.sum())} px, flanking {int(flank.sum())} px")
    try:
        with rasterio.open("data/external/derived_sgmc_faults_100m_u8.tif") as src:
            sg = (src.read(1) > 0) & valid & (ed_cat > R_PX)
        targets["sgmc_offcat"] = (ndimage.distance_transform_edt(~sg) <= R_PX) & valid
        print(f"sgmc off-catalogue px: {int(sg.sum())}")
    except Exception as exc:  # noqa: BLE001
        print("sgmc unavailable:", repr(exc))

    out = {"footprint_px": int(valid.sum()), "targets": {}, "rows": []}
    for name, tm in targets.items():
        out["targets"][name] = dict(px=int(tm.sum()), prevalence=float(tm.sum() / valid.sum()))
    layers = sorted({f.stem for f in WORK.glob("*.npy")
                     if not f.name.endswith("__rank.npy") and f.name != "valid_footprint.npy"})
    for lay in layers:
        sc = load(lay)
        row = {"layer": lay}
        for name, tm in targets.items():
            base = max(tm.sum() / valid.sum(), 1e-12)
            p40 = precision_at(sc, tm, valid, 40_000)
            row[name] = dict(p40=float(p40), p10=float(precision_at(sc, tm, valid, 10_000)),
                             lift40=float(p40 / base), auc=auc_tie_aware(sc, tm, valid))
        out["rows"].append(row)
        c, a1 = row["cat_halo"], row["A1_isolated"]
        print(f"{lay:<22} cat40={c['p40']:.4f} ({c['lift40']:>5.2f}x) auc={c['auc']:.4f} "
              f"| A1 40={a1['p40']:.4f} ({a1['lift40']:.2f}x) "
              f"| sgmc40={row.get('sgmc_offcat', {}).get('p40', float('nan')):.4f}")
    (ev / "layer_screen.json").write_text(json.dumps(out, indent=1))

    hit = [r for r in out["rows"] if r["layer"] == "B_scarp_p900"]
    if hit:
        got = hit[0]["cat_halo"]["p40"]
        print(f"\nREPRODUCTION  B_scarp_p900 precision@40k vs catalogue halo = {got:.4f}\n"
              f"              GEMSDOE47 published 0.5049  ->  delta {got - 0.5049:+.4f}\n"
              f"              random baseline here {out['targets']['cat_halo']['prevalence']:.4f} "
              f"(published 0.0861)")
    print("\nwrote evidence/layer_screen.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
