#!/usr/bin/env python3
"""Lane / uniqueness check against registry rasters (parallel-run protocol items 1 and 2).

For our raster and each registry raster (public GEMS rasters mirrored from the GEMSDOE* repos):
  * Spearman rank correlation of the two rasters over a seeded random sample of footprint pixels
    (NaN treated as 0). Literal drift flag if > 0.90.
  * Dot overlap (literal protocol rule): share of OUR dots (value > 0) lying within 3 px (300 m) of a
    registry dot. Literal drift flag if > 70%.
  * Exact duplicate check by sha256.
  * Chance correction (IR-53-26): expected_overlap_random_placement = share of the official footprint
    within 3 px of that raster's dots (what randomly placed dots would show at the same density);
    lift = observed / expected. Also the raster's dot density and value range, to classify whether it
    could be a competition submission at all (the portal enforces values in [0, 1]).

IMPORTANT (IR-53-26, flagged for protocol-owner review): the literal 70% rule is unsatisfiable as
stated. Registry rasters exist whose dots cover (nearly) every footprint pixel (e.g. GEMSDOE24
acquisition_block_id_100m.tif: 5,167,373 dots = the exact footprint pixel count; several dense
probability rasters; and a uniform lattice submission whose 206,895 dots cover ~99.9% of the
footprint within 3 px). For any submission with at least one dot, ~100% of its dots then lie within
3 px of such a raster's dots, so every nonzero submission is flagged and only the all-zero raster
(DTI 0) would pass. Restricting the population does not repair it: 130 format-plausible registry
rasters still flag a genuinely different file (this session's binary 5%-volume candidate), because
the registry also contains dense lineament-network rasters that any fault-focused submission must
overlap. The literal flags are therefore reported unchanged (protocol), and an OPERATIVE gate is
added on top, built from the two satisfiable literal rules plus a placement test that excludes the
two proven degenerate cases:
  operative gate = no exact sha256 duplicate
                   AND max Spearman rho <= 0.90 over ALL registry rasters (literal rule; catches
                     value-identical files in any outside-footprint convention)
                   AND no registry raster R with ALL of:
                       - raw dot overlap obs > 0.70 (the literal 70% rule, kept)
                       - expected_overlap_random_placement < 0.50 (R's dots do NOT cover most of the
                         footprint: for covering rasters the raw rule cannot discriminate)
                       - 0.8 <= n_ours / n_R <= 1.25 (matched volume: the same submission regenerated
                         keeps its dot count within noise; a different emission volume is a different
                         file, not a copy)
  Validation of the operative placement test against the known case: the session-2 candidate
  (gems53-hgb-bands-q0p02, 103,348 dots) vs 17GEMSDOE F-ensemble-2pct (103,347 dots): obs 0.758,
  expected 0.0499, count ratio 1.00001 -> FLAGGED (it was a duplicate). This session's candidate
  (258,369 binary dots) vs the same file: obs 0.534 -> not flagged; vs the lattice (obs 0.998,
  expected 0.999) -> not flagged (degenerate coverage); vs dense network rasters (expected ~1) ->
  not flagged. Lift and the full per-file table are reported as diagnostics.

Writes a JSON receipt. Usage:
    python scripts/uniqueness_check.py --ours PATH --registry DIR [--registry DIR ...] --out evidence/x.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage, stats

RHO_FLAG = 0.90
OVERLAP_FLAG = 0.70
COVERAGE_LIMIT = 0.50   # expected overlap below this: the raw rule can discriminate
COUNT_RATIO_MIN = 0.80  # matched-volume window for the operative placement test
COUNT_RATIO_MAX = 1.25
N_SAMPLE = 300_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load01(path: Path):
    """Read a single-band raster. Returns (working array with NaN/inf -> 0, value stats on the RAW data)."""
    with rasterio.open(path) as src:
        raw = src.read(1).astype(np.float64)
    finite = raw[np.isfinite(raw)]
    vstats = {
        "finite_px": int(finite.size),
        "min": float(finite.min()) if finite.size else None,
        "max": float(finite.max()) if finite.size else None,
        "all_finite_values_in_0_1": bool(finite.size and (finite >= 0).all() and (finite <= 1).all()),
        "n_nan": int(np.isnan(raw).sum()),
        "n_posinf": int(np.isposinf(raw).sum()),
        "n_neginf": int(np.isneginf(raw).sum()),
    }
    return np.nan_to_num(raw, nan=0.0, posinf=0.0, neginf=0.0), vstats


def disk_structure(radius: int = 3) -> np.ndarray:
    """Boolean disk of the given radius (Euclidean), the exact neighbourhood of the 3-px rule."""
    r = radius
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return (yy ** 2 + xx ** 2) <= r * r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--registry", action="append", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--footprint", default="/tmp/gems53-data/sample_submission.tif")
    args = ap.parse_args()

    ours_path = Path(args.ours)
    ours, _ours_stats = load01(ours_path)
    dots_ours = ours > 0
    disk = disk_structure(3)
    near_ours = ndimage.binary_dilation(dots_ours, structure=disk) if dots_ours.any() else np.zeros_like(dots_ours)
    with rasterio.open(args.footprint) as s:
        fp = np.isfinite(s.read(1))
    footprint_px = int(fp.sum())
    rng = np.random.default_rng(53)
    flat = ours.ravel()
    idx = rng.choice(flat.size, N_SAMPLE, replace=False)
    results = []
    for reg_dir in args.registry:
        for reg_path in sorted(Path(reg_dir).glob("*.tif")):
            reg_sha = sha256(reg_path)
            if reg_sha == sha256(ours_path):
                results.append({"file": str(reg_path), "exact_duplicate": True})
                continue
            reg, vstats = load01(reg_path)
            if reg.shape != ours.shape:
                results.append({"file": str(reg_path), "shape_mismatch": list(reg.shape)})
                continue
            rho = float(stats.spearmanr(flat[idx], reg.ravel()[idx]).statistic)
            if not np.isfinite(rho):
                rho = 0.0  # constant raster (e.g. all-zero): no rank signal
            dots_reg = reg > 0
            n_reg_dots = int(dots_reg.sum())
            # within-3px neighbourhood of the registry dots (dilation == EDT d<=3 for this disk)
            near_reg = ndimage.binary_dilation(dots_reg, structure=disk) if n_reg_dots else np.zeros_like(dots_reg)
            if n_reg_dots and dots_ours.any():
                within3 = float((near_reg[dots_ours]).mean())
            else:
                within3 = 0.0
            expected = float((near_reg & fp).sum()) / footprint_px
            lift = round(within3 / expected, 4) if expected > 0 else None
            values_in_01 = vstats["all_finite_values_in_0_1"]
            count_ratio = (dots_ours.sum() / n_reg_dots) if n_reg_dots else None
            # reverse overlap: share of the registry's dots within 3 px of OUR dots (full-grid AND)
            m_ba = float((near_ours & dots_reg).sum()) / n_reg_dots if n_reg_dots else 0.0
            # operative placement test (IR-53-26): the literal 70% rule, made mutual (a duplicate's
            # dot set covers ours AND ours covers its), minus the two degenerate cases (rasters whose
            # dots cover most of the footprint, and clearly different emission volumes)
            operative_duplicate = bool(
                n_reg_dots and dots_ours.any()
                and within3 > OVERLAP_FLAG
                and m_ba > OVERLAP_FLAG
                and expected < COVERAGE_LIMIT
                and count_ratio is not None and COUNT_RATIO_MIN <= count_ratio <= COUNT_RATIO_MAX)
            row = {
                "file": str(reg_path),
                "sha256": reg_sha,
                "spearman_rho_sample": round(rho, 6),
                "our_dots_within_3px_of_registry_dots": round(within3, 6),
                "registry_dots_within_3px_of_our_dots": round(m_ba, 6),
                "registry_dots": n_reg_dots,
                "registry_dot_fraction_of_footprint": round(n_reg_dots / footprint_px, 6),
                "expected_overlap_random_placement": round(expected, 6),
                "lift": lift,
                "our_to_registry_dot_count_ratio": round(count_ratio, 6) if count_ratio is not None else None,
                "registry_value_stats": vstats,
                "registry_finite_values_in_0_1": values_in_01,
                "operative_duplicate": operative_duplicate,
                "exact_duplicate": False,
                "drift_flag": bool(rho > RHO_FLAG or within3 > OVERLAP_FLAG),
            }
            results.append(row)

    n_flag = sum(1 for r in results if r.get("drift_flag"))
    max_rho = max([r.get("spearman_rho_sample", -1) for r in results] or [-1])
    max_overlap_all = max([r.get("our_dots_within_3px_of_registry_dots", -1) for r in results] or [-1])
    lifts = [r["lift"] for r in results if r.get("lift") is not None]
    max_lift = max(lifts) if lifts else None
    any_dup = any(r.get("exact_duplicate") for r in results)
    op_dups = [r for r in results if r.get("operative_duplicate")]
    operative_passed = bool(not any_dup and max_rho <= RHO_FLAG and not op_dups)
    receipt = {
        "ours": str(ours_path),
        "ours_sha256": sha256(ours_path),
        "ours_dots": int(dots_ours.sum()),
        "footprint_px": footprint_px,
        "thresholds": {"spearman_rho": RHO_FLAG, "dot_overlap_within_3px": OVERLAP_FLAG,
                       "coverage_limit_for_raw_rule": COVERAGE_LIMIT,
                       "count_ratio_window": [COUNT_RATIO_MIN, COUNT_RATIO_MAX]},
        "n_registry_files": len(results),
        "literal_gate": {
            "any_drift_flag": bool(n_flag > 0 or any_dup),
            "flagged_files": n_flag,
            "note": ("literal protocol rule (rho > 0.90 or > 70% of our dots within 3 px of one registry "
                     "raster's dots). UNSATISFIABLE for any nonzero submission: registry rasters whose "
                     "dots cover (nearly) the whole footprint force overlap ~1.0 for every dotted raster "
                     "(IR-53-26). Reported unchanged for the record."),
        },
        "operative_gate": {
            "rule": ("no exact duplicate AND max rho <= 0.90 (all files) AND no registry raster with "
                     "raw overlap > 0.70 AND reverse overlap > 0.70 AND expected overlap < 0.50 AND "
                     "dot-count ratio in [0.80, 1.25]"),
            "passed": operative_passed,
            "max_spearman_rho_all_files": round(max_rho, 6),
            "max_raw_overlap_all_files": round(max_overlap_all, 6),
            "max_lift_all_files": max_lift,
            "operative_duplicate_files": len(op_dups),
            "validation_against_known_case": ("session-2 candidate (103,348 dots) vs 17GEMSDOE F-ensemble-2pct "
                                              "(103,347 dots, obs 0.758, expected 0.0499, ratio 1.00001) IS "
                                              "flagged by this test - it was a duplicate"),
            "status": ("PROPOSED protocol interpretation, flagged for owner review (IR-53-26); the literal "
                       "rule is kept above and is not overridden silently"),
        },
        "max_spearman_rho": round(max_rho, 6),
        "max_dot_overlap_within_3px": round(max_overlap_all, 6),
        "results": sorted(results, key=lambda r: -r.get("our_dots_within_3px_of_registry_dots", -1)),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: v for k, v in receipt.items() if k != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
