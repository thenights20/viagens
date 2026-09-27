(() => {
  const qs = s => document.querySelector(s);
  if (qs('#appleStockApp') || !qs('.main-tabs')) return;

  const PRODUCT = 'iPhone 18 Pro Max Burgundy · 256GB';
  const LOCATIONS = [
    { label: 'Altamonte Springs', value: 'Altamonte Springs, FL' },
    { label: 'Aventura', value: 'Aventura, FL' },
    { label: 'Boca Raton', value: 'Boca Raton, FL' },
    { label: 'Brandon', value: 'Brandon, FL' },
    { label: 'Estero', value: 'Estero, FL' },
    { label: 'Fort Lauderdale', value: 'Fort Lauderdale, FL' },
    { label: 'Miami', value: 'Miami, FL' },
    { label: 'Miami Beach', value: 'Miami Beach, FL' },
    { label: 'Naples', value: 'Naples, FL' },
    { label: 'Orlando', value: 'Orlando, FL' },
    { label: 'Palm Beach Gardens', value: 'Palm Beach Gardens, FL' },
    { label: 'Sarasota', value: 'Sarasota, FL' },
    { label: 'Tampa', value: 'Tampa, FL' },
    { label: 'Wellington', value: 'Wellington, FL' }
  ];
  const DISCOVERY_LABELS = [
    'Orlando', 'Tampa', 'Miami', 'Fort Lauderdale', 'Naples', 'Palm Beach Gardens',
    'Sarasota', 'Altamonte Springs', 'Brandon', 'Estero', 'Aventura', 'Boca Raton',
    'Miami Beach', 'Wellington'
  ];
  const DISCOVERY_LOCATIONS = DISCOVERY_LABELS.map(label => LOCATIONS.find(x => x.label === label)).filter(Boolean);
  const TARGET_STORE_COUNT = 18;
  const APPLE_URL = 'https://www.apple.com/shop/buy-iphone/iphone-18-pro';
  const FAST_TARGET_CYCLE_MS = 30000;
  const MIN_QUERY_DELAY = 6000;
  const DISCOVERY_DELAY = 7000;
  const PLAN_CACHE_KEY = 'appleStockFastPlanV1';
  const FIND_HISTORY_KEY = 'appleStockFindHistoryV1';
  const MAX_FIND_HISTORY = 80;

  let apiBase = '';
  let active = false;
  let timer = null;
  let blockStreak = 0;
  let previousAvailable = new Set();
  let checks = 0;
  let audioCtx = null;
  let locationIndex = 0;
  let discoveryIndex = 0;
  let steadyChecks = 0;
  let discoveryMode = true;
  let activeLocations = [];
  let findHistory = loadFindHistory();
  const citySnapshots = new Map();

  function restoreFastPlan(){
    try{
      const labels=JSON.parse(localStorage.getItem(PLAN_CACHE_KEY)||'[]');
      if(!Array.isArray(labels)||!labels.length)return[];
      const plan=labels.map(label=>LOCATIONS.find(x=>x.label===label)).filter(Boolean);
      return plan.length===labels.length?plan:[];
    }catch{return[];}
  }

  function saveFastPlan(plan){
    try{localStorage.setItem(PLAN_CACHE_KEY,JSON.stringify(plan.map(x=>x.label)));}catch{}
  }

  function clearFastPlan(){
    try{localStorage.removeItem(PLAN_CACHE_KEY);}catch{}
  }

  activeLocations=restoreFastPlan();
  discoveryMode=activeLocations.length===0;

  function queryDelay(){
    if(discoveryMode)return DISCOVERY_DELAY;
    const n=Math.max(1,activeLocations.length);
    return Math.max(MIN_QUERY_DELAY,Math.ceil(FAST_TARGET_CYCLE_MS/n));
  }

  function cycleSeconds(){
    const n=discoveryMode?Math.min(6,DISCOVERY_LOCATIONS.length):Math.max(1,activeLocations.length);
    return Math.round((n*queryDelay())/1000);
  }

  function optimizeCoverage(){
    const entries=[];
    for(const [label,snap] of citySnapshots.entries()){
      const location=LOCATIONS.find(x=>x.label===label);
      if(!location||!snap||!Array.isArray(snap.stores))continue;
      const keys=new Set(snap.stores.map(storeKey));
      if(keys.size)entries.push({location,keys});
    }
    const universe=new Set();
    entries.forEach(e=>e.keys.forEach(k=>universe.add(k)));
    const uncovered=new Set(universe);
    const remaining=[...entries];
    const chosen=[];
    while(uncovered.size&&remaining.length){
      let bestIndex=-1,bestGain=0;
      for(let i=0;i<remaining.length;i++){
        let gain=0;
        remaining[i].keys.forEach(k=>{if(uncovered.has(k))gain++;});
        if(gain>bestGain){bestGain=gain;bestIndex=i;}
      }
      if(bestIndex<0||bestGain===0)break;
      const best=remaining.splice(bestIndex,1)[0];
      chosen.push(best.location);
      best.keys.forEach(k=>uncovered.delete(k));
    }
    return chosen.length?chosen:[...LOCATIONS];
  }

  function beginDiscovery(){
    discoveryMode=true;
    discoveryIndex=0;
    locationIndex=0;
    steadyChecks=0;
    citySnapshots.clear();
    clearFastPlan();
  }

  const style = document.createElement('style');
  style.textContent = `
    .apple-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap;margin:0 0 9px}
    .apple-head h2{margin:0 0 3px;font-size:20px}.apple-head .sub{max-width:920px;font-size:12px;line-height:1.35}
    .apple-history{padding:10px 11px;margin-bottom:9px}
    .apple-history-top{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:8px}
    .apple-history-title{font-size:13px;font-weight:900}.apple-history-title small{display:block;margin-top:2px;color:var(--muted);font-size:10px;font-weight:500}
    .apple-history-metrics{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:7px}
    .apple-history-metric{border:1px solid var(--line);background:var(--panel2);border-radius:9px;padding:8px 9px;min-height:54px}
    .apple-history-metric span{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.07em}
    .apple-history-metric b{display:block;margin-top:3px;font-size:14px;line-height:1.2}
    .apple-timeline{display:flex;gap:6px;overflow-x:auto;padding:7px 0 1px;scrollbar-width:thin}
    .apple-time-chip{flex:0 0 auto;min-width:142px;border:1px solid var(--line);background:var(--panel2);border-radius:9px;padding:7px 8px}
    .apple-time-chip b{display:block;font-size:12px}.apple-time-chip span{display:block;margin-top:2px;color:var(--muted);font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:190px}
    .apple-history-empty{color:var(--muted);font-size:11px;padding:4px 1px}
    .apple-form{padding:10px;display:grid;grid-template-columns:2.2fr .9fr .8fr;gap:8px;align-items:end;margin-bottom:9px}
    .apple-field label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 4px}
    .apple-fixed{display:flex;align-items:center;min-height:36px;padding:0 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel2);font-weight:800;font-size:13px}
    .apple-actions{display:flex;gap:7px;align-items:center;grid-column:1/-1;flex-wrap:wrap}
    .apple-start,.apple-stop{border:0;cursor:pointer;font-weight:900;padding:8px 13px;border-radius:9px;min-width:145px;min-height:36px}
    .apple-start{background:var(--accent);color:#07111f}.apple-stop{background:var(--panel2);color:var(--hot);border:1px solid var(--hot)}
    .apple-start:disabled,.apple-stop:disabled{opacity:.45;cursor:not-allowed}
    .apple-link{display:inline-flex;align-items:center;text-decoration:none;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-weight:800;padding:8px 10px;border-radius:9px;font-size:12px}
    .apple-status{padding:9px 11px;border:1px solid var(--line);border-radius:10px;background:var(--panel2);margin:0 0 8px;color:var(--muted);line-height:1.35;font-size:12px}
    .apple-status.live{color:var(--accent)}.apple-status.ok{color:var(--ok);border-color:var(--ok);font-weight:800}.apple-status.warn{color:var(--warn);border-color:var(--warn)}.apple-status.bad{color:var(--hot);border-color:var(--hot)}
    .apple-alert{padding:12px;margin:0 0 8px;border:2px solid var(--ok);border-radius:11px;background:color-mix(in srgb,var(--ok) 10%,var(--panel));animation:applePulse 1s ease-in-out infinite alternate}
    .apple-alert b{display:block;color:var(--ok);font-size:17px;margin-bottom:3px}.apple-alert span{font-size:12px}
    @keyframes applePulse{from{box-shadow:0 0 0 rgba(91,214,160,0)}to{box-shadow:0 0 20px rgba(91,214,160,.2)}}
    .apple-summary{grid-template-columns:repeat(4,1fr);gap:7px;margin:8px 0}
    .apple-summary .card{padding:10px 11px}.apple-summary .card b{font-size:20px;margin-top:2px}
    .apple-stores{display:grid;grid-template-columns:repeat(4,minmax(205px,1fr));gap:7px;padding:8px}
    .apple-store{border:1px solid var(--line);background:var(--panel2);border-radius:10px;padding:10px;min-height:108px;display:flex;flex-direction:column;justify-content:space-between;gap:6px}
    .apple-store.available{border-color:var(--ok);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--ok) 35%,transparent)}
    .apple-store h3{margin:0 0 2px;font-size:13px}.apple-store .where{color:var(--muted);font-size:9px;line-height:1.3}
    .apple-store .state{font-weight:950;font-size:10px}.apple-store.available .state{color:var(--ok)}.apple-store.unavailable .state{color:var(--hot)}.apple-store.unknown .state{color:var(--warn)}
    .apple-store .quote{color:var(--muted);font-size:9px;line-height:1.25}.apple-store .distance{font-size:9px;color:var(--accent);font-weight:800}
    .apple-note{margin-top:7px;padding:8px 10px;font-size:10px;line-height:1.4}
    @media(max-width:1200px){.apple-stores{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:1000px){.apple-form{grid-template-columns:1fr 1fr}.apple-stores{grid-template-columns:repeat(2,1fr)}.apple-summary{grid-template-columns:repeat(2,1fr)}.apple-history-metrics{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:700px){.apple-form{grid-template-columns:1fr}.apple-actions{grid-column:1}.apple-stores{grid-template-columns:1fr}.apple-actions>*{flex:1;justify-content:center}.apple-history-metrics{grid-template-columns:1fr 1fr}}
  `;
  document.head.appendChild(style);

  const tab = document.createElement('button');
  tab.className = 'main-tab';
  tab.dataset.main = 'apple';
  tab.textContent = '🍎 Apple · FL';
  qs('.main-tabs').appendChild(tab);

  const app = document.createElement('main');
  app.id = 'appleStockApp';
  app.hidden = true;
  app.innerHTML = `
    <div class="apple-head">
      <div><h2>🍎 Monitor de estoque · ${TARGET_STORE_COUNT} Apple Stores na Flórida</h2><div class="sub">Monitora retirada em loja do <b>${PRODUCT}</b>, somente <b>256GB Burgundy</b>, em todas as lojas do print, <b>exceto a nº 7 (St. Johns Town Center / Jacksonville)</b>. O modo rápido aprende quais pontos cobrem as mesmas ${TARGET_STORE_COUNT} lojas e reduz consultas redundantes.</div></div>
      <a class="apple-link" href="${APPLE_URL}" target="_blank" rel="noopener">Abrir produto na Apple ↗</a>
    </div>

    <section class="panel apple-history">
      <div class="apple-history-top">
        <div class="apple-history-title">📈 Horários em que o iPhone apareceu<small>Histórico salvo neste navegador; usado apenas para mostrar padrões observados.</small></div>
        <div class="sub" id="appleHistoryHint">Ainda sem histórico suficiente para indicar um padrão.</div>
      </div>
      <div class="apple-history-metrics">
        <div class="apple-history-metric"><span>Último achado</span><b id="appleLastFound">—</b></div>
        <div class="apple-history-metric"><span>Janela mais frequente</span><b id="appleBestWindow">—</b></div>
        <div class="apple-history-metric"><span>Horários fortes</span><b id="appleHotTimes">—</b></div>
        <div class="apple-history-metric"><span>Achados registrados</span><b id="appleFindCount">0</b></div>
      </div>
      <div class="apple-timeline" id="appleTimeline"><div class="apple-history-empty">Nenhum achado registrado ainda.</div></div>
    </section>

    <section class="panel apple-form">
      <div class="apple-field"><label>Produto monitorado</label><div class="apple-fixed">${PRODUCT}</div></div>
      <div class="apple-field"><label>Lojas monitoradas</label><div class="apple-fixed">${TARGET_STORE_COUNT} lojas · Flórida</div></div>
      <div class="apple-field"><label>Intervalo atual</label><div class="apple-fixed" id="appleFrequency">${queryDelay()/1000} segundos</div></div>
      <div class="apple-actions">
        <button id="appleStart" class="apple-start">▶ Monitorar agora</button>
        <button id="appleStop" class="apple-stop" disabled>■ Parar</button>
        <span class="sub" id="appleHint">Modo rápido: mantém as 18 lojas, mas consulta apenas os pontos necessários para cobri-las.</span>
      </div>
    </section>

    <div id="appleAvailabilityAlert" class="apple-alert" hidden></div>
    <div id="appleStatus" class="apple-status">Monitor parado. Clique em “Monitorar agora”.</div>

    <section class="cards apple-summary">
      <div class="card"><span>Lojas verificadas</span><b id="appleStoreCount">—</b></div>
      <div class="card"><span>Disponíveis agora</span><b id="appleAvailableCount">—</b></div>
      <div class="card"><span>Consultas</span><b id="appleChecks">0</b></div>
      <div class="card"><span>Última consulta</span><b id="appleUpdated" style="font-size:15px">—</b></div>
    </section>

    <section class="panel">
      <div class="apple-stores" id="appleStores"></div>
      <div class="empty" id="appleEmpty"><strong>Aguardando primeira consulta.</strong>O monitor mostrará as lojas-alvo da Flórida conforme elas forem consultadas.</div>
    </section>

    <div class="note apple-note"><b>Como o modo rápido funciona:</b> na primeira execução ele começa por pontos estratégicos e só acrescenta outras regiões se ainda faltar alguma das ${TARGET_STORE_COUNT} lojas. Ao encontrar cobertura completa, calcula um conjunto mínimo de pontos e salva esse plano neste navegador. O objetivo é revisar as mesmas lojas em cerca de 30–40 segundos, com menos requisições por minuto do que o ciclo anterior.</div>
    <div class="note apple-note"><b>Como o alerta funciona:</b> “Disponível” só aparece quando a própria Apple informa retirada habilitada para a variante monitorada. Se a Apple limitar as consultas, o painel mostra “bloqueado/aguardando” e reduz temporariamente a frequência — nunca converte bloqueio em “sem estoque”. O monitor depende desta página permanecer aberta; navegadores móveis podem suspender timers quando a aba fica em segundo plano ou a tela é bloqueada.</div>
  `;
  const indigo = qs('#indigoApp');
  const flights = qs('#flightsApp');
  if (indigo) indigo.after(app);
  else if (flights) flights.after(app);
  else document.querySelector('.wrap').appendChild(app);

  async function loadConfig(){
    try{
      const r=await fetch('./data/flight-search-config.json?t='+Date.now(),{cache:'no-store'});
      const d=await r.json();apiBase=String(d.api_base||'').trim();
    }catch{apiBase='';}
  }

  function jsonpAvailability(location,timeoutMs=12000){
    return new Promise((resolve,reject)=>{
      if(!apiBase){reject(new Error('Serviço de pesquisa não conectado.'));return;}
      const cb='appleCb_'+Date.now().toString(36)+Math.random().toString(36).slice(2);
      const script=document.createElement('script');
      let finished=false;
      const timerId=setTimeout(()=>finish(new Error('A Apple demorou para responder.')),timeoutMs);
      function finish(err,value){
        if(finished)return;finished=true;clearTimeout(timerId);
        try{delete window[cb]}catch{}
        script.remove();err?reject(err):resolve(value);
      }
      window[cb]=value=>finish(null,value);
      script.onerror=()=>finish(new Error('Não foi possível consultar o serviço.'));
      script.src=`${apiBase}?route=${encodeURIComponent('api/apple/availability')}&location=${encodeURIComponent(location)}&callback=${encodeURIComponent(cb)}&t=${Date.now()}`;
      document.head.appendChild(script);
    });
  }

  function fmtTime(v){
    if(!v)return'—';
    try{return new Date(v).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});}catch{return'—';}
  }

  function loadFindHistory(){
    try{
      const raw=JSON.parse(localStorage.getItem(FIND_HISTORY_KEY)||'[]');
      return Array.isArray(raw)?raw.filter(x=>x&&x.ts):[];
    }catch{return[];}
  }

  function saveFindHistory(){
    try{localStorage.setItem(FIND_HISTORY_KEY,JSON.stringify(findHistory.slice(0,MAX_FIND_HISTORY)));}catch{}
  }

  function fmtFound(v){
    if(!v)return'—';
    try{return new Date(v).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).replace(',', ' ·');}catch{return'—';}
  }

  function halfHourLabel(date){
    const h=date.getHours(),m=date.getMinutes()<30?0:30;
    const end=new Date(date);end.setMinutes(m+29,59,999);
    const startText=String(h).padStart(2,'0')+':'+String(m).padStart(2,'0');
    const endText=String(end.getHours()).padStart(2,'0')+':'+String(end.getMinutes()).padStart(2,'0');
    return startText+'–'+endText;
  }

  function analyzeFindHistory(){
    const valid=findHistory.filter(x=>x&&x.ts&&!Number.isNaN(Date.parse(x.ts)));
    if(!valid.length)return{last:'—',best:'—',hot:'—',count:0,hint:'Ainda sem histórico suficiente para indicar um padrão.'};
    const bins=new Map();
    valid.forEach(item=>{
      const d=new Date(item.ts);
      const key=String(d.getHours()).padStart(2,'0')+':'+(d.getMinutes()<30?'00':'30');
      bins.set(key,(bins.get(key)||0)+1);
    });
    const ranked=[...bins.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]));
    const labelFor=key=>{
      const [h,m]=key.split(':').map(Number);
      const d=new Date();d.setHours(h,m,0,0);
      return halfHourLabel(d);
    };
    const best=ranked.length?labelFor(ranked[0][0]):'—';
    const hot=ranked.slice(0,3).map(([key,count])=>`${labelFor(key)}${count>1?` (${count}×)`:''}`).join(' · ')||'—';
    const hint=valid.length<3
      ? `Já há ${valid.length} achado(s), mas ainda é cedo para chamar isso de padrão.`
      : `Padrão histórico: maior concentração em ${best}. Isso não garante novo estoque nesse horário.`;
    return{last:fmtFound(valid[0].ts),best,hot,count:valid.length,hint};
  }

  function renderFindHistory(){
    const p=analyzeFindHistory();
    qs('#appleLastFound').textContent=p.last;
    qs('#appleBestWindow').textContent=p.best;
    qs('#appleHotTimes').textContent=p.hot;
    qs('#appleFindCount').textContent=String(p.count);
    qs('#appleHistoryHint').textContent=p.hint;
    const timeline=qs('#appleTimeline');
    if(!findHistory.length){
      timeline.innerHTML='<div class="apple-history-empty">Nenhum achado registrado ainda. O primeiro estoque detectado passará a aparecer aqui.</div>';
      return;
    }
    timeline.innerHTML=findHistory.slice(0,16).map(item=>{
      const names=Array.isArray(item.stores)?item.stores:[];
      const storesText=names.slice(0,2).join(' · ')+(names.length>2?' +'+(names.length-2):'');
      return `<div class="apple-time-chip"><b>${escapeHtml(fmtFound(item.ts))}</b><span>${escapeHtml(storesText||`${item.count||1} loja(s)`)}</span></div>`;
    }).join('');
  }

  function recordFindings(stores,checkedAt){
    if(!stores.length)return;
    const ts=checkedAt&&Date.parse(checkedAt)?new Date(checkedAt).toISOString():new Date().toISOString();
    const names=[...new Set(stores.map(x=>String(x.name||'Apple Store')).filter(Boolean))].sort();
    const key=names.join('|');
    const latest=findHistory[0];
    if(latest){
      const latestKey=(Array.isArray(latest.stores)?[...latest.stores].sort():[]).join('|');
      const diff=Math.abs(Date.parse(ts)-Date.parse(latest.ts||0));
      if(key===latestKey&&diff<5*60*1000)return;
    }
    findHistory.unshift({ts,count:stores.length,stores:names});
    findHistory=findHistory.slice(0,MAX_FIND_HISTORY);
    saveFindHistory();
    renderFindHistory();
  }

  function storeKey(x){return [String(x.store_number||x.name||''),String(x.storage||x.part_number||'')].join('|');}

  function ensureAudio(){
    if(audioCtx)return;
    try{audioCtx=new (window.AudioContext||window.webkitAudioContext)();}catch{}
  }

  function alarm(){
    try{
      ensureAudio();
      if(!audioCtx)return;
      if(audioCtx.state==='suspended')audioCtx.resume();
      const now=audioCtx.currentTime;
      [0,.28,.56].forEach(offset=>{
        const o=audioCtx.createOscillator(),g=audioCtx.createGain();
        o.frequency.setValueAtTime(880,now+offset);
        g.gain.setValueAtTime(.0001,now+offset);
        g.gain.exponentialRampToValueAtTime(.22,now+offset+.025);
        g.gain.exponentialRampToValueAtTime(.0001,now+offset+.22);
        o.connect(g);g.connect(audioCtx.destination);o.start(now+offset);o.stop(now+offset+.24);
      });
    }catch{}
  }

  function notifyNew(stores){
    if(!stores.length)return;
    alarm();
    const names=stores.map(x=>`${x.name} · ${x.storage||''}`).join(', ');
    if('Notification' in window && Notification.permission==='granted'){
      try{new Notification('iPhone disponível na Apple!',{body:`${PRODUCT} disponível: ${names}`,tag:'apple-iphone-stock',renotify:true});}catch{}
    }
    document.title='✅ IPHONE DISPONÍVEL · '+names;
    setTimeout(()=>{document.title='Acompanhamento Pessoal de Ofertas';},15000);
  }

  async function askNotifications(){
    ensureAudio();
    if('Notification' in window && Notification.permission==='default'){
      try{await Notification.requestPermission();}catch{}
    }
  }

  function escapeHtml(v=''){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

  function mergeSnapshots(){
    const merged=new Map();
    for(const snap of citySnapshots.values()){
      for(const store of snap.stores){
        const key=storeKey(store);
        const prev=merged.get(key);
        const prevTime=prev?Date.parse(prev.observed_at||0)||0:0;
        const nextTime=Date.parse(store.observed_at||0)||0;
        if(!prev||nextTime>=prevTime)merged.set(key,store);
      }
    }
    return [...merged.values()];
  }

  function render(data){
    checks+=1;
    qs('#appleChecks').textContent=String(checks);
    qs('#appleUpdated').textContent=fmtTime(data.checked_at);
    const stores=Array.isArray(data.stores)?data.stores:[];
    const available=stores.filter(x=>x.available===true);
    qs('#appleStoreCount').textContent=String(stores.length);
    qs('#appleAvailableCount').textContent=String(available.length);

    const current=new Set(available.map(storeKey));
    const newly=available.filter(x=>!previousAvailable.has(storeKey(x)));
    if(newly.length){
      notifyNew(newly);
      recordFindings(newly,data.checked_at);
    }
    previousAvailable=current;

    const alert=qs('#appleAvailabilityAlert');
    if(available.length){
      alert.hidden=false;
      alert.innerHTML=`<b>✅ ESTOQUE ENCONTRADO!</b><span>${available.map(x=>`Apple ${escapeHtml(x.name)} · ${escapeHtml(x.storage||'')} · ${escapeHtml(x.distance_text||'')}`).join('<br>')}</span>`;
    }else{
      alert.hidden=true;alert.innerHTML='';
    }

    const box=qs('#appleStores');box.innerHTML='';
    qs('#appleEmpty').hidden=stores.length>0;
    const ordered=[...stores].sort((a,b)=>(Number(b.available)-Number(a.available))||(Number(a.distance||9999)-Number(b.distance||9999)));
    for(const x of ordered){
      const known=x.pickup_display==='available'||x.pickup_display==='unavailable';
      const css=x.available?'available':known?'unavailable':'unknown';
      const label=x.available?'✅ DISPONÍVEL PARA RETIRADA':known?'ESGOTADO / INDISPONÍVEL':'⚠️ ESTADO NÃO CONFIRMADO';
      const div=document.createElement('div');div.className='apple-store '+css;
      div.innerHTML=`
        <div><h3>Apple ${escapeHtml(x.name||'Store')} · ${escapeHtml(x.storage||'')}</h3><div class="where">${escapeHtml([x.address,[x.city,x.state,x.postal_code].filter(Boolean).join(' ')].filter(Boolean).join(' · '))}</div>${x.distance_text?`<div class="distance">${escapeHtml(x.distance_text)}</div>`:''}</div>
        <div><div class="state">${label}</div><div class="quote">${escapeHtml(x.quote||x.pickup_display||'Sem informação')}</div></div>`;
      box.appendChild(div);
    }
  }

  function setStatus(message,css='live'){
    const el=qs('#appleStatus');el.className='apple-status '+css;el.textContent=message;
  }

  function schedule(delay){
    clearTimeout(timer);
    if(!active)return;
    qs('#appleFrequency').textContent=(delay/1000).toFixed(delay%1000?1:0)+' segundos';
    timer=setTimeout(checkNow,delay);
  }

  async function checkNow(){
    if(!active)return;
    if(document.hidden){setStatus('⏸ Monitor ativo, mas a aba está em segundo plano. Retomarei ao voltar para esta página.','warn');return;}

    if(!discoveryMode&&!activeLocations.length){
      beginDiscovery();
    }

    const target=discoveryMode
      ? DISCOVERY_LOCATIONS[Math.min(discoveryIndex,DISCOVERY_LOCATIONS.length-1)]
      : activeLocations[locationIndex%activeLocations.length];
    if(!target){setStatus('Não encontrei um ponto válido para consultar.','bad');return;}

    setStatus(discoveryMode
      ? `🧭 Calibrando cobertura rápida · consultando ${target.label}…`
      : `🔎 Modo rápido · consultando ${target.label}…`,'live');

    try{
      const data=await jsonpAvailability(target.value,45000);
      if(!active)return;
      if(!data||data.ok!==true){
        if(data&&data.blocked){
          blockStreak+=1;
          const delay=blockStreak>=3?60000:blockStreak===2?30000:15000;
          setStatus(`⚠️ A Apple limitou temporariamente as consultas (HTTP ${data.http_status||'—'}). Nova tentativa no mesmo ponto em ${delay/1000}s.`,'warn');
          schedule(delay);return;
        }
        blockStreak=0;
        setStatus('⚠️ '+String(data&&data.error||'Resposta da Apple não confirmada.')+' Nova tentativa no mesmo ponto em 10s.','warn');
        schedule(10000);return;
      }

      blockStreak=0;
      const cityStores=(Array.isArray(data.stores)?data.stores:[]).map(x=>({...x,search_area:target.label,observed_at:data.checked_at}));
      citySnapshots.set(target.label,{stores:cityStores,checked_at:data.checked_at});

      if(discoveryMode)discoveryIndex+=1;
      else{locationIndex=(locationIndex+1)%activeLocations.length;steadyChecks+=1;}

      const stores=mergeSnapshots();
      const available=stores.filter(x=>x.available===true);
      render({...data,stores,stores_count:stores.length,available_count:available.length,any_available:available.length>0});

      const missing=Array.isArray(data.missing_variants)?data.missing_variants:[];
      if(missing.length){
        setStatus('⚠️ Variante 256GB ainda sem SKU configurado no serviço.','warn');
        schedule(queryDelay());return;
      }

      const n=available.length;

      if(discoveryMode&&(stores.length>=TARGET_STORE_COUNT||discoveryIndex>=DISCOVERY_LOCATIONS.length)){
        activeLocations=optimizeCoverage();
        discoveryMode=false;
        locationIndex=0;
        steadyChecks=0;
        if(stores.length>=TARGET_STORE_COUNT)saveFastPlan(activeLocations);
        const delay=queryDelay();
        const cycle=Math.round(activeLocations.length*delay/1000);
        const coverageText=stores.length>=TARGET_STORE_COUNT
          ? `${TARGET_STORE_COUNT}/${TARGET_STORE_COUNT} lojas cobertas`
          : `${stores.length}/${TARGET_STORE_COUNT} lojas retornadas pela Apple`;
        setStatus(n
          ? `✅ Estoque encontrado. Modo rápido calibrado: ${coverageText}; ${activeLocations.length} ponto(s), ciclo de ~${cycle}s.`
          : `⚡ Modo rápido calibrado: ${coverageText}; ${activeLocations.length} ponto(s), ciclo de ~${cycle}s.`,n?'ok':'live');
        schedule(delay);return;
      }

      if(!discoveryMode&&steadyChecks>=activeLocations.length){
        steadyChecks=0;
        if(stores.length<TARGET_STORE_COUNT){
          beginDiscovery();
          setStatus(`🧭 O plano rápido retornou ${stores.length}/${TARGET_STORE_COUNT} lojas. Recalibrando automaticamente para não deixar nenhuma de fora.`,'warn');
          schedule(DISCOVERY_DELAY);return;
        }
      }

      if(discoveryMode){
        setStatus(n
          ? `✅ ${n} loja(s) com retirada disponível. Calibração já encontrou ${stores.length}/${TARGET_STORE_COUNT} lojas.`
          : `🧭 Calibrando modo rápido: ${stores.length}/${TARGET_STORE_COUNT} lojas cobertas até agora.`,n?'ok':'live');
      }else{
        const delay=queryDelay();
        const cycle=Math.round(activeLocations.length*delay/1000);
        setStatus(n
          ? `✅ ${n} loja(s) com retirada disponível agora entre as ${TARGET_STORE_COUNT} lojas-alvo. Modo rápido: ciclo ~${cycle}s.`
          : `⚡ Modo rápido: ${stores.length}/${TARGET_STORE_COUNT} lojas verificadas por ${activeLocations.length} ponto(s); ciclo ~${cycle}s. Nenhuma disponível agora.`,n?'ok':'live');
      }
      schedule(queryDelay());
    }catch(err){
      if(!active)return;
      setStatus('⚠️ '+String(err&&err.message||err)+' Tentarei novamente no mesmo ponto em 10s.','warn');
      schedule(10000);
    }
  }

  async function start(){
    if(active)return;
    renderFindHistory();
    if(!apiBase)await loadConfig();
    if(!apiBase){setStatus('Serviço de pesquisa não conectado. Atualize a página e tente novamente.','bad');return;}
    await askNotifications();
    active=true;blockStreak=0;previousAvailable=new Set();locationIndex=0;discoveryIndex=0;steadyChecks=0;citySnapshots.clear();
    activeLocations=restoreFastPlan();
    discoveryMode=activeLocations.length===0;
    qs('#appleStart').disabled=true;qs('#appleStop').disabled=false;
    if(discoveryMode){
      setStatus(`▶ Monitor iniciado em calibração rápida. Primeiro testa pontos estratégicos e só adiciona outros se necessário para cobrir as ${TARGET_STORE_COUNT} lojas.`,'live');
    }else{
      const delay=queryDelay();
      const cycle=Math.round(activeLocations.length*delay/1000);
      setStatus(`▶ Monitor iniciado com plano rápido salvo: ${activeLocations.length} ponto(s), ciclo estimado de ~${cycle}s para as ${TARGET_STORE_COUNT} lojas.`,'live');
    }
    qs('#appleFrequency').textContent=(queryDelay()/1000).toFixed(queryDelay()%1000?1:0)+' segundos';
    checkNow();
  }

  function stop(){
    active=false;clearTimeout(timer);timer=null;
    qs('#appleStart').disabled=false;qs('#appleStop').disabled=true;
    qs('#appleFrequency').textContent=(queryDelay()/1000).toFixed(queryDelay()%1000?1:0)+' segundos';
    setStatus('Monitor parado.','');
  }

  function activate(){
    renderFindHistory();
    qs('#productsApp')&&(qs('#productsApp').hidden=true);
    qs('#flightsApp')&&(qs('#flightsApp').hidden=true);
    qs('#indigoApp')&&(qs('#indigoApp').hidden=true);
    document.querySelectorAll('.main-tab').forEach(x=>x.classList.toggle('active',x===tab));
    app.hidden=false;
  }

  tab.addEventListener('click',activate);
  document.querySelectorAll('.main-tab').forEach(b=>{if(b!==tab)b.addEventListener('click',()=>{app.hidden=true;});});
  qs('#appleStart').addEventListener('click',start);
  qs('#appleStop').addEventListener('click',stop);
  document.addEventListener('visibilitychange',()=>{
    if(!active)return;
    if(document.hidden){clearTimeout(timer);timer=null;}
    else{setStatus('↻ Retomando monitor da Apple…','live');checkNow();}
  });

  renderFindHistory();
  loadConfig();
})();