(() => {
  const q = (s) => document.querySelector(s);
  const money = (v) => v == null ? '—' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v));
  const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe = (u='') => { try { const x=new URL(u); return x.protocol==='https:'?x.href:'#'; } catch { return '#'; } };
  const fmtDate = (v) => { if(!v) return '—'; const [y,m,d]=v.split('-').map(Number); return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(y,m-1,d)); };
  let data = {origins:[],results:[],coverage:{}};

  const tabs = q('#flightTabs');
  const app = q('#flightsApp');
  if (!tabs || !app || q('#flightExplorerPanel')) return;

  const style = document.createElement('style');
  style.textContent = `
    .explorer-filters{grid-template-columns:1.15fr 1.15fr 1fr 1fr 1.45fr 1fr 1fr}
    .explorer-rank{font-size:20px;font-weight:900;color:var(--accent);min-width:44px}
    .explorer-price{font-size:21px;font-weight:900;white-space:nowrap}
    .explorer-scope{font-size:10px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.07em}
    .explorer-progress{height:7px;background:var(--panel2);border:1px solid var(--line);border-radius:999px;overflow:hidden;margin-top:8px}
    .explorer-progress i{display:block;height:100%;background:var(--accent);width:0}
    .explorer-hint{color:var(--muted);font-size:11px;line-height:1.5;margin-top:5px}
    @media(max-width:1100px){.explorer-filters{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:700px){.explorer-filters{grid-template-columns:1fr 1fr}.explorer-filters #explorerQuery{grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const btn = document.createElement('button');
  btn.className = 'tab';
  btn.dataset.flightView = 'explorer100';
  btn.textContent = '🔎 100 destinos';
  tabs.insertBefore(btn, tabs.children[1] || null);

  const panel = document.createElement('div');
  panel.id = 'flightExplorerPanel';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="flight-head">
      <div><h3 class="section-title">🔎 Busca flexível · 100 menores opções</h3>
      <div class="sub">Selecione uma cidade de origem e escolha Brasil ou Internacional. O sistema procura as menores tarifas encontradas em janelas distribuídas pelos próximos 6 meses.</div></div>
      <div class="flight-actions">
        <div class="pill"><span class="dot"></span><span id="explorerUpdated">Aguardando primeira busca</span></div>
        <a class="manual-btn" href="https://github.com/thenights20/viagens/actions/workflows/flight-explorer.yml" target="_blank" rel="noopener">🔎 Buscar agora</a>
      </div>
    </div>
    <section class="cards">
      <div class="card"><span>Opções exibidas</span><b id="explorerCount">—</b></div>
      <div class="card"><span>Destinos únicos</span><b id="explorerUnique">—</b></div>
      <div class="card"><span>Horizonte</span><b id="explorerHorizon">6 meses</b></div>
      <div class="card"><span>Catálogo pesquisado</span><b id="explorerCatalog">100</b></div>
    </section>
    <section class="panel filters explorer-filters">
      <select id="explorerOrigin"><option value="">Selecione a origem</option></select>
      <select id="explorerScope"><option value="domestic">🇧🇷 Destinos nacionais</option><option value="international">🌎 Destinos internacionais</option><option value="">Nacionais + internacionais</option></select>
      <select id="explorerMode"><option value="options">100 menores opções</option><option value="unique">Menor preço por destino</option></select>
      <input id="explorerMaxPrice" type="number" min="0" step="100" placeholder="Preço máx. R$">
      <input id="explorerQuery" placeholder="Destino, país ou aeroporto…">
      <select id="explorerStops"><option value="">Qualquer escala</option><option value="0">Somente direto</option><option value="1">Até 1 escala</option><option value="2">Até 2 escalas</option></select>
      <select id="explorerSort"><option value="price">Menor preço</option><option value="date">Data mais próxima</option><option value="destination">Destino A–Z</option></select>
    </section>
    <section class="panel">
      <div class="table-wrap"><table><thead><tr><th>#</th><th>Destino</th><th>Datas</th><th>Companhia / escalas</th><th>Preço encontrado</th><th>Fonte</th><th></th></tr></thead><tbody id="explorerRows"></tbody></table></div>
      <div class="empty" id="explorerEmpty"><strong>Selecione uma cidade de origem.</strong>Depois escolha Nacional ou Internacional para ver as opções mais baratas.</div>
    </section>
    <div class="note" id="explorerNote"><b>Como funciona:</b> a busca percorre 100 destinos e seis janelas de datas entre aproximadamente 3 semanas e 5,5 meses. O painel mostra até 100 combinações de destino + datas, sempre ordenadas pelo menor preço encontrado. A tarifa é dinâmica e precisa ser confirmada antes da emissão.</div>
  `;
  const firstPanel = q('#hunterPanel');
  app.insertBefore(panel, firstPanel || null);

  function fillOrigins() {
    const el = q('#explorerOrigin');
    const current = el.value;
    el.innerHTML = '<option value="">Selecione a origem</option>' + (data.origins||[]).map(x=>`<option value="${esc(x.code)}">${esc(x.code+' · '+x.name)}</option>`).join('');
    if ([...el.options].some(o=>o.value===current)) el.value=current;
    else {
      const withData = (data.origins||[]).find(o => {
        const c=data.coverage?.[o.code];
        return Number(c?.domestic?.options||0)+Number(c?.international?.options||0)>0;
      });
      if (withData) el.value=withData.code;
    }
  }

  function rowsFiltered() {
    const origin=q('#explorerOrigin').value;
    const scope=q('#explorerScope').value;
    const mode=q('#explorerMode').value;
    const max=Number(q('#explorerMaxPrice').value||0);
    const term=q('#explorerQuery').value.trim().toLowerCase();
    const stops=q('#explorerStops').value;
    let rows=[...(data.results||[])].filter(x=>{
      const hay=[x.destination,x.destination_name,x.destination_country,x.airline].join(' ').toLowerCase();
      return origin && x.origin===origin && (!scope||x.scope===scope) && (!max||Number(x.price)<=max) && (!term||hay.includes(term)) && (stops===''||Number(x.stops_count||0)<=Number(stops));
    });
    if(mode==='unique'){
      const best=new Map();
      for(const x of rows){const k=x.destination,cur=best.get(k);if(!cur||Number(x.price)<Number(cur.price))best.set(k,x)}
      rows=[...best.values()];
    }
    const sort=q('#explorerSort').value;
    rows.sort((a,b)=>sort==='date'?String(a.departure_date).localeCompare(String(b.departure_date))||Number(a.price)-Number(b.price):sort==='destination'?String(a.destination_name||a.destination).localeCompare(String(b.destination_name||b.destination),'pt-BR')||Number(a.price)-Number(b.price):Number(a.price)-Number(b.price));
    return rows.slice(0,100);
  }

  function render() {
    const origin=q('#explorerOrigin').value;
    const scope=q('#explorerScope').value;
    const rows=rowsFiltered();
    const tb=q('#explorerRows'); tb.innerHTML='';
    const empty=q('#explorerEmpty');
    if(!origin){empty.hidden=false;empty.innerHTML='<strong>Selecione uma cidade de origem.</strong>Depois escolha Nacional ou Internacional para ver as opções mais baratas.';}
    else if(!rows.length){empty.hidden=false;empty.innerHTML='<strong>Ainda não há tarifa nesta combinação.</strong>A busca está percorrendo as seis janelas dos próximos 6 meses; use “Buscar agora” para antecipar uma nova rodada.';}
    else empty.hidden=true;
    rows.forEach((x,i)=>{
      const tr=document.createElement('tr');
      const scopeLabel=x.scope==='domestic'?'Brasil':'Internacional';
      tr.innerHTML=`
        <td><span class="explorer-rank">${i+1}</span></td>
        <td class="route"><b>${esc(x.destination_name||x.destination)} <small>(${esc(x.destination)})</small></b><small>${esc(x.destination_country||'')} · <span class="explorer-scope">${scopeLabel}</span></small></td>
        <td class="date-stack"><b>${fmtDate(x.departure_date)} → ${fmtDate(x.return_date)}</b><small>${Number(x.trip_days||0)} dias · em ${Number(x.days_ahead||0)} dias</small></td>
        <td><b>${esc(x.airline||'Google Flights')}</b><small class="ref">${esc(x.stops||'')} ${x.duration?'· '+esc(x.duration):''}</small></td>
        <td class="explorer-price">${money(x.price)}</td>
        <td><span class="badge ${x.source_kind==='swoop-deals'?'deal':'official'}">${esc(x.source_kind==='swoop-deals'?'Data flexível':'Busca dirigida')}</span><br><small class="ref">${esc(x.provider||'')}</small></td>
        <td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Ver voo</a></td>`;
      tb.appendChild(tr);
    });
    q('#explorerCount').textContent=rows.length+'/100';
    q('#explorerUnique').textContent=new Set(rows.map(x=>x.destination)).size;
    q('#explorerCatalog').textContent=data.catalog_count??100;
    const c=data.coverage?.[origin];
    const picked=scope?c?.[scope]:null;
    const detail=picked?` · ${picked.options||0}/100 opções disponíveis · ${picked.unique_destinations||0} destinos únicos`:'';
    q('#explorerNote').innerHTML=`<b>Como funciona:</b> a busca percorre ${data.catalog_count||100} destinos e seis janelas distribuídas pelos próximos ${data.horizon_days||183} dias. O painel mostra até 100 combinações de destino + datas, sempre ordenadas pelo menor preço encontrado${detail}. A tarifa é dinâmica e precisa ser confirmada antes da emissão.`;
  }

  function metrics() {
    q('#explorerHorizon').textContent=Math.round(Number(data.horizon_days||183)/30)+' meses';
    q('#explorerCatalog').textContent=data.catalog_count??100;
    const stamp=data.generated_at?new Date(data.generated_at).toLocaleString('pt-BR'):'aguardando primeira busca';
    const scan=data.scan||{};
    q('#explorerUpdated').textContent=data.generated_at?`Atualizado ${stamp}${scan.origin?' · última: '+scan.origin:''}`:stamp;
    fillOrigins();
  }

  async function boot() {
    try { const r=await fetch('./data/flight-explorer.json?t='+Date.now(),{cache:'no-store'}); data=await r.json(); }
    catch { data={origins:[],results:[],coverage:{}}; }
    metrics();
    if(!panel.hidden) render();
  }

  function activate(){
    document.querySelectorAll('#flightTabs .tab').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    ['hunterPanel','radarPanel','externalPanel','airlinesPanel'].forEach(id=>{const el=q('#'+id);if(el)el.hidden=true});
    panel.hidden=false;
    render();
  }

  btn.addEventListener('click',activate);
  document.querySelectorAll('#flightTabs .tab').forEach(b=>{if(b!==btn)b.addEventListener('click',()=>{panel.hidden=true})});
  ['explorerOrigin','explorerScope','explorerMode','explorerMaxPrice','explorerQuery','explorerStops','explorerSort'].forEach(id=>q('#'+id).addEventListener('input',render));
  const productsMain=document.querySelector('.main-tab[data-main="products"]');
  if(productsMain)productsMain.addEventListener('click',()=>{panel.hidden=true});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)boot()});
  boot();
  setInterval(boot,90000);
})();
