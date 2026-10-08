> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# 03 · Negative results, and what each one killed

Written so the next run does not repeat them. Every number below is reproducible from
`evidence/*.json` in this repo; nothing here is inferred from memory or from a sibling site.

Ordering is by how much compute each dead end cost us.

---

## N-1 · Co-training with pseudo-labels is refuted on both instruments (the largest one)

**The idea** (the brief's mechanism, and the one the group had never tried): train View A on the
geophysical bands and View B on the surface bands; wherever one view is confident and the other
abstains, harvest that disagreement as a pseudo-label, retrain, and emit the second-round model.
Blum & Mitchell's COLT'98 result (doi:10.1145/279943.279962) says this *can* work when each view is
individually sufficient and their errors are conditionally independent given the label.

**What happened.** Pre-registered gates, evaluated on the arm `cotrain|25000`, on both instruments:

| gate | tip (truncation) | hide (whole-component) |
|---|---|---|
| beats naive union at equal budget | −0.01582 → **FAIL** | −0.03027 → **FAIL** |
| beats the better single view | +0.00097 → pass | +0.00183 → pass |
| placement, not mass (vs identical-mass scramble) | −0.01667 → **FAIL** | −0.03183 → **FAIL** |
| fold support (≥3/4 folds beating random) | 0/4 → **FAIL** | 0/4 → **FAIL** |
| promoted | **false** | **false** |

Absolute DTI for the arm: `cotrain|37654` = 0.0084 (tip) / 0.0078 (hide) — the *worst* of every arm
we measured, including the random control at 0.0253 / 0.0396.

**The reading — and a retraction that matters more than the failure.** *This section used to assert that the
independence premise survived, quoting r = 0.4298 (tip, n = 11 blocks) and r = −0.1406 (hide). Those numbers
came from a pre-fix run of the diagnostic; `evidence/independence_*.json` was rewritten afterwards and no
longer contains them. Quoting them further would have been exactly the failure the register exists to catch.
What the files on disk say, re-read at 22:33 UTC:*

| reading | tip | hide |
|---|---|---|
| block-level false-alarm Pearson | **undefined** — both views' per-block false-alarm rate is constant (all zeros), so fewer than 3 usable blocks; Spearman degenerates to 1.0 on the ties | **undefined** — same |
| block-level miss-rate Pearson | −0.2235 (Spearman −0.1636) | **+0.8307** (Spearman 0.7727) |
| held-pixel logit Pearson | +0.1748 over 19,183 held px (negatives-only slice undefined) | +0.1316 over 36,375 held px |
| held strata | 0.62 % concordant, 2.42 % A-only, 9.13 % B-only | 0.12 % concordant, 1.19 % A-only, 10.74 % B-only |

The honest statement is narrower than the one we wrote. The pre-registered **abandonment test could not fire
at this grid size** — it is a block-level correlation, and the block-level false-alarm variance is
degenerate. Of the two readings that *are* available, they disagree with each other: the pixel-level logit is
weakly coupled (+0.17 tip, +0.13 hide, far below the 0.60 threshold), while the block-level *miss-rate*
correlation on `hide` is +0.83 — the views miss the same neighbourhoods, which is what a shared
interpolation grid and a shared geology would do. **Conditional independence is therefore neither established
nor refuted here: it is unmeasured at the granularity the pre-registration specified, and where a block-level
quantity can be measured it looks worse than the theorem would like.** The mechanism's own result is
unambiguous regardless: mean AUC Δ −0.0159 with 1/4 fold support, and the arm is worst-of-all on both
instruments (0.0084 tip / 0.0078 hide vs 0.0253 / 0.0396 for matched random), so the pseudo-label round is
dropped on its own measurement, not on the premise's. What the strata still show is physical and unaffected:
A-only pixels sit at median band-15 rank 455.0 against 296.7 for B-only and 251.2 for concordant
(`evidence/strata.json`) — deeper cover, exactly where a surface view must abstain.

**Rule we adopted:** the disagreement signal is used as a *stratification of the emission budget*, never
as a label source, in this competition and at this prevalence (~0.2 % of pixels).

**And the rule the retraction taught:** any number quoted in prose is re-read, in the same session, from the
file that publishes it — evidence JSONs are overwritten by every re-run of the script that makes them, and
prose is not.

---

## N-2 · A whole-footprint rank field's top-K is not a fault detector

Before the fold machinery existed we scored the top 40 k pixels of the blended rank field over the whole
footprint in hide mode and got essentially the random control. Cause: the top of a rank field is the
*regional anomaly* — a basement-high, a drainage-basin-scale gravity low — not a linear structure. Any
"take the most extreme values" rule spends its budget on 10 km blobs. This is the same failure mode that
killed GEMSDOE47's off-catalogue SGMC arm.

**Rule adopted:** ranking must always be applied *inside a permitted set* (footprint minus catalogue,
and for corridor mass, inside the corridor), and any arm whose field is unimodal-scaled must be checked
against `random` at the same budget in the same mask.

---

## N-3 · Hide mode is structurally blind to near-trace mass; tip mode is blind to isolated faults

`union_cor|37654` scores 0.0320 on tip and **0.0001** on hide. That is not a weakness of the arm, it is
arithmetic: the hide folds hold out whole components, so only 0.5 % of held-out truth lies within 5 px of
a *visible* trace, and a corridor arm is by construction looking next to visible traces. Conversely tip
folds truncate known traces, so an arm that finds an isolated, never-mapped fault gets no credit there.

Two consequences we now treat as design rules:

1. **Never select on one instrument.** Every arm is reported on both, and the shipped selection rule is a
   two-regime composite (corridor mass scored by the tip-winning ranking, far-field mass by the
   hide-winning ranking), *not* the minimum of the two.
2. **Max-min alone is a trap.** The best arm by max-min is `B_only|25000` (0.0296 / 0.0497) and it
   throws away the entire near-trace population, where the truth is densest (88.5 % of tip-fold truth
   lies within 5 px of a visible trace). Selecting by max-min would have discarded the corridor — the one
   regime the organiser's own statement says is *in scope* ("new-fault truth can lie within 300 m of a
   known trace, and those corrections are a competition goal", chrisk-dd, Sep 21).
3. Tip-mode prevalence is data-determined (4–8 k px per fold), so only *ranking* transfers between folds;
   absolute tip DTI must never be read as a score forecast.

---

## N-4 · The pre-registered blend weights were asserted, and backwards

`registry/preregistration.json` opened with w = (0.55 r_A + 0.20 r_B + 0.25 min) because co-training
theory says the two views are comparable in quality. On this data the surface view dominates: `B_only`
is the **only** arm that beats its random control on both instruments (0.0291 tip / 0.0518 hide at
37,654 px; +31 % over random on hide but winning only 2/4 folds, and +15 % on tip), while A-only is below
random on hide. Any re-weighting therefore has to be recorded as an *amendment* to the pre-registration
with the fitted numbers in it — never applied silently. The `wt_A20B80` family is exactly that amendment,
declared in the arm table rather than hidden in a config.

---

## N-5 · NaN outside the footprint is unwritable *and* unsubmittable

`grid.write_geotiff` refuses non-finite pixels, and the portal's own validator enforces `0 <= v <= 1`,
which NaN fails regardless of the comparison direction. That is the mechanism behind the historical
"Predicted values must be in range [0, 1]" rejection this lab hit before: it was never a scaling problem,
it was the no-data encoding. The page's "null or NaN where there is no data" sentence and the validator
contradict each other; scoring is identical either way (p = 0 contributes nothing to FPw), so the safe
encoding is 0.0 and `gates.format_report` now calls NaN a problem by name.

---

## N-6 · Inherited dead ends, re-listed so they stay dead

All of these were measured, in this family, and are not to be retried without new information:

| tried | result | why it fails |
|---|---|---|
| fit a truth model to published leaderboard scores | RMSE 0.1449 against scores of 0.25–0.38 | unusable; the board is too coarse and too few |
| supervised detectors trained to reproduce the catalogue | 0.1223, then 0.0286 | the metric rewards *new* faults only; a catalogue copy is max-penalised |
| external fault catalogues as positive priors | QFaults → 1 px in footprint, INGENIOUS → 0 px | nothing mapped there yet; as a *negative* filter they are still interesting |
| 1 m LiDAR acquisition | download volume exceeds this sandbox | licence is fine (public domain), bandwidth is not |
| potential-field transforms at 300 m cell size | magnetic transforms AUC ≈ 0.52; cross-strike magnetic braid 0.4987; strain-ratio Laplacian 0.4765; basement-depth signed step 0.5113; Laplacian of fine strain ≈ 0.5; drainage-azimuth asymmetry 0.4796 | the provided grids are already processed to the point where a second derivative amplifies nothing but noise |

---

## N-7 · Process failures worth recording (they cost hours, not model quality)

* `pkill -f <pattern>` inside a tool call kills the tool call itself whenever the pattern also matches
  the invoking shell's command line. It bit us twice (once silently dropping the command queued after it).
  Use the process tools, or `pgrep` then `kill <pid>`, and never put the target's name in the same compound
  command.
* A 12-arm × 6-budget × 4-fold × 2-mode sweep (`scripts/budget_sweep.py`) does not fit in a 2 CPU / 3 GB
  box: ~40 min of wall time for a table whose informative rows are readable in ~7 min from a named arm
  list. The script is left in the repo, correct but unrun; `scripts/composite_split.py` replaces it with
  an explicit `--far/--cor/--splits` grid.
* Bash heredoc patch scripts inside compound commands are unsafe (one unbalanced bracket swallows the
  rest of the command and writes nothing). Prefer editing files with a real edit tool and then verifying
  with `grep -n` + `ast.parse`. Both silent patch failures in this session were caught by that habit.
* This sandbox has no network egress except the agent's own page-fetching tool (`curl` to
  drivendata.org → `SSL_ERROR_SYSCALL`, `urllib` → TLS EOF). Anything that must be *live* belongs in the
  GitHub-hosted workflow, which is why `.github/workflows/feed.yml` exists instead of a cron in here.

---

## N-8 · Declaring something unrecoverable before fetching the remote

We wrote, in `knowledge/00` and on the site, that the brief's verbatim wording could not be recovered: the
checkout had one commit and no brief file. That was true of the *working tree* and false of the
*repository* — `origin/main` had two further merged PRs, and `git show origin/main:README.md` §8 contains the
prompt verbatim. Recovered at 22:35 UTC, and it corrected a real claim on the way in (the radiometric clause
is conditional in the original, absolute in our reconstruction).

**Rule:** before writing "not available anywhere", `git fetch && git ls-tree -r origin/main --name-only`, and
`grep` the merged branches. In a family of repos where siblings merge into the same `main`, the branch you
were cut from is not the repository.

---

## N-9 · A GitHub Actions workflow that has never run is not "done" (found 22:26 UTC)

`.github/workflows/feed.yml` — the thing the whole "you never have to check the site by hand" promise
rests on — failed twice in 0 seconds with **no log and no job**, because an inline `python - <<'PY'` block
inside a `run: |` scalar had lost its indentation when that block was edited. A block scalar ends at the
first non-indented line, so the file stopped being valid YAML, and Actions rejects it before any step
runs. Nothing in the repo noticed: `pytest` did not parse it, `check_site.py` did not read it, and the
site itself was fine, so the *absence* of the problem looked like its presence.

Fixed by re-indenting the step, and then by making the repo unable to forget: `tests/test_workflows.py`
now (a) `yaml.safe_load`s every workflow file, (b) asserts the feed workflow contains the refresh, commit
and "fail loudly" steps, (c) asserts the commit step touches only `docs/data/` — publishing a raster stays
a human act — and (d) asserts the fetcher stays stdlib-only so a package index cannot freeze the board.

Two things this exposed that are worth keeping as rules, not as fixes:

* **The runner has no scientific stack, so any verification that needs one must decline rather than
  degrade.** The generated `docs/downloads/index.html` re-runs the format gate on every staged raster,
  which needs `rasterio`; on a runner without it the page used to be rewritten with "gate not run" for
  every file — a safety table silently emptied. It now leaves the committed version alone and logs that it
  skipped (see `download_index`).
* **A lint that misfires is worse than no lint.** The first version of that test re-derived YAML's
  block-scalar indentation rule with a regex and failed on valid YAML; deleted. `yaml.safe_load` is the
  authority, and the test says so in a comment so nobody re-adds the clever version.

---

## N-9 · The whole-component hide-and-recover simulator does not predict the organiser's score

**What was run.** All 13 restored scored rasters, 4 spatial folds each. Held-out truth = whole
8-connected catalogue components assigned to spatial blocks by majority vote, thinned to the inferred
prevalence. Emission = each file's own pixels restricted to that fold's legal set, plus a mass-matched
uniform-random control on the same folds. Scored with `src/gems52/metric.py`, the transcription pinned
by `tests/test_metric.py`. Scripts: `work/a6_calibrate.py`, `work/a10_calibrate2.py`.

**Result.**

* Spearman ρ(reported score, simulated DTI) = **−0.1045**, p = **0.734**, n = 13.
* Spearman ρ(reported score, simulated lift over random) = **−0.1265**, p = 0.680.
* `h33-2-b2`, the group's best file on the board (0.2778), is the **worst** of the 13 on the
  instrument: simulated DTI 0.0046 against 0.0496 for mass-matched random, lift **0.09×**.
* `8GEMSDOE_Hedge-v2` ranks **first** on the instrument (0.316, lift 4.19×) and scored **0.1563**.

**The confound was checked and is not the explanation.** The first run let hidden truth sit inside the
200 m ring that a corridor-excluding prior may not enter, which structurally handicaps exactly the
files that obey the rule. Restricting the hidden truth to pixels more than 200 m from the *visible*
catalogue (`work/a10`) moved the champion's lift from 0.10 to 0.09 and left ρ unchanged.

**What it kills.** Every selection this repo made through that gate, including the
`promoted: false, forced: true` decision recorded in `docs/data/submission.json` and the "+33 %"
corridor effect quoted in `knowledge/02` H52-2 as the primary emitter arm. The premise of the
instrument is that the hidden truth is a held-out part of the mapped catalogue; `knowledge/10` §2–§3
measure that the hidden truth does not come within 200 m of the mapped catalogue at all. The premise is
false, so the instrument measures the wrong quantity and its ordering carries no information — ρ ≈ 0 is
not a weak signal, it is the expected reading for an instrument pointed at the wrong target.

**Rule adopted.** A validation instrument is only an instrument if it reproduces the ordering of
artefacts whose real scores are already known. We hold 13 such artefacts. Any new instrument must be
calibrated against them before it is allowed to promote anything. This one was not, and fails.

**What replaced it.** Exact set algebra over five scored files that stand in verified nesting
relations (`A ⊂ B ⊂ E`, `C ⊂ E`). That yields `|G|`, the dead ring, and an exact interval on the
credit carried by the double-corroborated atom — see `knowledge/10`. It is arithmetic on artefacts the
organiser has already scored, which is the only ground truth available without portal access.

## N-10 · No point or local-differential feature re-ranks inside the champion file

**What was run.** 63 features — the 19 competition bands, their horizontal gradients, Laplacians and
5×5 ranges, linearity ratios (gradient over local standard deviation), all 12 LiDAR scarp bands, the 4
radiometric bands and 4 ratio bands, and the SGMC layer — scored against the credit hierarchy of
`knowledge/10` §3, with AUC computed inside each of the 4×4 spatial blocks that contain both classes
(10–11 blocks) and averaged. Script: `work/a12_atoms.py`, output `work/a12_feature_auc.json`.

**Result.** Best AUC(`P1` vs `P2`) = **0.5453** (`lin_detelev`, sd 0.008); next `sc_step_max` 0.5453,
`sc_downface` 0.5419, `rad_K` 0.5399. That is the maximum of 63 tests, so after multiplicity it is not
a signal. Best AUC(`P1` vs `P5`) = 0.5376, AUC(`P1` vs `P6`) = 0.5451 — the same nothing.

**The part that matters more than the null.** The *habitat* signature is strong and it is not credit.
AUC(`A` vs uniform random) reaches **0.7023** for `ddetelev_range5`, 0.6605 for `ddetelev_hg`, 0.6522
for `sc_upface`, and 0.6494 for inverted `rad_K` — the champion's dots sit on radiometrically depleted,
high-relief ground. But `P2`, `P5` and `P6`, which carry 4–20× less credit per pixel than `P1`, have
almost the same habitat AUCs against random (0.7023 / 0.6802 / 0.6834 for `ddetelev_range5`).

**What it kills.** Any plan whose argument is "train a classifier on the credited tier, then emit its
top-K and expect the credited tier's credit density". The classifier learns the habitat, and habitat
does not separate credited from uncredited mass. This is a stronger and more specific statement than
N-6's "supervised detectors trained to reproduce the catalogue fail": here the target is not the
catalogue but the group's own organiser-credited pixels, and it still does not transfer.

**Rule adopted.** `ρ_novel` — the credit density of mass this repo has never emitted — enters every
projection as a *prior* with a stated range, never as a point estimate. See
`src/gems52/revealed.py::budget_rule`.

## N-11 · Structure-tensor coherence does not re-rank inside the champion file either

**What was run.** Coherence, gradient magnitude and coherence × gradient magnitude from the structure
tensor, at σ = 2, 4 and 8 px, on 12 bands (gravity anomaly, RTP, detrended elevation, TMI horizontal
gradient, gravity horizontal gradient, depth to base of basin fill, second invariant of strain, TMI,
detrended-elevation slope, tilt curvature, conductivity, shear rate) — 108 features, same blocked AUC
protocol. Script: `work/a13_coherence.py`.

**Result.** Best AUC(`P1` vs `P2`) = **0.5122** (`tc` gradient magnitude at σ = 2, se 0.0032), i.e.
worse than the point features. Coherence itself never exceeds 0.5066 on that contrast.

**What it does *not* kill.** Coherence of the credited dot *cloud* — as opposed to coherence of a
geophysical band — is strongly non-random: mean 0.549 against 0.412 for a matched uniform-random cloud
at σ = 6 px, and 16.8 % of credited dots above coherence 0.8 against 2.2 % of random dots (7.6×). The
two independent thinnings `A` and `C` agree on the recovered orientation histogram to cosine
**0.9952** while the random control is flat, and the dominant recovered strike is 100–110° in array
convention = azimuth ≈ 010–020°, the NNE–SSW Basin-and-Range normal-fault strike of this footprint.
So the *fabric* is recoverable and geologically correct; what is not recoverable is which individual
dots on it were right. That distinction is what H54-2 is built on (`knowledge/11`).

## N-12 · Radiometric alteration ratios are not an alteration signal here

**What was run.** The 4 external radiometric bands (K, Th, U, TC) and 4 external ratio bands (Th/K,
U/K, U/Th) plus band 6 `tc`, against the credited tier, same blocked protocol (`work/a9`, `work/a12`).

**Result.** All four channels are strongly depleted on the credited dots — `rad_K` AUC 0.3506,
`rad_TC` 0.3702, `rad_Th` 0.4075, `rad_U` 0.4279 against random — while all three *ratios* sit within
0.05 of chance: `ext_ThK` 0.4959, `ext_UK` 0.5723, `ext_UTh` 0.5547.

**What it kills.** Hypothesis H54-4 as a standalone emitter. Depletion in K, Th and U *together* with
unchanged ratios is bare rock and thin soil on steep ground — the same habitat `ddetelev_range5`
already captures at 0.6664 — not hydrothermal alteration, which moves the ratios and leaves total
count roughly alone. The bands are kept as View B features; the alteration-halo claim is withdrawn.

## N-13 · A per-block AUC of 1.000 over n = 3 samples

The first H53 build reported View A and View B block AUCs including a block with **1.000**. That block
held **3 labelled samples**. `scripts/build_revealed_submission.py` now tags every block with
`counted_in_mean` (n ≥ 500) and reports the mean over counted blocks only, alongside the raw list, so
a degenerate block can inflate nothing. Reported means after the fix: View A 0.7031, View B 0.9241.

The general rule, which is the same one N-8 states about read-backs: **an aggregate that silently
includes a degenerate subgroup is worse than no aggregate.** Report the n next to the statistic.

---

## Added by H55 (2026-10-07). Same rule as the rest of this file: a negative result is written down with
## the number that makes it negative, so the next session does not re-derive it.

**N-15 — the potential-field view fails the H55 promotion rule; its mean comparison with random is mixed.**
With the view split corrected (band 6 moved out, N-18) and placement fixed (400 m hard-core),
`A_only|hc4|37654` has mean DTI **0.02979 hide / 0.02894 tip** against matched-budget random
**0.03948 / 0.02477**: below random on `hide`, but above random on `tip`. It wins **1/4 hide** and
**2/4 tip** folds, so it fails the preregistered requirement of at least 3/4 wins on **each** instrument.
This is a failure of the promotion threshold, not evidence that both instrument means are below random.
N-6 predicted weak potential-field ranking at the layer level (transform AUC ≈ 0.52 at a 300 m cell);
the H55 fold counts likewise do not qualify View A as the primary emitter. *Leaves open:* potential-field
layers as corroboration inside a Phase-2 reasoning record, where they cost nothing. The separate
conditional-independence test is recorded in `evidence/h55_verification_20261007T0150Z.json`.

**N-16 — every blend of the two views scores at or below the surface view alone.** `AB_w80`
(0.8·B + 0.2·A, both regionally centred) = 0.09112 hide / 0.05358 tip; `B_c50` alone = 0.09112 / 0.05421;
`B_c100` alone = 0.09167 / 0.05448. The geometric mean, the arithmetic mean and the min were all worse again
on the single-fold run. *Kills:* the two-view premise as a source of ranking improvement, for the third
time, now with the split corrected. *Leaves open:* View A at a coarser cell (≥300 m) used to *gate* a 100 m
surface detection — a different experiment, and the only version the measurements do not already exclude.

**N-17 — the disagreement strata, used as a modulator of the ranking, make it worse.** Boosting View B where
A is confident and B abstains (`Bdis_A`) scored 0.06776 on `hide` fold 0; damping it where B is confident and
A abstains (`Bsup_B`) scored 0.06902; unmodulated `B_only` scored **0.07387** at identical emitter, budget,
mask and fold. *Kills:* the "A-confident/B-abstains ⇒ buried fault, so rank it up" move — the brief's central
discovery mechanism — which this repo has now tested as a pseudo-label source (N-1, refuted) and as a rank
modulator (refuted). *Survives:* the strata as a **description**. A-only pixels do sit in materially deeper
cover (mean depth-to-basement rank 455 vs 251 for concordant) and do carry a larger gravity step (6.06 vs
2.59). A real population fact is not a ranking signal.

**N-18 — the correction that makes N-15 to N-17 mean what they say.** Band 6 of the organiser's own
`training_features.tif` is the GeoDAWN **aeroradiometric total-count** grid, not the "tilt angle or total
curvature — magnetic field derivative" its TIFF tag claims: Spearman **+1.0000** against the independently
reduced USGS TC grid (DOI 10.5066/P93LGLVQ), **+0.9914** against K+Th+U (which is what a total-count channel
*is*), |ρ| ≤ 0.149 against all five magnetic bands in the same file, and strictly positive (2.953 … 88.573)
where a tilt angle is bounded by ±π/2. `src/gems52/features.py` filed it in **View A** as `A_mag_tilt_abs`, so
every independence measurement this family ever took had a surface-geochemistry band inside the
potential-field view, which inflates any A↔B correlation and makes the "views miss the same neighbourhoods"
reading partly an artefact of the mis-filing. **IR-52-019 corrects IR-52-001.** *Kills:* the sentence
"training_features.tif contains no radiometric band", which appears in `knowledge/04`, `knowledge/06`,
`docs/irregularities.html`, `docs/data/prepared_manifest.json` and `src/gems52_h1/spec.py`. *Does not kill:*
the H52 holdout numbers — still valid measurements of the H52 field, just of a field with a mis-assigned band.

**N-19 — the conditional-independence premise is REFUTED, and the test that refutes it finally fires.** The
pre-registration said: correlate the two views' per-block out-of-fold error on labelled negatives across
spatial blocks, abandon if strongly correlated (`ABANDON_R = 0.60`). In H52 this **could not fire** — fewer
than three usable blocks, Spearman degenerate to 1.0 on ties — so N-1 correctly recorded the premise as
*unmeasured*. On the corrected split: **40 usable blocks of 62** per fold, **4/4 folds of both instruments**,
max |Spearman| = **0.7625** (`hide`) and **0.7107** (`tip`). *Kills:* co-training, on the brief's own
criterion, and the hope that a better block statistic would rescue it. *Two qualifications that must travel
with the verdict:* the false-alarm-rate-at-fixed-budget statistic correlates weakly (max |ρ| 0.2494, negative
on 3 of 8 folds), so this is the verdict of the statistic the pre-registration **named**; and View A's
block-level FAR has CV 1.35–5.22 against View B's 0.75–1.18, i.e. View A finds a few regional anomalies and
nothing else — a third independent route to N-2 and N-15.

**N-20 — the thermal-fluid layer is neutral at a 37,654 px budget, and "neutral" is the finding.**
`B_therm` (View B centred, plus INGENIOUS/GDR thermal lineaments injected as a rank bonus) beat `B_c50` — the
identical field without them — by **0.00003** on the selection sum (0.15171 vs 0.15168), 4/4 folds on both
instruments each. Only **3,340** of 5,165,840 footprint cells carry a thermal lineament, because the walk is
gated by structure-tensor coherence (median 0.106; 643,745 cells clear the 0.30 floor). *Kills:* the claim
that this file is better because of the springs. It is not. *Leaves open:* a much larger budget, where 3,340
high-conviction cells are a bigger share of the file, and a lower coherence floor, which would lengthen the
traces at the cost of inventing some. Both untested, both cheap, neither claimed.

**N-21 — our own coverage-greedy was worse than top-K, and that was a bug, not a property.**
`np.maximum(cf[nbi], kk, out=cf[nbi])` writes into a throwaway copy, because fancy indexing copies. The
running cover was never raised, every later candidate looked uncovered, the greedy packed into the belief
field's peak and reported `A/S` = 1.8–2.1 with DTI 0.0115 on the fold where the hard-core rule reached
0.10101. An earlier draft of `knowledge/12` recorded that as "the greedy under-spreads when ρ̂ is peaked";
the claim is **withdrawn**. Fixed, the greedy reaches `A/S` = 9.27 (98.8 % of ceiling) and banks 20 % more
ρ̂-weighted coverage than hard-core thinning and 33 % more than top-K, on both a flat and a clustered belief.
**IR-52-025.** *Kills:* the plan "improve the placement by improving the greedy's objective" — the objective
was already right. *Teaches:* `out=` with a fancy-indexed destination is a silent no-op, and the telescoping
identity `sum(marginal gains) == Σ ρ̂·K_E` is the one-line test that catches it.
