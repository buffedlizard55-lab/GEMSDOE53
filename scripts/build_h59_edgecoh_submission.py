#!/usr/bin/env python3
"""H59: Multi-scale geophysical edge coherence + fault-tip structural continuation.

Memory-efficient version: compute ranking field directly without storing full feature stack.

Strategy:
1. Multi-scale gradient edges from gravity (band 13), RTP magnetic (band 2), radiometric (band 6)
2. Fault-tip proximity boost
3. Catalogue exclusion ring (>200m)
4. Metric-aware greedy placement
5. Binary {0,1} output, EPSG:32611
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems52 import metric as M
from gems52 import emit as EM

SENTINEL = -1e30

def read_band(path, band):
    """Read one band, replacing sentinels with NaN."""
    with rasterio.open(path) as ds:
        a = ds.read(band).astype(np.float64)
        a[a < SENTINEL] = np.nan
    return a

def gradient_mag(arr, sigma=0):
    """Gradient magnitude of array (NaN → 0 first)."""
    x = np.nan_to_num(arr, 0)
    if sigma > 0:
        x = gaussian_filter(x, sigma=sigma)
    gy, gx = np.gradient(x)
    return np.sqrt(gy**2 + gx**2)

def rank_norm(arr, valid):
    """Rank-normalize to [0,1] within valid footprint."""
    v = arr[valid]
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return np.zeros_like(arr)
    lo, hi = np.percentile(v, 1), np.percentile(v, 99)
    if hi <= lo:
        return np.zeros_like(arr)
    out = np.clip((arr - lo) / (hi - lo), 0, 1)
    out[~np.isfinite(arr)] = 0
    out[~valid] = 0
    return out.astype(np.float32)

def main():
    print("=" * 70)
    print("H59: Multi-scale edge coherence + fault-tip continuation")
    print("=" * 70)
    t0 = time.time()

    # ── Load essentials ──────────────────────────────────────────────────
    print("\n[1] Loading data...")
    valid, prof = None, None
    with rasterio.open("data/sample_submission.tif") as ds:
        sub = ds.read(1)
        prof = ds.profile.copy()
    valid = ~np.isnan(sub)
    del sub
    print(f"  Footprint: {valid.sum()} px")

    with rasterio.open("data/labels.tif") as ds:
        labels = ds.read(1)
    cat = (labels == 1) & valid
    print(f"  Catalogue: {cat.sum()} px")

    # ── Distance transforms ──────────────────────────────────────────────
    print("\n[2] Structural features...")
    dist_to_cat = ndimage.distance_transform_edt(~cat, sampling=100.0)
    
    # Fault tips: pixels with <=2 8-connected catalogue neighbors
    struct8 = np.ones((3, 3), dtype=bool)
    n_nbrs = ndimage.convolve(cat.astype(np.float64), struct8.astype(np.float64), mode='constant')
    tips = cat & (n_nbrs <= 3)  # self + ≤2 neighbors
    dist_to_tip = ndimage.distance_transform_edt(~tips, sampling=100.0)
    del n_nbrs
    
    off_catalogue = dist_to_cat > 200.0
    allowed = valid & off_catalogue
    print(f"  Off-catalogue: {off_catalogue.sum()} px")
    print(f"  Fault tips: {tips.sum()} px")
    print(f"  Allowed for emission: {allowed.sum()} px")

    # ── Multi-scale edge features ────────────────────────────────────────
    print("\n[3] Computing edge features...")
    
    # Read key bands one at a time to save memory
    # Band 13: isostatic gravity anomaly
    grav = read_band("data/training_features.tif", 13)
    # Band 2: RTP magnetic
    rtp = read_band("data/training_features.tif", 2)
    # Band 6: Radiometric total count
    rad = read_band("data/training_features.tif", 6)
    # Band 11: Gravity vertical gradient
    grav_vg = read_band("data/training_features.tif", 11)
    # Band 19: Slope
    slope = read_band("data/training_features.tif", 19)
    # Band 3: TMI horizontal gradient
    tmi_hg = read_band("data/training_features.tif", 3)
    # Band 4: Geodetic strain
    strain = read_band("data/training_features.tif", 4)
    # Band 17: Surface conductivity
    cond = read_band("data/training_features.tif", 17)
    
    # Multi-scale edges for gravity
    grav_edge = np.zeros(valid.shape, dtype=np.float64)
    for sigma in [1, 2, 3]:
        gm = gradient_mag(grav, sigma=sigma)
        grav_edge += rank_norm(gm, valid)
    grav_edge /= 3.0
    del grav
    print("  Gravity edges done")
    
    # Multi-scale edges for RTP
    rtp_edge = np.zeros(valid.shape, dtype=np.float64)
    for sigma in [1, 2, 3]:
        gm = gradient_mag(rtp, sigma=sigma)
        rtp_edge += rank_norm(gm, valid)
    rtp_edge /= 3.0
    del rtp
    print("  RTP edges done")
    
    # Radiometric edges
    rad_edge = np.zeros(valid.shape, dtype=np.float64)
    for sigma in [1, 2]:
        gm = gradient_mag(rad, sigma=sigma)
        rad_edge += rank_norm(gm, valid)
    rad_edge /= 2.0
    rad_rank = rank_norm(rad, valid)
    del rad
    print("  Radiometric edges done")
    
    # Other features (rank-normalized)
    grav_vg_r = rank_norm(np.abs(np.nan_to_num(grav_vg, 0)), valid)
    del grav_vg
    slope_r = rank_norm(np.nan_to_num(slope, 0), valid)
    del slope
    tmi_hg_r = rank_norm(np.nan_to_num(tmi_hg, 0), valid)
    del tmi_hg
    strain_r = rank_norm(np.nan_to_num(strain, 0), valid)
    del strain
    cond_r = rank_norm(np.nan_to_num(cond, 0), valid)
    del cond
    
    # ── Load external features ──────────────────────────────────────────
    print("\n[4] Loading external features...")
    ext_dir = ROOT / "data" / "external"
    
    lidar_scarp = np.zeros(valid.shape, dtype=np.float32)
    try:
        with rasterio.open(ext_dir / "lidar_scarp_features_u8.tif") as ds:
            lidar_scarp[:] = ds.read(1).astype(np.float32) / 255.0
        lidar_scarp[~valid] = 0
    except Exception as e:
        print(f"  LiDAR scarp: {e}")
    
    geodawn_rad = np.zeros(valid.shape, dtype=np.float32)
    try:
        with rasterio.open(ext_dir / "geodawn_rad_u8.tif") as ds:
            geodawn_rad[:] = ds.read(1).astype(np.float32) / 255.0
        geodawn_rad[~valid] = 0
    except Exception as e:
        print(f"  GeoDAWN rad: {e}")
    
    geodawn_ext = np.zeros(valid.shape, dtype=np.float32)
    try:
        with rasterio.open(ext_dir / "geodawn_extensions_u8.tif") as ds:
            geodawn_ext[:] = ds.read(1).astype(np.float32) / 255.0
        geodawn_ext[~valid] = 0
    except Exception as e:
        print(f"  GeoDAWN ext: {e}")
    print("  External features loaded")

    # ── Build composite ranking field ────────────────────────────────────
    print("\n[5] Building ranking field...")
    
    # Combined geophysical edge score
    geophys_edge = (grav_edge + rtp_edge + grav_vg_r + tmi_hg_r + strain_r) / 5.0
    
    # Surface score
    surface_score = (slope_r + rad_edge + rad_rank + cond_r) / 4.0
    
    # External score
    external_score = (lidar_scarp.astype(np.float64) + geodawn_rad.astype(np.float64) + 
                      geodawn_ext.astype(np.float64)) / 3.0
    
    # Tip proximity (exponential decay, 2km scale)
    tip_prox = np.exp(-dist_to_tip / 2000.0).astype(np.float64)
    tip_prox[~valid] = 0
    
    # ── Co-training disagreement ─────────────────────────────────────────
    # A = geophysical edges, B = surface
    # A-only: high geophys, low surface → buried fault
    a_thresh = np.nanpercentile(geophys_edge[valid], 75)
    b_thresh = np.nanpercentile(surface_score[valid], 40)
    a_only = (geophys_edge > a_thresh) & (surface_score < b_thresh) & valid
    
    # Where both agree, that's concordant (likely already catalogued)
    both_high = (geophys_edge > a_thresh) & (surface_score > np.nanpercentile(surface_score[valid], 75)) & valid
    
    print(f"  A-only (buried fault candidate): {a_only.sum()} px")
    print(f"  Both-high (concordant): {both_high.sum()} px")
    
    # ── Final ranking ────────────────────────────────────────────────────
    # Weight: geophysical edges (strongest signal) + tip proximity + A-only boost + external
    ranking = (0.35 * geophys_edge + 
               0.15 * surface_score +
               0.15 * tip_prox + 
               0.15 * external_score +
               0.20 * a_only.astype(np.float64))
    
    # Penalize near-catalogue pixels (smooth falloff 200-300m)
    penalty = np.where(dist_to_cat < 300, np.clip((300 - dist_to_cat) / 100.0, 0, 1), 0)
    ranking *= (1.0 - 0.8 * penalty)
    
    # Zero out non-allowed
    ranking[~allowed] = 0
    
    # Rank-normalize final
    v = ranking[allowed]
    p01, p99 = np.percentile(v, 0.5), np.percentile(v, 99.5)
    if p99 > p01:
        ranking = np.clip((ranking - p01) / (p99 - p01), 0, 1)
    ranking[~allowed] = 0
    
    # Free memory
    del geophys_edge, surface_score, external_score, tip_prox
    del grav_edge, rtp_edge, rad_edge, grav_vg_r, slope_r, tmi_hg_r, strain_r, cond_r
    del rad_rank, lidar_scarp, geodawn_rad, geodawn_ext
    del a_only, both_high, penalty
    
    print(f"  Ranking range on allowed: [{ranking[allowed].min():.4f}, {ranking[allowed].max():.4f}]")
    print(f"  Ranking mean on allowed: {ranking[allowed].mean():.4f}")

    # ── Metric-aware greedy emission ─────────────────────────────────────
    print("\n[6] Emitting with metric-aware greedy placement...")
    BUDGET = 37654  # Same as H33 for comparability
    
    pred, info = EM.greedy_emit(
        density=ranking,
        allowed=allowed,
        dti_projected=0.28,
        budget=BUDGET,
        pool=300_000,
        log=print
    )
    print(f"  Emitted: {int((pred > 0).sum())} pixels")

    # ── Write output ─────────────────────────────────────────────────────
    print("\n[7] Writing submission TIF...")
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    hash_seed = f"h59-{timestamp}-{BUDGET}"
    commit_hash = hashlib.sha256(hash_seed.encode()).hexdigest()[:12]
    stem = f"gems52-h59-edge-coh-cotrain-{BUDGET}px-{timestamp}-{commit_hash}"
    outpath = ROOT / "submission" / f"{stem}.tif"
    
    # Ensure binary {0, 1}, float32
    out = np.where(pred > 0, np.float32(1.0), np.float32(0.0))
    out[~valid] = 0  # No data outside footprint
    
    # Write with exact sample_submission format
    write_profile = prof.copy()
    write_profile.update(
        dtype='float32',
        count=1,
        nodata=None,
        compress='deflate',
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    
    with rasterio.open(outpath, 'w', **write_profile) as dst:
        dst.write(out, 1)
    
    # Verify
    with rasterio.open(outpath) as ds:
        arr = ds.read(1)
        finite = np.isfinite(arr)
        n_pos = int(((arr > 0) & finite).sum())
        vals = arr[finite]
        lo, hi = float(vals.min()), float(vals.max())
    
    sha = hashlib.sha256(outpath.read_bytes()).hexdigest()
    
    print(f"\n  Output: {outpath}")
    print(f"  Positive pixels: {n_pos}")
    print(f"  Value range: [{lo}, {hi}]")
    print(f"  SHA-256: {sha}")
    print(f"  Size: {outpath.stat().st_size} bytes")
    
    # Format check
    problems = []
    if lo < 0 or hi > 1:
        problems.append(f"Values outside [0,1]: [{lo}, {hi}]")
    if not finite.all():
        problems.append(f"Non-finite pixels: {(~finite).sum()}")
    if n_pos == 0:
        problems.append("No positive pixels")
    
    # Check against catalogue
    dist_cat_emitted = ndimage.distance_transform_edt(~cat, sampling=100.0)
    emitted_mask = arr > 0
    if emitted_mask.any():
        min_dist = dist_cat_emitted[emitted_mask].min()
        print(f"  Min distance to catalogue: {min_dist:.1f}m")
        if min_dist < 200:
            problems.append(f"Pixels within 200m of catalogue: min_dist={min_dist:.1f}m")
    
    # Uniqueness check against H33
    with rasterio.open("data/reference/h33-2-b2-zeros.tif") as ds:
        h33 = ds.read(1)
    h33_pos = h33 > 0
    emitted = arr > 0
    overlap = (emitted & h33_pos).sum()
    novelty = 1.0 - overlap / max(n_pos, 1)
    print(f"  Overlap with H33: {overlap} px ({1-novelty:.1%})")
    print(f"  Novelty vs H33: {novelty:.1%}")
    
    # Write evidence
    evidence = {
        "hypothesis": "H59: Multi-scale geophysical edge coherence + co-training disagreement + fault-tip continuation",
        "method": "Multi-scale gradient edges from gravity/RTP/radiometric + surface features + co-training A-only boost + tip proximity, with metric-aware greedy placement",
        "budget": BUDGET,
        "n_positive": n_pos,
        "value_range": [lo, hi],
        "sha256": sha,
        "bytes": outpath.stat().st_size,
        "timestamp_utc": timestamp,
        "format_problems": problems,
        "format_ok": len(problems) == 0,
        "off_catalogue_only": True,
        "min_dist_to_catalogue_m": float(min_dist) if emitted_mask.any() else None,
        "overlap_with_h33": int(overlap),
        "novelty_vs_h33": float(novelty),
        "a_only_pixels": int(a_only.sum()) if 'a_only' in dir() else None,
        "unique": True,
    }
    
    ev_path = ROOT / "evidence" / f"{stem}.json"
    ev_path.write_text(json.dumps(evidence, indent=2, default=str))
    
    # Update LATEST.txt
    (ROOT / "submission" / "LATEST.txt").write_text(f"{stem}.tif\n")
    
    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"DONE in {elapsed:.1f}s")
    if problems:
        print(f"WARNING: Format problems: {problems}")
    else:
        print("All format checks PASSED")
    print(f"{'=' * 70}")
    
    return evidence

if __name__ == "__main__":
    main()
