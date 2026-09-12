(() => {
  const q = s => document.querySelector(s);
  const money = v => v == null ? '—' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v));
  const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe = (u='') => { try { const x=new URL(u); return x.protocol==='https:'?x.href:'#'; } catch { return '#'; } };
  const fmtDate = v => { if(!v) return '—'; const [y,m,d]=v.split('-').map(Number); return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(y,m-1,d)); };
  const norm = s => String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  const sleep = ms => new Promise(r=>setTimeout(r,ms));
  const RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/flight-month-search.json';
  const ACTIONS_RUNS = 'https://api.github.com/repos/thenights20/viagens/actions/workflows/flight-month-search.yml/runs?event=workflow_dispatch&per_page=15';
  const ACTIONS_RUN = id => `https://api.github.com/repos/thenights20/viagens/actions/runs/${id}/jobs?per_page=10`;

  const ORIGINS = [
    ['DOU','Dourados'],['PMG','Ponta Porã'],['JTC','Bauru'],['GRU','Guarulhos'],['CGH','São Paulo / Congonhas'],['VCP','Campinas / Viracopos'],['GIG','Rio de Janeiro / Galeão'],['TJL','Três Lagoas'],['ARU','Araçatuba'],['PPB','Presidente Prudente / Pres. Venceslau'],['MII','Marília']
  ];
  const REGIONAL = new Set(['DOU','PMG','JTC','TJL','ARU','PPB','MII']);
  const DESTINATIONS = [
    ['CGR','Campo Grande'],['CGB','Cuiabá'],['BSB','Brasília'],['GYN','Goiânia'],['CWB','Curitiba'],['LDB','Londrina'],['MGF','Maringá'],['IGU','Foz do Iguaçu'],['FLN','Florianópolis'],['NVT','Navegantes'],['POA','Porto Alegre'],['VCP','Campinas'],['CGH','São Paulo / Congonhas'],['GRU','São Paulo / Guarulhos'],['SJP','São José do Rio Preto'],['RAO','Ribeirão Preto'],['UDI','Uberlândia'],['CNF','Belo Horizonte'],['GIG','Rio de Janeiro / Galeão'],['SDU','Rio de Janeiro / Santos Dumont'],['VIX','Vitória'],['SSA','Salvador'],['REC','Recife'],['FOR','Fortaleza'],['NAT','Natal'],['MCZ','Maceió'],['AJU','Aracaju'],['JPA','João Pessoa'],['THE','Teresina'],['SLZ','São Luís'],['BEL','Belém'],['MAO','Manaus'],['PVH','Porto Velho'],['BVB','Boa Vista'],['MCP','Macapá'],['PMW','Palmas'],['JDO','Juazeiro do Norte'],['IOS','Ilhéus'],['BPS','Porto Seguro'],['PNZ','Petrolina'],['RBR','Rio Branco'],['STM','Santarém'],['IMP','Imperatriz'],['MOC','Montes Claros'],['JOI','Joinville'],['XAP','Chapecó'],['PFB','Passo Fundo'],['ROO','Rondonópolis'],['FEN','Fernando de Noronha'],['CAC','Cascavel'],
    ['EZE','Buenos Aires / Ezeiza'],['AEP','Buenos Aires / Aeroparque'],['SCL','Santiago'],['ASU','Assunção'],['MVD','Montevidéu'],['LIM','Lima'],['BOG','Bogotá'],['UIO','Quito'],['GYE','Guayaquil'],['VVI','Santa Cruz de la Sierra'],['PTY','Cidade do Panamá'],['SJO','San José'],['GUA','Cidade da Guatemala'],['MEX','Cidade do México'],['CUN','Cancún'],['PUJ','Punta Cana'],['SDQ','Santo Domingo'],['MIA','Miami'],['FLL','Fort Lauderdale'],['MCO','Orlando'],['JFK','Nova York / JFK'],['EWR','Nova York / Newark'],['BOS','Boston'],['IAD','Washington / Dulles'],['ATL','Atlanta'],['ORD','Chicago'],['DFW','Dallas / Fort Worth'],['IAH','Houston'],['LAX','Los Angeles'],['SFO','San Francisco'],['LAS','Las Vegas'],['YYZ','Toronto'],['YUL','Montreal'],['YVR','Vancouver'],['LIS','Lisboa'],['OPO','Porto'],['MAD','Madri'],['BCN','Barcelona'],['CDG','Paris'],['LHR','Londres / Heathrow'],['FCO','Roma'],['MXP','Milão'],['FRA','Frankfurt'],['AMS','Amsterdã'],['ZRH','Zurique'],['VIE','Viena'],['ATH','Atenas'],['IST','Istambul'],['DXB','Dubai'],['DOH','Doha']
  ];

  let data = {request:{},stats:{},results:[],daily_min:[]};
  let apiBase = '';
  let searching = false;
  let stopRequested = false;
  let activeRun = null;
  const tabs = q('#flightTabs');
  const app = q('#flightsApp');
  if (!tabs || !app || q('#flightMonthPanel')) return;

  const style = document.createElement('style');
  style.textContent = `
    body.flight-search-focus .wrap{padding-top:12px}
    body.flight-search-focus header{margin-bottom:5px;align-items:center}
    body.flight-search-focus header h1{font-size:clamp(24px,2.2vw,31px);margin:0}
    body.flight-search-focus header .sub{display:none}
    body.flight-search-focus .main-tabs{margin:5px 0 8px;padding-bottom:8px}
    body.flight-search-focus .main-tab{padding:8px 12px;font-size:13px}
    body.flight-search-focus #flightsApp>.flight-head{display:none!important}
    body.flight-search-focus #flightTabs{margin:5px 0 8px;gap:5px}
    body.flight-search-focus #flightTabs .tab{padding:7px 10px;font-size:12px;border-radius:9px}
    body.flight-search-focus #flightsApp>.foot{display:none}
    .month-titlebar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:2px 0 7px;flex-wrap:wrap}
    .month-titlebar strong{font-size:16px}.month-titlebar small{display:block;color:var(--muted);font-size:11px;margin-top:2px}
    .month-titlebar .pill{padding:6px 9px;font-size:11px}
    .month-search-grid{display:grid;grid-template-columns:1.1fr 1.3fr .95fr .72fr auto;gap:8px;align-items:end;padding:10px}
    .month-search-grid label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;margin:0 0 4px}
    .month-search-grid input,.month-search-grid select{padding:8px 10px;border-radius:9px;min-height:37px}
    .month-search-btn{border:0;background:var(--accent);color:#07111f;font-weight:900;border-radius:9px;padding:9px 14px;cursor:pointer;min-height:37px;white-space:nowrap}
    .month-search-btn:disabled{opacity:.6;cursor:wait}.month-search-btn:hover{filter:brightness(1.07)}
    .month-progress{border-top:1px solid var(--line);padding:9px 10px 8px;background:rgba(119,167,255,.035)}
    .month-progress-head{display:flex;align-items:center;gap:10px;justify-content:space-between;margin-bottom:7px}
    .month-progress-title{display:flex;align-items:center;gap:8px;min-width:0;flex:1}.month-progress-title b{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.month-progress-title strong{color:var(--accent);font-size:13px;min-width:40px;text-align:right}
    .month-progress-track{height:8px;border-radius:999px;background:var(--panel2);border:1px solid var(--line);overflow:hidden}.month-progress-fill{height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--ok));transition:width .45s ease}
    .month-progress-meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}.month-progress-meta span{font-size:10px;color:var(--muted);border:1px solid var(--line);background:var(--panel2);border-radius:999px;padding:4px 7px}
    .month-stop-btn{border:1px solid rgba(255,104,116,.5);background:rgba(255,104,116,.08);color:var(--hot);font-weight:900;border-radius:8px;padding:6px 9px;cursor:pointer;font-size:11px;white-space:nowrap}.month-stop-btn:hover{background:rgba(255,104,116,.16)}.month-stop-btn:disabled{opacity:.55;cursor:wait}
    .month-search-status{padding:7px 10px;border-top:1px solid var(--line);color:var(--muted);font-size:11px;line-height:1.4}.month-search-status.wait{color:var(--warn)}.month-search-status.ok{color:var(--ok)}.month-search-status.bad{color:var(--hot)}
    .month-cards{gap:8px;margin:9px 0}.month-cards .card{padding:10px 12px;border-radius:12px}.month-cards .card span{font-size:9px}.month-cards .card b{font-size:21px;margin-top:2px}
    .month-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;padding:9px}.month-day{min-height:58px;border:1px solid var(--line);background:var(--panel2);border-radius:9px;padding:7px}.month-day b{display:block;font-size:10px;color:var(--muted);margin-bottom:3px}.month-day strong{font-size:12px}.month-day.hot{border-color:var(--ok)}.month-day.hot strong{color:var(--ok)}
    .month-result-price{font-size:18px;font-weight:900;white-space:nowrap}.month-rank{font-size:16px;font-weight:900;color:var(--accent)}
    #flightMonthPanel .section-title{margin:10px 0 5px;font-size:15px}
    #flightMonthPanel .note{margin-top:9px;padding:9px 11px}
    @media(max-width:1100px){.month-search-grid{grid-template-columns:repeat(2,1fr)}.month-search-grid .month-search-action{grid-column:1/-1}.month-search-btn{width:100%}}
    @media(max-width:700px){body.flight-search-focus header h1{font-size:22px}.month-search-grid{grid-template-columns:1fr 1fr}.month-calendar{grid-template-columns:repeat(3,1fr)}.month-search-grid .dest-field{grid-column:1/-1}.month-progress-head{align-items:flex-start}.month-progress-title{flex-wrap:wrap}.month-cards{grid-template-columns:repeat(2,1fr)}}
  `;
  document.head.appendChild(style);

  const btn = document.createElement('button');
  btn.className = 'tab';
  btn.dataset.flightView = 'monthsearch';
  btn.textContent = '🔎 Buscar passagens';
  tabs.insertBefore(btn, tabs.children[1] || null);

  const panel = document.createElement('div');
  panel.id = 'flightMonthPanel';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="month-titlebar">
      <div><strong>🔎 Buscar passagens</strong><small>Escolha a rota e o mês. A varredura só começa quando você clicar em Pesquisar agora.</small></div>
      <div class="pill"><span class="dot"></span><span id="monthSearchUpdated">Aguardando busca</span></div>
    </div>
    <section class="panel">
      <div class="month-search-grid">
        <div><label>Origem</label><select id="monthOrigin"></select></div>
        <div class="dest-field"><label>Destino</label><input id="monthDestination" list="monthDestinations" placeholder="Ex.: Miami ou MIA"><datalist id="monthDestinations"></datalist></div>
        <div><label>Mês a pesquisar</label><input id="monthValue" type="month"></div>
        <div><label>Escalas</label><select id="monthStops"><option value="0">Direto</option><option value="1">Até 1</option><option value="2" selected>Até 2</option></select></div>
        <div class="month-search-action"><button class="month-search-btn" id="monthSearchButton">🔎 Pesquisar agora</button></div>
      </div>
      <div class="month-progress" id="monthProgress" hidden>
        <div class="month-progress-head">
          <div class="month-progress-title"><b id="monthProgressStage">Preparando pesquisa…</b><strong id="monthProgressPct">0%</strong></div>
          <button class="month-stop-btn" id="monthStopButton">■ Parar pesquisa</button>
        </div>
        <div class="month-progress-track"><div class="month-progress-fill" id="monthProgressFill"></div></div>
        <div class="month-progress-meta"><span id="monthProgressCombos">0 / 0 combinações</span><span id="monthProgressRemaining">faltam —</span><span id="monthProgressElapsed">0s</span><span id="monthProgressStep">aguardando início</span></div>
      </div>
      <div class="month-search-status" id="monthSearchStatus">Em um mês de 31 dias são até 465 combinações possíveis de ida e volta.</div>
    </section>
    <section class="cards month-cards"><div class="card"><span>Menor preço</span><b id="monthLowest">—</b></div><div class="card"><span>Combinações</span><b id="monthCombos">—</b></div><div class="card"><span>Com preço</span><b id="monthPriced">—</b></div><div class="card"><span>Melhores exibidas</span><b id="monthCount">—</b></div></section>
    <section class="panel" id="monthCalendarPanel" hidden><h3 class="section-title" style="padding:0 10px">Menor preço para cada dia de ida</h3><div class="month-calendar" id="monthCalendar"></div></section>
    <section class="panel" style="margin-top:9px"><div class="table-wrap"><table><thead><tr><th>#</th><th>Ida</th><th>Volta</th><th>Dias</th><th>Companhia / escalas</th><th>Preço</th><th>Fonte</th><th></th></tr></thead><tbody id="monthRows"></tbody></table></div><div class="empty" id="monthEmpty"><strong>Faça uma pesquisa.</strong>As melhores combinações aparecerão aqui.</div></section>
    <div class="note"><b>Varredura completa:</b> o sistema testa todos os pares de ida e volta dentro do mês, ordena as tarifas encontradas e mostra as 100 mais baratas.</div>`;
  app.insertBefore(panel, q('#hunterPanel') || null);

  q('#monthOrigin').innerHTML = ORIGINS.map(([c,n])=>`<option value="${c}">${c} · ${esc(n)}</option>`).join('');
  q('#monthDestinations').innerHTML = DESTINATIONS.map(([c,n])=>`<option value="${esc(n)}">${c}</option><option value="${c}">${esc(n)}</option>`).join('');
  const monthInput=q('#monthValue'), now=new Date(), pad=n=>String(n).padStart(2,'0'), monthKey=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}`;
  monthInput.min=monthKey(new Date(now.getFullYear(),now.getMonth(),1));
  monthInput.max=monthKey(new Date(now.getFullYear(),now.getMonth()+6,1));
  monthInput.value=monthKey(new Date(now.getFullYear(),now.getMonth()+1,1));

  function resolveDestination(raw){
    const value=String(raw||'').trim();
    if(/^[a-z]{3}$/i.test(value)) return value.toUpperCase();
    const n=norm(value);
    const exact=DESTINATIONS.find(([c,name])=>norm(name)===n||norm(`${name} (${c})`)===n);
    if(exact) return exact[0];
    const partial=DESTINATIONS.filter(([c,name])=>norm(name).includes(n)||norm(c)===n);
    return partial.length===1?partial[0][0]:'';
  }

  function formRequest(){
    return {origin:q('#monthOrigin').value.trim().toUpperCase(),destination:resolveDestination(q('#monthDestination').value),month:q('#monthValue').value,max_stops:Number(q('#monthStops').value||2)};
  }

  function comboTotal(month){
    if(!/^\d{4}-\d{2}$/.test(month)) return 0;
    const [y,m]=month.split('-').map(Number);
    const last=new Date(y,m,0).getDate();
    const today=new Date();
    let first=1;
    if(today.getFullYear()===y && today.getMonth()+1===m) first=Math.min(last,today.getDate()+1);
    const available=Math.max(0,last-first+1);
    return Math.max(0,(available*(available-1))/2);
  }

  function resetActiveMetrics(total){
    q('#monthLowest').textContent='—';
    q('#monthCombos').textContent=`0/${total}`;
    q('#monthPriced').textContent='calculando';
    q('#monthCount').textContent='aguardando';
  }

  function render(){
    const rows=data.results||[],stats=data.stats||{},req=data.request||{};
    q('#monthRows').innerHTML=rows.map((x,i)=>`<tr><td><span class="month-rank">${i+1}</span></td><td><b>${fmtDate(x.departure_date)}</b></td><td><b>${fmtDate(x.return_date)}</b></td><td>${Number(x.trip_days||0)} dias</td><td><b>${esc(x.airline||'Google Flights')}</b><small class="statline">${esc(x.stops||'')} ${x.duration?'· '+esc(x.duration):''}</small></td><td class="month-result-price">${money(x.price)}</td><td><span class="badge official">${esc(x.source_kind==='swoop'?'Swoop':'Google')}</span></td><td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Ver voo</a></td></tr>`).join('');
    q('#monthEmpty').hidden=rows.length>0;
    q('#monthLowest').textContent=money(stats.lowest_price);
    q('#monthCombos').textContent=stats.combinations??'—';
    q('#monthPriced').textContent=stats.priced_combinations!=null?`${stats.priced_combinations} · ${stats.coverage_pct||0}%`:'—';
    q('#monthCount').textContent=rows.length?`${rows.length}/100`:'—';
    if(data.generated_at) q('#monthSearchUpdated').textContent=`Atualizado ${new Date(data.generated_at).toLocaleString('pt-BR')} · ${req.origin||''}→${req.destination||''}`;
    const daily=data.daily_min||[],cal=q('#monthCalendar');
    if(daily.length){
      const low=Math.min(...daily.map(x=>Number(x.price)||Infinity));
      cal.innerHTML=daily.map(x=>{const d=Number((x.departure_date||'').slice(-2)),hot=Number(x.price)<=low*1.06?' hot':'';return`<div class="month-day${hot}"><b>Dia ${d}</b><strong>${money(x.price)}</strong><small class="statline">volta ${fmtDate(x.return_date)} · ${Number(x.trip_days||0)} dias</small></div>`}).join('');
      q('#monthCalendarPanel').hidden=false;
    }else{cal.innerHTML='';q('#monthCalendarPanel').hidden=true;}
  }

  function showProgress(total){
    q('#monthProgress').hidden=false;
    q('#monthStopButton').disabled=false;
    updateProgress({pct:1,stage:'Enviando solicitação…',done:0,total,detail:'iniciando',elapsed:0});
  }

  function updateProgress({pct,stage,done,total,detail,elapsed}){
    pct=Math.max(0,Math.min(100,Math.round(Number(pct)||0)));
    done=Math.max(0,Math.min(total,Math.round(Number(done)||0)));
    q('#monthProgressFill').style.width=`${pct}%`;
    q('#monthProgressPct').textContent=`${pct}%`;
    q('#monthProgressStage').textContent=stage||'Pesquisa em andamento…';
    q('#monthProgressCombos').textContent=`${done} / ${total} combinações${pct<100?' (estimativa)':''}`;
    q('#monthProgressRemaining').textContent=`faltam ${Math.max(0,total-done)}`;
    q('#monthProgressElapsed').textContent=`${Math.max(0,Math.round(elapsed||0))}s`;
    q('#monthProgressStep').textContent=detail||'processando';
    if(searching && total) q('#monthCombos').textContent=`~${done}/${total}`;
  }

  async function loadConfig(){
    try{const r=await fetch('./data/flight-search-config.json?t='+Date.now(),{cache:'no-store'});if(r.ok){const c=await r.json();apiBase=String(c.api_base||'').replace(/\/$/,'');}}catch{}
  }

  async function loadLastResult(){
    try{const r=await fetch('./data/flight-month-search.json?t='+Date.now(),{cache:'no-store'});if(r.ok){const old=await r.json();if(old&&old.results)data=old;}}catch{}
  }

  function resultMatches(result,request,started,previousGeneratedAt){
    if(!result||!result.request) return false;
    const r=result.request;
    if(r.origin!==request.origin||r.destination!==request.destination||r.month!==request.month) return false;
    if(Number(r.max_stops)!==Number(request.max_stops)) return false;
    if(previousGeneratedAt && result.generated_at===previousGeneratedAt) return false;
    const generated=Date.parse(result.generated_at||'');
    return Number.isFinite(generated) && generated >= started-15000;
  }

  async function fetchRunState(request,started,total){
    try{
      const rr=await fetch(`${ACTIONS_RUNS}&t=${Date.now()}`,{cache:'no-store'});
      if(!rr.ok) return null;
      const runs=(await rr.json()).workflow_runs||[];
      const run=runs.find(x=>{
        const created=Date.parse(x.created_at||'');
        const title=String(x.display_title||'');
        return created>=started-90000 && title.includes(`${request.origin} → ${request.destination}`) && title.includes(request.month);
      });
      if(!run) return null;
      activeRun=run;
      if(run.status==='queued') return {pct:4,stage:'Aguardando executor do GitHub…',done:0,total,detail:'na fila',run};
      if(run.status==='completed'){
        if(run.conclusion==='success') return {pct:98,stage:'Finalizando e publicando resultado…',done:total,total,detail:'publicando',run};
        if(run.conclusion==='cancelled') return {cancelled:true,run};
        return {failed:true,error:`A execução terminou com status ${run.conclusion||'erro'}.`,run};
      }
      const jr=await fetch(`${ACTIONS_RUN(run.id)}&t=${Date.now()}`,{cache:'no-store'});
      if(!jr.ok) return {pct:10,stage:'Preparando ambiente…',done:0,total,detail:'workflow iniciado',run};
      const jobs=(await jr.json()).jobs||[];
      const job=jobs[0];
      const steps=job?.steps||[];
      const current=steps.find(s=>s.status==='in_progress') || [...steps].reverse().find(s=>s.status==='completed');
      const name=String(current?.name||'Preparando ambiente');
      const stepBase={
        'Checkout':5,
        'Preparar solicitação':8,
        'Python':11,
        'Dependências':14,
        'Validar código':18,
        'Pesquisar matriz completa do período':20,
        'Validar resultado':91,
        'Persistir resultado':96,
        'Resumo':99
      };
      if(name==='Pesquisar matriz completa do período'){
        const stepStart=Date.parse(current.started_at||run.run_started_at||run.created_at||'') || started;
        const sec=Math.max(0,(Date.now()-stepStart)/1000);
        const expected=REGIONAL.has(request.origin)?Math.max(420,total*2.5):Math.max(150,total*.9);
        const frac=Math.min(.96,sec/expected);
        const pct=20+frac*69;
        const done=Math.floor(total*frac);
        return {pct,stage:'Pesquisando todas as combinações…',done,total,detail:`etapa de preços · ~${done}/${total}`,run};
      }
      const pct=stepBase[name]??12;
      const done=pct>=90?total:0;
      return {pct,stage:name==='Persistir resultado'?'Salvando resultado…':name==='Validar resultado'?'Validando as melhores tarifas…':'Preparando a pesquisa…',done,total,detail:name,run};
    }catch{return null;}
  }

  function fallbackProgress(request,started,total){
    const elapsed=(Date.now()-started)/1000;
    const expected=REGIONAL.has(request.origin)?Math.max(480,total*2.7):Math.max(180,total*1.0);
    const frac=Math.min(.92,elapsed/expected);
    const pct=8+frac*80;
    const done=Math.floor(total*frac);
    return {pct,stage:'Pesquisando combinações…',done,total,detail:'progresso estimado'};
  }

  async function pollPublicResult(request,started,previousGeneratedAt,total){
    const status=q('#monthSearchStatus');
    let lastActionsCheck=0;
    let state=null;
    for(let i=0;i<540;i++){
      if(stopRequested) throw new Error('__STOPPED__');
      await sleep(5000);
      if(stopRequested) throw new Error('__STOPPED__');
      const elapsed=Math.round((Date.now()-started)/1000);

      if(Date.now()-lastActionsCheck>30000 || !activeRun){
        lastActionsCheck=Date.now();
        const live=await fetchRunState(request,started,total);
        if(live) state=live;
        if(live?.failed) throw new Error(live.error);
        if(live?.cancelled && !stopRequested) throw new Error('A pesquisa foi cancelada no servidor.');
      }

      const p=state||fallbackProgress(request,started,total);
      updateProgress({...p,elapsed});
      status.className='month-search-status wait';
      status.textContent=`🔎 ${p.stage} Você pode continuar nesta página enquanto o sistema trabalha.`;

      try{
        const r=await fetch(`${RESULT_RAW}?t=${Date.now()}`,{cache:'no-store'});
        if(r.ok){
          const fresh=await r.json();
          if(resultMatches(fresh,request,started,previousGeneratedAt)) return fresh;
        }
      }catch{}
    }
    throw new Error('A busca excedeu o tempo máximo de espera.');
  }

  async function dispatchWithoutCors(request){
    await fetch(`${apiBase}/api/search`,{method:'POST',mode:'no-cors',cache:'no-store',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(request)});
  }

  async function stopSearch(){
    if(!searching) return;
    stopRequested=true;
    const stop=q('#monthStopButton'),status=q('#monthSearchStatus');
    stop.disabled=true;stop.textContent='⏳ Parando…';
    status.className='month-search-status wait';status.textContent='⛔ Solicitando o cancelamento da pesquisa…';
    try{
      const cancelMonth=q('#monthValue').value || monthKey(new Date());
      await dispatchWithoutCors({origin:'QZZ',destination:'QZX',month:cancelMonth,max_stops:0});
      updateProgress({pct:0,stage:'Pesquisa interrompida',done:0,total:comboTotal(q('#monthValue').value),detail:'cancelada',elapsed:0});
      status.className='month-search-status bad';status.textContent='⛔ Pesquisa interrompida. Você já pode iniciar outra busca.';
    }catch{
      status.className='month-search-status bad';status.textContent='A tela foi interrompida. O servidor pode levar alguns segundos para encerrar a execução.';
    }
  }

  async function searchInsidePage(){
    if(searching) return;
    const request=formRequest(),status=q('#monthSearchStatus'),button=q('#monthSearchButton');
    if(!/^[A-Z]{3}$/.test(request.destination)){status.className='month-search-status bad';status.textContent='Escolha uma cidade/aeroporto válido, por exemplo Miami ou MIA.';return;}
    if(!request.month){status.className='month-search-status bad';status.textContent='Escolha o mês que deseja pesquisar.';return;}
    if(!apiBase){status.className='month-search-status bad';status.textContent='O Google Apps Script da pesquisa ainda não foi conectado.';return;}

    searching=true;stopRequested=false;activeRun=null;
    button.disabled=true;button.textContent='⏳ Pesquisando…';
    const total=comboTotal(request.month);
    resetActiveMetrics(total);
    showProgress(total);
    status.className='month-search-status wait';status.textContent='🔎 Enviando a pesquisa para o motor…';
    const started=Date.now();
    const previousGeneratedAt=data.generated_at||'';
    try{
      await dispatchWithoutCors(request);
      updateProgress({pct:3,stage:'Pesquisa enviada. Aguardando início…',done:0,total,detail:'solicitação recebida',elapsed:0});
      data=await pollPublicResult(request,started,previousGeneratedAt,total);
      render();
      updateProgress({pct:100,stage:'Pesquisa concluída',done:Number(data.stats?.combinations||total),total:Number(data.stats?.combinations||total),detail:'resultado publicado',elapsed:(Date.now()-started)/1000});
      q('#monthStopButton').disabled=true;
      status.className='month-search-status ok';
      status.textContent=`✅ Busca concluída em ${Math.round((Date.now()-started)/1000)}s. Foram pesquisadas ${data.stats?.combinations||0} combinações e as menores tarifas estão abaixo.`;
    }catch(e){
      if(String(e.message||e)==='__STOPPED__'){
        status.className='month-search-status bad';
        status.textContent='⛔ Pesquisa interrompida. Você já pode iniciar outra busca.';
      }else{
        status.className='month-search-status bad';
        status.textContent=`Não foi possível concluir a busca: ${e.message||e}`;
      }
    }finally{
      searching=false;button.disabled=false;button.textContent='🔎 Pesquisar agora';
      const stop=q('#monthStopButton');stop.disabled=true;stop.textContent='■ Parar pesquisa';
    }
  }

  async function boot(){await Promise.all([loadConfig(),loadLastResult()]);if(!panel.hidden)render();}
  function setFocus(on){document.body.classList.toggle('flight-search-focus',!!on);}
  function activate(){
    document.querySelectorAll('#flightTabs .tab').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    ['hunterPanel','radarPanel','externalPanel','airlinesPanel'].forEach(id=>{const el=q('#'+id);if(el)el.hidden=true;});
    panel.hidden=false;setFocus(true);render();
  }

  q('#monthSearchButton').addEventListener('click',searchInsidePage);
  q('#monthStopButton').addEventListener('click',stopSearch);
  btn.addEventListener('click',activate);
  document.querySelectorAll('#flightTabs .tab').forEach(b=>{if(b!==btn)b.addEventListener('click',()=>{panel.hidden=true;setFocus(false);});});
  const productsMain=document.querySelector('.main-tab[data-main="products"]');
  if(productsMain)productsMain.addEventListener('click',()=>{panel.hidden=true;setFocus(false);});
  const flightsMain=document.querySelector('.main-tab[data-main="flights"]');
  if(flightsMain)flightsMain.addEventListener('click',()=>{if(btn.classList.contains('active')&&!panel.hidden)setFocus(true);});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!searching)loadConfig();});
  boot();
})();