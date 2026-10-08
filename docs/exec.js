// Executive-summary render: the download block and the expectation line come from the feed, never
// from text typed into this page.
(async function () {
  await Promise.all(['submission', 'holdout_tip', 'holdout_hide', 'feed'].map(n => G52.load(n)));
  G52.stamp();
  const sub = G52.data.submission || {}, h = G52.data.holdout_tip || {}, hh = G52.data.holdout_hide || {};
  const dl = document.querySelector('.hero .dl, #exec-dl');
  if (sub.exists && sub.file) {
    const nm = sub.file;
    document.querySelectorAll('[data-exec-dl]').forEach(n => {
      n.innerHTML = `<a class="dlbtn" href="${sub.download || 'downloads/' + nm}" download>
        Download <code>${nm}</code><small>${(sub.bytes || 0).toLocaleString()} bytes ·
        ${sub.sha256 ? 'sha256 ' + sub.sha256.slice(0, 16) + '…' : ''}</small></a>`;
    });
    const px = (sub.stats && sub.stats.emitted != null) ? sub.stats.emitted : '?';
    const note = sub.note || `gems52 · metric-aware emission · ${sub.n_segments ?? '?'} segments, `
      + `${px} px · {0,1} mass · no NaN · sha256 `
      + `${sub.sha256 ? sub.sha256.slice(0, 16) : '?'}…`
      + ` · strictly novel against every prior of this family, not their union`;
    document.querySelectorAll('[data-note]').forEach(n => n.innerHTML = `<code>${esc(note)}</code>`);
    const gate = sub.holdout_gates || {};
    document.querySelectorAll('[data-gate-verdict]').forEach(n => {
      const tag = gate.promoted ? '<span class="tag ok">promoted</span>'
                                : '<span class="tag warn">not promoted</span>';
      n.innerHTML = `${tag} control bar on both instruments
        <b>${gate.composite_control_bar ? 'cleared' : 'not cleared'}</b> · registered
        +0.010-over-union bar <b>${gate.registered_union_bar ? 'cleared' : 'not met'}</b>
        (${Object.entries(gate.vs_naive_union || {}).map(([m, v]) => `${m} ${v == null ? '–' : (v >= 0 ? '+' : '') + v.toFixed(4)}`).join(', ')})
        · built with <code>--force</code> = <b>${sub.forced ? 'yes' : 'no'}</b>. ${esc(gate.reason || '')}`;
    });
  }
  const e = document.getElementById('expect');
  if (e) {
    const best = Object.entries(h.summary || {}).sort((a, b) => b[1].mean - a[1].mean)[0];
    const sib = Object.entries(h.summary || {}).filter(([k]) => k.startsWith('sibling:')).sort((a, b) => b[1].mean - a[1].mean)[0];
    const rnd = Object.entries(h.summary || {}).filter(([k]) => k.startsWith('random|')).sort((a, b) => b[1].mean - a[1].mean)[0];
    const mean = o => Object.entries(o || {}).filter(([k]) => k.startsWith('random|'))
      .reduce((m, [, v]) => Math.max(m, v.mean), 0);
    const lift = (o, key) => {
      const b = (o.summary || {})[key], r = mean(o.summary);
      return (b && r) ? (b.mean / r - 1) : null;
    };
    const lt = lift(h, best[0]), lh = (() => {
      const hs = hh.summary || {};
      const bk = Object.keys(hs).sort((a, b) => hs[b].mean - hs[a].mean)[0];
      return lift(hh, bk);
    })();
    const pct = x => x == null ? '–' : `${(x * 100).toFixed(0)} %`;
    e.innerHTML = best ? `On the <b>${esc(h.mode || 'tip')}</b> instrument the shipped arm
      <code>${esc(best[0])}</code> reaches <b>${best[1].mean.toFixed(4)}</b> ± ${best[1].sd.toFixed(4)}
      (fold sd), and on the whole-component instrument <b>${hh.mean_best != null ? hh.mean_best.toFixed(4) : (Object.values(hh.summary || {}).sort((a, b) => b.mean - a.mean)[0] || {}).mean?.toFixed(4) ?? '–'}</b>.
      Against uniform-random emission at the <em>same budget in the same mask</em>, that is a placement lift of
      <b>${pct(lt)}</b> (truncation) and <b>${pct(lh)}</b> (whole-component). Those are recovery numbers on
      hidden catalogue segments — <b>not a forecast of the portal score</b>. What we stake is the mechanism:
      same scale as the group's incumbent file, better-validated placement, no masked overlap. Whether the
      corridor transfers is the open question, and it is why the two bars above are reported before the
      download is used.` : 'no holdout table yet';
  }
})();
