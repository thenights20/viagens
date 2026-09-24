(() => {
  const qs = s => document.querySelector(s);
  if (qs('#appleStockApp') || !qs('.main-tabs')) return;

  const PRODUCT = 'iPhone 18 Pro Max Burgundy · 256GB';
  const LOCATIONS = [
    { label: 'Fort Lauderdale', value: 'Fort Lauderdale, FL' },
    { label: 'Orlando', value: 'Orlando, FL' },
    { label: 'Tampa', value: 'Tampa, FL' }
  ];
  const APPLE_URL = 'https://www.apple.com/shop/buy-iphone/iphone-18-pro';
  const NORMAL_DELAY = 5000;
  let apiBase = '';
  let active = false;
  let timer = null;
  let blockStreak = 0;
  let previousAvailable = new Set();
  let checks = 0;
  let audioCtx = null;
  let locationIndex = 0;
  const citySnapshots = new Map();

  const style = document.createElement('style');
  style.textContent = `
    .apple-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;margin:5px 0 16px}
    .apple-head h2{margin:0 0 5px;font-size:24px}.apple-head .sub{max-width:900px}
    .apple-form{padding:15px;display:grid;grid-template-columns:2fr 1fr 1fr;gap:11px;align-items:end;margin-bottom:15px}
    .apple-field label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 5px}
    .apple-fixed{display:flex;align-items:center;min-height:42px;padding:0 12px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);font-weight:800}
    .apple-actions{display:flex;gap:9px;align-items:center;grid-column:1/-1;flex-wrap:wrap}
    .apple-start,.apple-stop{border:0;cursor:pointer;font-weight:900;padding:11px 16px;border-radius:10px;min-width:170px}
    .apple-start{background:var(--accent);color:#07111f}.apple-stop{background:var(--panel2);color:var(--hot);border:1px solid var(--hot)}
    .apple-start:disabled,.apple-stop:disabled{opacity:.45;cursor:not-allowed}
    .apple-link{display:inline-flex;align-items:center;text-decoration:none;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-weight:800;padding:10px 13px;border-radius:10px}
    .apple-status{padding:13px 15px;border:1px solid var(--line);border-radius:12px;background:var(--panel2);margin:0 0 14px;color:var(--muted);line-height:1.45}
    .apple-status.live{color:var(--accent)}.apple-status.ok{color:var(--ok);border-color:var(--ok);font-weight:800}.apple-status.warn{color:var(--warn);border-color:var(--warn)}.apple-status.bad{color:var(--hot);border-color:var(--hot)}
    .apple-alert{padding:18px;margin:0 0 15px;border:2px solid var(--ok);border-radius:15px;background:color-mix(in srgb,var(--ok) 10%,var(--panel));animation:applePulse 1s ease-in-out infinite alternate}
    .apple-alert b{display:block;color:var(--ok);font-size:23px;margin-bottom:5px}.apple-alert span{font-size:15px}
    @keyframes applePulse{from{box-shadow:0 0 0 rgba(91,214,160,0)}to{box-shadow:0 0 28px rgba(91,214,160,.24)}}
    .apple-summary{grid-template-columns:repeat(4,1fr)}
    .apple-stores{display:grid;grid-template-columns:repeat(3,minmax(230px,1fr));gap:10px;padding:13px}
    .apple-store{border:1px solid var(--line);background:var(--panel2);border-radius:13px;padding:14px;min-height:145px;display:flex;flex-direction:column;justify-content:space-between;gap:10px}
    .apple-store.available{border-color:var(--ok);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--ok) 35%,transparent)}
    .apple-store h3{margin:0 0 4px;font-size:16px}.apple-store .where{color:var(--muted);font-size:11px;line-height:1.4}
    .apple-store .state{font-weight:950;font-size:12px}.apple-store.available .state{color:var(--ok)}.apple-store.unavailable .state{color:var(--hot)}.apple-store.unknown .state{color:var(--warn)}
    .apple-store .quote{color:var(--muted);font-size:11px;line-height:1.4}.apple-store .distance{font-size:11px;color:var(--accent);font-weight:800}
    .apple-note{margin-top:12px}
    @media(max-width:1000px){.apple-form{grid-template-columns:1fr 1fr}.apple-stores{grid-template-columns:repeat(2,1fr)}.apple-summary{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:700px){.apple-form{grid-template-columns:1fr}.apple-actions{grid-column:1}.apple-stores{grid-template-columns:1fr}.apple-actions>*{flex:1;justify-content:center}}
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
      <div><h2>🍎 Monitor de estoque · Fort Lauderdale · Orlando · Tampa</h2><div class="sub">Monitora retirada em loja do <b>${PRODUCT}</b>, somente <b>256GB Burgundy</b>, nas cidades de <b>Fort Lauderdale, Orlando e Tampa</b>. O monitor alterna uma cidade a cada 5 segundos; cada cidade é reconsultada aproximadamente a cada 15 segundos.</div></div>
      <a class="apple-link" href="${APPLE_URL}" target="_blank" rel="noopener">Abrir produto na Apple ↗</a>
    </div>

    <section class="panel apple-form">
      <div class="apple-field"><label>Produto monitorado</label><div class="apple-fixed">${PRODUCT}</div></div>
      <div class="apple-field"><label>Cidades monitoradas</label><div class="apple-fixed">Fort Lauderdale · Orlando · Tampa</div></div>
      <div class="apple-field"><label>Frequência</label><div class="apple-fixed" id="appleFrequency">5 segundos</div></div>
      <div class="apple-actions">
        <button id="appleStart" class="apple-start">▶ Monitorar agora</button>
        <button id="appleStop" class="apple-stop" disabled>■ Parar</button>
        <span class="sub" id="appleHint">Somente lojas localizadas nessas três cidades entram no resultado.</span>
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
      <div class="empty" id="appleEmpty"><strong>Aguardando primeira consulta.</strong>O monitor mostrará aqui somente lojas de Fort Lauderdale, Orlando e Tampa.</div>
    </section>

    <div class="note apple-note"><b>Como o alerta funciona:</b> “Disponível” só aparece quando a própria Apple informa retirada habilitada para a variante monitorada. Se a Apple limitar as consultas, o painel mostra “bloqueado/aguardando” e reduz temporariamente a frequência — nunca converte bloqueio em “sem estoque”. O monitor de 5 segundos depende desta página permanecer aberta; navegadores móveis podem suspender timers quando a aba fica em segundo plano ou a tela é bloqueada.</div>
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
    if(newly.length)notifyNew(newly);
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
    qs('#appleFrequency').textContent=(delay/1000)+' segundos';
    timer=setTimeout(checkNow,delay);
  }

  async function checkNow(){
    if(!active)return;
    if(document.hidden){setStatus('⏸ Monitor ativo, mas a aba está em segundo plano. Retomarei ao voltar para esta página.','warn');return;}
    const target=LOCATIONS[locationIndex%LOCATIONS.length];
    locationIndex=(locationIndex+1)%LOCATIONS.length;
    setStatus(`🔎 Consultando estoque oficial da Apple em ${target.label}…`,'live');
    try{
      const data=await jsonpAvailability(target.value,45000);
      if(!active)return;
      if(!data||data.ok!==true){
        if(data&&data.blocked){
          blockStreak+=1;
          const delay=blockStreak>=3?60000:blockStreak===2?30000:15000;
          setStatus(`⚠️ A Apple limitou temporariamente as consultas (HTTP ${data.http_status||'—'}). Nova tentativa em ${delay/1000}s.`,'warn');
          schedule(delay);return;
        }
        blockStreak=0;
        setStatus('⚠️ '+String(data&&data.error||'Resposta da Apple não confirmada.')+' Nova tentativa em 10s.','warn');
        schedule(10000);return;
      }
      blockStreak=0;
      const cityStores=(Array.isArray(data.stores)?data.stores:[]).map(x=>({...x,search_area:target.label}));
      citySnapshots.set(target.label,{stores:cityStores,checked_at:data.checked_at});
      const merged=new Map();
      for(const snap of citySnapshots.values()){
        for(const store of snap.stores){
          const key=storeKey(store);
          const prev=merged.get(key);
          if(!prev||store.available===true||prev.available!==true)merged.set(key,store);
        }
      }
      const stores=[...merged.values()];
      const available=stores.filter(x=>x.available===true);
      render({...data,stores,stores_count:stores.length,available_count:available.length,any_available:available.length>0});
      const missing=Array.isArray(data.missing_variants)?data.missing_variants:[];
      if(missing.length)setStatus('⚠️ Variante 256GB ainda sem SKU configurado no serviço.','warn');
      const n=available.length;
      const loaded=citySnapshots.size;
      setStatus(n?`✅ ${n} loja(s) com retirada disponível agora em Fort Lauderdale, Orlando ou Tampa.`:`Monitorando ${loaded}/3 cidades: ${stores.length} loja(s) verificadas, nenhuma com retirada disponível neste momento.`,n?'ok':'live');
      schedule(NORMAL_DELAY);
    }catch(err){
      if(!active)return;
      setStatus('⚠️ '+String(err&&err.message||err)+' Tentarei novamente em 10s.','warn');
      schedule(10000);
    }
  }

  async function start(){
    if(active)return;
    if(!apiBase)await loadConfig();
    if(!apiBase){setStatus('Serviço de pesquisa não conectado. Atualize a página e tente novamente.','bad');return;}
    await askNotifications();
    active=true;blockStreak=0;previousAvailable=new Set();locationIndex=0;citySnapshots.clear();
    qs('#appleStart').disabled=true;qs('#appleStop').disabled=false;
    setStatus('▶ Monitor iniciado. Alternando Fort Lauderdale, Orlando e Tampa a cada 5 segundos.','live');
    checkNow();
  }

  function stop(){
    active=false;clearTimeout(timer);timer=null;
    qs('#appleStart').disabled=false;qs('#appleStop').disabled=true;
    qs('#appleFrequency').textContent='5 segundos';
    setStatus('Monitor parado.','');
  }

  function activate(){
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

  loadConfig();
})();