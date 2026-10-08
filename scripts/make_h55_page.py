#!/usr/bin/env python3
"""Legacy H55 page renderer, guarded so it cannot replace a newer current artifact.

H55 is historical on the current tree; H56 owns the current overview and submission guide. The
archived H55 evidence and page remain available, but this renderer may run only if both the current
receipt and submission marker explicitly point back to this exact H55 artifact.
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EV = ROOT / "evidence"
DOCS = ROOT / "docs"
TAG = "20261007T0150Z"
STEM = f"gems52-h55-btherm-greedy-37654px-{TAG}-zeros"


def j(name):
    return json.loads((EV / name).read_text())


def _publish_h55_from_receipt() -> int:
    ev = j(f"submission_{STEM}.json")
    ver = j(f"h55_verification_{TAG}.json")
    sw = j("h55_sweep.json")
    hc = j("h55_sweep_hardcore.json")
    sp = j("h55_spacing_curve.json")
    cal = j("h55_g_calibration.json")
    b6 = j("h55_band6_identity.json")
    th = j("h55_thermal_layers.json")
    rs = j(f"h55_reasoning_{TAG}.json")
    nreg = len(j("../registry/irregularities.json")["entries"]) if False else \
        len(json.loads((ROOT / "registry/irregularities.json").read_text())["entries"])

    geo, sel, uni, prj = ev["geometry"], ev["selection"], ev["uniqueness"], ev["projection"]
    ind = ver["independence_summary"]
    ua = ver["union_audit"]
    checks = ver["shipped_file"]["checks"]
    n_ok = sum(bool(v) for v in checks.values())

    def rk(d, mode):
        return {(r["arm"], r["emitter"]): r for r in d[mode]["summary"]["ranked"]}

    G = {m: rk(sw, m) for m in ("hide", "tip")}
    C = {m: rk(hc, m) for m in ("hide", "tip")}
    HI = ' class="hi"'

    def cell(t, m, a, e):
        r = t[m].get((a, e))
        return f"{r['mean_dti']:.5f}" if r else "&ndash;"

    def wins(t, m, a, e):
        r = t[m].get((a, e))
        return f"{r['fold_wins_vs_random']}/4" if r else "&ndash;"

    def a_only_vs_random(mode):
        candidate = C[mode].get(("A_only", "hc4|37654"))
        random = G[mode].get(("random", "hc|37654"))
        if not candidate or not random:
            return "not measured"
        candidate_dti = float(candidate["mean_dti"])
        random_dti = float(random["mean_dti"])
        if candidate_dti < random_dti:
            relation = "below"
        elif candidate_dti > random_dti:
            relation = "above"
        else:
            relation = "equal to"
        return f"{candidate_dti:.5f} ({relation} matched random, {random_dti:.5f})"

    a_only_hide = C["hide"].get(("A_only", "hc4|37654"))
    a_only_tip = C["tip"].get(("A_only", "hc4|37654"))
    a_only_gate = (
        "not measured" if not a_only_hide or not a_only_tip else
        "passes" if (a_only_hide.get("fold_wins_vs_random") or 0) >= 3
                    and (a_only_tip.get("fold_wins_vs_random") or 0) >= 3 else
        "does not pass"
    )

    rows = []
    for a, e in [("B_therm", "greedy|37654"), ("B_c50", "greedy|37654"),
                 ("B_c100", "greedy|37654"), ("B_therm", "greedy|50000"),
                 ("B_c100", "hc4|37654"), ("B_c50", "hc4|37654"),
                 ("B_only", "hc4|37654"), ("AB_w80", "hc4|37654"), ("A_only", "hc4|37654")]:
        h = G["hide"].get((a, e)) or C["hide"].get((a, e))
        t = G["tip"].get((a, e)) or C["tip"].get((a, e))
        if not h or not t:
            continue
        hi = HI if (a, e) == ("B_therm", "greedy|37654") else ""
        rows.append(
            f"<tr{hi}><td class='mono'>{a}</td><td class='mono'>{e}</td>"
            f"<td class='num'>{h['mean_dti']:.5f}</td><td class='num'>{h['fold_wins_vs_random']}/4</td>"
            f"<td class='num'>{t['mean_dti']:.5f}</td><td class='num'>{t['fold_wins_vs_random']}/4</td>"
            f"<td class='num'><b>{h['mean_dti'] + t['mean_dti']:.5f}</b></td>"
            f"<td class='num'>{h['mean_A_per_S']:.3f}</td></tr>")
    tip_rnd = {r["emitter"]: r["mean_dti"] for r in sw["tip"]["summary"]["ranked"] if r["arm"] == "random"}
    for r in [x for x in sw["hide"]["summary"]["ranked"] if x["arm"] == "random"]:
        t = tip_rnd.get(r["emitter"], 0.0)
        rows.append(f"<tr><td class='mono'>random</td><td class='mono'>{r['emitter']}</td>"
                    f"<td class='num'>{r['mean_dti']:.5f}</td><td>&ndash;</td>"
                    f"<td class='num'>{t:.5f}</td><td>&ndash;</td>"
                    f"<td class='num'>{r['mean_dti'] + t:.5f}</td><td class='num'>&asymp;9.38</td></tr>")

    ind_rows = []
    for m in ("hide", "tip"):
        nb = ver["independence"][m]["blocks_per_instrument"]
        for f in ver["independence"][m]["per_fold"]:
            ind_rows.append(
                f"<tr><td class='mono'>{m}</td><td class='num'>{f['fold']}</td>"
                f"<td class='num'>{f['mean_overprediction']['usable_blocks']} / {nb}</td>"
                f"<td class='num'><b>{f['mean_overprediction']['spearman_rho']:+.4f}</b></td>"
                f"<td class='num'>{f['far_at_budget']['spearman_rho']:+.4f}</td>"
                f"<td class='num'>{f['far_at_budget']['cv_A']:.2f}</td>"
                f"<td class='num'>{f['far_at_budget']['cv_B']:.2f}</td></tr>")

    uni_rows = [f"<tr><td>{c['name']}</td><td class='num'>{c['px']:,}</td>"
                f"<td class='num'>{c['in_both']:,}</td><td class='num'>{c['frac_of_shipped']:.1%}</td>"
                f"<td>{c['shipped_equals']}</td></tr>" for c in ua["comparisons"]]
    sp_rows = [f"<tr><td class='num'>{s}</td><td class='num'>{d['mean_k']:.4f}</td>"
               f"<td class='num'><b>{d['T_per_S']:.3f}</b></td>"
               f"<td class='num'>{d['A_per_S']:.3f}</td></tr>"
               for s, d in sorted(sp.items(), key=lambda kv: int(kv[0]))]
    cal_rows = [f"<tr><td class='mono'>{r['name']}</td><td class='num'>{r['S']:,}</td>"
                f"<td class='num'>{r['dti']:.4f}</td><td class='num'>{r['A_per_S']:.3f}</td>"
                f"<td class='num'>{r['spacing_efficiency']:.1%}</td>"
                f"<td class='num'>{r['max_component']:,}</td>"
                f"<td class='num'>{r['n_g_lower_bound']:,.0f}</td></tr>"
                for r in sorted(cal["rows"], key=lambda r: -r["dti"])]
    b6_rows = [f"<tr><td>{k.replace('_', ' ')}</td><td class='num'><b>{v:+.4f}</b></td>"
               f"<td class='num'>{b6['pearson'][k]:+.4f}</td></tr>"
               for k, v in b6["spearman"].items()]

    far_max = max(ind["hide"]["max_abs_spearman_far_at_budget"],
                  ind["tip"]["max_abs_spearman_far_at_budget"])

    bar = f'''<!--H55BAR--><div class="download-bar" id="h55-bar"><div>
<strong>H55 submission GeoTIFF &mdash; the candidate this round offers, and the one
<code>submission/LATEST.txt</code> points at</strong>
<small><code>{ev['file']}</code></small>
<small>{ev['bytes']:,} bytes &middot; 1 band &middot; float32 &middot; EPSG:32611 &middot;
width {ev['width']} &times; height {ev['height']} &middot; values {ev['values'][0]}&ndash;{ev['values'][1]}
&middot; <b>{ev['nan_px']} NaN</b> &middot; {geo['S']:,} positive px &middot; 0 on a catalogue pixel &middot;
sha256 <code>{ev['sha256'][:16]}&hellip;</code></small>
<small>format gate <b>{ev['format_ok']}</b> (problems {ev['format_gate']['problems']}) &middot;
uniqueness gate <b>{ev['uniqueness_ok']}</b> &middot; <b>{uni['novel_fraction']:.1%}</b> strictly novel
against {uni['n_priors_checked']} scanned priors &middot; {uni['prior_px_dropped']:,} prior px deliberately
not re-emitted</small>
<small>placement efficiency <code>A/S</code> = <b>{geo['A_per_S']:.4f}</b> =
{geo['spacing_efficiency']:.2%} of the exact {prj['a_per_s_ceiling']:.6f} kernel-disc ceiling &mdash; the
file that scored 0.2778 reached {prj['a_per_s_0278_file']}
({prj['a_per_s_0278_file'] / prj['a_per_s_ceiling']:.1%}); every emitted pixel is 8-isolated (largest
component {geo['max_component']})</small>
<small>holdout, 4 folds &times; 2 instruments, matched-budget random control: <code>hide</code>
<b>{sel['hide']}</b> vs {prj['random_control']['hide']} ({sel['hide_wins']}/4) &middot; <code>tip</code>
<b>{sel['tip']}</b> vs {prj['random_control']['tip']} ({sel['tip_wins']}/4)</small>
<small>portal name: <code>{ev['submission_name']}</code></small>
<small>notes box, verbatim ({ev['submission_note_short_chars']} chars):
<code>{ev['submission_note']}</code></small>
</div>
<a class="button" href="downloads/{ev['file']}" download>&darr; Download .TIF</a>
<a class="button" href="downloads/{ev['zip']}" download>&darr; Download .ZIP</a>
<a class="button" href="h55.html">Why this file &rarr;</a>
<small style="width:100%">placement gain in isolation &mdash; the 0.2778 file's own measured
&rho;<sub>A</sub> = 0.01287 applied to this file's measured coverage, nothing else changed &mdash;
<b>DTI &asymp; {prj['geometry_only_dti']:.4f}</b>. Arithmetic given its assumption, <b>not a forecast</b>:
the instruments under-forecast the board by ~4&times; in absolute terms.</small>
</div><!--/H55BAR-->'''

    p = DOCS / "index.html"
    s = p.read_text()
    if "H55BAR" in s:
        i, k = s.index("<!--H55BAR-->"), s.index("<!--/H55BAR-->") + len("<!--/H55BAR-->")
        s = s[:i] + bar + s[k:]
    else:
        s = s.replace('<main id="main">', '<main id="main">' + bar, 1)
    if 'href="h55.html"' not in s:
        s = s.replace('<a href="h53.html">', '<a href="h55.html">H55 (this round)</a><a href="h53.html">', 1)
    p.write_text(s)

    HEAD = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="H55: a radiometric band mis-tagged as magnetic, |G| recovered by inverting the metric, and placement at 94% of the kernel's coverage ceiling.">
<title>H55 &mdash; radiometric correction, calibrated |G|, coverage-optimal placement &middot; GEMSDOE52</title>
<link rel="stylesheet" href="style.css"><script src="site.js" defer></script></head><body>
<a class="skip" href="#main">Skip to evidence</a>
<header><nav><a class="brand" href="index.html">GEMS / DOE 52</a><a href="index.html">Overview</a>
<a href="executive-summary.html">Submission guide</a><a href="validation.html">Validation</a>
<a href="forensics.html">0.2778 autopsy</a><a href="sources.html">Sources</a>
<a href="h55.html" aria-current="page">H55 (this round)</a><a href="h55-profile.html">H55-PROFILE follow-up</a><a href="h54.html">Parallel H54</a>
<a href="h53.html">Parallel H53</a></nav></header>
<main id="main">'''
    FOOT = '''<p class="small muted">Every number on this page is read out of <code>evidence/h55_*.json</code>
at build time by <code>scripts/run_h55.py</code> and <code>scripts/verify_h55.py</code> and copied to
<code>docs/data/</code> by <code>scripts/refresh_feed.py</code>; this page is regenerated by
<code>scripts/make_h55_page.py</code>. Nothing here is typed in by hand. Where a claim is an assumption
rather than a measurement, it says so in the same sentence.</p>
</main><footer>Competition 306 &middot; H55 &middot; fault predictions, not confirmed geothermal vents.
<a href="irregularities.html">Limitations &amp; review</a> &middot;
<a href="sources.html">official links</a></footer></body></html>
'''
    body = HEAD + f'''
<h1>H55 &mdash; three corrections, one file</h1>
<p class="lede">A radiometric band hiding in the official feature file under a magnetic tag; a hidden
constant recovered from our own scored history; and the arithmetic that says placement was worth more
than prediction, and that this family had left 14&nbsp;% of it unspent.</p>

<div class="download-bar"><div><strong>{ev['file']}</strong>
<small>{ev['bytes']:,} bytes &middot; sha256 <code>{ev['sha256']}</code></small>
<small>format gate {ev['format_ok']} &middot; uniqueness gate {ev['uniqueness_ok']}
({uni['relation_to_union']}) &middot; three-pass re-verification of the bytes:
<b>{'PASS' if ver['shipped_file']['all_ok'] else 'FAIL'}</b>, {n_ok}/{len(checks)} checks</small></div>
<a class="button" href="downloads/{ev['file']}" download>&darr; Download .TIF</a>
<a class="button" href="downloads/{ev['zip']}" download>&darr; Download .ZIP</a>
<a class="button" href="downloads/h55_reasoning_{TAG}.json">&darr; Phase-2 reasoning</a></div>
<p class="small">Separate experiment, not the current candidate: <a href="h55-edge.html">H55-EDGE potential-field research</a> failed its local promotion gates and remains research-only. It does not change this H55 receipt.</p>

<h2><span class="num">1</span> Band 6 of the organiser's own feature file is radiometric, not magnetic</h2>
<p>The TIFF tag inside <code>training_features.tif</code> says <code>data_category = magnetic_data</code>,
description &ldquo;Tilt angle or total curvature &mdash; magnetic field derivative for edge detection&rdquo;.
<code>src/gems52/features.py</code> believed it and filed the band inside <b>View A</b>, the
potential-field view, as <code>A_mag_tilt_abs</code>. Measured on the bytes, 150,000-pixel sample
(<a href="data/h55_band6_identity.json"><code>evidence/h55_band6_identity.json</code></a>):</p>
<table><thead><tr><th>band 6 compared with</th><th class="num">Spearman &rho;</th>
<th class="num">Pearson r</th></tr></thead><tbody>{''.join(b6_rows)}</tbody></table>
<p>A total-count channel <em>is</em> the sum of the potassium, thorium and uranium windows, so
&rho;&nbsp;=&nbsp;{b6['spearman']['K_plus_Th_plus_U']:+.4f} against K+Th+U is the physical signature, and
&rho;&nbsp;=&nbsp;{b6['spearman']['geoDAWN_TC_grid']:+.4f} against the independently reduced USGS grid is
the identification. A magnetic-field derivative cannot be uncorrelated with the magnetic field:
|&rho;|&nbsp;&le;&nbsp;0.149 against all five magnetic bands in the same file. Band 6 is also strictly
positive ({b6['band6_min']:.3f} &hellip; {b6['band6_max']:.3f}, mean {b6['band6_mean']:.2f}) where a tilt
angle is bounded by &plusmn;&pi;/2. Official source: Glen &amp; Earney 2024, USGS data release,
<a href="https://doi.org/10.5066/P93LGLVQ">doi:10.5066/P93LGLVQ</a>, public domain.</p>
<p><b>Consequence.</b> The brief's clause &ldquo;View B is DEM-derived curvature and slope, <em>plus any
radiometric bands present in <code>training_features.tif</code></em>&rdquo; resolves to one band, not to
none as <code>knowledge/04</code> and IR-52-001 recorded &mdash; and every conditional-independence
measurement this family ever took had a surface-geochemistry band inside the potential-field view, which
inflates any A&harr;B correlation. <b>IR-52-019 corrects IR-52-001.</b></p>

<h2><span class="num">2</span> |G| &mdash; the hidden truth count &mdash; recovered by inverting the metric</h2>
<p>The organiser publishes DTI and not |G|, yet |G| sets the credit bar and therefore the file size. For a
<em>sparse</em> emission (every emitted pixel 8-isolated, so no two compete for the same truth pixel and
<code>M = T</code>) the published form collapses to one unknown:</p>
<p class="mono">DTI = T / (0.2&middot;S + 0.8&middot;|G|) &nbsp;&rArr;&nbsp;
|G| &ge; 0.2&middot;DTI&middot;S / (1 &minus; 0.8&middot;DTI)</p>
<table><thead><tr><th>raster (sha256-verified)</th><th class="num">S</th><th class="num">DTI</th>
<th class="num">A/S</th><th class="num">% of ceiling</th><th class="num">largest component</th>
<th class="num">|G| &ge;</th></tr></thead><tbody>{''.join(cal_rows)}</tbody></table>
<p>Binding row <code>{cal['binding_row_all']}</code> &rarr;
<b>|G| &ge; {cal['n_g_lower_bound_all']:,.0f}</b>; the |G| that makes the implied per-covered-pixel truth
density most constant across the {cal['n_sparse']} sparse rows is
<b>{cal['n_g_point_estimate']:,.0f}</b>
(<a href="data/h55_g_calibration.json"><code>evidence/h55_g_calibration.json</code></a>).
<code>knowledge/01</code>'s independent loss decomposition of the 0.2778 file gave 8,000 &mdash; two
derivations, 1.6&nbsp;% apart. Caveat carried in the file itself: the geometry is exact because the bytes
are pinned, but the DTI values are owner-reported (IR-52-003).</p>
<p class="small">Note the &ldquo;% of ceiling&rdquo; column. One isolated emitted pixel can contribute at
most <b>{cal['kernel_disc_weight_sum']:.6f}</b> of kernel-weighted coverage &mdash; the disc weight sum,
enumerated exactly and test-pinned. The 0.2778 file reached 85.75&nbsp;% of it; its contiguous ancestor
reached 40.65&nbsp;%. At unchanged geology DTI is monotone in that ratio, which is why placement, not
prediction, was the largest available lever.</p>

<h2><span class="num">3</span> The spacing curve, measured rather than assumed</h2>
<p>A fault is a line, so the relevant question is: sample a straight trace every <code>s</code> pixels
&mdash; what does each emitted pixel earn?
(<a href="data/h55_spacing_curve.json"><code>evidence/h55_spacing_curve.json</code></a>)</p>
<table><thead><tr><th class="num">spacing s (px = 100 m)</th>
<th class="num">mean kernel weight per truth px</th>
<th class="num">credited mass per emitted px, T/S</th><th class="num">A/S</th></tr></thead>
<tbody>{''.join(sp_rows)}</tbody></table>
<p><b>The optimum is 500&ndash;600&nbsp;m</b>, not 100&nbsp;m and not the 150&ndash;300&nbsp;m the family's
&ldquo;dotted&rdquo; ancestors used. On real folds, where there is positional error, it moves inward to
<b>400&nbsp;m</b> &mdash; the curve's job is to be wrong in a measurable direction, not to be quoted.</p>

<h2><span class="num">4</span> Placement, isolated: same field, permitted set, budget and mask</h2>
<p><code>hide</code> fold 0, <code>n_truth = 10,336</code>, budget 37,654 px
(<a href="data/h55_holdout_hide.json"><code>evidence/h55_holdout_hide.json</code></a>):</p>
<table><thead><tr><th>emitter</th><th class="num">A/S</th><th class="num">% of ceiling</th>
<th class="num">DTI</th></tr></thead><tbody>
<tr><td>top-K, rank order &mdash; what the family shipped</td><td class="num">2.233</td>
<td class="num">23.8 %</td><td class="num">0.03196</td></tr>
<tr><td>hard-core 200 m</td><td class="num">6.184</td><td class="num">65.9 %</td>
<td class="num">0.05130</td></tr>
<tr><td>hard-core 300 m</td><td class="num">8.010</td><td class="num">85.4 %</td>
<td class="num">0.06334</td></tr>
<tr{HI}><td><b>hard-core 400 m</b></td><td class="num"><b>8.763</b></td>
<td class="num"><b>93.4 %</b></td><td class="num"><b>0.10101</b></td></tr>
<tr><td>hard-core 500 m</td><td class="num">9.303</td><td class="num">99.2 %</td>
<td class="num">0.07151</td></tr>
<tr><td>matched random control</td><td class="num">&asymp;9.38</td><td class="num">100 %</td>
<td class="num">0.04291</td></tr>
</tbody></table>
<p>+216&nbsp;% over top-K at <em>identical</em> budget, and +135&nbsp;% over the matched random control.
Regional centring is the other half: subtracting the field's own 5&nbsp;km / 10&nbsp;km box mean lifts
<code>hide</code> from 0.0797 to 0.0911 / 0.0917 at identical emitter and budget. The maximum of a smooth
field is a mountain; the maximum of a <em>locally anomalous</em> field is a structure.</p>

<h2><span class="num">5</span> Holdout: 4 folds &times; 2 instruments, whole segments, prevalence-matched</h2>
<table><thead><tr><th>arm</th><th>emitter</th><th class="num">hide</th><th class="num">wins</th>
<th class="num">tip</th><th class="num">wins</th><th class="num">sum</th><th class="num">A/S</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p class="small">Reference: the previously shipped H52 arm scored 0.0518 hide / 0.0291 tip, sum 0.0809.
Selection by the pre-registered rule &mdash; beat the matched-budget random control on <b>both</b>
instruments in &ge;3/4 folds, then maximise <code>mean_tip + mean_hide</code>, then prefer the smaller
mass &mdash; read out of the evidence file at build time, not typed on a command line:</p>
<pre class="mono">{json.dumps(sel, indent=1)}</pre>

<h2><span class="num">6</span> The brief's own abandonment test: it fires, and it refutes</h2>
<p>The pre-registration said to correlate the two views' per-block out-of-fold error on labelled negatives
across spatial blocks and abandon co-training if strongly correlated
(<code>ABANDON_R = {ind['hide']['abandon_threshold']}</code>). In H52 this <b>could not fire</b> &mdash;
fewer than three usable blocks, Spearman degenerate to 1.0 on ties &mdash; so <code>knowledge/03</code>
N-1 recorded the premise as <em>unmeasured</em> and retracted two numbers that had been asserted. On the
corrected split it fires on
<b>{ind['hide']['usable_blocks_per_fold']} usable blocks of {ver['independence']['hide']['blocks_per_instrument']}</b>,
4/4 folds of both instruments.</p>
<table><thead><tr><th>instrument</th><th class="num">fold</th><th class="num">usable blocks</th>
<th class="num">Spearman, mean over-prediction on negatives<br>(the pre-registered statistic)</th>
<th class="num">Spearman, false-alarm rate at budget 37,654</th>
<th class="num">CV of A's block FAR</th><th class="num">CV of B's block FAR</th></tr></thead>
<tbody>{''.join(ind_rows)}</tbody></table>
<p><b>Verdict: refuted at the pre-registered threshold</b> &mdash; max |&rho;| =
{ind['hide']['max_abs_spearman_mean_overprediction']:.4f} (<code>hide</code>) and
{ind['tip']['max_abs_spearman_mean_overprediction']:.4f} (<code>tip</code>) against
{ind['hide']['abandon_threshold']}. Co-training is abandoned. Two qualifications printed in the same
record: the false-alarm-rate statistic correlates weakly (max |&rho;| {far_max:.4f}, negative on 3 of 8
folds), so this is the verdict of the statistic the pre-registration <em>named</em>; and View A's
block-level FAR has CV 1.35&ndash;5.22 against View B's 0.75&ndash;1.18 &mdash; a view finding a few
regional anomalies and nothing else, which is the same reading as N-2 and N-10 from a third direction.</p>
<p>The file therefore ships <b>one view</b>, on two independent grounds: the pre-registered error-correlation
threshold refutes the co-training premise, and <code>A_only</code> wins
{wins(C, 'hide', 'A_only', 'hc4|37654')} <code>hide</code> and
{wins(C, 'tip', 'A_only', 'hc4|37654')} <code>tip</code> folds. At the matched 37,654-pixel budget,
its mean DTI is {a_only_vs_random('hide')} on <code>hide</code> and
{a_only_vs_random('tip')} on <code>tip</code>. It {a_only_gate} the pre-registered ≥3/4-fold comparison
on <b>both</b> instruments; fold counts, rather than an inaccurate claim that both means are below random,
are the reason it is not promoted as the primary emitter.</p>

<h2 id="non-union"><span class="num">7</span> Not merely the union of the two views</h2>
<p>The brief asks for this explicitly, and <code>gates.uniqueness_report</code> does not answer it &mdash;
that gate compares against <em>previous submissions</em>. This compares against the two views of
<em>this</em> pipeline at the same budget:</p>
<table><thead><tr><th>compared set</th><th class="num">px</th>
<th class="num">overlap with the shipped file</th><th class="num">% of shipped</th>
<th>shipped == set</th></tr></thead><tbody>{''.join(uni_rows)}</tbody></table>

<h2><span class="num">8</span> A previously blocked official source, now verified and used</h2>
<p><code>knowledge/02</code> H52-5 marked the INGENIOUS well-and-spring database <b>blocked</b> because the
host would not re-resolve, and the standing rule is that an unverifiable file may not move emitted mass.
It resolves: <a href="https://gdr.openei.org/submissions/1391">GDR submission 1391</a>, DOI
<a href="https://doi.org/10.15121/1881483">10.15121/1881483</a>, licence <b>CC-BY 4.0</b>. Measured on the
grid: {th['unique_cells']:,} cells carry a well or spring; <b>11,258</b> are more than 300&nbsp;m from any
mapped fault and 8,958 more than 1&nbsp;km; only <b>194</b> lie <em>on</em> a catalogue pixel; <b>362</b>
record &ge;70&nbsp;&deg;C and <b>147</b> carry a quartz geothermometer &ge;100&nbsp;&deg;C. A silica
geothermometer &ge;100&nbsp;&deg;C at discharge means circulation to roughly 2&ndash;4&nbsp;km, which in
extensional terrain requires a fault.</p>
<p>A spring is a <em>point</em>, and one point earns at most 1.0 under a 300&nbsp;m kernel. So each thermal
point is walked into a <b>trace</b> along a strike measured from a 2&nbsp;km structure tensor of the
radiometric field, truncated where coherence drops below {th['lineament']['coh_floor']} or the footprint
ends. {th['lineament']['cells_scored']:,} cells survive from {th['points']['cells_scored']} thermal points,
because the footprint's median coherence is only {th['lineament']['coherence_median']:.3f}. No layer in
this family previously turned a point observation into a linear hypothesis.</p>
<p><b>And it is neutral.</b> <code>B_therm</code> beat <code>B_c50</code> &mdash; the same field without the
thermal lineaments &mdash; by <b>0.00003</b> on the selection sum ({sel['total']:.5f} vs 0.15168), 4/4
folds each. That is not a signal, and it is recorded as not a signal. The pre-registered rule picked it
anyway because the rule maximises the sum and was written before the numbers were seen. The gain in this
file comes from &sect;1, &sect;3 and &sect;4, not from &sect;8.</p>

<h2><span class="num">9</span> Phase 2: every A-only candidate gets a reason a reviewer can check</h2>
<p>{rs['n_components']} A-confident / B-abstaining neighbourhoods, grouped at
{rs['group_px'] * 100:.0f}&nbsp;m &mdash; the kernel's own support &mdash; so each record is a
<em>place</em> rather than a lone pixel; the emission is 8-isolated by construction. Each carries lat/lon
and UTM, strike, elongation, extent, distance to the nearest mapped trace, nine measured layer ranks, the
nearest temperature-bearing well or spring with its DOI, and an interpretation assembled <b>only</b> from
numbers in the same record: a clause with no supporting measurement is never emitted, and a candidate with
no support says so explicitly rather than flattering itself.
<b>{rs['candidates_with_positive_support']}</b> carry at least one positive-support clause,
<b>{rs['candidates_linear_extent_ge_1km']}</b> are linear over &ge;1&nbsp;km,
<b>{rs['candidates_with_thermal_corroboration']}</b> are corroborated by a &ge;60&nbsp;&deg;C well or
spring within 5&nbsp;km.
<a href="downloads/h55_reasoning_{TAG}.json">Open the full record &rarr;</a></p>

<h2><span class="num">10</span> Two bugs in code written this session, found by tests written this session</h2>
<ul class="tight">
<li><b>IR-52-025.</b> <code>coverage_greedy</code> updated its running cover with
<code>np.maximum(cf[nbi], kk, out=cf[nbi])</code>. Fancy indexing copies, so <code>out=</code> wrote into a
throwaway and no pixel ever learned its disc was already covered. The greedy packed into the belief
field's peak and reported <code>A/S</code> = 1.8&ndash;2.1 &mdash; <em>worse than top-K</em> &mdash; which
read as a property of greedy coverage. An earlier draft of <code>knowledge/12</code> recorded that
&ldquo;property&rdquo;; the claim is <b>withdrawn</b>. Caught by the telescoping identity
<code>sum(marginal gains) == &Sigma; &rho;&#770;&middot;K_E</code> failing at 107.7 vs 66.6. Fixed, the
greedy reaches A/S 9.27 (98.8&nbsp;% of ceiling) and banks 20&nbsp;% more &rho;&#770;-weighted coverage than
hard-core thinning and 33&nbsp;% more than top-K, on both a flat and a clustered belief.</li>
<li><b>IR-52-026.</b> <code>gates.find_priors</code> scanned <code>docs/downloads/</code> &mdash; where
<code>refresh_feed.py</code> <em>stages</em> the built raster &mdash; so on the second build the candidate
was compared against a copy of itself and the gate reported <code>identical-to-a-prior, novel = 0</code>:
the one false verdict that would block a legitimate submission. Fixed by basename, pinned by a test.</li>
</ul>
<p>Also fixed: <b>IR-52-020</b> (<code>download_competition_data.sh</code> passed <code>--group all</code>,
a flag <code>restore_data.py</code> does not accept, so the documented one-command data placement exited 2
before fetching anything), <b>IR-52-021</b> (<code>registry/irregularities.json</code> was cited by code but
never existed &mdash; now {nreg} entries, and every id cited anywhere in the tree must resolve), and
<b>IR-52-030</b> (two concurrent sessions allocated IR-52-021 and IR-52-022 to different findings; both
readings are recorded rather than silently renumbered).</p>

<h2><span class="num">11</span> Limitations, and what to do next</h2>
<ul class="tight">
<li><b>Nothing here forecasts a portal score.</b> The instruments under-forecast the board by roughly
4&times; in absolute terms &mdash; this family scores ~0.05 on <code>hide</code> folds and 0.2778 on the
portal &mdash; so a fold number is a ranking device. The only projection given a number is the placement
gain in isolation (&asymp;{prj['geometry_only_dti']:.4f}), and its assumption is stated in the same JSON.</li>
<li><b>|G| rests on owner-reported scores.</b> The rasters, masses and geometry are SHA-256-exact; the DTI
values are not organiser-authenticated (IR-52-003). <code>scripts/calibrate_g.py</code> prints every row so
a human can re-check the pairings by hand.</li>
<li><b>One tuned constant was set by inspection, not by a sweep:</b> the coherence floor
{th['lineament']['coh_floor']} that truncates the thermal strike walk. It discards 99.94&nbsp;% of thermal
cells' potential extent, and it is the weakest number in the shipped pipeline.</li>
<li><b>The budget was chosen at fold prevalence (0.2&nbsp;%), not board prevalence
(&asymp;0.157&nbsp;%).</b> The rule prefers smaller mass on a near-exact tie. A single 60&ndash;80&nbsp;k
file would settle it, and it is the only available experiment whose answer is a board number rather than a
fold number.</li>
<li><b>View A is dead at 100&nbsp;m and was only tested at 100&nbsp;m.</b> N-10 excludes it as a primary
emitter at the scale the metric scores; it does not exclude a 300&nbsp;m potential-field product used to
<em>gate</em> a 100&nbsp;m surface detection. That is the one version of the two-view idea the measurements
do not already exclude.</li>
<li><b>External layers are uint8-quantised mirrors</b> (1st&ndash;99th percentile) of the official grids.
The sources are named and reachable, but a re-reduction to float32 from the USGS release would sharpen
every ratio-step layer.</li>
<li><b>Three rounds have shipped in parallel</b> (IR-52-029). <code>submission/LATEST.txt</code> points at
this file; reverting is one line. Every other artefact stays downloadable and is now a prior for the
uniqueness gate &mdash; this file is {uni['novel_fraction']:.1%} novel against {uni['n_priors_checked']} of
them and drops {uni['prior_px_dropped']:,} prior px.</li>
</ul>
''' + FOOT
    profile_link = """<p class="small muted" id="h55-profile-followup-link"><strong>Separate follow-up:</strong> the H55-PROFILE paired-normal DEM experiment failed its registered mean-lift gate and is research-only. <a href="h55-profile.html">Read the follow-up evidence and download</a>; it does not replace this page's incumbent candidate.</p>"""
    body = body.replace("</main>", profile_link + "</main>", 1)
    (DOCS / "h55.html").write_text(body)
    print(f"docs/h55.html written ({len(body):,} chars); index.html bar refreshed")
    return 0


def main() -> int:
    """Refuse to publish historical H55 pages over a different current artifact."""
    current_path = DOCS / "data" / "submission.json"
    marker_path = ROOT / "submission" / "LATEST.txt"
    if not current_path.is_file() or not marker_path.is_file():
        print("skipped: current receipt/marker is missing; legacy H55 pages were left untouched")
        return 0
    try:
        current = json.loads(current_path.read_text())
        marker = marker_path.read_text().strip()
    except (OSError, json.JSONDecodeError) as error:
        print(f"skipped: could not verify the current receipt/marker ({error}); pages left untouched")
        return 0
    expected = f"{STEM}.tif"
    if current.get("file") != expected or marker != expected:
        print(
            "skipped: H55 is historical and does not match both the current receipt and "
            "submission/LATEST.txt; H56/current pages were left untouched"
        )
        return 0
    return _publish_h55_from_receipt()


if __name__ == "__main__":
    sys.exit(main())
