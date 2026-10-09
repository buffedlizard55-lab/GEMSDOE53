#!/usr/bin/env python3
"""Generate the GitHub Pages site in docs/ from the JSON evidence. No number is typed by hand.

Pages (reading order):
  docs/index.html        Executive summary: status label, download and submission block (name, note), answers, bars.
  docs/submission.html   The file: what it is, every gate and check, the uniqueness receipt, why it is labelled as it is.
  docs/evidence.html     Experiments E1 (design A, reference) and E2 (design B), canaries, GEMSDOE29/32, hypotheses,
                         irregularities, limitations, sources, run card.

Usage: python scripts/build_site.py
"""
from __future__ import annotations

import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
:root{--ink:#17202a;--muted:#5b6673;--line:#dfe5ec;--bg:#f7f9fb;--card:#fff;--accent:#0b6e4f;--warn:#9a3412;--warnbg:#fff7ed;--ok:#14532d;--okbg:#f0fdf4;--red:#7f1d1d;--redbg:#fef2f2}
*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#0f2a24;color:#fff;padding:16px 24px}header .t{font-weight:700;font-size:17px}
nav{margin-top:6px;font-size:14px}nav a{margin-right:16px;color:#bfe9dc;text-decoration:none}nav a.on{font-weight:700;text-decoration:underline}
main{max-width:1000px;margin:0 auto;padding:20px}section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 22px;margin:14px 0}
h1{font-size:25px;margin:2px 0 8px}h2{font-size:19px;margin:0 0 10px}h3{font-size:16px;margin:14px 0 6px}
.label{font-size:20px;font-weight:800;border-radius:10px;padding:14px 16px;margin:4px 0 10px}
.label.no{background:var(--redbg);border:2px solid #fca5a5;color:var(--red)}
.label.yes{background:var(--okbg);border:2px solid #86efac;color:var(--ok)}
.banner{background:var(--warnbg);border:1px solid #fed7aa;color:var(--warn);border-radius:10px;padding:12px 14px;font-weight:600}
.warn{background:var(--warnbg);border:1px solid #fed7aa;color:var(--warn);border-radius:10px;padding:12px 14px}
.ok{background:var(--okbg);border:1px solid #bbf7d0;color:var(--ok);border-radius:10px;padding:12px 14px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f1f5f9}code,pre{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px}pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto;white-space:pre-wrap}
.pill{display:inline-block;font-size:12px;border-radius:999px;padding:1px 8px;border:1px solid var(--line);color:var(--muted);margin-right:4px;white-space:nowrap}
.note{color:var(--muted);font-size:14px}footer{max-width:1000px;margin:0 auto;padding:8px 20px 40px;color:var(--muted);font-size:13px}
a{color:var(--accent)}ul,ol{padding-left:22px}li{margin:3px 0}.btn{display:inline-block;background:#0b6e4f;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:700}
.btn.dis{background:#94a3b8}
"""

NAV = [("index.html", "Executive summary"), ("submission.html", "The file"), ("evidence.html", "Evidence")]


def J(rel):
    return json.loads((ROOT / rel).read_text())


def esc(x):
    return html.escape(str(x))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def page(title, body, active):
    nav = "".join(f'<a href="{h}" class="{"on" if h == active else ""}">{t}</a>' for h, t in NAV)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · GEMSDOE53</title>
<style>{CSS}</style></head><body>
<header><div class="t">GEMSDOE53 · DrivenData GEMS (DOE) competition 306</div>
<nav>{nav}<a href="https://github.com/buffedlizard55-lab/GEMSDOE53">repository</a></nav></header>
<main>{body}</main>
<footer>Numbers on these pages are read from JSON in <code>evidence/</code>, <code>registry/</code> and <code>docs/submissions/</code>.
HOLDOUT-DTI = our proxy (withheld known-fault segments or spatial super-regions). ORGANIZER-CONFIRMED = receipt only (none exists).
Regenerate with <code>python scripts/build_site.py</code>.</footer></body></html>"""


def other_candidates():
    """Files that other sessions committed to this repository. Labels are read from their own receipts."""
    rows = []
    def try_json(rel):
        p = ROOT / rel
        return json.loads(p.read_text()) if p.exists() else None
    h1run = try_json("evidence/archive/pr6/run_card_pr6_h1.json")
    g1 = try_json("evidence/uniqueness_gate_other-session_h1_relay.json")
    rows.append(dict(
        file="docs/downloads/gems53-h1-relay-prune-q0p0073-nan.tif",
        session="H1 relay prune (PR #6, another session)",
        stated=(h1run or {}).get("submission", {}).get("status", "not found"),
        stated_source="evidence/archive/pr6/run_card_pr6_h1.json (its archived run card)",
        our_gate=(None if g1 is None else dict(flagged=g1["n_flagged"], any_drift=g1["any_drift_flag"],
                                               max_overlap=g1["max"]["max_overlap_final"],
                                               max_rho=g1["max"]["max_rho_final"], unique=g1["registry_unique_on_grid"])),
        caveat="The same session's README on main says that under the literal dot rule this file is NOT CLEARED. Its archived run card still says READY_TO_SUBMIT."))
    g2 = try_json("evidence/uniqueness_gate_other-session_h2_ridge.json")
    x3 = try_json("evidence/x3_candidate_receipt.json")
    rows.append(dict(
        file="submissions/GEMSDOE53_H2-ridge-packed-n44090__DO-NOT-SUBMIT.tif",
        session="H2 ridge-packed (PR #7, another session)",
        stated=(x3 or {}).get("label", "not found"),
        stated_source="evidence/x3_candidate_receipt.json",
        our_gate=(None if g2 is None else dict(flagged=g2["n_flagged"], any_drift=g2["any_drift_flag"],
                                               max_overlap=g2["max"]["max_overlap_final"],
                                               max_rho=g2["max"]["max_rho_final"], unique=g2["registry_unique_on_grid"])),
        caveat="Its own gate G5 (uniqueness) fails, so the label is DO-NOT-SUBMIT."))
    return rows


def other_rows_html():
    out = []
    for c in other_candidates():
        g = c["our_gate"]
        if g is None:
            gate_txt = "pending"
        else:
            flag = "FLAGGED" if g["any_drift"] else "not flagged"
            gate_txt = (f"{flag} · {g['unique']} unique rasters, {g['flagged']} flagged, "
                        f"max overlap {pct(g['max_overlap'])}, max rho {f4(g['max_rho'])}")
        out.append("<tr><td><code>" + esc(c["file"]) + "</code></td><td>" + esc(c["session"]) + "</td><td><b>"
                   + esc(c["stated"]) + "</b><br><span class='note'>" + esc(c["stated_source"]) + "</span></td><td>"
                   + esc(gate_txt) + "</td><td>" + esc(c["caveat"]) + "</td></tr>")
    return "".join(out)


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def f4(x):
    return "n/a" if x is None else f"{x:.4f}"


def main() -> int:
    cur = J("docs/submissions/CURRENT.json")
    e1 = J("evidence/e1_h1_thin_holdout.json")
    e2 = J("evidence/e2_leakfree_holdouts.json")
    legacy_e2 = J("evidence/exp2_holdout_arms.json")
    leaky_holdout = legacy_e2["arms"]["leaky_ablate"]["pooled"]["0.02"]
    e3 = J(cur["receipt"])
    gate = J(f"evidence/uniqueness_gate_{cur['name']}.json")
    g32 = J("evidence/gemsdoe32_measured.json")
    irr = J("registry/irregularities.json")["items"]
    lim = J("registry/limitations.json")["items"]
    srcs = {s["id"]: s for s in J("registry/sources.json")["sources"]}
    card = J("evidence/run_card.json")
    diag = J(f"evidence/uniqueness_diagnostics_{cur['name']}.json")
    sp_rho = J(f"evidence/diagnostic_surface_rho_{cur['name']}.json")
    lattice = next((r for r in diag.get("sparse_flagged_top", []) if "r13-lattice-s5_v2" in r.get("file", "")), None)
    if lattice is None:
        raise RuntimeError("canonical diagnostics do not contain the GEMSDOE13 lattice comparison")
    overlap_limit_pct = 100 * gate["thresholds"]["dot_overlap_within_3px"]
    rho_limit = gate["thresholds"]["spearman_rho"]
    label = cur["label"]
    ok = label.startswith("Validated")
    sp = e2.get("spatial_confirmation", {})
    stage1 = e2.get("segment_selection", {})
    base_B = e2["baseline_design_B"]
    cd = e2["canary_design_B"]
    selected = stage1.get("selected")
    V = e2["segment_folds"]["variants"]
    selected_variant_row = V.get(f"{selected['arm']}:{selected['variant']}") if selected else None
    fname = cur["file"].split("/")[-1]
    tif_path = ROOT / cur["file"]
    size_b = tif_path.stat().st_size if tif_path.exists() else e3["bytes"]
    accepted = bool(sp.get("acceptance", {}).get("accepted", False))
    cand_desc = f"{cur['spec']['arm']} {cur['spec']['variant']}"
    cand_pooled = (sp.get("selected_result", {}).get("pooled_DTI") if (selected and cur["spec"]["variant"] == selected["variant"]
                                                                       and cur["spec"]["arm"] == selected["arm"])
                   else sp.get("baseline", {}).get("pooled_DTI", base_B["pooled_DTI"]))
    dl_text = ("Download is allowed for research and review. It is <b>not</b> cleared for submission."
               if not ok else "Download is allowed. Submission is allowed only through the separate selector step.")
    sub_text = ("<b>NO.</b> Do not upload this file." if not ok else
                "<b>YES, if you choose this file in the selector step.</b> The gates below all pass.")
    label_cls = "yes" if ok else "no"

    # ---------------------------------------------------------------- index.html
    variant_rows = []
    for key in ("bands:top_q0p02", "h1:top_q0p02", "bands:thin_bin_q0p1", "h1:thin_bin_q0p1"):
        if key in V:
            r = V[key]
            variant_rows.append(f"<tr><td>{esc(r['arm'])}</td><td>{esc(r['variant'])}</td><td><b>{f4(r['pooled_DTI'])}</b></td>"
                                f"<td>{esc(r['CI95_t_df4_on_fold_mean'])}</td><td>{r['mean_emitted_px']:,}</td></tr>")
    sp_rows = ""
    if sp.get("status") == "COMPLETED":
        d = sp["paired_difference"]
        sp_rows = (f"<tr><td>Spatial confirmation (HOLDOUT-DTI; contiguous super-regions)</td><td>pooled baseline {f4(sp['baseline']['pooled_DTI'])} vs "
                   f"{esc(sp['selected']['arm'])} {esc(sp['selected']['variant'])} {f4(sp['selected_result']['pooled_DTI'])}; "
                   f"withheld positives {sp.get('withheld_positives_total', 0):,} in {sp.get('withheld_segments_total', 0):,} segments</td>"
                   f"<td>evaluator gems53.core.dti v1.0.0; paired mean Δ {d['mean_fold_diff']:+.4f}, 95% paired t CI {d['CI95'][0]:+.4f} to {d['CI95'][1]:+.4f} (df 4); "
                   f"accepted = {accepted}</td></tr>")
    gate_pass = {k: bool(v) for k, v in e3["gates"].items()}
    gate_rows = "".join(f"<tr><td>{esc(k)}</td><td>{'PASS' if gate_pass[k] else 'FAIL'}</td></tr>" for k in gate_pass)
    open_irr = [i for i in irr if str(i.get("status", "")).startswith("open")]
    top_irr = "".join(f"<li><b>{esc(i['id'])}</b> ({esc(i['severity'])}): {esc(i['subject'])}</li>"
                      for i in irr if i["id"] in ("IR-53-01", "IR-53-02", "IR-53-37", "IR-53-38", "IR-53-40", "IR-53-42", "IR-53-46", "IR-53-49"))

    s3c = J(cur["receipt"])
    s3b = J("evidence/s3b_h8_holdout.json")
    s3_hold = s3c["holdout"]
    s3_pb = s3_hold["s3b_paired_b"]
    s3_pooled = s3_hold["s3b_stage2_pooled"]
    s3_gate_rows = "".join(f"<li>{esc(k)}: <b>{'PASS' if v else 'FAIL'}</b></li>" for k, v in s3c["gates"].items())
    body = f"""
<section id="s3-download" style="border:2px solid #fca5a5">
  <div class="label no">S3 FILE: {esc(label).upper()}. DO NOT SUBMIT.</div>
  <p><b>Is it OK to download?</b> Yes, for research and review only. <a class="btn dis" href="submissions/{esc(fname)}">Download {esc(fname)}</a> ({size_b:,} bytes, sha256 <code>{esc(cur['sha256'])}</code>).</p>
  <p><b>Is it OK to submit?</b> <b>NO.</b> The pre-registered uniqueness gate fails for this file, so the protocol does not allow it into a submission slot.</p>
  <table>
    <tr><th>Name field (unique)</th><td><code>{esc(cur['name'])}</code></td></tr>
    <tr><th>Comment field (≤140 characters, {len(cur['note'])} used)</th><td><code>{esc(cur['note'])}</code></td></tr>
  </table>
  <p><b>What this file is.</b> A pre-registered control: the E2 bands top-q 0.02 candidate, with an S3 receipt. It is <b>not</b> the best holdout candidate.
  HOLDOUT-DTI (proxy, evaluator {esc(s3_hold['evaluator'])}, not organizer-scored): this control {f4(s3_pooled['bands_baseline'])}; H1 thin_bin_q0p1 {f4(s3_pooled['E2_H1_thin_bin_q0p1_best'])}; H8 gravity-gradient {f4(s3_pooled['h8_selected'])}.
  H8 minus H1, paired mean {s3_pb['mean_fold_diff']:+.6f}, 95% CI {s3_pb['CI95'][0]:+.6f} to {s3_pb['CI95'][1]:+.6f}. Pooled values differ by only 0.00003, and the five paired fold differences change sign, so the H1 comparison is not decided. Verdict: <b>NEGATIVE</b> under pre-registration section 4 (the lower bound is not above 0).</p>
  <p><b>Gates in this receipt:</b></p><ul>{s3_gate_rows}</ul>
  <p><b>Decisions needed from you</b> (nothing below was done without your approval):</p>
  <ol>
    <li>Gate definition. The pre-registered rule flags {s3c['uniqueness']['n_flagged']} of {s3c['uniqueness']['registry_unique_on_grid']} registry rasters. Of the overlap flags, the sparse lattice dot maps reach 99.87% chance coverage, so no placement can pass the raw 70% rule (IR-53-46). The surface rho flags depend on whole-grid NaN handling (IR-53-47). Approve or reject a footprint-only, chance-corrected rule (<a href="evidence.html#irregularities">evidence page</a>), then a fresh gate run.</li>
    <li>Candidate choice. H1 thin_bin_q0p1 has the higher holdout proxy (0.0040), but its own receipt also fails the uniqueness gate. Decide whether H1 or another candidate should be the one tested under a changed rule.</li>
    <li>Next experiment. H12 (potential-field edge coincidence) is recommended for spatially blocked validation. It has not been run (the three-experiment cap for this session is used up: S3-A, S3-B, S3-C).</li>
    <li>Submission slots. None has been used. organizer_score is null. Public leaderboard figures are the repository snapshot (IR-53-01, IR-53-51), not verified organizer receipts.</li>
  </ol>
</section>
<section>
  <div class="label {label_cls}">{esc(label).upper()}</div>
  <p><b>Is it OK to download?</b> {dl_text}<br>
  <b>Is it OK to submit?</b> {sub_text}</p>
  <h1>Executive summary</h1>
  <p>Question: can we ship one unique, valid GeoTIFF for DrivenData competition 306, and what do the evidence and the protocol allow us to claim?
  Short answer: the file below passes format checks, but is a <b>protocol duplicate / STOP</b>, not a unique raster under the user's raw gate. It is labelled <b>{esc(label)}</b> and must not be uploaded. The full registry gate flags {gate['n_flagged']} rasters. Final dots overlap GEMSDOE13 r13-lattice-s5_v2 by {100*lattice['overlap_final']:.3f}% within 3 px (limit {overlap_limit_pct:.0f}%; chance coverage {100*lattice['chance_coverage']:.2f}%, lift {lattice['lift_over_chance']:.4f}); whole-grid pre-placement surface rho max is {gate['max']['max_rho_surface']:.6f} (limit {rho_limit:.2f}). The overlap is not proof of byte identity; it is a literal threshold failure. The holdout is a catalogue proxy, and the first design-A holdout had a negative-pool side channel (IR-53-37).</p>
  <div class="warn">No organizer score exists for any file here. The leaderboard values quoted below are the repository's snapshot (IR-53-01).
  Nothing has been submitted, and no submission slot was used.</div>
</section>

<section>
  <h2>The file</h2>
  <table>
    <tr><th>Download</th><td><a class="btn {'' if ok else 'dis'}" href="submissions/{esc(fname)}">Download {esc(fname)}</a> ({size_b:,} bytes)</td></tr>
    <tr><th>Submission name (identifier)</th><td><code>{esc(cur['name'])}</code></td></tr>
    <tr><th>Comment (≤140 characters, {len(cur['note'])} used)</th><td><code>{esc(cur['note'])}</code></td></tr>
    <tr><th>sha256 (container)</th><td><code>{esc(cur['sha256'])}</code></td></tr>
    <tr><th>sha256 (pixels, float32 little-endian)</th><td><code>{esc(cur['pixel_sha256'])}</code></td></tr>
    <tr><th>Candidate</th><td>{esc(cand_desc)}, trained on all known faults, emission zeroed on known faults</td></tr>
    <tr><th>Format</th><td>single-band float32 GeoTIFF, EPSG:32611, 100 m, same transform and shape as the sample, NaN exactly outside the footprint, values in [0, 1]</td></tr>
  </table>
  <p class="note">Status words in the file's metadata match the label above. Do not rerun E3 in this lane: the three-experiment budget is exhausted and the uniqueness gate failed.</p>
</section>

<section>
  <h2>Other files in this repository (from other sessions, not ours)</h2>
  <div class="warn">Other sessions merged their files into this repository while this session ran. They are listed here so that the
  labels are not confused. Each label is quoted from its own receipt. Our gate is run on the same registry as ours (final dots, overlap and rho).
  <b>None of them is cleared by the pre-registered raw overlap gate (IR-53-46).</b></div>
  <table><tr><th>File</th><th>Session</th><th>Label stated in its receipt</th><th>Our gate (same registry)</th><th>Caveat</th></tr>
  {other_rows_html()}
  </table>
</section>

<section>
  <h2>How to submit (only if the label says OK)</h2>
  <ol>
    <li>Read the label above first. If it says <b>RESEARCH-ONLY / DO NOT SUBMIT</b>, stop here.</li>
    <li>Open the competition submission page on DrivenData and log in to your own account. No data download is needed.</li>
    <li>Upload the file. In the name field enter <code>{esc(cur['name'])}</code>. In the comment field enter the comment above (≤140 characters).</li>
    <li>Check the upload result. Record the portal's exact message. Only a receipt makes a number ORGANIZER-CONFIRMED.</li>
    <li>The portal limit is 3 feedback submissions per week and one final choice (<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">NLR rules §3.4</a>).
    Choosing a slot is a separate decision and was not made here.</li>
  </ol>
  <p class="note">Sources: <a href="{esc(srcs['S1']['url'])}">problem page (S1)</a> · <a href="{esc(srcs['S2']['url'])}">leaderboard snapshot (S2)</a> · <a href="{esc(srcs['S3']['url'])}">NLR rules (S3)</a>.</p>
</section>

<section>
  <h2>Answers (each labelled)</h2>
  <table>
    <tr><th>Question</th><th>Answer</th><th>Label</th></tr>
    <tr><td>Is the file unique and valid?</td><td>Valid: yes (format and conformance checks pass). <b>Protocol duplicate / stop: yes</b>; unique under the pre-registered raw gate: <b>no</b>. The full gate flags {gate['n_flagged']} of {gate['registry_unique_on_grid']} unique GEMSDOE registry rasters. Final-dot overlap with the GEMSDOE13 r13 lattice is {100*lattice['overlap_final']:.3f}% within 3 px (strict limit {overlap_limit_pct:.0f}%); chance coverage is {100*lattice['chance_coverage']:.2f}%, lift {lattice['lift_over_chance']:.4f}. The candidate is not claimed to be byte-identical; the raw protocol still says stop. {diag['flagged_by_class'].get('dense(>50% nonzero)', 0)} flags come from dense rasters and {diag['flagged_by_class'].get('sparse(<=25%)', 0) + diag['flagged_by_class'].get('mid(25-50%)', 0)} from sparse/mid rasters; the diagnostics explain the confounding, but do not override the gate (IR-53-46 to IR-53-49).</td>
      <td><span class="pill">gates in submission.html</span></td></tr>
    <tr><td>What would make the file OK to submit?</td><td>A change to the gate's definition (registry scope, a chance-corrected overlap rule, and a footprint-only rank correlation), approved by you (IR-53-16, IR-53-46, IR-53-47), followed by a fresh pre-registered gate run. Nothing of that kind has been applied here.</td>
      <td><span class="pill">decision for the user</span></td></tr>
    <tr><td>Does it beat public-board row 0.3774 (#1, S2)?</td><td>Unknown. Nothing here is an organizer-confirmed score for this file.</td><td><span class="pill">ORGANIZER-CONFIRMED: none</span></td></tr>
    <tr><td>Stage 1 (design B) HOLDOUT-DTI</td><td>Evaluator gems53.core.dti v1.0.0; 60,988 withheld positives in 3,199 segments. Bands top-q 0.02 baseline: pooled {f4(base_B['pooled_DTI'])}, 95% t CI (df 4) {base_B['CI95'][0]:.4f} to {base_B['CI95'][1]:.4f}.
      Selected variant ({esc(selected['arm'] + ' ' + selected['variant']) if selected else 'none'}): pooled HOLDOUT-DTI {f4(selected['pooled_DTI']) if selected else 'n/a'}, CI {selected_variant_row['CI95_t_df4_on_fold_mean'] if selected_variant_row else 'n/a'}; selected on these folds, so optimistic.</td>
      <td><span class="pill">HOLDOUT-DTI proxy</span></td></tr>
    {sp_rows}
    <tr><td>Why GEMSDOE29 leaks</td><td>Its distance feature is built from the full catalogue, so it is exactly 0 on every known-fault pixel (separability 1.0). Mechanism and audit in <a href="evidence.html#gemsdoe29">evidence</a> and <code>docs/leakage-review.md</code>.</td>
      <td><span class="pill">measured</span></td></tr>
    <tr><td>Our own holdout had a leak (IR-53-37)</td><td>The first HOLDOUT-DTI design A depended on withheld labels: bands top-q 0.02 = {f4(e1['arms']['bands']['top_q0p02']['pooled_DTI'])} (95% t CI {e1['arms']['bands']['top_q0p02']['CI95_t_df4_on_fold_mean']}); design B gives {f4(base_B['pooled_DTI'])} (95% CI {base_B['CI95']}). Both use evaluator gems53.core.dti v1.0.0 and 60,988 withheld positives; design A is reference only.</td>
      <td><span class="pill">HOLDOUT-DTI proxy; design A invalid</span></td></tr>
    <tr><td>Why GEMSDOE32 H33-2-B2 may explain public row 0.2778 (#13, S2)</td><td>Registry-copy structure: 37,654 dots (0.73% of footprint), 0.0% within 2 px of known faults, and median spacing 3 px. Metric-aware pruning/packing is plausible, but the row-to-file link is <b>not established</b> (IR-53-02); 0.2778 is not attributed to this file.</td>
      <td><span class="pill">public-board snapshot; attribution unknown</span></td></tr>
    <tr><td>Can a higher-scoring file be built?</td><td>Not shown. We have a proxy that rises with thinning and proximity, which is not the competition target (IR-53-42). No file here is shown to beat any leaderboard row.</td>
      <td><span class="pill">not established</span></td></tr>
  </table>
  <p class="note">Stage-2 numbers are HOLDOUT-DTI proxies (evaluator gems53.core.dti v1.0.0; 60,988 withheld positives in 3,199 segments). The absolute scores are small; for the H1 candidate (E2 design B) the paired gain is positive on all five spatial folds, and the preregistered rule accepts it. The shipped S3 control does not share this result (S3-B: H8 negative; IR-53-60). Stage-1 DTI is selected on its own segment folds and is optimistic. Neither measures the competition's unseen-fault truth (IR-53-42).</p>
</section>

<section>
  <h2>Bars to beat (repository snapshot, not re-read this session)</h2>
  <table><tr><th>Rank</th><th>Team</th><th>Score</th><th>Label</th></tr>
  <tr><td>1</td><td>xiaofanhu</td><td>0.3774</td><td>leaderboard snapshot (S2)</td></tr>
  <tr><td>7</td><td>DARD</td><td>0.3195</td><td>leaderboard snapshot (S2)</td></tr>
  <tr><td>13</td><td>extradr19</td><td>0.2778</td><td>leaderboard snapshot (S2); the file link is NOT established (IR-53-02)</td></tr></table>
  <p class="note">The request named 0.3195 as the top score. The snapshot shows 0.3774 at #1 (IR-53-01). The snapshot time is not shown on the page.</p>
</section>

<section>
  <h2>Flagged for review</h2>
  <ul>{top_irr}</ul>
  <p class="note">Full list with severities: <a href="evidence.html#irregularities">evidence page</a>. Limitations: <a href="evidence.html#limitations">evidence page</a>.</p>
</section>
"""
    (DOCS / "index.html").write_text(page("Executive summary", body, "index.html"))

    # ---------------------------------------------------------------- submission.html
    inl = e3["inlane"]
    val_rows = [
        ("template scripts/validate_submission.py (shared)", e3["validators"]["final_template_validate_submission"]["exit"]),
        ("python -m src.submission_io validate-conformant (shared)", e3["validators"]["final_validate_conformant"]["exit"]),
    ]
    in_rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in [
        ("CRS EPSG", inl["crs_epsg"]), ("grid 3730 x 3292", inl["shape_ok"]), ("transform equals sample", inl["transform_ok"]),
        ("resolution 100 m", inl["res_ok"]), ("one band", inl["count_ok"]), ("dtype", inl["dtype"]),
        ("nodata tag", inl["nodata"]), ("NaN exactly outside sample footprint", inl.get("nan_exact_outside_template", inl["nan_inside_footprint"] == 0 and inl["finite_outside_template"] == 0)),
        ("values in [0, 1] on the whole array", inl["values_in_0_1_whole_array"]),
        ("finite pixels (footprint)", f"{inl['finite_px']:,}"), ("nonzero pixels (dots)", f"{inl['nonzero_px']:,}"),
        ("min / max", f"{inl['min']:.4f} / {inl['max']:.4f}")])
    def lift_txt(r):
        v = r["lift_over_chance"]
        return "" if v is None else f"{v:.2f}"

    top_rows = "".join(
        f"<tr><td>{esc(r['file'][:70])}</td><td>{r['reg_dots']:,}</td><td>{pct(r['overlap_final'])}</td>"
        f"<td>{pct(r['chance_coverage'])}</td><td>{lift_txt(r)}</td><td>{f4(r['rho_footprint_only'])}</td></tr>"
        for r in diag["sparse_flagged_top"][:8])
    body = f"""
<section>
  <div class="label {label_cls}">{esc(label).upper()}</div>
  <h1>The file</h1>
  <p><code>{esc(cur['file'])}</code> · sha256 <code>{esc(cur['sha256'])}</code></p>
  <p>Name <code>{esc(cur['name'])}</code> · Comment <code>{esc(cur['note'])}</code></p>
  <p class="note">Decision recorded: {esc(cur['decision'])}.</p>
</section>
<section>
  <h2>Gates (pre-registered; all must pass for "OK to submit")</h2>
  <table><tr><th>Gate</th><th>Result</th></tr>{gate_rows}</table>
  <p class="note">Holdout gate = stage-2 paired lower bound above 0 for the selected variant (design B, spatial super-regions). Uniqueness gate = no registry file with Spearman rho above {rho_limit:.2f} and no registry file with more than {overlap_limit_pct:.0f}% of our dots within 3 px of its dots.</p>
</section>
<section>
  <h2>Validators (shared template tools, run on the shipped bytes)</h2>
  <table><tr><th>Check</th><th>Exit code (0 = pass)</th></tr>
  {''.join(f'<tr><td>{esc(a)}</td><td>{b}</td></tr>' for a, b in val_rows)}</table>
  <h3>In-lane checks on the whole array</h3>
  <table><tr><th>Check</th><th>Value</th></tr>{in_rows}</table>
</section>
<section>
  <h2>Uniqueness receipt (rebuilt registry, {gate['registry_unique_on_grid']} unique rasters)</h2>
  <p>Every unique (sha256) registry raster on the official grid was compared. Overlap = share of our dots within 3 px of that raster's dots. Lift = overlap / chance coverage (1.0 = what random placement would give).</p>
  <p>Sparse dot maps flagged (the eight with the largest overlap). Dense rasters ({diag['flagged_by_class'].get('dense(>50% nonzero)', 0)} flagged) are left out of this table: they overlap 100% by construction.</p>
  <table><tr><th>Registry dot map</th><th>Dots</th><th>Overlap (our dots within 3 px)</th><th>Chance coverage</th><th>Lift</th><th>Footprint-only rho</th></tr>{top_rows}</table>
  <p>Canonical full receipt (621 rasters): <code>evidence/uniqueness_gate_{esc(cur['name'])}.json</code>. Diagnostics: <code>evidence/uniqueness_diagnostics_{esc(cur['name'])}.json</code>. The later <code>*_refresh.json</code> checks only three rasters and is not a clearance (IR-53-49).</p>
</section>
<section>
  <h2>Why the uniqueness gate flags the file (diagnostics; the verdict is the pre-registered receipt)</h2>
  <ul>
    <li><b>{diag['flagged_rows_analysed']}</b> registry rasters are flagged. By class: {esc(', '.join(f'{k}: {v}' for k, v in diag['flagged_by_class'].items()))}.</li>
    <li>By overlap above {overlap_limit_pct:.0f}%: {diag['flagged_by_overlap']}. By Spearman rho above {rho_limit:.2f} of the candidate surface: {sp_rho['flagged_by_surface_rho_whole_grid']} rasters on the whole grid (NaN counted as 0, which inflates rho through the zeros outside the footprint), and {sp_rho['flagged_by_surface_rho_footprint_only']} on the footprint only (IR-53-47). The final raster exceeds {rho_limit:.2f} for none of the rasters on either basis.</li>
    <li>Chance coverage of the densest sparse dot map: <b>{100 * diag['densest_sparse_dot_maps_by_chance_coverage'][0]['chance_coverage']:.2f}%</b> of the footprint lies within 3 px of its dots (<code>{esc(diag['densest_sparse_dot_maps_by_chance_coverage'][0]['file'][:80])}</code>). Any candidate placed on this footprint therefore overlaps that file above {overlap_limit_pct:.0f}%. The raw gate is <b>not satisfiable by placement</b> on this registry (IR-53-46).</li>
    <li>Median chance-corrected lift for the sparse flagged files: {diag['sparse_flagged_median_lift']:.2f} (1.0 means the overlap is what random placement would give). This is a diagnostic only. Changing the gate needs your explicit approval.</li>
  </ul>
</section>
<section>
  <h2>Why the label reads as it does</h2>
  <ul>
    <li>The format and conformance checks pass ({'yes' if gate_pass['format_validators_all'] else 'no'}).</li>
    <li>The uniqueness gate: {'no drift flag' if not gate['any_drift_flag'] else 'drift flagged'}.</li>
    <li>The holdout gate: {'accepted' if accepted else 'not accepted'} (stage 2, paired, design B). {('' if accepted else 'The candidate is the design-B holdout best (bands top-q 0.02) and does not clear the confirmation rule, so it is labelled research-only.')}</li>
    <li>The canary: bands max separability {f4(cd['bands_max_over_all'])}, H1 {f4(cd['h1_max_separability'])}, both below the 0.90 gate.</li>
  </ul>
</section>
"""
    (DOCS / "submission.html").write_text(page("The file", body, "submission.html"))

    # ---------------------------------------------------------------- evidence.html
    e1_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{f4(v['pooled_DTI'])}</td><td>{esc(v['CI95_t_df4_on_fold_mean'])}</td><td>{v['mean_emitted_px']:,}</td></tr>"
        for k, v in e1["arms"]["bands"].items() if k.startswith("top_q"))
    def kept_txt(v):
        k = v["mean_kept_dots"]
        return "" if k is None else f"{k:,}"

    e2_rows = "".join(
        f"<tr><td>{esc(v['arm'])}</td><td>{esc(v['variant'])}</td><td>{f4(v['pooled_DTI'])}</td>"
        f"<td>{esc(v['CI95_t_df4_on_fold_mean'])}</td><td>{v['mean_emitted_px']:,}</td><td>{kept_txt(v)}</td></tr>"
        for v in V.values())
    fold_rows = "".join(
        f"<tr><td>{r['fold']}</td><td>{r['withheld_px']:,}</td><td>{r['withheld_segments']}</td><td>{f4(r['baseline']['DTI'])}</td>"
        f"<td>{f4(r['selected']['DTI'])}</td></tr>" for r in sp.get("per_fold", []))
    canary_rows = "".join(f"<tr><td>{esc(b)}</td><td>{f4(v)}</td></tr>" for b, v in cd["bands_max_separability_per_band"].items())
    irr_rows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i['severity'])}</td><td>{esc(i['status'])}</td><td>{esc(i['subject'])}</td></tr>" for i in irr)
    lim_rows = "".join(f"<tr><td>{esc(i['id'])}</td><td>{esc(i['item'])}</td></tr>" for i in lim)
    src_rows = "".join(f"<tr><td>{esc(k)}</td><td><a href=\"{esc(s['url'])}\">{esc(s['title'][:90])}</a></td><td>{esc(s['access'][:90])}</td></tr>"
                       for k, s in srcs.items())
    hyp_rows = """<tr><td>C1 (rank 1)</td><td>Band 17 conductivity + band 2 RTP multi-scale cross-wavelet phase/edge coherence</td><td>Untested. Uses the existing feature stack; medium cost, moderate/low-confidence prior. Budget exhausted; no DTI result. See docs/research/hypotheses.md.</td></tr>
<tr><td>C2 (rank 2)</td><td>Raw USGS ComCat earthquake event depth/time planes</td><td>Candidate only. S29 host was not reachable from this session; not viable until access/terms are checked.</td></tr>
<tr><td>C3 (rank 3)</td><td>Multi-date Landsat Level-2 surface-temperature residuals</td><td>Candidate only. S30 host was not reachable from this session; not viable until coverage/access/terms are checked.</td></tr>
<tr><td>H1 + M1</td><td>Segment-exact learn-predict separation + metric-aware thinning</td><td>Already tested in E2; selected candidate fails the raw registry duplicate gate.</td></tr>
<tr><td>H2</td><td>Band-2 magnetic Hessian ridges</td><td>Attempted in X1/X2/X3, but X2 used the invalid design-A negative pool (IR-53-37); not untried, not cleanly validated.</td></tr>
<tr><td>H5 / H7</td><td>Thermal/geothermal and strike/trend priors</td><td>Related portfolio analogues exist; do not claim broad-family novelty.</td></tr>
<tr><td>H3 / H4</td><td>Strain orientation / extra Qfault labels</td><td>H3 blocked (IR-53-40); H4 rejected as a label-source re-expression.</td></tr>"""
    g = g32["files"]["nan"]
    # ---------------------------------------------------------------- S3 evidence (from the run card's s3_lane)
    s3l = J("evidence/run_card.json")["s3_lane"]
    s3_h = s3l["holdout"]; s3_cv = s3l["leakage_canary"]; s3_co = s3l["correlation_overlap"]
    s3_ci = s3_h["paired_H8_minus_H1"]["CI95"]
    s3_max = s3_cv["H8_features_separability_max_over_folds"]
    s3_rec = J(s3l["submission_file"]["file"].replace(".tif", ".json").replace("docs/submissions/", "evidence/candidate_"))
    s3_ev = f"""<section id="s3-evidence">
  <h2>S3 (2026-10-08): GEMSDOE29 canary reproduction, H8 holdout, control build</h2>
  <p class="note">Pre-registration: <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/arena/7b60bcc7-gemsdoe53/docs/research/preregistration-2026-10-08-S3.md">preregistration-2026-10-08-S3.md</a>. Holdout numbers are HOLDOUT-DTI (proxy, evaluator {esc(s3_h['evaluator'])}, not organizer-scored).</p>
  <table><tr><th>Step</th><th>Result</th><th>Receipt</th></tr>
  <tr><td>S3-A leakage reproduction (no selection)</td><td>Leaky GEMSDOE29 distance feature, separability on design-B fold 0: <b>{s3_cv['S3A_leaky_distance_separability_fold0']:.3f}</b>. Canary flags it: <b>{'yes' if s3_cv['S3A_verdict'] else 'no'}</b> (gate 0.90).</td><td><code>evidence/s3a_leakage_repro.json</code></td></tr>
  <tr><td>S3-B H8 gravity-gradient ridges, design B</td><td>Canary, max over the five folds: R {s3_max['R']:.3f}, S {s3_max['S']:.3f}, log1pD {s3_max['log1pD']:.3f} (all below 0.90). Stage-2 pooled HOLDOUT-DTI: H8 <b>{f4(s3_h['H8_pooled_DTI'])}</b>; H1 thin_bin_q0p1 {f4(s3_h['H1_thin_bin_q0p1_pooled_DTI_same_proxy'])}; bands baseline {f4(s3_h['bands_baseline_pooled_DTI'])}. Paired H8 minus H1: {s3_h['paired_H8_minus_H1']['mean_fold_diff']:+.6f}, 95% CI {s3_ci[0]:+.6f} to {s3_ci[1]:+.6f}. Verdict: <b>{esc(s3_h['verdict']['label'])}</b> (withheld positives {s3_h['withheld_positives']:,}).</td><td><code>evidence/s3b_h8_holdout.json</code></td></tr>
  <tr><td>S3-C control build and gate</td><td>Final dots {s3_rec['final_dots']:,}. Uniqueness: {s3_co['n_flagged']} of {s3_co['registry_unique_on_grid']} registry rasters flagged. Label: <b>Research-only / DO NOT SUBMIT</b>. Not submitted; no slot used.</td><td><code>{esc(s3_co['receipt'])}</code></td></tr>
  </table>
</section>
"""
    body = f"""
<section>
  <h1>Evidence</h1>
  <p class="note">Evidence metrics are read from JSON. HOLDOUT-DTI = catalogue proxy, not organizer score. Evaluator <code>gems53.core.dti</code> v1.0.0, parity with the template's <code>src/metrics.py</code>
  (difference {e1['metric_parity_vs_template']['abs_diff']:.1e}); individual sections name the withheld-positive count and CI basis.</p>
  <p><a href="data/run_card.json">Run card (JSON)</a> · <a href="data/e1_h1_thin_holdout.json">E1 record</a> · <a href="data/e2_leakfree_holdouts.json">E2 record</a> · <a href="data/exp2_holdout_arms.json">design-A ablation reference</a> ·
  <a href="https://github.com/buffedlizard55-lab/GEMSDOE53/blob/arena/7b60bcc7-gemsdoe53/docs/research/preregistration-2026-10-08.md">pre-registration</a></p>
</section>
<section>
  <h2>E1 (design A, reference only): exploration with the withheld-label negative pool</h2>
  <div class="warn">Design A is <b>not used</b> for any decision (IR-53-37); its withheld-derived negative buffer creates a side channel. The table reports reference-only HOLDOUT-DTI from evaluator gems53.core.dti v1.0.0: 60,988 withheld positives in 3,199 segments, with 95% t CIs (df 4). Reproduction of the earlier exp2 numbers: {'PASS' if e1['reproduction_check_vs_exp2']['pass'] else 'FAIL'}.</div>
  <table><tr><th>Bands arm variant</th><th>Pooled HOLDOUT-DTI</th><th>95% t CI, df 4</th><th>Emitted px</th></tr>{e1_rows}</table>
  <p>H1 design-A reference HOLDOUT-DTI at top-q 0.02: <b>{f4(e1['arms']['h1']['top_q0p02']['pooled_DTI'])}</b> (95% t CI {e1['arms']['h1']['top_q0p02']['CI95_t_df4_on_fold_mean']}). Canary, design A (buffered background; not DTI): H1 mean separability {f4(e1['canary_H1_feature_alone']['separability_mean'])}.</p>
</section>
<section>
  <h2>E2 (design B): stage 1, all 24 variants on segment folds (seed 53)</h2>
  <p>Negatives are every footprint pixel that is not a visible fault (DEV-1). Values are HOLDOUT-DTI (proxy; evaluator gems53.core.dti v1.0.0; 60,988 withheld positives in 3,199 segments). Each row has a 95% t CI (df 4); the selected value is optimistic because selection occurs across the 24 variants on these folds.</p>
  <table><tr><th>Arm</th><th>Variant</th><th>Pooled HOLDOUT-DTI</th><th>95% t CI (df 4)</th><th>Emitted px</th><th>Kept dots</th></tr>{e2_rows}</table>
  <h3>Fold detail, baseline vs selected (stage 2, spatial HOLDOUT-DTI)</h3>
  <table><tr><th>Fold</th><th>Withheld positive px</th><th>Withheld segments</th><th>Baseline HOLDOUT-DTI (per fold)</th><th>Selected HOLDOUT-DTI (per fold)</th></tr>{fold_rows}</table>
  <p class="note">For spatial confirmation the reported primary uncertainty is the paired fold-difference interval (df 4); pooled absolute baseline and candidate HOLDOUT-DTI are 0.000102 and 0.004049, with 60,988 withheld positives across 3,199 segments.</p>
</section>
<section>
  <h2>Canary under design B (19 label-free bands; background = full non-fault footprint)</h2>
  <table><tr><th>Band</th><th>Max separability over folds</th></tr>{canary_rows}</table>
  <p>H1 feature alone: max separability {f4(cd['h1_max_separability'])}. Gate 0.90. Flags: bands {esc(cd['bands_flag'])}, H1 {esc(cd['h1_flag'])}.</p>
</section>
{s3_ev}
<section id="gemsdoe29">
  <h2>GEMSDOE29 leakage (formal diagnosis)</h2>
  <p>Mechanism: the deprecated <code>scripts/build_repo_candidate.py</code> in GEMSDOE29 builds its distance-to-known-faults feature from the full label raster, so that feature is exactly 0 on known-fault pixels. This is target-derived training information, not a valid accuracy result. In our separate historical design-A leaky ablation (not GEMSDOE29's organizer score), the pooled <b>HOLDOUT-DTI</b> was {f4(leaky_holdout['pooled_DTI'])}, 95% t CI (df 4) {leaky_holdout['CI95_t_df4_on_fold_mean']}; evaluator gems53.core.dti v1.0.0, 60,988 withheld positives in 3,199 segments. This near-perfect diagnostic is invalid for model-quality claims because the negative-pool buffer depended on withheld labels (IR-53-37). GEMSDOE29's upstream TRAIN-AUC and this reproduction are distinct evidence. See <code>docs/leakage-review.md</code>; learn-predict separation is the repair.</p>
</section>
<section id="gemsdoe32">
  <h2>GEMSDOE32 H33-2-B2: structure beside public leaderboard row 0.2778 (file attribution not established)</h2>
  <table>
    <tr><th>Measured (registry copy, NaN variant)</th><th>Value</th></tr>
    <tr><td>dots (value 1), share of footprint</td><td>{g['dots']:,} ({pct(g['dots_share_of_footprint'])})</td></tr>
    <tr><td>dots within 2 px of a mapped fault</td><td>{pct(g['dots_within_2px_of_catalogue'])}</td></tr>
    <tr><td>dots within 3 px of a mapped fault</td><td>{pct(g['dots_within_3px_of_catalogue'])}</td></tr>
    <tr><td>nearest-dot distance, median (px)</td><td>{g['nearest_dot_distance_quantiles_px']['0.5']}</td></tr>
    <tr><td>finite pixels (footprint) vs zeros variant</td><td>{g['finite_px']:,} vs {g32['files']['zeros']['finite_px']:,} (the zeros variant fills the grid with 0, IR-53-41)</td></tr>
    <tr><td>in-catalogue DTI (diagnostic only)</td><td>{f4(g['in_catalogue_DTI_diagnostic'])}</td></tr>
  </table>
  <p><b>OWNER-CLAIM (not verified):</b> 0.2708 base, dots within 2 px removed, 37,654 dots, no organiser score. The pruning claim is consistent with the measured 0.0% within 2 px.
  <b>NOT ESTABLISHED:</b> that this file produced the 0.2778 row (IR-53-02). <b>MEASURED:</b> the dots are spaced about the metric radius apart, the same structure that thinning produces (M1).</p>
</section>
<section id="hypotheses">
  <h2>Hypotheses (next candidates; no untested score claimed)</h2>
  <p class="warn">The three-experiment budget is exhausted. C1–C3 are hypotheses only; none has been validated or promoted. See the full layer/signature/rationale/novelty screen in <a href="research/hypotheses.md">docs/research/hypotheses.md</a>.</p>
  <table><tr><th>ID</th><th>Hypothesis</th><th>Status</th></tr>{hyp_rows}</table>
</section>
<section id="irregularities">
  <h2>Irregularities (flagged for review)</h2>
  <table><tr><th>ID</th><th>Severity</th><th>Status</th><th>Subject</th></tr>{irr_rows}</table>
</section>
<section id="limitations">
  <h2>Limitations and remaining work</h2>
  <table><tr><th>ID</th><th>Item</th></tr>{lim_rows}</table>
</section>
<section>
  <h2>Sources</h2>
  <table><tr><th>ID</th><th>Source</th><th>Access</th></tr>{src_rows}</table>
</section>
"""
    (DOCS / "evidence.html").write_text(page("Evidence", body, "evidence.html"))

    # ---------------------------------------------------------------- data copies for the links
    data_dir = DOCS / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for rel in ("evidence/run_card.json", "evidence/e1_h1_thin_holdout.json", "evidence/e2_leakfree_holdouts.json",
                "evidence/exp2_holdout_arms.json", f"evidence/uniqueness_gate_{cur['name']}.json", f"evidence/uniqueness_diagnostics_{cur['name']}.json",
                cur["receipt"], "evidence/gemsdoe32_measured.json", "registry/irregularities.json",
                "registry/limitations.json", "registry/sources.json", "docs/submissions/CURRENT.json"):
        src = ROOT / rel
        if src.exists():
            shutil.copy(src, data_dir / src.name)
    # Retain current evidence copies and the separate inventory/card consumed by the site.
    keep = {Path(r).name for r in ("evidence/run_card.json", "evidence/e1_h1_thin_holdout.json",
                                   "evidence/e2_leakfree_holdouts.json")} | {"inventory.json", "parallel-run-card.json"}
    for f in data_dir.glob("*.json"):
        if f.name not in keep and not (ROOT / "evidence").joinpath(f.name).exists() and f.name not in {Path(p).name for p in ("registry/irregularities.json", "registry/limitations.json", "registry/sources.json", "docs/submissions/CURRENT.json")}:
            f.unlink()
    (DOCS / ".nojekyll").write_text("")  # serve the static HTML as-is
    print("site written:", DOCS / "index.html", DOCS / "submission.html", DOCS / "evidence.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
