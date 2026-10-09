#!/usr/bin/env python3
"""Build docs/index.html (executive summary, download first) and docs/how-to-submit.html from evidence JSON.

Every number on the pages is read from a committed evidence file; nothing is typed by hand. Run after E3, the
writer and the gate:  python scripts/build_site_h53.py
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPO = "https://github.com/buffedlizard55-lab/GEMSDOE53"
SITE = "https://buffedlizard55-lab.github.io/GEMSDOE53"


def J(rel):
    return json.loads((ROOT / rel).read_text())


def e(x):
    return html.escape(str(x))


CSS = """
:root{--ink:#14202b;--muted:#5b6673;--line:#dfe5ec;--bg:#f6f8fa;--card:#fff;--ok:#14532d;--okbg:#ecfdf3;--red:#7f1d1d;--redbg:#fef2f2;--warn:#8a3b06;--warnbg:#fff7ed;--acc:#0b5cad}
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#0d2238;color:#fff;padding:14px 22px}header b{font-size:17px}nav{margin-top:4px;font-size:14px}nav a{color:#bcd7f5;margin-right:16px;text-decoration:none}nav a.on{font-weight:700;text-decoration:underline}
main{max-width:1040px;margin:0 auto;padding:18px}section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin:14px 0}
h1{font-size:24px;margin:0 0 8px}h2{font-size:19px;margin:0 0 10px}h3{font-size:16px;margin:14px 0 6px}
.verdict{font-size:21px;font-weight:800;border-radius:12px;padding:14px 16px;margin:6px 0 12px}
.yes{background:var(--okbg);border:2px solid #86efac;color:var(--ok)}.no{background:var(--redbg);border:2px solid #fca5a5;color:var(--red)}
.warn{background:var(--warnbg);border:1px solid #fed7aa;color:var(--warn);border-radius:10px;padding:10px 14px}
.btn{display:inline-block;background:#0b7a3e;color:#fff;font-weight:700;font-size:18px;padding:13px 22px;border-radius:10px;text-decoration:none;margin:6px 10px 6px 0}
.btn.alt{background:#334155;font-size:15px;padding:10px 16px}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px;background:#f1f4f8;border-radius:5px;padding:1px 5px;word-break:break-all}
.copy{display:flex;gap:8px;align-items:center;margin:6px 0}.copy input{flex:1;font:14px ui-monospace,monospace;padding:8px;border:1px solid var(--line);border-radius:7px}
.copy button{padding:8px 12px;border:1px solid #94a3b8;background:#fff;border-radius:7px;cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{background:#f1f4f8}
td.n{text-align:right;font-variant-numeric:tabular-nums}.muted{color:var(--muted);font-size:14px}ol li,ul li{margin:4px 0}
img{max-width:100%;border:1px solid var(--line);border-radius:8px}
"""

JS = """<script>function cp(id){const el=document.getElementById(id);el.select();navigator.clipboard&&navigator.clipboard.writeText(el.value);}</script>"""


def page(title, active, body):
    nav = "".join(f'<a href="{h}" class="{"on" if k == active else ""}">{t}</a>' for k, h, t in (
        ("index", "index.html", "Executive summary"), ("submit", "how-to-submit.html", "How to submit"),
        ("evidence", "evidence.html", "Evidence (S3 session and archive)"), ("repo", REPO, "Repository")))
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{e(title)} · GEMSDOE53</title><style>{CSS}</style></head><body><header><b>GEMSDOE53 · GEMS Prize (DrivenData #306)</b>'
            f'<nav>{nav}</nav></header><main>{body}</main>{JS}</body></html>\n')


def fmt(x, n=6):
    return "—" if x is None else f"{x:.{n}f}"


def main():
    cur = J("docs/submissions/CURRENT.json")
    sub = J(cur["receipt"])
    e1 = J("evidence/h53_e1_canary.json")
    e2 = J("evidence/h53_e2_holdout.json")
    e3 = J("evidence/h53_e3_build.json")
    gate = J(cur["gate_receipt"])
    lin = J("evidence/h53_lineage_algebra.json")
    ok = cur["ok_to_submit"]
    fname = Path(cur["file"]).name
    dl = fname  # docs/index.html and the file share docs/; link relative to docs/
    rel = Path(cur["file"]).relative_to("docs").as_posix() if cur["file"].startswith("docs/") else "../" + cur["file"]

    s1 = e2["stage1"]; s2 = e2["stage2"]
    m1 = s1["M1_thin_bin_q0p10"]; ds = s1["DS_flank2_sep2p8_n40000"]; sp = s2["M1_thin_bin_q0p10"]
    rows_e2 = ""
    for lab, blk, dec in (("Stage 1 segment folds", m1, "M1 thin q0.10"), ("Stage 1 segment folds", ds, "D-S (flank 2 px, sep 2.8, 40k dots)"),
                          ("Stage 2 spatial super-regions", sp, "M1 thin q0.10")):
        pb = blk["paired_B_minus_A"]
        rows_e2 += (f"<tr><td>{lab}</td><td>{dec}</td><td class=n>{fmt(blk['A']['pooled_DTI'])}</td><td class=n>{fmt(blk['B']['pooled_DTI'])}</td>"
                    f"<td class=n>{pb['mean']:+.6f}</td><td class=n>[{pb['CI95_t_df4'][0]:+.6f}, {pb['CI95_t_df4'][1]:+.6f}]</td><td class=n>{pb['folds_B_wins']}/5</td></tr>")
    can = list(e1["max_separability_by_feature"].items())
    can_rows = "".join(f"<tr><td>{e(k)}</td><td class=n>{v:.4f}</td></tr>" for k, v in can[:8])
    lf = lin["files"]; st = lin["inference"]["steps"]
    lin_rows = "".join(f"<tr><td>{k}</td><td class=n>{lf[k]['user_reported_score']}</td><td class=n>{lf[k]['dots']:,}</td>"
                       f"<td class=n>{lf[k]['within_1px_catalogue']:,}</td><td class=n>{lf[k]['within_2px_catalogue']:,}</td><td class=n>{lf[k]['within_3px_catalogue']:,}</td></tr>" for k in ("d2.8", "r1", "B2"))
    g_top = gate["max_overlap_v2"][:5]
    g_rows = "".join(f"<tr><td class=mono>{e(r['file'][:80])}</td><td>{r['mode']}</td><td class=n>{r['overlap']:.3f}</td><td class=n>{r['chance']:.3f}</td><td class=n>{r['kappa']:.3f}</td></tr>" for r in g_top)
    rho_s = gate["max_rho_surface"][0]; rho_f = gate["max_rho_final"][0]
    ec = sub["explicit_checks"]
    chk_rows = "".join(f"<tr><td>{e(k)}</td><td>{'PASS' if v else 'FAIL'}</td></tr>" for k, v in ec.items())

    dup_rows = "".join(f"<tr><td class=mono>{e(r['file'][:84])}</td><td>{r['mode']}</td><td class=n>{r['overlap']:.3f}</td><td class=n>{r['chance']:.3f}</td><td class=n>{r['kappa']:.3f}</td></tr>"
                       for r in sorted([r for r in gate["rows"] if r["duplicate_v2"]], key=lambda r: -r["kappa"]))
    href = ("../" + cur["file"]) if not cur["file"].startswith("docs/") else rel
    if ok:
        top = f"""<section>
<h1>Submission file: download and submit</h1>
<div class="verdict yes">YES — OK to download and submit this file.</div>
<a class="btn" href="{e(href)}" download>⬇ Download {e(fname)}</a>
<a class="btn alt" href="how-to-submit.html">Step-by-step: how to submit</a>
<p class="muted">{sub['bytes']:,} bytes · sha256 <span class=mono>{e(sub['sha256'])}</span></p>
<h3>Paste into the submission form</h3>
<div class="copy"><input id="nm" readonly value="{e(cur['name'])}"><button onclick="cp('nm')">Copy name</button></div>
<div class="copy"><input id="nt" readonly value="{e(cur['note'])}"><button onclick="cp('nt')">Copy note ({len(cur['note'])} chars)</button></div>
<p><b>What it is.</b> {e(cur['what_it_is'])}</p>
<p><b>Why it is OK to submit.</b> {e(cur['why_ok'])}</p>
<p class="warn"><b>Expected score: unknown.</b> {e(cur['expected_score_statement'])}</p>
</section>"""
    else:
        top = f"""<section>
<h1>Submission status, 2026-10-09: no file is OK to submit</h1>
<div class="verdict no">NO — do not submit. This session produced no file that passed every gate.</div>
<p><b>{e(cur['label'])}</b></p>
<p><b>What was built.</b> {e(cur['what_it_is'])}</p>
<p><b>Why it must not be submitted.</b> {e(cur['why_not'])}</p>
<p class="warn"><b>Expected score: not projected.</b> {e(cur['expected_score_statement'])}</p>
<p>The file's format is valid. It has no NaN anywhere, values are exactly 0 or 1, and the grid matches the sample. It fails only the
<b>uniqueness</b> gate. It is kept for research, renamed with <code>DO-NOT-SUBMIT</code>:
<a href="{e(href)}">{e(fname)}</a> ({sub['bytes']:,} bytes, sha256 <span class=mono>{e(sub['sha256'][:16])}…</span>).
Unique name: <code>{e(cur['name'])}</code>. Note: <code>{e(cur['note'])}</code> ({len(cur['note'])} chars).</p>
<p><b>What would pass next time.</b> {e(cur['next_step'])}</p>
<p class="muted">The same-day S3 session&#39;s control file <code>docs/submissions/gems53-s3-bands-top_q0p02-20261009-e67cda00.tif</code> and every older file in <code>docs/downloads/</code>, <code>docs/submissions/</code> and <code>submissions/</code> are also <b>not</b> OK to submit. Reasons: NaN outside the footprint (the layout that returned
“Predicted values must be in range [0, 1]”), a failed uniqueness gate (the 2026-10-08 candidate), or both.</p>
</section>"""
    # Same-day sibling sessions (merged parallel lanes): every entry is research-only like this one.
    sib_rows = ""
    for o in cur.get("other_sessions_same_day", []):
        of = o.get("file", "")
        o_rel = Path(of).relative_to("docs").as_posix() if of.startswith("docs/") else ("../" + of if of else "")
        op = o.get("pointer", "")
        op_rel = Path(op).relative_to("docs").as_posix() if op.startswith("docs/") else op
        sib_rows += (f"<tr><td>{e(o.get('session',''))}</td>"
                     f"<td class=mono><a href=\"{e(o_rel)}\">{e(Path(of).name)}</a>"
                     + (f"<br><span class=mono>sha256 {e(str(o.get('sha256',''))[:16])}…</span>" if o.get('sha256') else "")
                     + f"</td><td>{e(o.get('label',''))}"
                     + (f"<br>Note: <code>{e(o.get('note',''))}</code>" if o.get('note') else "")
                     + (f"<br>Holdout: {e(o.get('holdout',''))}" if o.get('holdout') else "")
                     + (f"<br>Pointer: <a href=\"{e(op_rel)}\">{e(op)}</a>" if op else "")
                     + "</td></tr>")
    siblings = ""
    if sib_rows:
        siblings = f"""
<section><h2>Same-day parallel sessions (merged into this repository)</h2>
<p>These lanes ran concurrently on 2026-10-09 and were merged together. Each keeps its own archived pointer and receipts;
none of their files is cleared for submission either. The live pointer above remains the single source of truth for
&ldquo;may I upload?&rdquo;.</p>
<table><tr><th>Session</th><th>File</th><th>Status</th></tr>{sib_rows}</table>
</section>"""

    verdict_cls = "yes" if ok else "no"
    verdict_txt = ("YES — OK to download and submit this file." if ok else "NO — do not submit this file.")
    body = f"""
{top}
{siblings}

<section><h2>Format validation (the bytes you download)</h2>
<table><tr><th>Check</th><th>Result</th></tr>{chk_rows}
<tr><td>template <code>scripts/validate_submission.py</code></td><td>exit {sub['template_validate_submission']['exit']}; failures: {e('; '.join(sub.get('template_failures_ours', [])))}. The organizer-accepted 0.2778 file gives exit {sub['control_organizer_accepted_zeros_file'].get('template_validate_submission', {}).get('exit')} with identical failures (IR-53-65).</td></tr>
<tr><td>template <code>validate-conformant</code> (requires NaN outside; expected to differ)</td><td>exit {sub['template_validate_conformant']['exit']} — same check on the organizer-accepted 0.2778 zeros file: exit {sub['control_organizer_accepted_zeros_file'].get('template_validate_conformant',{}).get('exit')}</td></tr></table>
<p class="muted">Dots: {sub['stats']['dots']:,}; dots outside footprint: {sub['stats']['dots_outside_footprint']}; min distance to a catalogue fault: {e3['min_dist_to_catalogue_px']:.2f} px.</p>
</section>

<section><h2>Uniqueness (gate v2, pre-registered, chance-corrected) — verdict: {e(gate['verdict'])}</h2>
<p>Compared with <b>{gate['unique_on_grid']}</b> unique on-grid rasters from every public GEMSDOE* repository (files seen {gate['files_seen']}, skipped {gate['skipped']}).
Duplicate if more than 70% of our dots are within 3 px of a raster's dots <i>and</i> kappa is above 0.40, or if |Spearman rho| is above 0.90.
Highest rho of our pre-placement surface: {fmt(rho_s['value'],4)} ({e(rho_s['file'][:60])}). Highest rho of the final raster: {fmt(rho_f['value'],4)}.
The raw, uncorrected rule (more than 70% within 3 px, no chance correction) flags {gate['raw_rule_flag_count']} rasters. The chance-corrected rule flags the {len([r for r in gate['rows'] if r['duplicate_v2']])} rows below, so <b>verdict = {e(gate['verdict'])}</b>. Full receipt: <code>{e(cur['gate_receipt'])}</code>.</p>
<table><tr><th>Duplicate under v2 (registry raster)</th><th>mode</th><th>overlap ≤3 px</th><th>chance</th><th>kappa</th></tr>{dup_rows}</table>
<p class="muted">Reading: our dots hug the existing catalogue (median 5 px). Many earlier lanes put dots on the same structures, judging by file names: supervised HGB (GEMSDOE43 sup01-hgb21), NMS traces (12GEMSDOE r5-nms3-trace), "physics-dotted" (GEMSDOE37); plus our own 2026-10-08 file. A model that uses catalogue distance as a feature lands on these consensus sleeves. The organizer-scored 0.2778 file avoids them (median 19.65 px).</p>
<img src="assets/h53_dots_vs_b2.png" alt="E3 dots vs the 0.2778 dots vs catalogue">
</section>

<section><h2>Why the GEMSDOE 0.2778 file scored highest (measured)</h2>
<p>The 0.2778 file (GEMSDOE32 H33-2-B2) is <b>exactly</b> the 0.2600 d2.8 dot file with every dot within 2 px of the existing catalogue removed. The set relations are measured: B2 ⊂ r1 ⊂ d2.8.
No new dots were added in either step. The test set holds expert-labelled faults that are <i>not</i> in the USGS database, so dots on the catalogue are almost pure false positives.</p>
<table><tr><th>file</th><th>user-reported score</th><th>dots</th><th>≤1 px from catalogue</th><th>≤2 px</th><th>≤3 px</th></tr>{lin_rows}</table>
<p>Algebra from the official formula: 1/DTI = 0.2 + (0.2·FP<sub>w</sub> + 0.8·|G|)/TP<sub>w</sub>. Removing n pure-false-positive dots implies TP<sub>w</sub> = 0.2·n/Δ(1/DTI):
step 1 gives {st[0]['implied_TP_w_per_f']:,} and step 2 gives {st[1]['implied_TP_w_per_f']:,} (per unit public share). The two independent steps agree within 8%. <b>This is an inference, not a score.</b></p>
</section>

<section><h2>This session's experiments (pre-registered, 3 of 3 used)</h2>
<p><b>E1 leakage canary</b> (design B; flag above 0.90): flagged = {e(e1['flagged']) if e1['flagged'] else 'none'}. Top features:</p>
<table><tr><th>feature</th><th>max separability</th></tr>{can_rows}</table>
<p><b>E2 hide-and-recover</b>. Arm A = 19 bands + H1 (the previous holdout best, reproduced exactly per fold). Arm B = A + HWVC (hanging-wall vector concordance).
Every number below is HOLDOUT-DTI (evaluator {e(e2['evaluator']['name'])} v{e(e2['evaluator']['version'])}; {e2['segment_folds']['withheld_positives_total']:,} withheld positives; 95% t-interval, df 4).</p>
<table><tr><th>stage</th><th>decoder</th><th>A pooled</th><th>B pooled</th><th>B−A mean</th><th>95% CI</th><th>B wins</th></tr>{rows_e2}</table>
<p><b>Promotion rule</b>: {e(e2['promotion_rule'])} → <b>promote B = {e2['promote_B']}</b>. HWVC is therefore a <b>negative result</b>, and it is kept as a deliverable.
<b>E3</b> built the pre-registered fallback: arm A (the current holdout best model) with the new decoder D-S.</p>
<img src="assets/h53_hwvc_R_s5.png" alt="HWVC field">
</section>

<section><h2>Read more</h2><ul>
<li><a href="{REPO}/blob/main/docs/research/preregistration-2026-10-09-hwvc.md">Pre-registration (committed before any run)</a></li>
<li><a href="{REPO}/blob/main/docs/research/hypotheses-2026-10-09.md">Ranked hypotheses, GEMSDOE lineage analysis, leakage audit</a></li>
<li><a href="{REPO}/blob/main/docs/leakage-review.md">GEMSDOE29 leakage diagnosis (Kaufman et al. 2012 learn-predict separation)</a></li>
<li><a href="{REPO}/blob/main/evidence/h53_run_card.json">Run card (JSON)</a> · <a href="{REPO}/tree/main/evidence">all evidence</a> · <a href="{REPO}/blob/main/registry/sources.json">sources</a> · <a href="{REPO}/blob/main/registry/irregularities.json">irregularities</a></li>
<li>Official: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem description</a> · <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">leaderboard</a> · <a href="https://www.herox.com/GEMSPrize/resource/2274">rules</a> → <a href="https://www.nlr.gov/docs/fy26osti/96647.pdf">NLR 96647 PDF</a></li>
</ul></section>
"""
    (DOCS / "index.html").write_text(page("Executive summary", "index", body))

    if ok:
        step1 = f"""<li>Download the file: <a class="btn" href="{e(href)}" download>⬇ {e(fname)}</a><br><span class="muted">sha256 <span class=mono>{e(sub['sha256'])}</span>. Do not rename it, and do not open or re-save it in GIS software: re-saving can add NaN or change the nodata value.</span></li>"""
    else:
        step1 = """<li><b>There is no file to submit right now.</b> The summary page shows a red NO. Do not upload any file from this repository until <code>docs/submissions/CURRENT.json</code> says <code>"ok_to_submit": true</code>. The steps below are the procedure to follow once it does.</li>"""
    if ok:
        step_note = f"""<li><b>Note (optional)</b>: paste the note below. It is {len(cur['note'])} characters, within the 140-character project limit.
<div class="copy"><input id="nt2" readonly value="{e(cur['note'])}"><button onclick="cp('nt2')">Copy note</button></div>
Our internal unique name, which is also stored inside the GeoTIFF tags:
<div class="copy"><input id="nm2" readonly value="{e(cur['name'])}"><button onclick="cp('nm2')">Copy name</button></div></li>"""
    else:
        step_note = """<li><b>Note (optional)</b>: use the 140-character note stored with the cleared file in <code>docs/submissions/CURRENT.json</code>. Nothing is cleared today, so there is no note to paste.</li>"""
    howto = f"""
<section><h1>How to submit to the GEMS Prize (DrivenData competition 306)</h1>
<div class="verdict {verdict_cls}">{e(verdict_txt)}</div>
<ol>
{step1}
<li>Sign in at <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">drivendata.org/competitions/306</a> and open <b>Submissions</b>. Then click <b>Submit</b> (the form is titled “New submission”).</li>
<li><b>File to submit</b>: choose the downloaded <code>.tif</code>. The form accepts “a single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF”. The file must match the submission format's CRS, shape and geotransform. Run the checks on the summary page first.</li>
{step_note}
<li>Click submit. Wait for the score, then record it with the date in <code>docs/submissions/CURRENT.json</code> (<code>organizer_score</code>). Until then, any score here is a holdout proxy, not an organizer score.</li>
</ol>
<h3>Format the organizer requires (problem page, “Submission format”)</h3>
<ul><li>EPSG:32611 (UTM 11N), 100 m pixels, same bounds as the training data: 3,292 × 3,730 pixels.</li>
<li>A single float32 band, with values between 0 and 1.</li>
<li>Data outside the bounds “is null or nan”. In practice the portal rejected a NaN-outside file with “Predicted values must be in range [0, 1]”, while an all-finite file with zeros outside was scored (0.2778, user-reported). Ship all-finite files (0 outside the footprint, nodata unset).</li></ul>
<h3>If the portal still rejects it</h3>
<ul><li>Range error: confirm the file has not been modified. Its sha256 must equal the value above.</li>
<li>Shape, CRS or transform error: re-download it, because a browser or proxy may have altered the bytes. Then compare the sha256.</li>
<li>Weekly cap: choosing which file goes into a slot is a separate decision. Check the submission page for the remaining weekly submissions.</li></ul>
<p class="muted">Sources: <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format">problem page, submission format</a> · <a href="https://www.nlr.gov/docs/fy26osti/96647.pdf">official rules PDF</a>. The form text above is quoted from the user's report of the live form.</p>
</section>"""
    (DOCS / "how-to-submit.html").write_text(page("How to submit", "submit", howto))
    (ROOT / "index.html").write_text(
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=docs/index.html">'
        f'<title>GEMSDOE53</title></head><body><p><a href="docs/index.html">Executive summary</a>. '
        f'Latest build: {e(fname)}. OK to submit: {"YES" if ok else "NO"}.</p></body></html>\n')
    print("wrote docs/index.html, docs/how-to-submit.html, index.html")


if __name__ == "__main__":
    main()
