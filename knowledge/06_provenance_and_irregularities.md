> **Historical report — superseded where contradicted by R2.** See `09_r2_review.md` and `evidence/reference_forensics_r2.json`. In particular: known pixels do not pay penalties; H33 removed off-catalogue flanks; the old OOF independence report contained no negative predictions; hidden prevalence and a 0.464 ceiling are not established.

# 06 · Provenance and the irregularities register

The machine-readable twin of this file is `docs/irregularities.html`; this note is the version that keeps
the *reasoning* about each item, because a register without reasoning gets re-litigated every session.

## 1. What is verified how

| claim | verification | strength |
|---|---|---|
| metric formula, constants (α=0.2, β=0.8, R=300 m=3 px), kernel `k(d)=max(1−d/R,0)`, format rules (single band float32 in [0,1], EPSG:32611, 100 m, same bounds, null/NaN outside footprint), two rounds with a blind final pick | official page 967, re-read 2026-10-06 21:33 UTC; `src/gems52/metric.py` reproduces the page's own worked example (3.00/1.89/2.00 → 0.60) in `tests/test_metric.py` | **strong** — code + page agree |
| mask is pixel-exact to the training labels; only new-fault truth counts; near-trace predictions are penalised unless new truth is there; new truth *may* sit within 300 m of a known trace | chrisk-dd (organiser staff), community thread 11516 post #4, 21 Sep | **strong** — staff statement, and it changed our design |
| Phase-2 pool = test set updated by expert review of all Phase-1 submissions; no details of test faults | chrisk-dd, community thread 11527 post #7, 23 Sep | **strong** |
| board contents (24 rows, #1 0.3774, #13 this group 0.2778, column header "Best public DW-Tversky (in descending order)", submission counts 11 / 10) | fetched twice, 21:2x and 21:33 UTC, byte-identical; committed to `registry/leaderboard_snapshot_2026-10-06.json` | **strong for the board itself** |
| "the file that scored 0.2778 was `h33-2-b2`, = `h27-4-r1` minus 2,545 masked pixels (40,199→37,654)" | sibling-session owner report; the raster is **not** in this checkout, and the board carries no filename/hash/receipt | **weak** — arithmetic reproduces from files we do have, the pairing does not verify |
| every DTI, gate, fold, strata and layer-screen number in `evidence/` | computed in this repo from the pinned input rasters (`scripts/prepare_data.py` verifies 23 sha256 pins) | **strong and reproducible** |
| band inventory (19 bands; no radiometric channel) | organiser's data README, published as `docs/data/band_inventory.json` | **strong** |
| external datasets in `knowledge/04` | one live metadata/request probe each, with the exact query string recorded; **no bulk download from this environment** | **medium — deliberately labelled per row** |

## 2. Register

**IR-52-001 — there is no radiometric band.** Sibling notes mention gamma-ray features. The provided data
has 19 bands, none radiometric. Any feature builder that silently emits `B_gr`-like channels is wrong.
*Mitigated*: features are checked against the published inventory.

**IR-52-011a — the standing brief's View-B definition names "any radiometric bands in `training_features.tif`".**
Read strictly the clause is conditional, and the condition is false: the official file carries 19 bands and
none is radiometric (`IR-52-001`, `evidence/band_inventory.json`). The conditional is therefore satisfied
vacuously, not contradicted — but a builder that reads only the brief will look for bands that do not exist.
*Resolved*: View B takes radiometry from the GeoDAWN external bundle (`data/external/geodawn_rad_u8.tif`,
4 bands: K, Th, TC and the Th/K ratio, plus `geodawn_extensions_u8.tif` band 1), hash-pinned in
`registry/data_manifest.json`; the code path is `src/gems52/dicoincidence.py::CHANNELS` family
``radiometric``.

**IR-52-002 — "0.3195 is the highest score right now" is stale.** It is rank #7 (DARD). The live top is
0.3774 (xiaofanhu, 11 submissions), so the gap the group must close is 0.0996, not 0.0385. We flag the
user's number rather than adopting it, because acting on a remembered board is how a team optimises a
target that no longer exists.

**IR-52-003 — file↔score mappings in this family are owner reports, not organiser data.** The public board
shows a team and a number, and nothing else. The 0.2778 attribution to `h33-2-b2` is used on this site only
where the *mechanism* is what matters (deleting 6.3 % of one's own mass, all of it overlapping the mask,
raised DTI 2.6 %), and the file itself is not in the checkout. Stated on the site in the same breath as the
number.

**IR-52-020 — the session-2 brief's "0.3195 is the highest score right now" is the *brief's* number, and the
board says 0.3774.** This is the same disagreement as **IR-52-002** (where it is recorded as a stale user
number); it is listed again under the number the brief itself uses, `IR-52-020`, so that a reviewer holding
the brief and this register side by side can find the entry without having to know our internal numbering.
Both readings are true of different moments: 0.3195 is a real row (rank #7, DARD, 10 submissions) in
`registry/leaderboard_snapshot_2026-10-06.json`, and 0.3774 is the live #1 (xiaofanhu, 11 submissions) in
the same fetch. The operational consequence is the one already recorded: the gap to close is 0.0996, not
0.0385, and any target quoted from a memory rather than a fetch is treated as stale.

**IR-52-022 — we overwrote our own uncommitted work, and recovered it from the bytecode.** The H53-1
detector was written earlier in this session but never committed. While restoring it, two of its files were
replaced by rewrites: `src/gems52/structure.py` (overwritten by a draft with a different API, which broke
`dicoincidence.py` and `tests/test_structure.py` until noticed) and `scripts/validate_h53.py` +
`scripts/h53_detect.py` (replaced by this session's rewritten versions of the same procedure).
*Recovery, and its limits*: `structure.py` was recovered from the module's verified bytecode
(`src/gems52/__pycache__/structure.cpython-311.pyc`, compiled from the pre-overwrite source — the pyc records
the source's size and mtime, both of which match the lost file and not the draft), including its docstrings
and numerical steps; the reconstruction is checked **behaviourally** against the loaded bytecode module on
synthetic line/noise/mixed fields (max absolute difference < 1e-6 on energy, coherence, azimuth and the
along-strike persistence), and the one latent defect in the lost source (`with_lambda=True` referenced
unbound globals `lam1`/`lam2`) is fixed rather than reproduced. The two scripts are **not** recoverable —
they had no bytecode cache — so what survives of the pre-registered H53 gate is its rule, recorded in
`registry/preregistration_h53.json` with an explicit provenance note and the timestamps that show the gate
ran before the submission was written. The mitigation is the obvious one and is this session's action: the
whole H53 module set and its scripts are committed in the PR that closes this session, so a later rewrite
cannot destroy work that the repository already holds.

**IR-52-021 — the brief's "single remaining blocker to training is data placement" is stale in this
checkout.** That sentence describes the state of a *different* sibling checkout. Here `scripts/restore_data.py`
has already run to completion: `data/restore_receipt.json` exists, `ALL_VERIFIED=True`, 23 sha256 pins
verified, 907 MB of rasters present (`training_features.tif` 418,912,844 B, `labels.tif` 425,830 B,
`sample_submission.tif` 1,599,597 B). No `download_competition_data.sh` run is needed or possible from this
sandbox (egress-restricted). Consequence: any session that re-runs the restore or treats data placement as
the blocker is spending its budget on a solved problem — the real binders are the weekly submission limit
and the fact that the only offline truth is the catalogue itself.

**IR-52-004 — the rules document's host differs from the brief's citation.** `docs.nlr.gov` is cited; the
document resolves at `www.nlr.gov/docs/fy26osti/96647.pdf`. Not a contradiction, but a link that a human
following the brief would 404 on, so both are printed on `docs/sources.html`.

**IR-52-005 — `sample_submission.tif` contains 60,988 positive pixels, all of them on labelled fault
pixels.** A sample submission that is *not* empty, in a competition whose metric penalises catalogue
overlap. Two consequences: copying it is forbidden by the brief and would also be a metric own-goal.
*Mitigated*: emission is computed on `valid & ~catalogue`, and `gates.uniqueness_report` fails a candidate
whose mass is a subset of a prior's.

**IR-52-006 — the rules page and the portal validator disagree about no-data.** Page: "null or NaN where
there is no data". Validator: values must satisfy `0 ≤ v ≤ 1`, which NaN cannot. Writing 0.0 outside the
footprint is scoring-identical and passes both, so that is the encoding; NaN anywhere in a candidate is now
a named gate failure. This is the actual mechanism of the historical "Predicted values must be in range
[0, 1]" rejection.

**IR-52-007 — we shipped a bug in our own writer tonight, and the gate caught it.**
`grid.write_geotiff` built its affine with `from_origin(TRANSFORM[2], TRANSFORM[0], TRANSFORM[4],
TRANSFORM[5])` instead of `(c, f, a, −e)`; the first file written today therefore had
`transform (-100, 0, 243350, 0, -4508550, 100)`, `res [100, 4508550]` and a southern bound of −1.68e10 m.
`gates.format_report` compared it against `data/sample_submission.tif` and returned
`format_ok=False` with three named problems, so nothing reached the site in that state. The rejected file's
sha256 (`427159429ffcc206…`) and its evidence record are kept under
`evidence/submission_*-r1-rejected-transform.json`; the bytes are not in the repo.
*Fixed*: the writer now builds `Affine(*TRANSFORM)` and asserts the reconstruction (cell size 100 m, origin
from `c,f`) before writing, and `read_geotiff` re-reads the file so the receipt describes the bytes, not the
intent. Recorded here because "the gate found a bug in the thing that writes the gate's input" is the
evidence that the gate is real.

**IR-52-008 — the brief's verbatim wording is unrecoverable in this workspace.** Single commit, no brief
file, `grep -rl "Blum"` hits only our own module. Restated faithfully in `knowledge/00` with this
provenance note; no quotation marks were invented.

**IR-52-009 — this sandbox has no network egress** (`SSL_ERROR_SYSCALL` / TLS EOF for
`www.drivendata.org`). Live fetching belongs to `.github/workflows/feed.yml`; anything timestamped as
"live" in the sandbox came through the agent's page-fetch tool, and says so.

**IR-52-010 — the pre-registered promotion gate failed for the brief's own mechanism.** Co-training
pseudo-labels: −0.0158 (tip) and −0.0303 (hide) DTI against the naive union at equal budget, 0/4 fold
support on both instruments, `promoted=false` on both. Published, not buried; the disagreement *strata*
survive, the label round does not. No submission slot was spent.

**IR-52-011 — the first pre-registration's blend weights were asserted, not fitted**, and point the wrong
way for this population. Any re-weighting must appear as a *named arm* in `evidence/holdout_*.json`, never
as a quiet config change; `wt_A20B80` exists precisely to make the fitted version auditable.

**IR-52-012 — closed. The file was built nine minutes before the composite sweep finished** (corridor share
0.0 by explicit command line rather than by sweep verdict); the sweep then selected that same configuration,
and rebuilding from `evidence/composite.json` reproduced the identical sha256, so the interim state is now
only a provenance footnote. What replaced it in the record is the *substantive* caveat: The two extremes are both measured
(`union_cor|37654` 0.0320 tip / 0.0001 hide; `B_only|37654` 0.0291 / 0.0518), so the selection record in
`evidence/submission_*.json` says `selection_source: explicit --far/--cor/--split`, `promoted: false`,
`forced: true`. the sweep's control bar was misdefined in its first version (a
`max`-over-random-variants control that handed the corridor arm its own score as the bar to beat), and
`evidence/composite.json` now stores both selections. Fixed rule: `beats_random_all: true`
(tip +16.7 %, hide +32.1 % over matched-budget random), `beats_union_bar: false` (+0.0051 on tip against the
registered +0.010), `promoted: false`. Every interior split that funds the corridor scores lower on the
sum — see `knowledge/05` §3b.

**IR-45-001 (inherited) — the footprint area disagrees across the family**: 5,165,852 / 5,165,840 /
5,167,373 px. We recount → **5,165,840** (catalogue 60,894 px = 1.1803 % of it; the third number is a mask
definition with a 1-px collar). All fractions on the site are against the recount.

**IR-52-013 — the board implies the weekly limit is being consumed by the leaders.** xiaofanhu has 11
submissions at the top, our team 10. Nothing about this repo's schedule assumes we can iterate on the
leaderboard freely; that is what the two instruments and the register are for.

## 3. Three passes, what each one did (as the brief requires)

* **Pass 1 — build.** Metric, grid, features, co-training, holdout, gates written from the official pages;
  inputs pinned by sha256; metric unit-tested against the page's own worked example.
* **Pass 2 — re-derive independently.** Re-fetched the board (identical), recomputed the arm tables on both
  instruments, re-read every claim on this site against its `evidence/*.json`, wrote the register above, and
  cross-checked the 0.2778 mechanism against the sibling rasters actually present.
* **Pass 3 — try to break the publication path.** `scripts/check_site.py` (committed): dead links, JSON the
  JS asks for but the feed never writes, unbalanced inline scripts, hard-coded numbers on the numbers page,
  and a byte-for-byte re-serve of the .tif through a local HTTP server. It is this pass that surfaced
  IR-52-007 (writer transform), the `exists` flag the hero block needs, the missing
  `feed.html`/`irregularities.html`/`sources.html` that the nav pointed at, a TDZ bug in `feed.html`'s
  inline script, two page scripts that did not parse at all (`docs/tables.js`, unbalanced row-array
  literal; `docs/exec.js`, `a && b ?? c`), and the 0-byte-NaN encoding question that became IR-52-006.
  Six of these were invisible in the browser: a broken script on a data-driven page renders as "no data",
  which is why `check_site.py` parses the JS instead of loading the page and eyeballing it.

## 4. What would change our mind

1. `evidence/composite.json` selecting an interior corridor share that passes rule 1 on both instruments.
2. A relocated ComCat layer (D-1) that ranks far-field mass better than `B_only` on the hide instrument —
   the only incumbent we have not yet beaten.
3. Well-based stratigraphic offset (D-3) confirming or killing H52-1: if the marker bed does not step
   across an A-only structure, the "buried range-front fault" story is an artefact and the A-only stratum
   should stop informing the ranking at all.

**IR-52-016 — the scheduled board fetch reaches the page and reads nothing.** First CI run, 22:28 UTC:
HTTP 200 from `www.drivendata.org` (so GitHub's egress is fine, unlike this sandbox's TLS EOF), then
`leaderboard table parsed empty — page layout changed`, because the board table is built client-side and the
server HTML contains no `<tr>` rows to parse. The parser raises rather than publishing an empty board; the
run fell back to the dated snapshot and reported why. **Consequence for how this site must be read: "live
data feed" means live-attempted, snapshot-served for the leaderboard** — every other number on the site comes
from `evidence/`, which we generate ourselves, and is genuinely regenerated on every push. Closing this needs
a data endpoint the organiser publishes; guessing at one is not a fix, so the status line stays visible
instead.

---

## Additions from the H53 round (2026-10-07)

The register on [the site](../docs/irregularities.html) is authoritative and is generated by
`scripts/make_site_pages.py`; these are the one-line summaries so that `knowledge/` does not send a
reader to HTML for a fact.

**IR-52-017 — the validation instrument does not predict the organiser's score.** Spearman
ρ(reported, simulated DTI) = −0.1045, p = 0.734, n = 13 over every restored scored file. The group's
best file on the board ranks *last* of 13 on the instrument (lift 0.09× mass-matched random) and the
file the instrument ranks first scored 0.1563. Full measurement and the confound that was checked and
excluded: `knowledge/03` N-9. **Every selection made through that gate inherits the defect**, including
the `promoted: false, forced: true` decision recorded in `docs/data/submission.json` for the H52 file.

**IR-52-018 — the ≤200 m ring around the mapped catalogue earns exactly zero credit.**
`h33-2-b2` (0.2778) ⊂ `gems24-d2-8` (0.2600); the 6,436 px difference lies entirely inside 200 m of a
mapped trace and deleting it *raised* the score 6.8 %. `min` distance-to-catalogue inside `h33-2-b2` is
223.6 m, so it holds 0 px in the ring. This **contradicts** `knowledge/01` §5 item 2 and `knowledge/02`
H52-2, which made ranking that ring the primary emitter arm; §5 item 2 is now struck through with the
measurement. The staff claim that the mask is pixel-exact survives as a statement; the bytes say scoring
behaves as if there were a ~2 px ring, or as if the hidden truth never comes within 200 m. Both readings
give the same rule and the bytes cannot separate them.

**IR-52-019 — no feature available here re-ranks inside the champion file.** Best blocked AUC on the
credited-vs-uncredited contrast: 0.5453 over 63 point/local-differential features (the maximum of 63
tests), 0.5122 over 108 structure-tensor features. Habitat is strongly identifiable (AUC 0.7023 for the
champion's dots against uniform random) and strongly useless — the tiers carrying 4–20× less credit have
habitat AUCs of 0.68–0.70. `knowledge/03` N-10, N-11. Consequence: `ρ_novel` is a stated prior, never a
point estimate.

**IR-52-020 — a per-block AUC of 1.000 over n = 3 samples** appeared in the first H53 build. Blocks now
carry `counted_in_mean` (n ≥ 500) and the mean uses only counted blocks; the raw list is kept.
`knowledge/03` N-13.

**IR-52-021 — `gates.find_priors` treated competition inputs as prior submissions.** Sweeping a root
containing `data/training_features.tif` read band 1 of a 19-band feature stack as somebody's answer and
produced a "prior union" of 5,363,764 px against a 5,167,373 px footprint, which silently emptied the
novel-pixel pool to 93 px. Fixed with a `NOT_A_SUBMISSION` skip list plus
`tests/test_gates.py::test_find_priors_skips_competition_inputs`; the union is now 1,062,207 px over 18
real prior rasters.

**IR-52-022 — the downloads index was always one run behind the downloads directory.**
`refresh_feed.py` built `docs/downloads/index.html` before copying rasters into it, so the current
submission was on disk and absent from the table — the "download the file and submit it" promise pointed
at the previous round's artefact. Rasters are now staged first, and a one-click ZIP (raster + the note to
paste + the evidence JSON) is written beside the TIF.

**Carried forward, unchanged and still open:** IR-52-003 (no file→score mapping is
organiser-authenticated — every number in `knowledge/07` inherits this), IR-52-008 (there is no
radiometric band *in `training_features.tif`*; the radiometrics are the external
`geodawn_rad_u8.tif` / `geodawn_extensions_u8.tif` layers, which is what the brief's conditional clause
resolves to here), IR-52-009 (the external GDR CSVs are derived, not organiser-authenticated),
IR-52-016 (the scheduled board fetch reaches the page and reads nothing, because the table is built
client-side; the site therefore serves a dated snapshot and says so).

**IR-52-029 — two rounds shipped a submission in parallel, and this site now offers the later one.**
PR #8 merged to `main` while the H54 round was running, shipping
`gems52-h53-coincidence-gated-singles-37654px-r1.tif` (cross-dataset orientation coincidence, promoted on
the tip/hide instruments at +21 % / +28 % over the repo's previous best at that budget). This round ships
`gems52-h54-revealed-core-strike-continuation-50517px-r1.tif` and `submission/LATEST.txt` now points at
it. **That is one session's judgement call over another's shipped artefact, so it is flagged rather than
made quietly.**

The reason is a measurement, not a preference: `knowledge/03` N-9 / `IR-52-023` establish that the tip and
hide instruments carry no information about the organiser's score (Spearman ρ(reported, simulated DTI) =
−0.1045, p = 0.734, n = 13 over every restored scored file; the group's best file on the board ranks
*last* of the 13 on them). A promotion earned on those instruments is therefore not evidence about the
score. The H54 file's retained half rests on a different kind of claim — exact arithmetic on five scored
files standing in verified nesting relations, giving `t(A & C) ∈ [4,168, 5,223]` and hence
`DTI(core alone) ∈ [0.2546, 0.3190]` — which does not depend on any simulator being right.

Neither artefact is deleted. Both stay in `submission/`, both stay listed on the download page with their
own gate verdicts, and the H53 code, evidence and hypotheses keep their numbering (this round is
renumbered **H54**, `knowledge/10` and `knowledge/11`, precisely so that it does not collide). The H53
raster also becomes a *prior* for the uniqueness gate: measured prior union 1,117,016 px over 21 rasters,
novel pool 440,798 px, **0** collisions between the H54 novel mass and any prior pixel.

**Reverting is one line** — point `submission/LATEST.txt` back at the H53 file and re-run
`scripts/refresh_feed.py`. Nothing else in the repo depends on which of the two is offered.

## 6. Added by H55 (2026-10-07)

The machine-readable register **`registry/irregularities.json`** now exists — 41 entries. It was cited by
`src/gems52/features.py` from the day that file was written and did not exist until this session
(IR-52-021); `tests/test_scripts_and_registry.py` fails if any id cited anywhere in the tree is absent from
it, so the reference cannot dangle again.

| id | what | status |
|---|---|---|
| IR-52-019 | band 6 of the organiser's own feature file is radiometric total count, mis-tagged `magnetic_data` / "tilt angle or total curvature". **Corrects IR-52-001** | open — corrected in `src/gems55/radlayers.py` |
| IR-52-020 | `download_competition_data.sh` passed `--group all`, which `restore_data.py` does not accept, so the documented one-command data placement exited 2 before fetching anything | **fixed** + test |
| IR-52-021 | `registry/irregularities.json` cited by code, never created | **fixed** + test |
| IR-52-022 | prose said "3730 × 3292", which is height × width; rasterio reports width 3292, height 3730 | mitigated |
| IR-52-023 | \|G\| not published, and the H52 budget was inherited from an unrelated submission rather than derived | **closed** — \|G\| ≥ 8,128, estimate 8,129 |
| IR-52-024 | the family's best file spent 85.8 % of the kernel's placement ceiling; its contiguous ancestors 41 % | open — largest measured lever |
| IR-52-025 | **our own bug, found by our own test**: the coverage-greedy's running cover was updated through a fancy-indexed `out=`, i.e. into a throwaway, so it reported `A/S` 1.8–2.1 — worse than top-K — and that was mistaken for a property of greedy coverage. Claim withdrawn | **fixed** + test |
| IR-52-026 | **our own bug, found by our own gate**: `find_priors` scanned `docs/downloads/`, where `refresh_feed.py` stages the built raster, so the candidate was compared against a copy of itself → `identical-to-a-prior, novel = 0` | **fixed** + test |
| IR-52-027 | *(from main)* `find_priors` swept `training_features.tif` and the external layers in as prior submissions, giving a "prior union" of 5,363,764 px against a 5,167,373 px footprint | fixed on main; **main's README cites this as IR-52-021** — see IR-52-030 |
| IR-52-028 | *(from main)* the downloads index was built before the rasters were copied into it, so it was always one run behind | fixed on main; **main's README cites this as IR-52-022** — see IR-52-030 |
| IR-52-029 | three rounds have now shipped a submission in parallel; `submission/LATEST.txt` decides which one the site headlines | open, flagged — this session's choice and its reason are recorded in the entry |
| IR-52-030 | **the register's id space collided across concurrent sessions**: IR-52-021 and IR-52-022 denote different findings in this register and in main's README | open, deliberately **not** renumbered — both readings recorded and cross-referenced |
| IR-52-031 | `check_site.py`'s success line asserted "Scientific slot gate remains closed" — a claim about `approved_for_weekly_slot` it never read, which became actively false the moment an artefact shipped with that flag `True` | **fixed** — derived from the record, with an explicit "not recorded" branch |
| IR-45-001 | footprint/catalogue counts disagreeing across the family are a **mask definition**, not arithmetic: `labels ≥ 0` → 5,167,373 / 60,988; all-19-bands-finite → 5,165,840 / 60,894 | closed |
| IR-30-03, IR-30-029, IR-30-039, IR-43-001, IR-43-010 | ids allocated by sibling repositories and cited by `evidence/source_review_r2.json`; recorded so every cited id resolves, **not adopted** — nothing in the H55 pipeline depends on them | inherited |

Six of these (IR-52-020, 021, 025, 026, 030, 031) concern the *apparatus* rather than the geology, and
three of those six are bugs in code written this session, found by tests or by the apparatus itself this
session. That is the register
working: IR-52-007 was the same shape last session (the gate found a bug in the thing that writes the gate's
input), and in both cases the alternative was shipping it.

### What is verified how — H55 additions

| claim | verification | strength |
|---|---|---|
| band 6 is radiometric total count | 150,000-px Spearman against the independently reduced USGS GeoDAWN TC grid (+1.0000), against K+Th+U (+0.9914), and against all five magnetic bands in the same file (\|ρ\| ≤ 0.149); plus the sign/range argument. `evidence/h55_band6_identity.json` | **strong** — two independent sources agree exactly, and the physics (TC = window sum) is what the second correlation measures |
| the GeoDAWN release is official, free, public domain | USGS ScienceBase item 657e1d85d34e23d3533209f7 read live 2026-10-06: Glen & Earney 2024, https://doi.org/10.5066/P93LGLVQ | **strong** |
| the INGENIOUS well/spring database is official, free, CC-BY | GDR submission 1391 read live 2026-10-06, DOI 10.15121/1881483, file URL resolves. **Discharges the blocker** `knowledge/02` H52-5 recorded | **strong** — the blocker was "host unreachable", and it is reachable |
| \|G\| ≥ 8,128 | inversion of the published metric on 13 SHA-256-verified rasters; geometry exact, DTI owner-reported | **medium-strong** — arithmetic exact, one input second-hand |
| placement gain +216 % on `hide` fold 0 | one field, one permitted set, one budget, one mask, one fold, two emitters, the tested metric | **strong for the fold**, explicitly not a board forecast |
| `A_only` fails the ≥3/4-fold promotion gate on both instruments; its mean is below random on `hide` and above random on `tip` | 4 folds × 2 instruments, matched-budget random in the same permitted set (`evidence/h55_sweep_hardcore.json`) | **strong for the recorded fold comparison** |
| the conditional-independence premise is refuted | 40 usable blocks of 62, 4/4 folds, both instruments, the statistic the pre-registration named | **strong for that statistic**; the FAR statistic disagrees and is printed beside it |
| the thermal layer is neutral | selection-sum margin 0.00003 over the identical field without it | **strong as a null result** |
| the shipped bytes are what the record says | `scripts/verify_h55.py` re-reads the file: 23/23 checks, `PASS3_ALL_OK=True` | **strong** |

### What would change our mind — H55 version

1. A 60–80 k file scoring higher than this one. The fold `T(S)` curve is flat over 37,654–70,000 px, and the
   selection rule preferred the smaller mass on a near-tie; if the larger budget wins on the board, the fold
   curve misled us and should be re-derived at board prevalence (0.157 %, not 0.2 %).
2. View A becoming promotable at a coarser cell. N-15 excludes it at 100 m, which is the scale the metric
   scores; it does not exclude a 300 m product used to *gate* a 100 m surface detection.
3. A coherence floor below 0.30 on the thermal strike walk. At 0.30 only 3,340 cells survive and the median
   coherence is 0.106, so the floor is doing nearly all the work — and its value was set by inspection, not
   by a sweep. That is the weakest tuned constant in the shipped pipeline, named here so nobody has to find it.
4. An organiser answer to forum thread 11527, or to a question about the public test set's truth-pixel count
   or whether out-of-footprint mass is taxed. Either would replace an estimate with a measurement.

## 7. H55-EDGE negative result (separate from the main H55 and H55-PROFILE)

**H55-EDGE did not earn a weekly slot.** Its preregistered spatial holdout lift over View B was +0.000546, positive in 2/4 folds, below the required +0.005 and 3/4. The strict support-novelty gate also failed. The model output is retained as a research-only artifact; it has no portal upload, organizer score, or acceptance receipt. It does not replace `submission/LATEST.txt`, the main H55 candidate, or H55-PROFILE.

**Protocol deviation was discovered after the run and remains explicit.** The frozen `registry/h55_edge_preregistration.json` specified new LoG transforms for gravity bands 13/11/18 and RTP bands 2/9; the implementation transformed only bands 13 and 2. The holdout result covers only that narrower implementation. The original registration hash `12b678d62269589c42b4009ec07e38f53f325b8a4ece5e42da888f9c8e01c401` is unchanged and reconciled with `evidence/h55_edge_holdout.json`, `evidence/h55_edge_protocol_deviation.json`, and `evidence/h55_edge_submission.json`; do not retroactively alter it or tune the omitted channels on the same folds.

The 816-row A-only reasoning table has 816 distinct measured explanations; 801 rows have zero paired sigma-3 gravity/RTP edge response. The notes report the actual band 15/19 and signed-LoG values and alternate non-fault explanations. These are learner-stratum points, not confirmed faults or independent field observations. See [the H55-EDGE page](../docs/h55-edge.html), [the per-pixel CSV](../evidence/gems52-h55-grav-rtp-logedge-37654-c4b8c10205da-zeros-a-only-reasoning.csv), and [the full protocol-deviation receipt](../evidence/h55_edge_protocol_deviation.json).

The H55-EDGE result was executed before the origin/main integration. [Its provenance receipt](../evidence/h55_edge_execution_provenance.json) records hashes for the exact pre-merge source snapshot preserved in commit `709ac3b376e9f4d102de41865ae30f4a3dd0b728`. The later merge changes shared H55/R2 modules, so a rerun from the current tree is not the same execution. The ignored training rasters and derived feature cache are not committed; the receipt explicitly limits independent rerun claims.

## 8. H58 preflight — tracked rasters diverge from the owner-mirror pins

On 2026-10-07, `evidence/h58_preflight_integrity.json` compared the decoded cells of the three tracked files under `data/` with the separate staged restore. All three tracked byte streams fail `registry/data_manifest.json`'s SHA/size pins. The GeoTIFF grid metadata matches, but the cell data do not:

- `training_features.tif`: 97,207,447 / 233,304,040 decoded values differ; 97,120,016 differ where both rasters have valid values, with 87,431 validity-mask differences.
- `labels.tif`: 120,650 pixels differ despite identical class counts. The positive masks intersect at 663 pixels; each raster has 60,325 positive cells absent from the other.
- `sample_submission.tif`: 60,988 cells differ. The tracked sample is zero-valued on its finite domain; the staged mirror has 60,988 ones exactly on its staged labels. This conflicts with the official competition page's description of its example as predicting total fault absence.

The staging restore passes all 23 manifest byte/hash checks (`work/h58_pinned/restore_receipt.json`), but this authenticates only the owner-supplied mirror against the local manifest, **not** the organizer. No tracked TIFF was overwritten. The H58 runner read `work/h58_pinned` explicitly and recorded its input hashes; it used the sample only for grid profile/finite domain, never for prediction values. Its same-input holdout re-fit View A, View B and their union rather than treating the older, un-hash-bound H57 result as a baseline.

**H58-A execution outcome (2026-10-08T00:03:04Z).** Twenty qualified sites gave 123,173 positive `F_geo` support pixels. The unique binary TIFF passed the local sample-template/grid/range check and decoded-pattern comparison against 29 accessible prior rasters, but it emitted only 22 of 37,654 requested cells (37,632 short). Both hide and block had 0/4 fold wins and failed budget comparability; the local research gate is **false**. The reported mean DTI lifts (hide −0.056556, block −0.058306) are not matched-budget evidence and must not be interpreted as a refutation of the geological hypothesis. No zero-score cells were added. See `evidence/h58_result.json`, `evidence/h58_holdout.json`, and the post-run code audit in `evidence/h58_postrun_review.json` / `IR-H58-002`.

The post-run review also found that the registered five-pixel square local-maximum prefilter in the shared emitter leaves essentially the geothermometer field's site peaks before the three-pixel spacing pass. This explains the severe support shortfall. No parameter was changed and no result-informed rerun was made. Separately, the pseudo-AUC code used five iterations of default cross-connected dilation rather than a Euclidean 500 m clearance; those AUC values are exploratory and do not satisfy the preregistered negative mask (`IR-H58-003`). This mask issue does not change the primary hide/block outcome.

The H58 candidate remains a research artifact. `submission/LATEST.txt` remains on H57; no portal upload, weekly slot, organizer score, or approval occurred. Do not spend a slot until both the critical input/label provenance issue and the registered local promotion gate are resolved. The owner-mirror run cannot establish organizer-authenticated performance even if a future local gate passes.

**Geochemistry scope correction.** The GDR 1391 page was read live and lists the well/spring geodatabase and paleo-feature archive under a CC BY 4.0 license. That verifies metadata and the listed source, not the raw bytes. The GDR geodatabase itself was not downloaded here. The pinned well/spring CSV contains derived quartz/chalcedony/cation estimates but no raw major-ion chemistry; its upstream formulas and source-table linkage remain unverified. The H58 preregistration reads only row/column, observed temperature, quartz, and cation fields; it never reads the label-derived `dist_known_fault_px` column. Only the narrow cold-discharge geothermometer-agreement hypothesis is staged for a research holdout; raw mixing-model and paleo-deposit hypotheses remain deferred.

**Disposition:** keep the three tracked rasters untouched; keep the exact pinned restore separately; preserve previous H57 receipts as historical reports but mark their input provenance unresolved; fail closed on upload approval. Receipts and frozen slate: [`evidence/h58_restore_receipt.json`](../evidence/h58_restore_receipt.json), [`evidence/h58_preflight_integrity.json`](../evidence/h58_preflight_integrity.json), [`evidence/h58_result.json`](../evidence/h58_result.json), [`evidence/h58_postrun_review.json`](../evidence/h58_postrun_review.json), [`knowledge/19_hypotheses_H58_preregistered.md`](19_hypotheses_H58_preregistered.md), and [`registry/h58_preregistration.json`](../registry/h58_preregistration.json).
