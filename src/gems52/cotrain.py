"""Historical two-view baseline, retained for comparison, not the active R2 runner.

Blum & Mitchell, *Combining Labeled and Unlabeled Data with Co-Training*,
COLT 1998 pp. 92–100, DOI 10.1145/279943.279962. View sufficiency,
compatibility and conditional independence are assumptions, not findings here.
The old evidence omitted all OOF negative predictions and cannot establish
independence. New experiments use gems52.spatial and run_structural_pipeline.py.
A-only is a buried-structure HYPOTHESIS, not verified geology; B-only can also
be a real surface fault, not automatically a road/erosion artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from sklearn.linear_model import LogisticRegression

ABANDON_R = 0.60          # |r| of the two views' block-level OOF errors at which co-training is dropped
NEG_COLLAR_PX = 3         # labelled negatives keep 300 m clear of any positive (kernel support)


# --------------------------------------------------------------------------------------------
# feature stack
# --------------------------------------------------------------------------------------------
def build_stack_from_dir(dirname, names: list[str], valid: np.ndarray) -> np.ndarray:
    """Memory-safe variant of :func:`build_stack`: one layer is resident at a time.

    On a 12.28M-pixel grid the naive version needs ~700 MB of float32 for a 14-feature stack;
    this box has 3 GB total, so the loop loads, ranks, frees, and peaks at 49 MB.
    """
    from pathlib import Path as _P
    d = _P(dirname)
    out = np.zeros(valid.shape + (len(names),), dtype=np.uint8)
    for j, nm in enumerate(names):
        a = np.load(d / f"{nm}.npy", mmap_mode="r")[:]
        out[..., j] = rank_u8(a, valid)
        del a
    return out


def rank_u8(a: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Percentile-free min-max rank to uint8 inside the footprint (see build_stack for why)."""
    v = a[valid]
    lo, hi = float(np.nanmin(v)), float(np.nanmax(v))
    r = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a, dtype=np.float32)
    r = np.clip(np.nan_to_num(np.asarray(r, dtype=np.float32), nan=0.0), 0.0, 1.0)
    out = (r * 255.0).astype(np.uint8)
    out[~valid] = 0
    return out


def build_stack(layers: dict[str, np.ndarray], names: list[str], valid: np.ndarray) -> np.ndarray:
    """uint8 rank-encode the named layers into one (H, W, F) stack.

    255-level ranks, not float32: the whole grid then costs 12.28M x F bytes instead of 4 x that,
    which is the difference between fitting in 3 GB and not.  The metric resolves 100 m, not
    1/255 of a quantile, so the loss is immaterial for ranking; the *raw* float layers stay on
    disk for the physics audit and the emission score.
    """
    h, w = valid.shape
    out = np.zeros((h, w, len(names)), dtype=np.uint8)
    for j, nm in enumerate(names):
        a = np.asarray(layers[nm], dtype=np.float32)
        v = a[valid]
        lo, hi = np.nanmin(v), np.nanmax(v)
        r = np.full(a.shape, 0, dtype=np.float32)
        if hi > lo:
            r = (a - lo) / (hi - lo)
        r = np.clip(np.nan_to_num(r, nan=0.0), 0.0, 1.0)
        out[..., j] = (r * 255.0).astype(np.uint8)
    out[~valid] = 0
    return out


# --------------------------------------------------------------------------------------------
# negative sampling and labelled sets
# --------------------------------------------------------------------------------------------
def labelled_sets(cat: np.ndarray, valid: np.ndarray, rng: np.random.Generator,
                  neg_per_pos: int = 40, collar_px: int = NEG_COLLAR_PX
                  ) -> tuple[np.ndarray, np.ndarray]:
    """(pos_idx, neg_idx) into the flattened grid.

    Negatives are *labeled negatives* in the sense the brief uses: footprint pixels that the
    catalogue says are not fault, pushed at least ``collar_px`` away from any catalogue pixel,
    because a 300 m kernel would otherwise let a near-trace pixel teach the model that the trace
    is background.  They remain positive-unlabelled in the competition's real metric (a 0 in
    labels.tif is not a proven absence); this is recorded as IR-52-004 rather than hidden.
    """
    flat_cat = cat.ravel()
    pos = np.flatnonzero(flat_cat)
    clear = ~ndimage.binary_dilation(cat, iterations=collar_px).ravel()
    pool = np.flatnonzero(valid.ravel() & clear & ~flat_cat)
    n = min(pool.size, neg_per_pos * max(pos.size, 1))
    neg = rng.choice(pool, size=n, replace=False)
    return pos.astype(np.int64), neg.astype(np.int64)


# --------------------------------------------------------------------------------------------
# one view's learner
# --------------------------------------------------------------------------------------------
@dataclass
class View:
    name: str
    cols: list[int]
    model: LogisticRegression | None = None
    scaler_mu: np.ndarray = field(default=None)
    scaler_sd: np.ndarray = field(default=None)

    def fit(self, stack: np.ndarray, rows: np.ndarray, y: np.ndarray, seed: int = 0) -> "View":
        X = self._gather(stack, rows)
        self.scaler_mu = X.mean(axis=0)
        self.scaler_sd = X.std(axis=0) + 1e-6
        Z = (X - self.scaler_mu) / self.scaler_sd
        self.model = LogisticRegression(max_iter=400, C=1.0, class_weight="balanced",
                                        solver="lbfgs", random_state=seed)
        self.model.fit(Z, y)
        return self

    def _gather(self, stack: np.ndarray, rows: np.ndarray) -> np.ndarray:
        n = stack.shape[0] * stack.shape[1]
        flat = stack.reshape(n, stack.shape[2])
        return flat[rows][:, self.cols].astype(np.float32)

    def predict_rows(self, stack: np.ndarray, rows: np.ndarray) -> np.ndarray:
        Z = (self._gather(stack, rows) - self.scaler_mu) / self.scaler_sd
        return self.model.predict_proba(Z)[:, 1].astype(np.float32)

    def predict_grid(self, stack: np.ndarray, chunk: int = 1_000_000) -> np.ndarray:
        """Score every pixel.  Chunked, and the chunk slice is taken before the float cast, so the
        peak stays at one chunk (40 MB) instead of the whole stack (688 MB)."""
        n = stack.shape[0] * stack.shape[1]
        out = np.zeros(n, dtype=np.float32)
        flat = stack.reshape(n, stack.shape[2])
        for a in range(0, n, chunk):
            b = min(n, a + chunk)
            Z = (flat[a:b][:, self.cols].astype(np.float32) - self.scaler_mu) / self.scaler_sd
            out[a:b] = self.model.predict_proba(Z)[:, 1]
        return out

    def coef_report(self) -> dict:
        return {"view": self.name, "cols": self.cols,
                "coef": [float(v) for v in self.model.coef_[0]],
                "intercept": float(self.model.intercept_[0])}


def view_auc(p: np.ndarray, truth: np.ndarray) -> float:
    """Tie-aware AUC.  ``p`` and ``truth`` must be 1-D and the same length (callers pre-filter)."""
    pos = np.flatnonzero(truth)
    neg = np.flatnonzero(~truth)
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    q = np.sort(p[neg][: min(600_000, neg.size)])
    v = p[pos][: min(600_000, pos.size)]
    lo = np.searchsorted(q, v, side="left")
    hi = np.searchsorted(q, v, side="right")
    return float(np.mean((hi + lo) / 2.0) / q.size)


# --------------------------------------------------------------------------------------------
# the independence / abandonment test the brief mandates
# --------------------------------------------------------------------------------------------
def view_correlation(err_a: np.ndarray, err_b: np.ndarray) -> dict:
    """Correlate the two views' per-block errors on labelled negatives, and decide.

    ``err_*`` are per-block mean over-predictions on labelled negatives (i.e. 1 - specificity at
    the 0.5 operating point, averaged), one number per spatial block.  Pearson r over blocks plus
    a Spearman check, since with 16 blocks a single outlier can drive a Pearson estimate.
    """
    a, b = np.asarray(err_a, float), np.asarray(err_b, float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    from .spatial import correlations
    result = correlations(a, b)
    r, rho = result['pearson'], result['spearman']
    undefined = r is None or rho is None
    return dict(n_blocks=int(a.size), pearson_r=r, spearman_rho=rho,
                abandon=bool(undefined or abs(r) >= ABANDON_R or abs(rho) >= ABANDON_R),
                threshold=ABANDON_R, measured=not undefined,
                reason='undefined/constant errors disable exchange' if undefined else 'proxy diagnostic, not proof')


# --------------------------------------------------------------------------------------------
# co-training
# --------------------------------------------------------------------------------------------
def abstain_mask(p: np.ndarray, q_abstain: float = 0.60) -> tuple[float, np.ndarray]:
    """(threshold, abstain) where a view *abstains* iff its score is at or below its own
    ``q_abstain`` quantile on the unlabelled pool.  The abstain side of the rule is deliberately
    "withholds", not "believes the opposite": co-training should only be fed a view's convictions,
    and a view that is quietly confident should not be contradicted by a confident-negative label
    that the catalogue never actually asserts (see IR-52-004, positive-unlabelled)."""
    hi = float(np.quantile(p, q_abstain))
    return hi, (p <= hi)


@dataclass
class CoTrainResult:
    p_a: np.ndarray
    p_b: np.ndarray
    rounds: list[dict]
    independence: dict
    promoted: bool
    notes: list[str] = field(default_factory=list)
    p_a0: np.ndarray | None = None            # round-0 (supervised-on-catalogue only) scores
    p_b0: np.ndarray | None = None
    pseudo_a: np.ndarray | None = None         # rows that A proposed to B
    pseudo_b: np.ndarray | None = None


def co_train(stack: np.ndarray, views: tuple[View, View], pos: np.ndarray, neg: np.ndarray,
             fit_mask: np.ndarray, cat: np.ndarray, valid: np.ndarray,
             rounds: int = 1, conf_q: float = 0.995, seed: int = 0,
             log=print) -> CoTrainResult:
    """Blum-Mitchell co-training, one round = fit A on L+pseudo(B), fit B on L+pseudo(A).

    Pseudo-labels are positives taken from *unlabelled* pixels only (never from the catalogue, which
    is masked out of the real metric and therefore worthless as a target), only where the labelling
    view is in its own top ``1 - conf_q`` tail and the other view abstains, and only inside
    ``fit_mask`` so that nothing crosses into an evaluation block.
    """
    va, vb = views
    rng = np.random.default_rng(seed)
    y = np.concatenate([np.ones(pos.size, np.int8), np.zeros(neg.size, np.int8)])
    rows = np.concatenate([pos, neg])
    va.fit(stack, rows, y, seed)
    vb.fit(stack, rows, y, seed)

    pa = pa0 = va.predict_grid(stack)
    pb = pb0 = vb.predict_grid(stack)
    pseudo_from_a = pseudo_from_b = np.zeros(0, dtype=np.int64)
    vm = valid.ravel()
    cm = cat.ravel()[vm]
    history = [dict(round=0, auc_a=view_auc(pa[vm], cm), auc_b=view_auc(pb[vm], cm),
                    n_pseudo_a=0, n_pseudo_b=0)]
    notes: list[str] = []
    fit_rows = np.flatnonzero(fit_mask.ravel())
    unl = np.flatnonzero((valid & ~cat).ravel())
    for _ in range(max(0, rounds)):
        hi_a, ab_a = abstain_mask(pa[unl])
        hi_b, ab_b = abstain_mask(pb[unl])
        thr_a = float(np.quantile(pa[unl], conf_q))
        thr_b = float(np.quantile(pb[unl], conf_q))
        pseudo_from_a = unl[(pa[unl] >= thr_a) & ab_b]   # A confident, B abstains
        pseudo_from_b = unl[(pb[unl] >= thr_b) & ab_a]   # B confident, A abstains
        # keep only pseudo-labels inside the fit region, buffered away from every labelled pixel
        keep = fit_mask.ravel()
        pseudo_from_a = pseudo_from_a[keep[pseudo_from_a]]
        pseudo_from_b = pseudo_from_b[keep[pseudo_from_b]]
        if pseudo_from_a.size < 200 or pseudo_from_b.size < 200:
            notes.append(f"round skipped: too few pseudo-labels "
                         f"({pseudo_from_a.size} from A, {pseudo_from_b.size} from B)")
            break
        rows_a = np.concatenate([pos, neg, pseudo_from_b])
        y_a = np.concatenate([y, np.ones(pseudo_from_b.size, np.int8)])
        rows_b = np.concatenate([pos, neg, pseudo_from_a])
        y_b = np.concatenate([y, np.ones(pseudo_from_a.size, np.int8)])
        va.fit(stack, rows_a, y_a, seed)
        vb.fit(stack, rows_b, y_b, seed)
        pa = va.predict_grid(stack)
        pb = vb.predict_grid(stack)
        history.append(dict(round=len(history), auc_a=view_auc(pa[vm], cm), auc_b=view_auc(pb[vm], cm),
                           n_pseudo_a=int(pseudo_from_a.size), n_pseudo_b=int(pseudo_from_b.size),
                           conf_a=thr_a, conf_b=thr_b))
        log(f"  co-train round: pseudo A->B {pseudo_from_a.size}, B->A {pseudo_from_b.size}")
    return CoTrainResult(p_a=pa, p_b=pb, rounds=history, independence={}, promoted=False,
                         notes=notes, p_a0=pa0, p_b0=pb0,
                         pseudo_a=pseudo_from_a, pseudo_b=pseudo_from_b)


# --------------------------------------------------------------------------------------------
# disagreement strata -- the discovery signal
# --------------------------------------------------------------------------------------------
def strata(p_a: np.ndarray, p_b: np.ndarray, valid: np.ndarray, q_conf: float = 0.98,
           q_abstain_hi: float = 0.60) -> dict:
    """Split the unlabelled grid into concordant / A-only / B-only / silent, by per-view quantiles.

    A-only means the potential-field view is in its confident tail while the surface view abstains:
    potentially consistent with a covered structure, but not proof of one. B-only may be
    a real scarp or an artifact: independent geological verification is required.
    """
    v = valid.ravel()
    a = p_a[v]
    b = p_b[v]
    ca = float(np.quantile(a, q_conf))
    cb = float(np.quantile(b, q_conf))
    ha = float(np.quantile(a, q_abstain_hi))
    hb = float(np.quantile(b, q_abstain_hi))
    A = np.zeros(p_a.shape, dtype=np.int8)          # 0 silent, 1 concordant, 2 A-only, 3 B-only
    conf_a = (p_a >= ca)
    conf_b = (p_b >= cb)
    ab_a = (p_a <= ha)
    ab_b = (p_b <= hb)
    A[conf_a & conf_b] = 1
    A[conf_a & ~conf_b & ab_b] = 2
    A[conf_b & ~conf_a & ab_a] = 3
    A[~valid.ravel().reshape(A.shape)] = 0
    return dict(mask=A.reshape(valid.shape), thresholds=dict(conf_a=ca, conf_b=cb,
                                                              abstain_a=ha, abstain_b=hb),
                counts={k: int((A == i).sum()) for i, k in
                        enumerate(["silent", "concordant", "a_only", "b_only"])})
