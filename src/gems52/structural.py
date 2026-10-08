"""R2 signed normal persistence: core-data-only, label-free feature construction.

New mechanism: signed gravity/cover gradient anti-alignment across scales, and
cover-conditioned orientation disagreement with the surface. These features are
NOT independent measurements: the basement model may incorporate gravity.
All numerical units of derivatives are per metre on the template's 100 m grid;
the raw band's units are those of the provided data (not invented here).

Gaussian filters use normalized convolution, not zero-filled derivatives at a
footprint boundary. Maximum support is 36 pixels, recorded in the manifest.
Training statistics and histogram bins are fitted inside each training fold by
sklearn; no labels or test normalization are consulted in these transforms.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

A_BANDS = [i for i in range(1, 20) if i not in (12, 19)]
B_BANDS = [12, 19]
SCALES = (1, 3, 8)
SUPPORT_PX = 36


def smooth(a, valid, sigma):
    """Normalized Gaussian smoothing. A constant field stays constant at holes."""
    a = np.asarray(a, np.float32)
    good = np.asarray(valid, bool) & np.isfinite(a) & (a > -1e38)
    num = ndi.gaussian_filter(np.where(good, a, 0), sigma, mode="reflect", truncate=4.0)
    den = ndi.gaussian_filter(good.astype(np.float32), sigma, mode="reflect", truncate=4.0)
    return np.divide(num, den, out=np.zeros_like(num), where=den > 1e-8)


def normals(a, valid, sigma):
    s = smooth(a, valid, sigma)
    gy, gx = np.gradient(s, 100.0, 100.0)
    mag = np.hypot(gx, gy)
    return gx, gy, mag, s


def paired_scarp_profile(elevation, valid, sigma=2.0, offset_px=2.0, tile_rows=256):
    """Measure paired DEM flank slopes along the local uphill normal.

    This R3-H1 transform is intentionally surface-only: it samples a smoothed
    detrended-elevation profile at +/- ``offset_px`` (default 200 m) around each
    pixel, along the local DEM-gradient normal. The output is two dimensionless
    features: signed same-direction flank-slope concordance and signed left/right
    flank asymmetry. Samples are bilinear and computed in row tiles to bound peak
    memory on the 12 Mpixel competition grid. The input footprint must be eroded
    beyond the profile/smoothing support before these values are used for fitting.

    The transform is a geomorphic hypothesis, not proof of a fault; roads, fan
    margins, drainage, lithologic contacts and DEM artifacts can make similar
    profiles.
    """
    elev = np.asarray(elevation, dtype=np.float32)
    valid = np.asarray(valid, dtype=bool)
    if elev.ndim != 2 or valid.shape != elev.shape:
        raise ValueError("elevation and valid must be same-shaped 2-D arrays")
    if min(elev.shape) < 3:
        raise ValueError("profile transform needs at least a 3x3 grid")
    if not np.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma must be finite and positive")
    if not np.isfinite(offset_px) or offset_px <= 0:
        raise ValueError("offset_px must be finite and positive")
    if not isinstance(tile_rows, int) or tile_rows <= 0:
        raise ValueError("tile_rows must be a positive integer")

    field = smooth(elev, valid, sigma)
    gy, gx = np.gradient(field, 100.0, 100.0)
    magnitude = np.hypot(gx, gy)
    nx = np.divide(gx, magnitude, out=np.zeros_like(gx), where=magnitude > 1e-10)
    ny = np.divide(gy, magnitude, out=np.zeros_like(gy), where=magnitude > 1e-10)
    concordance = np.zeros(elev.shape, dtype=np.float32)
    asymmetry = np.zeros(elev.shape, dtype=np.float32)
    height, width = elev.shape
    columns = np.arange(width, dtype=np.float32)[None, :]
    distance_m = float(offset_px) * 100.0
    epsilon = 1e-12

    for y0 in range(0, height, tile_rows):
        y1 = min(height, y0 + tile_rows)
        rows = np.arange(y0, y1, dtype=np.float32)[:, None]
        tile_shape = (y1 - y0, width)
        coords = np.empty((2, *tile_shape), dtype=np.float32)
        samples = []
        for sign in (-1.0, 1.0):
            coords[0] = rows + sign * float(offset_px) * ny[y0:y1]
            coords[1] = columns + sign * float(offset_px) * nx[y0:y1]
            samples.append(ndi.map_coordinates(field, coords, order=1, mode="nearest", prefilter=False))
        left = (field[y0:y1] - samples[0]) / distance_m
        right = (samples[1] - field[y0:y1]) / distance_m
        left_abs, right_abs = np.abs(left), np.abs(right)
        denom = left_abs + right_abs
        same_direction = np.sign(left * right)
        good = denom > epsilon
        pair = np.zeros_like(denom, dtype=np.float32)
        asym = np.zeros_like(denom, dtype=np.float32)
        pair[good] = (same_direction[good] * (2.0 * np.minimum(left_abs[good], right_abs[good]) / denom[good])).astype(np.float32)
        asym[good] = (same_direction[good] * ((right_abs[good] - left_abs[good]) / denom[good])).astype(np.float32)
        concordance[y0:y1] = np.clip(pair, -1.0, 1.0)
        asymmetry[y0:y1] = np.clip(asym, -1.0, 1.0)

    concordance[~valid] = 0.0
    asymmetry[~valid] = 0.0
    if not np.isfinite(concordance[valid]).all() or not np.isfinite(asymmetry[valid]).all():
        raise ValueError("paired profile transform produced non-finite values")
    return concordance, asymmetry


def cosine(ax, ay, bx, by):
    """Signed normal dot product; undefined flat-field direction maps to 0."""
    den = np.hypot(ax, ay) * np.hypot(bx, by)
    return np.clip(np.divide(ax * bx + ay * by, den, out=np.zeros_like(den), where=den > 1e-12), -1, 1)


def coherence(gx, gy, valid, sigma=3):
    xx = smooth(gx * gx, valid, sigma)
    yy = smooth(gy * gy, valid, sigma)
    xy = smooth(gx * gy, valid, sigma)
    return np.clip(np.sqrt((xx - yy) ** 2 + 4 * xy ** 2) / (xx + yy + 1e-12), 0, 1)


def hessian(s):
    """Signed principal curvatures of a smoothed DEM, not absolute ridge scores."""
    gy, gx = np.gradient(s, 100.0, 100.0)
    yy, yx = np.gradient(gy, 100.0, 100.0)
    xy, xx = np.gradient(gx, 100.0, 100.0)
    off = (xy + yx) * 0.5
    root = np.sqrt((xx - yy) ** 2 + 4 * off ** 2)
    return (xx + yy + root) * 0.5, (xx + yy - root) * 0.5


def normal_profile(elevation, valid, sigma=3.0, offset_px=3.0, tangent_px=3.0, offsets_px=None):
    """Local-normal DEM profile features for a paired-shoulder hypothesis.

    The smoothed DEM gradient defines an unoriented local normal (its sign is fixed by
    increasing elevation). Elevations at +/- offset are bilinearly sampled along it. We
    retain the signed cross-normal step, balance of the two center-to-flank changes, and
    persistence of the step while sampling the local tangent. This is a profile transform,
    not a fault probability; roads, drainage and lithologic edges remain confounders.
    """
    from scipy.ndimage import map_coordinates

    gx, gy, magnitude, smooth_dem = normals(elevation, valid, sigma)
    ux = np.divide(gx, magnitude, out=np.zeros_like(gx), where=magnitude > 1e-8)
    uy = np.divide(gy, magnitude, out=np.zeros_like(gy), where=magnitude > 1e-8)
    h, w = elevation.shape
    yy, xx = np.indices((h, w), dtype=np.float32)

    def sample(source, y, x):
        coords = np.stack((y.astype(np.float32, copy=False), x.astype(np.float32, copy=False)))
        return map_coordinates(source, coords, order=1, mode="nearest", prefilter=False)

    offsets = tuple(float(x) for x in (offsets_px if offsets_px is not None else (offset_px,)))
    if not offsets or any(x <= 0 for x in offsets):
        raise ValueError("normal profile offsets must be positive")
    tx, ty = -uy, ux
    result = []
    for distance_px in offsets:
        z_plus = sample(smooth_dem, yy + distance_px * uy, xx + distance_px * ux)
        z_minus = sample(smooth_dem, yy - distance_px * uy, xx - distance_px * ux)
        # Remove the local first-order plane so a uniform hillslope does not score as a break.
        linear_change = distance_px * 100.0 * magnitude
        signed_step = z_plus - z_minus - 2.0 * linear_change
        plus_flank = z_plus - smooth_dem - linear_change
        minus_flank = smooth_dem - z_minus - linear_change
        pair_denominator = np.abs(plus_flank) + np.abs(minus_flank)
        pair_balance = np.divide(np.abs(plus_flank - minus_flank), pair_denominator,
                                 out=np.zeros_like(pair_denominator), where=pair_denominator > 1e-3)
        paired_flank = np.minimum(np.abs(plus_flank), np.abs(minus_flank))

        # A single isolated break is downweighted by averaging its detrended step along strike.
        persistence = np.abs(signed_step).astype(np.float32)
        for tangent_distance in (1.0, tangent_px):
            persistence += (np.abs(sample(signed_step, yy + tangent_distance * ty, xx + tangent_distance * tx)) +
                            np.abs(sample(signed_step, yy - tangent_distance * ty, xx - tangent_distance * tx))) * 0.5
        persistence /= 3.0
        result.extend((signed_step, paired_flank, pair_balance, persistence))
    for array in result:
        array[~valid] = 0.0
    return result


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_array(path, a):
    """Atomic, flushed array write with an independent numerical reread.

    Avoid unverified array.tofile/mmap assumptions in a virtualized filesystem.
    Filesystem defects must be caught before model training, not normalized away.
    """
    path = Path(path)
    tmp = path.with_suffix('.partial')
    with tmp.open('wb') as fh:
        np.lib.format.write_array_header_1_0(fh, dict(descr=np.lib.format.dtype_to_descr(a.dtype), fortran_order=False, shape=a.shape))
        data = memoryview(np.ascontiguousarray(a)).cast('B')
        for start in range(0, len(data), 1 << 20):
            fh.write(data[start:start + (1 << 20)])
        fh.flush()
        import os
        os.fsync(fh.fileno())
    if not np.array_equal(np.load(tmp), a, equal_nan=True):
        raise IOError(f'array write/reread mismatch: {path}')
    tmp.replace(path)


def build(features="data/training_features.tif", sample="data/sample_submission.tif", dest="work/r2/features", log=print):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with rasterio.open(sample) as ref:
        a = ref.read(1, masked=True)
        valid = ~np.ma.getmaskarray(a) & np.isfinite(a.data) & (a.data > -1e38)
        template = dict(shape=[ref.height, ref.width], crs=str(ref.crs), transform=list(ref.transform)[:6])
    with rasterio.open(features) as src:
        if src.count != 19 or [src.height, src.width] != template["shape"] or str(src.crs) != template["crs"] or list(src.transform)[:6] != template["transform"]:
            raise ValueError("training raster does not match the measured 19-band template")
        for i in range(1, src.count + 1):
            a = src.read(i)
            valid &= np.isfinite(a) & (a > -1e38)
        # Keep a separate input footprint; eroding by full support avoids boundary-only detections.
        save_array(dest / "input_footprint.npy", valid)
        eligible = ndi.distance_transform_edt(np.pad(valid, 1, constant_values=False))[1:-1, 1:-1] > SUPPORT_PX
        flat_idx = np.flatnonzero(eligible.ravel())
        save_array(dest / "valid.npy", eligible)
        save_array(dest / "flat_idx.npy", flat_idx)
        names, view_a, view_b, h2_features, structural_features, raw, cross, profile = [], [], [], [], [], [], [], []
        file_hashes = {}

        def put(name, values, view):
            v = np.asarray(values, np.float32).ravel()[flat_idx]
            if not np.isfinite(v).all():
                raise ValueError(f"nonfinite feature inside eligible footprint: {name}")
            save_array(dest / (name + ".npy"), v)
            file_hashes[name] = digest(dest / (name + ".npy"))
            names.append(name)
            if view == "A":
                view_a.append(name)
            elif view == "B":
                view_b.append(name)
            elif view == "H2":
                h2_features.append(name)
            elif view == "H55":
                profile.append(name)
            else:
                cross.append(name)
            if view not in ("H2", "H55"):
                structural_features.append(name)
            log(f"feature {len(names):02d} {name}", flush=True)

        def read(i):
            a = src.read(i).astype(np.float32)
            a[~valid] = np.nan
            return a

        for i in range(1, src.count + 1):
            name = f"raw_band_{i:02d}"
            put(name, read(i), "A" if i in A_BANDS else "B")
            raw.append(name)

        grav, cover, rtp = read(13), read(15), read(2)
        saved = {}
        for sigma in SCALES:
            gx, gy, gm, _ = normals(grav, valid, sigma)
            dx, dy, dm, _ = normals(cover, valid, sigma)
            put(f"A_gravity_grad_{sigma}", gm, "A")
            put(f"A_cover_grad_{sigma}", dm, "A")
            anti = -cosine(gx, gy, dx, dy)
            put(f"A_gravity_cover_signed_{sigma}", anti, "A")
            saved[sigma] = (gx, gy, dx, dy)
        for a, b in ((1, 3), (3, 8)):
            ax, ay, adx, ady = saved[a]
            bx, by, bdx, bdy = saved[b]
            put(f"A_gravity_persistence_{a}_{b}", cosine(ax, ay, bx, by), "A")
            put(f"A_cover_persistence_{a}_{b}", cosine(adx, ady, bdx, bdy), "A")
        gx, gy, dx, dy = saved[3]
        gcoh = coherence(gx, gy, valid)
        put("A_gravity_coherence", gcoh, "A")
        put("A_cover_coherence", coherence(dx, dy, valid), "A")
        anti3 = -cosine(gx, gy, dx, dy)
        # Copy the few channels used after clearing the large scale cache.
        gx, gy, dx, dy = (x.copy() for x in (gx, gy, dx, dy))
        saved.clear()
        for sigma in (1, 3):
            mx, my, mm, _ = normals(rtp, valid, sigma)
            put(f"A_RTP_grad_{sigma}", mm, "A")
        mx, my = mx.copy(), my.copy()
        del grav, rtp

        elev, slope = read(12), read(19)
        for sigma in SCALES:
            zx, zy, zm, zs = normals(elev, valid, sigma)
            put(f"B_elevation_grad_{sigma}", zm, "B")
            if sigma in (1, 3):
                ep, em = hessian(zs)
                put(f"B_curvature_plus_{sigma}", ep, "B")
                put(f"B_curvature_minus_{sigma}", em, "B")
                put(f"B_curvature_trace_{sigma}", ep + em, "B")
            if sigma == 3:
                surf_x, surf_y = zx.copy(), zy.copy()
                put("B_surface_coherence", coherence(zx, zy, valid), "B")
        for sigma in (1, 3):
            sx, sy, sm, _ = normals(slope, valid, sigma)
            put(f"B_slope_grad_{sigma}", sm, "B")
        for a, name, floor in ((elev, "elevation", 1.0), (slope, "slope", 0.1)):
            mu = smooth(a, valid, 8)
            # The variance support is the same 32-pixel Gaussian; no smoothing of an already smoothed residual.
            second = smooth(a * a, valid, 8)
            sd = np.sqrt(np.maximum(second - mu * mu, 0))
            residual = np.divide(a - mu, sd + floor)
            put(f"B_{name}_local_residual", residual, "B")
            put(f"B_{name}_local_sd", sd, "B")

        # R3-H1: paired flank geometry is kept out of the old view_B and
        # structural_contrast definitions so their baselines remain comparable.
        pair_concordance, shoulder_asymmetry = paired_scarp_profile(elev, valid, sigma=2.0, offset_px=2.0)
        put("B_paired_profile_concordance_200m", pair_concordance, "H2")
        put("B_paired_shoulder_asymmetry_200m", shoulder_asymmetry, "H2")
        del pair_concordance, shoulder_asymmetry

        # H55 paired-normal scales remain a separate, optional view; neither profile
        # family leaks into the original view_B or structural_contrast baseline.
        suffixes = ("normal_signed_step", "paired_flank_contrast",
                    "paired_flank_asymmetry", "tangent_step_persistence")
        for offset in (1, 2, 3, 4, 6):
            scale_features = normal_profile(elev, valid, offset_px=offset)
            for suffix, values in zip(suffixes, scale_features):
                put(f"H55_{suffix}_{offset}px", values, "H55")
            del scale_features, values

        put("C_gravity_surface_direction", cosine(gx, gy, surf_x, surf_y), "C")
        put("C_cover_surface_direction", cosine(dx, dy, surf_x, surf_y), "C")
        put("C_magnetic_surface_direction", np.abs(cosine(mx, my, surf_x, surf_y)), "C")
        logcover = np.log1p(np.maximum(cover, 0))
        put("C_signed_cover_surface_silence", np.maximum(anti3, 0) * logcover / (1 + np.abs(slope)), "C")
        put("C_cover_persistent_gravity", gcoh * logcover, "C")

    manifest = dict(version="h55-profile-v1", template=template,
                    feature_names=names, view_A=view_a, view_B=view_b,
                    view_B_paired_shoulder=view_b + h2_features, h2_features=h2_features,
                    view_B_h55=view_b + profile, raw_fusion=raw,
                    structural_contrast=structural_features,
                    structural_contrast_h55=structural_features + profile,
                    cross_features=cross, h55_profile_features=profile,
                    feature_sha256=file_hashes,
                    input_footprint_px=int(valid.sum()), eligible_px=int(eligible.sum()),
                    support_px=SUPPORT_PX, feature_scales_px=list(SCALES),
                    r3_h1_profile=dict(band=12, context_band=19, gaussian_sigma_px=2.0,
                                       offset_px=2.0, support_px=10, external_data_used=False),
                    inputs={"features_sha256": digest(features), "sample_sha256": digest(sample)},
                    external_data_used=False, radiometric_bands_present=False,
                    caveat="Catalogue-zero is not verified fault absence; gravity and modelled depth are not independent evidence; R3 paired-flank and H55 paired-normal features are geomorphic hypotheses, not fault labels.")
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class FeatureStore:
    """Verified read-only column arrays; gather one model chunk at a time.

    Feature columns are loaded on demand. Ordinary array loads avoid unverified
    memmap behavior on the sandbox filesystem; the available feature set depends
    on which preregistered hypothesis extensions were built.
    """
    def __init__(self, directory="work/r2/features"):
        self.directory = Path(directory)
        self.manifest = json.loads((self.directory / "manifest.json").read_text())
        self.flat_idx = np.load(self.directory / "flat_idx.npy", allow_pickle=False)
        self.valid = np.load(self.directory / "valid.npy")
        if not np.array_equal(self.flat_idx, np.flatnonzero(self.valid.ravel())):
            raise ValueError("feature index mapping corrupted; rebuild features")
        self.inverse = np.full(self.valid.size, -1, dtype=np.int32)
        self.inverse[self.flat_idx] = np.arange(self.flat_idx.size)
        self.columns = {}

    def gather(self, flat_rows, names):
        rows = self.inverse[np.asarray(flat_rows)]
        if (rows < 0).any():
            raise ValueError("requested row outside eligible feature footprint")
        out = np.empty((len(rows), len(names)), np.float32)
        for j, name in enumerate(names):
            if name not in self.columns:
                path = self.directory / (name + ".npy")
                if digest(path) != self.manifest["feature_sha256"][name]:
                    raise ValueError(f"feature byte-integrity failure: {name}")
                self.columns[name] = np.load(path, allow_pickle=False)
            out[:, j] = self.columns[name][rows]
        return out

    def feature_grid(self, name):
        if name not in self.columns:
            path = self.directory / (name + ".npy")
            if digest(path) != self.manifest["feature_sha256"][name]:
                raise ValueError(f"feature byte-integrity failure: {name}")
            self.columns[name] = np.load(path, allow_pickle=False)
        out = np.zeros(self.valid.size, np.float32)
        out[self.flat_idx] = self.columns[name]
        return out.reshape(self.valid.shape)
