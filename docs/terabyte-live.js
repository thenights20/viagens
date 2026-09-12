(() => {
  const q = (s) => document.querySelector(s);
  const moneyT = (v) => v == null ? '—' : new Intl.NumberFormat('pt-BR', {style:'currency',currency:'BRL'}).format(Number(v));
  const escT = (s='') => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const safeT = (u='') => { try { const x = new URL(u); return x.protocol === 'https:' ? x.href : '#'; } catch { return '#'; } };
  let teraData = {deals:[], page_health:[]};

  const style = document.createElement('style');
  style.textContent = `
    .tera-head{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin:5px 0 2px}
    .tera-head h2{margin:0;font-size:22px}.tera-live{color:var(--hot);font-weight:900}
    .tera-filters{grid-template-columns:2fr 1fr 1fr 1.25fr}
    .tera-move{font-weight:900}.tera-move.hot{color:var(--hot)}.tera-move.good{color:var(--ok)}
    .tera-reasons{max-width:340px;color:var(--muted);font-size:11px;line-height:1.45}
    .tera-reasons b{color:var(--text)}.tera-health{margin-top:10px}
    @media(max-width:1100px){.tera-filters{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:700px){.tera-filters{grid-template-columns:1fr}.tera-filters input{grid-column:auto}}
  `;
  document.head.appendChild(style);

  const tabs = q('#productTabs');
  const productsApp = q('#productsApp');
  if (!tabs || !productsApp || q('#terabytePanel')) return;

  const btn = document.createElement('button');
  btn.className = 'tab';
  btn.dataset.view = 'terabyte';
  btn.textContent = '⚡ Terabyte Live';
  tabs.insertBefore(btn, tabs.children[1] || null);

  const panel = document.createElement('div');
  panel.id = 'terabytePanel';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="tera-head">
      <div><h2>⚡ Terabyte Live <span class="tera-live">5 MIN</span></h2>
      <div class="sub">Radar dedicado à TerabyteShop: vitrines quentes em toda rodada, histórico de preço do SKU e catálogo em rotação.</div></div>
      <div class="flight-actions">
        <div class="pill"><span class="dot"></span><span id="teraUpdated">Aguardando primeira varredura</span></div>
        <a class="manual-btn" href="https://github.com/thenights20/viagens/actions/workflows/terabyte-live.yml" target="_blank" rel="noopener">⚡ Rodar agora</a>
      </div>
    </div>
    <section class="cards">
      <div class="card"><span>Observados nesta rodada</span><b id="teraObserved">—</b></div>
      <div class="card"><span>Produtos no histórico</span><b id="teraTracked">—</b></div>
      <div class="card"><span>Alertas 70+</span><b id="teraStrong">—</b></div>
      <div class="card"><span>Quedas ≥ 15%</span><b id="teraDrops">—</b></div>
    </section>
    <section class="panel filters tera-filters">
      <input id="teraQuery" placeholder="Produto, RTX, Ryzen, SSD, monitor…">
      <select id="teraMinScore"><option value="0">Todos os sinais</option><option value="55" selected>55+ abaixo do normal</option><option value="70">70+ alerta forte</option><option value="80">80+ queda forte</option><option value="90">90+ crítico</option></select>
      <input id="teraMaxPrice" type="number" min="0" step="50" placeholder="Preço máx. R$">
      <select id="teraArea"><option value="">Todas as vitrines</option></select>
    </section>
    <section class="panel">
      <div class="table-wrap"><table><thead><tr><th>Produto</th><th>Preço atual</th><th>Anterior / histórico</th><th>Movimento</th><th>Vitrine</th><th>Score</th><th></th></tr></thead><tbody id="teraRows"></tbody></table></div>
      <div class="empty" id="teraEmpty" hidden><strong>Nenhuma queda anormal neste filtro.</strong>O radar continua acumulando histórico a cada rodada.</div>
    </section>
    <div class="source-row tera-health" id="teraHealth"></div>
    <div class="note"><b>Modo Live:</b> Home, Promoções, Open Box, Hardware, PC Gamer e Kit Upgrade são revisitados em toda execução. As demais categorias e os produtos do sitemap entram em rotação. Um preço ganha prioridade quando cai de uma rodada para outra ou fica muito abaixo da própria mediana histórica. GitHub Actions agenda a cada 5 minutos, mas o início pode sofrer alguns minutos de atraso quando os runners do GitHub estão congestionados.</div>
  `;
  const firstExistingPanel = q('#productBugPanel');
  productsApp.insertBefore(panel, firstExistingPanel || null);

  const productPanelIds = ['productBugPanel','productCouponPanel','productSensorPanel','productsPanel','watchPanel','filters'];

  function hideOthers() {
    productPanelIds.forEach(id => { const el = q('#'+id); if (el) el.hidden = true; });
  }

  function fillAreas() {
    const el = q('#teraArea');
    const current = el.value;
    const vals = [...new Set((teraData.deals||[]).map(x => x.page).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'pt-BR'));
    el.innerHTML = '<option value="">Todas as vitrines</option>' + vals.map(v => `<option value="${escT(v)}">${escT(v)}</option>`).join('');
    if ([...el.options].some(o => o.value === current)) el.value = current;
  }

  function filtered() {
    const term = q('#teraQuery').value.trim().toLowerCase();
    const min = Number(q('#teraMinScore').value || 0);
    const max = Number(q('#teraMaxPrice').value || 0);
    const area = q('#teraArea').value;
    return [...(teraData.deals||[])].filter(x => {
      const hay = [x.title,x.category,x.category_rule,x.page].join(' ').toLowerCase();
      return (!term || hay.includes(term)) && Number(x.score||0) >= min && (!max || Number(x.price||0) <= max) && (!area || x.page === area);
    }).sort((a,b)=>(Number(b.score||0)-Number(a.score||0))||(Number(b.sudden_drop_pct||0)-Number(a.sudden_drop_pct||0))||(Number(a.price||0)-Number(b.price||0)));
  }

  function render() {
    const rows = filtered();
    const tb = q('#teraRows');
    tb.innerHTML = '';
    q('#teraEmpty').hidden = rows.length > 0;
    for (const x of rows) {
      const score = Number(x.score||0);
      const sudden = Number(x.sudden_drop_pct||0);
      const hist = Number(x.history_drop_pct||0);
      const advertised = Number(x.advertised_drop_pct||0);
      const move = sudden > 0 ? `-${sudden.toFixed(0)}% em 5 min` : hist > 0 ? `-${hist.toFixed(0)}% vs. histórico` : advertised > 0 ? `-${advertised.toFixed(0)}% anunciado` : 'observado';
      const reasons = (x.reasons||[]).slice(0,3);
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="prod"><b>${escT(x.title||'Produto')}</b><small>${escT(x.category||x.category_rule||'TerabyteShop')}</small></td>
        <td class="hunter-price">${moneyT(x.price)}<span class="statline">menor visto ${moneyT(x.lowest_seen)}</span></td>
        <td class="ref">${x.previous_price?`Anterior ${moneyT(x.previous_price)}<br>`:''}<small>Mediana ${moneyT(x.baseline_price)} · ${Number(x.history_count||0)} amostras</small></td>
        <td><span class="tera-move ${sudden>=15?'hot':hist>=10?'good':''}">${escT(move)}</span><div class="tera-reasons">${reasons.map((r,i)=>`${i===0?'<b>':''}${escT(r)}${i===0?'</b>':''}`).join('<br>')}</div></td>
        <td><span class="badge official">${escT(x.page||'Terabyte')}</span></td>
        <td><span class="score ${score>=80?'high':score>=60?'good':''}">${score}</span><br><span class="badge ${score>=90?'super':score>=80?'hot':score>=70?'deal':'strict'}">${escT(x.status||'')}</span></td>
        <td><a class="btn" href="${safeT(x.url)}" target="_blank" rel="noopener">Abrir</a></td>`;
      tb.appendChild(tr);
    }
  }

  function metrics() {
    q('#teraObserved').textContent = teraData.observed_this_run ?? 0;
    q('#teraTracked').textContent = teraData.tracked_products ?? 0;
    q('#teraStrong').textContent = teraData.strong_count ?? 0;
    q('#teraDrops').textContent = teraData.sudden_drop_count ?? 0;
    q('#teraUpdated').textContent = teraData.generated_at ? 'Atualizado ' + new Date(teraData.generated_at).toLocaleString('pt-BR') : 'Aguardando primeira varredura';
    fillAreas();
    const box = q('#teraHealth');
    box.innerHTML = '';
    for (const h of (teraData.page_health||[])) {
      const e = document.createElement('span');
      e.className = 'source-pill ' + (h.ok ? 'ok' : 'bad');
      e.textContent = `${h.ok?'●':'○'} ${h.label||'Página'}: ${h.items||0}`;
      if (h.message) e.title = h.message;
      box.appendChild(e);
    }
    const coverage = document.createElement('span');
    coverage.className = 'source-pill';
    coverage.textContent = `Catálogo: ${teraData.catalog_cursor||0}/${teraData.catalog_total||0}`;
    box.appendChild(coverage);
  }

  async function boot() {
    try {
      const r = await fetch('./data/terabyte-live.json?t='+Date.now(), {cache:'no-store'});
      teraData = await r.json();
    } catch {
      teraData = {deals:[],page_health:[]};
    }
    metrics();
    if (!panel.hidden) render();
  }

  function activate() {
    document.querySelectorAll('#productTabs .tab').forEach(x => x.classList.remove('active'));
    btn.classList.add('active');
    hideOthers();
    panel.hidden = false;
    render();
  }

  btn.addEventListener('click', activate);
  document.querySelectorAll('#productTabs .tab').forEach(b => {
    if (b !== btn) b.addEventListener('click', () => { panel.hidden = true; });
  });
  ['teraQuery','teraMinScore','teraMaxPrice','teraArea'].forEach(id => q('#'+id).addEventListener('input', render));

  const productMain = document.querySelector('.main-tab[data-main="products"]');
  if (productMain) productMain.addEventListener('click', () => setTimeout(() => { if (btn.classList.contains('active')) activate(); }, 0));
  const flightMain = document.querySelector('.main-tab[data-main="flights"]');
  if (flightMain) flightMain.addEventListener('click', () => { panel.hidden = true; });

  document.addEventListener('visibilitychange', () => { if (!document.hidden) boot(); });
  boot();
  setInterval(boot, 60000);
})();

(() => {
  if (document.querySelector('script[data-flight-explorer]')) return;

  const loadExplorer = () => {
    if (document.querySelector('script[data-flight-explorer]')) return;
    const s = document.createElement('script');
    s.src = './flight-explorer.js?v=20260912-5';
    s.defer = true;
    s.dataset.flightExplorer = '1';
    document.head.appendChild(s);
  };

  loadExplorer();
})();
