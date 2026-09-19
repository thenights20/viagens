(() => {
  const q = s => document.querySelector(s);
  const money = v => v == null || Number.isNaN(Number(v)) ? '—' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v));
  const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe = (u='') => { try { const x=new URL(u); return x.protocol==='https:'?x.href:'#'; } catch { return '#'; } };
  const fmtDate = v => { if(!v) return '—'; const [y,m,d]=String(v).slice(0,10).split('-').map(Number); return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(y,m-1,d)); };
  const fmtDateTime = v => v ? new Date(v).toLocaleString('pt-BR') : '—';
  const norm = s => String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
  const sleep = ms => new Promise(r=>setTimeout(r,ms));
  const RESULT_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/main/docs/data/flight-month-search.json';
  const LIVE_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/flight-live/docs/data/flight-search-live.json';
  const ACTIONS_RUNS = 'https://api.github.com/repos/thenights20/viagens/actions/workflows/flight-month-search.yml/runs?event=workflow_dispatch&per_page=15';
  const ACTIONS_RUN = id => `https://api.github.com/repos/thenights20/viagens/actions/runs/${id}/jobs?per_page=10`;
  const AIRPORTS_WORLD = './data/airports-world.json';

  const ORIGINS = [
    ['SAO','São Paulo — todos (GRU + CGH + VCP)'],['RIO','Rio de Janeiro — todos (GIG + SDU)'],['DOU','Dourados'],['PMG','Ponta Porã'],['JTC','Bauru'],['GRU','Guarulhos'],['CGH','São Paulo / Congonhas'],['VCP','Campinas / Viracopos'],['GIG','Rio de Janeiro / Galeão'],['TJL','Três Lagoas'],['ARU','Araçatuba'],['PPB','Presidente Prudente / Pres. Venceslau'],['MII','Marília']
  ];
  const DESTINATIONS = [
    ['CGR','Campo Grande'],['CGB','Cuiabá'],['BSB','Brasília'],['GYN','Goiânia'],['CWB','Curitiba'],['LDB','Londrina'],['MGF','Maringá'],['IGU','Foz do Iguaçu'],['FLN','Florianópolis'],['NVT','Navegantes'],['POA','Porto Alegre'],['VCP','Campinas'],['CGH','São Paulo / Congonhas'],['GRU','São Paulo / Guarulhos'],['SJP','São José do Rio Preto'],['RAO','Ribeirão Preto'],['UDI','Uberlândia'],['CNF','Belo Horizonte'],['GIG','Rio de Janeiro / Galeão'],['SDU','Rio de Janeiro / Santos Dumont'],['VIX','Vitória'],['SSA','Salvador'],['REC','Recife'],['FOR','Fortaleza'],['NAT','Natal'],['MCZ','Maceió'],['AJU','Aracaju'],['JPA','João Pessoa'],['THE','Teresina'],['SLZ','São Luís'],['BEL','Belém'],['MAO','Manaus'],['PVH','Porto Velho'],['BVB','Boa Vista'],['MCP','Macapá'],['PMW','Palmas'],['JDO','Juazeiro do Norte'],['IOS','Ilhéus'],['BPS','Porto Seguro'],['PNZ','Petrolina'],['RBR','Rio Branco'],['STM','Santarém'],['IMP','Imperatriz'],['MOC','Montes Claros'],['JOI','Joinville'],['XAP','Chapecó'],['PFB','Passo Fundo'],['ROO','Rondonópolis'],['FEN','Fernando de Noronha'],['CAC','Cascavel'],
    ['EZE','Buenos Aires / Ezeiza'],['AEP','Buenos Aires / Aeroparque'],['SCL','Santiago'],['ASU','Assunção'],['MVD','Montevidéu'],['LIM','Lima'],['BOG','Bogotá'],['UIO','Quito'],['GYE','Guayaquil'],['VVI','Santa Cruz de la Sierra'],['PTY','Cidade do Panamá'],['SJO','San José'],['GUA','Cidade da Guatemala'],['MEX','Cidade do México'],['CUN','Cancún'],['PUJ','Punta Cana'],['SDQ','Santo Domingo'],['MIA','Miami'],['FLL','Fort Lauderdale'],['MCO','Orlando'],['JFK','Nova York / JFK'],['EWR','Nova York / Newark'],['BOS','Boston'],['IAD','Washington / Dulles'],['ATL','Atlanta'],['ORD','Chicago'],['DFW','Dallas / Fort Worth'],['IAH','Houston'],['LAX','Los Angeles'],['SFO','San Francisco'],['LAS','Las Vegas'],['YYZ','Toronto'],['YUL','Montreal'],['YVR','Vancouver'],['LIS','Lisboa'],['OPO','Porto'],['MAD','Madri'],['BCN','Barcelona'],['CDG','Paris'],['LHR','Londres / Heathrow'],['FCO','Roma'],['MXP','Milão'],['FRA','Frankfurt'],['AMS','Amsterdã'],['ZRH','Zurique'],['VIE','Viena'],['ATH','Atenas'],['IST','Istambul'],['DXB','Dubai'],['DOH','Doha']
  ];
  const RESERVED = new Set([...ORIGINS.map(x=>x[0]),...DESTINATIONS.map(x=>x[0]),'QZZ','QZX']);
  const RANGE_CODES = (()=>{const out=[];for(const a of 'QRSTUVWXYZ')for(const b of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')for(const c of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'){const code=a+b+c;if(!RESERVED.has(code))out.push(code)}return out})();
  const PAIRS_PER_ORIGIN = 465;
  const AIRPORT_GROUPS = {
    SAO:['GRU','CGH','VCP'],
    RIO:['GIG','SDU'],
    NYC:['JFK','EWR','LGA'],
    WAS:['IAD','DCA','BWI'],
    LON:['LHR','LGW','STN','LTN','LCY'],
    PAR:['CDG','ORY'],
    TYO:['HND','NRT']
  };

  let data = {request:{},stats:{},results:[],daily_min:[],history_summary:{}};
  let savedPairs = {};
  let apiBase = '';
  let searching = false;
  let stopRequested = false;
  let activeRun = null;
  let activeRequest = null;
  let resultView = 'calendar';
  let worldAirports = [];
  let worldAirportByCode = new Map();
  let airportSuggestIndex = -1;
  const tabs = q('#flightTabs');
  const app = q('#flightsApp');
  if (!tabs || !app || q('#flightMonthPanel')) return;

  const style = document.createElement('style');
  style.textContent = `
    body.flight-search-focus .wrap{padding-top:10px}body.flight-search-focus header{margin-bottom:4px;align-items:center}body.flight-search-focus header h1{font-size:clamp(23px,2vw,30px);margin:0}body.flight-search-focus header .sub{display:none}
    body.flight-search-focus .main-tabs{margin:4px 0 7px;padding-bottom:7px}body.flight-search-focus .main-tab{padding:7px 11px;font-size:13px}body.flight-search-focus #flightsApp>.flight-head{display:none!important}
    body.flight-search-focus #flightTabs{margin:4px 0 7px;gap:5px}body.flight-search-focus #flightTabs .tab{padding:7px 10px;font-size:12px;border-radius:9px}body.flight-search-focus #flightsApp>.foot{display:none}
    .month-titlebar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:1px 0 6px;flex-wrap:wrap}.month-titlebar strong{font-size:16px}.month-titlebar small{display:block;color:var(--muted);font-size:11px;margin-top:2px}.month-titlebar .pill{padding:6px 9px;font-size:11px}
    .month-search-grid{display:grid;grid-template-columns:1.05fr 1.25fr .85fr 1.25fr .68fr auto;gap:7px;align-items:end;padding:9px}.month-search-grid label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;margin:0 0 4px}.month-search-grid input,.month-search-grid select{padding:8px 9px;border-radius:9px;min-height:37px}
    .dest-field{position:relative}.airport-suggest{position:absolute;z-index:80;left:0;right:0;top:calc(100% + 4px);max-height:330px;overflow:auto;background:var(--panel2);border:1px solid var(--line);border-radius:11px;box-shadow:0 18px 45px rgba(0,0,0,.42);padding:4px}.airport-suggest[hidden]{display:none}.airport-option{display:block;width:100%;border:0;background:transparent;color:var(--text);text-align:left;padding:8px 9px;border-radius:8px;cursor:pointer}.airport-option:hover,.airport-option.active{background:rgba(119,167,255,.13)}.airport-option b{display:block;font-size:12px}.airport-option small{display:block;color:var(--muted);font-size:10px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.airport-loading{padding:9px;color:var(--muted);font-size:10px}
    .month-period-range{display:grid;grid-template-columns:1fr 1fr;gap:6px}.month-search-btn{border:0;background:var(--accent);color:#07111f;font-weight:900;border-radius:9px;padding:9px 13px;cursor:pointer;min-height:37px;white-space:nowrap}.month-search-btn:disabled{opacity:.6;cursor:wait}.month-search-btn:hover{filter:brightness(1.07)}
    .month-progress{border-top:1px solid var(--line);padding:8px 9px;background:rgba(119,167,255,.035)}.month-progress-head{display:flex;align-items:center;gap:10px;justify-content:space-between;margin-bottom:6px}.month-progress-title{display:flex;align-items:center;gap:8px;min-width:0;flex:1}.month-progress-title b{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.month-progress-title strong{color:var(--accent);font-size:13px;min-width:40px;text-align:right}.month-progress-track{height:8px;border-radius:999px;background:var(--panel2);border:1px solid var(--line);overflow:hidden}.month-progress-fill{height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--ok));transition:width .35s ease}.month-progress-meta{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px}.month-progress-meta span{font-size:10px;color:var(--muted);border:1px solid var(--line);background:var(--panel2);border-radius:999px;padding:4px 7px}
    .month-stop-btn{border:1px solid rgba(255,104,116,.5);background:rgba(255,104,116,.08);color:var(--hot);font-weight:900;border-radius:8px;padding:6px 9px;cursor:pointer;font-size:11px;white-space:nowrap}.month-stop-btn:hover{background:rgba(255,104,116,.16)}.month-stop-btn:disabled{opacity:.55;cursor:wait}
    .month-search-status{padding:7px 9px;border-top:1px solid var(--line);color:var(--muted);font-size:11px;line-height:1.4}.month-search-status.wait{color:var(--warn)}.month-search-status.ok{color:var(--ok)}.month-search-status.bad{color:var(--hot)}
    .month-cards{gap:7px;margin:8px 0;grid-template-columns:repeat(5,1fr)}.month-cards .card{padding:9px 11px;border-radius:11px}.month-cards .card span{font-size:9px}.month-cards .card b{font-size:19px;margin-top:2px}
    .month-view-tabs{display:flex;gap:6px;margin:8px 0}.month-view-btn{border:1px solid var(--line);background:var(--panel);color:var(--text);border-radius:9px;padding:7px 10px;font-weight:800;font-size:11px;cursor:pointer}.month-view-btn.active{background:var(--accent);color:#07111f;border-color:transparent}
    .month-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;padding:9px}.month-day{min-height:63px;border:1px solid var(--line);background:var(--panel2);border-radius:9px;padding:7px}.month-day b{display:block;font-size:10px;color:var(--muted);margin-bottom:3px}.month-day strong{font-size:12px}.month-day.hot{border-color:var(--ok)}.month-day.hot strong{color:var(--ok)}
    .trend{display:inline-flex;align-items:center;font-weight:900;font-size:10px;border-radius:999px;padding:2px 6px;margin-top:3px;border:1px solid var(--line)}.trend.down{color:var(--ok);border-color:rgba(91,214,160,.45)}.trend.up{color:var(--hot);border-color:rgba(255,104,116,.45)}.trend.same{color:var(--muted)}.trend.new{color:var(--accent)}
    .month-result-price{font-size:17px;font-weight:900;white-space:nowrap}.month-rank{font-size:15px;font-weight:900;color:var(--accent)}.saved-pill{color:var(--ok)!important}
    #flightMonthPanel .section-title{margin:9px 0 5px;font-size:15px}#flightMonthPanel .note{margin-top:8px;padding:8px 10px}.history-diff.down{color:var(--ok);font-weight:900}.history-diff.up{color:var(--hot);font-weight:900}.history-diff.same{color:var(--muted);font-weight:800}
    @media(max-width:1180px){.month-search-grid{grid-template-columns:repeat(3,1fr)}.month-search-grid .month-search-action{grid-column:auto}.month-cards{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:760px){body.flight-search-focus header h1{font-size:21px}.month-search-grid{grid-template-columns:1fr 1fr}.month-search-grid .dest-field{grid-column:1/-1}.month-search-grid .period-cell{grid-column:1/-1}.month-search-grid .month-search-action{grid-column:1/-1}.month-search-btn{width:100%}.month-calendar{grid-template-columns:repeat(2,1fr)}.month-cards{grid-template-columns:repeat(2,1fr)}.month-progress-head{align-items:flex-start}.month-progress-title{flex-wrap:wrap}}
  `;
  style.textContent += `.month-result-filters{display:flex;gap:12px;flex-wrap:wrap;align-items:end;padding:12px;margin-bottom:10px}.month-result-filters>div{flex:1;min-width:170px}.month-result-filters label{display:block;margin-bottom:5px}.month-result-filters select{width:100%}.month-day{display:block;text-decoration:none;color:inherit}.month-day:hover,.month-day:focus-visible{border-color:#79a7ff;outline:2px solid #79a7ff;outline-offset:2px}.month-route{font-size:12px;line-height:1.5;color:#a9c5f5}.month-result-caption{padding:4px 12px 12px;color:#9db1ce}`;
  document.head.appendChild(style);

  const btn = document.createElement('button');
  btn.className = 'tab';btn.dataset.flightView='monthsearch';btn.textContent='🔎 Buscar passagens';
  tabs.insertBefore(btn,tabs.children[1]||null);

  const panel=document.createElement('div');panel.id='flightMonthPanel';panel.hidden=true;
  panel.innerHTML=`
    <div class="month-titlebar"><div><strong>🔎 Buscar passagens · v0.6.3</strong><small>Os achados são salvos durante a pesquisa. Se a execução parar, o que já foi encontrado continua disponível.</small></div><div class="pill"><span class="dot"></span><span id="monthSearchUpdated">Aguardando busca</span></div></div>
    <section class="panel">
      <div class="month-search-grid">
        <div><label>Origem</label><select id="monthOrigin"></select><small id="originGroupHint" style="display:block;margin-top:4px;color:var(--muted);font-size:9px"></small></div>
        <div class="dest-field"><label>Destino</label><input id="monthDestination" placeholder="Digite cidade, aeroporto ou IATA..." autocomplete="off" spellcheck="false"><div id="monthAirportSuggest" class="airport-suggest" hidden></div></div>
        <div><label>Período</label><select id="monthPeriodMode"><option value="month">Mês inteiro</option><option value="range">Intervalo de datas</option></select></div>
        <div class="period-cell"><div id="monthPeriodMonth"><label>Mês a pesquisar</label><input id="monthValue" type="month"></div><div id="monthPeriodRange" hidden><label>Datas</label><div class="month-period-range"><input id="rangeStart" type="date" title="Data inicial"><input id="rangeEnd" type="date" title="Data final"></div></div></div>
        <div><label>Escalas</label><select id="monthStops"><option value="0">Direto</option><option value="1">Até 1</option><option value="2" selected>Até 2</option></select></div>
        <div class="month-search-action"><button type="button" class="month-search-btn" id="monthSearchButton">🔎 Pesquisar agora</button></div>
      </div>
      <div class="month-progress" id="monthProgress" hidden>
        <div class="month-progress-head"><div class="month-progress-title"><b id="monthProgressStage">Preparando pesquisa…</b><strong id="monthProgressPct">0%</strong></div><button class="month-stop-btn" id="monthStopButton">■ Parar pesquisa</button></div>
        <div class="month-progress-track"><div class="month-progress-fill" id="monthProgressFill"></div></div>
        <div class="month-progress-meta"><span id="monthProgressCombos">0 / 0 combinações</span><span id="monthProgressPriced">0 com preço</span><span id="monthProgressRemaining">faltam —</span><span id="monthProgressElapsed">0s</span><span class="saved-pill" id="monthProgressSaved">✓ salvamento automático</span></div>
      </div>
      <div class="month-search-status" id="monthSearchStatus">Escolha a rota e o período. Em um mês de 31 dias são até 465 combinações.</div>
    </section>
    <div class="month-result-caption">Resumo da busca atual</div>
    <section class="cards month-cards"><div class="card"><span>Menor preço</span><b id="monthLowest">—</b></div><div class="card"><span>Combinações</span><b id="monthCombos">—</b></div><div class="card"><span>Com preço</span><b id="monthPriced">—</b></div><div class="card"><span>Melhores</span><b id="monthCount">—</b></div><div class="card"><span>Desde a última busca</span><b id="monthHistory">—</b></div></section>
    <div class="month-view-tabs"><button class="month-view-btn active" data-result-view="calendar">▦ Calendário</button><button class="month-view-btn" data-result-view="prices">↕ Preços e rotas</button><button class="month-view-btn" data-result-view="history">◴ Histórico</button></div>
    <div class="month-view-tabs"><button class="month-view-btn" id="showSavedSearches">Ver buscas salvas</button><button class="month-view-btn" id="showCurrentSearch">Voltar à busca atual</button></div>
    <div class="panel month-result-filters">
      <div><label for="resultScope">Resultados</label><select id="resultScope"><option value="current">Busca atual</option><option value="all">Todas as buscas salvas</option></select></div>
      <div><label for="resultOrigin">Filtrar origem</label><select id="resultOrigin"><option value="">Todas as origens</option></select></div>
      <div><label for="resultDestination">Filtrar destino</label><select id="resultDestination"><option value="">Todos os destinos</option></select></div>
      <div><label for="resultMonth">Mês</label><select id="resultMonth"><option value="">Todos os meses</option></select></div>
      <div><label for="resultSort">Ordenar por</label><select id="resultSort"><option value="price_asc">Menor preço primeiro</option><option value="price_desc">Maior preço primeiro</option><option value="date_asc">Data de ida</option></select></div>
    </div>
    <div id="resultCaption" class="month-result-caption"></div>
    <section class="panel" id="monthCalendarPanel"><h3 class="section-title" style="padding:0 10px">Menor preço para cada dia de ida</h3><div class="month-calendar" id="monthCalendar"></div><div class="empty" id="monthCalendarEmpty"><strong>Nenhum preço para os filtros selecionados.</strong>Altere os filtros ou faça uma nova busca.</div></section>
    <section class="panel" id="monthPricesPanel" hidden><div class="table-wrap"><table><thead><tr><th>#</th><th>Origem</th><th>Destino</th><th>Ida</th><th>Volta</th><th>Dias</th><th>Preço</th><th>Variação</th><th>Companhia / escalas</th><th></th></tr></thead><tbody id="monthRows"></tbody></table></div><div class="empty" id="monthEmpty"><strong>Nenhum resultado para os filtros selecionados.</strong>Selecione outra origem ou destino, ou faça uma nova busca.</div></section>
    <section class="panel" id="monthHistoryPanel" hidden><div class="table-wrap"><table><thead><tr><th>Rota</th><th>Ida</th><th>Volta</th><th>Agora</th><th>Anterior</th><th>Mudança</th><th>Menor histórico</th><th>Amostras anteriores</th></tr></thead><tbody id="monthHistoryRows"></tbody></table></div><div class="empty" id="monthHistoryEmpty"><strong>Ainda não há comparação.</strong>Na próxima pesquisa das mesmas datas o sistema mostrará se o preço subiu ou baixou.</div></section>
    <div class="note"><b>Salvamento progressivo:</b> durante a busca o sistema publica os achados parciais em uma área separada do site. Uma nova pesquisa das mesmas datas compara automaticamente o valor atual com o último valor salvo.</div>`;
  app.insertBefore(panel,q('#hunterPanel')||null);

  q('#monthOrigin').innerHTML=ORIGINS.map(([c,n])=>`<option value="${c}">${c} · ${esc(n)}</option>`).join('');const updateOriginHint=()=>{const code=q('#monthOrigin').value,h=q('#originGroupHint'),g=AIRPORT_GROUPS[code];if(h)h.textContent=g?'Inclui '+g.join(', '):''};q('#monthOrigin').addEventListener('change',updateOriginHint);updateOriginHint();
  setupAirportAutocomplete();

  const now=new Date(),pad=n=>String(n).padStart(2,'0'),monthKey=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}`,dateKey=d=>`${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  const monthInput=q('#monthValue');monthInput.min=monthKey(new Date(now.getFullYear(),now.getMonth(),1));monthInput.max=monthKey(new Date(now.getFullYear(),now.getMonth()+18,1));monthInput.value=monthKey(new Date(now.getFullYear(),now.getMonth()+1,1));
  const defaultRangeStart=new Date(now.getFullYear(),now.getMonth()+1,10),defaultRangeEnd=new Date(now.getFullYear(),now.getMonth()+1,15);
  q('#rangeStart').min=dateKey(new Date(now.getFullYear(),now.getMonth(),now.getDate()+1));q('#rangeStart').max=dateKey(new Date(now.getFullYear(),now.getMonth()+19,0));q('#rangeStart').value=dateKey(defaultRangeStart);
  q('#rangeEnd').min=q('#rangeStart').min;q('#rangeEnd').max=q('#rangeStart').max;q('#rangeEnd').value=dateKey(defaultRangeEnd);monthInput.addEventListener('change',()=>{const s=q('#monthSearchStatus');if(s&&monthInput.value)s.textContent='Mês selecionado: '+monthLabel(monthInput.value)+'. Clique em Pesquisar agora para iniciar.';});

  function fallbackAirports(){return DESTINATIONS.map(([code,name])=>({code,name,city:name,state:'',country:''}));}
  function setWorldAirports(list){
    const seen=new Set(),clean=[];
    for(const raw of (Array.isArray(list)?list:[])){
      const code=String(raw.code||raw.iata||'').trim().toUpperCase();
      if(!/^[A-Z]{3}$/.test(code)||seen.has(code))continue;
      seen.add(code);clean.push({code,name:String(raw.name||'').trim(),city:String(raw.city||'').trim(),state:String(raw.state||'').trim(),country:String(raw.country||'').trim().toUpperCase()});
    }
    worldAirports=clean.length?clean:fallbackAirports();worldAirportByCode=new Map(worldAirports.map(a=>[a.code,a]));
  }
  function airportDisplay(a){
    const place=a.city||a.name||a.code,name=a.name&&norm(a.name)!==norm(place)?` — ${a.name}`:'',where=[a.state,a.country].filter(Boolean).join(', ');
    return `${place}${name}${where?` · ${where}`:''} (${a.code})`;
  }
  function airportMatches(term){
    const n=norm(term);if(!n)return[];const source=worldAirports.length?worldAirports:fallbackAirports();
    return source.map(a=>{const c=norm(a.code),city=norm(a.city),name=norm(a.name),state=norm(a.state),country=norm(a.country),hay=`${c} ${city} ${name} ${state} ${country}`;let score=99;if(c===n)score=0;else if(c.startsWith(n))score=1;else if(city===n)score=2;else if(city.startsWith(n))score=3;else if(name.startsWith(n))score=4;else if(state.startsWith(n)||country===n)score=5;else if(hay.includes(n))score=6;return{a,score};}).filter(x=>x.score<99).sort((x,y)=>x.score-y.score||String(x.a.city||x.a.name).localeCompare(String(y.a.city||y.a.name),'pt-BR')).slice(0,12).map(x=>x.a);
  }
  function hideAirportSuggestions(){const box=q('#monthAirportSuggest');if(box){box.hidden=true;box.innerHTML='';}airportSuggestIndex=-1;}
  function chooseAirport(a){const input=q('#monthDestination');if(!input)return;input.value=airportDisplay(a);input.dataset.iata=a.code;hideAirportSuggestions();}
  function renderAirportSuggestions(term){
    const box=q('#monthAirportSuggest');if(!box)return;const matches=airportMatches(term);airportSuggestIndex=-1;
    if(!String(term||'').trim()){hideAirportSuggestions();return;}
    if(!matches.length){box.innerHTML='<div class="airport-loading">Nenhum aeroporto encontrado. Você também pode informar diretamente um código IATA de 3 letras.</div>';box.hidden=false;return;}
    box.innerHTML=matches.map((a,i)=>`<button type="button" class="airport-option" data-airport-index="${i}" data-airport-code="${esc(a.code)}"><b>${esc(a.code)} · ${esc(a.city||a.name||a.code)}</b><small>${esc([a.name,a.state,a.country].filter(Boolean).join(' · '))}</small></button>`).join('');box.hidden=false;
    box.querySelectorAll('.airport-option').forEach((el,i)=>el.addEventListener('pointerdown',e=>{e.preventDefault();chooseAirport(matches[i]);}));
  }
  async function loadWorldAirports(){
    setWorldAirports(fallbackAirports());const input=q('#monthDestination');if(input)input.title='Carregando base mundial de aeroportos…';
    try{const r=await fetch(AIRPORTS_WORLD,{cache:'force-cache'});if(!r.ok)throw new Error(`HTTP ${r.status}`);const list=await r.json();if(!Array.isArray(list)||list.length<5000)throw new Error('base incompleta');setWorldAirports(list);if(input)input.title=`Base mundial carregada: ${worldAirports.length.toLocaleString('pt-BR')} aeroportos com IATA`;}catch(e){if(input)input.title='Base mundial indisponível; usando lista principal de aeroportos.';console.warn('airport-database',e);}
  }
  function setupAirportAutocomplete(){
    const input=q('#monthDestination'),box=q('#monthAirportSuggest');if(!input||!box)return;setWorldAirports(fallbackAirports());loadWorldAirports();
    input.addEventListener('input',()=>{input.dataset.iata='';renderAirportSuggestions(input.value);});
    input.addEventListener('focus',()=>{if(input.value.trim())renderAirportSuggestions(input.value);});
    input.addEventListener('blur',()=>setTimeout(hideAirportSuggestions,140));
    input.addEventListener('keydown',e=>{const opts=[...box.querySelectorAll('.airport-option')];if(e.key==='Escape'){hideAirportSuggestions();return;}if(!opts.length)return;if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();airportSuggestIndex=e.key==='ArrowDown'?Math.min(opts.length-1,airportSuggestIndex+1):Math.max(0,airportSuggestIndex<0?opts.length-1:airportSuggestIndex-1);opts.forEach((o,i)=>o.classList.toggle('active',i===airportSuggestIndex));opts[airportSuggestIndex]?.scrollIntoView({block:'nearest'});return;}if(e.key==='Enter'&&airportSuggestIndex>=0){e.preventDefault();const code=opts[airportSuggestIndex]?.dataset.airportCode,a=worldAirportByCode.get(code);if(a)chooseAirport(a);}});
  }
  function resolveDestination(raw){const input=q('#monthDestination'),selected=String(input?.dataset?.iata||'').toUpperCase();if(/^[A-Z]{3}$/.test(selected))return selected;const value=String(raw||'').trim();if(/^[a-z]{3}$/i.test(value))return value.toUpperCase();const suffix=value.match(/\(([A-Z]{3})\)\s*$/i);if(suffix)return suffix[1].toUpperCase();const n=norm(value);const legacy=DESTINATIONS.find(([c,name])=>norm(name)===n||norm(`${name} (${c})`)===n);if(legacy)return legacy[0];const exact=(worldAirports.length?worldAirports:fallbackAirports()).filter(a=>norm(a.city)===n||norm(a.name)===n||norm(airportDisplay(a))===n);return exact.length===1?exact[0].code:'';}
  function pairIndex(startDay,endDay){let pos=0;for(let s=1;s<=30;s++)for(let e=s+1;e<=31;e++){if(s===startDay&&e===endDay)return pos;pos++}return-1}
  function encodeRangeOrigin(origin,startDate,endDate){const oi=ORIGINS.findIndex(x=>x[0]===origin);if(oi<0)return origin;const s=Number(startDate.slice(-2)),e=Number(endDate.slice(-2)),pi=pairIndex(s,e);if(pi<0)return origin;const code=RANGE_CODES[oi*PAIRS_PER_ORIGIN+pi];return code||origin}

  function periodModeChanged(){const range=q('#monthPeriodMode').value==='range';q('#monthPeriodMonth').hidden=range;q('#monthPeriodRange').hidden=!range;}
  function formRequest(){
    const origin=q('#monthOrigin').value.trim().toUpperCase(),destination=resolveDestination(q('#monthDestination').value),mode=q('#monthPeriodMode').value,max_stops=Number(q('#monthStops').value);
    const origins=AIRPORT_GROUPS[origin]||[origin];
    if(mode==='range'){
      const start=q('#rangeStart').value,end=q('#rangeEnd').value,month=start.slice(0,7);
      return{origin,destination,origins,period_mode:'range',start_date:start,end_date:end,month,max_stops,dispatch_origin:origin};
    }
    const month=q('#monthValue').value;
    return{origin,destination,origins,period_mode:'month',start_date:`${month}-01`,end_date:'',month,max_stops,dispatch_origin:origin};
  }
  function comboTotal(request){
    let start,end;
    if(request.period_mode==='range'){start=new Date(request.start_date+'T12:00:00');end=new Date(request.end_date+'T12:00:00');}
    else{const[y,m]=request.month.split('-').map(Number);start=new Date(y,m-1,1,12);end=new Date(y,m,0,12);}
    const today=new Date();today.setHours(12,0,0,0);const tomorrow=new Date(today);tomorrow.setDate(tomorrow.getDate()+1);if(start<tomorrow)start=tomorrow;
    const days=Math.floor((end-start)/86400000)+1;return days>=2?(days*(days-1))/2:0;
  }
  function trendHtml(x){if(x.previous_price==null)return'<span class="trend new">novo</span>';const cls=x.trend||'same';if(cls==='down')return`<span class="trend down">↓ ${money(Math.abs(x.change_amount))} (${Math.abs(Number(x.change_pct||0)).toFixed(1)}%)</span>`;if(cls==='up')return`<span class="trend up">↑ ${money(Math.abs(x.change_amount))} (${Math.abs(Number(x.change_pct||0)).toFixed(1)}%)</span>`;return'<span class="trend same">= igual</span>';}

  function setResultView(view){resultView=view;document.querySelectorAll('.month-view-btn').forEach(b=>b.classList.toggle('active',b.dataset.resultView===view));q('#monthCalendarPanel').hidden=view!=='calendar';q('#monthPricesPanel').hidden=view!=='prices';q('#monthHistoryPanel').hidden=view!=='history';}
  function airportName(code){const world=worldAirportByCode.get(String(code||'').toUpperCase());return (world&&(world.city||world.name))||[...ORIGINS,...DESTINATIONS].find(x=>x[0]===code)?.[1]||code||'—'}
  function routeLabel(row){return `${airportName(row.origin)} (${row.origin}) → ${airportName(row.destination)} (${row.destination})`}
  function flightLink(row){
    if(row.url&&safe(row.url)!=='#')return safe(row.url);
    const query=`Flights from ${row.origin} to ${row.destination} on ${row.departure_date} returning ${row.return_date}`;
    return `https://www.google.com/travel/flights?q=${encodeURIComponent(query)}&curr=BRL`;
  }
  function resultKey(row){return [row.origin,row.destination,row.departure_date,row.return_date,row.max_stops??data.request?.max_stops??2].join('|')}
  function availableRows(){
    const rows=new Map(),all=q('#resultScope').value==='all';
    if(all)for(const pair of Object.values(savedPairs)){
      if(!pair.departure_date||!(Number(pair.last_price)>0))continue;
      const obs=pair.observations||[],previous=obs.length>1?Number(obs[obs.length-2].price):null,price=Number(pair.last_price),change=previous==null?null:price-previous;
      const row={...pair,price,previous_price:previous,change_amount:change,change_pct:previous?change/previous*100:null,trend:change==null?'new':change<0?'down':change>0?'up':'same',historical_min:pair.min_price,history_samples:Math.max(0,(pair.samples||1)-1),trip_days:Math.round((Date.parse(pair.return_date)-Date.parse(pair.departure_date))/86400000),airline:'Não informada',stops:'',saved_at:pair.last_seen};
      rows.set(resultKey(row),row);
    }
    for(const row of (data.all_results||[...(data.daily_min||[]),...(data.results||[])])){
      const normalized={...data.request,...row,saved_at:data.updated_at||data.generated_at};
      if(Number(normalized.price)>0)rows.set(resultKey(normalized),normalized);
    }
    return [...rows.values()];
  }
  function filterRows(rows,origin,destination,sort,month){
    return rows.filter(x=>(!origin||x.origin===origin)&&(!destination||x.destination===destination)&&(!month||String(x.departure_date||'').slice(0,7)===month)).sort((a,b)=>sort==='date_asc'?a.departure_date.localeCompare(b.departure_date)||Number(a.price)-Number(b.price):sort==='price_desc'?Number(b.price)-Number(a.price):Number(a.price)-Number(b.price));
  }
  function resultOptions(rows){
    for(const [id,key,label] of [['#resultOrigin','origin','Todas as origens'],['#resultDestination','destination','Todos os destinos']]){
      const el=q(id),selected=el.value,codes=[...new Set(rows.map(x=>x[key]).filter(Boolean))].sort((a,b)=>airportName(a).localeCompare(airportName(b),'pt-BR'));
      el.innerHTML=`<option value="">${label}</option>`+codes.map(code=>`<option value="${esc(code)}">${esc(airportName(code))} (${esc(code)})</option>`).join('');
      el.value=codes.includes(selected)?selected:'';
    }
  }
  function monthLabel(key){if(!/^\d{4}-\d{2}$/.test(key||''))return key||'';const[y,m]=key.split('-').map(Number);const text=new Intl.DateTimeFormat('pt-BR',{month:'long',year:'numeric'}).format(new Date(y,m-1,1));return text.charAt(0).toUpperCase()+text.slice(1);}
  function resultMonthOptions(rows){const el=q('#resultMonth');if(!el)return;const selected=el.value,months=[...new Set(rows.map(x=>String(x.departure_date||'').slice(0,7)).filter(x=>/^\d{4}-\d{2}$/.test(x)))].sort();el.innerHTML='<option value="">Todos os meses</option>'+months.map(m=>`<option value="${esc(m)}">${esc(monthLabel(m))}</option>`).join('');el.value=months.includes(selected)?selected:'';}
  function calendarRows(rows){
    const days=new Map();for(const row of rows){const key=[row.origin,row.destination,row.departure_date].join('|');if(!days.has(key)||Number(row.price)<Number(days.get(key).price))days.set(key,row)}
    return [...days.values()].sort((a,b)=>a.departure_date.localeCompare(b.departure_date)||Number(a.price)-Number(b.price));
  }
  function render(){
    const available=availableRows();resultOptions(available);resultMonthOptions(available);
    const allScope=q('#resultScope').value==='all',filtered=filterRows(available,q('#resultOrigin').value,q('#resultDestination').value,q('#resultSort').value,q('#resultMonth')?.value||''),rows=filtered.slice(0,100),stats=data.stats||{},req=data.request||{},hist=data.history_summary||{};
    q('#resultCaption').textContent=`${filtered.length} opções encontradas${filtered.length>100?' · exibindo as primeiras 100':''} · ${q('#resultScope').value==='all'?'Buscas salvas — confira o preço atualizado ao abrir o voo':(req.origin&&req.destination?routeLabel(req):'Escolha a rota para pesquisar')}`;
    q('#monthRows').innerHTML=rows.map((x,i)=>`<tr><td><span class="month-rank">${i+1}</span></td><td><b>${esc(airportName(x.origin))}</b><small class="statline">${esc(x.origin)}</small></td><td><b>${esc(airportName(x.destination))}</b><small class="statline">${esc(x.destination)}</small></td><td><b>${fmtDate(x.departure_date)}</b></td><td><b>${fmtDate(x.return_date)}</b></td><td>${Number(x.trip_days||0)} dias</td><td class="month-result-price">${money(x.price)}<br>${trendHtml(x)}</td><td>${x.previous_price==null?'—':`${money(x.previous_price)} → ${money(x.price)}`}</td><td><b>${esc(x.airline||'Google Flights')}</b><small class="statline">${esc(x.stops||'')} ${x.duration?'· '+esc(x.duration):''}</small></td><td><a class="btn" href="${esc(flightLink(x))}" target="_blank" rel="noopener">Ver voo</a></td></tr>`).join('');
    q('#monthEmpty').hidden=rows.length>0;
    if(allScope){const histPrices=filtered.map(x=>Math.min(Number(x.price)||Infinity,Number(x.historical_min)||Infinity)).filter(Number.isFinite);q('#monthLowest').textContent=money(histPrices.length?Math.min(...histPrices):null);q('#monthLowest').parentElement.querySelector('span').textContent='Menor histórico salvo';q('#monthCombos').textContent=String(filtered.length);q('#monthPriced').textContent=filtered.length?'dados salvos':'0';q('#monthCount').textContent=filtered.length?`${Math.min(filtered.length,100)}/${filtered.length}`:'—';q('#monthHistory').textContent=filtered.length?'histórico preservado':'sem dados';}else{q('#monthLowest').parentElement.querySelector('span').textContent='Menor preço';q('#monthLowest').textContent=money(stats.lowest_price);const processed=stats.processed_combinations??stats.combinations;q('#monthCombos').textContent=stats.combinations!=null?`${processed}/${stats.combinations}`:'—';q('#monthPriced').textContent=stats.priced_combinations!=null?`${stats.priced_combinations} · ${stats.coverage_pct||0}%`:'—';q('#monthCount').textContent=data.results?.length?`${data.results.length}/100`:'—';q('#monthHistory').textContent=(hist.compared||hist.cheaper||hist.higher)?`↓${hist.cheaper||0} ↑${hist.higher||0}`:'sem comparação';}
    if(data.updated_at||data.generated_at)q('#monthSearchUpdated').textContent=`Salvo ${fmtDateTime(data.updated_at||data.generated_at)} · ${req.origin||''}→${req.destination||''}`;
    const daily=calendarRows(filtered),cal=q('#monthCalendar');
    if(daily.length){const low=Math.min(...daily.map(x=>Number(x.price)||Infinity));cal.innerHTML=daily.map(x=>{const d=Number((x.departure_date||'').slice(-2)),hot=Number(x.price)<=low*1.06?' hot':'';return`<a class="month-day${hot}" href="${esc(flightLink(x))}" target="_blank" rel="noopener" aria-label="${esc(`Pesquisar ${routeLabel(x)}, ida ${fmtDate(x.departure_date)}, volta ${fmtDate(x.return_date)}`)}"><b>${fmtDate(x.departure_date)}</b><small class="month-route">${esc(routeLabel(x))}</small><strong>${money(x.price)}</strong><small class="statline">volta ${fmtDate(x.return_date)} · ${Number(x.trip_days||0)} dias</small>${trendHtml(x)}<small class="statline">Pesquisar este voo ↗</small></a>`}).join('');q('#monthCalendarEmpty').hidden=true;}else{cal.innerHTML='';q('#monthCalendarEmpty').hidden=false;}
    const compared=rows.filter(x=>x.previous_price!=null).sort((a,b)=>Math.abs(Number(b.change_pct||0))-Math.abs(Number(a.change_pct||0)));
    q('#monthHistoryRows').innerHTML=compared.map(x=>`<tr><td class="month-route">${esc(routeLabel(x))}</td><td><b>${fmtDate(x.departure_date)}</b></td><td><b>${fmtDate(x.return_date)}</b></td><td class="month-result-price">${money(x.price)}</td><td>${money(x.previous_price)}</td><td class="history-diff ${esc(x.trend||'same')}">${x.trend==='down'?'↓':x.trend==='up'?'↑':'='} ${x.change_amount==null?'—':money(Math.abs(x.change_amount))} ${x.change_pct==null?'':`(${Math.abs(Number(x.change_pct)).toFixed(1)}%)`}</td><td>${money(x.historical_min)}</td><td>${Number(x.history_samples||0)}</td></tr>`).join('');
    q('#monthHistoryEmpty').hidden=compared.length>0;setResultView(resultView);
  }

  function clearForSearch(request,total){q('#resultScope').value='current';q('#resultOrigin').value='';q('#resultDestination').value='';if(q('#resultMonth'))q('#resultMonth').value='';data={request:{origin:request.origin,destination:request.destination,month:request.month,period_mode:request.period_mode,start_date:request.start_date,end_date:request.end_date,max_stops:request.max_stops},stats:{combinations:total,processed_combinations:0,priced_combinations:0,coverage_pct:0},results:[],daily_min:[],history_summary:{}};render();}
  function showProgress(total){q('#monthProgress').hidden=false;q('#monthStopButton').disabled=false;updateProgress({pct:0,stage:'Enviando solicitação…',done:0,total,priced:0,remaining:total,elapsed:0,detail:'envio ainda não confirmado'});}
  function updateProgress({pct,stage,done,total,priced,remaining,elapsed,detail}){pct=Math.max(0,Math.min(100,Math.round(Number(pct)||0)));done=Math.max(0,Math.min(Number(total)||0,Math.round(Number(done)||0)));q('#monthProgressFill').style.width=`${pct}%`;q('#monthProgressPct').textContent=`${pct}%`;q('#monthProgressStage').textContent=stage||'Pesquisa em andamento…';q('#monthProgressCombos').textContent=`${done} / ${total} combinações`;q('#monthProgressPriced').textContent=`${Number(priced||0)} com preço`;q('#monthProgressRemaining').textContent=`faltam ${remaining==null?Math.max(0,total-done):Math.max(0,remaining)}`;q('#monthProgressElapsed').textContent=`${Math.max(0,Math.round(elapsed||0))}s`;q('#monthProgressSaved').textContent=detail||'✓ salvamento automático';}

  async function requestJson(url){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try{const r=await fetch(`${url}${url.includes('?')?'&':'?'}t=${Date.now()}`,{cache:'no-store',signal:controller.signal});if(!r.ok)throw new Error(`HTTP ${r.status}`);return await r.json();}finally{clearTimeout(timer)}
  }
  async function loadConfig(){try{const c=await requestJson('./data/flight-search-config.json');apiBase=String(c.api_base||'').replace(/\/$/,'')}catch{}}
  async function fetchJson(url){try{return await requestJson(url)}catch{return null}}
  function bridgeProgress(request){
    return new Promise(resolve=>{
      if(!apiBase){resolve(null);return;}
      const callback='flightProgress_'+String(request.request_id||'').replace(/[^A-Za-z0-9_$]/g,'_');
      const script=document.createElement('script');
      let finished=false;
      const finish=value=>{if(finished)return;finished=true;clearTimeout(timer);try{script.remove()}catch{};try{delete window[callback]}catch{};resolve(value)};
      const timer=setTimeout(()=>finish(null),8000);
      window[callback]=value=>finish(value);
      script.onerror=()=>finish(null);
      script.src=`${apiBase}?route=${encodeURIComponent(`api/progress/${request.request_id}`)}&callback=${encodeURIComponent(callback)}&t=${Date.now()}`;
      document.head.appendChild(script);
    });
  }
  async function loadSavedPairs(){const saved=await fetchJson('./data/flight-price-history.json');if(saved?.pairs)savedPairs=saved.pairs;}
  async function loadLastResult(){const[final,live]=await Promise.all([fetchJson(RESULT_RAW),fetchJson(LIVE_RAW)]);const ft=Date.parse(final?.updated_at||final?.generated_at||'')||0,lt=Date.parse(live?.updated_at||live?.generated_at||'')||0;const chosen=lt>ft?live:final;if(chosen&&chosen.results)data=chosen;}

  function resultMatches(result,request,started){
    if(!result?.request)return false;
    const r=result.request;
    if(r.origin!==request.origin||r.destination!==request.destination||Number(r.max_stops)!==Number(request.max_stops))return false;
    if(request.period_mode==='range'){
      if(r.period_mode!=='range'||r.start_date!==request.start_date||r.end_date!==request.end_date)return false;
    }else if(r.month!==request.month||r.period_mode==='range')return false;
    if(request.request_id)return result.request_id===request.request_id;
    const t=Date.parse(result.started_at||result.generated_at||'');
    return Number.isFinite(t)&&t>=started-30000;
  }
  function liveProgress(live,elapsed){const s=live.stats||{},stage=live.stage||'starting',total=Number(s.combinations||0),primary=Number(s.primary_completed??s.processed_combinations??0),primaryTotal=Number(s.primary_total||total),fb=Number(s.fallback_done||0),fbTotal=Number(s.fallback_total||0),priced=Number(s.priced_combinations||0),resume=live.resume||{},reused=Number(resume.reused_combinations||0);let pct=0,label='Preparando pesquisa…',done=Math.min(primary,total),remaining=Math.max(0,total-done),detail=reused?`${reused} combinações reaproveitadas da última hora`:'aguardando primeiro lote';if(stage==='multisource'){pct=total?done/total*100:0;label=`Google Flights · ${done}/${total}`;remaining=Math.max(0,total-done);detail=`${reused?reused+' reaproveitadas · ':''}${Number(resume.searched_this_run||0)} pesquisadas agora · ${priced} com preço · checkpoint automático`;}else if(stage==='google'){pct=primaryTotal?primary/primaryTotal*100:0;label=`Etapa 1/2 · Google Flights · ${primary}/${primaryTotal}`;remaining=Math.max(0,primaryTotal-primary);detail=live.current_pair?`Consultando ${fmtDate(live.current_pair.departure_date)} → ${fmtDate(live.current_pair.return_date)} · salvo automaticamente`:`${priced} com preço · salvo automaticamente`;}else if(stage==='fallback'){pct=fbTotal?fb/fbTotal*100:0;label=`Etapa 2/2 · Confirmação · ${fb}/${fbTotal}`;done=total;remaining=Math.max(0,fbTotal-fb);detail=`${priced} combinações com preço · resultados salvos`;}else if(stage==='completed'){pct=100;label='Pesquisa concluída';done=total;remaining=0;detail=`Resultado salvo${reused?' · '+reused+' combinações reaproveitadas da última hora':''}`;}else if(stage==='interrupted'){pct=primaryTotal?primary/primaryTotal*100:0;label='Pesquisa interrompida · parcial preservado';detail=`Checkpoint salvo${reused?' · '+reused+' combinações reaproveitadas':''}`;}return{pct,stage:label,done,total,priced,remaining,elapsed,detail};}

  async function fetchRunState(request,started,total){try{const runs=(await requestJson(ACTIONS_RUNS)).workflow_runs||[];const run=runs.find(x=>{const created=Date.parse(x.created_at||'');const title=String(x.display_title||'');return title.startsWith(`Busca ${request.request_id} ·`)&&title.includes(`${request.dispatch_origin} → ${request.destination}`)});if(!run)return null;activeRun=run;if(run.status==='queued')return{pct:0,stage:'Na fila do GitHub Actions…',done:0,total,priced:0,detail:'na fila',run};if(run.status==='completed'){if(run.conclusion==='success')return{pct:100,stage:'Execução concluída · carregando resultado…',done:total,total,priced:Number(data.stats?.priced_combinations||0),detail:'publicando',run};if(run.conclusion==='cancelled')return{cancelled:true,run};return{failed:true,error:`A execução terminou com status ${run.conclusion||'erro'}.`,run};}const jobs=(await fetchJson(ACTIONS_RUN(run.id)))?.jobs||[],steps=jobs[0]?.steps||[],current=steps.find(s=>s.status==='in_progress')||[...steps].reverse().find(s=>s.status==='completed'),name=String(current?.name||'Preparando ambiente');return{pct:0,stage:name==='Pesquisar matriz completa do período'?'Motor iniciado · aguardando primeiro lote…':name==='Dependências'?'Preparando motor de pesquisa…':'Preparando pesquisa…',done:0,total,priced:0,detail:name,run};}catch{return null}}

  async function pollSearch(request,started,total){const status=q('#monthSearchStatus');let lastActionsCheck=0,state=null,lastLiveVersion='';for(let i=0;i<675;i++){if(stopRequested)throw new Error('__STOPPED__');await sleep(4000);if(stopRequested)throw new Error('__STOPPED__');const elapsed=Math.round((Date.now()-started)/1000);const live=await fetchJson(LIVE_RAW),matchedLive=resultMatches(live,request,started);if(matchedLive){data=live;const version=live.updated_at||JSON.stringify(live.stats);if(version!==lastLiveVersion){render();lastLiveVersion=version;}const p=liveProgress(live,elapsed);updateProgress(p);status.className=live.status==='partial'?'month-search-status bad':'month-search-status wait';status.textContent=live.status==='partial'?'⚠ A execução parou, mas todos os resultados encontrados até aqui foram preservados.':`🔎 ${p.stage} Os resultados já encontrados estão sendo salvos e exibidos abaixo.`;if(live.status==='completed'||live.status==='partial')return live;}
      if(Date.now()-lastActionsCheck>20000){lastActionsCheck=Date.now();const [a,bridge]=await Promise.all([fetchRunState(request,started,total),bridgeProgress(request)]);if(stopRequested)throw new Error('__STOPPED__');if(!matchedLive&&bridge?.status==='error')throw new Error(bridge.error||'O serviço recusou a pesquisa.');if(a)state=a;if(!state&&bridge&&['received','queued','running','completed','done'].includes(bridge.status)){const bs=String(bridge.status||'');state={pct:(bs==='completed'||bs==='done')?100:0,stage:bs==='queued'?'Pesquisa recebida · aguardando GitHub Actions…':bs==='completed'||bs==='done'?'Finalizando resultado…':'Pesquisa confirmada pelo serviço…',done:Number(bridge.completed||0),total:Number(bridge.total||total),priced:Number(bridge.priced||0),detail:bridge.message||'serviço confirmou o envio'};}if(a?.failed){if(data.results?.length){status.className='month-search-status bad';status.textContent='⚠ A execução terminou com erro, mas os achados parciais exibidos abaixo ficaram salvos.';return {...data,status:'partial'};}throw new Error(a.error)}if(a?.cancelled&&!stopRequested){if(data.results?.length)return {...data,status:'partial'};throw new Error('A pesquisa foi cancelada no servidor.')}}
      if(!matchedLive&&state)updateProgress({...state,elapsed,priced:Number(data.stats?.priced_combinations||0),remaining:Math.max(0,total-Number(state.done||0))});
      if(!matchedLive&&!state){
        updateProgress({pct:0,stage:'Aguardando confirmação do serviço…',done:0,total,priced:0,elapsed,detail:'envio ainda não confirmado'});
        status.textContent='Aguardando o serviço aceitar a pesquisa. O início ainda não foi confirmado.';
        if(Date.now()-started>120000){status.className='month-search-status wait';status.textContent='⏳ A confirmação está demorando, mas a pesquisa pode estar rodando. O sistema continuará acompanhando automaticamente.';}if(Date.now()-started>900000)throw new Error('O serviço não confirmou o início após 15 minutos. Tente novamente.');
      }
      const final=await fetchJson(RESULT_RAW);if(final&&resultMatches(final,request,started)&&final.status!=='running'){data=final;render();return final;}
    }throw new Error('A busca excedeu o tempo máximo de espera.');}

  function postBridge(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    const url=`${apiBase}?route=${encodeURIComponent(path)}&t=${Date.now()}`;
    return fetch(url,{method:'POST',mode:'no-cors',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(body)}).finally(()=>clearTimeout(timer));
  }
  function dispatchWithoutCors(request){
    // An opaque response cannot confirm acceptance. Poll the job even if its redirect stalls.
    postBridge('api/search',{origin:request.dispatch_origin,destination:request.destination,month:request.month,period_mode:request.period_mode,start_date:request.start_date,end_date:request.end_date,max_stops:request.max_stops,request_id:request.request_id}).catch(()=>{});
  }
  async function stopSearch(){
    if(!searching)return;stopRequested=true;
    q('#monthStopButton').disabled=true;
    const status=q('#monthSearchStatus');status.className='month-search-status bad';
    status.textContent='Acompanhamento interrompido. Solicitando cancelamento da pesquisa no servidor.';
    postBridge('api/cancel',{request_id:activeRequest.request_id}).catch(()=>{});
  }

  function validateRequest(request){if(!/^[A-Z]{3}$/.test(request.destination))return'Escolha uma cidade/aeroporto válido, por exemplo Miami ou MIA.';if(request.period_mode==='month'&&!/^\d{4}-\d{2}$/.test(request.month))return'Escolha o mês da viagem.';if(request.period_mode==='range'){if(!request.start_date||!request.end_date)return'Informe a data inicial e a data final.';if(request.end_date<=request.start_date)return'A data final precisa ser depois da data inicial.';}if(request.origin===request.destination)return'Origem e destino não podem ser iguais.';return'';}
  async function searchInsidePage(){if(searching)return;const request=formRequest(),status=q('#monthSearchStatus'),button=q('#monthSearchButton'),error=validateRequest(request);
    if((request.origins||[]).length>1){
      if(error){status.className='month-search-status bad';status.textContent=error;return}
      const group=request.origins.filter(code=>code!==request.destination);
      if(!group.length){status.className='month-search-status bad';status.textContent='O destino já está dentro do grupo de aeroportos escolhido.';return}
      status.className='month-search-status wait';status.textContent='🔎 Pesquisa agrupada: '+group.join(' + ')+'. As buscas serão executadas uma após a outra.';
      for(const code of group){q('#monthOrigin').value=code;await searchInsidePage();while(searching)await sleep(500);}
      q('#monthOrigin').value=request.origin;const hint=q('#originGroupHint');if(hint)hint.textContent='Inclui '+request.origins.join(', ');q('#resultScope').value='all';render();return;
    }if(error){status.className='month-search-status bad';status.textContent=error;return}if(!apiBase)await loadConfig();if(!apiBase){status.className='month-search-status bad';status.textContent='O serviço de pesquisa ainda não está conectado. Atualize a página e tente novamente.';return}const total=comboTotal(request);if(total<1){status.className='month-search-status bad';status.textContent='Esse período não possui combinações futuras de ida e volta.';return}
    request.request_id='web_'+(globalThis.crypto&&typeof globalThis.crypto.randomUUID==='function'?globalThis.crypto.randomUUID().replace(/-/g,''):(Date.now().toString(36)+Math.random().toString(36).slice(2)+Math.random().toString(36).slice(2))).slice(0,64);searching=true;stopRequested=false;activeRun=null;activeRequest=request;button.disabled=true;button.textContent='⏳ Pesquisando…';clearForSearch(request,total);showProgress(total);status.className='month-search-status wait';status.textContent='🔎 Pesquisa enviada. Confirmando recebimento pelo serviço…';await trackSearch(request,Date.now(),total,true);}
  async function trackSearch(request,started,total,dispatch=false){const button=q('#monthSearchButton'),status=q('#monthSearchStatus');const clock=setInterval(()=>{q('#monthProgressElapsed').textContent=`${Math.round((Date.now()-started)/1000)}s`},1000);try{if(dispatch)dispatchWithoutCors(request);data=await pollSearch(request,started,total);render();updateProgress({pct:data.status==='partial'?liveProgress(data,0).pct:100,stage:data.status==='partial'?'Parcial preservado':'Pesquisa concluída',done:Number(data.stats?.processed_combinations??data.stats?.combinations??total),total:Number(data.stats?.combinations||total),priced:Number(data.stats?.priced_combinations||0),remaining:0,elapsed:(Date.now()-started)/1000,detail:'✓ resultado salvo'});q('#monthStopButton').disabled=true;status.className=data.status==='partial'?'month-search-status bad':'month-search-status ok';status.textContent=data.status==='partial'?'⚠ A pesquisa parou antes do fim, mas tudo o que havia sido encontrado ficou salvo.':`✅ Busca concluída. ${data.stats?.priced_combinations||0} combinações com preço foram salvas.`;}catch(e){if(String(e.message||e)==='__STOPPED__'){status.className='month-search-status bad';status.textContent='⛔ Acompanhamento interrompido. O cancelamento no servidor foi solicitado; os achados salvos permanecem abaixo.';}else{status.className='month-search-status bad';status.textContent=`Não foi possível concluir a busca: ${e.message||e}. Se já havia resultados, eles permanecem salvos.`;}}finally{clearInterval(clock);if(stopRequested||data.status!=='completed'){q('#monthProgressStage').textContent=stopRequested?'Acompanhamento interrompido':'Pesquisa não concluída';}searching=false;button.disabled=false;button.textContent='🔎 Pesquisar agora';const stop=q('#monthStopButton');stop.disabled=true;stop.textContent='■ Parar pesquisa';}}

  async function boot(){
    await Promise.all([loadConfig(),loadLastResult(),loadSavedPairs()]);render();periodModeChanged();
    const started=Date.parse(data.started_at||'');
    if(data.status==='running'&&data.request_id&&Number.isFinite(started)&&Date.now()-started<45*60000&&!searching){
      const request={...data.request,request_id:data.request_id};
      request.dispatch_origin=request.period_mode==='range'?encodeRangeOrigin(request.origin,request.start_date,request.end_date):request.origin;
      activeRequest=request;searching=true;stopRequested=false;
      q('#monthSearchButton').disabled=true;q('#monthSearchButton').textContent='⏳ Pesquisando…';
      showProgress(Number(data.stats?.combinations||0));updateProgress(liveProgress(data,(Date.now()-started)/1000));
      trackSearch(request,started,Number(data.stats?.combinations||0));
    }
  }
  function setFocus(on){document.body.classList.toggle('flight-search-focus',!!on)}
  function activate(){document.querySelectorAll('#flightTabs .tab').forEach(x=>x.classList.remove('active'));btn.classList.add('active');['hunterPanel','radarPanel','externalPanel','airlinesPanel'].forEach(id=>{const el=q('#'+id);if(el)el.hidden=true});panel.hidden=false;setFocus(true);render();}

  for(const id of ['#resultScope','#resultOrigin','#resultDestination','#resultMonth','#resultSort']){const el=q(id);if(el)el.addEventListener('change',()=>{render();if(id==='#resultScope'&&el.value==='all')loadSavedPairs().then(render)});}
  q('#showSavedSearches').addEventListener('click',()=>{q('#resultScope').value='all';render();loadSavedPairs().then(render)});
  q('#showCurrentSearch').addEventListener('click',()=>{q('#resultScope').value='current';for(const id of ['#resultOrigin','#resultDestination','#resultMonth'])q(id).value='';render()});
  const reportStartError=e=>{const status=q('#monthSearchStatus');if(status){status.className='month-search-status bad';status.textContent='Não foi possível iniciar a pesquisa: '+String(e&&e.message?e.message:e||'erro desconhecido');}console.error('flight-search-start',e);};
  const searchBtn=q('#monthSearchButton');if(searchBtn)searchBtn.addEventListener('click',e=>{e.preventDefault();if(searching){const status=q('#monthSearchStatus');if(status){status.className='month-search-status wait';status.textContent='Já existe uma pesquisa em andamento. Aguarde a conclusão ou use Parar pesquisa.';}return;}Promise.resolve(searchInsidePage()).catch(reportStartError);});
  const stopBtn=q('#monthStopButton');if(stopBtn)stopBtn.addEventListener('click',e=>{e.preventDefault();Promise.resolve(stopSearch()).catch(reportStartError);});
  const periodMode=q('#monthPeriodMode');if(periodMode)periodMode.addEventListener('change',periodModeChanged);
  const rangeStartEl=q('#rangeStart');if(rangeStartEl)rangeStartEl.addEventListener('change',()=>{const end=q('#rangeEnd');if(end&&end.value<rangeStartEl.value)end.value=rangeStartEl.value});
  document.querySelectorAll('.month-view-btn').forEach(b=>b.addEventListener('click',()=>setResultView(b.dataset.resultView)));
  btn.addEventListener('click',activate);document.querySelectorAll('#flightTabs .tab').forEach(b=>{if(b!==btn)b.addEventListener('click',()=>{panel.hidden=true;setFocus(false)})});const productsMain=document.querySelector('.main-tab[data-main="products"]');if(productsMain)productsMain.addEventListener('click',()=>{panel.hidden=true;setFocus(false)});const flightsMain=document.querySelector('.main-tab[data-main="flights"]');if(flightsMain)flightsMain.addEventListener('click',()=>{if(btn.classList.contains('active')&&!panel.hidden)setFocus(true)});document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!searching){loadConfig();loadLastResult().then(render)}});boot();
})();
