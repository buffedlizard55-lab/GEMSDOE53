#!/usr/bin/env python3
"""Regenerate a dated, stdlib-only local-evidence feed. No portal interaction.

DrivenData automation is disabled by default: review registry/source_policy.json
and the site's disclosed limitation. A fresh local timestamp is NOT a fresh
leaderboard observation. Run this before scripts/publish_site_r2.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / 'evidence'
DOCS = ROOT / 'docs'
DATA = DOCS / 'data'
DL = DOCS / 'downloads'
BOARD = 'https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/'
OUR_BEST = 0.2778  # brief/owner attribution, NOT an authenticated artifact score


def log(message):
    print(message, flush=True)


def write(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / name
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')
    return path


def safe(value):
    if isinstance(value, float) and not (-float('inf') < value < float('inf')):
        return None
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v) for v in value]
    return value


def copy_evidence():
    # Historical evidence remains in Git for audit, but is not silently promoted
    # as current just because this scheduled publisher ran.
    copied = []
    for path in sorted(EV.glob('*_r[23]*.json')):
        write(path.name, safe(json.loads(path.read_text())))
        copied.append(path.name)
    for name in ('r2_preregistration', 'r3_preregistration', 'h55_preregistration',
                 'h55_edge_preregistration', 'h58_preregistration', 'h59_preregistration',
                 'source_policy', 'data_manifest', 'irregularities',
                 'leaderboard_snapshot_2026-10-07'):
        path = ROOT / 'registry' / (name + '.json')
        if path.exists():
            if name in ('h55_preregistration', 'h55_edge_preregistration',
                        'h58_preregistration', 'h59_preregistration'):
                # A frozen registration's bytes are part of its audit trail; preserve them in the
                # static site rather than semantically reserializing its JSON.
                target = DATA / (name + '.json')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
            else:
                write(name + '.json', safe(json.loads(path.read_text())))
            copied.append(name + '.json')
    # H55 publishes its own evidence the same way the R2 round publishes *_r2.json: copied on every
    # run so the page cannot drift from the artefact, and named by round so it is never mistaken for
    # another round's numbers.  The Phase-2 reasoning record is staged next to the raster it explains.
    for pat in ('h55_*.json', 'h58_*.json', 'h59_*.json', 'submission_gems52-h55-*.json',
                'submission_gems52-h58-*.json', 'submission_gems52-h59-*.json'):
        for path in sorted(EV.glob(pat)):
            write(path.name, safe(json.loads(path.read_text())))
            copied.append(path.name)
    marker = ROOT / 'submission/LATEST.txt'
    if marker.exists():
        current_name = marker.read_text().strip()
        current_stem = current_name[:-4] if current_name.endswith('.tif') else current_name
        current_receipt = EV / f'submission_{current_stem}.json'
        if current_receipt.exists() and current_stem.startswith('gems52-h56-cotrain-'):
            receipt = json.loads(current_receipt.read_text())
            write('submission_h56.json', safe(receipt))
            copied.append('submission_h56.json')
            # The audit page links the per-candidate reasoning record from the tagged receipt.
            # Publish only a basename under the evidence directory; never follow an arbitrary
            # receipt path outside the repository into the static site.
            reasoning_name = Path(str((receipt.get('reasoning') or {}).get('json') or '')).name
            if reasoning_name.startswith('h56_reasoning_') and reasoning_name.endswith('.json'):
                reasoning_source = EV / reasoning_name
                if reasoning_source.is_file():
                    DATA.mkdir(parents=True, exist_ok=True)
                    (DATA / reasoning_name).write_bytes(reasoning_source.read_bytes())
                    copied.append(reasoning_name)
    for path in sorted(EV.glob('h55_reasoning_*.json')):
        (DL / path.name).write_text(path.read_text())
    reasoning = EV / 'a_only_reasoning_r3.csv'
    if reasoning.exists():
        target = DL / reasoning.name
        DL.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != reasoning.read_bytes():
            target.write_bytes(reasoning.read_bytes())
        copied.append(reasoning.name)
    return copied


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def submission_note(d):
    """The <=200-character note that distinguishes this submission later.

    A record may carry both a short ``submission_note`` (what actually goes in the portal's box, which
    is length-limited) and a ``submission_note_long`` (the full reasoning, published on the site and in
    the evidence file).  Truncating the long one is what produced a note that ended mid-sentence, so
    the long form is never truncated into the short field: it is offered separately.
    """
    if d.get('submission_note'):
        return str(d['submission_note'])[:200]
    portal_note = (d.get('portal') or {}).get('note')
    if portal_note:
        return str(portal_note)[:200]
    n = (f"H54 revealed-core {d.get('retained_core_px', 0)}px + {d.get('novel_px', 0)}px novel "
         f"strike-continuation; 200m corridor excluded; |G|=14089")
    return n[:200]


def make_zip(name):
    """One-click ZIP beside the TIF: the raster, the note to paste, and the evidence behind it.

    Round-agnostic on purpose.  Two rounds have shipped records with different shapes (H54 carries
    ``retained_core_px`` / ``novel_along_strike_px`` / ``corridor_excluded_m``; H55 carries
    ``geometry`` / ``selection`` / ``uniqueness``), and a zip that prints ``None px retained core``
    for a round it was not written against is worse than a generic one.  So the body is assembled
    from the keys the record actually has, and says which round it came from.
    """
    import zipfile
    src = ROOT / 'submission' / name
    if not src.exists():
        return None
    stem = name[:-4] if name.endswith('.tif') else name
    zp = DL / f'{stem}.zip'
    if stem.startswith('gems52-h58-'):
        # H58's portal ZIP is intentionally a single member: exactly one GeoTIFF. The short portal
        # note and full evidence are published alongside it, not bundled as extra upload files.
        if zp.exists():
            try:
                with zipfile.ZipFile(zp) as existing:
                    valid = (existing.namelist() == [name]
                             and existing.read(name) == src.read_bytes()
                             and existing.testzip() is None)
                if valid:
                    return str(zp)
            except (OSError, KeyError, zipfile.BadZipFile):
                pass
        with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(src, arcname=name)
        return str(zp)
    ev = EV / f'submission_{stem}.json'
    d = json.loads(ev.read_text()) if ev.exists() else {}
    proj = d.get('projected_dti') or {}
    lines = [
        name,
        f"sha256 {d.get('sha256')}",
        f"{d.get('bytes')} bytes, 1 band, float32, EPSG:32611, values in [0,1], no NaN.",
        '',
        "SUBMISSION NOTE (<=200 chars, paste into the portal's notes box):",
        submission_note(d),
        '',
    ]
    if d.get('submission_name'):
        lines += [f"SUBMISSION NAME: {d['submission_name']}", '']
    if d.get('retained_core_px') is not None:
        lines += [
            f"What it is: {d.get('budget')} emitted pixels = {d.get('retained_core_px')} px retained "
            f"core (the double-corroborated atom A&C, whose credit the organiser's own published "
            f"scores bound exactly) + {d.get('novel_px')} px strictly novel "
            f"({d.get('novel_along_strike_px')} along the recovered strike of that structure, "
            f"{d.get('novel_far_px')} free candidates on the same fabric).",
            f"Nothing is emitted within {d.get('corridor_excluded_m')} m of a mapped trace, because "
            f"that ring's credit is exactly zero in the organiser's own scores (knowledge/10 s2).",
            f"Projected DTI {proj.get('mean_dti')} (P(win over 0.2778) {proj.get('p_win')}); the "
            f"projection is an integral over a stated prior, not a forecast - see "
            f"evidence/revealed_budget.json.",
            '',
        ]
    geo, sel, uni = d.get('geometry') or {}, d.get('selection') or {}, d.get('uniqueness') or {}
    if geo:
        lines += [
            f"What it is: {geo.get('S')} emitted pixels, every one 8-isolated "
            f"(largest component {geo.get('max_component')}), placed by a coverage-greedy on the "
            f"metric's own numerator.",
            f"Placement efficiency A/S = {geo.get('A_per_S')} = "
            f"{(geo.get('spacing_efficiency') or 0):.2%} of the exact 9.380298 kernel-disc ceiling; "
            f"the file that scored 0.2778 reached 8.044 (85.75%).",
        ]
    if sel:
        lines += [
            f"Selected by the pre-registered rule from {sel.get('source')}: "
            f"{sel.get('arm')}|{sel.get('emitter')}. Blocked whole-segment holdout, 4 folds x 2 "
            f"instruments, matched-budget random control: hide {sel.get('hide')} "
            f"({sel.get('hide_wins')}/4 folds) vs random; tip {sel.get('tip')} "
            f"({sel.get('tip_wins')}/4). Those are recovery numbers on hidden catalogue segments, "
            f"NOT a forecast of the portal score.",
            f"|G| = {sel.get('n_g')} calibrated by inverting DTI = T/(0.2*S + 0.8*|G|) on 13 "
            f"SHA-256-verified scored rasters (evidence/h55_g_calibration.json).",
        ]
    if uni:
        lines += [
            f"Uniqueness gate: {uni.get('relation_to_union')}; "
            f"{(uni.get('novel_fraction') or 0):.1%} of this file's pixels touch none of the "
            f"{uni.get('n_priors_checked')} priors scanned, and {uni.get('prior_px_dropped')} prior "
            f"pixels are deliberately not re-emitted.",
        ]
    if d.get('projection'):
        lines += [
            f"Placement gain in isolation (the 0.2778 file's own rho_A = 0.01287 applied to this "
            f"file's measured coverage, nothing else changed): DTI ~ "
            f"{d['projection'].get('geometry_only_dti')}. Arithmetic given its assumption, and the "
            f"assumption is stated in the evidence file.",
        ]
    if d.get('submission_note_long'):
        lines += ['', 'FULL REASONING (too long for the portal box; published on the site):',
                  str(d['submission_note_long']), '']
    body = "\n".join(lines)
    zp = DL / f'{stem}.zip'
    expected_members = [name, 'SUBMISSION_NOTE.txt'] + (['evidence.json'] if ev.exists() else [])
    # Preserve a byte-identical, already-valid archive rather than changing ZIP timestamps on every
    # scheduled refresh. Rebuild only when a member, note, or receipt actually changes.
    if zp.exists():
        try:
            with zipfile.ZipFile(zp) as existing:
                valid = (existing.namelist() == expected_members
                         and existing.read(name) == src.read_bytes()
                         and existing.read('SUBMISSION_NOTE.txt') == body.encode())
                if ev.exists():
                    valid = valid and existing.read('evidence.json') == ev.read_bytes()
                valid = valid and existing.testzip() is None
            if valid:
                return str(zp)
        except (OSError, KeyError, zipfile.BadZipFile):
            pass
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(src, arcname=name)
        z.writestr('SUBMISSION_NOTE.txt', body)
        if ev.exists():
            z.write(ev, arcname='evidence.json')
    return str(zp)


def latest_submission():
    # Two rounds ship artefacts and each keeps its own marker.  Prefer the one that carries a complete
    # gate report of its own, so the site never offers a file whose audit it cannot show; IR-52-029
    # records the choice, the reason, and that reverting is one line in submission/LATEST.txt.
    order = []
    for marker in (ROOT / 'submission/LATEST.txt', ROOT / 'submission/R2_LATEST.txt'):
        if marker.exists():
            nm = marker.read_text().strip()
            stem = nm[:-4] if nm.endswith('.tif') else nm
            own = EV / f'submission_{stem}.json'
            order.append((nm, marker, own))
    if not order:
        return dict(exists=False, file=None, note='No artifact has been built.')
    # A missing per-artefact receipt must NOT promote a different round's archive as "current".
    # This used to fall through to the next marker, so when H57 shipped without
    # evidence/submission_<h57 stem>.json the scheduled feed published the R2 archive's full report
    # under docs/data/submission.json -- pointing the whole site back at a two-year-old artefact.
    # The current marker wins whatever receipts exist; only its OWN receipt may be used.
    name, marker, own = order[0]
    stem = name[:-4] if name.endswith('.tif') else name
    path = DL / name
    r2 = EV / 'submission_r2.json'
    if own.exists():
        candidate = json.loads(own.read_text())
        if candidate.get('file') == name or candidate.get('stem') == stem:
            report = candidate
            report['file'] = name
        else:
            report = dict(file=name, approved_for_weekly_slot=False,
                          promotion='current round; no per-artefact receipt at '
                                    f'evidence/submission_{stem}.json, so no gate report is shown')
    elif r2.exists() and name == json.loads(r2.read_text()).get('file'):
        report = json.loads(r2.read_text())
    else:
        report = dict(file=name, approved_for_weekly_slot=False,
                      promotion='current round; no per-artefact receipt at '
                                f'evidence/submission_{stem}.json, so no gate report is shown')
    if report.get('synthetic') is True:
        report.update(
            approved_for_weekly_slot=False,
            promotion='synthetic methodology demo; not approved for portal upload',
            artifact_status='RESEARCH ONLY — SYNTHETIC METHODOLOGY DEMO',
            official_score_status='no portal upload or organizer score is recorded',
            submission_slots_used=0,
            slot_gate=dict(approved_for_weekly_slot=False,
                           reason='Synthetic inputs are not competition data; real-data holdout has not been run. Do not upload or spend a slot.'),
        )
    if report.get('format_gate') and not report.get('format'):
        report['format'] = report['format_gate']
    report['marker'] = str(marker.relative_to(ROOT))
    report['exists'] = path.exists()
    report['download'] = 'downloads/' + name
    report['download_zip'] = 'downloads/' + name.replace('.tif', '') + '.zip'
    if stem.startswith('gems52-h58-'):
        report.setdefault('short_tif', 'h58-candidate.tif')
        report.setdefault('short_zip', 'h58-candidate.zip')
        report.setdefault('promoted', False)
        report.setdefault('nonzero_px', report.get('emitted_pixels'))
    report['submission_note'] = submission_note(report)
    report['submission_note_chars'] = len(report['submission_note'])
    if path.exists():
        actual_bytes = path.stat().st_size
        actual = file_hash(path)
        if report.get('bytes') is not None and int(report['bytes']) != actual_bytes:
            raise ValueError('Published TIFF byte count differs from the audited receipt. Do not publish it.')
        if report.get('sha256') and report['sha256'] != actual:
            raise ValueError('Published TIFF differs from the audited TIFF. Do not upload it.')
        report['bytes'] = actual_bytes
        report['published_byte_hash_matches_receipt'] = report.get('sha256') == actual
    return report


def parse_board(text):
    """Conservative optional parser. It is never called without recorded permission."""
    import html
    rows = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', text, re.S):
        cells = [html.unescape(re.sub(r'<[^>]+>', ' ', x)).strip()
                 for x in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S)]
        scores = [float(t) for t in cells if re.fullmatch(r'0\.\d{3,6}', t)]
        if scores and cells and re.fullmatch(r'\d+', cells[0]):
            names = [t for t in cells[1:] if t and not re.fullmatch(r'[\d.]+', t)]
            rows.append(dict(rank=cells[0], team=names[0] if names else 'not parsed', score=scores[0]))
    return rows


def fetch_board(do_fetch=False):
    snapshots = sorted((ROOT / 'registry').glob('leaderboard_snapshot_*.json'))
    snap = snapshots[-1] if snapshots else None
    out = json.loads(snap.read_text()) if snap and snap.exists() else dict(rows=[])
    out.update(source=BOARD, owner_best_reported=OUR_BEST,
               artifact_score_authenticated=False,
               note='Dated participant-level observation; no filename/hash/receipt attribution. Participant identity is not authenticated as the user\'s team.')
    policy = json.loads((ROOT / 'registry/source_policy.json').read_text())['drivendata']
    allowed = bool(policy.get('automated_fetch_allowed') and policy.get('written_permission_reference'))
    out['automated_fetch_allowed'] = allowed
    if not allowed:
        out['status'] = 'dated snapshot; automated DrivenData access disabled by Terms-of-Use policy'
        out['fetch_requested_but_disabled'] = bool(do_fetch)
        # Crucially, fetched_utc is retained unchanged.
        return out
    if not do_fetch:
        out['status'] = 'dated snapshot; this run did not fetch external data'
        return out
    try:
        request = urllib.request.Request(BOARD, headers={'User-Agent': 'GEMSDOE52 permitted source refresh'})
        text = urllib.request.urlopen(request, timeout=25).read().decode('utf-8', 'replace')
        rows = parse_board(text)
        if not rows:
            raise ValueError('No verified table rows parsed; retaining prior snapshot')
        out.update(status='fetched under recorded permission', rows=rows, top=rows[0]['score'],
                   fetched_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    except Exception as error:
        out['status'] = 'external fetch failed; prior snapshot retained: ' + str(error)[:180]
        out['fetch_error'] = True
    return out


def current_branch(explicit=None):
    if explicit:
        return explicit
    head = ROOT / '.git/HEAD'
    if head.exists():
        value = head.read_text().strip()
        if value.startswith('ref: refs/heads/'):
            return value.removeprefix('ref: refs/heads/')
    return 'detached or unknown (not assumed)'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true', help='Only honored with recorded written permission; otherwise no DrivenData request.')
    parser.add_argument('--branch', help='Actual Actions ref, if Git is checked out detached.')
    args = parser.parse_args()
    copied = copy_evidence()
    DL.mkdir(parents=True, exist_ok=True)
    # Stage the rasters and the one-click ZIP BEFORE the report is written: the report points into
    # docs/downloads/, so publishing after it left the site offering a file that was not there yet
    # (IR-52-028).
    for f in sorted((ROOT / 'submission').glob('*.tif')):
        tgt = DL / f.name
        if not tgt.exists() or file_hash(tgt) != file_hash(f):
            tgt.write_bytes(f.read_bytes())
    for mk in ('LATEST.txt', 'R2_LATEST.txt'):
        mp = ROOT / 'submission' / mk
        if mp.exists():
            make_zip(mp.read_text().strip())
    # H58 is an explicitly named research result, not the global incumbent unless a later
    # independent gate approves it. Publish its one-TIFF package and stable review aliases from
    # the H58 receipt without changing submission/LATEST.txt or docs/data/submission.json.
    h58_result_path = EV / 'h58_result.json'
    if h58_result_path.is_file():
        try:
            h58_name = str(json.loads(h58_result_path.read_text())['artifact']['file'])
        except (KeyError, ValueError, OSError):
            h58_name = ''
        if h58_name.startswith('gems52-h58-') and (ROOT / 'submission' / h58_name).is_file():
            archive_path = make_zip(h58_name)
            alias_pairs = [(DL / h58_name, DL / 'h58-candidate.tif')]
            if archive_path:
                alias_pairs.append((Path(archive_path), DL / 'h58-candidate.zip'))
            for source, alias in alias_pairs:
                if source.is_file() and (not alias.exists() or file_hash(source) != file_hash(alias)):
                    alias.write_bytes(source.read_bytes())
    # Also publish explicitly named research-only ZIPs without promoting them
    # through either global pointer. Their package receipts remain per-artifact.
    edge_marker = ROOT / 'submission/H55_EDGE_LATEST.txt'
    if edge_marker.exists():
        edge_name = edge_marker.read_text().strip()
        edge_zip = ROOT / 'submission' / Path(edge_name).with_suffix('.zip').name
        if edge_zip.exists():
            target_zip = DL / edge_zip.name
            if not target_zip.exists() or file_hash(target_zip) != file_hash(edge_zip):
                target_zip.write_bytes(edge_zip.read_bytes())
    sub = latest_submission()
    board = fetch_board(args.fetch)
    write('submission.json', sub)
    write('leaderboard.json', board)
    inv = EV / 'prior_inventory_r2.json'
    entries = json.loads(inv.read_text()).get('entries', []) if inv.exists() else []
    write('feed.json', dict(
        generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        branch=current_branch(args.branch), repo='buffedlizard55-lab/GEMSDOE52',
        evidence_copied=copied,
        files=sorted({p.name for pat in ('*_r[23]*.json', 'h55_*.json', 'h58_*.json',
                                         'submission_gems52-h55-*.json', 'submission_gems52-h58-*.json')
                      for p in DATA.glob(pat)}),
        submission=sub.get('file'), downloads=len(list(DL.glob('*.tif'))),
        leaderboard_status=board['status'],
        leaderboard_last_observed_utc=board.get('fetched_utc') or board.get('observed_date_utc'),
        prior_entries=len(entries), eligible_prior_rasters=sum(bool(r.get('eligible_prior')) for r in entries),
        scientific_gate=sub.get('approved_for_weekly_slot', False), slots_used=0,
        freshness_note='Local evidence refresh is automatic; the board is a dated snapshot. No automatic portal submission.'))
    log('Feed updated. ' + board['status'])
    return 1 if board.get('fetch_error') else 0


if __name__ == '__main__':
    sys.exit(main())
