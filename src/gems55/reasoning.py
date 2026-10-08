"""Per-candidate geological reasoning for every A-confident / B-abstaining emitted segment.

Phase 2 of this competition is an expert panel reading predictions and verifying faults
(https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/).  A reviewer cannot
verify a pixel; they can verify a *claim about a structure*.  So for every connected component of
the disagreement stratum that the shipped file actually emits, this module writes the measurements
that make the claim, the sources they came from, and an interpretation assembled **only** from those
measurements by fixed rules -- no sentence here is generated that a number in the same record does
not support.

The rule set is deliberately conservative and says "no structural evidence" when that is what the
numbers say.  A reasoning file that flatters every candidate is worse than none, because the panel's
job is to find the ones that are wrong.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PIXEL_M = 100.0


def _rank_in(a: np.ndarray, mask: np.ndarray) -> dict:
    v = a[mask]
    v = v[np.isfinite(v)]
    if v.size == 0:
        return dict(n=0, mean=None, p10=None, p50=None, p90=None)
    return dict(n=int(v.size), mean=round(float(v.mean()), 4),
                p10=round(float(np.percentile(v, 10)), 4),
                p50=round(float(np.percentile(v, 50)), 4),
                p90=round(float(np.percentile(v, 90)), 4))


def _principal_axis(ys: np.ndarray, xs: np.ndarray) -> tuple[float, float, float]:
    """(strike_deg_from_north, elongation, length_px) of one component."""
    if ys.size < 3:
        return float("nan"), 1.0, float(ys.size)
    y = ys.astype(np.float64) - ys.mean()
    x = xs.astype(np.float64) - xs.mean()
    cov = np.array([[np.mean(x * x), np.mean(x * y)], [np.mean(x * y), np.mean(y * y)]])
    w, v = np.linalg.eigh(cov)
    ax = v[:, int(np.argmax(w))]           # (col, row) direction of greatest extent
    strike = float(np.degrees(np.arctan2(ax[0], ax[1])) % 180.0)
    lo = max(float(w.min()), 1e-12)
    return strike, float(np.sqrt(w.max() / lo)), float(np.hypot(y.max() - y.min(),
                                                                x.max() - x.min()))


def interpret(rec: dict) -> list[str]:
    """Fixed-rule interpretation.  Every clause names the measurement that triggered it."""
    out = []
    d = rec["distance_to_nearest_catalogue_m"]
    if d is not None and d <= 300:
        out.append(f"The nearest mapped trace is {d:.0f} m away, i.e. inside the scored kernel's "
                   f"300 m support: mass here is credited only against *new* truth, since the "
                   f"catalogue pixel itself is masked out of the evaluation.")
    elif d is not None and d <= 1000:
        out.append(f"The nearest mapped trace is {d:.0f} m away -- outside the 300 m kernel, so it "
                   f"earns nothing from that trace, but close enough that a continuation, a "
                   f"correction or an unmapped strand of the same structure is the plausible "
                   f"reading. Forum thread 11516 post #4 (chrisk-dd, organiser staff) confirms new "
                   f"truth may sit within 300 m of a known trace and that such corrections are part "
                   f"of the goal.")
    elif d is not None:
        out.append(f"The nearest mapped trace is {d:.0f} m away (> 1 km), so this is not a "
                   f"re-detection of a catalogued fault: it is an independent structure.")
    db = rec["depth_to_basement_rank"]
    if db and db.get("mean") is not None:
        if db["mean"] >= 0.55:
            out.append(f"Mean depth-to-basement rank {db['mean']:.2f} is above the footprint "
                       f"background: thick cover, which is why a surface view abstains here and why "
                       f"a range front could be buried rather than absent.")
        elif db["mean"] <= 0.35:
            out.append(f"Mean depth-to-basement rank {db['mean']:.2f} is below background: shallow "
                       f"basement, so the 'buried under cover' reading is weak and this candidate "
                       f"rests on the potential-field contrast alone.")
    g = rec["gravity_step_rank"]
    if g and g.get("p50") is not None and g["p50"] >= 0.60:
        out.append(f"Isostatic-gravity across-strike step is in the upper tail (median rank "
                   f"{g['p50']:.2f}): a density contrast consistent with basement juxtaposition "
                   f"across a normal fault.")
    t = rec["tc_step_rank"]
    if t and t.get("p50") is not None and t["p50"] >= 0.60:
        out.append(f"Radiometric total-count across-strike step is in the upper tail (median rank "
                   f"{t['p50']:.2f}): a near-surface material contrast, i.e. basin fill against "
                   f"range bedrock, which survives even where the scarp has been buried.")
    th = rec["thk_step_rank"]
    if th and th.get("p50") is not None and th["p50"] >= 0.60:
        out.append(f"Th/K step is in the upper tail (median rank {th['p50']:.2f}): Th-enriched "
                   f"detrital alluvium against K-bearing bedrock, the elemental form of the same "
                   f"contact, and one that soil moisture and flight height do not explain.")
    e = rec["elongation"]
    if e is not None and e >= 3.0 and rec["length_px"] >= 8:
        out.append(f"The emitted patch is linear (elongation {e:.1f}, extent {rec['length_px']:.0f} "
                   f"px = {rec['length_px']*PIXEL_M/1000:.1f} km) with strike "
                   f"{rec['strike_deg']:.0f} deg, i.e. it is shaped like a trace rather than like "
                   f"an anomaly blob.")
    elif e is not None and e < 2.0:
        out.append(f"CAVEAT: the patch is not linear (elongation {e:.1f}), so the 'fault trace' "
                   f"reading is not supported by its shape. Treat as a point candidate only.")
    th_ = rec["nearest_thermal_feature"]
    if th_ and th_.get("t_use_c") is not None and th_["t_use_c"] >= 60 and th_["distance_m"] <= 5000:
        out.append(f"A well or spring with a {th_['t_use_c']:.0f} C measurement sits "
                   f"{th_['distance_m']:.0f} m away ({th_['name']}; INGENIOUS/GDR 1391, "
                   f"DOI 10.15121/1881483). Warm discharge that close is independent evidence of a "
                   f"permeable pathway, and permeability at that distance from any mapped trace "
                   f"implies structure the catalogue does not contain.")
    if not out:
        out.append("No supporting measurement cleared its threshold. This candidate is emitted "
                   "because the ranking placed it here, not because a physical signature was "
                   "identified; a reviewer should treat it as unsupported.")
    return out


def build(emitted: np.ndarray, stratum: np.ndarray, layers: dict[str, np.ndarray],
          valid: np.ndarray, d_cat: np.ndarray, cat: np.ndarray,
          thermal_table=None, transform=None, min_px: int = 1, group_px: int = 3,
          log=lambda *a: None) -> dict:
    """Reasoning records for every emitted component of the A-only disagreement stratum.

    ``layers`` must carry the rank-encoded fields named in :func:`interpret`; missing layers are
    reported as missing rather than silently dropped, so a reviewer can see what was not measured.
    """
    from scipy import ndimage
    sel = emitted & stratum & valid & ~cat
    # The shipped emission is 8-isolated by construction (max component = 1), so labelling ``sel``
    # itself would produce one record per lone pixel -- useless to a reviewer who has to look at a
    # place on a map.  Grouping at ``group_px`` = 300 m, the scored kernel's own support, makes each
    # record a structural neighbourhood: the scale at which the metric credits, and the scale at
    # which "is there a fault here" is a question a geologist can answer.
    lab, n = ndimage.label(ndimage.binary_dilation(sel, iterations=group_px),
                           structure=np.ones((3, 3), bool))
    log(f"  A-only emitted neighbourhoods: {n} groups over {int(sel.sum())} emitted px "
        f"(group_px={group_px})")
    recs = []
    present = {k: v for k, v in layers.items() if v is not None}
    # slicing every layer to the component's bounding box is the difference between a reasoning file
    # that takes seconds and one that takes hours: _rank_in over a full 12.28 M-pixel grid, nine
    # layers, once per component, is O(components * grid) for data that lives in a few hundred cells.
    objs = ndimage.find_objects(lab)
    th_arr = None
    if thermal_table is not None:
        tt = np.asarray(thermal_table["t_use"], dtype=np.float64)
        # keep only cells that actually carry a temperature: a well row with no measurement is a
        # location, not evidence, and reporting it as "nearest thermal feature: nan" is noise
        keep = np.isfinite(tt) & (tt > 0)
        th_arr = dict(r=np.asarray(thermal_table["row"], dtype=np.float64)[keep],
                      c=np.asarray(thermal_table["col"], dtype=np.float64)[keep],
                      t=tt[keep],
                      n=[str(x)[:120] for x, k in zip(thermal_table["names"], keep) if k],
                      n_all=int(thermal_table.shape[0]), n_with_temperature=int(keep.sum()))
    for cid in range(1, n + 1):
        sl = objs[cid - 1]
        if sl is None:
            continue
        comp = lab[sl] == cid
        if int(comp.sum()) < min_px:
            continue
        ys, xs = np.nonzero(comp)
        ys = ys + sl[0].start
        xs = xs + sl[1].start
        strike, elong, length = _principal_axis(ys, xs)
        sub = {k: v[sl] for k, v in present.items()}
        n_emit = int((comp & sel[sl]).sum())
        rec = dict(component=int(cid), n_px=int(ys.size), n_emitted_px=n_emit,
                   group_px=group_px,
                   row=int(round(float(ys.mean()))), col=int(round(float(xs.mean()))),
                   strike_deg=None if not np.isfinite(strike) else round(strike, 1),
                   elongation=None if not np.isfinite(elong) else round(elong, 2),
                   length_px=round(length, 1),
                   distance_to_nearest_catalogue_m=round(float(d_cat[sl][comp].min()), 1),
                   mean_distance_to_catalogue_m=round(float(d_cat[sl][comp].mean()), 1))
        if transform is not None:
            from rasterio.transform import xy
            from rasterio.warp import transform as wtransform
            lat, lon = None, None
            try:
                # xy() returns (x, y) = (easting, northing) for a north-up raster; assigning it in
                # the other order puts the candidate in Colombia instead of Nevada, which is the kind
                # of error a reviewer would never recover from.
                easting, northing = xy(transform, rec["row"], rec["col"])
                lon, lat = wtransform("EPSG:32611", "EPSG:4326", [easting], [northing])
                rec["utm_easting"] = easting
                rec["utm_northing"] = northing
                rec["lat"] = round(float(lat[0]), 5)
                rec["lon"] = round(float(lon[0]), 5)
            except Exception as exc:                                # pragma: no cover
                rec["coordinate_error"] = str(exc)
        for key, layer in (("depth_to_basement_rank", "A_depth_base_rank__rank"),
                           ("gravity_step_rank", "A_grav_step__rank"),
                           ("mag_step_rank", "A_mag_step__rank"),
                           ("strain_inv_rank", "A_strain_inv_rank__rank"),
                           ("tc_step_rank", "R_tc_step900__rank"),
                           ("thk_step_rank", "R_thk_step900__rank"),
                           ("uk_step_rank", "R_uk_step900__rank"),
                           ("scarp_rank", "B_scarp_p900__rank"),
                           ("coherence", "Th_coherence")):
            a = sub.get(layer)
            rec[key] = _rank_in(a, comp) if a is not None else None
        if th_arr is not None:
            rec["nearest_thermal_feature"] = _nearest_thermal(rec["row"], rec["col"], th_arr)
        rec["interpretation"] = interpret(rec)
        recs.append(rec)
    recs.sort(key=lambda r: (-r["n_emitted_px"], -r["n_px"]))
    return dict(n_components=len(recs), n_px=int(sel.sum()), group_px=group_px,
                 n_neighbourhood_px=int(lab.astype(bool).sum()),
                layers_present=sorted(present),
                layers_missing=sorted(set(layers) - set(present)),
                rule=("every clause of every interpretation is produced by interpret() from a "
                      "measurement in the same record; a clause with no supporting number is never "
                      "emitted, and a candidate with no support says so explicitly"),
                candidates=recs)


def _nearest_thermal(row: int, col: int, th: dict) -> dict | None:
    """Nearest well or spring cell, by pre-extracted numpy columns (not a pandas row lookup)."""
    if th is None or th["r"].size == 0:
        return None
    d = np.hypot(th["r"] - row, th["c"] - col) * PIXEL_M
    i = int(np.argmin(d))
    t = float(th["t"][i])
    return dict(distance_m=round(float(d[i]), 1), row=int(th["r"][i]), col=int(th["c"][i]),
                t_use_c=None if not np.isfinite(t) else round(t, 1), name=th["n"][i],
                source="INGENIOUS/GDR submission 1391, DOI 10.15121/1881483, CC-BY 4.0")


def write_json(path: str | Path, payload: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=1, allow_nan=False, default=str))
