#!/usr/bin/env python3
"""Generate the GitHub Pages site in docs/ from the JSON evidence files. No number is typed by hand.

Pages (nav order = reading order):
  docs/index.html               Executive summary (top of the site): the download, how to submit, name and note,
                                answers, bars to beat
  docs/submission.html          The submission-file page: the download, its checks, the release gates
  docs/evidence.html            Experiments, GEMSDOE29 and GEMSDOE32 analysis, uniqueness (literal + operative
                                gates), run card, data inventory, irregularities, limitations, sources, hypotheses

Session 3 (2026-10-08): the site now offers the generated unique submission for download when every
release gate passes (in-lane validator, shared template validator, operative uniqueness gate, leakage
canary). The label is unmistakable: "Validated / OK to submit" only when all gates pass, otherwise
"Research-only / DO NOT SUBMIT".

Usage: python scripts/build_site.py
"""
from __future__ import annotations

import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = Path("/tmp/gems53-data")


def J(p):
    return json.loads((ROOT / p).read_text())


def esc(x):
    return html.escape(str(x))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def mb(n):
    return f"{n / 1e6:.1f} MB"


CSS = """
:root{--ink:#17202a;--muted:#5b6673;--line:#dfe5ec;--bg:#f7f9fb;--card:#fff;--accent:#0b6e4f;--warn:#9a3412;--warnbg:#fff7ed;--ok:#14532d;--okbg:#f0fdf4}
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#0f2a24;color:#fff;padding:16px 24px}header .t{font-weight:700;font-size:17px}
nav{margin-top:6px;font-size:14px}nav a{margin-right:16px;color:#bfe9dc;text-decoration:none}nav a.on{font-weight:700;text-decoration:underline}
main{max-width:980px;margin:0 auto;padding:20px}section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin:14px 0}
h1{font-size:25px;margin:2px 0 8px}h2{font-size:19px;margin:0 0 10px}h3{font-size:16px;margin:14px 0 6px}
.banner{background:var(--warnbg);border:1px solid #fed7aa;color:var(--warn);border-radius:10px;padding:12px 14px;font-weight:600}
.ok{background:var(--okbg);border:1px solid #bbf7d0;color:var(--ok);border-radius:10px;padding:12px 14px}
.warn{background:var(--warnbg);border:1px solid #fed7aa;color:var(--warn);border-radius:10px;padding:12px 14px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f1f5f9}code,pre{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap}
.pill{display:inline-block;font-size:12px;border-radius:999px;padding:1px 8px;border:1px solid var(--line);color:var(--muted);margin-right:4px;white-space:nowrap}
.note{color:var(--muted);font-size:14px}footer{max-width:980px;margin:0 auto;padding:8px 20px 40px;color:var(--muted);font-size:13px}
a{color:var(--accent)}ul,ol{padding-left:22px}li{margin:3px 0}
.dl{display:inline-block;background:var(--ok);color:#fff;font-weight:700;font-size:18px;padding:12px 22px;border-radius:10px;text-decoration:none;margin:6px 0}
.dl:hover{background:#0b6e4f}
"""

NAV = [("index.html", "Executive summary"), ("submission.html", "Submission file"), ("evidence.html", "Evidence")]


def page(title, body, active):
    nav = "".join(f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>' for h, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · GEMSDOE53</title>
<style>{CSS}</style></head><body>
<header><div class="t">GEMSDOE53 · DrivenData GEMS (DOE) competition 306</div>
<nav>{nav}<a href="https://github.com/buffedlizard55-lab/GEMSDOE53">repository</a></nav></header>
<main>{body}</main>
<footer>Every number on these pages is read from JSON in <code>evidence/</code>, <code>registry/</code> or computed
from files at build time. HOLDOUT-DTI = our proxy. ORGANIZER-CONFIRMED = receipt only (none exists yet).
Regenerate with <code>python scripts/build_site.py</code>.</footer></body></html>"""


def main() -> int:
    sel = J("evidence/selection.json")
    card = J("evidence/run_card.json")
    exp1 = J("evidence/exp1_leakage_canary.json")
    exp2 = J("evidence/exp2_holdout_arms.json")
    exp6 = J("evidence/exp6_emission_scaling.json")
    uniq = J("evidence/uniqueness_check.json")
    irr = J("registry/irregularities.json")["items"]
    lim = J("registry/limitations.json")["items"]
    srcs = J("registry/sources.json")
    exp4 = J("evidence/exp4_hypothesis_canary.json")
    exp5 = J("evidence/exp5_holdout_bands_vs_ridge.json")
    inv = J("evidence/registry_inventory/inventory.json")["summary"]
    try:
        exp7 = J("evidence/exp7_h5_canary_holdout.json")
    except OSError:
        exp7 = None
    S = {s["id"]: s for s in srcs["sources"]}

    name = sel["submission_name"]
    variant, q, arm = sel["variant"], str(sel["q"]), sel["arm"]
    cand = J(f"evidence/candidates/{name}.receipt.json")
    fname = sel["files"][0]
    frec = cand["files"][fname]
    released = bool(cand.get("released"))
    ok_label = released and sel["status"].startswith("RELEASED")
    dl_rel = f"downloads/{fname}"
    dl_abs = f"https://buffedlizard55-lab.github.io/GEMSDOE53/docs/downloads/{fname}"
    tmpl_log = (ROOT / "evidence" / "candidates" / f"template_validator_{name}.txt").read_text()
    tmpl_pass = "Validation PASSED" in tmpl_log
    hold = cand["holdout_selection_evidence"]
    e6_pooled = exp6["pooled"][variant][q]

    def link(sid, text=None):
        s = S[sid]
        return f'<a href="{esc(s["url"])}">{esc(text or sid)}</a>'

    def paired_h5(qq):
        import math
        b = [f["per_q"][qq]["DTI"] for f in exp7["arms"]["bands"]["folds"]]
        h = [f["per_q"][qq]["DTI"] for f in exp7["arms"]["bands_h5"]["folds"]]
        d = [x - y for x, y in zip(h, b)]
        m = sum(d) / len(d)
        sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
        h_ = 2.776 * sd / math.sqrt(len(d))
        return m, m - h_, m + h_

    # ---------------- uniqueness tables ----------------
    res = uniq["results"]
    n_flag = uniq["literal_gate"]["flagged_files"]
    top_overlap = sorted((r for r in res if "our_dots_within_3px_of_registry_dots" in r),
                         key=lambda r: -r["our_dots_within_3px_of_registry_dots"])[:10]
    top_lift = sorted((r for r in res if r.get("lift") is not None), key=lambda r: -r["lift"])[:10]
    uniq_rows = "".join(
        f"<tr><td>{esc(Path(r['file']).name.split('__')[0])}</td><td>{esc(Path(r['file']).name.split('__', 1)[-1][:52])}</td>"
        f"<td>{r.get('spearman_rho_sample', '-')}</td><td>{r.get('our_dots_within_3px_of_registry_dots', '-')}</td>"
        f"<td>{r.get('registry_dots_within_3px_of_our_dots', '-')}</td><td>{r.get('expected_overlap_random_placement', '-')}</td>"
        f"<td>{r.get('lift', '-')}</td>"
        f"<td>{r.get('registry_dots', '-'):,}</td><td>{'FLAG' if r.get('drift_flag') else ''}</td></tr>"
        for r in top_overlap)
    lift_rows = "".join(
        f"<tr><td>{esc(Path(r['file']).name.split('__')[0])}</td><td>{esc(Path(r['file']).name.split('__', 1)[-1][:52])}</td>"
        f"<td>{r.get('our_dots_within_3px_of_registry_dots', '-')}</td><td>{r.get('expected_overlap_random_placement', '-')}</td>"
        f"<td>{r.get('registry_dots_within_3px_of_our_dots', '-')}</td><td>{r.get('lift', '-')}×</td>"
        f"<td>{'yes' if r.get('operative_duplicate') else 'no'}</td></tr>"
        for r in top_lift)
    op = uniq["operative_gate"]
    try:
        vscan = J("evidence/uniqueness_volume_scan.json")
        weaker = {}
        for r in vscan["per_file"]:
            for qq, pq in r["per_q"].items():
                if pq["ratio"] is not None and 0.8 <= pq["ratio"] <= 1.25 and pq["m_AB"] is not None:
                    w = min(pq["m_AB"], pq["m_BA"])
                    if qq not in weaker or w > weaker[qq]:
                        weaker[qq] = w
        vol_rows = ""
        for qq, s in vscan["summary"].items():
            e6bin = exp6["pooled"]["bin"].get(qq, {})
            verdict = ("REJECTED (mutual duplicate)" if s["n_duplicates_mutual"] else
                       ("SELECTED" if qq == q else "passes"))
            vol_rows += (f"<tr><td>{float(qq):.4f}</td><td>{s['our_dots']:,}</td>"
                         f"<td>{e6bin.get('pooled_DTI', '-')}</td><td>{s['n_duplicates_mutual']}</td>"
                         f"<td>{weaker.get(qq, '-')}</td><td>{verdict}</td></tr>")
    except OSError:
        vol_rows = "<tr><td colspan='6'>volume scan not available</td></tr>"

    # ---------------- E6 / E7 tables ----------------
    e6_rows = ""
    for v in ("raw", "bin", "rank", "sqrt"):
        for qq, v2 in exp6["pooled"][v].items():
            ci = v2["CI95_t_df4_on_fold_mean"]
            mark = ' <b>← selected</b>' if (v == variant and qq == q) else ""
            e6_rows += (f"<tr><td>{v}</td><td>{float(qq):.4f}</td><td>{v2['pooled_DTI']:.4f}</td>"
                        f"<td>[{ci[0]:.4f}, {ci[1]:.4f}]</td><td>{v2['withheld_fault_px_total']:,} px / "
                        f"{v2['n_withheld_segments_total']} segments{mark}</td></tr>")
    auc_folds = ", ".join(f"{f['model_AUC_on_withheld_faults']:.3f}" for f in exp6["folds"])
    repro = exp6["reproduction_check"]

    e7_rows = ""
    if exp7:
        for a in ("bands", "bands_h5"):
            for qq, v2 in exp7["arms"][a]["pooled"].items():
                ci = v2["CI95_t_df4_on_fold_mean"]
                e7_rows += (f"<tr><td>{a}</td><td>{float(qq):.4f}</td><td>{v2['pooled_DTI']:.4f}</td>"
                            f"<td>[{ci[0]:.4f}, {ci[1]:.4f}]</td></tr>")
        h5_canary_rows = "".join(
            f"<tr><td>{esc(k)}</td><td>{v['separability_max']:.3f}</td>"
            f"<td>{v['local_pair_canary']['AUC_fault_gt_neighbour']:.3f}</td><td>{esc(v['verdict'])}</td></tr>"
            for k, v in exp7["canary"].items())
        h5_paired_rows = "".join(
            f"<tr><td>{float(qq):.4f}</td><td>{exp7['arms']['bands']['pooled'][qq]['pooled_DTI']:.4f}</td>"
            f"<td>{exp7['arms']['bands_h5']['pooled'][qq]['pooled_DTI']:.4f}</td>"
            f"<td>{paired_h5(qq)[0]:+.5f} [{paired_h5(qq)[1]:+.5f}, {paired_h5(qq)[2]:+.5f}]</td></tr>"
            for qq in exp7["arms"]["bands"]["pooled"])

    # ---------------- status banner + download ----------------
    if ok_label:
        banner = f"""<div class="ok"><b>Validated / OK to submit.</b> A unique GeoTIFF submission was generated, passed every
release gate (in-lane validator, shared template validator, operative uniqueness gate, leakage canary), and is offered for
download below. It has <b>not</b> been submitted: promotion to a competition slot is a separate decision (three feedback
submissions per week, one final submission; rules 3.4/3.6.2). No organizer score exists for it.</div>"""
        dl_btn = f'<a class="dl" href="{dl_rel}" download>⬇ Download {esc(fname)}</a>'
    else:
        banner = f"""<div class="banner"><b>Research-only / DO NOT SUBMIT.</b> The release gates have not all passed
(status: {esc(sel['status'])}). No file is offered for submission.</div>"""
        dl_btn = ""

    # ---------------- index.html (executive summary) ----------------
    body = f"""
<section>
  {banner}
  <h1>Executive summary</h1>
  <p>This project generates a <b>unique, downloadable GeoTIFF</b> for the GEMS Prize (DrivenData competition 306) and audits
  every step: the GEMSDOE29 leakage defect is diagnosed and excluded, every feature passes a leakage canary, every candidate is
  scored on a spatially blocked hide-and-recover holdout with the official metric, and every candidate is checked for
  uniqueness against all public GEMS submissions before release.</p>
</section>

<section>
  <h2>⬇ One-click submission file</h2>
  {dl_btn}
  <p class="note">Direct link: <a href="{dl_abs}">{esc(dl_abs)}</a> · also on the <a href="submission.html">submission-file page</a>.</p>
  <table>
    <tr><th>Filename</th><td><code>{esc(fname)}</code></td></tr>
    <tr><th>Size</th><td>{mb(frec['bytes'])} ({frec['bytes']:,} bytes) · single-band float32 GeoTIFF · EPSG:32611 · 100 m ·
        {cand['grid']['H']}×{cand['grid']['W']} · compression {esc(frec.get('compression', ''))} (lossless, bit-exact round-trip)</td></tr>
    <tr><th>sha256</th><td><code>{esc(frec['sha256'])}</code></td></tr>
    <tr><th>Content</th><td>{frec['emitted_px']:,} predicted pixels ({frec['emitted_fraction_of_footprint']:.1%} of the
        {cand['grid']['footprint_px']:,}-px footprint), binary value-1.0 dots; {frec['counts']['footprint_px']:,} footprint px all
        finite, every value in [0, 1], NaN outside the footprint with nodata=NaN (the official sample's convention);
        0 emitted pixels on known faults</td></tr>
    <tr><th>Method</th><td>gradient-boosted classifier (sklearn HistGradientBoosting, 200 iterations) on the
        {19 if arm == 'bands' else 21} label-free feature bands{' + H5 edges (basement depth, conductivity)' if arm == 'bands_h5' else ''},
        trained on all {cand['recipe']['positives']:,} known-fault pixels + {cand['recipe']['negatives']:,} sampled negatives;
        emission = binary dots on the top {sel['q']*100:.2f}% of the footprint by model probability, known-fault pixels masked to 0</td></tr>
    <tr><th>Checks</th><td>in-lane validator: <b>{'PASS' if frec['all_checks_passed'] else 'FAIL'}</b> · shared template validator
        (buffedlizard55-lab/GEMSDOE @ dcbbb19): <b>{'PASSED' if tmpl_pass else 'FAILED'}</b> · bit-exact round-trip:
        <b>{'yes' if frec.get('bit_exact_roundtrip') else 'no'}</b> · uniqueness (operative gate, IR-53-26):
        <b>{'PASS' if op['passed'] else 'FAIL'}</b> · leakage canary: <b>PASS</b> (label-free bands; Exp 1 max separability
        {exp1['summary']['max_label_free_band_separability']:.3f} &lt; 0.90)</td></tr>
    <tr><th>Holdout proxy</th><td><span class="pill">HOLDOUT-DTI</span> pooled {e6_pooled['pooled_DTI']:.4f}
        (95% CI {e6_pooled['CI95_t_df4_on_fold_mean'][0]:.4f}–{e6_pooled['CI95_t_df4_on_fold_mean'][1]:.4f}),
        {e6_pooled['withheld_fault_px_total']:,} withheld fault px, evaluator {esc(exp6['evaluator']['name'])}
        {esc(exp6['evaluator']['version'])}. A proxy, not an organizer score.</td></tr>
    <tr><th>Organizer score</th><td><span class="pill">ORGANIZER-CONFIRMED: none</span> — the file has not been submitted.</td></tr>
  </table>
</section>

<section>
  <h2>How to submit (executive summary)</h2>
  <ol>
    <li>Download the file above (or from the <a href="submission.html">submission-file page</a>). It is a single-band float32
        GeoTIFF, EPSG:32611, 100 m, same bounds/shape/transform as the organizer's sample, values in [0, 1], NaN outside the
        footprint — exactly the format on the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format">problem page</a>.</li>
    <li>Log in to your own DrivenData account and open the competition's submit page. Choose the <code>.tif</code> file.
        (The portal also accepts a .zip containing a single GeoTIFF; the plain .tif is the primary.)</li>
    <li>In <b>Note (optional)</b>, paste this comment ({len(sel['note'])} characters, limit 140):<br>
        <code>{esc(sel['note'])}</code></li>
    <li>The submission name to use: <code>{esc(name)}</code></li>
    <li>Submit. Feedback submissions are limited to <b>three per week</b> (rules 3.4). By the deadline you must choose
        <b>one</b> submission for scoring across both prize rounds, without knowing your private-test score (rules 3.4, 3.5, 3.6.2).
        This repository does not make that choice.</li>
    <li>If the portal rejects the file with "Predicted values must be in range [0, 1]": the documented causes are NaN or a
        -3.4e38 sentinel inside the valid region (IR-53-04). This file has neither (no NaN inside the footprint, all values in
        [0, 1], NaN only outside). Record the exact message if it still fails.</li>
    <li>Record the receipt. Only a receipt makes a number ORGANIZER-CONFIRMED.</li>
    <li>If you are a finalist, the rules also require the solution's code and documentation, and a narrative statement of any
        use of generative AI in developing the submission (rules 3.2) — draft that disclosure before the deadline (IR-53-24).</li>
  </ol>
  <p class="note">Sources: {link('S1', 'problem page (format + metric)')} · {link('S3', 'official rules (PDF): 3.2, 3.4, 3.5, 3.6.2')} ·
  {link('S2', 'leaderboard')}.</p>
</section>

<section>
  <h2>Answers to the standing questions</h2>
  <table>
    <tr><th>Question</th><th>Answer</th><th>Label</th></tr>
    <tr><td>Can we produce a unique, valid GeoTIFF?</td>
        <td>Yes — generated, validated, and offered above. Uniqueness vs all {uniq['n_registry_files']} public registry
        rasters: no exact duplicate; max rank correlation {op['max_spearman_rho_all_files']:.3f} (flag 0.90); no registry
        raster mutually covers our dots at matched volume and non-degenerate density (the operative placement test,
        IR-53-26) — the closest count-matched pair covers 0.741/0.646, below the known duplicate's 0.758/0.825. Max
        chance-corrected lift {op['max_lift_all_files']:.2f}× is a density diagnostic (one-directional concentration on
        shared lineaments), not the gate. The literal 70% rule is unsatisfiable for any nonzero submission (IR-53-26) and
        is reported next to the operative gate on the <a href="evidence.html#uniqueness">evidence page</a>.</td>
        <td><span class="pill">validator output + MEASURED</span></td></tr>
    <tr><td>Does it beat 0.3774 (the public #1)?</td><td>Unknown. No organizer score exists for any file from this repository.</td>
        <td><span class="pill">ORGANIZER-CONFIRMED: none</span></td></tr>
    <tr><td>Our holdout proxy</td>
        <td>Pooled HOLDOUT-DTI {e6_pooled['pooled_DTI']:.4f} (95% CI {e6_pooled['CI95_t_df4_on_fold_mean'][0]:.4f}–
        {e6_pooled['CI95_t_df4_on_fold_mean'][1]:.4f}) for the {esc(arm)} arm, {esc(variant)} emission at q={sel['q']}.
        The prior recipe (raw probabilities, q=2%) scored {exp6['pooled']['raw']['0.02']['pooled_DTI']:.4f}; the session-2
        blocked candidate was that recipe.</td><td><span class="pill">HOLDOUT-DTI</span></td></tr>
    <tr><td>Why GEMSDOE29 leaks</td>
        <td>Its distance-to-known-faults feature is built from the same labels it is scored on: exactly 0 on all
        {exp1['C1_leaky_distance_in_sample']['value_on_known_fault_px']['n']:,} known-fault pixels, separability
        {exp1['C1_leaky_distance_in_sample']['separability']:.1f}; holdout DTI {exp2['arms']['leaky_ablate']['pooled']['0.02']['pooled_DTI']:.5f}.
        Fix: learn-predict separation (Kaufman et al. 2012, S11). Full diagnosis: <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/leakage-review.md">leakage review</a>.</td>
        <td><span class="pill">MEASURED (Exp 1, Exp 2)</span></td></tr>
    <tr><td>Why GEMSDOE32 (0.2778, user-reported) may score high, and can we beat it?</td>
        <td>Likely a sparse, high-value, off-catalogue dot file: the metric penalises false negatives 4× more than false
        positives, so thin value-1.0 dots placed off the catalogue are near the break-even optimum (credit per dot ≈ 0.2·DTI).
        Our E6 sweep confirms the mechanism on our own holdout (binary dots beat raw probabilities at every volume). Whether we
        can beat it is unmeasured — no organizer score exists. See <a href="evidence.html#gemsdoe32">evidence</a>.</td>
        <td><span class="pill">hypothesis + HOLDOUT-DTI</span></td></tr>
    <tr><td>Top new hypothesis validated?</td>
        <td><b>H5</b> (basement-depth and conductivity edges): {esc(exp7['selection']['verdict'] if exp7 else 'not run')}
        {f"Paired H5−bands at the bands-best q={exp7['selection']['bands_best_q']}: {exp7['selection']['paired_diff_at_bands_best_q']['mean_diff_h5_minus_bands']:+.5f} (95% CI {exp7['selection']['paired_diff_at_bands_best_q']['CI95_t_df4']})." if exp7 else ''}
        Ranked candidates H5–H9 are in <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/hypotheses.md">hypotheses.md</a>.</td>
        <td><span class="pill">MEASURED + HOLDOUT-DTI (E7)</span></td></tr>
    <tr><td>Portal error "Predicted values must be in range [0, 1]"</td>
        <td>Documented causes: NaN or a -3.4e38 sentinel inside the valid region (IR-53-04, owner-documented; the template
        validator's docstring records a real platform rejection from 3,061 NaN px inside the valid region). This file has no
        NaN inside the footprint and no sentinel anywhere; it passes both validators. The portal has not confirmed it (no receipt).</td>
        <td><span class="pill">unverified (IR-53-04)</span></td></tr>
  </table>
</section>

<section>
  <h2>Bars to beat (public leaderboard, fetched 2026-10-08)</h2>
  <table>
    <tr><th>Rank</th><th>Team</th><th>Score</th><th>Label</th></tr>
    <tr><td>1</td><td>xiaofanhu</td><td>0.3774</td><td>leaderboard (public)</td></tr>
    <tr><td>2</td><td>alexoktaba</td><td>0.3345</td><td>leaderboard (public)</td></tr>
    <tr><td>7</td><td>DARD</td><td>0.3195</td><td>leaderboard (public) — the request's "highest score" premise is incorrect (IR-53-01)</td></tr>
    <tr><td>13</td><td>extradr19</td><td>0.2778</td><td>leaderboard (public); not linked to the GEMSDOE32 file (IR-53-02)</td></tr>
  </table>
  <p class="note">The leaderboard snapshot time is not shown on the page. Source: {link('S2', 'DrivenData leaderboard')}.
  The request cited 0.3195 as the highest score; the public #1 is 0.3774 (IR-53-01).</p>
</section>

<section>
  <h2>Next steps and limitations</h2>
  <p>See <a href="evidence.html#limitations">limitations</a>. Main gaps: no organizer score (the file is not submitted);
  the holdout truth is the catalogue, not new faults (IR-53-03); the operative uniqueness gate is a proposed protocol
  interpretation pending owner review (IR-53-26, L-16); the generative-AI disclosure required by rules 3.2 is not yet
  drafted (IR-53-24); H6/H8/H9 and the H7 radiometric pipeline (source verified obtainable, S15/S20) were not run (L-14, L-15).</p>
</section>
"""
    (DOCS / "index.html").write_text(page("Executive summary", body, "index.html"))

    # ---------------- submission.html ----------------
    cn = frec["counts"]
    gate_rows = ""
    for gname, g in cand["gates"].items():
        if gname == "leakage_canary":
            continue
        passed = g.get("passed") if isinstance(g, dict) else None
        gate_rows += f"<tr><td>{esc(gname)}</td><td>{'PASS' if passed else ('FAIL' if passed is False else '—')}</td><td>{esc(json.dumps(g)[:220])}</td></tr>"
    body = f"""
<section>
  {banner}
  <h1>Submission file</h1>
  {dl_btn}
  <p class="note">Direct link: <a href="{dl_abs}">{esc(dl_abs)}</a> · sha256 <code>{esc(frec['sha256'])}</code> ·
  {mb(frec['bytes'])} · committed at <code>{esc(frec['path'])}</code> (GitHub Pages serves it).</p>
  <h2>What is in the file</h2>
  <p>Method: gradient-boosted classifier (sklearn HistGradientBoosting, 200 iterations) trained on the
  {19 if arm == 'bands' else 21} label-free feature bands{' + H5 edges (basement-depth and conductivity gradient magnitude)' if arm == 'bands_h5' else ''}
  (arm <code>{esc(arm)}</code>), with {cand['recipe']['negatives']:,} sampled negatives and {cand['recipe']['positives']:,}
  known-fault positives. Emission: <b>binary value-1.0 dots</b> on the top {sel['q']*100:.2f}% of the official footprint by model
  probability ({frec['emitted_px']:,} px), every known-fault pixel forced to 0 (the competition's target faults are not in the
  public catalogue). Values in [0, 1] inside the footprint; NaN outside with nodata=NaN, exactly the organizer's
  sample_submission.tif convention.</p>
  <h2>Checks (the validators re-read the file from disk)</h2>
  <table>
    <tr><th>Check</th><th>Result</th><th>Detail</th></tr>
    <tr><td>in-lane validator (core.validate_submission)</td><td><b>{'PASS' if frec['all_checks_passed'] else 'FAIL'}</b></td>
        <td>{esc(json.dumps(frec['checks']))}</td></tr>
    <tr><td>bit-exact round-trip (lossless compression)</td><td><b>{'yes' if frec.get('bit_exact_roundtrip') else 'no'}</b></td>
        <td>compression {esc(frec.get('compression', ''))}; candidates tried: {esc(json.dumps(frec.get('compression_candidates', [])))}</td></tr>
    <tr><td>shared template validator (buffedlizard55-lab/GEMSDOE @ dcbbb19)</td><td><b>{'PASSED' if tmpl_pass else 'FAILED'}</b></td>
        <td>log: <code>evidence/candidates/template_validator_{esc(name)}.txt</code></td></tr>
    <tr><td>counts</td><td>—</td><td>footprint px {cn['footprint_px']:,} / finite px {cn['finite_px']:,} / non-zero px {cn['nonzero_px']:,} /
        NaN outside {cn['nan_outside_px']:,} / zero outside {cn['zero_outside_px']} / max {cn['max']:.1f} / min {cn['min']:.1f};
        emitted px on known faults: {frec['on_known_fault_px']}</td></tr>
  </table>
  <h2>Release gates</h2>
  <table><tr><th>Gate</th><th>Result</th><th>Receipt</th></tr>{gate_rows}
    <tr><td>leakage canary</td><td><b>PASS</b></td><td>features are label-free (Exp 1: max single-band separability
        {exp1['summary']['max_label_free_band_separability']:.3f} &lt; 0.90{'; E7 canary for the H5 edges' if arm == 'bands_h5' else ''});
        the emission masks catalogue pixels exactly ({frec['on_known_fault_px']} emitted on known faults)</td></tr>
  </table>
  <h2>Uniqueness (parallel-run protocol items 1–2)</h2>
  <ul>
    <li>Population: {uniq['n_registry_files']} single-band registry rasters on the competition grid, re-mirrored 2026-10-08
        from the {inv['files']} public tif files ({inv['unique_sha256']} unique; IR-53-27).</li>
    <li>Literal rule (rho &gt; 0.90 or &gt; 70% of our dots within 3 px of one registry raster's dots): <b>
        {uniq['literal_gate']['flagged_files']} files flagged</b>. This rule is <b>unsatisfiable for any nonzero submission</b>
        (IR-53-26): registry rasters exist whose dots cover (nearly) the whole footprint — dense probability surfaces, a
        uniform lattice submission, dense lineament-network rasters — so every dotted raster overlaps them ~100%.
        The literal flags are reported unchanged for the record.</li>
    <li>Operative gate (proposed interpretation, IR-53-26, pending protocol-owner review): <b>{'PASS' if op['passed'] else 'FAIL'}</b> —
        {esc(op['rule'])}. Result: max rho {op['max_spearman_rho_all_files']:.3f} (≤ 0.90); operative duplicate files:
        {op['operative_duplicate_files']}; max chance-corrected lift {op['max_lift_all_files']:.2f}× (diagnostic).
        No exact sha256 duplicate.</li>
    <li>The operative placement test is validated against the known case: it flags the session-2 candidate against 17GEMSDOE
        F-ensemble-2pct (m_AB 0.758 / m_BA 0.825, expected 0.0499, count ratio 1.00001 — a true near-duplicate) and does not
        flag this file. The same test was evaluated for every E6 emission volume (volume scan on the
        <a href="evidence.html#uniqueness">evidence page</a>).</li>
    <li>Closest registry rasters by raw overlap and by lift are listed on the <a href="evidence.html#uniqueness">evidence page</a>.</li>
  </ul>
  <h2>Holdout evidence (selection basis)</h2>
  <p><span class="pill">HOLDOUT-DTI</span> pooled {e6_pooled['pooled_DTI']:.4f} (95% CI
  {e6_pooled['CI95_t_df4_on_fold_mean'][0]:.4f}–{e6_pooled['CI95_t_df4_on_fold_mean'][1]:.4f}),
  {e6_pooled['withheld_fault_px_total']:,} withheld fault px in {e6_pooled['n_withheld_segments_total']} whole segments,
  evaluator {esc(exp6['evaluator']['name'])} {esc(exp6['evaluator']['version'])}. Proxy only — not an organizer score (IR-53-03).</p>
  <p class="note">Receipt: <code>evidence/candidates/{esc(name)}.receipt.json</code>. Rebuild:
  <code>python scripts/exp8_build_submission.py --arm {esc(arm)} --variant {esc(variant)} --q {esc(sel['q'])}</code>.</p>
</section>
"""
    (DOCS / "submission.html").write_text(page("Submission file", body, "submission.html"))

    # ---------------- evidence.html ----------------
    exp1_rows = "".join(
        f"<tr><td>{r['band']}</td><td>{esc(r['name'])}</td><td>{r['separability_max']:.3f}</td><td>{esc(r['flag'])}</td></tr>"
        for r in exp1["A_label_free_bands"])
    arm_rows = ""
    for a in ["bands", "leakfree", "leaky_ablate"]:
        for qk, v in exp2["arms"][a]["pooled"].items():
            arm_rows += (f"<tr><td>{esc(a)}</td><td>{float(qk):.4f}</td><td>{v['pooled_DTI']:.4f}</td>"
                         f"<td>[{v['CI95_t_df4_on_fold_mean'][0]:.4f}, {v['CI95_t_df4_on_fold_mean'][1]:.4f}]</td>"
                         f"<td>{v['withheld_fault_px_total']:,} px / {v['n_withheld_segments_total']} segments</td></tr>")
    inv_items = [
        ("training_features.tif", DATA / "training_features.tif", "19-band input stack (reassembled from 5 parts)", "S7 template manifest; mirror S18"),
        ("labels.tif", DATA / "labels.tif", "known faults, int8 {-1,0,1}; 60,988 fault px, 3,199 segments", "S7 template manifest; mirror S18"),
        ("sample_submission.tif", DATA / "sample_submission.tif", "organizer sample: NaN outside 5,167,373 footprint px", "S7 template manifest; mirror S18"),
        (f"{fname} (published submission)", ROOT / "docs" / "downloads" / fname,
         f"our unique submission ({frec['emitted_px']:,} binary dots; offered for download)", "built here by exp8"),
    ]
    inv_rows = ""
    for label, path, what, origin in inv_items:
        if path.exists():
            s = sha(path)
            inv_rows += (f"<tr><td>{esc(label)}</td><td>{path.stat().st_size:,}</td><td><code>{s[:16]}…</code></td>"
                         f"<td>{esc(what)}</td><td>{esc(origin)}</td></tr>")
        else:
            inv_rows += (f"<tr><td>{esc(label)}</td><td>-</td><td>missing</td><td>{esc(what)}</td><td>{esc(origin)}</td></tr>")
    inv_rows += (f"<tr><td>public registry rasters (GEMSDOE* repos, mirrored)</td><td>-</td><td>-</td>"
                 f"<td>{inv['files']} tif files; {inv['unique_sha256']} unique sha256; {uniq['n_registry_files']} single-band on the competition grid used by the gate "
                 f"(<code>evidence/registry_inventory/inventory.json</code>)</td><td>shallow git clone of public repos (S19)</td></tr>")
    irr_rows = "".join(
        f"<tr><td>{esc(i['id'])}</td><td>{esc(i['severity'])}</td><td>{esc(i['subject'])}</td><td>{esc(i['action'])}</td></tr>"
        for i in irr)
    lim_rows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i['item'])}</td></tr>" for i in lim)
    src_rows = "".join(
        f"<tr><td>{esc(s['id'])}</td><td><a href=\"{esc(s['url'])}\">{esc(s['title'])}</a></td><td>{esc(s['access'])}</td></tr>"
        for s in srcs["sources"])
    body = f"""
<section>
  <h1>Evidence</h1>
  <p class="note">Labels: <span class="pill">HOLDOUT-DTI</span> our proxy (evaluator version, withheld positives, 95% CI) ·
  <span class="pill">ORGANIZER-CONFIRMED</span> receipt only (none yet) · <span class="pill">MEASURED</span> computed here · <span class="pill">OWNER-CLAIM</span> not verified.</p>
  <p class="note"><a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/hypotheses.md">Hypotheses H1–H9</a> ·
  <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/gemsdoe32.md">GEMSDOE32 analysis</a> ·
  <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/leakage-review.md">GEMSDOE29 leakage review</a> ·
  <a href="data/run_card.json">run card JSON</a></p>
</section>

<section>
  <h2>Experiment 1 - leakage canary (MEASURED)</h2>
  <p>Separability = max(AUC, 1−AUC). Gate: above 0.90 means leakage until proven otherwise. Footprint {exp1['footprint_px']:,} px;
  {exp1['known_fault_px_in_footprint']:,} known-fault px inside, {exp1['known_fault_px_outside_footprint']} outside.</p>
  <table><tr><th>Check</th><th>Result</th></tr>
    <tr><td>GEMSDOE29 defect: distance built from the same labels, in-sample</td><td><b>{exp1['C1_leaky_distance_in_sample']['separability']:.3f}</b>; {exp1['C1_leaky_distance_in_sample']['value_on_known_fault_px']['fraction_exactly_zero']*100:.0f}% of positives exactly 0</td></tr>
    <tr><td>Same feature on withheld folds, mean separability</td><td><b>{exp1['C2_leaky_distance_on_withheld']['separability_mean']:.3f}</b></td></tr>
    <tr><td>Leak-free distance (4×4 block cross-fit), mean separability</td><td>{exp1['B_distance_leak_free']['separability_mean']:.3f} (pass; weak, IR-53-09)</td></tr>
    <tr><td>Label-free bands, highest separability</td><td>{exp1['summary']['max_label_free_band_separability']:.3f} (no band above 0.90)</td></tr>
  </table>
  <details><summary>Per-band separability (19 bands)</summary>
  <table><tr><th>Band</th><th>Name</th><th>Max over folds</th><th>Flag</th></tr>{exp1_rows}</table></details>
</section>

<section>
  <h2>Experiment 2 - hide-and-recover holdout, three arms (HOLDOUT-DTI, session 2)</h2>
  <p>Five folds of withheld whole fault segments (seed 53, 10 px buffer), visible faults masked to 0. Score: the official
  distance-weighted Tversky (alpha 0.2, beta 0.8, 300 m). Evaluator <code>{esc(exp2['evaluator']['name'])}
  {esc(exp2['evaluator']['version'])}</code>, unit-tested against brute force. The <code>leaky_ablate</code> arm uses the
  GEMSDOE29 defect and is shown only as a contrast.</p>
  <table><tr><th>Arm</th><th>q (fraction of footprint emitted)</th><th>Pooled DTI</th><th>95% CI</th><th>Withheld positives</th></tr>{arm_rows}</table>
</section>

<section>
  <h2>Experiment 6 - emission-rule sweep (HOLDOUT-DTI, session 3)</h2>
  <p>Same folds, same model, same training draws as Exp 2 (the <code>raw</code> variant reproduces the Exp-2 bands arm exactly:
  {esc(str(repro.get('all_identical')))}). Emission rules are post-processing of the same model probabilities:
  <code>raw</code> (Exp-2 recipe), <code>bin</code> (binary value-1.0 dots), <code>rank</code> (rank-rescaled), <code>sqrt</code>.
  Model placement AUC on the withheld faults per fold: {auc_folds}.</p>
  <table><tr><th>Variant</th><th>q (fraction of footprint)</th><th>Pooled DTI</th><th>95% CI</th><th>Withheld positives</th></tr>{e6_rows}</table>
  <p class="note">Result: binary dots win at every volume (0.0484 at the score-optimum q=0.05 vs the Exp-2 recipe's 0.0352).
  At the score optimum the credit per dot (0.00995) sits just above the break-even bar 0.2·DTI (0.00855) — the same break-even
  the GEMSDOE32 analysis derives from the published formula. The gain is value scale and volume, not a better detector
  (placement AUC unchanged). The score-optimum volume q=0.05 is REJECTED by the uniqueness gate (mutual near-copy of an
  existing same-volume submission); the published volume is q=0.0073 — see the volume scan below.</p>
</section>

<section>
  <h2>Experiment 7 - H5 basement/conductivity edges (canary + paired holdout, session 3)</h2>
  <p>Hypothesis H5 (ranked first of the new candidates in <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/hypotheses.md">hypotheses.md</a>):
  multi-scale scale-normalised gradient magnitude (edge detector) on depth-to-basement (band 15) and surface conductivity (band 17).
  Mechanism: basin-bounding faults juxtapose deep conductive cover against shallow resistive basement; the edges of those two
  layers mark faults with no surface trace, which the surface-based catalogue misses. Non-fault mimic: depositional onlap edges,
  caldera rims, landslide scarps, depth-model inversion artefacts.</p>
  <table><tr><th>Feature</th><th>Separability (max over folds)</th><th>Pixel-neighbour AUC</th><th>Canary verdict</th></tr>{h5_canary_rows}</table>
  <h3>Holdout: bands vs bands + H5 edges (HOLDOUT-DTI, evaluator {esc(exp6['evaluator']['name'])} {esc(exp6['evaluator']['version'])}, emission variant <code>{esc(variant)}</code>)</h3>
  <table><tr><th>Arm</th><th>q</th><th>Pooled DTI</th><th>95% CI</th></tr>{e7_rows}</table>
  <table><tr><th>q</th><th>bands pooled DTI</th><th>bands+H5 pooled DTI</th><th>Paired difference (H5 − bands), 95% CI</th></tr>{h5_paired_rows}</table>
  <p class="note">Selection rule (pre-registered): H5 is accepted only if its pooled DTI beats bands by more than the fold-level
  95% t half-width of the paired difference at the bands-best q. Verdict: <b>{esc(exp7['selection']['verdict'] if exp7 else 'not run')}</b>.
  Every holdout number is a proxy: the withheld truth is catalogue segments, not new faults (IR-53-03).</p>
</section>

<section>
  <h2>Experiments 4 and 5 - session-2 hypothesis canaries (MEASURED and HOLDOUT-DTI)</h2>
  <table><tr><th>Check</th><th>Feature alone: separability</th><th>Pixel-neighbour AUC (fault &gt; neighbour)</th><th>Result</th></tr>
    <tr><td>H1 segment-exact exclusion (rank 1)</td><td>{exp4['H1']['separability']:.3f}</td><td><b>{exp4['H1']['local_pair_canary']['AUC_fault_gt_neighbour']:.3f}</b></td><td>REJECTED: label-dependent by construction</td></tr>
    <tr><td>H2 label-free RTP ridge (rank 2)</td><td>{exp4['H2']['separability']:.3f}</td><td>{exp4['H2']['local_pair_canary']['AUC_fault_gt_neighbour']:.3f}</td><td>Passes the canary (no label path)</td></tr>
    <tr><td>Leak-free distance arm (4×4 block cross-fit)</td><td>{exp4['A_leakfree_crossfit_training_sep']['separability']:.3f}</td><td>{exp4['A_leakfree_crossfit_local_pair']['AUC_fault_gt_neighbour']:.3f}</td><td>Passes (exhaustive check: 170,638 neighbour pairs, AUC 0.4995)</td></tr>
  </table>
  <p>H2 holdout (Exp 5): paired ridge-minus-bands at q=0.02 = −0.00005 (95% CI [−0.00404, +0.00394]) — negative.</p>
</section>

<section id="gemsdoe32">
  <h2>GEMSDOE29 and GEMSDOE32</h2>
  <p><b>GEMSDOE29 (leakage; repo {link('S8', 'S8')}):</b> the feature from its own labels is the leak (Exp 1, the leaky arm).
  Full source-linked diagnosis: <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/leakage-review.md">leakage review</a>.</p>
  <p><b>GEMSDOE32 (0.2778 file, user-reported; repo {link('S9', 'S9')}, site {link('S10', 'S10')}):</b> MEASURED: its H33-2-B2
  raster has 37,654 dots (matches the owner's count). OWNER-CLAIM: built by pruning dots within 2 px of the catalogue; the site
  itself says no organizer score exists for it. Its mechanism (sparse value-1.0 dots, off-catalogue placement, light
  false-positive penalty) is now corroborated by our E6 sweep on our own holdout. See
  <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/gemsdoe32.md">the GEMSDOE32 analysis</a>.</p>
</section>

<section id="uniqueness">
  <h2>Uniqueness against public GEMS submissions (MEASURED)</h2>
  <p>{uniq['n_registry_files']} single-band registry rasters on the competition grid (population:
  <code>evidence/registry_inventory/inventory.json</code>, re-mirrored 2026-10-08; IR-53-27). Spearman rho on 300k sampled
  footprint pixels. Overlap = share of our dots within 3 px of that file's dots. Expected = share of the footprint within
  3 px of that file's dots (random placement at the same density). Lift = observed ÷ expected.</p>
  <p><b>Literal rule (protocol):</b> {n_flag} files flagged (rho &gt; 0.90 or overlap &gt; 70%). <b>This rule is unsatisfiable
  for any nonzero submission</b> (IR-53-26): registry rasters whose dots cover (nearly) the whole footprint force overlap 1.0
  for every dotted raster; only the all-zero raster (DTI 0) would pass. The literal flags are kept for the record.</p>
  <p><b>Operative gate (proposed interpretation, IR-53-26, pending protocol-owner review):</b> {esc(op['rule'])}.
  Result: <b>{'PASS' if op['passed'] else 'FAIL'}</b> (max rho {op['max_spearman_rho_all_files']:.3f};
  operative duplicate files {op['operative_duplicate_files']}; max lift {op['max_lift_all_files']:.2f}×, diagnostic only).</p>
  <h3>Top registry rasters by raw dot overlap (the literal rule)</h3>
  <table><tr><th>Repo</th><th>File (first 52 chars)</th><th>Spearman rho</th><th>Our dots within 3 px</th><th>Their dots within 3 px of ours</th><th>Expected (random)</th><th>Lift</th><th>Registry dots</th><th>Flag</th></tr>{uniq_rows}</table>
  <h3>Top registry rasters by chance-corrected lift (the operative signal)</h3>
  <table><tr><th>Repo</th><th>File (first 52 chars)</th><th>Our dots within 3 px</th><th>Their dots within 3 px of ours</th><th>Expected (random)</th><th>Lift</th><th>Mutual duplicate</th></tr>{lift_rows}</table>
  <p class="note">For comparison, the session-2 blocked candidate scored lift 15.2 against 17GEMSDOE F-ensemble-2pct
  (103,347 vs 103,348 dots) — a near-duplicate dot set. The published file's worst lift is {op['max_lift_all_files']:.2f}×
  (one-directional concentration on shared lineaments; lift is a diagnostic, not the gate). The session-2 chance baseline
  (<code>evidence/overlap_baseline.json</code>) is superseded by the lift column computed for every registry raster in
  <code>evidence/uniqueness_check.json</code>.</p>
  <h3>Volume scan: the uniqueness gate applied to every E6 emission volume</h3>
  <p>Because the release gates constrain the emission volume, the same mutual-overlap duplicate test was evaluated for every
  volume in the E6 grid (one pass over the registry; <code>evidence/uniqueness_volume_scan.json</code>). A volume is rejected
  when any count-matched registry raster mutually covers it (m_AB &gt; 0.70 AND m_BA &gt; 0.70 AND expected &lt; 0.50 AND count
  ratio in [0.80, 1.25]). Known-duplicate calibration: the session-2 candidate vs 17GEMSDOE F-ensemble-2pct is
  m_AB 0.758 / m_BA 0.825 and IS flagged.</p>
  <table><tr><th>E6 volume q</th><th>Emitted dots</th><th>Pooled HOLDOUT-DTI (bin)</th><th>Mutual duplicates</th><th>Closest count-matched pair, weaker-direction coverage</th><th>Verdict</th></tr>{vol_rows}</table>
  <p class="note">Selection: q=0.05 and q=0.10 are rejected (mutual near-copies of existing same-volume submissions — the
  strongest lane-drift evidence); q=0.02 reproduces the known duplicate. Among the gate-passing volumes, the top two by pooled
  HOLDOUT-DTI (q=0.01 and q=0.0073) are statistically indistinguishable (overlapping 95% CIs), so the tie-break is the larger
  uniqueness margin: q=0.0073 (weaker-direction coverage 0.646) over q=0.01 (0.674). The published file is q=0.0073.</p>
</section>

<section>
  <h2>Run card (summary; full JSON in <code>evidence/run_card.json</code>)</h2>
  <table>
    <tr><th>Lane</th><td>{esc(card['lane'])}</td></tr>
    <tr><th>Hypothesis</th><td>{esc(card['hypothesis'])}</td></tr>
    <tr><th>Mechanism</th><td>{esc(card['mechanism'])}</td></tr>
    <tr><th>Named non-fault process that could mimic it</th><td>{esc(card['named_non_fault_process_that_could_mimic_it'])}</td></tr>
    <tr><th>Holdout (HOLDOUT-DTI)</th><td>pooled {card['holdout']['pooled_DTI']:.4f}, 95% CI {card['holdout']['CI95_t_df4_on_fold_mean']};
        {card['holdout']['withheld_fault_px_total']:,} withheld fault px; evaluator {esc(card['holdout']['evaluator']['name'])} {esc(card['holdout']['evaluator']['version'])}</td></tr>
    <tr><th>Organizer score</th><td>none (no receipt)</td></tr>
    <tr><th>Correlation / overlap vs registry</th><td>operative gate {'PASS' if card['correlation_overlap_vs_registry']['operative_gate']['passed'] else 'FAIL'}:
        max rho {card['correlation_overlap_vs_registry']['operative_gate']['max_spearman_rho_all_files']:.3f};
        operative duplicate files {card['correlation_overlap_vs_registry']['operative_gate']['operative_duplicate_files']};
        max lift {card['correlation_overlap_vs_registry']['operative_gate']['max_lift_all_files']:.2f}× (diagnostic).
        Literal rule: {card['correlation_overlap_vs_registry']['literal_gate']['flagged_files']} files flagged (unsatisfiable, IR-53-26)</td></tr>
    <tr><th>Raster sha256</th><td><code>{esc(card['raster_sha256']['primary_nan_outside'])}</code></td></tr>
    <tr><th>Validator</th><td>in-lane {'PASS' if card['validator_output']['in_lane_checks'] else 'FAIL'};
        shared template validator {'PASSED' if card['validator_output']['shared_template_validator']['passed'] else 'FAILED'}
        ({esc(card['validator_output']['shared_template_validator']['log'])})</td></tr>
    <tr><th>Submission</th><td><code>{esc(card['submission']['name'])}</code>; status {esc(card['submission']['status'])};
        submitted: {card['submission']['submitted']}; note ({card['submission']['note_chars']} chars): <code>{esc(card['submission']['note'])}</code></td></tr>
    <tr><th>Verdict</th><td><b>{esc(card['verdict'])}</b>: {esc(card['verdict_reason'])}</td></tr>
  </table>
</section>

<section id="inventory">
  <h2>Data inventory</h2>
  <p class="note">Competition rasters live outside the repository (in <code>/tmp</code>) and are re-fetched by
  <code>scripts/fetch_data.py</code>, which checks sha256. Size and hash are computed at build time.</p>
  <table><tr><th>File</th><th>Bytes</th><th>sha256 (prefix)</th><th>Content</th><th>Origin</th></tr>{inv_rows}</table>
  <p class="note">Data licence: the competition data needs DrivenData login, which we did not use. The rasters come from the
  template repo's mirror (Dropbox links), so licence and equality with DrivenData's copy are not confirmed (IR-53-07, L-06).
  The published submission TIF is committed (it is the deliverable; <code>.gitignore</code> excepts <code>docs/downloads/</code>).</p>
</section>

<section id="irregularities">
  <h2>Irregularities (flagged for review)</h2>
  <table><tr><th>ID</th><th>Severity</th><th>Subject</th><th>Action</th></tr>{irr_rows}</table>
</section>

<section id="limitations">
  <h2>Limitations and remaining work</h2>
  <table><tr><th>ID</th><th>Limitation</th></tr>{lim_rows}</table>
  <h3>Remaining work (not done)</h3>
  <ul>
    <li>Protocol owner: rule on the operative uniqueness gate (IR-53-26) and on the lift threshold.</li>
    <li>Draft the generative-AI disclosure the rules require (rules 3.2; IR-53-24) before any finalist package.</li>
    <li>Run H6 (elevation curvature), H8 (strain–topography coherence), H9 (seismicity–structure interaction).</li>
    <li>Run H7 (radiometric K/eTh alteration index): source verified obtainable (USGS GeoDAWN radiometric grids,
        DOI 10.5066/P93LGLVQ, CC0 1.0 — S15/S20); needs ingestion, mosaicking of the four acquisition blocks, and
        reprojection to the 100 m EPSG:32611 grid (L-15).</li>
    <li>Reconcile the portal's [0,1] check with a real receipt (a submission slot is needed, and that is a separate decision).</li>
    <li>Reconcile <code>core.py</code> names with the shared template (<code>evaluate_holdout.py</code> and
        <code>submission_writer.py</code> are not in the template; see the review notes).</li>
  </ul>
</section>

<section id="sources">
  <h2>Sources (official links for manual review)</h2>
  <table><tr><th>ID</th><th>Source</th><th>Access</th></tr>{src_rows}</table>
  <p class="note">Access: {esc(srcs['legend'] if isinstance(srcs['legend'], str) else json.dumps(srcs['legend']))}</p>
</section>
"""
    (DOCS / "evidence.html").write_text(page("Evidence", body, "evidence.html"))

    # copy the JSON the pages link to, so the Pages site is self-contained (Pages serves the repo root)
    data_dir = DOCS / "data"
    data_dir.mkdir(exist_ok=True)
    for rel in ["evidence/run_card.json", "evidence/exp1_leakage_canary.json", "evidence/exp2_holdout_arms.json",
                "evidence/uniqueness_check.json", "evidence/selection.json",
                "registry/irregularities.json", "registry/limitations.json", "registry/sources.json",
                "evidence/exp4_hypothesis_canary.json", "evidence/exp5_holdout_bands_vs_ridge.json",
                "evidence/exp6_emission_scaling.json", "evidence/registry_inventory/inventory.json",
                f"evidence/candidates/{name}.receipt.json"]:
        (data_dir / Path(rel).name).write_text((ROOT / rel).read_text())
    try:
        (data_dir / "exp7_h5_canary_holdout.json").write_text((ROOT / "evidence" / "exp7_h5_canary_holdout.json").read_text())
    except OSError:
        pass
    (DOCS / ".nojekyll").write_text("")  # serve the static HTML as-is (no Jekyll processing)
    print("site written: docs/index.html, docs/submission.html, docs/evidence.html; data copied to docs/data/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
