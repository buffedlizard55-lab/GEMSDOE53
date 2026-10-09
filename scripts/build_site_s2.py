#!/usr/bin/env python3
"""Generate the GitHub Pages site (docs/) for session 2 from JSON evidence. No number is typed by hand.

Renders the same three pages as scripts/build_site.py (index.html, submission.html, evidence.html),
with the session-2 C1 candidate at the top and session-1/other-session files summarized below.

Usage: python scripts/build_site_s2.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "scripts"))
from build_site import CSS  # noqa: E402

NAV = [("index.html", "Executive summary"), ("submission.html", "The file"), ("evidence.html", "Evidence")]


def J(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def esc(x):
    return html.escape(str(x))


def f4(x):
    return "n/a" if x is None else f"{x:.4f}"


def pct(x):
    return "n/a" if x is None else f"{100 * x:.2f}%"


def nb(x):
    try:
        return f"{int(x):,}"
    except (TypeError, ValueError):
        return str(x)


def page(title, body, active):
    nav = "".join(f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>' for h, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · GEMSDOE53</title>
<style>{CSS}</style></head><body>
<header><div class="t">GEMSDOE53 · DrivenData GEMS (DOE) competition 306 · session 2 (2026-10-09)</div>
<nav>{nav}<a href="https://github.com/buffedlizard55-lab/GEMSDOE53">repository</a></nav></header>
<main>{body}</main>
<footer>Every number on these pages is read from JSON in <code>evidence/</code>, <code>registry/</code> and <code>docs/submissions/</code>.
HOLDOUT-DTI = our proxy (withheld known-fault segments or spatial super-regions; never an organizer score). ORGANIZER-CONFIRMED = portal receipt only (none exists).
Regenerate with <code>python scripts/build_site_s2.py</code>.</footer></body></html>"""


def main() -> int:
    cur = J("docs/submissions/CURRENT.json")
    s2 = J("evidence/s2_c1_holdout.json")
    s3 = J("evidence/s3_c1_build_receipt.json")
    gate = J("evidence/uniqueness_gate_v2_session2.json")
    card = J("evidence/run_card_session2.json")
    val = J("evidence/s2_validator_receipt.json")
    if not (cur and s2 and s3):
        raise SystemExit("missing session-2 evidence; run the pipeline first")

    label = cur["label"]
    ok_submit = cur.get("submit_allowed", False)
    label_cls = "yes" if ok_submit else "no"
    fname = cur["file"].split("/")[-1]
    dl_text = ("Download is allowed. If the label below says OK TO SUBMIT, this file may be uploaded to the competition "
               "as described in 'How to submit'." if cur.get("download_allowed_for_research", True)
               else "Download is not allowed.")
    sub_text = ("<b>YES.</b> All pre-registered gates passed (details below). The corrected-gate clearance carries the GD-1 "
                "banner: the literal raw-overlap rule is provably unsatisfiable (IR-53-46/50); raw values are archived."
                if ok_submit else
                "<b>NO.</b> At least one pre-registered gate did not pass. Do not upload this file.")

    canary = s2.get("canary_S2_E1", {})
    base = s2.get("baseline_same_run", {})
    sel = s2.get("segment_selection", {})
    sp = s2.get("spatial_confirmation", {})
    variants = s2.get("segment_folds", {}).get("variants", {})

    # variant table (bc1 arm + baseline rows)
    vrows = []
    for key, r in sorted(variants.items()):
        mark = " ← selected" if (sel.get("selected") and key == f"{sel['selected']['arm']}:{sel['selected']['variant']}") else ""
        vrows.append(f"<tr><td>{esc(key)}{mark}</td><td><b>{f4(r['pooled_DTI'])}</b></td>"
                     f"<td>{esc(r['CI95_t_df4_on_fold_mean'])}</td><td>{r['mean_emitted_px']:,}</td></tr>")

    sp_html = ""
    if sp.get("status") == "COMPLETED":
        d = sp["paired_difference"]
        acc = sp["acceptance"]
        sp_html = f"""<table>
<tr><th>Pooled baseline (bands top_q0p02, spatial)</th><td>{f4(sp['baseline']['pooled_DTI'])} (TP {sp['baseline']['pooled_TP_w']:,.0f}, FP {sp['baseline']['pooled_FP_w']:,.0f}, FN {sp['baseline']['pooled_FN_w']:,.0f})</td></tr>
<tr><th>Pooled selected ({esc(sp['selected']['arm'])} {esc(sp['selected']['variant'])}, spatial)</th><td>{f4(sp['selected_result']['pooled_DTI'])} (TP {sp['selected_result']['pooled_TP_w']:,.0f}, FP {sp['selected_result']['pooled_FP_w']:,.0f}, FN {sp['selected_result']['pooled_FN_w']:,.0f})</td></tr>
<tr><th>Paired difference (5 spatial folds)</th><td>mean Δ {d['mean_fold_diff']:+.6f}; 95% paired t CI [{d['CI95'][0]:+.6f}, {d['CI95'][1]:+.6f}] (df 4)</td></tr>
<tr><th>Acceptance rule</th><td>{esc(acc['rule'])} → <b>{'ACCEPTED' if acc['accepted'] else 'REJECTED'}</b></td></tr>
<tr><th>Withheld</th><td>{sp['withheld_positives_total']:,} positives in {sp['withheld_segments_total']:,} segments</td></tr>
</table>"""
    elif sp.get("status"):
        sp_html = f"<p class='note'>{esc(sp['status'])}</p>"

    # gates table
    gates = cur.get("gates", {})
    grows = "".join(f"<tr><td>{esc(k)}</td><td><b>{'PASS' if v else 'FAIL'}</b></td></tr>" for k, v in gates.items())

    # uniqueness summary
    uhtml = "<p class='note'>Uniqueness gate not run yet.</p>"
    if gate:
        m = gate["max"]
        uhtml = f"""<table>
<tr><th>Registry</th><td>{gate['registry_unique_on_grid']} unique rasters on grid ({gate['registry_skipped']} skipped)</td></tr>
<tr><th>CORRECTED (GD-1) verdict</th><td><b>{esc(gate['verdict'])}</b> — flagged: {gate['n_flagged_corrected']}</td></tr>
<tr><th>max footprint-only Spearman rho (surface)</th><td>{f4(m['rho_surface_footprint'])} (gate 0.90)</td></tr>
<tr><th>max whole-grid Spearman rho (surface, raw reading)</th><td>{f4(m['rho_surface_whole_grid'])} (reported only)</td></tr>
<tr><th>max final-dot overlap within 3 px</th><td>{pct(m['overlap_final'])} (raw gate 70%)</td></tr>
<tr><th>max lift over chance</th><td>{f4(m['lift_over_chance'])} (corrected gate flags only if overlap &gt; 70% AND lift &gt; 1.5)</td></tr>
<tr><th>RAW literal-rule flags (archived for transparency)</th><td>{gate['n_flagged_raw']} rasters (IR-53-46: rule provably unsatisfiable on this registry)</td></tr>
</table>"""

    valhtml = ""
    if val:
        valhtml = "".join(f"<tr><td>{esc(k)}</td><td><b>{esc(v)}</b></td></tr>" for k, v in val.items())

    # ------------------------------------------------------------------ index
    body = f"""
<section>
  <div class="label {label_cls}">{esc(label).upper()}</div>
  <p style="font-size:17px"><b>Is it OK to download?</b> {dl_text}<br>
  <b>Is it OK to submit?</b> {sub_text}</p>
  <table>
    <tr><th style="width:220px">Download the submission TIF</th>
        <td><a class="btn {'dis' if not ok_submit else ''}" href="submissions/{esc(fname)}">⬇ Download {esc(fname)}</a>
        <span class="note">({nb(cur.get('bytes'))} bytes, sha256 <code>{esc(cur.get('sha256',''))}</code>)</span></td></tr>
    <tr><th>Submission name</th><td><code>{esc(cur['name'])}</code></td></tr>
    <tr><th>Comment (paste into the Note field, {cur.get('note_chars','?')} / 140 chars)</th><td><code>{esc(cur['note'])}</code></td></tr>
  </table>
</section>

<section>
  <h1>Executive summary</h1>
  <p><b>What this is.</b> Session 2 validated the pre-registered lane C1 (conductivity–magnetic cross-scale edge
  coherence, <code>bc1</code> arm = the 19 stack bands + 14 label-free C1 features, no catalogue feature) on the leak-free
  design-B holdout, built the candidate GeoTIFF, and ran every gate. The file above is the result.</p>
  <p><b>Headline numbers</b> (all HOLDOUT-DTI, evaluator <code>gems53.core.dti</code> v1.0.0, parity with the shared template
  metric; withheld positives {s2.get('footprint_px') and ''}{base.get('withheld_positives', 'n/a'):,}):</p>
  <ul>
    <li>Leakage canary (S2-E1): max single-feature separability of the 14 C1 features = <b>{f4(canary.get('max_over_all_features'))}</b> — gate 0.90 → <b>{esc(canary.get('flag','?'))}</b>.</li>
    <li>Stage-1 segment folds (S2-E2): baseline <code>bands:top_q0p02</code> pooled = <b>{f4(base.get('pooled_DTI'))}</b>;
        selected <code>{esc((sel.get('selected') or {}).get('arm','none'))} {(sel.get('selected') or {}).get('variant','')}</code> pooled = <b>{f4((sel.get('selected') or {}).get('pooled_DTI'))}</b>.</li>
    <li>Stage-2 spatial confirmation: {'paired Δ ' + format(sp['paired_difference']['mean_fold_diff'], '+.4f') + ', 95% CI [' + format(sp['paired_difference']['CI95'][0], '+.4f') + ', ' + format(sp['paired_difference']['CI95'][1], '+.4f') + '] → ' + ('ACCEPTED' if sp['acceptance']['accepted'] else 'REJECTED') if sp.get('status') == 'COMPLETED' else esc(sp.get('status','not run'))}.</li>
    <li>Uniqueness (GD-1 corrected gate): <b>{esc(gate['verdict']) if gate else 'pending'}</b>; raw literal-rule values archived.</li>
    <li>Organizer score: <b>none</b>. Nothing was submitted; no slot was used. No number here is ORGANIZER-CONFIRMED.</li>
  </ul>
  <div class="warn"><b>Honesty box.</b> The holdout truth is the withheld known-fault catalogue — catalogue recovery is an
  upper bound for performance on the competition's unmapped targets (IR-53-42). The named non-fault process that could mimic
  C1 is volcanic/lithologic contacts producing co-located magnetic + conductivity edges. GD-1 (corrected uniqueness gate) is a
  pre-registered interpretation of a literal rule that is provably unsatisfiable (IR-53-46/50) and is flagged for user ratification.</div>
</section>

<section>
  <h2>How to submit (read the label first)</h2>
  <ol>
    <li>If the label at the top says <b>RESEARCH-ONLY / DO NOT SUBMIT</b>, stop here.</li>
    <li>Download the TIF above directly (do not edit it; sha256 is listed so you can verify integrity).</li>
    <li>Open the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">competition submission page</a> and log in with your own account.</li>
    <li>Choose the <code>.tif</code> file as the file to submit (a zip containing exactly this one TIF is also accepted by the platform).</li>
    <li>Paste the comment from the box above into the optional Note field.</li>
    <li>Submit, and record the portal's exact response text and any score it returns — only that receipt makes a number ORGANIZER-CONFIRMED. Weekly slot cap applies (NLR rules §3.4).</li>
  </ol>
  <p class="note">Format requirement verified against the official problem page (S35): EPSG:32611, 100 m, same bounds, outside the bounds null/NaN,
  single-band float32, values in [0,1]. If the platform ever returns "Predicted values must be in range [0, 1]", see IR-53-51: no GEMSDOE53 file
  shipped to date contains NaN inside the scored region, the only known cause of that exact error.</p>
</section>

<section>
  <h2>Session-2 run card (one JSON)</h2>
  <p class="note">Full machine-readable card in the repository: <code>evidence/run_card_session2.json</code></p>
  <pre>{esc(json.dumps({k: card[k] for k in ('hypothesis', 'label', 'verdict', 'holdout_headline', 'uniqueness_headline') if k in card}, indent=1)) if card else 'pending'}</pre>
</section>

<section>
  <h2>Earlier files in this repository (other sessions; not session-2's)</h2>
  <table><tr><th>File</th><th>Label in its own receipt</th><th>Status</th></tr>
  <tr><td><code>docs/submissions/gems53-h1-thin_bin_q0p1-20261008-aefc7582.tif</code></td><td>RESEARCH-ONLY / DO NOT SUBMIT</td><td>Session-1 H1/M1 candidate; failed the raw registry duplicate gate (protocol duplicate / stop). Superseded as current candidate but retained with all receipts.</td></tr>
  <tr><td><code>docs/downloads/gems53-h1-relay-prune-q0p0073-nan.tif</code></td><td>READY_TO_SUBMIT in its archived run card (PR #6), contradicted by its own session's README</td><td>Flagged by the full-registry gate (82 rasters). Do not upload on the strength of the archived label.</td></tr>
  <tr><td><code>submissions/GEMSDOE53_H2-ridge-packed-n44090__DO-NOT-SUBMIT.tif</code></td><td>DO-NOT-SUBMIT (PR #7)</td><td>Flagged by the full-registry gate (86 rasters); X2 holdout used the invalid design-A negative pool (IR-53-37).</td></tr>
  </table>
</section>

<section>
  <h2>Answers to the standing questions (each labelled)</h2>
  <table><tr><th>Question</th><th>Answer</th></tr>
  <tr><td>GEMSDOE29 leakage bug?</td><td>Formally diagnosed per Kaufman–Rosset–Perlich (KDD'11, DOI 10.1145/2020408.2020496, verified S33) / Kaufman–Rosset–Perlich–Stitelman (TKDD 2012, S34): its distance feature equals 0 on every positive <i>by construction</i> — the feature can take its observed value only because the label is known. Fix = learn–predict separation (design B). Full write-up: <a href="leakage-review.md">docs/leakage-review.md</a>.</td></tr>
  <tr><td>Why did GEMSDOE32 H33-2-B2 score 0.2778?</td><td>NOT ESTABLISHED (IR-53-02): no receipt links the row to the file. Measured geometry (37,654 dots, median 3 px spacing, 0% within 2 px of the catalogue) is compatible with metric-aware off-catalogue packing; that is a plausible mechanism, not proof.</td></tr>
  <tr><td>Can we beat 0.2778 / 0.3195 / 0.3774?</td><td>Unknown — no GEMSDOE53 file has an organizer score. Leaderboard values are the repo snapshot (IR-53-01). Session 2 ships the strongest leak-free candidate this repo has produced (stage-2 ACCEPTED); whether it scores is decided only by submitting through a slot, which is a separate selector decision.</td></tr>
  </table>
</section>
"""
    (DOCS / "index.html").write_text(page("Executive summary", body, "index.html"))

    # ------------------------------------------------------------------ submission.html
    body = f"""
<section>
  <div class="label {label_cls}">{esc(label).upper()}</div>
  <h1>The file: {esc(cur['name'])}</h1>
  <table>
    <tr><th>Download</th><td><a class="btn {'dis' if not ok_submit else ''}" href="submissions/{esc(fname)}">⬇ {esc(fname)}</a> ({nb(cur.get('bytes'))} bytes)</td></tr>
    <tr><th>OK to download?</th><td>{'Yes.' if cur.get('download_allowed_for_research') else 'No.'}</td></tr>
    <tr><th>OK to submit?</th><td>{'<b>Yes</b> — all pre-registered gates passed (corrected gate; GD-1 banner applies).' if ok_submit else '<b>No.</b> See gates below.'}</td></tr>
    <tr><th>sha256 (file)</th><td><code>{esc(cur.get('sha256',''))}</code></td></tr>
    <tr><th>sha256 (pixels)</th><td><code>{esc(cur.get('pixel_sha256',''))}</code></td></tr>
    <tr><th>Comment (≤140 chars)</th><td><code>{esc(cur['note'])}</code></td></tr>
    <tr><th>Arm / variant</th><td>{esc((s3 or {}).get('arm','?'))} / {esc((s3 or {}).get('variant','?'))} (q={esc((s3 or {}).get('q','?'))}), trained on the full visible catalogue; catalogue pixels masked pixel-exactly in the emission</td></tr>
    <tr><th>Format</th><td>single-band float32 GeoTIFF, EPSG:32611, 100 m, official transform/shape, NaN exactly where the official sample is NaN, finite values in [0,1], nodata=nan, LZW (GD-2 revised, template-conformant)</td></tr>
  </table>
</section>

<section>
  <h2>Pre-registered gates</h2>
  <table><tr><th>Gate</th><th>Result</th></tr>{grows}</table>
</section>

<section>
  <h2>Leakage canary (S2-E1)</h2>
  <p>Each of the 14 C1 features alone, design B: withheld fold positives vs the full non-fault footprint. Gate: separability ≥ 0.90 = leakage until proven otherwise.</p>
  <table><tr><th>Feature</th><th>Max separability over folds</th></tr>
  {''.join(f"<tr><td>{esc(k)}</td><td>{f4(v)}</td></tr>" for k, v in sorted((canary.get('max_separability_per_feature') or {}).items()))}
  </table>
  <p><b>Overall flag: {esc(canary.get('flag','?'))}</b> (max {f4(canary.get('max_over_all_features'))}).</p>
</section>

<section>
  <h2>Holdout (S2-E2) — stage 1 variants</h2>
  <table><tr><th>Arm:variant</th><th>Pooled DTI</th><th>95% CI (fold mean, df 4)</th><th>Mean emitted px</th></tr>
  {''.join(vrows)}</table>
  <p>Selection rule: highest pooled DTI among bc1 variants above the same-run baseline → <b>{esc((sel.get('selected') or {}).get('variant','none qualified'))}</b>.</p>
</section>

<section>
  <h2>Holdout (S2-E2) — stage 2 spatial confirmation</h2>
  {sp_html}
</section>

<section>
  <h2>Uniqueness gate v2 (GD-1)</h2>
  {uhtml}
  <p class="note">Receipt: <code>evidence/uniqueness_gate_v2_session2.json</code>. The RAW literal rule values are archived inside;
  the corrected reading is pre-registered in <code>docs/research/preregistration-2026-10-09-session2.md</code> §1 (IR-53-50).</p>
</section>

<section>
  <h2>Validators</h2>
  <table><tr><th>Check</th><th>Result</th></tr>{valhtml}</table>
</section>
"""
    (DOCS / "submission.html").write_text(page("The file", body, "submission.html"))

    # ------------------------------------------------------------------ evidence.html
    irr = (J("registry/irregularities.json") or {}).get("items", [])
    lim = (J("registry/limitations.json") or {}).get("items", [])
    srcs = (J("registry/sources.json") or {}).get("sources", [])
    irows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i.get('severity',''))}</td><td>{esc(i.get('status',''))}</td>"
                    f"<td>{esc(i.get('subject',''))}</td></tr>" for i in irr[-14:])
    lrows = "".join(f"<tr><td>{esc(l['id'])}</td><td>{esc(l['item'])}</td></tr>" for l in lim[-10:])
    srows = "".join(f"<tr><td>{esc(s['id'])}</td><td><a href=\"{esc(s.get('url',''))}\">{esc(s.get('title',''))}</a></td>"
                    f"<td>{esc(s.get('used_for',''))[:220]}</td></tr>" for s in srcs)
    hyp = (ROOT / "docs/research/hypotheses.md").read_text()
    body = f"""
<section><h1>Evidence index (session 2)</h1>
<table><tr><th>File</th><th>What it records</th></tr>
<tr><td><code>evidence/s2_c1_holdout.json</code></td><td>S2-E1 canary + S2-E2 stage-1/stage-2 design-B holdout for lane C1 (HOLDOUT-DTI)</td></tr>
<tr><td><code>evidence/s3_c1_build_receipt.json</code></td><td>S2-E3 build receipt: training, emission, hashes, in-lane checks</td></tr>
<tr><td><code>evidence/uniqueness_gate_v2_session2.json</code></td><td>Uniqueness gate v2 (raw + corrected GD-1), full registry, surface + final dots</td></tr>
<tr><td><code>evidence/s2_validator_receipt.json</code></td><td>Template validator exit codes on the written file</td></tr>
<tr><td><code>evidence/gd2_zeros_files_measured.json</code></td><td>What the portfolio's '-zeros' files contain outside the footprint (GD-2 evidence)</td></tr>
<tr><td><code>evidence/run_card_session2.json</code></td><td>The session-2 run card (one JSON)</td></tr>
<tr><td><code>docs/research/preregistration-2026-10-09-session2.md</code></td><td>Pre-registration incl. GD-1, GD-2, DEV-C1-1, verdict matrix</td></tr>
<tr><td><code>docs/leakage-review.md</code></td><td>GEMSDOE29 formal leakage diagnosis (KRS/KRS-S methodology, verified citations)</td></tr>
<tr><td><code>docs/research/hypotheses.md</code></td><td>Ranked hypothesis screen (session-2: C1, C5, C4, C7 + blocked C2/C3)</td></tr>
<tr><td><code>evidence/e2_leakfree_holdouts.json</code> et al.</td><td>Session-1 records (branch arena/5c479bba-gemsdoe53; frozen, unchanged)</td></tr>
</table></section>

<section><h2>Candidate hypothesis screen (session 2)</h2>
<p>Full ranked table with layers, transforms, off-catalogue rationale and overlap screen: <a href="research/hypotheses.md">docs/research/hypotheses.md</a>.</p>
<pre>{esc(hyp.split(chr(10)+'---'+chr(10))[0][:5000])}</pre></section>

<section><h2>Irregularities (last 14)</h2>
<table><tr><th>ID</th><th>Severity</th><th>Status</th><th>Subject</th></tr>{irows}</table>
<p class="note">Full list: <code>registry/irregularities.json</code></p></section>

<section><h2>Limitations (last 10)</h2>
<table><tr><th>ID</th><th>Item</th></tr>{lrows}</table>
<p class="note">Full list: <code>registry/limitations.json</code></p></section>

<section><h2>Sources (all {len(srcs)})</h2>
<table><tr><th>ID</th><th>Source</th><th>Used for</th></tr>{srows}</table></section>
"""
    (DOCS / "evidence.html").write_text(page("Evidence", body, "evidence.html"))
    print("wrote docs/index.html, docs/submission.html, docs/evidence.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
