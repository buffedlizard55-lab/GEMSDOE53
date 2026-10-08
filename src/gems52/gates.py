"""On-disk format and decoded-prediction uniqueness gates.

Range checks use RAW raster values, not NaN-skipping min/max. The all-finite
policy is our compatibility precaution; the public specification explicitly
allows null/NaN outside the footprint, so NaN is not claimed to be a proven
portal defect. Source-grid metadata must exactly match the reference even in
small test fixtures. No fixture-grid bypass of CRS/transform comparison.

All supplied priors are processed: the old `priors[:top]` silently checked only
eight files. Continuous predictions are compared numerically and by >=0.5
support; a dense low-confidence field is not falsely treated as a binary
proposal everywhere it is >0. Binary priors use their exact positive support.
The 20% support-novelty condition is stronger than simply having a new hash.
An inventory's finite scope must be disclosed; this cannot prove uniqueness
against inaccessible/private/unlinked artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio

from .grid import SHAPE, TRANSFORM


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_raster(path):
    with rasterio.open(path) as src:
        if src.count != 1:
            raise ValueError(f"prior has {src.count} bands, not a single prediction band")
        return src.read(1)


def format_report(path, sample, epsg=32611, cell=100.0, footprint=None):
    path, sample = Path(path), Path(sample)
    out = dict(path=str(path), bytes=path.stat().st_size, sha256=sha256(path))
    problems = []
    with rasterio.open(path) as src, rasterio.open(sample) as ref:
        a = src.read(1)
        out.update(bands=src.count, dtype=src.dtypes[0], crs=str(src.crs), width=src.width, height=src.height,
                   bounds=list(src.bounds), ref_bounds=list(ref.bounds), transform=list(src.transform)[:6],
                   nodata=float(src.nodata) if src.nodata is not None and np.isfinite(src.nodata) else str(src.nodata) if src.nodata is not None else None,
                   blocksize=list(src.block_shapes[0]), fixture_grid=ref.shape != SHAPE,
                   has_validity_mask=bool((src.dataset_mask() == 0).any()))
        if src.count != 1:
            problems.append(f"{src.count} bands, must be 1")
        if src.dtypes[0] != "float32":
            problems.append(f"dtype {src.dtypes[0]}, must be float32")
        if src.shape != ref.shape:
            problems.append(f"shape {src.shape} != reference {ref.shape}")
        if src.crs != ref.crs or src.crs is None:
            problems.append(f"CRS {src.crs} != reference {ref.crs}")
        if src.transform != ref.transform:
            problems.append("transform differs from sample_submission.tif")
        if src.bounds != ref.bounds:
            problems.append(f"bounds {src.bounds} != reference {ref.bounds}")
        if ref.shape == SHAPE:
            if src.crs is None or src.crs.to_epsg() != epsg:
                problems.append(f"CRS must be EPSG:{epsg}")
            if tuple(src.transform)[:6] != TRANSFORM:
                problems.append(f"transform differs from pinned competition transform {TRANSFORM}")
            if tuple(src.res) != (cell, cell):
                problems.append(f"resolution {src.res} != {(cell, cell)}")
        finite = np.isfinite(a)
        out.update(nan_pixels=int(np.isnan(a).sum()), infinity_pixels=int(np.isinf(a).sum()), n_nan=int((~finite).sum()))
        if not finite.all():
            problems.append(f"{out['n_nan']} NaN/infinite pixels: fail our all-finite export policy (public spec permits outside-footprint NaN)")
        if finite.any():
            lo, hi = float(a[finite].min()), float(a[finite].max())
            out.update(min=lo, max=hi, mean=float(a[finite].mean()), n_nonzero=int(((a > 0) & finite).sum()), mass=float(a[finite].sum(dtype=np.float64)))
            if lo < 0 or hi > 1:
                problems.append(f"values outside [0,1]: min {lo}, max {hi}")
        else:
            problems.append("every pixel is NaN/infinite")
        if src.nodata is not None and (not np.isfinite(src.nodata) or not 0 <= src.nodata <= 1):
            problems.append("nodata tag outside all-finite [0,1] export policy")
        if footprint is not None:
            fp = np.asarray(footprint, bool)
            if fp.shape != a.shape:
                problems.append(f"footprint shape {fp.shape} != raster shape {a.shape}")
            else:
                out["mass_outside_footprint"] = int(((a > 0) & ~fp).sum())
                if out["mass_outside_footprint"]:
                    problems.append(f"{out['mass_outside_footprint']} emitted pixels outside the valid footprint")
    out.update(problems=problems, ok=not problems,
               validation_class="local on-disk template/range check; not organizer upload acceptance")
    return out


def find_priors(roots, exclude=None, *, min_bytes=1000):
    found, seen = [], set()
    for root in roots:
        if not Path(root).exists():
            continue
        for path in sorted(Path(root).rglob("*.tif")):
            # Competition *inputs* are not prior submissions.  Sweeping a root that contains them
            # (the obvious mistake is passing the repository's parent so sibling checkouts are
            # covered) reads band 1 of the 19-band feature stack as if it were somebody's answer, and
            # the "prior union" then covers more pixels than the footprint itself -- which silently
            # destroys both the novelty fraction and the not-the-union test, and in the H54 build
            # emptied the novel pool to 93 px.  Measured before this exclusion: union 5,363,764 px
            # against a 5,167,373 px footprint.  IR-52-027; regression test in tests/test_gates.py.
            sp = str(path)
            if ("data/raw" in sp or path.name == "labels.tif"
                    or path.name.startswith("sample_submission")
                    or "training_features" in sp or "/external/" in sp or "data/external" in sp):
                continue
            if exclude is not None and path.resolve() == Path(exclude).resolve():
                continue
            # ... and never a *copy* of the candidate either.  scripts/refresh_feed.py stages every
            # built raster into docs/downloads/ so the site can serve it, and docs/downloads/ is one
            # of the roots this function scans; without the basename check the file is compared
            # against itself and reports "identical-to-a-prior, novel = 0", which is the one verdict
            # that would stop a legitimate submission.  Caught by scripts/check_site.py on the H55
            # build, not by reasoning about it.  IR-52-026; regression test in tests/test_gates.py.
            if exclude is not None and path.name == Path(exclude).name:
                continue
            if path.stat().st_size < min_bytes:
                continue
            if path.resolve() not in seen:
                seen.add(path.resolve())
                found.append(path)
    return found


def canonical(a):
    # Normalize only invalid/nodata prior cells, never a valid probability.
    return np.where(np.isfinite(a) & (a >= 0) & (a <= 1), a, 0).astype('<f4')


def uniqueness_report(emitted, priors, top=None):
    """Check EVERY prior. `top` retained for compatibility but never limits checking."""
    candidate = np.asarray(emitted, np.float32)
    if candidate.ndim != 2 or not np.isfinite(candidate).all() or (candidate < 0).any() or (candidate > 1).any():
        raise ValueError("candidate must be a finite, 2D [0,1] prediction")
    new = candidate > 0
    n_new = int(new.sum())
    union = np.zeros(new.shape, bool)
    rows = []
    decoded_hash = hashlib.sha256(candidate.astype('<f4').tobytes()).hexdigest()
    for path in priors:
        try:
            with rasterio.open(path) as src:
                if src.count != 1 or src.shape != candidate.shape:
                    raise ValueError(f"not aligned single-band prediction ({src.count} bands, {src.shape})")
                old_values = canonical(src.read(1))
            binary = bool(np.isin(old_values, [0, 1]).all())
            old = old_values > 0 if binary else old_values >= 0.5
            union |= old
            inter = int((new & old).sum())
            old_count = int(old.sum())
            rows.append(dict(path=str(path), prior_px=old_count, new_px=n_new, binary=binary,
                             support_definition=">0 for binary" if binary else ">=0.5 for continuous; exact numeric equality also checked",
                             decoded_sha256=hashlib.sha256(old_values.tobytes()).hexdigest(),
                             intersection=inter, jaccard=float(inter / max(int((new | old).sum()), 1)),
                             identical=bool(np.array_equal(candidate, old_values)),
                             subset_of_prior=inter == n_new and n_new <= old_count,
                             superset_of_prior=inter == old_count and n_new >= old_count,
                             novel_vs_this=n_new - inter))
        except Exception as exc:
            rows.append(dict(path=str(path), error=f"{type(exc).__name__}: {str(exc)[:180]}"))
    novel, dropped = int((new & ~union).sum()), int((union & ~new).sum())
    fraction = novel / max(n_new, 1)
    ok = bool(priors) and n_new > 0 and not any(r.get("identical") or r.get("error") for r in rows) and fraction >= 0.2 and dropped > 0
    pattern_unique = bool(priors) and n_new > 0 and not any(r.get('identical') or r.get('error') for r in rows)
    literal_union = novel == 0 and dropped == 0
    return dict(n_priors_checked=len(rows), per_prior=rows, candidate_decoded_sha256=decoded_hash,
                canonical_pattern_unique=pattern_unique,
                equals_literal_prior_union=literal_union,
                research_publication_ok=pattern_unique and not literal_union,
                support_novelty_gate_ok=ok,
                gate_correction='Original >=20% support novelty retained as a FAILED diagnostic, not silently waived for slot promotion. A dense density-probe covers almost the entire survey and ignorance-mass rasters are not fault probabilities, so all-prior union support novelty is not decoded-pattern uniqueness. Fresh model inference may be released research-only if canonical-distinct and not a literal union.',
                union_px=int(union.sum()), novel_vs_all_priors=novel, novel_fraction=fraction, prior_px_dropped=dropped,
                relation_to_union="strictly-novel-and-selective" if ok else "identical-to-a-prior" if any(r.get("identical") for r in rows) else
                                  "subset-of-union" if novel == 0 else "insufficient-novelty-or-incomplete-audit",
                ok=ok, top_argument_ignored=top is not None,
                rule="distinct decoded values from every supplied prior, >=20% new support against binary/>=0.5 continuous proposal union, and selective prior-pixel removal",
                scope="Only the supplied, aligned accessible inventory; not a proof against all private/unlinked submissions")


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
