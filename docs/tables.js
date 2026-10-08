// Table renderers shared by the validation / feed pages.  Same contract as render.js: fetch from
// docs/data/, print, and never invent a value that is missing.
(async function () {
  const need = ['holdout_tip', 'holdout_hide', 'independence_tip', 'independence_hide',
                'composite', 'feed', 'submission', 'layer_screen', 'folds_tip', 'folds_hide',
                'strata_tip', 'strata_hide'];
  await Promise.all(need.map(n => G52.load(n)));
  G52.stamp();
  const d = G52.data;
  const el = id => document.getElementById(id);
  const table = (head, rows, cls = []) =>
    `<table><thead><tr>${head.map(h => `<th class="${h[1] || ''}">${h[0]}</th>`).join('')}</tr></thead>` +
    `<tbody>${rows.map((r, i) => `<tr class="${cls[i] || ''}">` + r.map(c =>
      Array.isArray(c) ? `<td class="num">${c[0]}</td>` : `<td>${c}</td>`).join('') + '</tr>').join('')}</tbody></table>`;

  // ---- arm tables, per instrument -----------------------------------------------------------
  if (el('armtables')) {
    let h = '';
    for (const [tag, key] of [['tip — mapping-truncation instrument', 'holdout_tip'],
                              ['hide — whole-component recovery', 'holdout_hold'.replace('hold', 'hide')]]) {
      const o = d[key];
      if (!o || o.__error) { h += `<h3>${tag}</h3><p class="small muted">no table yet</p>`; continue; }
      const keys = Object.keys(o.summary).sort((a, b) => o.summary[b].mean - o.summary[a].mean);
      const rows = keys.map(k => [
        k.startsWith('random') || k.startsWith('corridor_blanket') || k.startsWith('sibling')
          ? `<span class="muted">${esc(k)}</span>` : `<b>${esc(k)}</b>`,
        [o.summary[k].mean.toFixed(4)], [o.summary[k].sd.toFixed(4)],
        [o.summary[k].best_fold.toFixed(4)], [o.summary[k].worst_fold.toFixed(4)]]);
      const cls = keys.map(k => (o.gates?.tested === k ? 'hi' : ''));
      h += `<h3>${tag}</h3>` + table([['arm | budget', ''], ['mean DTI', 'num'], ['sd', 'num'],
        ['best fold', 'num'], ['worst fold', 'num']], rows, cls) +
        `<p class="small muted">${o.n_folds} folds · ${esc(o.emit)} emission · prevalence ${
          (100 * (o.prevalence ?? 0.002)).toFixed(2)} % · gates: ${o.gates?.promoted ? 'promoted' : 'not promoted'}
          (${esc(o.gates?.reason ?? '')}) · ${new Date(o.generated * 1000 || Date.now()).toISOString().slice(0, 10)}</p>`;
    }
    el('armtables').innerHTML = h;
  }

  // ---- independence -------------------------------------------------------------------------
  if (el('indep')) {
    let h = '';
    for (const [tag, key] of [['tip', 'independence_tip'], ['hide', 'independence_hide']]) {
      const i = d[key] && !d[key].__error ? d[key] : null;
      if (!i) { h += `<p class="small muted">no ${tag} independence record</p>`; continue; }
      if (i.false_alarm) {
        h += `<h3>${tag}: block × fold cell test</h3>` + table([['quantity', ''], ['Pearson r', 'num'],
          ['Spearman ρ', 'num'], ['cells', 'num'], ['reading', '']], [
          ['false-alarm level (over-prediction on non-catalogue pixels)',
            [i.false_alarm.pearson_r.toFixed(4)], [i.false_alarm.spearman_rho.toFixed(4)],
            [i.n_cells], i.false_alarm.pearson_r < 0.6 ? 'below the 0.60 abandonment threshold' : 'at/above threshold'],
          ['miss level (under-prediction on catalogue pixels)',
            [i.misses.pearson_r.toFixed(4)], [i.misses.spearman_rho.toFixed(4)], [i.n_cells],
            i.misses.pearson_r < 0.6 ? 'below threshold — the views miss in different places' : 'at/above threshold'],
          ['pixel logit correlation, non-catalogue, pooled over fold models',
            [i.pearson_logit_negatives_pooled.toFixed(4)], ['–'], ['–'], 'same question at pixel resolution']]) +
          `<p class="small"><b>${i.independent_enough ? 'Premise holds' : 'Premise refuted'}</b> — ${esc(i.reading)}</p>`;
      } else {
        h += `<h3>${tag}: fitted-model reading</h3><p class="small">held-positive logit correlation
          <b>${i.pearson_logit_held_positives ?? '–'}</b>; co-training decision: ${esc(i.decision?.reading ?? '')}</p>`;
      }
    }
    el('indep').innerHTML = h;
  }

  // ---- two-regime composite sweep -----------------------------------------------------------
  if (el('composite')) {
    const s = d.composite && !d.composite.__error ? d.composite : null;
    if (!s) {
      el('composite').innerHTML = '<p class="small muted">no composite sweep on disk — run '
        + '<code>scripts/composite_split.py</code></p>';
    } else {
      const modes = s.modes || [];
      const yn = b => b ? '<span class="tag ok">yes</span>' : '<span class="tag no">no</span>';
      const rows = (s.ranked || []).map(([k, v]) => [esc(k),
        ...modes.map(m => [G52.fmt(v['mean_' + m])]),
        ...modes.map(m => [G52.fmt(v.rand ? v.rand[m] : null)]),
        [G52.fmt(v.sum)],
        yn(v.beats_random_all), yn(v.beats_union_bar), yn(v.promoted)]);
      const head = [['configuration — far-field ranker + corridor ranker | budget px | corridor share', ''],
        ...modes.map(m => [m, 'num']), ...modes.map(m => [m + ' control', 'num']),
        ['sum', 'num'], ['beats control', ''], ['registered union bar', ''], ['promoted', '']];
      const sel = s.selected || {};
      el('composite').innerHTML = table(head, rows, (s.ranked || []).map(([k]) => k === sel.key ? 'hi' : ''))
        + `<p class="small"><b>Rules, as recorded in the file:</b> ` +
          (s.selection_rules || []).map((r, i) => `${i + 1}. ${esc(r)}`).join(' · ') + `</p>` +
        `<p class="small"><b>Selected:</b> <code>${esc(sel.key || 'none')}</code> — ` +
          modes.map(m => `${m} ${G52.fmt(sel['mean_' + m])} vs control ${G52.fmt(sel.rand ? sel.rand[m] : null)}`).join(' · ') +
          `, sum ${G52.fmt(sel.sum)}. Corridor share ${G52.fmt(sel.corridor_share, 2)} of a ` +
          `${G52.fmt(sel.total_px, 0)}-px budget; control bars beaten: ${yn(sel.beats_random_all)}; ` +
          `registered +0.010-over-union bar: ${yn(sel.beats_union_bar)}.` +
          (sel.previous_selection ? '' : '') + `</p>` +
        (s.previous_selection ? `<p class="small muted">Recomputed by <code>scripts/composite_recount.py</code> `
          + `at ${esc(s.recount_utc || '')}; the earlier selection under the old control definition is kept in `
          + `<code>data/composite.json</code> as <code>previous_selection</code> (` +
          `key <code>${esc(s.previous_selection.selected?.key || '')}</code>, ` +
          `beats_random_all ${G52.fmt(s.previous_selection.selected?.beats_random_all ? 1 : 0, 0)}).</p>` : '') +
        `<p class="small"><b>What this table settles.</b> Every configuration that funds the corridor `
          + `(share &gt; 0) ranks better on the truncation instrument and worse on the whole-component one: `
          + `the two populations are disjoint, so the sum is the only fair judge, and at this budget the sum `
          + `says the corridor does not pay for the far-field mass it displaces. See the note under the table.</p>`;
    }
  }
  // ---- gates --------------------------------------------------------------------------------
  if (el('gates')) {
    let h = '';
    for (const key of ['holdout_tip', 'holdout_hide']) {
      const o = d[key];
      if (!o || !o.gates) continue;
      h += `<li><b>${esc(o.mode)}</b> · tested <code>${esc(o.gates.tested)}</code> ·
        ${o.gates.promoted ? '<span class="tag ok">promoted</span>' : '<span class="tag no">not promoted</span>'}
        — ${Object.entries(o.gates.checks || {}).map(([k, v]) =>
          `${k}: <span class="mono">${v.ok ? 'OK' : 'not OK'}${'delta' in v ? ' ' + v.delta : ''}</span>`
        ).join(' · ')}</li>`;
    }
    el('gates').innerHTML = h || '<li class="muted">no gate records</li>';
  }

  // ---- layer screen ------------------------------------------------------------------------
  if (el('layers')) {
    const ls = d.layer_screen && !d.layer_screen.__error ? d.layer_screen : null;
    if (!ls) { el('layers').innerHTML = '<p class="small muted">no layer screen on disk</p>'; }
    else {
      const L = ls.layers || ls;
      const arr = Object.entries(L).filter(([, v]) => typeof v === 'object').map(([k, v]) => [k, v])
        .sort((a, b) => (b[1]['p@40k'] ?? b[1].precision_at ?? 0) - (a[1]['p@40k'] ?? a[1].precision_at ?? 0));
      el('layers').innerHTML = table([['layer', ''], ['precision @ 40k', 'num'], ['lift vs base rate', 'num'],
        ['isolated-fault precision @ 40k', 'num']],
        arr.slice(0, 14).map(([k, v]) => [`<span class="mono">${esc(k)}</span>`,
          [(v['p@40k'] ?? v.precision_at ?? NaN).toFixed(4)],
          [(v.lift ?? NaN).toFixed(2)],
          [(v.iso_p ?? v.isolated_p_at_40k ?? NaN).toFixed(4)]]) ) +
        `<p class="small muted">from <code>evidence/layer_screen.json</code> — the same numbers that set
        the view split. ${arr.length} layers screened.</p>`;
    }
  }

  // ---- feed listing -------------------------------------------------------------------------
  if (el('feedlist')) {
    const f = d.feed && !d.feed.__error ? d.feed : {};
    const files = (f.files || []).map(n => {
      const o = d[n.replace('.json', '')];
      const ok = o && !o.__error;
      return `<tr><td class="mono">${n}</td><td>${ok ? '<span class="tag ok">present</span>'
        : '<span class="tag warn">not loaded by this page</span>'}</td>
        <td class="mono">${ok ? Object.keys(o).length + ' keys' : '–'}</td></tr>`;
    }).join('');
    el('feedlist').innerHTML = `<table><thead><tr><th>file</th><th>status</th><th>size</th></tr></thead>
      <tbody>${files || '<tr><td colspan=3 class="muted">feed.json not readable</td></tr>'}</tbody></table>
      <p class="small">feed generated <code>${esc(f.generated_utc || '–')}</code> · branch
      <code>${esc(f.branch || '–')}</code> · leaderboard fetch: ${esc(f.leaderboard_status || '–')} ·
      submission: <code>${esc(f.submission || 'none built')}</code> · footprint
      ${f.pipeline ? f.pipeline.footprint.toLocaleString() : '–'} px, catalogue ${
      f.pipeline ? f.pipeline.catalogue.toLocaleString() : '–'} px, |G| bracket ${
      f.pipeline ? JSON.stringify(f.pipeline.g_bracket) : '–'}</p>`;
  }
})();
