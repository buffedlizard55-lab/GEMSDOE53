#!/usr/bin/env python3
"""Lane / uniqueness check against EVERY registry raster (parallel-run protocol, items 1 and 2). Version 2.

For our final raster and each registry raster (public GEMS submissions, see scripts/fetch_registry.py):
  * exact duplicate check by SHA-256;
  * Spearman rank correlation over a seeded random sample of FOOTPRINT pixels (NaN treated as 0). Flag if > 0.90;
  * dot overlap: share of OUR dots (value > 0) that lie within 3 px (300 m) of a registry dot. Flag if > 70%.
    A registry raster is "dense" when more than 20% of its footprint pixels are > 0 (probability maps, not
    dot files). Dense rasters have no meaningful "dots", so their overlap is computed against their top-N pixels,
    where N = our dot count. Both numbers are recorded for every file; the flag uses the mode named in the row.
  * pre-placement surface check (optional --surface): the continuous score surface BEFORE dots are placed is
    rank-correlated with each registry raster and its top-N pixels are overlap-tested the same way.

Version history: v1 (2026-09-25 prior session) used 138 files and no dense rule. v2 (this file) covers the full
registry and adds the dense rule, the surface check, and KD-tree overlap.

Usage:
  python scripts/uniqueness_check.py --ours PATH --registry DIR [--surface SURFACE.npy] --out evidence/x.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import stats
from scipy.spatial import cKDTree

RHO_FLAG = 0.90
OVERLAP_FLAG = 0.70
WITHIN_PX = 3.0
DENSE_FRACTION = 0.20
N_SAMPLE = 300_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_plain(path: Path) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float64)
    return np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)


def _finite_or_none(x):
    x = float(x)
    return x if np.isfinite(x) else None


def within_px_share(ours_rc: np.ndarray, reg_rc: np.ndarray) -> float:
    if reg_rc.shape[0] == 0 or ours_rc.shape[0] == 0:
        return 0.0
    tree = cKDTree(reg_rc)
    d, _ = tree.query(ours_rc, k=1)
    return float((d <= WITHIN_PX).mean())


def top_n_rc(values: np.ndarray, footprint: np.ndarray, n: int) -> np.ndarray:
    vals = np.where(footprint, values, -np.inf)
    flat = vals.ravel()
    n = min(n, int(np.isfinite(flat).sum()))
    if n <= 0:
        return np.zeros((0, 2), dtype=np.int64)
    idx = np.argpartition(-flat, n - 1)[:n]
    idx = idx[np.argsort(-flat[idx], kind="stable")]
    rr, cc = np.unravel_index(idx, values.shape)
    return np.stack([rr, cc], axis=1)


def check(ours_path: Path, registry_dir: Path | None, footprint: np.ndarray, surface: np.ndarray | None = None,
          sample_seed: int = 53) -> dict:
    """Return a receipt dict. `footprint` is the boolean official footprint (finite sample pixels)."""
    ours = load_plain(ours_path)
    ours_rc = np.stack(np.nonzero(ours > 0), axis=1)
    n_ours = int(ours_rc.shape[0])
    ours_sha = sha256(ours_path)
    fp_idx = np.flatnonzero(footprint.ravel())
    rng = np.random.default_rng(sample_seed)
    samp = fp_idx[rng.choice(fp_idx.size, min(N_SAMPLE, fp_idx.size), replace=False)]
    ours_s = ours.ravel()[samp]
    surf_s = surface.ravel()[samp] if surface is not None else None
    surf_rc = top_n_rc(surface, footprint, n_ours) if surface is not None else None

    rows = []
    files = sorted(registry_dir.glob("*.tif")) if registry_dir else []
    for reg_path in files:
        row: dict = {"file": reg_path.name}
        reg_sha = sha256(reg_path)
        row["sha256"] = reg_sha
        if reg_sha == ours_sha:
            row.update(exact_duplicate=True, drift_flag=True)
            rows.append(row)
            continue
        reg = load_plain(reg_path)
        if reg.shape != ours.shape:
            row.update(shape_mismatch=list(reg.shape), drift_flag=False)
            rows.append(row)
            continue
        reg_s = reg.ravel()[samp]
        rho = _finite_or_none(stats.spearmanr(ours_s, reg_s).statistic)  # constant rasters have undefined rho
        reg_pos = reg > 0
        frac_pos = float(reg_pos[footprint].mean())
        dense = frac_pos > DENSE_FRACTION
        topn_rc = top_n_rc(reg, footprint, n_ours)
        ov_topn = within_px_share(ours_rc, topn_rc)
        if dense:  # strict nonzero-dot overlap is meaningless for a probability map; not computed (speed)
            ov_strict = None
            ov_mode = "dense_top_N"
            ov_used = ov_topn
        else:
            strict_rc = np.stack(np.nonzero(reg_pos), axis=1)
            ov_strict = within_px_share(ours_rc, strict_rc)
            ov_mode = "nonzero_dots"
            ov_used = ov_strict
        row.update(
            exact_duplicate=False,
            spearman_rho_sample=None if rho is None else round(rho, 6),
            spearman_undefined_reason=None if rho is not None else "constant input (no rank variation)",
            registry_nonzero_fraction_of_footprint=round(frac_pos, 6),
            registry_dense=dense,
            our_dots_within_3px_strict=None if ov_strict is None else round(ov_strict, 6),
            our_dots_within_3px_top_N=round(ov_topn, 6),
            overlap_mode=ov_mode,
            our_dots_within_3px_used=round(ov_used, 6),
            registry_dots_nonzero=int(reg_pos.sum()),
        )
        flags = {"rho": rho is not None and rho > RHO_FLAG, "overlap": ov_used > OVERLAP_FLAG}
        if surf_s is not None:
            rho_s = _finite_or_none(stats.spearmanr(surf_s, reg_s).statistic)
            ov_s = within_px_share(surf_rc, topn_rc)
            row.update(surface_spearman_rho=None if rho_s is None else round(rho_s, 6),
                       surface_top_N_within_3px=round(ov_s, 6))
            flags["surface_rho"] = rho_s is not None and rho_s > RHO_FLAG
            flags["surface_overlap"] = ov_s > OVERLAP_FLAG
        row["drift_flags"] = [k for k, v in flags.items() if v]
        row["drift_flag"] = bool(any(flags.values()))
        rows.append(row)

    def mx(key):
        vals = [r[key] for r in rows if r.get(key) is not None]  # undefined (None) values are skipped
        return max(vals) if vals else None

    receipt = {
        "method_version": 2,
        "ours": str(ours_path),
        "ours_sha256": ours_sha,
        "ours_dots": n_ours,
        "thresholds": {"spearman_rho": RHO_FLAG, "dot_overlap_within_3px": OVERLAP_FLAG,
                       "within_px": WITHIN_PX, "dense_fraction_rule": DENSE_FRACTION},
        "spearman_sample_px": int(samp.size),
        "registry_dir": str(registry_dir) if registry_dir else None,
        "n_registry_files": len(files),
        "n_registry_files_compared": sum(1 for r in rows if "spearman_rho_sample" in r),
        "n_dense_registry_files": sum(1 for r in rows if r.get("registry_dense")),
        "any_drift_flag": bool(any(r.get("drift_flag", False) for r in rows)),
        "max_spearman_rho": mx("spearman_rho_sample"),
        "max_dot_overlap_within_3px_used": mx("our_dots_within_3px_used"),
        "max_surface_spearman_rho": mx("surface_spearman_rho"),
        "max_surface_top_N_within_3px": mx("surface_top_N_within_3px"),
        "results": sorted(rows, key=lambda r: -r.get("our_dots_within_3px_used", -1)),
    }
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", required=True)
    ap.add_argument("--registry", required=True)
    ap.add_argument("--sample", default="/tmp/gems53-data/sample_submission.tif")
    ap.add_argument("--surface", default=None, help="optional .npy pre-placement surface (NaN outside footprint)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with rasterio.open(args.sample) as src:
        footprint = np.isfinite(src.read(1))
    surface = np.load(args.surface) if args.surface else None
    receipt = check(Path(args.ours), Path(args.registry), footprint, surface)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(receipt, indent=2))
    print(json.dumps({k: v for k, v in receipt.items() if k != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
