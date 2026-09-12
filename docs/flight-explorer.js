(() => {
  const q = s => document.querySelector(s);
  const money = v => v == null ? '—' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v));
  const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe = (u='') => { try { const x=new URL(u); return x.protocol==='https:'?x.href:'#'; } catch { return '#'; } };
  const fmtDate = v => { if(!v) return '—'; const [y,m,d]=String(v).split('-').map(Number); return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(y,m-1,d)); };
  const norm = s => String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  const sleep = ms => new Promise(r=>setTimeout(r,ms));
  const clamp = (n,min,max) => Math.max(min,Math.min(max,n));
  const RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/flight-month-search.json';
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
  let activeRequestId = '';
  let cancelRequestedAt = 0;
  let lastProgressSeen = false;
  const tabs = q('#flightTabs');
  const app = q('#flightsApp');
  if (!tabs || !app || q('#flightMonthPanel')) return;

  const style = document.createElement('style');
  style.textContent = `
    body.flight-search-compact .wrap{padding-top:12px}
    body.flight-search-compact header{margin-bottom:5px;align-items:center}
    body.flight-search-compact header h1{font-size:28px;margin:0 0 2px}
    body.flight-search-compact header>.header-actions .pill{padding:6px 9px;font-size:11px}
    body.flight-search-compact header .sub{font-size:12px;line-height:1.25}
    body.flight-search-compact .main-tabs{margin:4px 0 8px;padding-bottom:8px;gap:6px}
    body.flight-search-compact .main-tab{padding:7px 12px;font-size:12px;border-radius:9px}
    body.flight-search-compact #flightsApp>.flight-head{display:none}
    body.flight-search-compact #flightTabs{margin:5px 0 8px;gap:5px}
    body.flight-search-compact #flightTabs .tab{padding:6px 10px;font-size:11px;border-radius:8px}
    .month-shell{margin-top:2px}
    .month-title-row{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:2px 0 7px}
    .month-title-row h3{margin:0;font-size:18px}.month-title-row .sub{font-size:12px;line-height:1.35;max-width:980px}
    .month-search-grid{display:grid;grid-template-columns:1.15fr 1.35fr 1fr .8fr auto;gap:8px;align-items:end;padding:10px 12px}
    .month-search-grid label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;margin:0 0 4px}
    .month-search-grid input,.month-search-grid select{padding:8px 10px;min-height:36px}
    .month-search-btn{border:0;background:var(--accent);color:#07111f;font-weight:900;border-radius:9px;padding:8px 14px;cursor:pointer;min-height:36px;white-space:nowrap}.month-search-btn:disabled{opacity:.6;cursor:wait}.month-search-btn:hover{filter:brightness(1.07)}
    .month-search-status{padding:7px 12px;border-top:1px solid var(--line);color:var(--muted);font-size:11px;line-height:1.4}.month-search-status.wait{color:var(--warn)}.month-search-status.ok{color:var(--ok)}.month-search-status.bad{color:var(--hot)}
    .search-progress{border-top:1px solid var(--line);padding:9px 12px 10px;background:rgba(0,0,0,.08)}
    .progress-top{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px}.progress-stage{font-size:11px;font-weight:800;color:var(--text)}.progress-pct{font-size:12px;font-weight:900;color:var(--accent)}
    .progress-track{height:9px;border-radius:999px;background:var(--panel2);border:1px solid var(--line);overflow:hidden;position:relative}.progress-fill{height:100%;width:0;background:var(--accent);transition:width .35s ease}.progress-fill.indeterminate{width:35%!important;animation:flightProgress 1.15s ease-in-out infinite alternate}
    @keyframes flightProgress{from{transform:translateX(-85%)}to{transform:translateX(270%)}}
    .progress-bottom{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:7px;flex-wrap:wrap}.progress-stats{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:10px}.progress-stats b{color:var(--text);font-size:11px}.stop-search{border:1px solid var(--hot);background:transparent;color:var(--hot);font-weight:900;border-radius:8px;padding:5px 9px;cursor:pointer;font-size:10px}.stop-search:hover{background:rgba(255,104,116,.08)}.stop-search:disabled{opacity:.5;cursor:default}
    #flightMonthPanel>.cards{margin:10px 0;gap:8px}#flightMonthPanel>.cards .card{padding:11px 13px}#flightMonthPanel>.cards .card b{font-size:22px}
    .month-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;padding:9px}.month-day{min-height:59px;border:1px solid var(--line);background:var(--panel2);border-radius:9px;padding:7px}.month-day b{display:block;font-size:10px;color:var(--muted);margin-bottom:4px}.month-day strong{font-size:12px}.month-day.hot{border-color:var(--ok)}.month-day.hot strong{color:var(--ok)}
    .month-result-price{font-size:18px;font-weight:900;white-space:nowrap}.month-rank{font-size:16px;font-weight:900;color:var(--accent)}
    #flightMonthPanel .section-title{margin:10px 0 5px}
    @media(max-width:1100px){.month-search-grid{grid-template-columns:repeat(2,1fr)}.month-search-grid .month-search-action{grid-column:1/-1}.month-search-btn{width:100%}}
    @media(max-width:700px){body.flight-search-compact header .sub{display:none}body.flight-search-compact header h1{font-size:23px}.month-title-row{align-items:flex-start;flex-direction:column}.month-search-grid{grid-template-columns:1fr 1fr}.month-calendar{grid-template-columns:repeat(4,1fr)}.month-search-grid .dest-field{grid-column:1/-1}.progress-bottom{align-items:stretch}.stop-search{width:100%}}
  `;
  document.head.appendChild(style);

  const btn = document.createElement('button');
  btn.className = 'tab'; btn.dataset.flightView = 'monthsearch'; btn.textContent = '🔎 Buscar passagens';
  tabs.insertBefore(btn, tabs.children[1] || null);

  const panel = document.createElement('div');
  panel.id = 'flightMonthPanel'; panel.className='month-shell'; panel.hidden = true;
  panel.innerHTML = `
    <div class="month-title-row"><div><h3>🔎 Buscar passagens</h3><div class="sub">Escolha origem, destino e o mês. A busca só começa ao clicar e testa todas as combinações possíveis de ida e volta dentro do período.</div></div><div class="pill"><span class="dot"></span><span id="monthSearchUpdated">Aguardando busca</span></div></div>
    <section class="panel"><div class="month-search-grid">
      <div><label>Origem</label><select id="monthOrigin"></select></div>
      <div class="dest-field"><label>Destino</label><input id="monthDestination" list="monthDestinations" placeholder="Ex.: Miami ou MIA"><datalist id="monthDestinations"></datalist></div>
      <div><label>Mês a pesquisar</label><input id="monthValue" type="month"></div>
      <div><label>Escalas</label><select id="monthStops"><option value="0">Direto</option><option value="1">Até 1</option><option value="2" selected>Até 2</option></select></div>
      <div class="month-search-action"><button class="month-search-btn" id="monthSearchButton">🔎 Pesquisar agora</button></div>
    </div>
    <div class="search-progress" id="monthProgress" hidden>
      <div class="progress-top"><span class="progress-stage" id="monthProgressStage">Preparando pesquisa…</span><span class="progress-pct" id="monthProgressPct">0%</span></div>
      <div class="progress-track"><div class="progress-fill" id="monthProgressFill"></div></div>
      <div class="progress-bottom"><div class="progress-stats"><span>Verificadas <b id="monthProgressDone">0/0</b></span><span>Faltam <b id="monthProgressLeft">—</b></span><span>Com preço <b id="monthProgressPriced">0</b></span><span>Tempo <b id="monthProgressTime">0s</b></span></div><button class="stop-search" id="monthStopButton">⛔ Parar pesquisa</button></div>
    </div>
    <div class="month-search-status" id="monthSearchStatus">Escolha a rota e o mês. Em um mês de 31 dias são até 465 combinações de ida e volta.</div></section>
    <section class="cards"><div class="card"><span>Menor preço</span><b id="monthLowest">—</b></div><div class="card"><span>Combinações pesquisadas</span><b id="monthCombos">—</b></div><div class="card"><span>Com preço</span><b id="monthPriced">—</b></div><div class="card"><span>Melhores exibidas</span><b id="monthCount">—</b></div></section>
    <section class="panel" id="monthCalendarPanel" hidden><h3 class="section-title" style="padding:0 10px">Menor preço para cada dia de ida</h3><div class="month-calendar" id="monthCalendar"></div></section>
    <section class="panel" style="margin-top:10px"><div class="table-wrap"><table><thead><tr><th>#</th><th>Ida</th><th>Volta</th><th>Dias</th><th>Companhia / escalas</th><th>Preço</th><th>Fonte</th><th></th></tr></thead><tbody id="monthRows"></tbody></table></div><div class="empty" id="monthEmpty"><strong>Faça uma pesquisa.</strong>As melhores combinações aparecerão aqui.</div></section>
    <div class="note"><b>Matriz completa:</b> ida e volta precisam estar dentro do mês selecionado. O resultado mostra as 100 combinações mais baratas. Os preços são dinâmicos e devem ser confirmados antes da emissão.</div>`;
  app.insertBefore(panel, q('#hunterPanel') || null);

  q('#monthOrigin').innerHTML = ORIGINS.map(([c,n])=>`<option value="${c}">${c} · ${esc(n)}</option>`).join('');
  q('#monthDestinations').innerHTML = DESTINATIONS.map(([c,n])=>`<option value="${esc(n)}">${c}</option><option value="${c}">${esc(n)}</option>`).join('');
  const monthInput=q('#monthValue'), now=new Date(), pad=n=>String(n).padStart(2,'0'), monthKey=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}`;
  monthInput.min=monthKey(new Date(now.getFullYear(),now.getMonth(),1)); monthInput.max=monthKey(new Date(now.getFullYear(),now.getMonth()+6,1)); monthInput.value=monthKey(new Date(now.getFullYear(),now.getMonth()+1,1));

  function resolveDestination(raw){
    const value=String(raw||'').trim(); if(/^[a-z]{3}$/i.test(value)) return value.toUpperCase();
    const n=norm(value), exact=DESTINATIONS.find(([c,name])=>norm(name)===n||norm(`${name} (${c})`)===n); if(exact) return exact[0];
    const partial=DESTINATIONS.filter(([c,name])=>norm(name).includes(n)||norm(c)===n); return partial.length===1?partial[0][0]:'';
  }
  function makeRequestId(){
    const raw=(globalThis.crypto&&crypto.randomUUID)?crypto.randomUUID():`${Date.now()}_${Math.random().toString(36).slice(2)}`;
    return raw.replace(/[^A-Za-z0-9_-]/g,'').slice(0,40);
  }
  function formRequest(){return{origin:q('#monthOrigin').value.trim().toUpperCase(),destination:resolveDestination(q('#monthDestination').value),month:q('#monthValue').value,max_stops:Number(q('#monthStops').value||2)}}
  function expectedCombinations(month){
    if(!/^\d{4}-\d{2}$/.test(month)) return 0;
    const [y,m]=month.split('-').map(Number), last=new Date(y,m,0).getDate();
    let first=1; const t=new Date(); if(y===t.getFullYear()&&m===t.getMonth()+1) first=Math.min(last,Math.max(1,t.getDate()+1));
    const usable=Math.max(0,last-first+1); return usable>1?(usable*(usable-1))/2:0;
  }
  function render(){
    const rows=data.results||[],stats=data.stats||{},req=data.request||{};
    q('#monthRows').innerHTML=rows.map((x,i)=>`<tr><td><span class="month-rank">${i+1}</span></td><td><b>${fmtDate(x.departure_date)}</b></td><td><b>${fmtDate(x.return_date)}</b></td><td>${Number(x.trip_days||0)} dias</td><td><b>${esc(x.airline||'Google Flights')}</b><small class="statline">${esc(x.stops||'')} ${x.duration?'· '+esc(x.duration):''}</small></td><td class="month-result-price">${money(x.price)}</td><td><span class="badge official">${esc(x.source_kind==='swoop'?'Swoop':'Google')}</span></td><td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Ver voo</a></td></tr>`).join('');
    q('#monthEmpty').hidden=rows.length>0; q('#monthLowest').textContent=money(stats.lowest_price); q('#monthCombos').textContent=stats.combinations??'—'; q('#monthPriced').textContent=stats.priced_combinations!=null?`${stats.priced_combinations} · ${stats.coverage_pct||0}%`:'—'; q('#monthCount').textContent=rows.length?`${rows.length}/100`:'—';
    if(data.generated_at) q('#monthSearchUpdated').textContent=`Atualizado ${new Date(data.generated_at).toLocaleString('pt-BR')} · ${req.origin||''}→${req.destination||''}`;
    const daily=data.daily_min||[],cal=q('#monthCalendar');
    if(daily.length){const low=Math.min(...daily.map(x=>Number(x.price)||Infinity));cal.innerHTML=daily.map(x=>{const d=Number((x.departure_date||'').slice(-2)),hot=Number(x.price)<=low*1.06?' hot':'';return`<div class="month-day${hot}"><b>Dia ${d}</b><strong>${money(x.price)}</strong><small class="statline">volta ${fmtDate(x.return_date)} · ${Number(x.trip_days||0)} dias</small></div>`}).join('');q('#monthCalendarPanel').hidden=false;} else {cal.innerHTML='';q('#monthCalendarPanel').hidden=true;}
  }
  function clearResultCards(total){
    q('#monthLowest').textContent='—'; q('#monthCombos').textContent=`0/${total||'—'}`; q('#monthPriced').textContent='0'; q('#monthCount').textContent='—';
  }
  function stageLabel(stage,p){
    const labels={queued:'Na fila do servidor',starting:'Preparando ambiente',searching:'Pesquisando combinações',fallback:'Complementando datas sem preço',ranking:'Ordenando os menores preços',publishing:'Publicando resultados',done:'Concluído',canceling:'Cancelando pesquisa',canceled:'Pesquisa cancelada',error:'Erro na pesquisa'};
    let label=labels[stage]||p.message||'Pesquisa em andamento';
    if(stage==='fallback'&&p.fallback_total!=null) label+=` · ${Number(p.fallback_done||0)}/${Number(p.fallback_total||0)} reconsultas`;
    if(p.current_pair) label+=` · ${p.current_pair}`;
    return label;
  }
  function updateProgress(p={},started=Date.now(),expected=0){
    const progress=q('#monthProgress'),fill=q('#monthProgressFill'); progress.hidden=false;
    const hasReal=Number.isFinite(Number(p.percent)); lastProgressSeen=lastProgressSeen||hasReal;
    const pct=hasReal?clamp(Number(p.percent),0,100):0;
    fill.classList.toggle('indeterminate',!hasReal); if(hasReal) fill.style.width=`${pct}%`; else fill.style.width='35%';
    q('#monthProgressPct').textContent=hasReal?`${Math.round(pct)}%`:'…';
    q('#monthProgressStage').textContent=stageLabel(p.stage||p.status,p);
    const total=Number(p.total||expected||0),done=Number(p.completed||p.done||0),left=Math.max(0,total-done),priced=Number(p.priced||0);
    q('#monthProgressDone').textContent=total?`${done}/${total}`:`${done}`; q('#monthProgressLeft').textContent=total?String(left):'—'; q('#monthProgressPriced').textContent=String(priced); q('#monthProgressTime').textContent=`${Math.round((Date.now()-started)/1000)}s`;
    if(total) q('#monthCombos').textContent=`${done}/${total}`; if(priced) q('#monthPriced').textContent=String(priced);
  }
  function jsonp(url,timeout=9000){
    return new Promise((resolve,reject)=>{
      const cb='__flightProgress_'+Date.now()+'_'+Math.random().toString(36).slice(2),script=document.createElement('script'); let done=false;
      const finish=(err,val)=>{if(done)return;done=true;clearTimeout(timer);try{delete window[cb]}catch{};script.remove();err?reject(err):resolve(val)};
      window[cb]=v=>finish(null,v); script.onerror=()=>finish(new Error('progress unavailable')); script.src=url+(url.includes('?')?'&':'?')+'callback='+encodeURIComponent(cb)+'&t='+Date.now(); document.head.appendChild(script);
      const timer=setTimeout(()=>finish(new Error('progress timeout')),timeout);
    });
  }
  async function loadConfig(){try{const r=await fetch('./data/flight-search-config.json?t='+Date.now(),{cache:'no-store'});if(r.ok){const c=await r.json();apiBase=String(c.api_base||'').replace(/\/$/,'')}}catch{}}
  async function loadLastResult(){try{const r=await fetch('./data/flight-month-search.json?t='+Date.now(),{cache:'no-store'});if(r.ok){const old=await r.json();if(old&&old.results)data=old}}catch{}}
  function resultMatches(result,request,requestId,started,previousGeneratedAt){
    if(!result||!result.request) return false; const r=result.request;
    if(r.origin!==request.origin||r.destination!==request.destination||r.month!==request.month||Number(r.max_stops)!==Number(request.max_stops)) return false;
    if(previousGeneratedAt&&result.generated_at===previousGeneratedAt) return false;
    const generated=Date.parse(result.generated_at||''); if(!Number.isFinite(generated)||generated<started-15000) return false;
    return !result.request_id||result.request_id===requestId||!lastProgressSeen;
  }
  async function pollSearch(request,requestId,started,previousGeneratedAt,expected){
    const status=q('#monthSearchStatus'); let loops=0;
    while(loops++<1080){
      await sleep(2500); const elapsed=Math.round((Date.now()-started)/1000); let p=null;
      try{p=await jsonp(`${apiBase}/api/progress/${encodeURIComponent(requestId)}`);if(p&&typeof p==='object'){updateProgress(p,started,expected);if(p.status==='canceled'||p.stage==='canceled'){const e=new Error('Pesquisa cancelada.');e.code='CANCELED';throw e;}if(p.status==='error'||p.stage==='error')throw new Error(p.error||p.message||'A pesquisa terminou com erro.');}}catch(e){if(e&&e.code==='CANCELED')throw e;}
      if(cancelRequestedAt&&Date.now()-cancelRequestedAt>15000&&!lastProgressSeen){const e=new Error('Pesquisa interrompida nesta tela.');e.code='CANCELED_LOCAL';throw e;}
      try{const r=await fetch(`${RESULT_RAW}?t=${Date.now()}`,{cache:'no-store'});if(r.ok){const fresh=await r.json();if(resultMatches(fresh,request,requestId,started,previousGeneratedAt))return fresh;}}catch{}
      if(!p) updateProgress({stage:'searching',message:'Pesquisa em andamento'},started,expected);
      status.className='month-search-status wait'; status.textContent=`🔎 Pesquisa em andamento… ${elapsed}s. A barra acima mostra o estágio e o que ainda falta.`;
    }
    throw new Error('A busca excedeu o tempo máximo de espera.');
  }
  async function dispatchWithoutCors(request){
    await fetch(`${apiBase}/api/search`,{method:'POST',mode:'no-cors',cache:'no-store',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(request)});
  }
  async function cancelSearch(){
    if(!searching||!activeRequestId||cancelRequestedAt) return;
    cancelRequestedAt=Date.now(); const b=q('#monthStopButton'),status=q('#monthSearchStatus'); b.disabled=true;b.textContent='⏳ Cancelando…';
    updateProgress({stage:'canceling',percent:lastProgressSeen?undefined:null},Date.now(),0); status.className='month-search-status wait';status.textContent='⛔ Cancelamento solicitado. Aguardando o servidor interromper a execução…';
    try{await fetch(`${apiBase}/api/cancel`,{method:'POST',mode:'no-cors',cache:'no-store',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify({request_id:activeRequestId})});}catch{}
  }
  async function searchInsidePage(){
    if(searching)return; const request=formRequest(),status=q('#monthSearchStatus'),button=q('#monthSearchButton'),stop=q('#monthStopButton');
    if(!/^[A-Z]{3}$/.test(request.destination)){status.className='month-search-status bad';status.textContent='Escolha uma cidade/aeroporto válido, por exemplo Miami ou MIA.';return;}
    if(!request.month){status.className='month-search-status bad';status.textContent='Escolha o mês que deseja pesquisar.';return;}
    if(!apiBase){status.className='month-search-status bad';status.textContent='O Google Apps Script da pesquisa ainda não foi conectado.';return;}
    searching=true; activeRequestId=makeRequestId(); cancelRequestedAt=0; lastProgressSeen=false; request.request_id=activeRequestId; button.disabled=true;button.textContent='⏳ Pesquisando…';stop.disabled=false;stop.textContent='⛔ Parar pesquisa';
    const started=Date.now(),previousGeneratedAt=data.generated_at||'',expected=expectedCombinations(request.month); clearResultCards(expected); q('#monthProgress').hidden=false; updateProgress({stage:'queued',percent:1,total:expected,completed:0,priced:0},started,expected); status.className='month-search-status wait';status.textContent='🔎 Enviando a pesquisa para o servidor…';
    try{
      await dispatchWithoutCors(request); status.textContent='✅ Pesquisa enviada. Preparando a varredura das combinações…';
      data=await pollSearch(request,activeRequestId,started,previousGeneratedAt,expected); render(); updateProgress({stage:'done',percent:100,total:data.stats?.combinations||expected,completed:data.stats?.combinations||expected,priced:data.stats?.priced_combinations||0},started,expected); stop.disabled=true;
      status.className='month-search-status ok';status.textContent=`✅ Busca concluída em ${Math.round((Date.now()-started)/1000)}s. Foram pesquisadas ${data.stats?.combinations||0} combinações e as menores tarifas estão abaixo.`;
    }catch(e){
      stop.disabled=true;
      if(e&&String(e.code||'').startsWith('CANCELED')){updateProgress({stage:'canceled',percent:lastProgressSeen?undefined:null,total:expected,completed:0,priced:0},started,expected);status.className='month-search-status bad';status.textContent='⛔ Pesquisa parada. Você pode alterar os filtros e iniciar outra busca.';}
      else{status.className='month-search-status bad';status.textContent=`Não foi possível concluir a busca: ${e.message||e}`;}
    }finally{searching=false;activeRequestId='';button.disabled=false;button.textContent='🔎 Pesquisar agora';}
  }

  async function boot(){await Promise.all([loadConfig(),loadLastResult()]);if(!panel.hidden)render();}
  function compact(on){document.body.classList.toggle('flight-search-compact',!!on);}
  function activate(){document.querySelectorAll('#flightTabs .tab').forEach(x=>x.classList.remove('active'));btn.classList.add('active');['hunterPanel','radarPanel','externalPanel','airlinesPanel'].forEach(id=>{const el=q('#'+id);if(el)el.hidden=true;});panel.hidden=false;compact(true);render();}
  q('#monthSearchButton').addEventListener('click',searchInsidePage); q('#monthStopButton').addEventListener('click',cancelSearch); btn.addEventListener('click',activate);
  document.querySelectorAll('#flightTabs .tab').forEach(b=>{if(b!==btn)b.addEventListener('click',()=>{panel.hidden=true;compact(false);});});
  const productsMain=document.querySelector('.main-tab[data-main="products"]');if(productsMain)productsMain.addEventListener('click',()=>{panel.hidden=true;compact(false);});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!searching)loadConfig();}); boot();
})();