> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# Why `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` scored 0.2778, and what it would take to beat it

Answered at the level the question deserves: first what the file *is*, then the algebra that turns
that file into 0.2778, then the counterfactuals that bound what any file can do, then the concrete
headroom. Numbers are ours unless flagged; the file-to-score mapping itself is **owner-reported, not
organiser-authenticated** (see `knowledge/06_provenance_and_irregularities.md`).

## 1. What the file is

`h33-2-b2` = `h27-4-r1` **minus the catalogue mask**: 40,199 emitted pixels, of which 2,545 sat
exactly on label pixels, leaving **37,654** scored pixels. Nothing else changed. Deleting 6.3 % of
the file's own mass raised the score by about 2.6 %. That single fact is the whole story of the
score: the edit was *free precision*, because a pixel the organiser has masked can never earn credit
but can always pay the false-positive tax.

## 2. The algebra that produces 0.2778

The official metric (page 967, verbatim in the README) is

```
DTI = TPw / (alpha*FPw + beta*FNw + eps),  alpha=0.2, beta=0.8, R=300 m=3 px
k(d) = max(1 - d/R, 0)
TPw  = sum over truth g of  max_x  p(x) k(|x-g|)
FPw  = sum over x with p>0 of p(x) * (1 - max_g k(|x-g|))
```

Two consequences that decide everything here, both pinned in `tests/test_metric.py`:

* **`FNw == |G| - TPw`** exactly, so with binary mass
  `DTI = T / (0.2*(T + S - M) + 0.8*|G|)` where `T` = credited mass, `S` = emitted mass,
  `M` = `Σ_g max_x k`. The denominator's `S - M` term is the **placement tax**: mass that is not
  within 3 px of a truth pixel, *or whose nearest truth pixel is already better covered*.
* **the metric is not scale-invariant**, and for a single pixel with weight `lambda`
  `DTI = lambda*k / (0.2*lambda + 0.8)`, increasing in `lambda` ⇒ the optimal mass on any
  accepted pixel is **1.0**. Continuous scores are a mistake; `{0,1}` is optimal.

For `h33-2-b2` the loss decomposition we reconstructed was **tax 6,757 > credit 3,870 > miss
3,304** (in units of truth-pixel-mass): the file lost more to badly placed mass than it lost to
faults it never found. That is why removing 2,545 masked pixels helped — it removed pure tax.

## 3. The two counterfactuals that bound the field

* **Scatter control.** An identical-mass, incoherent (scattered) emission scored **0.0778** in this
  family. Same mass, 3.6x worse score. So on this leaderboard **placement is worth more than
  detector recall**: the metric is largely a test of whether you understand `k(d)`.
* **Perfect-precision counterfactual.** Taking the same 37,654-pixel budget and assuming every pixel
  lands inside 224 m of a new fault (`S = M`) gives `DTI = T/(0.2*0 + 0.8*|G|)` peaking at
  **0.464** for the |G| bracket we infer below. That is roughly the ceiling of "placement only"
  at this budget, and it is why the leader at 0.3774 is nearly maxed on placement: they must be
  finding structure, not just tidying mass.

## 4. What |G| is, and the bar it implies

`|G|` (number of new-fault truth pixels) is not published. It is bracketable from the organiser's own
scores: a submission that emits `S` pixels and earns `T` implies
`|G| >= T/(0.8*DTI) - ... `, and the eleven published scores in this family bracket it at
**5,764 - 15,179 px**, i.e. 0.112 - 0.294 % of the 5,165,840-px footprint (the catalogue itself is
1.179 %). We therefore validate folds thinned into exactly that prevalence band.

Now evaluate the metric's own acceptance rule at those scores. Our rule (derived and test-pinned) is

```
accept x  iff  gain(x) > [alpha*DTI / (1 - alpha*DTI)] * (1 - wmax(x))
```

`wmax(x)` is the best kernel weight x already contributes to an uncovered truth pixel. Because the
100 m grid makes the kernel take only the seven values
`1.000, 0.667, 0.529, 0.333, 0.255, 0.057, 0.0` (d = 0, 1, sqrt2, 2, sqrt5, 2sqrt2, 3 px), the bar
barely moves over the whole live leaderboard:

| DTI | bar | weights above bar | largest accepting distance |
|---|---|---|---|
| 0.05 - 0.20 | 0.010 - 0.042 | all six | 2.83 px (283 m) |
| **0.2778** | 0.0588 | five | **2.24 px (224 m)** |
| 0.32 | 0.0684 | five | 2.24 px |
| 0.3774 (live #1) | 0.0816 | five | 2.24 px |
| 0.464 (perfect-precision ceiling) | 0.1023 | five | 2.24 px |

**Read this table before writing any submission.** From 0.28 to 0.46 the marginal rule is the same
sentence: *emit a pixel iff it is within 224 m of a fault pixel the catalogue does not already have*.
So there is no score-dependent tuning knob; the only thing that moves the number is the **ranking**
of candidates, and the only ranking that matters is "how likely is there an uncatalogued fault pixel
within 2 px of here".

## 5. So can we beat 0.2778?

Three independent levers, in the order their size is actually known:

1. **Never pay tax on masked pixels** (worth +2.6 % alone, and it is what `h33-2-b2` did). Free,
   already in `holdout.mask_visible` / `emit`'s `allowed` set. Everyone at the top does this.
2. ~~**Rank the near-trace corridor instead of pruning it.**~~ **REFUTED ON THE BYTES, 2026-10-07 —
   see `knowledge/10` §2 and §3.** This item argued that mass 1-2 px off a mapped trace is scored and
   is where a truncated trace gets corrected, and cited "`h33-2-b2` shows 6.3 % of its mass was there
   and paid off". The restored reference file does not support either half of that. Measured:
   `h33-2-b2` has **0 px** within 1 px and **0 px** within 2 px of the mapped catalogue; its minimum
   distance-to-catalogue is **223.6 m**. It is a strict subset of `gems24-d2-8` (reported 0.2600), and
   `d2-8 \ h33-2-b2` = **6,436 px, every one of them inside 200 m of a mapped trace** — 14.6 % of
   that file's mass, not 6.3 %. Deleting exactly that ring is what turned 0.2600 into 0.2778: the ring
   did not pay off, it cost **6.8 %**. Inverting the metric on the nested pair gives its credit as
   **exactly zero**, and `|G|` = 14,088.7 px falls out of the same equation.
   The staff claim that the mask is pixel-exact (thread 11516 #4) survives as a *statement*; the bytes
   say the scoring behaves as if there were a ~2 px ring, or as if the hidden truth simply does not
   come within 200 m of the mapped catalogue. The two readings cannot be separated from here, and both
   give the same rule. **Do not emit inside 200 m of a mapped trace.** Cost of obeying it: zero.
   GEMSDOE45's `isolated`-pixel count (24,347 of 60,988) is unchanged and is now read as a fact about
   the catalogue's own topology, not as evidence for a corridor arm.
3. **Actually find uncatalogued structure.** This is what separates 0.28 from 0.37, and it is the
   reason for the A-only/B-only disagreement analysis in this repo. Our own measurement (see
   `knowledge/03`): the *detector* part is real but modest (A-view AUC 0.73-0.82 for recovering a
   hidden whole segment, single-view), while the *co-training* mechanism as such fails its lift test.
   So the honest expectation is a small gain here, not a doubling.

What will **not** work, already measured in this family: fitting a model to reproduce the catalogue
(live 0.1223, 0.0286), external fault catalogues as positive priors (QFaults-v2, INGENIOUS -> ~0
off-catalogue hits), topography-only off-catalogue selection (measures "is this a mountain"), and
1 m LiDAR fetching (unreachable + licence unclear). Any new proposal must differ from those.
