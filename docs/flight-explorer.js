(() => {
  const q = s => document.querySelector(s);
  const money = v => v == null ? '—' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v));
  const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe = (u='') => { try { const x=new URL(u); return x.protocol==='https:'?x.href:'#'; } catch { return '#'; } };
  const fmtDate = v => { if(!v) return '—'; const [y,m,d]=v.split('-').map(Number); return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(y,m-1,d)); };
  const sleep = ms => new Promise(r=>setTimeout(r,ms));
  const norm = s => String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();

  const ORIGINS = [
    ['DOU','Dourados'],['PMG','Ponta Porã'],['JTC','Bauru'],['GRU','Guarulhos'],['CGH','São Paulo / Congonhas'],['VCP','Campinas / Viracopos'],['GIG','Rio de Janeiro / Galeão'],['TJL','Três Lagoas'],['ARU','Araçatuba'],['PPB','Presidente Prudente / Pres. Venceslau'],['MII','Marília']
  ];
  const DESTINATIONS = [
    ['CGR','Campo Grande'],['CGB','Cuiabá'],['BSB','Brasília'],['GYN','Goiânia'],['CWB','Curitiba'],['LDB','Londrina'],['MGF','Maringá'],['IGU','Foz do Iguaçu'],['FLN','Florianópolis'],['NVT','Navegantes'],['POA','Porto Alegre'],['VCP','Campinas'],['CGH','São Paulo / Congonhas'],['GRU','São Paulo / Guarulhos'],['SJP','São José do Rio Preto'],['RAO','Ribeirão Preto'],['UDI','Uberlândia'],['CNF','Belo Horizonte'],['GIG','Rio de Janeiro / Galeão'],['SDU','Rio de Janeiro / Santos Dumont'],['VIX','Vitória'],['SSA','Salvador'],['REC','Recife'],['FOR','Fortaleza'],['NAT','Natal'],['MCZ','Maceió'],['AJU','Aracaju'],['JPA','João Pessoa'],['THE','Teresina'],['SLZ','São Luís'],['BEL','Belém'],['MAO','Manaus'],['PVH','Porto Velho'],['BVB','Boa Vista'],['MCP','Macapá'],['PMW','Palmas'],['JDO','Juazeiro do Norte'],['IOS','Ilhéus'],['BPS','Porto Seguro'],['PNZ','Petrolina'],['RBR','Rio Branco'],['STM','Santarém'],['IMP','Imperatriz'],['MOC','Montes Claros'],['JOI','Joinville'],['XAP','Chapecó'],['PFB','Passo Fundo'],['ROO','Rondonópolis'],['FEN','Fernando de Noronha'],['CAC','Cascavel'],
    ['EZE','Buenos Aires / Ezeiza'],['AEP','Buenos Aires / Aeroparque'],['SCL','Santiago'],['ASU','Assunção'],['MVD','Montevidéu'],['LIM','Lima'],['BOG','Bogotá'],['UIO','Quito'],['GYE','Guayaquil'],['VVI','Santa Cruz de la Sierra'],['PTY','Cidade do Panamá'],['SJO','San José'],['GUA','Cidade da Guatemala'],['MEX','Cidade do México'],['CUN','Cancún'],['PUJ','Punta Cana'],['SDQ','Santo Domingo'],['MIA','Miami'],['FLL','Fort Lauderdale'],['MCO','Orlando'],['JFK','Nova York / JFK'],['EWR','Nova York / Newark'],['BOS','Boston'],['IAD','Washington / Dulles'],['ATL','Atlanta'],['ORD','Chicago'],['DFW','Dallas / Fort Worth'],['IAH','Houston'],['LAX','Los Angeles'],['SFO','San Francisco'],['LAS','Las Vegas'],['YYZ','Toronto'],['YUL','Montreal'],['YVR','Vancouver'],['LIS','Lisboa'],['OPO','Porto'],['MAD','Madri'],['BCN','Barcelona'],['CDG','Paris'],['LHR','Londres / Heathrow'],['FCO','Roma'],['MXP','Milão'],['FRA','Frankfurt'],['AMS','Amsterdã'],['ZRH','Zurique'],['VIE','Viena'],['ATH','Atenas'],['IST','Istambul'],['DXB','Dubai'],['DOH','Doha']
  ];

  let data = {request:{},stats:{},results:[],daily_min:[]};
  let apiBase = '';
  let searching = false;
  const tabs = q('#flightTabs');
  const app = q('#flightsApp');
  if (!tabs || !app || q('#flightMonthPanel')) return;

  const style = document.createElement('style');
  style.textContent = `
    .month-search-grid{display:grid;grid-template-columns:1.2fr 1.5fr 1fr .9fr auto;gap:9px;align-items:end;padding:13px}
    .month-search-grid label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;margin:0 0 5px}
    .month-search-btn{border:0;background:var(--accent);color:#07111f;font-weight:900;border-radius:10px;padding:11px 16px;cursor:pointer;min-height:41px;white-space:nowrap}
    .month-search-btn:hover{filter:brightness(1.07)}.month-search-btn:disabled{opacity:.55;cursor:wait}
    .month-search-status{padding:10px 13px;border-top:1px solid var(--line);color:var(--muted);font-size:12px;line-height:1.5}
    .month-search-status.wait{color:var(--warn)} .month-search-status.ok{color:var(--ok)} .month-search-status.bad{color:var(--hot)}
    .month-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:7px;padding:12px}
    .month-day{min-height:66px;border:1px solid var(--line);background:var(--panel2);border-radius:10px;padding:8px}
    .month-day b{display:block;font-size:11px;color:var(--muted);margin-bottom:5px}.month-day strong{font-size:13px}.month-day.hot{border-color:var(--ok)}.month-day.hot strong{color:var(--ok)}
    .month-result-price{font-size:20px;font-weight:900;white-space:nowrap}.month-rank{font-size:18px;font-weight:900;color:var(--accent)}
    .matrix-example{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:var(--accent)}
    @media(max-width:1100px){.month-search-grid{grid-template-columns:repeat(2,1fr)}.month-search-grid .month-search-action{grid-column:1/-1}.month-search-btn{width:100%}}
    @media(max-width:700px){.month-search-grid{grid-template-columns:1fr}.month-calendar{grid-template-columns:repeat(4,1fr)}}
  `;
  document.head.appendChild(style);

  const btn = document.createElement('button');
  btn.className = 'tab';
  btn.dataset.flightView = 'monthsearch';
  btn.textContent = '📅 Buscar passagem';
  tabs.insertBefore(btn, tabs.children[1] || null);

  const panel = document.createElement('div');
  panel.id = 'flightMonthPanel';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="flight-head">
      <div><h3 class="section-title">📅 Busca completa do mês</h3><div class="sub">Escolha origem, destino e mês. O sistema testa todas as combinações possíveis de ida e volta dentro daquele mês e ordena os menores preços.</div></div>
      <div class="flight-actions"><div class="pill"><span class="dot"></span><span id="monthSearchUpdated">Aguardando busca</span></div></div>
    </div>
    <section class="panel">
      <div class="month-search-grid">
        <div><label>Origem</label><select id="monthOrigin"></select></div>
        <div><label>Destino</label><input id="monthDestination" list="monthDestinations" placeholder="Ex.: Miami ou MIA"><datalist id="monthDestinations"></datalist></div>
        <div><label>Mês</label><input id="monthValue" type="month"></div>
        <div><label>Escalas</label><select id="monthStops"><option value="0">Somente direto</option><option value="1">Até 1 escala</option><option value="2" selected>Até 2 escalas</option></select></div>
        <div class="month-search-action"><button class="month-search-btn" id="monthSearchButton">🔎 Pesquisar mês</button></div>
      </div>
      <div class="month-search-status" id="monthSearchStatus">Exemplo de outubro: <span class="matrix-example">01→02, 01→03, 01→04 … 02→03, 02→04 … 30→31</span>. Em um mês de 31 dias são 465 combinações.</div>
    </section>
    <section class="cards">
      <div class="card"><span>Menor preço</span><b id="monthLowest">—</b></div>
      <div class="card"><span>Combinações consultadas</span><b id="monthCombos">—</b></div>
      <div class="card"><span>Com preço</span><b id="monthPriced">—</b></div>
      <div class="card"><span>Melhores exibidas</span><b id="monthCount">—</b></div>
    </section>
    <section class="panel" id="monthCalendarPanel" hidden><h3 class="section-title" style="padding:0 12px">Menor preço para cada dia de ida</h3><div class="month-calendar" id="monthCalendar"></div></section>
    <section class="panel" style="margin-top:14px"><div class="table-wrap"><table><thead><tr><th>#</th><th>Ida</th><th>Volta</th><th>Dias</th><th>Companhia / escalas</th><th>Preço</th><th>Fonte</th><th></th></tr></thead><tbody id="monthRows"></tbody></table></div><div class="empty" id="monthEmpty"><strong>Faça uma pesquisa.</strong>As melhores combinações do mês aparecerão aqui.</div></section>
    <div class="note"><b>Matriz completa:</b> ida e volta precisam estar dentro do mês selecionado. O resultado mostra as 100 combinações mais baratas entre todas as datas pesquisadas. Os preços são dinâmicos e devem ser confirmados antes da emissão.</div>
  `;
  const firstPanel = q('#hunterPanel');
  app.insertBefore(panel, firstPanel || null);

  q('#monthOrigin').innerHTML = ORIGINS.map(([c,n])=>`<option value="${c}">${c} · ${esc(n)}</option>`).join('');
  q('#monthDestinations').innerHTML = DESTINATIONS.map(([c,n])=>`<option value="${esc(n)}">${c}</option><option value="${c}">${esc(n)}</option>`).join('');

  const monthInput = q('#monthValue');
  const now = new Date();
  const pad = n => String(n).padStart(2,'0');
  const monthKey = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}`;
  const minMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const maxMonth = new Date(now.getFullYear(), now.getMonth()+6, 1);
  monthInput.min = monthKey(minMonth); monthInput.max = monthKey(maxMonth);
  monthInput.value = monthKey(new Date(now.getFullYear(), now.getMonth()+1, 1));

  function resolveDestination(raw){
    const value = String(raw||'').trim();
    if(/^[a-z]{3}$/i.test(value)) return value.toUpperCase();
    const n = norm(value);
    const exact = DESTINATIONS.find(([c,name])=>norm(name)===n || norm(`${name} (${c})`)===n);
    if(exact) return exact[0];
    const partial = DESTINATIONS.filter(([c,name])=>norm(name).includes(n) || norm(c)===n);
    return partial.length===1 ? partial[0][0] : '';
  }

  function formRequest(){
    return {
      origin:q('#monthOrigin').value.trim().toUpperCase(),
      destination:resolveDestination(q('#monthDestination').value),
      month:q('#monthValue').value,
      max_stops:Number(q('#monthStops').value||2)
    };
  }

  function render(){
    const rows = data.results || [];
    const stats = data.stats || {};
    const req = data.request || {};
    q('#monthRows').innerHTML = rows.map((x,i)=>`<tr>
      <td><span class="month-rank">${i+1}</span></td>
      <td><b>${fmtDate(x.departure_date)}</b></td>
      <td><b>${fmtDate(x.return_date)}</b></td>
      <td>${Number(x.trip_days||0)} dias</td>
      <td><b>${esc(x.airline||'Google Flights')}</b><small class="statline">${esc(x.stops||'')} ${x.duration?'· '+esc(x.duration):''}</small></td>
      <td class="month-result-price">${money(x.price)}</td>
      <td><span class="badge official">${esc(x.source_kind==='swoop'?'Swoop':'Google')}</span></td>
      <td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Ver voo</a></td></tr>`).join('');
    q('#monthEmpty').hidden = rows.length>0;
    q('#monthLowest').textContent = money(stats.lowest_price);
    q('#monthCombos').textContent = stats.combinations ?? '—';
    q('#monthPriced').textContent = stats.priced_combinations != null ? `${stats.priced_combinations} · ${stats.coverage_pct||0}%` : '—';
    q('#monthCount').textContent = rows.length ? `${rows.length}/100` : '—';
    if(data.generated_at) q('#monthSearchUpdated').textContent = `Atualizado ${new Date(data.generated_at).toLocaleString('pt-BR')} · ${req.origin||''}→${req.destination||''}`;

    const daily = data.daily_min || [];
    const cal = q('#monthCalendar');
    if(daily.length){
      const low = Math.min(...daily.map(x=>Number(x.price)||Infinity));
      cal.innerHTML = daily.map(x=>{const d=Number((x.departure_date||'').slice(-2));const hot=Number(x.price)<=low*1.06?' hot':'';return `<div class="month-day${hot}"><b>Dia ${d}</b><strong>${money(x.price)}</strong><small class="statline">volta ${fmtDate(x.return_date)} · ${Number(x.trip_days||0)} dias</small></div>`}).join('');
      q('#monthCalendarPanel').hidden=false;
    } else { cal.innerHTML=''; q('#monthCalendarPanel').hidden=true; }
  }

  async function loadConfig(){
    try{
      const r=await fetch('./data/flight-search-config.json?t='+Date.now(),{cache:'no-store'});
      if(r.ok){const c=await r.json();apiBase=String(c.api_base||'').replace(/\/$/,'');}
    }catch{}
  }

  async function loadLastResult(){
    try{const r=await fetch('./data/flight-month-search.json?t='+Date.now(),{cache:'no-store'});if(r.ok){const old=await r.json();if(old&&old.results)data=old;}}
    catch{}
  }

  async function pollJob(jobId, started){
    const status=q('#monthSearchStatus');
    for(let i=0;i<600;i++){
      await sleep(2500);
      let r;
      try{r=await fetch(`${apiBase}/api/search/${encodeURIComponent(jobId)}`,{cache:'no-store'});}catch(e){throw new Error('Não foi possível consultar o servidor de busca.');}
      if(!r.ok) throw new Error(`Servidor respondeu ${r.status}.`);
      const j=await r.json();
      const elapsed=Math.round((Date.now()-started)/1000);
      if(j.status==='done') return j.result;
      if(j.status==='error') throw new Error(j.error||'A pesquisa falhou.');
      status.className='month-search-status wait';
      status.textContent=`🔎 Pesquisando todas as combinações do mês… ${elapsed}s. Você pode permanecer nesta página.`;
    }
    throw new Error('A busca excedeu o tempo máximo de espera.');
  }

  async function searchInsidePage(){
    if(searching) return;
    const request=formRequest();
    const status=q('#monthSearchStatus');
    const button=q('#monthSearchButton');
    if(!/^[A-Z]{3}$/.test(request.destination)){
      status.className='month-search-status bad';status.textContent='Escolha uma cidade/aeroporto válido, por exemplo Miami ou MIA.';return;
    }
    if(!request.month){status.className='month-search-status bad';status.textContent='Escolha o mês da viagem.';return;}
    if(!apiBase){
      status.className='month-search-status bad';
      status.textContent='O motor de busca interna ainda não está conectado ao servidor. O botão não abrirá mais o GitHub; falta apenas ativar o backend da pesquisa.';
      return;
    }
    searching=true;button.disabled=true;button.textContent='⏳ Pesquisando…';
    status.className='month-search-status wait';
    status.textContent='🔎 Iniciando a matriz completa do mês…';
    const started=Date.now();
    try{
      const r=await fetch(`${apiBase}/api/search`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
      if(!r.ok){const t=await r.text();throw new Error(t||`Servidor respondeu ${r.status}.`);}
      const first=await r.json();
      data=await pollJob(first.job_id,started);
      render();
      status.className='month-search-status ok';
      status.textContent=`✅ Busca concluída em ${Math.round((Date.now()-started)/1000)}s. Foram consultadas ${data.stats?.combinations||0} combinações e as menores tarifas estão abaixo.`;
    }catch(e){status.className='month-search-status bad';status.textContent=`Não foi possível concluir a busca: ${e.message||e}`;}
    finally{searching=false;button.disabled=false;button.textContent='🔎 Pesquisar mês';}
  }

  async function boot(){
    await Promise.all([loadConfig(),loadLastResult()]);
    if(!panel.hidden) render();
  }

  function activate(){
    document.querySelectorAll('#flightTabs .tab').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    ['hunterPanel','radarPanel','externalPanel','airlinesPanel'].forEach(id=>{const el=q('#'+id);if(el)el.hidden=true});
    panel.hidden=false;render();
  }

  q('#monthSearchButton').addEventListener('click',searchInsidePage);
  btn.addEventListener('click',activate);
  document.querySelectorAll('#flightTabs .tab').forEach(b=>{if(b!==btn)b.addEventListener('click',()=>{panel.hidden=true})});
  const productsMain=document.querySelector('.main-tab[data-main="products"]');
  if(productsMain)productsMain.addEventListener('click',()=>{panel.hidden=true});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!searching)loadConfig()});
  boot();
})();
