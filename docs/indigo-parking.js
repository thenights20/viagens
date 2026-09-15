(() => {
  const qs = s => document.querySelector(s);
  if (qs('#indigoApp') || !qs('.main-tabs')) return;

  const BOOKING_URL = 'https://indigoneo.com.br/pt/booking/99980448';
  const RESULT_URL = './data/indigo-parking-search.json';
  let apiBase = '';
  let searching = false;
  let lastData = null;

  const style = document.createElement('style');
  style.textContent = `
    .indigo-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;margin:5px 0 16px}
    .indigo-head h2{margin:0 0 5px;font-size:24px}.indigo-head .sub{max-width:820px}
    .indigo-form{padding:15px;display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:11px;margin-bottom:15px}
    .indigo-field label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 5px}
    .indigo-actions{display:flex;gap:9px;align-items:center;grid-column:1/-1;flex-wrap:wrap}
    .indigo-search{border:0;cursor:pointer;background:var(--accent);color:#07111f;font-weight:900;padding:11px 16px;border-radius:10px;min-width:190px}
    .indigo-search:disabled{opacity:.55;cursor:wait}.indigo-link{display:inline-flex;align-items:center;text-decoration:none;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-weight:800;padding:10px 13px;border-radius:10px}
    .indigo-status{padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel2);margin:0 0 15px;color:var(--muted)}
    .indigo-status.ok{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 50%,var(--line))}.indigo-status.bad{color:var(--hot);border-color:color-mix(in srgb,var(--hot) 50%,var(--line))}.indigo-status.wait{color:var(--warn)}
    .indigo-summary{grid-template-columns:repeat(4,1fr)}.indigo-summary .best b{font-size:19px;color:var(--ok)}
    .indigo-slots{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:9px;padding:13px}
    .indigo-slot{border:1px solid var(--line);background:var(--panel2);border-radius:12px;padding:13px;min-height:112px;display:flex;flex-direction:column;justify-content:space-between;gap:9px}
    .indigo-route-time{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.indigo-route-time strong{font-size:18px}.indigo-arrow{color:var(--muted);font-weight:900}.indigo-time-label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px}
    .indigo-slot small{color:var(--muted);line-height:1.35}.indigo-slot.available{border-color:var(--ok);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--ok) 35%,transparent)}
    .indigo-slot.available strong,.indigo-slot.available .indigo-state{color:var(--ok)}.indigo-slot.sold_out .indigo-state{color:var(--hot)}.indigo-slot.error .indigo-state{color:var(--warn)}
    .indigo-state{font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}.indigo-best{font-size:11px;color:var(--ok);font-weight:900}.indigo-price{font-size:12px;font-weight:900;color:var(--text);margin-top:3px}
    .indigo-note{margin-top:12px}.indigo-empty{padding:28px;text-align:center;color:var(--muted)}.indigo-hint{color:var(--muted)}.indigo-hint strong{color:var(--accent)}
    @media(max-width:1100px){.indigo-form{grid-template-columns:repeat(3,1fr)}.indigo-slots{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:700px){.indigo-form{grid-template-columns:1fr 1fr}.indigo-slots{grid-template-columns:1fr 1fr}.indigo-summary{grid-template-columns:repeat(2,1fr)}.indigo-actions>*{flex:1;justify-content:center}.indigo-form .wide{grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const tab = document.createElement('button');
  tab.className = 'main-tab';
  tab.dataset.main = 'indigo';
  tab.textContent = '🚗 Estacionamento GRU';
  qs('.main-tabs').appendChild(tab);

  const app = document.createElement('main');
  app.id = 'indigoApp';
  app.hidden = true;
  app.innerHTML = `
    <div class="indigo-head">
      <div><h2>🚗 Indigo · Aeroporto de Guarulhos</h2><div class="sub">Teste várias combinações de <b>entrada e saída</b> para descobrir quais liberam vaga no estacionamento da Indigo.</div></div>
      <a class="indigo-link" href="${BOOKING_URL}" target="_blank" rel="noopener">Abrir Indigo ↗</a>
    </div>

    <section class="panel indigo-form">
      <div class="indigo-field"><label>Entrada · data inicial</label><input id="indigoEntryDateFrom" type="date"></div>
      <div class="indigo-field"><label>Entrada · data final</label><input id="indigoEntryDateTo" type="date"></div>
      <div class="indigo-field"><label>Entrada a partir de</label><input id="indigoEntryFrom" type="time" step="1800" value="12:00"></div>
      <div class="indigo-field"><label>Entrada até</label><input id="indigoEntryTo" type="time" step="1800" value="15:00"></div>

      <div class="indigo-field"><label>Saída · data inicial</label><input id="indigoExitDateFrom" type="date"></div>
      <div class="indigo-field"><label>Saída · data final</label><input id="indigoExitDateTo" type="date"></div>
      <div class="indigo-field"><label>Saída a partir de</label><input id="indigoExitFrom" type="time" step="1800" value="06:00"></div>
      <div class="indigo-field"><label>Saída até</label><input id="indigoExitTo" type="time" step="1800" value="09:00"></div>

      <div class="indigo-field"><label>Estacionamento</label><select id="indigoProduct"><option value="terminal3_garage" selected>T3 Edifício Garagem · coberto</option><option value="terminal3_flex">T3 Flex</option><option value="terminal2_standard">Terminal 2 Standard</option><option value="terminal1">Terminal 1</option><option value="any">Qualquer opção disponível</option></select></div>
      <div class="indigo-field"><label>Intervalo</label><select id="indigoStep"><option value="30" selected>30 minutos · recomendado</option><option value="60">60 minutos · rápido</option></select></div>
      <div class="indigo-field"><label>Exibição</label><select id="indigoShow"><option value="all" selected>Todas as combinações</option><option value="available">Só disponíveis</option></select></div>
      <div class="indigo-actions"><button class="indigo-search" id="indigoSearchButton">🔎 Pesquisar combinações</button><span class="indigo-hint" id="indigoHint">Calculando combinações…</span></div>
    </section>

    <div class="indigo-status" id="indigoStatus">Escolha as faixas de entrada e saída para pesquisar.</div>

    <section class="cards indigo-summary">
      <div class="card"><span>Combinações testadas</span><b id="indigoTested">—</b></div>
      <div class="card"><span>Disponíveis</span><b id="indigoAvailable">—</b></div>
      <div class="card best"><span>Melhor combinação</span><b id="indigoBest">—</b></div>
      <div class="card"><span>Última consulta</span><b id="indigoUpdated" style="font-size:16px">—</b></div>
    </section>

    <section class="panel"><div class="indigo-slots" id="indigoSlots"></div><div class="indigo-empty" id="indigoEmpty">Ainda não há resultado para esta pesquisa.</div></section>
    <div class="note indigo-note"><b>Como usar:</b> o sistema cruza todos os horários de entrada com todos os horários de saída. Um bloco verde mostra exatamente a combinação que vale tentar no site da Indigo. A disponibilidade pode mudar a qualquer momento.</div>
  `;
  const flightsApp = qs('#flightsApp');
  if (flightsApp) flightsApp.after(app); else document.querySelector('.wrap').appendChild(app);

  function localDate(days=0){const d=new Date();d.setDate(d.getDate()+days);const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`;}
  qs('#indigoEntryDateFrom').value=localDate(1);
  qs('#indigoEntryDateTo').value=localDate(1);
  qs('#indigoExitDateFrom').value=localDate(22);
  qs('#indigoExitDateTo').value=localDate(22);

  async function loadConfig(){try{const r=await fetch('./data/flight-search-config.json?t='+Date.now(),{cache:'no-store'});const d=await r.json();apiBase=String(d.api_base||'').trim();}catch{apiBase='';}}
  function requestId(){const suffix=globalThis.crypto&&crypto.randomUUID?crypto.randomUUID().replace(/-/g,''):Date.now().toString(36)+Math.random().toString(36).slice(2);return ('indigo_'+suffix).slice(0,64);}
  function mins(v){const [h,m]=String(v||'').split(':').map(Number);return h*60+m;}
  function slots(a,b,step){if(!a||!b||mins(b)<mins(a))return 0;return Math.floor((mins(b)-mins(a))/step)+1;}
  function halfHour(v){return /^(?:[01]\d|2[0-3]):(?:00|30)$/.test(String(v||''));}
  function dates(a,b){if(!a||!b||b<a)return[];const out=[];for(let d=new Date(a+'T12:00:00Z'),end=new Date(b+'T12:00:00Z');d<=end;d.setUTCDate(d.getUTCDate()+1))out.push(d.toISOString().slice(0,10));return out;}
  function formRequest(){return{
    entry_date_from:qs('#indigoEntryDateFrom').value,
    entry_date_to:qs('#indigoEntryDateTo').value,
    exit_date_from:qs('#indigoExitDateFrom').value,
    exit_date_to:qs('#indigoExitDateTo').value,
    entry_from_time:qs('#indigoEntryFrom').value,
    entry_to_time:qs('#indigoEntryTo').value,
    exit_from_time:qs('#indigoExitFrom').value,
    exit_to_time:qs('#indigoExitTo').value,
    step_minutes:Number(qs('#indigoStep').value),
    product:qs('#indigoProduct').value,
    request_id:requestId()
  };}
  function timeValues(a,b,step){const out=[];if(!a||!b||mins(b)<mins(a))return out;for(let m=mins(a);m<=mins(b);m+=step)out.push(`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`);return out;}
  function estimated(r){const ed=dates(r.entry_date_from,r.entry_date_to),xd=dates(r.exit_date_from,r.exit_date_to),et=timeValues(r.entry_from_time,r.entry_to_time,r.step_minutes),xt=timeValues(r.exit_from_time,r.exit_to_time,r.step_minutes);let n=0;for(const a of ed)for(const at of et)for(const b of xd)for(const bt of xt)if(`${b}T${bt}`>`${a}T${at}`)n++;return n;}
  function updateHint(){const r=formRequest(),n=estimated(r),ed=dates(r.entry_date_from,r.entry_date_to).length,xd=dates(r.exit_date_from,r.exit_date_to).length;qs('#indigoHint').innerHTML=n?`Serão testadas <strong>${n}</strong> combinações · ${ed} dia(s) de entrada × ${xd} dia(s) de saída.`:'Defina faixas válidas.';}
  function validate(r){
    if(!r.entry_date_from||!r.entry_date_to||!r.exit_date_from||!r.exit_date_to)return'Informe as quatro datas da faixa.';
    if(r.entry_date_to<r.entry_date_from)return'A data final de entrada precisa ser igual ou posterior à inicial.';
    if(r.exit_date_to<r.exit_date_from)return'A data final de saída precisa ser igual ou posterior à inicial.';
    if(r.exit_date_to<r.entry_date_from)return'A faixa de saída termina antes da faixa de entrada.';
    if(dates(r.entry_date_from,r.entry_date_to).length>7||dates(r.exit_date_from,r.exit_date_to).length>7)return'Cada faixa de datas pode ter no máximo 7 dias.';
    if(![r.entry_from_time,r.entry_to_time,r.exit_from_time,r.exit_to_time].every(halfHour))return'Na Indigo os horários precisam terminar em :00 ou :30.';
    if(r.entry_to_time<r.entry_from_time)return'O fim da faixa de entrada precisa ser depois do início.';
    if(r.exit_to_time<r.exit_from_time)return'O fim da faixa de saída precisa ser depois do início.';
    const n=estimated(r);if(!n)return'Nenhuma combinação válida.';if(n>3000)return`Essa faixa gera ${n} combinações. O máximo por varredura é 3.000; reduza datas ou horários.`;
    return'';
  }
  function postSearch(r){const url=`${apiBase}?route=${encodeURIComponent('api/indigo/search')}&t=${Date.now()}`;return fetch(url,{method:'POST',mode:'no-cors',cache:'no-store',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(r)});}
  async function readResult(){try{const x=await fetch(RESULT_URL+'?t='+Date.now(),{cache:'no-store'});if(!x.ok)return null;return await x.json();}catch{return null;}}
  function bridgeJsonp(route,timeoutMs=12000){return new Promise((resolve,reject)=>{if(!apiBase){reject(new Error('Serviço de pesquisa não conectado.'));return;}const cb='indigoCb_'+Date.now().toString(36)+Math.random().toString(36).slice(2);const script=document.createElement('script');const timer=setTimeout(()=>finish(new Error('Serviço demorou para responder.')),timeoutMs);function finish(err,value){clearTimeout(timer);try{delete window[cb]}catch{}script.remove();err?reject(err):resolve(value);}window[cb]=value=>finish(null,value);script.onerror=()=>finish(new Error('Não foi possível consultar o serviço.'));script.src=`${apiBase}?route=${encodeURIComponent(route)}&callback=${encodeURIComponent(cb)}&t=${Date.now()}`;document.head.appendChild(script);});}
  function sameRequest(data,r){const q=data?.request||{};return data?.request_id===r.request_id&&String(q.entry_date_from||q.entry_date||'')===r.entry_date_from&&String(q.entry_date_to||q.entry_date||'')===r.entry_date_to&&String(q.exit_date_from||q.exit_date||'')===r.exit_date_from&&String(q.exit_date_to||q.exit_date||'')===r.exit_date_to&&String(q.entry_from_time||q.from_time||'')===r.entry_from_time&&String(q.entry_to_time||q.to_time||'')===r.entry_to_time&&String(q.exit_from_time||q.exit_time||'')===r.exit_from_time&&String(q.exit_to_time||q.exit_time||'')===r.exit_to_time&&Number(q.step_minutes)===Number(r.step_minutes)&&q.product===r.product;}
  function fmtDateTime(v){try{return new Date(v).toLocaleString('pt-BR')}catch{return'—'}}
  function money(v){return Number.isFinite(Number(v))&&Number(v)>0?new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v)):'';}
  function pickBest(data){if(data?.best_combination)return data.best_combination;return [...(data?.results||[])].filter(x=>x.available===true).sort((a,b)=>(Number(a.price??Infinity)-Number(b.price??Infinity))||String(a.entry_date).localeCompare(String(b.entry_date))||String(a.entry_time).localeCompare(String(b.entry_time))||String(a.exit_date).localeCompare(String(b.exit_date))||String(a.exit_time).localeCompare(String(b.exit_time)))[0]||null;}
  function render(data){
    lastData=data;
    const all=[...(data.results||[])];
    const show=qs('#indigoShow').value;
    const rows=show==='available'?all.filter(x=>x.available===true):all;
    const available=all.filter(x=>x.available===true);
    const best=pickBest(data);
    qs('#indigoTested').textContent=String(data.stats?.tested_combinations??all.length);
    qs('#indigoAvailable').textContent=String(data.stats?.available_combinations??available.length);
    qs('#indigoBest').textContent=best?`${best.entry_date.slice(5).split('-').reverse().join('/')} ${best.entry_time} → ${best.exit_date.slice(5).split('-').reverse().join('/')} ${best.exit_time}`:'Nenhuma';
    qs('#indigoUpdated').textContent=data.generated_at?fmtDateTime(data.generated_at):'—';
    const box=qs('#indigoSlots');box.innerHTML='';qs('#indigoEmpty').hidden=rows.length>0;
    if(!rows.length){qs('#indigoEmpty').textContent=show==='available'?'Nenhuma combinação disponível nesta varredura.':'Nenhuma combinação retornada.';return;}
    for(const x of rows){
      const div=document.createElement('div');const isBest=best&&x.available===true&&x.entry_date===best.entry_date&&x.entry_time===best.entry_time&&x.exit_date===best.exit_date&&x.exit_time===best.exit_time;const cls=x.available===true?'available':x.status==='error'?'error':'sold_out';const label=x.available===true?'DISPONÍVEL':x.status==='error'?'ERRO':x.status==='not_offered'?'NÃO OFERTADO':'ESGOTADO';
      div.className='indigo-slot '+cls;
      const ed=String(x.entry_date||'').slice(5).split('-').reverse().join('/'),xd=String(x.exit_date||'').slice(5).split('-').reverse().join('/');
      div.innerHTML=`<div>${isBest?'<div class="indigo-best">★ MELHOR COMBINAÇÃO</div>':''}<div class="indigo-route-time"><div><span class="indigo-time-label">Entrada · ${ed}</span><strong>${String(x.entry_time||'—')}</strong></div><span class="indigo-arrow">→</span><div><span class="indigo-time-label">Saída · ${xd}</span><strong>${String(x.exit_time||'—')}</strong></div></div></div><div><div class="indigo-state">${label}</div>${x.available===true&&money(x.price)?`<div class="indigo-price">${money(x.price)}</div>`:''}<small>${x.available===true?'Essa combinação liberou vaga':'Combinação testada'}</small></div>`;
      box.appendChild(div);
    }
    const status=qs('#indigoStatus');status.className='indigo-status '+(available.length?'ok':'bad');
    status.textContent=available.length?`✅ ${available.length} combinação(ões) liberaram vaga. Melhor: entrada ${best.entry_date} ${best.entry_time} · saída ${best.exit_date} ${best.exit_time}${money(best.price)?' · '+money(best.price):''}.`:'Nenhuma combinação disponível nas faixas testadas. Amplie as datas ou os horários.';
  }
  async function poll(r){
    const status=qs('#indigoStatus'),started=Date.now(),timeoutMs=45*60*1000;
    while(Date.now()-started<timeoutMs){
      await new Promise(ok=>setTimeout(ok,2500));let bridge=null;try{bridge=await bridgeJsonp('api/indigo/search/'+r.request_id,10000);}catch{}
      if(bridge?.status==='error')throw new Error(bridge.error||'A pesquisa terminou com erro.');
      if(bridge?.status==='done'&&bridge.result){render(bridge.result);return bridge.result;}
      const data=await readResult();if(data?.status==='error'&&data.request_id===r.request_id)throw new Error(data.error||'A pesquisa terminou com erro.');if(data?.status==='completed'&&sameRequest(data,r)){render(data);return data;}
      const sec=Math.round((Date.now()-started)/1000),phase=bridge?.status==='queued'?'na fila':bridge?.status==='in_progress'?'testando combinações na Indigo':bridge?.status==='running'?'iniciando busca':'aguardando execução';status.textContent=`🔎 ${phase}… ${sec}s`;
    }
    throw new Error('A pesquisa excedeu 45 minutos. Tente reduzir as datas ou horários e pesquisar novamente.');
  }
  async function search(){
    if(searching)return;const r=formRequest(),err=validate(r),status=qs('#indigoStatus'),btn=qs('#indigoSearchButton');if(err){status.className='indigo-status bad';status.textContent=err;return;}if(!apiBase)await loadConfig();if(!apiBase){status.className='indigo-status bad';status.textContent='Serviço de pesquisa não conectado. Atualize a página e tente novamente.';return;}
    searching=true;btn.disabled=true;btn.textContent='⏳ Pesquisando…';status.className='indigo-status wait';status.textContent=`Enviando ${estimated(r)} combinações para varredura…`;
    try{await postSearch(r);await poll(r);}catch(e){status.className='indigo-status bad';status.textContent='Não foi possível concluir: '+String(e?.message||e);}finally{searching=false;btn.disabled=false;btn.textContent='🔎 Pesquisar combinações';}
  }
  function activate(){if(typeof window.setMain==='function')window.setMain('indigo');else{qs('#productsApp')&&(qs('#productsApp').hidden=true);qs('#flightsApp')&&(qs('#flightsApp').hidden=true);document.querySelectorAll('.main-tab').forEach(x=>x.classList.toggle('active',x===tab));}app.hidden=false;}
  tab.addEventListener('click',activate);document.querySelectorAll('.main-tab').forEach(b=>{if(b!==tab)b.addEventListener('click',()=>{app.hidden=true;});});
  qs('#indigoSearchButton').addEventListener('click',search);qs('#indigoShow').addEventListener('change',()=>{if(lastData)render(lastData);});
  ['indigoEntryDateFrom','indigoEntryDateTo','indigoExitDateFrom','indigoExitDateTo','indigoEntryFrom','indigoEntryTo','indigoExitFrom','indigoExitTo','indigoStep'].forEach(id=>qs('#'+id).addEventListener('change',updateHint));
  loadConfig();updateHint();
})();
