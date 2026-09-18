(() => {
  const qs = s => document.querySelector(s);
  if (qs('#indigoApp') || !qs('.main-tabs')) return;

  const BOOKING_URL = 'https://indigoneo.com.br/pt/booking/99980448';
  const RESULT_URL = './data/indigo-parking-search.json';
  const PAGE_SIZE = 200;
  let apiBase = '';
  let searching = false;
  let lastData = null;
  let activeFilter = 'all';
  let visibleLimit = PAGE_SIZE;

  const style = document.createElement('style');
  style.textContent = `
    .indigo-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;margin:5px 0 16px}
    .indigo-head h2{margin:0 0 5px;font-size:24px}.indigo-head .sub{max-width:850px}
    .indigo-form{padding:15px;display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:11px;margin-bottom:15px}
    .indigo-field label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 5px}
    .indigo-fixed{display:flex;align-items:center;min-height:42px;padding:0 12px;border:1px solid var(--line);border-radius:9px;background:var(--panel2);font-weight:800}
    .indigo-actions{display:flex;gap:9px;align-items:center;grid-column:1/-1;flex-wrap:wrap}
    .indigo-search{border:0;cursor:pointer;background:var(--accent);color:#07111f;font-weight:900;padding:11px 16px;border-radius:10px;min-width:205px}
    .indigo-search:disabled{opacity:.55;cursor:wait}.indigo-link{display:inline-flex;align-items:center;text-decoration:none;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-weight:800;padding:10px 13px;border-radius:10px}
    .indigo-hint{color:var(--muted);line-height:1.4}.indigo-hint strong{color:var(--accent)}.indigo-hint.warn{color:var(--warn)}
    .indigo-status{padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel2);margin:0 0 10px;color:var(--muted)}
    .indigo-status.ok{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 50%,var(--line))}.indigo-status.bad{color:var(--hot);border-color:color-mix(in srgb,var(--hot) 50%,var(--line))}.indigo-status.wait{color:var(--warn)}
    .indigo-progress{height:10px;border:1px solid var(--line);border-radius:999px;background:var(--panel2);overflow:hidden;margin:0 0 15px}.indigo-progress>span{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--ok));transition:width .3s ease}
    .indigo-best-card{padding:16px 18px;margin:0 0 15px;border:1px solid var(--ok);border-radius:14px;background:color-mix(in srgb,var(--ok) 8%,var(--panel));display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
    .indigo-best-card .title{font-size:12px;font-weight:900;color:var(--ok);text-transform:uppercase;letter-spacing:.06em}.indigo-best-card .route{font-size:22px;font-weight:950;margin-top:4px}.indigo-best-card .price{font-size:24px;font-weight:950;color:var(--ok)}
    .indigo-summary{grid-template-columns:repeat(5,1fr)}.indigo-summary .best b{font-size:19px;color:var(--ok)}
    .indigo-filters{display:flex;gap:7px;flex-wrap:wrap;padding:12px 13px 0}.indigo-filter{border:1px solid var(--line);background:var(--panel2);color:var(--text);border-radius:999px;padding:8px 12px;font-weight:800;cursor:pointer}.indigo-filter.active{background:var(--accent);border-color:var(--accent);color:#07111f}
    .indigo-results-head{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:12px 13px 0}.indigo-results-head b{font-size:14px}.indigo-results-head span{color:var(--muted);font-size:12px}
    .indigo-slots{display:grid;grid-template-columns:repeat(5,minmax(150px,1fr));gap:9px;padding:13px}
    .indigo-slot{border:1px solid var(--line);background:var(--panel2);border-radius:12px;padding:13px;min-height:118px;display:flex;flex-direction:column;justify-content:space-between;gap:9px}
    .indigo-route-time{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.indigo-route-time strong{font-size:18px}.indigo-arrow{color:var(--muted);font-weight:900}.indigo-time-label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px}
    .indigo-slot small{color:var(--muted);line-height:1.35}.indigo-slot.available{border-color:var(--ok);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--ok) 35%,transparent)}
    .indigo-slot.available strong,.indigo-slot.available .indigo-state{color:var(--ok)}.indigo-slot.sold_out .indigo-state{color:var(--hot)}.indigo-slot.unconfirmed .indigo-state{color:var(--warn)}
    .indigo-state{font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}.indigo-best{font-size:11px;color:var(--ok);font-weight:900}.indigo-price{font-size:14px;font-weight:950;color:var(--text);margin-top:3px}
    .indigo-note{margin-top:12px}.indigo-empty{padding:28px;text-align:center;color:var(--muted)}.indigo-more{display:block;margin:0 auto 15px;border:1px solid var(--line);background:var(--panel2);color:var(--text);padding:9px 15px;border-radius:9px;font-weight:800;cursor:pointer}
    @media(max-width:1100px){.indigo-form{grid-template-columns:repeat(3,1fr)}.indigo-slots{grid-template-columns:repeat(3,1fr)}.indigo-summary{grid-template-columns:repeat(3,1fr)}}
    @media(max-width:700px){.indigo-form{grid-template-columns:1fr 1fr}.indigo-slots{grid-template-columns:1fr}.indigo-summary{grid-template-columns:repeat(2,1fr)}.indigo-actions>*{flex:1;justify-content:center}.indigo-form .wide{grid-column:1/-1}.indigo-best-card .route{font-size:18px}}
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
      <div><h2>🚗 Caçador de disponibilidade · Indigo GRU</h2><div class="sub">Cruze vários dias e horários de <b>entrada × saída</b>. Verde só aparece após o T3 Edifício Garagem ser encontrado com <b>SoldOut = false</b>, preço válido e confirmação repetida da Indigo.</div></div>
      <a class="indigo-link" href="${BOOKING_URL}" target="_blank" rel="noopener">Abrir Indigo ↗</a>
    </div>

    <section class="panel indigo-form">
      <div class="indigo-field"><label>Data inicial de entrada</label><input id="indigoEntryDateFrom" type="date"></div>
      <div class="indigo-field"><label>Data final de entrada</label><input id="indigoEntryDateTo" type="date"></div>
      <div class="indigo-field"><label>Horário inicial de entrada</label><input id="indigoEntryFrom" type="time" step="1800" value="12:00"></div>
      <div class="indigo-field"><label>Horário final de entrada</label><input id="indigoEntryTo" type="time" step="1800" value="15:00"></div>

      <div class="indigo-field"><label>Data inicial de saída</label><input id="indigoExitDateFrom" type="date"></div>
      <div class="indigo-field"><label>Data final de saída</label><input id="indigoExitDateTo" type="date"></div>
      <div class="indigo-field"><label>Horário inicial de saída</label><input id="indigoExitFrom" type="time" step="1800" value="06:00"></div>
      <div class="indigo-field"><label>Horário final de saída</label><input id="indigoExitTo" type="time" step="1800" value="09:00"></div>

      <div class="indigo-field wide"><label>Estacionamento</label><select id="indigoProduct"><option value="terminal3_garage" selected>T3 Edifício Garagem · coberto</option><option value="terminal3_flex">T3 Flex</option><option value="terminal2_standard">Terminal 2 Standard</option><option value="terminal1">Terminal 1</option><option value="any">Qualquer opção disponível</option></select></div>
      <div class="indigo-field"><label>Intervalo</label><div class="indigo-fixed">30 minutos</div></div>
      <div class="indigo-actions"><button class="indigo-search" id="indigoSearchButton">🔎 Caçar disponibilidade</button><span class="indigo-hint" id="indigoHint">Calculando combinações…</span></div>
    </section>

    <div class="indigo-status" id="indigoStatus">Escolha as faixas de entrada e saída para pesquisar.</div>
    <div class="indigo-progress" id="indigoProgress" hidden><span id="indigoProgressBar"></span></div>

    <section class="indigo-best-card" id="indigoBestCard" hidden>
      <div><div class="title">⭐ Melhor combinação encontrada</div><div class="route" id="indigoBestRoute">—</div></div>
      <div class="price" id="indigoBestPrice">—</div>
    </section>

    <section class="cards indigo-summary">
      <div class="card"><span>Progresso</span><b id="indigoTested">—</b></div>
      <div class="card"><span>Disponíveis</span><b id="indigoAvailable">—</b></div>
      <div class="card"><span>Esgotadas</span><b id="indigoSoldOut">—</b></div>
      <div class="card"><span>Não confirmadas</span><b id="indigoUnconfirmed">—</b></div>
      <div class="card"><span>Último checkpoint</span><b id="indigoUpdated" style="font-size:15px">—</b></div>
    </section>

    <section class="panel">
      <div class="indigo-filters" id="indigoFilters">
        <button class="indigo-filter active" data-filter="all">Todas</button>
        <button class="indigo-filter" data-filter="available">Disponíveis</button>
        <button class="indigo-filter" data-filter="sold_out">Esgotadas</button>
        <button class="indigo-filter" data-filter="unconfirmed">Não confirmadas</button>
      </div>
      <div class="indigo-results-head"><b id="indigoResultsTitle">Todas as combinações</b><span id="indigoResultsCount"></span></div>
      <div class="indigo-slots" id="indigoSlots"></div>
      <div class="indigo-empty" id="indigoEmpty">Ainda não há resultado para esta pesquisa.</div>
      <button class="indigo-more" id="indigoMore" hidden>Mostrar mais resultados</button>
    </section>
    <div class="note indigo-note"><b>Confiabilidade:</b> as consultas são sequenciais e cada resposta é repetida. Respostas divergentes ficam amarelas como “Não confirmado / instável”. A execução salva checkpoints em lotes; ao repetir a mesma pesquisa em até 1 hora, somente o que falta ou falhou é consultado novamente.</div>
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
  function halfHour(v){return /^(?:[01]\d|2[0-3]):(?:00|30)$/.test(String(v||''));}
  function dates(a,b){if(!a||!b||b<a)return[];const out=[];for(let d=new Date(a+'T12:00:00Z'),end=new Date(b+'T12:00:00Z');d<=end;d.setUTCDate(d.getUTCDate()+1))out.push(d.toISOString().slice(0,10));return out;}
  function timeValues(a,b){const out=[];if(!a||!b||mins(b)<mins(a))return out;for(let m=mins(a);m<=mins(b);m+=30)out.push(`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`);return out;}
  function readForm(withId=false){const value={entry_date_from:qs('#indigoEntryDateFrom').value,entry_date_to:qs('#indigoEntryDateTo').value,exit_date_from:qs('#indigoExitDateFrom').value,exit_date_to:qs('#indigoExitDateTo').value,entry_from_time:qs('#indigoEntryFrom').value,entry_to_time:qs('#indigoEntryTo').value,exit_from_time:qs('#indigoExitFrom').value,exit_to_time:qs('#indigoExitTo').value,step_minutes:30,product:qs('#indigoProduct').value};if(withId)value.request_id=requestId();return value;}
  function estimated(r){
    const entries=[],exits=[];
    for(const date of dates(r.entry_date_from,r.entry_date_to))for(const time of timeValues(r.entry_from_time,r.entry_to_time))entries.push(Date.parse(`${date}T${time}:00Z`));
    for(const date of dates(r.exit_date_from,r.exit_date_to))for(const time of timeValues(r.exit_from_time,r.exit_to_time))exits.push(Date.parse(`${date}T${time}:00Z`));
    exits.sort((a,b)=>a-b);let total=0;
    for(const entry of entries){let low=0,high=exits.length;while(low<high){const mid=Math.floor((low+high)/2);if(exits[mid]<=entry)low=mid+1;else high=mid;}total+=exits.length-low;}
    return total;
  }
  function updateHint(){const r=readForm(),n=estimated(r),ed=dates(r.entry_date_from,r.entry_date_to).length,xd=dates(r.exit_date_from,r.exit_date_to).length,h=qs('#indigoHint');h.className='indigo-hint'+(n>1000?' warn':'');h.innerHTML=n?`Serão testadas <strong>${n.toLocaleString('pt-BR')}</strong> combinações · ${ed} dia(s) de entrada × ${xd} dia(s) de saída.${n>1000?' Pesquisa grande: será processada em lotes e poderá demorar mais.':''}`:'Defina faixas válidas.';}
  function validate(r){
    if(!r.entry_date_from||!r.entry_date_to||!r.exit_date_from||!r.exit_date_to)return'Informe as quatro datas da faixa.';
    if(r.entry_date_to<r.entry_date_from)return'A data final de entrada precisa ser igual ou posterior à inicial.';
    if(r.exit_date_to<r.exit_date_from)return'A data final de saída precisa ser igual ou posterior à inicial.';
    if(r.exit_date_to<r.entry_date_from)return'A faixa de saída termina antes da faixa de entrada.';
    if(![r.entry_from_time,r.entry_to_time,r.exit_from_time,r.exit_to_time].every(halfHour))return'Na Indigo os horários precisam terminar em :00 ou :30.';
    if(r.entry_to_time<r.entry_from_time)return'O horário final de entrada precisa ser igual ou posterior ao inicial.';
    if(r.exit_to_time<r.exit_from_time)return'O horário final de saída precisa ser igual ou posterior ao inicial.';
    if(!estimated(r))return'Nenhuma combinação válida de entrada e saída.';
    return'';
  }
  function postSearch(r){const url=`${apiBase}?route=${encodeURIComponent('api/indigo/search')}&t=${Date.now()}`;return fetch(url,{method:'POST',mode:'no-cors',cache:'no-store',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(r)});}
  async function readResult(){try{const x=await fetch(RESULT_URL+'?t='+Date.now(),{cache:'no-store'});if(!x.ok)return null;return await x.json();}catch{return null;}}
  function bridgeJsonp(route,timeoutMs=12000){return new Promise((resolve,reject)=>{if(!apiBase){reject(new Error('Serviço de pesquisa não conectado.'));return;}const cb='indigoCb_'+Date.now().toString(36)+Math.random().toString(36).slice(2);const script=document.createElement('script');const timer=setTimeout(()=>finish(new Error('Serviço demorou para responder.')),timeoutMs);function finish(err,value){clearTimeout(timer);try{delete window[cb]}catch{}script.remove();err?reject(err):resolve(value);}window[cb]=value=>finish(null,value);script.onerror=()=>finish(new Error('Não foi possível consultar o serviço.'));script.src=`${apiBase}?route=${encodeURIComponent(route)}&callback=${encodeURIComponent(cb)}&t=${Date.now()}`;document.head.appendChild(script);});}
  function sameRequest(data,r){const q=data?.request||{};return data?.request_id===r.request_id&&String(q.entry_date_from||'')===r.entry_date_from&&String(q.entry_date_to||'')===r.entry_date_to&&String(q.exit_date_from||'')===r.exit_date_from&&String(q.exit_date_to||'')===r.exit_date_to&&String(q.entry_from_time||'')===r.entry_from_time&&String(q.entry_to_time||'')===r.entry_to_time&&String(q.exit_from_time||'')===r.exit_from_time&&String(q.exit_to_time||'')===r.exit_to_time&&Number(q.step_minutes)===30&&q.product===r.product;}
  function fmtDateTime(v){try{return new Date(v).toLocaleString('pt-BR')}catch{return'—'}}
  function shortDate(v){return String(v||'').slice(5).split('-').reverse().join('/');}
  function money(v){return Number.isFinite(Number(v))&&Number(v)>0?new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v)):'';}
  function isAvailable(x){return x?.status==='available'&&x?.available===true&&x?.confirmed===true&&x?.evidence?.product_found===true&&x?.evidence?.sold_out===false&&x?.evidence?.valid_price===true&&Number(x?.price)>0;}
  function chronological(a,b){return String(a.entry_date).localeCompare(String(b.entry_date))||String(a.entry_time).localeCompare(String(b.entry_time))||String(a.exit_date).localeCompare(String(b.exit_date))||String(a.exit_time).localeCompare(String(b.exit_time));}
  function ordered(rows){const available=rows.filter(isAvailable).sort((a,b)=>(Number(a.price)-Number(b.price))||(Number(a.center_distance_minutes??Infinity)-Number(b.center_distance_minutes??Infinity))||chronological(a,b));const rank={unstable:0,error:1,sold_out:2,not_offered:3};const rest=rows.filter(x=>!isAvailable(x)).sort((a,b)=>(rank[a.status]??9)-(rank[b.status]??9)||chronological(a,b));return[...available,...rest];}
  function pickBest(data){const server=data?.best_combination;if(server&&server.confirmed===true&&Number(server.price)>0)return server;return ordered([...(data?.results||[])]).find(isAvailable)||null;}
  function filteredRows(all){if(activeFilter==='available')return all.filter(isAvailable);if(activeFilter==='sold_out')return all.filter(x=>x.status==='sold_out');if(activeFilter==='unconfirmed')return all.filter(x=>['unstable','error','not_offered'].includes(x.status)||(!x.confirmed&&!isAvailable(x)));return all;}
  function labelFor(x){if(isAvailable(x))return{css:'available',label:'DISPONÍVEL',note:'Confirmada novamente pela Indigo'};if(x.status==='sold_out')return{css:'sold_out',label:'ESGOTADO',note:x.confirmed?'Esgotamento confirmado novamente':'Esgotado'};if(x.status==='unstable')return{css:'unconfirmed',label:'⚠️ NÃO CONFIRMADO / INSTÁVEL',note:'As respostas repetidas divergiram'};if(x.status==='not_offered')return{css:'unconfirmed',label:'NÃO OFERTADO',note:'O produto correto não apareceu'};return{css:'unconfirmed',label:'⚠️ NÃO CONFIRMADO / ERRO',note:'A Indigo não confirmou esta combinação'};}
  function updateFilterCounts(all){const values={all:all.length,available:all.filter(isAvailable).length,sold_out:all.filter(x=>x.status==='sold_out').length,unconfirmed:all.filter(x=>['unstable','error','not_offered'].includes(x.status)||(!x.confirmed&&!isAvailable(x))).length};qs('#indigoFilters').querySelectorAll('button').forEach(b=>{const names={all:'Todas',available:'Disponíveis',sold_out:'Esgotadas',unconfirmed:'Não confirmadas'};b.textContent=`${names[b.dataset.filter]} (${values[b.dataset.filter]})`;b.classList.toggle('active',b.dataset.filter===activeFilter);});}
  function render(data,{partial=false}={}){
    lastData=data;
    const all=ordered([...(data.results||[])]),rows=filteredRows(all),best=pickBest(data),stats=data.stats||{};
    const done=Number(data.progress?.completed??stats.processed_combinations??all.length),total=Number(data.progress?.total??stats.total_combinations??all.length),percent=total?Math.min(100,Number(data.progress?.percent??done*100/total)):0;
    qs('#indigoTested').textContent=`${done.toLocaleString('pt-BR')} / ${total.toLocaleString('pt-BR')}`;
    qs('#indigoAvailable').textContent=String(all.filter(isAvailable).length);
    qs('#indigoSoldOut').textContent=String(all.filter(x=>x.status==='sold_out').length);
    qs('#indigoUnconfirmed').textContent=String(all.filter(x=>['unstable','error','not_offered'].includes(x.status)||(!x.confirmed&&!isAvailable(x))).length);
    qs('#indigoUpdated').textContent=data.generated_at?fmtDateTime(data.generated_at):'—';
    qs('#indigoProgress').hidden=false;qs('#indigoProgressBar').style.width=percent+'%';
    const bestCard=qs('#indigoBestCard');bestCard.hidden=!best;
    if(best){qs('#indigoBestRoute').textContent=`${shortDate(best.entry_date)} ${best.entry_time} → ${shortDate(best.exit_date)} ${best.exit_time}`;qs('#indigoBestPrice').textContent=money(best.price)||'Preço confirmado';}
    updateFilterCounts(all);
    const titles={all:'Todas as combinações · disponíveis primeiro',available:'Disponíveis confirmadas',sold_out:'Combinações esgotadas',unconfirmed:'Não confirmadas / instáveis'};
    qs('#indigoResultsTitle').textContent=titles[activeFilter];qs('#indigoResultsCount').textContent=`${rows.length.toLocaleString('pt-BR')} resultado(s)`;
    const box=qs('#indigoSlots');box.innerHTML='';const shown=rows.slice(0,visibleLimit);qs('#indigoEmpty').hidden=shown.length>0;
    if(!shown.length)qs('#indigoEmpty').textContent=partial?'Nenhum resultado deste filtro até agora.':'Nenhuma combinação neste filtro.';
    for(const x of shown){
      const state=labelFor(x),div=document.createElement('div');const isBest=best&&isAvailable(x)&&x.entry_date===best.entry_date&&x.entry_time===best.entry_time&&x.exit_date===best.exit_date&&x.exit_time===best.exit_time;
      div.className='indigo-slot '+state.css;
      div.innerHTML=`<div>${isBest?'<div class="indigo-best">★ MELHOR COMBINAÇÃO</div>':''}<div class="indigo-route-time"><div><span class="indigo-time-label">Entrada · ${shortDate(x.entry_date)}</span><strong>${String(x.entry_time||'—')}</strong></div><span class="indigo-arrow">→</span><div><span class="indigo-time-label">Saída · ${shortDate(x.exit_date)}</span><strong>${String(x.exit_time||'—')}</strong></div></div></div><div><div class="indigo-state">${state.label}</div>${isAvailable(x)&&money(x.price)?`<div class="indigo-price">${money(x.price)}</div>`:''}<small>${state.note}</small></div>`;
      box.appendChild(div);
    }
    const more=qs('#indigoMore');more.hidden=rows.length<=visibleLimit;if(!more.hidden)more.textContent=`Mostrar mais (${(rows.length-visibleLimit).toLocaleString('pt-BR')} restantes)`;
    const status=qs('#indigoStatus');
    if(partial){status.className='indigo-status wait';status.textContent=`🔎 ${done.toLocaleString('pt-BR')} / ${total.toLocaleString('pt-BR')} combinações processadas (${percent.toLocaleString('pt-BR')}%). ${all.filter(isAvailable).length} disponível(is) confirmada(s) até agora.${Number(data.resume?.reused_combinations)>0?' '+data.resume.reused_combinations+' reaproveitada(s) do checkpoint.':''}`;}
    else if(all.some(isAvailable)){status.className='indigo-status ok';status.textContent=`✅ Pesquisa concluída: ${all.filter(isAvailable).length} combinação(ões) realmente disponível(is). Melhor: ${shortDate(best.entry_date)} ${best.entry_time} → ${shortDate(best.exit_date)} ${best.exit_time}${money(best.price)?' · '+money(best.price):''}.`;}
    else{status.className='indigo-status bad';status.textContent='Pesquisa concluída sem combinação disponível confirmada. Resultados instáveis não foram marcados em verde.';}
  }
  async function poll(r){
    const status=qs('#indigoStatus'),started=Date.now(),timeoutMs=6*60*60*1000;
    while(Date.now()-started<timeoutMs){
      await new Promise(ok=>setTimeout(ok,3000));let bridge=null;try{bridge=await bridgeJsonp('api/indigo/search/'+r.request_id,12000);}catch{}
      if(bridge?.result&&sameRequest(bridge.result,r))render(bridge.result,{partial:bridge.status!=='done'});
      if(bridge?.status==='error')throw new Error(bridge.error||'A pesquisa terminou com erro.');
      if(bridge?.status==='done'&&bridge.result){render(bridge.result);return bridge.result;}
      const data=await readResult();
      if(data?.status==='error'&&data.request_id===r.request_id)throw new Error(data.error||'A pesquisa terminou com erro.');
      if(data?.status==='completed'&&sameRequest(data,r)){render(data);return data;}
      if(!bridge?.result){const sec=Math.round((Date.now()-started)/1000),phase=bridge?.status==='queued'?'na fila':bridge?.status==='in_progress'?'iniciando lotes':bridge?.status==='running'?'iniciando busca':'aguardando execução';status.className='indigo-status wait';status.textContent=`🔎 ${phase}… ${sec}s`;}
    }
    throw new Error('A pesquisa excedeu seis horas. Repita a mesma busca para reaproveitar o checkpoint da última hora.');
  }
  async function search(){
    if(searching)return;const r=readForm(true),err=validate(r),status=qs('#indigoStatus'),btn=qs('#indigoSearchButton'),count=estimated(r);
    if(err){status.className='indigo-status bad';status.textContent=err;return;}
    if(!apiBase)await loadConfig();if(!apiBase){status.className='indigo-status bad';status.textContent='Serviço de pesquisa não conectado. Atualize a página e tente novamente.';return;}
    searching=true;lastData=null;visibleLimit=PAGE_SIZE;btn.disabled=true;btn.textContent='⏳ Pesquisando…';status.className='indigo-status wait';status.textContent=`Enviando ${count.toLocaleString('pt-BR')} combinações para processamento sequencial em lotes${count>1000?' — esta pesquisa poderá demorar mais':''}…`;qs('#indigoProgress').hidden=false;qs('#indigoProgressBar').style.width='0%';
    try{await postSearch(r);await poll(r);}catch(e){status.className='indigo-status bad';status.textContent='Não foi possível concluir: '+String(e?.message||e);}finally{searching=false;btn.disabled=false;btn.textContent='🔎 Caçar disponibilidade';}
  }
  function activate(){if(typeof window.setMain==='function')window.setMain('indigo');else{qs('#productsApp')&&(qs('#productsApp').hidden=true);qs('#flightsApp')&&(qs('#flightsApp').hidden=true);document.querySelectorAll('.main-tab').forEach(x=>x.classList.toggle('active',x===tab));}app.hidden=false;}
  tab.addEventListener('click',activate);document.querySelectorAll('.main-tab').forEach(b=>{if(b!==tab)b.addEventListener('click',()=>{app.hidden=true;});});
  qs('#indigoSearchButton').addEventListener('click',search);
  qs('#indigoFilters').addEventListener('click',event=>{const button=event.target.closest('[data-filter]');if(!button)return;activeFilter=button.dataset.filter;visibleLimit=PAGE_SIZE;if(lastData)render(lastData,{partial:lastData.status!=='completed'});});
  qs('#indigoMore').addEventListener('click',()=>{visibleLimit+=PAGE_SIZE;if(lastData)render(lastData,{partial:lastData.status!=='completed'});});
  ['indigoEntryDateFrom','indigoEntryDateTo','indigoExitDateFrom','indigoExitDateTo','indigoEntryFrom','indigoEntryTo','indigoExitFrom','indigoExitTo','indigoProduct'].forEach(id=>{qs('#'+id).addEventListener('change',updateHint);qs('#'+id).addEventListener('input',updateHint);});
  loadConfig();updateHint();
})();
