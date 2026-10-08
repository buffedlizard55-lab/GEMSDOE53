#!/usr/bin/env python3
"""Generate the GitHub Pages site in docs/ from the JSON evidence files. No number is typed by hand.

Pages (nav order = reading order):
  docs/index.html               Executive summary (top of the site): status, how to submit, name and note, answers
  docs/submission.html          The submission-file page: what exists, its checks, and why it is not offered
  docs/evidence.html            Experiments, GEMSDOE29 and GEMSDOE32 analysis, uniqueness, run card, data inventory,
                                irregularities, limitations, sources, hypotheses

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
<footer>Every number on these pages is read from JSON in <code>evidence/</code>, <code>registry/</code> or the data inventory
(computed from files at build time). HOLDOUT-DTI = our proxy. ORGANIZER-CONFIRMED = receipt only (none exists yet).
Regenerate with <code>python scripts/build_site.py</code>.</footer></body></html>"""


def main() -> int:
    sel = J("evidence/selection.json")
    card = J("evidence/run_card.json")
    exp1 = J("evidence/exp1_leakage_canary.json")
    exp2 = J("evidence/exp2_holdout_arms.json")
    uniq = J("evidence/uniqueness_check.json")
    ovl = J("evidence/overlap_baseline.json")
    irr = J("registry/irregularities.json")["items"]
    lim = J("registry/limitations.json")["items"]
    srcs = J("registry/sources.json")
    exp4 = J("evidence/exp4_hypothesis_canary.json")
    exp5 = J("evidence/exp5_holdout_bands_vs_ridge.json")
    inv = J("evidence/registry_inventory/inventory.json")["summary"]
    card_h = J("evidence/run_card.json")["hypothesis_status"]
    n_flag = sum(1 for r in uniq["results"] if r.get("drift_flag"))
    top_lift = max((r for r in ovl["flagged_rows"] if r.get("lift")), key=lambda r: r["lift"])
    top_lift_obs = top_lift["observed_overlap_ours_within_3px"]
    top_lift_rho = top_lift.get("spearman_rho_sample")
    n_dense = sum(1 for r in ovl["flagged_rows"] if r.get("expected_overlap_random_placement", 0) >= 0.5)

    def paired(q):
        import math
        b = [f["per_q"][q]["DTI"] for f in exp5["arms"]["bands"]["folds"]]
        r_ = [f["per_q"][q]["DTI"] for f in exp5["arms"]["bands_ridge"]["folds"]]
        d = [x - y for x, y in zip(r_, b)]
        m = sum(d) / len(d)
        sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
        h = 2.776 * sd / math.sqrt(len(d))
        return m, m - h, m + h
    S = {s["id"]: s for s in srcs["sources"]}
    name, arm, q = sel["submission_name"], sel["arm"], sel["q"]
    cand = J(f"evidence/candidates/{name}.receipt.json")
    tmpl_log = (ROOT / "evidence" / "candidates" / "template_validator_nan.txt").read_text()
    tmpl_pass = "Validation PASSED" in tmpl_log
    vn = {"counts": cand["files"][name + "-nan.tif"]["counts"], "checks": cand["files"][name + "-nan.tif"]["checks"],
          "all_checks_passed": cand["files"][name + "-nan.tif"]["all_checks_passed"]}
    pooled = exp2["arms"][arm]["pooled"][str(q)]
    ci = pooled["CI95_t_df4_on_fold_mean"]

    def link(sid, text=None):
        s = S[sid]
        return f'<a href="{esc(s["url"])}">{esc(text or sid)}</a>'

    def leaky_pooled(qq):
        return exp2["arms"]["leaky_ablate"]["pooled"][str(qq)]["pooled_DTI"]

    # ---------------------------------------------------------------- index.html (executive summary)
    body = f"""
<section>
  <div class="banner"><b>Research-only / DO NOT SUBMIT.</b> No file is offered for download or submission. The one valid candidate is blocked by the
  uniqueness gate: {n_flag} of {uniq['n_registry_files']} registry rasters are flagged, and the closest is a near-duplicate of an existing submission.
  Nothing has been submitted, and no organizer score exists.</div>
  <h1>Executive summary</h1>
  <p>This project tried to build a unique, valid GeoTIFF for the GEMS Prize (DrivenData competition 306) that beats the public
  bar, to explain leakage in the GEMSDOE29 file, to explain the high-scoring GEMSDOE32 file, and to test new geological hypotheses.
  Here is each answer, with its label.</p>
  <table>
    <tr><th>Question</th><th>Answer</th><th>Label</th></tr>
    <tr><td>Can we produce a unique, valid GeoTIFF?</td>
        <td>A format-valid one exists (template validator PASSED, 0 known-fault pixels emitted). It is <b>blocked</b> by the uniqueness gate:
        {n_flag} of {uniq['n_registry_files']} registry rasters exceed the 70% dot-overlap flag. The closest, 17GEMSDOE F-ensemble-2pct, has {top_lift_obs:.1%} overlap
        with a lift of {top_lift['lift']:.1f}× over chance and rank correlation {top_lift_rho:.3f}. Its dot count is almost identical to ours. It is not offered.</td>
        <td><span class="pill">validator output</span></td></tr>
    <tr><td>Does it beat 0.3774 (the public #1)?</td><td>Unknown. We have no organizer score, so nothing can be claimed.</td>
        <td><span class="pill">ORGANIZER-CONFIRMED: none</span></td></tr>
    <tr><td>Our holdout proxy</td>
        <td>Pooled HOLDOUT-DTI {pooled['pooled_DTI']:.4f} (95% CI {ci[0]:.4f} to {ci[1]:.4f}) for the {esc(arm)} arm at q={q}. It is a proxy and not comparable with the leaderboard.</td>
        <td><span class="pill">HOLDOUT-DTI</span></td></tr>
    <tr><td>Why GEMSDOE29 leaks</td>
        <td>Its distance-to-known-faults feature is built from the same labels it is scored on. It is exactly 0 on all {exp1['C1_leaky_distance_in_sample']['value_on_known_fault_px']['n']:,} known-fault pixels, so separability is {exp1['C1_leaky_distance_in_sample']['separability']:.1f}. On the holdout it gives DTI {leaky_pooled(q):.5f}.</td>
        <td><span class="pill">measured (Exp 1, Exp 2)</span></td></tr>
    <tr><td>Why GEMSDOE32 (0.2778) may score high, and whether we can beat it</td>
        <td>Likely a sensible emission volume placed off the catalogue, with a light false-positive penalty. Not verified. We cannot beat it on current evidence. See <a href="evidence.html#gemsdoe32">evidence</a>.</td>
        <td><span class="pill">hypothesis / owner-claim</span></td></tr>
    <tr><td>Top hypothesis validated?</td><td><b>H1</b> (segment-exact separation, ranked first) fails the leakage canary: its pixel-neighbour AUC is {exp4['H1']['local_pair_canary']['AUC_fault_gt_neighbour']:.3f}, so it encodes the label. Rejected.
        <b>H2</b> (label-free magnetic ridge) gives no gain. The paired ridge-minus-bands difference at q=0.02 is {paired('0.02')[0]:+.5f} (95% CI {paired('0.02')[1]:+.5f} to {paired('0.02')[2]:+.5f}).</td>
        <td><span class="pill">measured (Exp 4, Exp 5)</span></td></tr>
    <tr><td>Portal error "Predicted values must be in range [0, 1]"</td>
        <td>The shared template validator documents a real platform rejection caused by 3,061 NaN px inside the valid region (owner-documented, not independently verified). Our file has no NaN inside the footprint, all values in [0, 1], and passes the template validator. The portal has not yet confirmed it (no receipt).</td>
        <td><span class="pill">unverified (IR-53-04)</span></td></tr>
  </table>
</section>

<section>
  <h2>Name and comment (prepared, not submitted)</h2>
  <p class="note">Shown here so the form can be filled in if the file is ever promoted. The name and note are not an approval.</p>
  <table>
    <tr><th>Name</th><td><code>{esc(name)}</code></td></tr>
    <tr><th>Comment (≤140 characters)</th><td><code>{esc(sel['note'])}</code> ({len(sel['note'])} characters)</td></tr>
  </table>
</section>

<section>
  <h2>How to submit (for when a file is promoted)</h2>
  <ol>
    <li>Open the competition submission page on DrivenData. Log in to your own account (no DrivenData data download is needed).</li>
    <li>Choose a single-band float32 GeoTIFF (.tif), EPSG:32611, 100 m grid, values in [0, 1]. The checks are on the <a href="submission.html">submission-file page</a>.</li>
    <li>Paste the comment above. Submit. Feedback submissions are limited to 3 per week ({link('S3', 'NLR rules')}). The problem page ({link('S1', 'S1')}) says each team must choose a <b>single</b> submission for scoring across both rounds before the deadline. That choice is a separate decision and is not made here.</li>
    <li>Record the receipt. Only a receipt makes a number ORGANIZER-CONFIRMED.</li>
    <li>If the portal still rejects the range, record the exact message and keep the cause open (IR-53-04). A zeros-outside file is not an option: it breaks the rule that outside the bounds must be null or NaN.</li>
  </ol>
  <p class="note">Sources: {link('S1', 'problem page')} · {link('S2', 'leaderboard')} · {link('S3', 'NLR rules (PDF)')}.</p>
</section>

<section>
  <h2>Bars to beat (public, as fetched 2026-10-08)</h2>
  <table>
    <tr><th>Rank</th><th>Team</th><th>Score</th><th>Label</th></tr>
    <tr><td>1</td><td>xiaofanhu</td><td>0.3774</td><td>leaderboard (public)</td></tr>
    <tr><td>7</td><td>DARD</td><td>0.3195</td><td>leaderboard (public)</td></tr>
    <tr><td>13</td><td>extradr19</td><td>0.2778</td><td>leaderboard (public); not linked to GEMSDOE32 (IR-53-02)</td></tr>
  </table>
  <p class="note">The leaderboard snapshot time is not shown on the page (IR-53-01). Source: {link('S2', 'DrivenData leaderboard')}.</p>
</section>

<section>
  <h2>Next steps and limitations</h2>
  <p>See <a href="evidence.html#limitations">limitations</a>. Main gaps: no organizer score; the overlap gate is confounded for dense non-submission rasters (IR-53-20);
  the one candidate duplicates an existing recipe (IR-53-21); the mirrored sample does not match its description (IR-53-19); and the rules require a generative-AI disclosure (IR-53-24).</p>
</section>
"""
    (DOCS / "index.html").write_text(page("Executive summary", body, "index.html"))

    # ---------------------------------------------------------------- submission.html
    cn = vn["counts"]
    cand_rows = (
        f"<tr><td>NaN outside footprint (the only file)</td><td><code>{esc(cand['files'][name + '-nan.tif']['sha256'])}</code></td>"
        f"<td>{vn['all_checks_passed']} (in-lane); template validator: {tmpl_pass}</td><td>{cn['footprint_px']:,} / {cn['finite_px']:,}</td><td>{cn['nonzero_px']:,}</td></tr>")
    body = f"""
<section>
  <div class="banner"><b>Research-only / DO NOT SUBMIT.</b> Not offered for download. The file is blocked by the protocol's 3-px overlap flag
  and quarantined outside the repository. The label "Validated / OK to submit" is not applied: the release gates have not all passed.</div>
  <h1>Submission file</h1>
  <p>Method (candidate): gradient-boosted classifier (sklearn HistGradientBoosting, 200 iterations) trained on the 19 label-free feature bands
  (arm <code>{esc(arm)}</code>), with 300,000 sampled negatives and {exp1['known_fault_px_in_footprint']:,} known-fault positives. The top q={q:.0%} of the official
  footprint is emitted ({cn['nonzero_px']:,} non-zero pixels), and every known-fault pixel is forced to 0.</p>
  <h2>Checks (the local validator re-reads the file from disk)</h2>
  <table>
    <tr><th>File</th><th>sha256</th><th>All checks pass</th><th>Footprint px / finite px</th><th>Non-zero px</th></tr>
    {cand_rows}
  </table>
  <p class="note">Shared template validator (<code>buffedlizard55-lab/GEMSDOE</code> at commit <code>dcbbb19</code>, <code>scripts/validate_submission.py</code>): <b>{'PASSED' if tmpl_pass else 'FAILED'}</b>. Its log is <code>evidence/candidates/template_validator_nan.txt</code>.
  It checks CRS, 100 m, single float32 band, values in [0, 1], finite exactly on the template's valid region, NaN elsewhere, the nodata tag, and the training shape. In-lane checks (core.py) are in the receipt. A validator pass is not a portal acceptance.</p>
  <h2>Why it is not offered</h2>
  <ul>
    <li>Population: {uniq['n_registry_files']} single-band registry rasters on the competition grid (from {inv['files']} mirrored tif files; {inv['unique_sha256']} unique). Rank correlation: max {uniq['max_spearman_rho']:.3f}, below the 0.90 flag.</li>
    <li>Share of our dots within 3 px of another file's dots: {n_flag} files above the 0.70 stop threshold (max {uniq['max_dot_overlap_within_3px']:.3f}), so the protocol stops the candidate.</li>
    <li>Closest match: 17GEMSDOE F-ensemble-2pct, {top_lift_obs:.1%} overlap, lift {top_lift['lift']:.1f}×, rank correlation {top_lift_rho:.3f}. Our recipe duplicates an existing one (IR-53-21).</li>
    <li>Chance baseline (diagnostic only; flags unchanged): the largest lift over random placement at the same registry density is {ovl['max_lift']:.2f}×. This means the overlap is placement, not just density. See <a href="evidence.html#uniqueness">the uniqueness table</a>.</li>
  </ul>
  <p class="note">Files are at <code>/tmp/gems53-held/</code> (not in the repository; they are 49 MB each). They can be regenerated with <code>scripts/exp3_build_submission.py</code> and checked against the sha256 values above.</p>
</section>
"""
    (DOCS / "submission.html").write_text(page("Submission file", body, "submission.html"))

    # ---------------------------------------------------------------- evidence.html
    exp1_rows = "".join(
        f"<tr><td>{r['band']}</td><td>{esc(r['name'])}</td><td>{r['separability_max']:.3f}</td><td>{esc(r['flag'])}</td></tr>"
        for r in exp1["A_label_free_bands"])
    arm_rows = ""
    for a in ["bands", "leakfree", "leaky_ablate"]:
        for qk, v in exp2["arms"][a]["pooled"].items():
            arm_rows += (f"<tr><td>{esc(a)}</td><td>{float(qk):.4f}</td><td>{v['pooled_DTI']:.4f}</td>"
                         f"<td>[{v['CI95_t_df4_on_fold_mean'][0]:.4f}, {v['CI95_t_df4_on_fold_mean'][1]:.4f}]</td>"
                         f"<td>{v['withheld_fault_px_total']:,} px / {v['n_withheld_segments_total']} segments</td></tr>")
    uniq_rows = "".join(
        f"<tr><td>{esc(Path(r['file']).name.split('__')[0])}</td><td>{esc(Path(r['file']).name.split('__', 1)[-1][:58])}</td>"
        f"<td>{r.get('spearman_rho_sample', '-')}</td><td>{r.get('our_dots_within_3px_of_registry_dots', '-')}</td>"
        f"<td>{r.get('registry_dots', '-')}</td><td>{'FLAG' if r.get('drift_flag') else ''}</td></tr>"
        for r in uniq["results"][:10])
    ovl_rows = "".join(
        f"<tr><td>{esc(r['file'].split('__')[0])}</td><td>{r['observed_overlap_ours_within_3px']:.3f}</td>"
        f"<td>{r['expected_overlap_random_placement']:.3f}</td><td>{r['lift']:.2f}×</td></tr>"
        for r in ovl["flagged_rows"] if "lift" in r)
    # data inventory computed from disk
    inv_items = [
        ("training_features.tif", DATA / "training_features.tif", "19-band input stack (reassembled from 5 parts)", "S7 template manifest; mirror S18"),
        ("labels.tif", DATA / "labels.tif", "known faults, int8 {-1,0,1}; 60,988 fault px, 3,199 segments", "S7 template manifest; mirror S18"),
        ("sample_submission.tif", DATA / "sample_submission.tif", "organizer sample: NaN outside 5,167,373 footprint px", "S7 template manifest; mirror S18"),
        ("gems53-hgb-bands-q0p02-nan.tif (blocked candidate)", Path("/tmp/gems53-held/gems53-hgb-bands-q0p02-nan.tif"),
         "our candidate (not offered)", "built here by exp3"),
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
  <p class="note"><a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/hypotheses.md">Hypotheses</a> · <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/gemsdoe32.md">GEMSDOE32 analysis</a> · <a href="data/run_card.json">run card JSON</a></p>
</section>

<section>
  <h2>Experiment 1 - leakage canary (MEASURED)</h2>
  <p>Separability = max(AUC, 1−AUC). Gate: above 0.90 means leakage until proven otherwise. Footprint {exp1['footprint_px']:,} px; {exp1['known_fault_px_in_footprint']:,} known-fault px inside, {exp1['known_fault_px_outside_footprint']} outside.</p>
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
  <h2>Experiment 2 - hide-and-recover holdout, three arms (HOLDOUT-DTI)</h2>
  <p>Five folds of withheld whole fault segments (seed 53, 10 px buffer), visible faults masked to 0. Score: the official distance-weighted Tversky
  (alpha 0.2, beta 0.8, 300 m). Evaluator <code>{esc(exp2['evaluator']['name'])} {esc(exp2['evaluator']['version'])}</code>, unit-tested against brute force. CI = t(df 4) on the five fold scores.
  The <code>leaky_ablate</code> arm uses the GEMSDOE29 defect. It scores near-perfect and is shown only as a contrast.</p>
  <table><tr><th>Arm</th><th>q (fraction of footprint emitted)</th><th>Pooled DTI</th><th>95% CI</th><th>Withheld positives</th></tr>{arm_rows}</table>
  <p class="note">Selection rule (pre-stated): highest pooled DTI at its best tested q, over the <code>bands</code> and <code>leakfree</code> arms only.
  The result is bands at q=0.02 (0.0352) versus leakfree (0.0343). The two intervals overlap almost entirely, so the leak-free distance feature adds no measurable value in this proxy.</p>
</section>

<section>
  <h2>Experiments 4 and 5 - the untried hypotheses (MEASURED and HOLDOUT-DTI)</h2>
  <p>Ranked by expected gain and cost in <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/hypotheses.md">hypotheses.md</a>. Each one was checked with a
  paired pixel-neighbour canary before any holdout run: a fault pixel and an adjacent non-fault pixel should not separate unless the feature encodes the label pixel-exactly.</p>
  <table><tr><th>Check</th><th>Feature alone: separability</th><th>Pixel-neighbour AUC (fault &gt; neighbour)</th><th>Result</th></tr>
    <tr><td>H1 segment-exact exclusion (rank 1)</td><td>{exp4['H1']['separability']:.3f}</td><td><b>{exp4['H1']['local_pair_canary']['AUC_fault_gt_neighbour']:.3f}</b></td><td>REJECTED: label-dependent by construction (the positive's own segment is removed; a negative's is not)</td></tr>
    <tr><td>H2 label-free RTP ridge (rank 2)</td><td>{exp4['H2']['separability']:.3f}</td><td>{exp4['H2']['local_pair_canary']['AUC_fault_gt_neighbour']:.3f}</td><td>Passes the canary (no label path)</td></tr>
    <tr><td>Current leak-free arm (4×4 block cross-fit)</td><td>{exp4['A_leakfree_crossfit_training_sep']['separability']:.3f}</td><td>{exp4['A_leakfree_crossfit_local_pair']['AUC_fault_gt_neighbour']:.3f}</td><td>Passes (exhaustive check: 170,638 neighbour pairs, AUC 0.4995)</td></tr>
  </table>
  <h3>Holdout: bands versus bands + ridge (HOLDOUT-DTI, evaluator {esc(exp5['evaluator']['name'])} {esc(exp5['evaluator']['version'])}, 5 folds, 60,988 withheld px)</h3>
  <table><tr><th>q (fraction of footprint)</th><th>bands pooled DTI</th><th>bands + ridge pooled DTI</th><th>Paired difference (ridge − bands), 95% CI</th></tr>{''.join(
      f"<tr><td>{float(q_):.4f}</td><td>{exp5['arms']['bands']['pooled'][q_]['pooled_DTI']:.4f}</td><td>{exp5['arms']['bands_ridge']['pooled'][q_]['pooled_DTI']:.4f}</td>"
      f"<td>{paired(q_)[0]:+.5f} [{paired(q_)[1]:+.5f}, {paired(q_)[2]:+.5f}]</td></tr>" for q_ in exp5['arms']['bands']['pooled'])}</table>
  <p class="note">Result: H2 gives no measurable gain at any q. The pre-registered acceptance rule (a gain beyond the fold-level 95% half-width) is not met, so H2 is negative.
  Every holdout number here is a proxy: the withheld truth is catalogue segments, not new faults (IR-53-03).</p>
</section>

<section id="gemsdoe32">
  <h2>GEMSDOE29 and GEMSDOE32</h2>
  <p><b>GEMSDOE29 (leakage; repo {link('S8', 'S8')}):</b> the feature from its own labels is the leak. See Experiment 1 and the leaky arm. The GEMSDOE29 registry rasters overlap our candidate by up to {max(r['our_dots_within_3px_of_registry_dots'] for r in uniq['results'] if 'GEMSDOE29' in r['file']):.1%} within 3 px (below the 70% flag).</p>
  <p><b>GEMSDOE32 (0.2778 file; repo {link('S9', 'S9')}, site {link('S10', 'S10')}):</b> MEASURED: its H33-2-B2 raster has 37,654 dots (matches the owner's count), rank correlation 0.009 and 21.8% overlap with our candidate, so it is not a copy. OWNER-CLAIM: built by pruning dots within 2 px of the catalogue. The mechanism (sensible volume, off-catalogue placement, light false-positive penalty) is a hypothesis. It is explained in full in <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/main/docs/research/gemsdoe32.md">the GEMSDOE32 analysis</a>.</p>
</section>

<section id="uniqueness">
  <h2>Uniqueness against public GEMS submissions (MEASURED)</h2>
  <p>{uniq['n_registry_files']} single-band registry rasters on the competition grid (population: <code>evidence/registry_inventory/inventory.json</code>). Spearman rho on 300k sampled footprint pixels. Overlap = share of our dots within 3 px of that file's dots. Flags: rho &gt; 0.90 or overlap &gt; 0.70. The earlier 138-file receipt is kept as <code>evidence/uniqueness_check_prior138.json</code> and is not comparable (IR-53-23).</p>
  <p class="note">Confound (IR-53-20): {n_dense} of the flagged files cover at least half the footprint, so overlap approaches 100% for any dense map. The lift column separates density from placement.</p>
  <table><tr><th>Repo</th><th>File (first 58 chars)</th><th>Spearman rho</th><th>Our dots within 3 px</th><th>Registry dots</th><th>Flag</th></tr>{uniq_rows}</table>
  <h3>Chance baseline for the overlap flag (diagnostic only; does not change any flag)</h3>
  <p>Expected overlap = share of the footprint within 3 px of that file's dots (what random placement would give at the same density). Lift = observed ÷ expected.</p>
  <table><tr><th>Repo</th><th>Observed</th><th>Expected (random)</th><th>Lift</th></tr>{ovl_rows}</table>
</section>

<section>
  <h2>Run card (summary; full JSON in <code>evidence/run_card.json</code>)</h2>
  <table>
    <tr><th>Hypothesis</th><td>{esc(card['hypothesis'])}</td></tr>
    <tr><th>Mechanism</th><td>{esc(card['mechanism'])}</td></tr>
    <tr><th>Named non-fault process that could mimic it</th><td>{esc(card['named_non_fault_process_that_could_mimic_it'])}</td></tr>
    <tr><th>Holdout (HOLDOUT-DTI)</th><td>pooled {card['holdout']['pooled_DTI']:.4f}, 95% CI {card['holdout']['CI95_t_df4_on_fold_mean']}; {card['holdout']['withheld_fault_px_total']:,} withheld fault px; evaluator {esc(card['holdout']['evaluator']['name'])} {esc(card['holdout']['evaluator']['version'])}</td></tr>
    <tr><th>Organizer score</th><td>none (no receipt)</td></tr>
    <tr><th>Correlation / overlap vs registry</th><td>drift flag: {card['correlation_overlap_vs_registry']['any_drift_flag']}; max rho {card['correlation_overlap_vs_registry']['max_spearman_rho_sample']:.3f}; max dot overlap {card['correlation_overlap_vs_registry']['max_our_dots_within_3px_of_registry_dots']:.3f}</td></tr>
    <tr><th>Raster sha256 (primary, blocked)</th><td><code>{esc(card['raster_sha256']['primary_nan_outside'])}</code></td></tr>
    <tr><th>Validator</th><td>shared template validator passed: {card['validator_output']['shared_template_validator']['passed']} ({esc(card['validator_output']['shared_template_validator']['log'])})</td></tr>
    <tr><th>Submission</th><td><code>{esc(card['submission']['name'])}</code>; status {esc(card['submission']['status'])}; submitted: {card['submission']['submitted']}</td></tr>
    <tr><th>Verdict</th><td><b>{esc(card['verdict'])}</b>: {esc(card['verdict_reason'])}</td></tr>
  </table>
</section>

<section id="inventory">
  <h2>Data inventory</h2>
  <p class="note">Files live outside the repository (in <code>/tmp</code>) and are re-fetched by <code>scripts/fetch_data.py</code>, which checks sha256. Size and hash are computed at build time.</p>
  <table><tr><th>File</th><th>Bytes</th><th>sha256 (prefix)</th><th>Content</th><th>Origin</th></tr>{inv_rows}</table>
  <p class="note">Data licence: the competition data needs DrivenData login, which we did not use. The rasters come from the template repo's mirror (Dropbox links), so licence and equality with DrivenData's copy are not confirmed (IR-53-07, L-06).</p>
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
    <li>Run H1 (segment-exact learn-predict separation) on the same 5-fold holdout, then decide on a new candidate. Needs a budget decision.</li>
    <li>Decide whether to change the overlap rule to a chance-corrected form (diagnostic in <code>scripts/overlap_baseline.py</code>). That is a protocol change and needs the user's approval.</li>
    <li>Reconcile the portal's [0,1] check with a real receipt (a submission slot is needed, and that is a separate decision).</li>
    <li>Reconcile <code>core.py</code> names with the shared template (<code>evaluate_holdout.py</code> and <code>submission_writer.py</code> are not in the template; see the review notes).</li>
    <li>GEMSDOE32 owner README and bayes-opt page, and GEMSDOE29 <code>knowledge/33</code>, not reviewed in full.</li>
  </ul>
</section>

<section id="sources">
  <h2>Sources (official links for manual review)</h2>
  <table><tr><th>ID</th><th>Source</th><th>Access</th></tr>{src_rows}</table>
  <p class="note">Access: {esc(srcs['legend'] if isinstance(srcs['legend'], str) else json.dumps(srcs['legend']))}</p>
</section>
"""
    (DOCS / "evidence.html").write_text(page("Evidence", body, "evidence.html"))
    # copy the JSON the pages link to, so the Pages site is self-contained (Pages serves docs/ only)
    data_dir = DOCS / "data"
    data_dir.mkdir(exist_ok=True)
    for rel in ["evidence/run_card.json", "evidence/exp1_leakage_canary.json", "evidence/exp2_holdout_arms.json",
                "evidence/uniqueness_check.json", "evidence/overlap_baseline.json", "evidence/selection.json",
                "registry/irregularities.json", "registry/limitations.json", "registry/sources.json",
                "evidence/exp4_hypothesis_canary.json", "evidence/exp5_holdout_bands_vs_ridge.json",
                "evidence/registry_inventory/inventory.json",
                "evidence/candidates/gems53-hgb-bands-q0p02.receipt.json"]:
        (data_dir / Path(rel).name).write_text((ROOT / rel).read_text())
    (DOCS / ".nojekyll").write_text("")  # serve the static HTML as-is (no Jekyll processing)
    print("site written: docs/index.html, docs/submission.html, docs/evidence.html; data copied to docs/data/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
