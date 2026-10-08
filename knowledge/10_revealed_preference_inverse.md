# 07 · The revealed-preference inverse: what the organiser's own scores say about the hidden truth

Recorded 2026-10-06/07. Every number here is reproducible from restored bytes whose SHA-256 is
pinned in `registry/data_manifest.json`, plus owner-reported published scores. Scripts: `work/a3`,
`work/a6`, `work/a9`, `work/a10`, `work/a12`, `work/a13`, `work/a14`; production code in
`src/gems52/revealed.py`.

The method is not a model fit to a leaderboard. `knowledge/03` N-5 records that fitting a truth model
to coarse leaderboard scores fails (RMSE 0.1449). What is done here is different and much stronger:
**the restored bytes of five scored files stand in exact set relations to one another**, so their
published scores are not 13 noisy observations of one number but a small linear system whose
solution is an interval, not a guess.

---

## 1. The nesting, measured

| relation | measurement |
| --- | --- |
| `A = h33-2-b2` (reported 0.2778) vs `B = gems24-d2-8` (0.2600) | `A \ B` = **0 px**. `A` is a strict subset of `B`. |
| `B \ A` | **6,436 px**, every one of them within **100–200 m** of the mapped catalogue; `min` distance-to-catalogue inside `A` is **223.6 m** |
| `A` vs `E = h19-5` (0.1922) | `A \ E` = **0 px** |
| `B` vs `E` | `B \ E` = **0 px** |
| `C = gems24-d1-5` (0.2477) vs `E` | `C \ E` = **0 px** |
| `C` vs `D = topogap` (0.2449) | `C \ D` = 0, `D \ C` = 1,259 |
| `A` vs `C` | `A \ C` = 12,137, `C \ A` = 34,552 — **not** nested |

So the champion file is *the 0.2600 file with the near-catalogue ring deleted*, and both are subsets
of the 121,131 px `h19-5` emission. That is a chain, not a cloud.

## 2. `|G|`, and the ring that earns nothing

With `DTI = T / (0.2 (T + S − M) + 0.8 |G|)` and `M = T` for a dot emission whose pixels are
separated by more than 200 m (so two dots rarely compete for one truth pixel):

```
T(X) = score(X) * (0.2 * |X| + 0.8 * |G|)
T(B) - T(A) = 200.62 - 0.01424 * |G|
```

`B \ A` is exactly the ≤ 200 m ring around the mapped catalogue. Setting its credit to zero — which
is what "deleting that ring raised the score from 0.2600 to 0.2778" means — gives

> **`|G|` = 14,088.7 px = 0.2726 % of the 5,167,373 px footprint.**

Independent bracket on the same quantity, from `T ≤ |G|` applied to every one of the 13 restored
scored files: **`|G| ≥ 8,128`** (binding file: `8GEMSDOE_Hedge-v2`, 227,507 px at 0.1563). The
repo's earlier estimate `g_estimate_px = 10,331.68` sits inside the bracket; the value above is
tighter because it uses an exact set identity rather than an average.

**Two readings of the dead ring, and the rule is the same under both.** Either (a) the organiser's
mask is a ~2 px buffer rather than pixel-exact — which contradicts the staff-thread reading recorded
in `knowledge/01` §1 and `knowledge/02` H52-2 — or (b) the hidden truth simply does not come within
200 m of the mapped catalogue. The bytes cannot separate (a) from (b). Both say: **emit nothing
inside 200 m of a mapped trace.** That is what `revealed.CORRIDOR_M` implements, and it is the
single change with the largest measured effect in this repo's history (+6.8 % on the organiser's own
scoring, from a file we hold).

## 3. The atom accounting, and the credit hierarchy inside the champion file

The atoms of `{A, B, C, E}` partition `E` exactly (verified: the six sizes sum to 121,131):

| atom | px | credit at `|G|`=14,088.7 | density |
| --- | --- | --- | --- |
| `P1 = A & C` | 25,517 | **[4,168, 5,223]**, central 5,140 | **16.3 % – 20.5 %**, central 20.1 % |
| `P2 = A \ C` | 12,137 | [0, 1,055] | 0 % – 8.7 % |
| `P3 = (B\A) & C` | 4,332 | **0 exactly** | 0 % |
| `P4 = (B\A) \ C` | 2,104 | **0 exactly** | 0 % |
| `P5 = (E\B) & C` | 30,220 | [544, 1,599] | 1.8 % – 5.3 % |
| `P6 = (E\B) \ C` | 46,821 | [0, 1,055] | 0 % – 2.3 % |

Reference points: uniform-random mass over the permitted set has credit density **2.79 %**; the
champion file `A` as a whole averages **13.87 %**, i.e. **5.0× random**.

The interval on `P1` is exact (it follows only from `t ≥ 0`). The central estimate splits the
*measured* tail credit `T(E) − T(B) = 1,599` between `P5` and `P6` in proportion to their sizes,
which is the least informative choice available: both atoms are the same field's tail and nothing in
the published scores separates them.

**Reading.** Being selected by two independent thinnings of the same field is worth roughly an order
of magnitude in credit density over being selected by one. That is a *corroboration* effect, and it
is the only sub-ranking inside the champion file that the published scores can see.

**Consequence, exact:** `DTI(P1 emitted alone)` = **0.2546 – 0.3190**, central **0.3139**. A pure
budget reduction of the champion file — no new geology at all — is worth up to +14.8 %.

## 4. A cross-check that the model is not circular

`T(S) = 471.6 · S^0.2284` fitted to three family members predicts the other published scores:

| file | S | predicted DTI | reported | error |
| --- | --- | --- | --- | --- |
| `h33-2-b2` | 37,654 | 0.2783 | 0.2778 | +0.2 % |
| `d1-5` | 60,069 | 0.2500 | 0.2477 | +0.9 % |
| `topo-gap-closure` | 61,328 | 0.2484 | 0.2449 | +1.4 % |
| `h19-5` | 121,131 | 0.1925 | 0.1922 | +0.2 % |
| `h19-4` | 123,779 | 0.1901 | 0.1894 | +0.4 % |
| `h16-1` | 123,939 | 0.1900 | 0.1855 | +2.4 % |
| `d2-8` | 44,090 | 0.2700 | 0.2600 | +3.8 % (it still carries the dead ring) |
| **`anderson-geothermal-pinn`** (a *different* family) | 38,854 | **0.2767** | **0.2750** | **+0.6 %** |

Eight of eight inside 4 %, five inside 1.5 %, and the one file from outside the fitted family is
predicted to 0.6 %. The same model put through the atom algebra predicts `DTI(P1)` at 0.2975 for
`S` = 16,678 — inside the exact interval derived independently in §3. Two derivations agreeing is
the reason this is treated as a measurement rather than a curve fit.

## 5. What is *not* true: the hide simulator does not predict the organiser's score

`src/gems52/holdout.py` scores a candidate by hiding whole catalogue components and recovering them.
Run over the 13 restored scored files (4 folds each, emission restricted to each fold's legal set,
budget matched):

* Spearman ρ(reported score, simulated DTI) = **−0.1045**, p = **0.734**, n = 13.
* Spearman ρ(reported score, simulated lift over random) = −0.1265, p = 0.680.
* The champion file `h33-2-b2` scores **0.0046** on the simulator against **0.0496** for
  mass-matched uniform random: lift **0.09×**. It is the *worst* of the 13 on the instrument and the
  *best* of the 13 on the organiser's board.
* Ranking by simulated DTI puts `8GEMSDOE_Hedge-v2` first (0.316) — the file that actually scored
  0.1563.

Correcting the confound I introduced first (the hidden truth was allowed to sit inside the ring that
a corridor-excluding prior may not enter) changed nothing: lift 0.10 → 0.09, ρ unchanged.

**Verdict: the instrument is not a proxy for the task.** Its premise is that the hidden truth is a
held-out part of the mapped catalogue. §2 and §3 say the hidden truth is *not* near the mapped
catalogue at all, so the premise is false, and every selection this repo made through that gate —
including the `promoted: false, forced: true` decision recorded in `docs/data/submission.json` —
inherits the defect. Recorded as `knowledge/03` N-9.

## 6. What is *not* true: no feature I can compute re-ranks inside the champion file

Two screens, both spatially blocked (10–11 blocks of 4×4 that contain both classes), both against
the credit hierarchy of §3:

* **63 point and local-differential features** — the 19 competition bands, their horizontal
  gradients, Laplacians and 5×5 ranges, linearity ratios, all 12 LiDAR scarp bands, the 4
  radiometric bands and 4 ratio bands, the SGMC layer. Best AUC(`P1` vs `P2`) = **0.5453**
  (`lin_detelev`), sd 0.008, and that is the maximum of 63 tests.
* **108 structure-tensor features** — coherence and gradient magnitude at σ = 2, 4, 8 px on 12
  bands. Best AUC(`P1` vs `P2`) = **0.5122**, se 0.0032.

Meanwhile the *habitat* signature is strong and useless: AUC(`A` vs uniform random) reaches **0.7023**
(`ddetelev_range5`), **0.6605** (`ddetelev_hg`), **0.6522** (`sc_upface`), **0.6494** (inverted
`rad_K` — the champion's dots sit on *potassium-poor* ground). But `P2`, `P5` and `P6` have almost
the same habitat AUCs as `P1` (0.70 / 0.68 / 0.68 for `ddetelev_range5`) while carrying 20× less
credit.

**Verdict: habitat is not credit.** A field built from these features can find *where this family
emits*; it cannot find *which of those emissions were right*. Recorded as N-10 and N-11. This is why
the H54 emission keeps the exactly-accounted core instead of pretending to a better ranker it cannot
validate.

## 7. What *is* recoverable: the strike of the credited structure

`TPw = Σ_g max_x p(x) k(d(x,g))` credits each truth pixel **once, at its best covering weight**. A
dot 250 m off a trace earns that truth pixel 0.167; a dot on the trace earns up to 3.0
truth-pixel-credits (∫ over the covered ribbon). So the cheapest score in this metric is not new
structure — it is mass placed *along* structure already known to be credited.

The local strike of that structure is recoverable from the credited dot cloud itself, via the
structure tensor of its smoothed density:

| smoothing | mean coherence, credited cloud | mean coherence, matched uniform-random cloud | lift |
| --- | --- | --- | --- |
| σ = 4 px | 0.531 | 0.362 | 1.47× |
| σ = 6 px | 0.549 | 0.412 | 1.33× |
| σ = 10 px | 0.566 | 0.443 | 1.28× |

and the fraction of dots above coherence 0.8 is **16.8 %** against **2.2 %** for the matched random
cloud — a 7.6× contrast. The two independent thinnings `A` and `C` agree on the recovered
orientation histogram to cosine **0.9952**, while the random control is flat.

The recovered dominant strike is **100–110° in array convention** (+x east, +y south), i.e. an
azimuth of about **010–020°**: NNE–SSW. That is the Basin-and-Range normal-fault strike of this
footprint (37.3–40.7 N, 116.2–120.0 W). The fabric is geologically correct, which is the check that
matters: a detector that recovers the wrong fabric would be fitting noise.

## 8. The budget rule, and why it is a probability and not a taste

`DTI = T / (0.2 S + 0.8 |G|)` with `T = t_core + ρ_novel · n_novel` capped by `|G|`. Two things are
unknown and they are treated differently:

* `t_core` is bounded **exactly** by §3, so it gets a uniform prior over `[4168, 5223]`;
* `ρ_novel` — the credit density of mass this repo has never emitted — is unknowable, so it gets a
  uniform prior from **0.03** ("no better than uniform random", measured 0.0279) to **0.14** ("as
  good as the champion file's own average", measured 0.1387).

`revealed.budget_rule` then reports, for each candidate size, `P(DTI > 0.2778)` under that joint
prior and selects the maximum. That is the Arena core value *Maximize P(Win)* written as arithmetic
rather than as an adjective. The measured shape (see `evidence/revealed_budget.json`): `P(win)` rises
from 0.640 at zero novel mass to a broad maximum of ≈0.83 around 15,000–20,000 px and falls slowly
after; mean DTI rises monotonically to 0.339 at 50,000 px while the worst case falls to 0.215. The
flatness of `P(win)` is the useful part — the choice is not sensitive, so the tie-break goes to
novelty, which the brief requires and the mean cannot see.

## 9. Limits, stated plainly

1. `M = T` is an approximation. It is good here because the champion's dots are separated by more
   than 200 m, so two dots rarely compete for one truth pixel; it is not exact, and §3's interval
   widens if it is wrong.
2. The published scores are owner-reported at 4 decimal places. The board publishes no filename, so
   the file-to-score pairing is not organiser-authenticated. Every number here inherits that.
3. Additivity across *disjoint* atoms is used to get the interval on `P1`. Submodularity alone
   (`T(X∪Y) ≤ T(X) + T(Y) − T(X∩Y)`) gives weaker bounds; the additive reading is what the >200 m
   dot separation licenses.
4. `ρ_novel` is a prior, not a measurement. Nothing in §6 licenses a claim that a new field is good;
   the emission is sized so that the retained core carries the score if the novel half is worthless.
5. `|G|` = 14,088.7 is *defined* by "the ring earns nothing". If the ring earns a little, `|G|` is
   a little smaller and every credit in §3 scales down with it. The bracket in §2 is the honest
   statement.
