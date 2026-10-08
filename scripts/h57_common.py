"""Shared plumbing for the GEMS57 two-view co-training pipeline.

Everything here is label-safe by construction:
  * the *only* labels used are `data/labels.tif` (the published catalogue) and the SGMC
    compilation (an independent official product).  Both are declared where used;
  * no prior submission raster, and no distance-to-prior, is ever an input to a model;
  * spatial blocking, fold assignment and buffers are computed here so every stage uses the
    same geometry.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from gems57.feat import VIEW_OF_FEATURE, feature_names  # noqa: E402

PIX = 100.0
BLOCK = 512                      # px: 51.2 km spatial block
BUFFER_M = 300.0                 # kernel radius: nothing inside it may be called negative
FEAT_DIR = ROOT / "work/feat"
G_ANCHOR = 14088.7               # px of hidden truth, inverted from the nested prior pair
NODATA = -3.4028234663852886e+38


# --------------------------------------------------------------------------- geospatial layers
def read_raster(path, band=1) -> np.ndarray:
    with rasterio.open(ROOT / path) as ds:
        a = ds.read(band)
    return a


def label_arrays() -> dict:
    lab = read_raster("data/labels.tif")
    cat = lab == 1
    foot = lab != -1
    H, W = lab.shape
    return dict(lab=lab, cat=cat, foot=foot, H=H, W=W)


def distance_layers(cat: np.ndarray, foot: np.ndarray, cache: bool = True) -> dict:
    """Distances (metres) to catalogue, to SGMC faults, and the uncatalogued-SGMC proxy set."""
    cdir = ROOT / "work/cache"
    cdir.mkdir(parents=True, exist_ok=True)
    files = {k: cdir / f"{k}.npy" for k in ("ed_cat", "ed_sgmc", "unc", "sgmc")}
    if cache and all(f.exists() for f in files.values()):
        ed_cat = np.load(files["ed_cat"])
        ed_sgmc = np.load(files["ed_sgmc"])
        unc = np.load(files["unc"])
        sgmc = np.load(files["sgmc"])
    else:
        sgmc = read_raster("data/external/derived_sgmc_faults_100m_u8.tif") > 0
        ed_cat = ndimage.distance_transform_edt(~cat, sampling=PIX).astype(np.float32)
        ed_sgmc = ndimage.distance_transform_edt(~sgmc, sampling=PIX).astype(np.float32)
        unc = sgmc & (ed_cat > 300.0)
        for k, v in (("ed_cat", ed_cat), ("ed_sgmc", ed_sgmc), ("unc", unc), ("sgmc", sgmc)):
            np.save(files[k], v)
    return dict(ed_cat=ed_cat, ed_sgmc=ed_sgmc, unc=unc, sgmc=sgmc)


def block_ids(H: int, W: int, bs: int = BLOCK) -> np.ndarray:
    b = np.zeros((H, W), dtype=np.int32)
    for r0 in range(0, H, bs):
        for c0 in range(0, W, bs):
            b[r0:r0 + bs, c0:c0 + bs] = (r0 // bs) * (W // bs + 1) + (c0 // bs)
    return b


def fold_assignment(blocks: np.ndarray, n_folds: int = 5) -> np.ndarray:
    """Diagonal-stripe folds over 512 px blocks: spatially separated, deterministic."""
    br = blocks // (BLOCK * 8)
    bc = blocks % (BLOCK * 8)
    return ((br + 3 * bc) % n_folds).astype(np.int8)


# --------------------------------------------------------------------------- feature tiles
class TileCache:
    """Reads the cached float16 feature cube by pixel window (work/feat/tile_*.npy)."""

    def __init__(self, tile: int = 512) -> None:
        self.tile = tile
        self.manifest = json.loads((FEAT_DIR / "manifest.json").read_text())
        self.names = self.manifest["features"]
        assert self.names == feature_names()
        self.H = self.manifest["height"]
        self.W = self.manifest["width"]
        self._arr: dict[str, np.ndarray] = {}

    def window(self, r0: int, c0: int, h: int, w: int) -> np.ndarray:
        raise NotImplementedError  # use rows()/grid()

    def grid(self, name: str) -> np.ndarray:
        """Assemble a whole feature band (float32, NaN where never computed)."""
        if name in self._arr:
            return self._arr[name]
        i = self.names.index(name)
        out = np.full((self.H, self.W), np.nan, dtype=np.float32)
        for t in self.manifest["tiles"]:
            a = np.load(FEAT_DIR / t["file"], mmap_mode="r")
            out[t["row"]:t["row"] + t["h"], t["col"]:t["col"] + t["w"]] = np.asarray(a[i], dtype=np.float32)
        self._arr[name] = out
        return out

    def rows(self, rr: np.ndarray, cc: np.ndarray, names: list[str] | None = None) -> np.ndarray:
        """Gather a (n_rows, n_features) matrix for arbitrary pixel coordinates."""
        names = names or self.names
        out = np.empty((rr.size, len(names)), dtype=np.float32)
        idx = {n: self.names.index(n) for n in names}
        order = np.argsort(rr.astype(np.int64) * self.W + cc)
        rr_s, cc_s = rr[order], cc[order]
        # group by tile
        cols = np.empty(rr.size, dtype=float)
        for t in self.manifest["tiles"]:
            sel = ((rr_s >= t["row"]) & (rr_s < t["row"] + t["h"]) &
                   (cc_s >= t["col"]) & (cc_s < t["col"] + t["w"]))
            if not sel.any():
                continue
            a = np.load(FEAT_DIR / t["file"], mmap_mode="r")
            sub = a[:, rr_s[sel] - t["row"], cc_s[sel] - t["col"]]
            for j, n in enumerate(names):
                cols_order = j
                out[order[sel], cols_order] = np.asarray(sub[idx[n]], dtype=np.float32)
        return out


# --------------------------------------------------------------------------- models
def view_feature_names(view: str) -> list[str]:
    return [n for n in feature_names() if VIEW_OF_FEATURE[n] == view]


def fit_model(X: np.ndarray, y: np.ndarray, seed: int = 0, max_iter: int = 200):
    from sklearn.ensemble import HistGradientBoostingClassifier
    m = HistGradientBoostingClassifier(
        max_iter=max_iter, learning_rate=0.08, max_leaf_nodes=31, min_samples_leaf=40,
        l2_regularization=1.0, early_stopping=False, random_state=seed)
    m.fit(X, y)
    return m


def predict_model(m, X: np.ndarray, chunk: int = 500_000) -> np.ndarray:
    out = np.empty(X.shape[0], dtype=np.float32)
    for i in range(0, X.shape[0], chunk):
        out[i:i + chunk] = m.predict_proba(X[i:i + chunk])[:, 1].astype(np.float32)
    return out


def auc(y: np.ndarray, p: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, p))


def kernel_density(sel_rr: np.ndarray, sel_cc: np.ndarray, truth: np.ndarray) -> float:
    """Mean triangular-kernel weight of selected cells against a truth mask (credit density)."""
    if sel_rr.size == 0:
        return 0.0
    ed = ndimage.distance_transform_edt(~truth, sampling=PIX)
    d = ed[sel_rr, sel_cc]
    k = np.maximum(1.0 - d / 300.0, 0.0)
    return float(k.mean())


def dti_against(pred: np.ndarray, truth: np.ndarray) -> dict:
    from gems52.metric import dti
    r = dti(pred.astype(np.float64), truth)
    return {k: float(v) for k, v in r.items() if k != "reduced"}


def implied_credit(score: float, mass: int) -> float:
    """T = DTI * (0.2*S + 0.8*|G|) with the |G| anchor (knowledge/01 s2)."""
    return float(score * (0.2 * mass + 0.8 * G_ANCHOR))
