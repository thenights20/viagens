(() => {
  const q = s => document.querySelector(s);
  const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safe = (u='') => { try { const x=new URL(u); return x.protocol==='https:'?x.href:'#'; } catch { return '#'; } };
  const fmtDate = v => { if(!v) return '—'; const [y,m,d]=String(v).slice(0,10).split('-').map(Number); return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(y,m-1,d)); };
  const fmtMiles = v => Number.isFinite(Number(v)) && Number(v) > 0 ? `${new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0}).format(Number(v))} milhas` : '—';
  const norm = s => String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();

  const tabs = q('#flightTabs');
  const app = q('#flightsApp');
  if (!tabs || !app || q('#milesSearchPanel')) return;

  let data = {version:'0.2.0',generated_at:null,results:[],sources:{}};
  let activeQuery = null;
  let apiBase = '';
  let searching = false;
  const RESULT_RAW = './data/miles-search.json';
  const AIRPORTS_WORLD = './data/airports-world.json';
  const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
  let worldAirports = [];
  let worldAirportByCode = new Map();
  const airportSuggestIndex = {origin:-1,destination:-1};

  const PROGRAMS = {
    Smiles: {
      label: 'Smiles',
      url: 'https://www.smiles.com.br/home',
      note: 'Resgate com milhas Smiles'
    },
    'LATAM Pass': {
      label: 'LATAM Pass',
      url: 'https://www.latamairlines.com/br/pt',
      note: 'Resgate com Milhas LATAM Pass'
    },
    'Azul Fidelidade': {
      label: 'Azul Fidelidade',
      url: 'https://www.voeazul.com.br/br/pt/home',
      note: 'Resgate com pontos/milhas Azul Fidelidade'
    },
    AAdvantage: {
      label: 'American Airlines · AAdvantage',
      url: 'https://www.aa.com/booking/search/find-flights?anchorEvent=false&from=comp_nav&locale=pt_BR&tripType=roundTrip',
      note: 'Resgate com milhas AAdvantage'
    }
  };

  const style = document.createElement('style');
  style.textContent = `
    .miles-titlebar{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:1px 0 6px;flex-wrap:wrap}.miles-titlebar strong{font-size:16px}.miles-titlebar small{display:block;color:var(--muted);font-size:11px;margin-top:2px}.miles-titlebar .pill{padding:6px 9px;font-size:11px}
    .miles-search-grid{display:grid;grid-template-columns:1.05fr 1.25fr .85fr 1.25fr .95fr .9fr auto;gap:7px;align-items:end;padding:9px}.miles-search-grid label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;margin:0 0 4px}.miles-search-grid input,.miles-search-grid select{padding:8px 9px;border-radius:9px;min-height:37px}.miles-airport-field{position:relative}.miles-airport-suggest{position:absolute;z-index:90;left:0;right:0;top:calc(100% + 4px);max-height:330px;overflow:auto;background:var(--panel2);border:1px solid var(--line);border-radius:11px;box-shadow:0 18px 45px rgba(0,0,0,.42);padding:4px}.miles-airport-suggest[hidden]{display:none}.miles-airport-option{display:block;width:100%;border:0;background:transparent;color:var(--text);text-align:left;padding:8px 9px;border-radius:8px;cursor:pointer}.miles-airport-option:hover,.miles-airport-option.active{background:rgba(119,167,255,.13)}.miles-airport-option b{display:block;font-size:12px}.miles-airport-option small{display:block;color:var(--muted);font-size:10px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.miles-airport-loading{padding:9px;color:var(--muted);font-size:11px}.miles-period-range{display:grid;grid-template-columns:1fr 1fr;gap:6px}.miles-search-btn{border:0;background:var(--accent);color:#07111f;font-weight:900;border-radius:9px;padding:9px 13px;cursor:pointer;min-height:37px;white-space:nowrap}.miles-search-btn:hover{filter:brightness(1.07)}
    .miles-status{padding:8px 10px;border-top:1px solid var(--line);color:var(--muted);font-size:11px;line-height:1.45}.miles-status.ok{color:var(--ok)}.miles-status.warn{color:var(--warn)}.miles-status.bad{color:var(--hot)}
    .miles-value{font-size:18px;font-weight:900;white-space:nowrap;color:var(--ok)}.miles-program{font-weight:900}.miles-provider-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.miles-provider-actions a{display:inline-flex;align-items:center;text-decoration:none;border:1px solid var(--line);background:var(--panel);color:var(--text);padding:8px 10px;border-radius:9px;font-size:11px;font-weight:800}.miles-provider-actions a:hover{border-color:var(--accent)}
    .miles-source-health{margin-top:10px}.miles-note strong{color:var(--text)}
    @media(max-width:1180px){.miles-search-grid{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:760px){.miles-search-grid{grid-template-columns:1fr 1fr}.miles-search-grid .miles-airport-field,.miles-search-grid .miles-period-cell,.miles-search-grid .miles-search-action{grid-column:1/-1}.miles-search-btn{width:100%}}
  `;
  document.head.appendChild(style);

  const btn = document.createElement('button');
  btn.className = 'tab';
  btn.dataset.flightView = 'miles';
  btn.textContent = '⭐ Buscar por milhas';
  const monthBtn = tabs.querySelector('[data-flight-view="monthsearch"]');
  if (monthBtn && monthBtn.nextSibling) tabs.insertBefore(btn, monthBtn.nextSibling);
  else if (monthBtn) tabs.appendChild(btn);
  else tabs.insertBefore(btn, tabs.children[1] || null);

  const panel = document.createElement('div');
  panel.id = 'milesSearchPanel';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="miles-titlebar">
      <div><strong>⭐ Buscar passagens por milhas · v0.2.0</strong><small>Mesmo modelo de período da busca paga: mês inteiro ou intervalo de datas. A tabela exibe somente milhas.</small></div>
      <div class="pill"><span class="dot"></span><span id="milesUpdated">Aguardando consulta</span></div>
    </div>
    <section class="panel">
      <div class="miles-search-grid">
        <div class="miles-airport-field"><label>Origem</label><input id="milesOrigin" placeholder="Ex.: Orlando, MCO ou aeroporto" autocomplete="off" spellcheck="false"><div id="milesOriginSuggest" class="miles-airport-suggest" hidden></div></div>
        <div class="miles-airport-field"><label>Destino</label><input id="milesDestination" placeholder="Ex.: Miami, MIA ou aeroporto" autocomplete="off" spellcheck="false"><div id="milesDestinationSuggest" class="miles-airport-suggest" hidden></div></div>
        <div><label>Período</label><select id="milesPeriodMode"><option value="month">Mês inteiro</option><option value="range">Intervalo de datas</option></select></div>
        <div class="miles-period-cell"><div id="milesPeriodMonth"><label>Mês a pesquisar</label><input id="milesMonthValue" type="month"></div><div id="milesPeriodRange" hidden><label>Datas</label><div class="miles-period-range"><input id="milesRangeStart" type="date" title="Data inicial"><input id="milesRangeEnd" type="date" title="Data final"></div></div></div>
        <div><label>Programa</label><select id="milesProgram"><option value="">Todos os programas</option><option value="Smiles">Smiles</option><option value="LATAM Pass">LATAM Pass</option><option value="Azul Fidelidade">Azul Fidelidade</option><option value="AAdvantage">American Airlines · AAdvantage</option></select></div>
        <div><label>Cabine</label><select id="milesCabin"><option value="">Qualquer cabine</option><option value="economy" selected>Econômica</option><option value="premium_economy">Premium Economy</option><option value="business">Executiva</option><option value="first">Primeira classe</option></select></div>
        <div class="miles-search-action"><button type="button" class="miles-search-btn" id="milesSearchButton">⭐ Pesquisar milhas</button></div>
      </div>
      <div class="miles-status" id="milesStatus">Escolha a rota e o período para consultar os resultados em milhas.</div>
    </section>

    <section class="cards">
      <div class="card"><span>Resultados</span><b id="milesResultCount">0</b></div>
      <div class="card"><span>Menor resgate</span><b id="milesLowest">—</b></div>
      <div class="card"><span>Programas pesquisados</span><b id="milesProgramCount">4</b></div>
      <div class="card"><span>Unidade exibida</span><b style="font-size:19px">Milhas</b></div>
    </section>

    <section class="panel">
      <div class="table-wrap"><table><thead><tr><th>Programa</th><th>Rota</th><th>Datas</th><th>Cabine</th><th>Valor</th><th></th></tr></thead><tbody id="milesRows"></tbody></table></div>
      <div class="empty" id="milesEmpty"><strong>Nenhum valor em milhas para esta consulta.</strong>A tabela não converte preços em reais nem cria estimativas. Só entram valores de resgate efetivamente coletados.</div>
    </section>

    <div class="source-row miles-source-health" id="milesSources"></div>
    <div class="note miles-note"><strong>Fontes incluídas:</strong> Smiles, LATAM Pass, Azul Fidelidade e American Airlines AAdvantage. Taxas, dinheiro + milhas e conversões para reais não são exibidos nesta aba.
      <div class="miles-provider-actions" id="milesProviderActions"></div>
    </div>
  `;
  app.appendChild(panel);

  function fallbackAirports(){
    const out=[],seen=new Set();
    const add=(code,name,city='')=>{code=String(code||'').trim().toUpperCase();if(!/^[A-Z]{3}$/.test(code)||seen.has(code))return;seen.add(code);out.push({code,name:String(name||'').trim(),city:String(city||name||'').trim(),state:'',country:''});};
    const paidOrigin=q('#monthOrigin');
    if(paidOrigin)for(const opt of paidOrigin.options)add(optionCode(opt),opt.textContent||opt.label||'',opt.textContent||opt.label||'');
    const paidDest=q('#monthDestinations');
    if(paidDest)for(const opt of paidDest.options)add(optionCode(opt),opt.value||opt.label||opt.textContent||'',opt.value||opt.label||opt.textContent||'');
    [['GRU','Guarulhos'],['CGH','São Paulo / Congonhas'],['VCP','Campinas / Viracopos'],['GIG','Rio de Janeiro / Galeão'],['MCO','Orlando'],['MIA','Miami'],['JFK','Nova York / JFK'],['EWR','Nova York / Newark']].forEach(x=>add(x[0],x[1],x[1]));
    return out;
  }

  function setWorldAirports(list){
    const seen=new Set(),clean=[];
    for(const raw of (Array.isArray(list)?list:[])){
      const code=String(raw.code||raw.iata||'').trim().toUpperCase();
      if(!/^[A-Z]{3}$/.test(code)||seen.has(code))continue;
      seen.add(code);
      clean.push({code,name:String(raw.name||'').trim(),city:String(raw.city||'').trim(),state:String(raw.state||'').trim(),country:String(raw.country||'').trim().toUpperCase()});
    }
    worldAirports=clean.length?clean:fallbackAirports();
    worldAirportByCode=new Map(worldAirports.map(a=>[a.code,a]));
  }

  function airportDisplay(a){
    const place=a.city||a.name||a.code,name=a.name&&norm(a.name)!==norm(place)?` — ${a.name}`:'',where=[a.state,a.country].filter(Boolean).join(', ');
    return `${place}${name}${where?` · ${where}`:''} (${a.code})`;
  }

  function airportMatches(term){
    const n=norm(term);if(!n)return[];
    const source=worldAirports.length?worldAirports:fallbackAirports();
    return source.map(a=>{
      const c=norm(a.code),city=norm(a.city),name=norm(a.name),state=norm(a.state),country=norm(a.country),hay=`${c} ${city} ${name} ${state} ${country}`;
      let score=99;
      if(c===n)score=0;else if(c.startsWith(n))score=1;else if(city===n)score=2;else if(city.startsWith(n))score=3;else if(name.startsWith(n))score=4;else if(state.startsWith(n)||country===n)score=5;else if(hay.includes(n))score=6;
      return{a,score};
    }).filter(x=>x.score<99).sort((x,y)=>x.score-y.score||String(x.a.city||x.a.name).localeCompare(String(y.a.city||y.a.name),'pt-BR')).slice(0,12).map(x=>x.a);
  }

  function airportInput(kind){return q(kind==='origin'?'#milesOrigin':'#milesDestination');}
  function airportBox(kind){return q(kind==='origin'?'#milesOriginSuggest':'#milesDestinationSuggest');}

  function hideAirportSuggestions(kind){
    const box=airportBox(kind);
    if(box){box.hidden=true;box.innerHTML='';}
    airportSuggestIndex[kind]=-1;
  }

  function chooseAirport(kind,a){
    const input=airportInput(kind);if(!input)return;
    input.value=airportDisplay(a);
    input.dataset.iata=a.code;
    hideAirportSuggestions(kind);
  }

  function renderAirportSuggestions(kind,term){
    const box=airportBox(kind);if(!box)return;
    const matches=airportMatches(term);airportSuggestIndex[kind]=-1;
    if(!String(term||'').trim()){hideAirportSuggestions(kind);return;}
    if(!matches.length){box.innerHTML='<div class="miles-airport-loading">Nenhum aeroporto encontrado. Digite o código IATA de 3 letras ou tente o nome da cidade.</div>';box.hidden=false;return;}
    box.innerHTML=matches.map((a,i)=>`<button type="button" class="miles-airport-option" data-airport-index="${i}" data-airport-code="${esc(a.code)}"><b>${esc(a.code)} · ${esc(a.city||a.name||a.code)}</b><small>${esc([a.name,a.state,a.country].filter(Boolean).join(' · '))}</small></button>`).join('');
    box.hidden=false;
    box.querySelectorAll('.miles-airport-option').forEach((el,i)=>el.addEventListener('pointerdown',ev=>{ev.preventDefault();chooseAirport(kind,matches[i]);}));
  }

  async function loadWorldAirports(){
    setWorldAirports(fallbackAirports());
    for(const kind of ['origin','destination']){const input=airportInput(kind);if(input)input.title='Carregando base mundial de aeroportos…';}
    try{
      const r=await fetch(AIRPORTS_WORLD,{cache:'force-cache'});if(!r.ok)throw new Error('HTTP '+r.status);
      const list=await r.json();if(!Array.isArray(list)||list.length<5000)throw new Error('base incompleta');
      setWorldAirports(list);
      for(const kind of ['origin','destination']){const input=airportInput(kind);if(input)input.title=`Base mundial carregada: ${worldAirports.length.toLocaleString('pt-BR')} aeroportos com IATA`;}
    }catch(err){
      for(const kind of ['origin','destination']){const input=airportInput(kind);if(input)input.title='Base mundial indisponível; usando a lista principal de aeroportos.';}
      console.warn('miles-airport-database',err);
    }
  }

  function setupAirportAutocomplete(kind){
    const input=airportInput(kind),box=airportBox(kind);if(!input||!box)return;
    input.addEventListener('input',()=>{input.dataset.iata='';renderAirportSuggestions(kind,input.value);});
    input.addEventListener('focus',()=>{if(input.value.trim())renderAirportSuggestions(kind,input.value);});
    input.addEventListener('blur',()=>setTimeout(()=>hideAirportSuggestions(kind),140));
    input.addEventListener('keydown',ev=>{
      const opts=[...box.querySelectorAll('.miles-airport-option')];
      if(ev.key==='Escape'){hideAirportSuggestions(kind);return;}
      if(!opts.length)return;
      if(ev.key==='ArrowDown'||ev.key==='ArrowUp'){
        ev.preventDefault();
        airportSuggestIndex[kind]=ev.key==='ArrowDown'?Math.min(opts.length-1,airportSuggestIndex[kind]+1):Math.max(0,airportSuggestIndex[kind]<0?opts.length-1:airportSuggestIndex[kind]-1);
        opts.forEach((o,i)=>o.classList.toggle('active',i===airportSuggestIndex[kind]));
        opts[airportSuggestIndex[kind]]?.scrollIntoView({block:'nearest'});
        return;
      }
      if(ev.key==='Enter'&&airportSuggestIndex[kind]>=0){
        ev.preventDefault();
        const code=opts[airportSuggestIndex[kind]]?.dataset.airportCode,a=worldAirportByCode.get(code);
        if(a)chooseAirport(kind,a);
      }
    });
  }

  function optionCode(o){
    const value=String(o?.value||'').trim(),label=String(o?.label||o?.textContent||'').trim();
    if(/^[A-Z]{3}$/i.test(value))return value.toUpperCase();
    if(/^[A-Z]{3}$/i.test(label))return label.toUpperCase();
    const m=(value+' '+label).match(/\\b([A-Z]{3})\\b/i);
    return m?m[1].toUpperCase():'';
  }

  function resolveAirport(kind,raw){
    const input=airportInput(kind),selected=String(input?.dataset?.iata||'').toUpperCase();
    if(/^[A-Z]{3}$/.test(selected))return selected;
    const value=String(raw||'').trim();
    if(/^[a-z]{3}$/i.test(value))return value.toUpperCase();
    const suffix=value.match(/\\(([A-Z]{3})\\)\\s*$/i);
    if(suffix)return suffix[1].toUpperCase();
    const n=norm(value);
    const exact=(worldAirports.length?worldAirports:fallbackAirports()).filter(a=>norm(a.city)===n||norm(a.name)===n||norm(airportDisplay(a))===n);
    return exact.length===1?exact[0].code:'';
  }

  function periodChanged(){const range=q('#milesPeriodMode').value==='range';q('#milesPeriodMonth').hidden=range;q('#milesPeriodRange').hidden=!range;}

  function currentQuery(){
    const period_mode=q('#milesPeriodMode').value;
    return {
      origin:resolveAirport('origin',q('#milesOrigin').value),
      destination:resolveAirport('destination',q('#milesDestination').value),
      period_mode,
      month:q('#milesMonthValue').value,
      start_date:period_mode==='range'?q('#milesRangeStart').value:'',
      end_date:period_mode==='range'?q('#milesRangeEnd').value:'',
      program:q('#milesProgram').value,
      cabin:q('#milesCabin').value
    };
  }

  function validate(x){
    if(!/^[A-Z]{3}$/.test(x.origin))return 'Escolha um aeroporto de origem válido. Você pode digitar o código IATA ou o nome da cidade e selecionar o aeroporto sugerido.';
    if(!/^[A-Z]{3}$/.test(x.destination))return 'Escolha um aeroporto de destino válido. Você pode digitar o código IATA ou o nome da cidade e selecionar o aeroporto sugerido.';
    if(x.origin===x.destination)return 'Origem e destino não podem ser iguais.';
    if(x.period_mode==='month'&&!/^20\d\d-(0[1-9]|1[0-2])$/.test(x.month))return 'Escolha o mês da viagem.';
    if(x.period_mode==='range'&&(!x.start_date||!x.end_date||x.end_date<x.start_date))return 'Informe um intervalo de datas válido.';
    return '';
  }

  function cabinLabel(v){return ({economy:'Econômica',premium_economy:'Premium Economy',business:'Executiva',first:'Primeira classe'})[v]||v||'Não informado';}
  function rowProgram(x){return String(x.program||x.source||'').trim();}
  function rowOrigin(x){return String(x.origin||'').toUpperCase();}
  function rowDestination(x){return String(x.destination||'').toUpperCase();}

  function inPeriod(x,query){
    const dep=String(x.departure_date||'').slice(0,10),ret=String(x.return_date||'').slice(0,10);
    if(query.period_mode==='month')return dep.startsWith(query.month)||(ret&&ret.startsWith(query.month));
    if(!dep)return false;
    return dep>=query.start_date&&dep<=query.end_date&&(!ret||(ret>=query.start_date&&ret<=query.end_date));
  }

  function matchingRows(query){
    return [...(data.results||[])].filter(x=>
      rowOrigin(x)===query.origin&&rowDestination(x)===query.destination&&inPeriod(x,query)&&
      (!query.program||rowProgram(x)===query.program)&&(!query.cabin||String(x.cabin||'economy')===query.cabin)&&Number(x.miles)>0
    ).sort((a,b)=>Number(a.miles)-Number(b.miles));
  }

  function providerUrl(name){return PROGRAMS[name]?.url||'#';}

  function renderProviderActions(query){
    const box=q('#milesProviderActions');box.innerHTML='';
    const names=query?.program?[query.program]:Object.keys(PROGRAMS);
    names.forEach(name=>{const a=document.createElement('a');a.href=providerUrl(name);a.target='_blank';a.rel='noopener';a.textContent=`Abrir ${PROGRAMS[name].label}`;a.title=`${query?.origin||''} → ${query?.destination||''} · ${PROGRAMS[name].note}`;box.appendChild(a);});
  }

  function renderSources(){
    const box=q('#milesSources');box.innerHTML='';
    Object.keys(PROGRAMS).forEach(name=>{const info=(data.sources||{})[name],e=document.createElement('span');e.className='source-pill '+(info?.ok?'ok':'bad');e.textContent=info?`${info.ok?'●':'○'} ${name}${Number.isFinite(Number(info.items))?`: ${info.items}`:''}`:`○ ${name} · aguardando coleta`;if(info?.message)e.title=info.message;box.appendChild(e);});
  }

  function render(query=activeQuery){
    const rows=query?matchingRows(query):[];
    const tb=q('#milesRows');tb.innerHTML='';
    q('#milesEmpty').hidden=rows.length>0;
    q('#milesResultCount').textContent=rows.length;
    q('#milesLowest').textContent=rows.length?fmtMiles(rows[0].miles):'—';
    q('#milesProgramCount').textContent=query?.program?'1':'4';
    for(const x of rows){
      const dates=x.return_date?`${fmtDate(x.departure_date)} → ${fmtDate(x.return_date)}`:fmtDate(x.departure_date);
      const program=rowProgram(x)||'Programa';
      const tr=document.createElement('tr');
      tr.innerHTML=`<td><span class="badge official miles-program">${esc(program)}</span></td><td class="route"><b>${esc(rowOrigin(x))} → ${esc(rowDestination(x))}</b><small>${esc(x.origin_name||rowOrigin(x))} → ${esc(x.destination_name||rowDestination(x))}</small></td><td class="date-stack"><b>${esc(dates)}</b></td><td>${esc(cabinLabel(x.cabin))}</td><td class="miles-value">${fmtMiles(x.miles)}</td><td><a class="btn" href="${safe(x.url||providerUrl(program))}" target="_blank" rel="noopener">Abrir resgate</a></td>`;
      tb.appendChild(tr);
    }
    renderProviderActions(query||currentQuery());
  }

  async function requestJson(url){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try{
      const r=await fetch(`${url}${url.includes('?')?'&':'?'}t=${Date.now()}`,{cache:'no-store',signal:controller.signal});
      if(!r.ok)throw new Error('HTTP '+r.status);
      return await r.json();
    }finally{clearTimeout(timer);}
  }

  async function loadConfig(){
    try{
      const c=await requestJson('./data/flight-search-config.json');
      apiBase=String(c.api_base||'').replace(/\/$/,'');
    }catch{}
  }

  function makeRequestId(){
    const raw=globalThis.crypto&&typeof globalThis.crypto.randomUUID==='function'
      ?globalThis.crypto.randomUUID().replace(/-/g,'')
      :(Date.now().toString(36)+Math.random().toString(36).slice(2)+Math.random().toString(36).slice(2));
    return 'miles_'+raw.slice(0,56);
  }

  function resultMatches(result,query,requestId){
    if(!result||result.request_id!==requestId||!result.request)return false;
    const r=result.request;
    if(r.origin!==query.origin||r.destination!==query.destination)return false;
    if(String(r.program||'')!==String(query.program||'')||String(r.cabin||'')!==String(query.cabin||''))return false;
    if((r.period_mode||'month')!==query.period_mode)return false;
    if(query.period_mode==='range')return r.start_date===query.start_date&&r.end_date===query.end_date;
    return r.month===query.month;
  }

  function bridgeState(requestId){
    return new Promise(resolve=>{
      if(!apiBase){resolve(null);return;}
      const callback='milesState_'+String(requestId).replace(/[^A-Za-z0-9_$]/g,'_');
      const script=document.createElement('script');
      let finished=false;
      const finish=value=>{if(finished)return;finished=true;clearTimeout(timer);try{script.remove()}catch{};try{delete window[callback]}catch{};resolve(value);};
      const timer=setTimeout(()=>finish(null),8000);
      window[callback]=value=>finish(value);
      script.onerror=()=>finish(null);
      script.src=`${apiBase}?route=${encodeURIComponent('api/miles/search/'+requestId)}&callback=${encodeURIComponent(callback)}&t=${Date.now()}`;
      document.head.appendChild(script);
    });
  }

  function postBridge(query,requestId){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    const url=`${apiBase}?route=${encodeURIComponent('api/miles/search')}&t=${Date.now()}`;
    const body={...query,request_id:requestId};
    fetch(url,{
      method:'POST',
      mode:'no-cors',
      cache:'no-store',
      signal:controller.signal,
      headers:{'Content-Type':'text/plain;charset=UTF-8'},
      body:JSON.stringify(body)
    }).catch(()=>{}).finally(()=>clearTimeout(timer));
  }

  async function loadData(){
    try{data=await requestJson(RESULT_RAW);}
    catch{data={version:'0.2.0',generated_at:null,results:[],sources:{}};}
    q('#milesUpdated').textContent=data.generated_at?'Atualizado '+new Date(data.generated_at).toLocaleString('pt-BR'):'Aguardando primeira coleta';
    renderSources();
  }

  async function waitForResult(query,requestId,status){
    const started=Date.now();
    let lastBridgeCheck=0;
    for(let i=0;i<120;i++){
      await sleep(2000);
      const final=await requestJson(RESULT_RAW).catch(()=>null);
      if(final&&resultMatches(final,query,requestId)&&final.status!=='running')return final;

      if(Date.now()-lastBridgeCheck>8000){
        lastBridgeCheck=Date.now();
        const state=await bridgeState(requestId);
        if(state?.status==='error')throw new Error(state.error||'A busca por milhas terminou com erro.');
        if(state?.status==='queued')status.textContent='⏳ Busca recebida. Aguardando execução no GitHub Actions…';
        else if(state?.status==='in_progress'||state?.status==='running')status.textContent='🔎 Consultando disponibilidade real de resgate em milhas…';
        else status.textContent='🔎 Busca enviada. Aguardando o resultado da consulta em milhas…';
      }
      if(Date.now()-started>240000)throw new Error('A busca por milhas excedeu 4 minutos.');
    }
    throw new Error('A busca por milhas não retornou resultado.');
  }

  async function search(){
    if(searching)return;
    const query=currentQuery(),status=q('#milesStatus'),button=q('#milesSearchButton'),error=validate(query);
    if(error){status.className='miles-status bad';status.textContent=error;return;}
    if(!apiBase)await loadConfig();
    if(!apiBase){status.className='miles-status bad';status.textContent='O serviço de pesquisa ainda não está conectado. Atualize a página e tente novamente.';return;}

    const requestId=makeRequestId();
    searching=true;
    button.disabled=true;
    button.textContent='⏳ Pesquisando…';
    activeQuery=query;
    status.className='miles-status warn';
    status.textContent='🔎 Enviando consulta de disponibilidade em milhas…';
    try{
      postBridge(query,requestId);
      const result=await waitForResult(query,requestId,status);
      data=result;
      q('#milesUpdated').textContent=data.generated_at?'Atualizado '+new Date(data.generated_at).toLocaleString('pt-BR'):'Consulta concluída';
      renderSources();
      render(query);
      const rows=matchingRows(query);
      if(result.status==='error')throw new Error(result.error||'A consulta de milhas terminou com erro.');
      if(rows.length){
        status.className='miles-status ok';
        status.textContent=`✅ ${rows.length} opção(ões) encontrada(s), ordenadas do menor para o maior valor em milhas.`;
      }else if(result.notice){
        status.className='miles-status warn';
        status.textContent=result.notice;
      }else{
        status.className='miles-status warn';
        status.textContent='Consulta concluída, mas não houve disponibilidade em milhas para esta rota, período e cabine.';
      }
    }catch(err){
      await loadData().catch(()=>{});
      render(query);
      status.className='miles-status bad';
      status.textContent='Não foi possível concluir a busca por milhas: '+String(err?.message||err);
    }finally{
      searching=false;
      button.disabled=false;
      button.textContent='⭐ Pesquisar milhas';
    }
  }

  function hideBuiltIn(){['hunterPanel','radarPanel','externalPanel','airlinesPanel','flightMonthPanel'].forEach(id=>{const el=q('#'+id);if(el)el.hidden=true;});}
  function setFocus(on){document.body.classList.toggle('flight-search-focus',!!on);}
  function activate(){document.querySelectorAll('#flightTabs .tab').forEach(x=>x.classList.remove('active'));btn.classList.add('active');hideBuiltIn();panel.hidden=false;setFocus(true);render(activeQuery);}

  setWorldAirports(fallbackAirports());setupAirportAutocomplete('origin');setupAirportAutocomplete('destination');const paidOrigin=q('#monthOrigin');if(paidOrigin&&paidOrigin.value){const code=String(paidOrigin.value).trim().toUpperCase();const a=fallbackAirports().find(x=>x.code===code);if(a)chooseAirport('origin',a);else q('#milesOrigin').value=code;}loadWorldAirports();defaults();periodChanged();renderProviderActions(null);renderSources();loadConfig();loadData();
  q('#milesPeriodMode').addEventListener('change',periodChanged);
  q('#milesRangeStart').addEventListener('change',()=>{const start=q('#milesRangeStart'),end=q('#milesRangeEnd');end.min=start.value||start.min;if(end.value<start.value)end.value=start.value;});
  q('#milesSearchButton').addEventListener('click',e=>{e.preventDefault();search().catch(err=>{const status=q('#milesStatus');status.className='miles-status bad';status.textContent='Não foi possível carregar a consulta: '+String(err?.message||err);});});
  btn.addEventListener('click',activate);
  document.querySelectorAll('#flightTabs .tab').forEach(b=>{if(b!==btn)b.addEventListener('click',()=>{panel.hidden=true;if(b.dataset.flightView!=='monthsearch')setFocus(false);});});
  const productsMain=document.querySelector('.main-tab[data-main="products"]');if(productsMain)productsMain.addEventListener('click',()=>{panel.hidden=true;setFocus(false);});
  const flightsMain=document.querySelector('.main-tab[data-main="flights"]');if(flightsMain)flightsMain.addEventListener('click',()=>{if(btn.classList.contains('active'))activate();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)loadData().then(()=>render(activeQuery));});
})();
