"""H55-5: thermal-fluid evidence extended along a measured structural strike.

The data, and why it is now unblocked
-------------------------------------
``data/external/gdr_wellspring_in_footprint.csv`` is a 27,092-row extract of the INGENIOUS regional
well and spring temperature + aqueous-geochemistry database:

    Great Basin Center for Geothermal Energy, *INGENIOUS - Great Basin Regional Dataset
    Compilation*, Geothermal Data Repository submission 1391, DOI 10.15121/1881483,
    licence CC-BY 4.0, https://gdr.openei.org/submissions/1391
    file: https://gdr.openei.org/files/1391/wellspringdata.gdb.zip

``knowledge/02`` H52-5 recorded this source as **blocked** because the GDR host could not be
re-resolved from the environment where that note was written, and the standing rule is that an
unverifiable file may not move emitted mass.  That blocker is discharged: the submission page and
the file URL both resolve and were read this session (2026-10-06), the DOI is registered, and the
licence is CC-BY 4.0 -- which satisfies the competition's external-data rule ("free to share, and
permitted for use in the challenge and for sharing with the sponsor").

The one number in the CSV that this module does **not** trust is ``dist_known_fault_px``: it was
computed by whoever built the extract, and the rule here is that a derived column is not evidence.
Distance to the visible catalogue is recomputed from ``data/labels.tif`` on the pinned grid.

The physics
-----------
A spring or shallow well whose *silica geothermometer* temperature is high has equilibrated with
rock at that temperature.  Quartz-geothermometer temperatures >= 100 C at discharge imply
circulation to roughly 2-4 km on a normal Great Basin gradient, and that requires (a) elevated heat
flow and (b) a permeable pathway deep enough to reach it.  In extensional terrain that pathway is a
fault: the damage zone and the fault core are the only structures with the fracture permeability and
the throw to bring deep fluid to the surface quickly enough to discharge hot rather than to lose its
heat to the country rock.

So a thermal anomaly is a **point sample of a fault's existence**, taken at the place the fault
intersects the water table.  Two facts make it useful here rather than redundant:

* Measured on the grid, 12,570 distinct cells carry a well or spring; **11,258 of them are more
  than 300 m from any mapped catalogue fault** and 8,958 are more than 1 km away.  The catalogue
  does not explain them.
* Only 194 of those cells sit *on* a catalogue pixel, i.e. the thermal population is almost
  entirely independent of the mapped trace population.

The gap this closes: a spring tells you a fault is *there* but not which *way it runs*.  A single
point earns almost nothing under a 300 m kernel.  So the point is extended along a **measured local
structural strike** -- the direction along which the radiometric/relief field does *not* vary, from
a 2 km structure tensor -- and gated by that tensor's coherence, so a point in unstructured alluvium
stays a point instead of being smeared into an invented 6 km trace.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

PIXEL_M = 100.0
CSV = "data/external/gdr_wellspring_in_footprint.csv"
LABELS = "data/labels.tif"

# silica geothermometer preference order: quartz (most robust, slowest equilibrating) first
GEOTHERM_COLS = ("geothermquartz_c", "geothermchalc_c", "geothermcat_c")
CLASS_WEIGHT = {"hot": 1.0, "warm": 0.6, "cold": 0.0, "unknown": 0.35, "": 0.35}
T_REF_LOW = 25.0        # C: a discharge temperature at or below this is not a thermal anomaly
T_REF_HIGH = 200.0      # C: reservoir temperature at which the anomaly score saturates


def _num(a):
    import pandas as pd
    return pd.to_numeric(a, errors="coerce")


def load_wellspring(path: str | Path = CSV) -> dict:
    """Group the CSV to one row per 100 m cell with the strongest evidence in that cell."""
    import pandas as pd
    df = pd.read_csv(path)
    df["row"] = df["row"].astype(int)
    df["col"] = df["col"].astype(int)
    df["t_obs"] = _num(df["temp_c"])
    for c in GEOTHERM_COLS:
        df[c] = _num(df[c]) if c in df else np.nan
    df["t_res"] = df[list(GEOTHERM_COLS)].max(axis=1, skipna=True)
    df["cls"] = (df["thermalclass"].astype(str).str.strip().str.lower()
                 .map(CLASS_WEIGHT).fillna(0.35))
    # the reservoir estimate is the physics; fall back to the discharge measurement only if absent
    df["t_use"] = df["t_res"].where(df["t_res"].notna() & (df["t_res"] > 0), df["t_obs"])
    g = df.groupby(["row", "col"], as_index=False).agg(
        t_use=("t_use", "max"), t_obs=("t_obs", "max"), t_res=("t_res", "max"),
        cls=("cls", "max"), n_records=("t_use", "size"),
        layers=("layer", lambda s: "|".join(sorted(set(s)))),
        names=("name", lambda s: "|".join(sorted({str(x) for x in s})[:3])))
    return dict(table=g, raw_rows=int(len(df)))


def distance_to_catalogue(shape: tuple[int, int], labels_path: str | Path = LABELS) -> tuple[
        np.ndarray, np.ndarray, np.ndarray]:
    from scipy import ndimage
    with rasterio.open(labels_path) as src:
        lab = src.read(1)
    cat = lab == 1
    valid = lab >= 0
    d = ndimage.distance_transform_edt(~cat, sampling=PIXEL_M)
    return cat, valid, d.astype(np.float32)


def point_field(shape, table, valid, d_cat, t_floor: float = 60.0) -> tuple[np.ndarray, dict]:
    """Thermal-anomaly score per cell, zero where there is no well or spring, or where it is cold.

    ``score = s_T^2 * (0.35 + 0.65 * s_D) * class_weight``

    * ``s_T`` is the reservoir temperature anomaly scaled between 25 C and 200 C and squared, so a
      marginal 40 C spring cannot compete with a 150 C one.
    * ``s_D`` saturates at 3 km from the visible catalogue: the further a hot discharge is from any
      mapped fault, the more certainly it is evidence of an *unmapped* one.  The 0.35 floor keeps a
      hot spring that happens to sit on a mapped trace from being discarded -- the organiser masks
      the trace pixel itself, but the anomaly still locates the structure the trace continues along.
    * Cells whose evidence is only a cold measurement score zero.
    """
    out = np.zeros(shape, dtype=np.float32)
    t = np.asarray(table["t_use"], dtype=np.float64)
    r = np.asarray(table["row"], dtype=np.int64)
    c = np.asarray(table["col"], dtype=np.int64)
    cls = np.asarray(table["cls"], dtype=np.float64)
    ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
    r, c, t, cls = r[ok], c[ok], t[ok], cls[ok]
    fin = np.isfinite(t) & (t >= t_floor)
    r, c, t, cls = r[fin], c[fin], t[fin], cls[fin]
    sT = np.clip((t - T_REF_LOW) / (T_REF_HIGH - T_REF_LOW), 0.0, 1.0)
    dc = d_cat[r, c]
    sD = np.clip(dc / 3000.0, 0.0, 1.0)
    score = (sT ** 2) * (0.35 + 0.65 * sD) * cls
    inside = valid[r, c]
    r, c, score = r[inside], c[inside], score[inside]
    # several records can share a cell: keep the strongest, do not sum (a repeated analysis of one
    # spring is not two springs)
    np.maximum.at(out, (r, c), score.astype(np.float32))
    diag = dict(cells_scored=int((out > 0).sum()), t_floor=t_floor,
                score_sum=float(out.sum()), score_max=float(out.max()),
                cells_ge_0p25=int((out >= 0.25).sum()),
                cells_ge_0p5=int((out >= 0.5).sum()),
                cells_off_catalogue_gt300m=int(((out > 0) & (d_cat > 300)).sum()))
    return out, diag


def structure_strike(field: np.ndarray, valid: np.ndarray, window_m: float = 2000.0
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Local strike azimuth (radians, 0 = N) and coherence from a smoothed structure tensor.

    The strike is the direction along which ``field`` does *not* change -- the small-eigenvalue
    eigenvector of ``J = [[sum gy^2, sum gy gx], [sum gy gx, sum gx^2]]``.  Coherence
    ``((l1-l2)/(l1+l2))^2`` is 1 for a perfectly lineated field and 0 for isotropic noise, and it is
    what stops a thermal point in structureless alluvium from being painted into a fake trace.
    """
    from scipy import ndimage
    f = np.nan_to_num(np.asarray(field, dtype=np.float32), nan=0.0)
    f = np.where(valid, f, 0.0)
    gy, gx = np.gradient(f.astype(np.float32), PIXEL_M, PIXEL_M, edge_order=2)
    r = max(1, int(round(window_m / (2 * PIXEL_M))))
    jyy = ndimage.uniform_filter(gy * gy, size=2 * r + 1, mode="constant")   # row / south
    jxx = ndimage.uniform_filter(gx * gx, size=2 * r + 1, mode="constant")   # col / east
    jyx = ndimage.uniform_filter(gy * gx, size=2 * r + 1, mode="constant")
    tr = jxx + jyy
    det = jxx * jyy - jyx * jyx
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = np.maximum(tr / 2.0 - disc, 0.0)
    coh = np.where(l1 + l2 > 1e-18, ((l1 - l2) / np.maximum(l1 + l2, 1e-18)) ** 2, 0.0)
    # theta is the direction of MAXIMUM change, as (cos, sin) in (col=east, row=south) space.
    # Along-strike is that rotated by 90 deg: (dcol, drow) = (-sin theta, cos theta).  Returning the
    # unit vector rather than an angle removes every north/south sign convention from the walk.
    theta = 0.5 * np.arctan2(2.0 * jyx, jxx - jyy)
    dcol = np.where(valid, -np.sin(theta), 0.0).astype(np.float32)
    drow = np.where(valid, np.cos(theta), 0.0).astype(np.float32)
    return drow, dcol, np.where(valid, coh, 0.0).astype(np.float32)


def extend_along_strike(points: np.ndarray, drow: np.ndarray, dcol: np.ndarray,
                        coherence: np.ndarray, valid: np.ndarray, length_m: float = 3000.0,
                        step_m: float = 100.0, coh_floor: float = 0.30,
                        taper: str = "linear") -> np.ndarray:
    """Paint each thermal point into a bilateral lineament along the locally measured strike.

    The walk stops when coherence falls below ``coh_floor`` or leaves the footprint: a lineament is a
    hypothesis about a *structure*, and where there is no measured structure there is no hypothesis
    to make.  Weight decays linearly to zero at ``length_m`` and is scaled by the local coherence, so
    a point in unstructured alluvium stays a point.
    """
    out = np.zeros(points.shape, dtype=np.float32)
    ys, xs = np.nonzero(points > 0)
    n_steps = max(1, int(round(length_m / step_m)))
    step = step_m / PIXEL_M
    for y, x in zip(ys, xs):
        s0 = float(points[y, x])
        dy, dx = float(drow[y, x]), float(dcol[y, x])
        if not (np.isfinite(dy) and np.isfinite(dx)) or (dy == 0.0 and dx == 0.0):
            out[y, x] = max(out[y, x], s0)
            continue
        for sgn in (1.0, -1.0):
            cy, cx = float(y), float(x)
            for k in range(1, n_steps + 1):
                cy += sgn * dy * step
                cx += sgn * dx * step
                iy, ix = int(round(cy)), int(round(cx))
                if not (0 <= iy < points.shape[0] and 0 <= ix < points.shape[1]):
                    break
                if (not valid[iy, ix]) or coherence[iy, ix] < coh_floor:
                    break
                w = s0 * (1.0 - k / n_steps) if taper == "linear" else s0 * np.exp(-2.0 * k / n_steps)
                w *= float(np.clip((coherence[iy, ix] - coh_floor) / (1.0 - coh_floor), 0.0, 1.0))
                if w > out[iy, ix]:
                    out[iy, ix] = w
    return out


def build(work_dir: str = "work", t_floor: float = 60.0, length_m: float = 3000.0,
          coh_floor: float = 0.30, strike_source: str = "R_tc_rank", log=None) -> dict:
    """Build and cache the two thermal layers; returns their diagnostics."""
    log = log or (lambda *a: print(*a, flush=True))
    work = Path(work_dir) / "derived"
    valid = np.load(work / "valid_footprint.npy")
    cat, val_lab, d_cat = distance_to_catalogue(valid.shape)
    loaded = load_wellspring()
    table = loaded["table"]
    pts, pdiag = point_field(valid.shape, table, valid, d_cat, t_floor=t_floor)
    np.save(work / "Th_point.npy", pts)
    log(f"  Th_point: {pdiag}")

    src = np.load(work / f"{strike_source}.npy", mmap_mode="r")[:]
    src = np.asarray(src, dtype=np.float32)
    drow, dcol, coh = structure_strike(src, valid)
    np.save(work / "Th_strike_drow.npy", drow)
    np.save(work / "Th_strike_dcol.npy", dcol)
    np.save(work / "Th_coherence.npy", coh)
    lin = extend_along_strike(pts, drow, dcol, coh, valid, length_m=length_m, coh_floor=coh_floor)
    np.save(work / "Th_lineament.npy", lin)
    ldiag = dict(cells_scored=int((lin > 0).sum()), score_sum=float(lin.sum()),
                 score_max=float(lin.max()), length_m=length_m, coh_floor=coh_floor,
                 strike_source=strike_source,
                 coherence_median=float(np.median(coh[valid])),
                 cells_above_coh_floor=int((coh[valid] >= coh_floor).sum()),
                 off_catalogue_px=int(((lin > 0) & ~cat & valid).sum()))
    log(f"  Th_lineament: {ldiag}")
    rep = dict(csv=CSV, source="https://gdr.openei.org/submissions/1391",
               doi="10.15121/1881483", licence="CC-BY 4.0",
               raw_csv_rows=loaded["raw_rows"], unique_cells=int(len(table)),
               distance_recomputed_from=LABELS, points=pdiag, lineament=ldiag)
    ev = Path("evidence")
    ev.mkdir(exist_ok=True)
    (ev / "h55_thermal_layers.json").write_text(json.dumps(rep, indent=1))
    return rep
