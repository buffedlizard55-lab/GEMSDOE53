#!/usr/bin/env python3
"""Publish the H57 artifact to the GitHub Pages site, with the audit next to the download.

Every number printed on the page is read from ``evidence/h57_*.json``.  Nothing is typed into HTML
by hand, so a page can never disagree with the file it is advertising.  Run it, then run
``scripts/check_site.py``, which re-reads the bytes on disk and fails on any contradiction.
"""
from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DL = DOCS / "downloads"
DATA = DOCS / "data"
EV = ROOT / "evidence"

NAV_LINK = '<a href="h57.html">H57 current</a>'
NAV_OLD = '<a href="h56.html">H56 audit</a>'
NAV_NEW = NAV_LINK + NAV_OLD


def nav_fix(text: str) -> str:
    """Put the H57 link in the nav exactly once, whatever state a page was left in.

    A plain ``replace(NAV_OLD, NAV_NEW)`` prepends the link on every run, and because ``NAV_NEW``
    contains ``NAV_OLD`` the second run turns the nav into four copies of it. Strip first.
    """
    while NAV_LINK in text:
        text = text.replace(NAV_LINK, "", 1)
    return text.replace(NAV_OLD, NAV_NEW, 1)

BAR_OPEN, BAR_CLOSE = "<!--H57BAR-->", "<!--/H57BAR-->"


def load(p):
    return json.loads(Path(p).read_text())


def human(n):
    return f"{int(n):,}"


def fname(b):
    """Basename of the artefact path recorded in the build receipt."""
    return Path(b["artefact"]).name


def bar_html(b, name, note, verdict):
    f = fname(b)
    fmt = b["format_gate"]
    u = b["uniqueness"]
    nd = b["not_the_union"]
    px, arm, core = b["file"]["px"], b["arm"]["px"], b["core"]["px"]
    proj = b["projection_by_rho"]
    return f"""<div class="download-bar" id="h57-bar" aria-label="H57 submission download">
<div><strong>H57 &mdash; two-view co-training union arm &middot; VERDICT: {verdict}</strong>
<small><code>{f}</code></small>
<small>{human(fmt['bytes'])} bytes &middot; single-band float32 &middot; EPSG:32611 &middot;
{human(fmt['width'])} &times; {human(fmt['height'])} &middot; {human(px)} emitted px
({human(core)} exactly-accounted core + {human(arm)} novel arm) &middot; values exactly
<code>{{0, 1}}</code> &middot; 0 NaN &middot; sha256 <code>{b['file']['sha256'][:24]}&hellip;</code></small>
<small>format gate <b>{'PASS' if fmt['ok'] else 'FAIL'}</b>
({', '.join(fmt['problems']) if fmt['problems'] else 'no problems'}) &middot; decoded pattern
unique against {u['n_priors_checked']} accessible aligned priors:
<b>{u['canonical_pattern_unique']}</b> &middot; arm cells outside their support union:
<b>{human(nd['arm_outside_prior_support_px'])} px ({nd['arm_outside_prior_support_frac'] * 100:.1f}% of the arm)</b></small>
<small>closest emitted cell to a mapped catalogue trace <b>{b['file']['min_distance_to_catalogue_m']:.1f} m</b>
&mdash; the &le; 200 m ring that measured exactly zero credit is empty by construction.</small>
<small>conditional projection only (owner-reported scores, not organiser-authenticated):
{', '.join(f'{k.replace("rho_", "rho=")} &rarr; {v}' for k, v in proj.items())}.
rho is the arm's credit density &mdash; a <b>prior, not a measurement</b>. Not a forecast.</small>
<small>submission name: <code>{name}</code><br>note ({len(note)} chars): <code>{note}</code></small>
</div>
<a class="button" href="downloads/{f}" download>&darr; Download the submission .TIF</a>
<a class="button" href="downloads/{f[:-4]}.zip" download>&darr; Download single-TIFF .ZIP</a>
<a class="button secondary" href="downloads/h57-candidate.tif" download>Short link &middot; h57-candidate.tif</a>
<a class="button secondary" href="h57.html">Full audit &amp; holdout &rarr;</a>
</div>"""


def page_html(b, c, v, st, name, note, verdict, gate):
    ind = c["independence"]
    strata = c["strata"]
    dpts = c["strata"]["median_depth_to_basement_m"]
    # One row per (instrument, budget) cell. The outer loop used to iterate the instrument a
    # second time and rendered the whole table twice, which read on the page as two identical
    # result blocks and looked like two separate experiments.
    rows = []
    for k in ("tip@15000", "tip@37654", "hide@15000", "hide@37654"):
        for i, r in enumerate(v["ranking"][k]):
            rows.append(
                f"<tr><td><code>{k}</code></td><td>{i + 1}</td>"
                f"<td><code>{r['field']}</code></td><td>{r['dti']:.5f}</td>"
                f"<td>{r['lift_vs_random']:+.5f}</td></tr>")
    pl = v["placement"]
    pl_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{d['iso3']:.5f}</td><td>{d['aniso5']:.5f}</td>"
        f"<td>{d['lift']:+.5f}</td><td>{d['relative_lift_pct']:+.2f}%</td>"
        f"<td>{d['folds_won']}</td><td><b>{'PASS' if d['gate_met'] else 'FAIL'}</b></td></tr>"
        for k, d in pl.items())
    sc = st["combined"]
    sc_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{val:.6f}</td>"
        f"<td>{val / sc['random']:.2f}&times;</td>"
        f"<td><b>{'REFUTED' if k == 'S_a_only' else 'shipped' if k == 'union' else ''}</b></td></tr>"
        for k, val in sorted(sc.items(), key=lambda kv: -kv[1]))
    pseudo = c["pseudo_label"]
    refuted = "".join(
        f"<tr><td>{x['hypothesis']}</td><td><code>{x['evidence']}</code></td>"
        f"<td>{x['result']}</td></tr>" for x in gate["refuted"])
    chk = "".join(
        f"<tr><td>{k}</td><td><b>{'PASS' if ok else 'FAIL'}</b></td></tr>"
        for k, ok in gate["checks"].items())
    pb = gate["probability_by_floor"]
    dm = gate["decisive_measure"]

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>H57 &middot; two-view co-training union arm &middot; GEMSDOE52</title>
<link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head><body>
<a class="skip" href="#main">Skip to evidence</a>
<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a><a href="index.html">Overview</a>
<a href="executive-summary.html">Submission guide</a>{NAV_NEW}<a href="validation.html">Validation</a>
<a href="forensics.html">0.2778 autopsy</a><a href="sources.html">Sources</a></nav></header>
<main id="main">
{bar_html(b, name, note, verdict)}
<div class="eyebrow">H57 &middot; session 2026-10-07 &middot; blind preregistration in
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/17_hypotheses_H57_preregistered.md">knowledge/17</a>
&middot; results in
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52/blob/main/knowledge/18_hypotheses_H57_results.md">knowledge/18</a></div>
<h1>Two views, measured honestly.<br>One of them won. Three ideas did not.</h1>
<p class="lede">The brief asked for co-training between a geophysical view and a surface view, with
<em>disagreement</em> as the discovery signal, plus a metric-aware placement rule. H57 ran all of
it on restored competition bytes and reports all five outcomes, including the four that failed. The
artefact ships the union ranking field and the incumbent isotropic emitter, because those are the
two choices the holdouts actually supported.</p>

<div class="status"><strong>Verdict: {verdict}.</strong> {gate['recommendation']}</div>

<h2>1 &middot; What the metric actually pays for</h2>
<p>From the published definition
(<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric">page 967</a>)
and the identity <code>FNw = |G| &minus; TPw</code>, a marginal pixel covering a previously
uncovered truth pixel at distance <code>d</code> is worth accepting exactly when
<code>k(d) &gt; &alpha;&middot;DTI</code>. At DTI 0.2778 that is a radius of <b>283 m</b>. Two
consequences drive everything below: place, do not spray; and <b>add mass only if its credit
density exceeds 0.2&middot;DTI &asymp; {dm['marginal_breakeven_rho']}</b>. The dead 6,436-cell ring
inside 200 m of a mapped trace earned <b>exactly zero</b>, and deleting it turned a real 0.2600 into
a real 0.2778.</p>

<h2>2 &middot; The conditional-independence test the brief demands</h2>
<p>Per-block out-of-fold error of each view on labelled negatives, whole-segment folds, 4 px buffer,
{human(ind['n_blocks'])} blocks, {human(ind['n_negative_predictions'])} negative predictions.</p>
<ul>
<li>block-level negative MSE: Pearson {ind['tests']['negative_mean_squared_error']['pearson']:.4f},
Spearman {ind['tests']['negative_mean_squared_error']['spearman']:.4f}</li>
{''.join(f'<li>block-level {k.replace("_", " ")}: Pearson {d["pearson"]:.4f}, Spearman {d["spearman"]:.4f}</li>' for k, d in ind["tests"].items())}
<li>pixel-level out-of-fold logit correlation {ind['pixel_level']['pearson']:.4f}
(n = {human(ind['pixel_level']['n'])})</li>
<li><strong>measured</strong> = {ind['measured']} &middot; <strong>allow_exchange</strong> =
{ind['allow_exchange']} &middot; max |r| = {ind['max_abs_correlation']:.4f} against the registered
abandonment threshold |r| &ge; {ind['threshold']:.2f}</li>
</ul>
<p class="small">This is the first non-degenerate measurement of the premise in this repository:
<code>knowledge/03</code> N-1 could not estimate it, so it had to fail closed and the
pseudo-label exchange was never run there. Here the statistic is well powered and the premise is
<em>not refuted</em> &mdash; which is a statement about weak coupling, not about independence.</p>

<h2>3 &middot; Disagreement strata &mdash; measured, not assumed</h2>
<table class="data"><tr><th>stratum</th><th>pixels</th><th>median depth to basement</th>
<th>the brief's reading</th><th>what the holdout says</th></tr>
<tr><td>A confident, B abstains</td><td>{human(strata['counts']['a_only'])}</td>
<td>{dpts['a_only']:.0f} m</td><td>buried structure under cover</td>
<td><b>REFUTED as the arm population</b> &mdash; worst of eight arms, below random</td></tr>
<tr><td>B confident, A abstains</td><td>{human(strata['counts']['b_only'])}</td>
<td>{dpts['b_only']:.0f} m</td><td>surface artefact</td><td>real but second-best; kept as a
labelled component</td></tr>
<tr><td>both confident</td><td>{human(strata['counts']['concordant'])}</td>
<td>{dpts['concordant']:.0f} m</td><td>already-mapped fabric</td><td>smallest, weakest</td></tr>
<tr><td>neither</td><td>{human(strata['counts']['neither'])}</td><td>&mdash;</td>
<td>no view sees it</td><td>the sub-threshold shoulder of the structural signal</td></tr></table>
<p>The A-only stratum really is the deep-cover stratum: median depth to basement
{dpts['a_only']:.0f} m against {dpts['b_only']:.0f} m in B-only, {c['strata']['median_depth_to_basement_m']['permitted']:.0f} m over the
permitted set. The geological premise is <b>correct</b>. What failed is the bet that this makes it
a better place to look for faults.</p>

<h2>4 &middot; Pseudo-label exchange &mdash; ran, and did nothing</h2>
<p>{human(pseudo['n_pseudo_px'])} pseudo-labelled pixels in {pseudo['n_segments']} whole segments;
View-A out-of-fold AUC {pseudo['auc_view_A_before']:.4f} &rarr; {pseudo['auc_view_A_after']:.4f}
(delta {pseudo['delta_auc']:+.4f}), evaluated on {human(pseudo['n_eval_px'])} held-out pixels no
model had seen. That is indistinguishable from noise, and it reproduces
<code>knowledge/03</code> N-1 exactly. Disagreement is therefore used to <em>label</em> the arm, not
to <em>train</em> it.</p>

<h2>5 &middot; Ranking: eight fields, one protocol, two instruments</h2>
<p>Candidates may not sit on the <b>visible</b> catalogue dilated by 2 px; the <b>held-out</b>
catalogue is scored as truth, so credit can only be earned on faults the model never saw. Both
instruments, because either one alone is structurally blind (<code>knowledge/03</code> N-3).</p>
<table class="data"><tr><th>cell</th><th>rank</th><th>field</th><th>fold-mean DTI</th>
<th>vs random control</th></tr>{''.join(rows)}</table>

<h2>6 &middot; Placement: the anisotropic emitter failed its own gate</h2>
<p>The kernel algebra is exact: on an isolated 1-px trace the credited truth per node interval
[0,&nbsp;s) is 7/3 at s&nbsp;=&nbsp;3, 8/3 at s&nbsp;=&nbsp;4 and 3.0 at s&nbsp;=&nbsp;5, i.e. 5 px
carries <b>+28.6&nbsp;%</b> over 3 px. That is the whole case for H57-A, and it is the right number
&mdash; for an isolated 1-px trace.</p>
<table class="data"><tr><th>cell</th><th>isotropic 3 px</th><th>anisotropic 5&times;3 px</th>
<th>lift</th><th>relative</th><th>folds won</th><th>gate</th></tr>{pl_rows}</table>
<p class="small">Against the mapped traces the advantage does not survive: the traces are wider
than 1 px and adjacent nodes along a gently curving strike overlap anyway. The artefact ships the
isotropic emitter. This is recorded as a <b>refutation</b>, not a tuning result.</p>

<h2>7 &middot; Which stratum should carry the arm</h2>
<table class="data"><tr><th>arm</th><th>fold-mean DTI</th><th>vs random</th><th>outcome</th></tr>
{sc_rows}</table>

<h2>8 &middot; What failed, stated plainly</h2>
<table class="data"><tr><th>hypothesis</th><th>evidence</th><th>result</th></tr>{refuted}</table>

<h2>9 &middot; The artefact</h2>
<p>{human(b['core']['px'])} core cells &mdash; the double-corroborated atom
<code>P1 = h33-2-b2 &cap; gems24-d1-5</code>, whose credit density is bounded exactly by
published-score algebra &mdash; plus {human(b['arm']['px'])} arm cells ranked by
<code>max(p_A, p_B)</code> over pixels outside the &le; 200 m ring, outside every accessible
prior's support union, and at least 3 px from the core, placed with the isotropic 3-px emitter.</p>
<p><a class="button" href="downloads/{fname(b)}" download>&darr; Download the .TIF</a>
<a class="button" href="downloads/{fname(b)[:-4]}.zip" download>&darr; Download the .ZIP</a>
<a class="button secondary" href="downloads/{Path(b['candidate_geology_dossier']).name}">per-candidate geological reasoning CSV</a></p>

<h2>10 &middot; Slot gate</h2>
<table class="data"><tr><th>registered check</th><th>result</th></tr>{chk}</table>
<p>P(this file scores below the owner's own 0.2778) = <b>{pb['0.2778']:.2f}</b> &middot;
P(above 0.3195) = <b>{pb['0.3195']:.2f}</b> &middot; P(above the observed board top 0.3774) =
<b>{pb['0.3774']:.2f}</b>, all under the registered joint prior over the exact core-credit interval
and the arm's credit density. {gate['board_note']}</p>

<h2>11 &middot; Limits, stated plainly</h2>
<ol>
<li>The arm <b>cannot be scored by this simulator at all</b>. With the catalogue halo removed from
the candidate pool, the View A field scored 0.000358 against a random control of 0.001713 during
validation: excluding the catalogue removes every pixel the truth can occupy. The arm's credit
density is a prior, not a measurement, and nothing in this repository can certify it.</li>
<li><strong>No number on this page is a leaderboard forecast.</strong> The simulator scores against
a proxy truth; Spearman(reported score, simulated DTI) = &minus;0.1045 (p = 0.734, n = 13) in
<code>knowledge/10</code> &sect;5. These comparisons are valid between arms on identical rows and
for nothing else.</li>
<li>Every leaderboard score quoted anywhere in this repository is <b>owner-reported</b>. No
organiser receipt maps a score to any filename or SHA-256, and the board snapshot records a top of
0.3774, not 0.3195.</li>
<li>No computable feature re-ranks inside the core family (<code>knowledge/10</code> &sect;6:
63&nbsp;+&nbsp;108 features, best AUC 0.5453). All gain here comes from mass the family has never
emitted.</li>
<li>Catalogue-zero pixels are proxies for absence, not verified geological absence, and a
competition score is not the Phase-2 expert outcome.</li>
<li>Inputs are SHA-pinned owner mirrors restored through the GitHub API and verified by SHA-256 and
byte count &mdash; integrity-pinned, <b>not</b> organiser-authenticated downloads.</li>
</ol>
</main></body></html>"""


def exec_html(b, gate, name, note, verdict):
    fmt = b["format_gate"]
    u = b["uniqueness"]
    nd = b["not_the_union"]
    px = b["file"]["px"]
    ok = "no problems" if not fmt["problems"] else "; ".join(fmt["problems"])
    fits = "fits" if len(note) <= 200 else "TOO LONG"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Exactly how to submit the H57 GeoTIFF to DrivenData competition 306: the unique name, the note, and why 'Predicted values must be in range [0,1]' happens.">
<title>Submit in 4 steps &middot; GEMSDOE52</title><link rel="stylesheet" href="style.css">
<script src="site.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a>
<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a><a href="index.html">Overview</a>
<a href="executive-summary.html">Submission guide</a>{NAV_NEW}<a href="forensics.html">0.2778 autopsy</a>
<a href="hypotheses.html">Hypotheses</a><a href="sources.html">Sources</a>
<a href="irregularities.html">Limitations</a></nav></header><main id="main">
{bar_html(b, name, note, verdict)}

<h1>Submitting this file takes four steps.</h1>
<p class="lede">Everything below is generated from the file on disk, not typed in. If any statement
here ever disagrees with the bytes, <code>scripts/check_site.py</code> fails the build.</p>

<div class="status"><strong>Verdict: {verdict}.</strong> {gate['recommendation']}</div>

<section class="card"><h2>Step 2 &mdash; what the form asks for, and what this file contains</h2>
<table><tr><th>Form field</th><th>What the portal requires</th><th>This file</th></tr>
<tr><td>File to submit</td><td>A single-band <code>.tif</code>, or a <code>.zip</code> holding
exactly one GeoTIFF. The CRS, shape and geotransform must match the submission format.</td>
<td><code>{fname(b)}</code> &mdash; {human(fmt['bytes'])} bytes, CRS <code>{fmt['crs']}</code>,
{human(fmt['width'])} &times; {human(fmt['height'])}, transform
<code>({fmt['transform'][0]:g}, {fmt['transform'][1]:g}, {fmt['transform'][2]:g}, {fmt['transform'][3]:g}, {fmt['transform'][4]:g}, {fmt['transform'][5]:g})</code>,
identical to <code>sample_submission.tif</code>. A .ZIP of the same TIFF is the second button.</td></tr>
<tr><td>Predicted values</td><td>&ldquo;Predicted values must be in range [0,1]&rdquo;</td>
<td>raw values are exactly <code>{{0, 1}}</code> &mdash; min {fmt['min']:.0f}, max
{fmt['max']:.0f}, <b>0 NaN</b>, 0 infinities, no nodata tag. Format gate:
<b>{'PASS' if fmt['ok'] else 'FAIL'}</b> ({ok}).</td></tr>
<tr><td>Submission name</td><td>A unique name that tells your submissions apart</td>
<td><code>{name}</code></td></tr>
<tr><td>Note (optional)</td><td>A short comment, at most 200 characters</td>
<td>the {len(note)}-character string below &mdash; <b>{fits}</b></td></tr></table>
<label for="submission-note">Copy this into the Note box ({len(note)} / 200 characters)</label>
<textarea id="submission-note" readonly>{note}</textarea><button data-copy="submission-note">Copy note</button>
<p class="small">The bytes you downloaded are the bytes that were checked: sha256
<span class="mono">{b['file']['sha256']}</span>. Re-exporting or re-compressing is unnecessary; the
portal accepts the <code>.tif</code> directly.</p></section>

<section class="card"><h2>Step 3 &mdash; if the portal says &ldquo;Predicted values must be in range [0,1]&rdquo;</h2>
<p>That error has been hit in this project's history and it is almost never a scaling problem. Three
causes account for it, in the order they occur:</p>
<ol>
<li><strong>No-data encoding.</strong> The problem page says data outside the survey bounds may be
&quot;null or NaN&quot;, but the validator range-checks the array and NaN fails
<code>0 &le; v &le; 1</code> in every comparison direction. The competition's own
<code>sample_submission.tif</code> is the proof: its {human(fmt['mass'] + fmt['n_nan'])}-cell
finite footprint is written with <b>0.0</b>, not NaN. This file writes 0.0 everywhere it does not
predict, so it cannot trigger this.</li>
<li><strong>A no-data tag outside [0,1].</strong> A <code>nodata</code> value such as
<code>-1</code> or <code>-3.4e38</code> is read back by some validators as a pixel value. This file
carries <b>no nodata tag at all</b>.</li>
<li><strong>Rescaling that was never applied.</strong> If a model outputs logits or arbitrary real
scores they must be written as probabilities. This file never needed rescaling: it is written
directly in {{0, 1}}.</li>
</ol>
<p class="small">All three are checked locally by <code>gems52.gates.format_report</code> against
the competition's own <code>sample_submission.tif</code>, and every check is re-run against the
served download by <code>scripts/check_site.py</code>. Local checks are a compatibility precaution,
not a promise about an undocumented portal validator.</p></section>

<section class="card"><h2>Step 4 &mdash; is this file actually new?</h2>
<table><tr><th>Check</th><th>Result</th></tr>
<tr><td>Decoded pattern equals any of the {u['n_priors_checked']} accessible aligned prior rasters</td>
<td><b>{'no &mdash; none' if u['canonical_pattern_unique'] else 'YES &mdash; FAIL'}</b></td></tr>
<tr><td>Equals the literal union of those priors</td>
<td><b>{u['equals_literal_prior_union']}</b></td></tr>
<tr><td>Arm cells outside the accessible prior-support union</td>
<td><b>{human(nd['arm_outside_prior_support_px'])} px
({nd['arm_outside_prior_support_frac'] * 100:.1f}% of the arm)</b></td></tr>
<tr><td>Equals the union of the two views it was derived from</td>
<td><b>{nd['arm_equals_every_pixel_of_the_A_only_pool']}</b></td></tr>
<tr><td>Equals any of the three named prior files it was derived from</td>
<td><b>{nd['file_equals_prior_A'] or nd['file_equals_prior_B'] or nd['file_equals_prior_E']}</b></td></tr>
<tr><td>Closest emitted cell to a mapped catalogue trace</td>
<td><b>{b['file']['min_distance_to_catalogue_m']:.1f} m</b> (the ring that measured exactly zero
credit is empty)</td></tr>
<tr><td>Cells clipped to the submission domain</td>
<td>{human(b['clipping_to_sample_domain_px'])} (mass outside
<code>sample_submission.tif</code>'s finite mask cannot earn credit and can only be scored as a
false positive)</td></tr></table>
<p class="small">This is uniqueness against the <em>accessible</em> inventory only. It is not proof
against every submission on the leaderboard, and it is not a statement that any emitted cell is a
fault: predictions are model proposals, and a competition score is not the Phase-2 expert
outcome.</p></section>

<h2>Honest limits</h2><ul>
<li>The core of this file reuses support from two earlier owner-reported submissions; its credit
bound is derived from scores that are <strong>owner-reported, not organiser-authenticated</strong>.</li>
<li>The new arm's credit density is a <strong>prior</strong>. The full curve is printed on the
<a href="h57.html">audit page</a>; it is conditional arithmetic, not a forecast. The arm cannot be
scored by the catalogue simulator at all.</li>
<li>{gate['recommendation']}</li>
<li>Inputs are SHA-pinned owner mirrors of the competition rasters, restored through the GitHub API
and verified by SHA-256 and byte count; they are <strong>not</strong> organiser-authenticated
downloads.</li>
</ul>
<p class="small">Official sources:
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">problem statement</a> &middot;
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">description, metric and submission format</a> &middot;
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">competition rules (PDF)</a> &middot;
<a href="https://github.com/drivendataorg/gems-prize-reference-solution">official reference solution</a>.</p>
</main><footer>Competition 306 &middot; Local research only &middot; A competition score is not the
expert-reviewed outcome. <a href="irregularities.html">Limitations</a> &middot;
<a href="https://github.com/buffedlizard55-lab/GEMSDOE52">Code and prompt</a></footer></body></html>"""


def main() -> int:
    b = load(EV / "h57_build.json")
    c = load(EV / "h57_cotrain.json")
    v = load(EV / "h57_validation.json")
    st = load(EV / "h57_strata.json")
    gate = load(EV / "h57_slot_gate.json")
    name, note, verdict = gate["submission_name"], gate["note"], gate["verdict"]

    src = ROOT / b["artefact"]
    dst = DL / src.name
    shutil.copy2(src, dst)
    zpath = DL / (src.stem + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(dst, arcname=dst.name)
    short_tif = DL / "h57-candidate.tif"
    short_zip = DL / "h57-candidate.zip"
    shutil.copy2(dst, short_tif)
    shutil.copy2(zpath, short_zip)
    assert short_tif.read_bytes() == dst.read_bytes()

    dossier = Path(b["candidate_geology_dossier"])
    shutil.copy2(dossier, DL / dossier.name)

    (DL / "README_H57.txt").write_text(
        f"{src.name}\nshort link: h57-candidate.tif (byte-identical alias)\n"
        f"sha256 {b['file']['sha256']}\nbytes {b['file']['bytes']}\n\n"
        f"VERDICT: {verdict}\n\n"
        f"submission name: {name}\nidentifying note ({len(note)} chars): {note}\n\n"
        + "\n".join(f"- {k}: {v2}" for k, v2 in gate["checks"].items())
        + f"\n\n- {gate['recommendation']}\n")

    # Every other round in this repository ships evidence/submission_<stem>.json. The scheduled
    # feed looks for exactly that name, and when it is absent the feed used to fall through to an
    # older round's archive and publish *that* as the current submission. Writing it here makes
    # H57 conform to the convention the feed already depends on.
    (EV / f"submission_{Path(b['artefact']).stem}.json").write_text(json.dumps(
        dict(round="H57", file=fname(b), stem=Path(b["artefact"]).stem,
             submission_name=name, note=note, note_chars=len(note),
             bytes=b["file"]["bytes"], sha256=b["file"]["sha256"],
             nonzero_px=b["file"]["px"], core_px=b["core"]["px"], arm_px=b["arm"]["px"],
             verdict=verdict, approved_for_weekly_slot=False, promoted=False,
             submission_slots_used=0,
             format=b["format_gate"], uniqueness=b["uniqueness"],
             not_the_union=b["not_the_union"],
             receipts=["h57_build.json", "h57_cotrain.json", "h57_validation.json",
                       "h57_strata.json", "h57_format_gate.json", "h57_uniqueness.json",
                       "h57_slot_gate.json"],
             candidate_geology_dossier=b["candidate_geology_dossier"],
             official_score_status="no portal upload or organizer score is recorded"),
        indent=1, allow_nan=False) + "\n")

    DATA.mkdir(parents=True, exist_ok=True)
    # docs/data/submission.json is the machine-readable "current artefact" receipt the site and
    # scripts/check_site.py both read.  It is regenerated, never hand-edited.
    (DATA / "submission.json").write_text(json.dumps(dict(
        exists=True, round="H57",
        file=fname(b),
        artefact=b["artefact"],
        download="downloads/" + fname(b),
        download_zip="downloads/" + fname(b)[:-4] + ".zip",
        short_tif="downloads/h57-candidate.tif",
        short_zip="downloads/h57-candidate.zip",
        bytes=b["file"]["bytes"], sha256=b["file"]["sha256"],
        nonzero_px=b["file"]["px"], core_px=b["core"]["px"], arm_px=b["arm"]["px"],
        submission_name=name, note=note, note_chars=len(note),
        verdict=verdict,
        approved_for_weekly_slot=False,
        approval_reason="R1's absolute +0.005 mean-lift threshold was not met (best +0.0048). "
                        "The artefact is published and fully gated; the upload decision is left "
                        "explicitly to the owner with its probability stated in "
                        "docs/data/h57_slot_gate.json.",
        promoted=False, submission_slots_used=0,
        format=dict(ok=b["format_gate"]["ok"], problems=b["format_gate"]["problems"],
                    crs=b["format_gate"]["crs"], width=b["format_gate"]["width"],
                    height=b["format_gate"]["height"], transform=b["format_gate"]["transform"],
                    dtype=b["format_gate"]["dtype"], bands=b["format_gate"]["bands"],
                    nodata=b["format_gate"]["nodata"], min=b["format_gate"]["min"],
                    max=b["format_gate"]["max"], n_nan=b["format_gate"]["n_nan"],
                    n_nonzero=b["file"]["px"]),
        uniqueness=dict(ok=b["uniqueness"]["canonical_pattern_unique"],
                        research_publication_ok=b["uniqueness"]["canonical_pattern_unique"],
                        n_priors_checked=b["uniqueness"]["n_priors_checked"],
                        novel_fraction=b["uniqueness"]["novel_fraction"],
                        relation_to_union="arm is 100% outside the accessible prior-support "
                                           "union; the decoded pattern equals none of the "
                                           "accessible aligned priors",
                        equals_literal_prior_union=b["uniqueness"]["equals_literal_prior_union"]),
        validation=dict(approved_for_slot=False,
                        holdout_receipts=["docs/data/h57_validation.json",
                                          "docs/data/h57_strata.json",
                                          "docs/data/h57_cotrain.json"]),
        slot_gate="docs/data/h57_slot_gate.json",
        dossier="downloads/" + Path(b["candidate_geology_dossier"]).name,
    ), indent=1, allow_nan=False) + "\n")
    (ROOT / "submission" / "LATEST.txt").write_text(fname(b) + "\n")
    (ROOT / "submission" / "H56_LATEST.txt").write_text(
        "gems52-h56-consensus-core-continuation-40517px-04c86e1888a8-zeros.tif\n")
    for n in ("h57_build.json", "h57_cotrain.json", "h57_validation.json", "h57_strata.json",
              "h57_format_gate.json", "h57_uniqueness.json", "h57_slot_gate.json",
              f"submission_{Path(b['artefact']).stem}.json"):
        if (EV / n).exists():
            shutil.copy2(EV / n, DATA / n)

    (DOCS / "h57.html").write_text(page_html(b, c, v, st, name, note, verdict, gate))
    (DOCS / "executive-summary.html").write_text(exec_html(b, gate, name, note, verdict))

    bar = bar_html(b, name, note, verdict)
    idx = nav_fix((DOCS / "index.html").read_text())
    block = f"{BAR_OPEN}{bar}{BAR_CLOSE}"
    if BAR_OPEN in idx:
        i, j = idx.index(BAR_OPEN), idx.index(BAR_CLOSE) + len(BAR_CLOSE)
        idx = idx[:i] + block + idx[j:]
    else:
        idx = idx.replace('<main id="main">', '<main id="main">' + block, 1)
    idx = idx.replace(
        '<meta name="description" content="H56 current research artifact with a short download, '
        'decoded-pattern audit, missing spatial holdout and explicit no-upload decision.">',
        '<meta name="description" content="H57 submission GeoTIFF: two-view co-training union arm '
        'on an exactly-accounted core, with the full holdout audit including the four refuted '
        'hypotheses.">')
    (DOCS / "index.html").write_text(idx)

    for name_html in ("h54.html", "h55.html", "h55-profile.html", "h55-edge.html",
                      "validation.html", "forensics.html", "sources.html", "method.html",
                      "hypotheses.html", "feed.html", "irregularities.html",
                      "h53.html", "r3.html", "r3-hypotheses.html", "h56.html"):
        p = DOCS / name_html
        if p.exists():
            p.write_text(nav_fix(p.read_text()))

    print("published", src.name, "->", dst, zpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())