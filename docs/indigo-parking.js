(() => {
  const qs = (s) => document.querySelector(s);
  if (qs('#indigoApp') || !qs('.main-tabs')) return;

  const BOOKING_URL = 'https://indigoneo.com.br/pt/booking/99980448';
  const RESULT_URL = './data/indigo-parking-search.json';
  let apiBase = '';
  let searching = false;

  const style = document.createElement('style');
  style.textContent = `
    .indigo-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;margin:5px 0 16px}
    .indigo-head h2{margin:0 0 5px;font-size:24px}.indigo-head .sub{max-width:760px}
    .indigo-form{padding:15px;display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:11px;margin-bottom:15px}
    .indigo-field label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 5px}
    .indigo-actions{display:flex;gap:9px;align-items:end;grid-column:1/-1;flex-wrap:wrap}
    .indigo-search{border:0;cursor:pointer;background:var(--accent);color:#07111f;font-weight:900;padding:11px 16px;border-radius:10px;min-width:190px}
    .indigo-search:disabled{opacity:.55;cursor:wait}.indigo-link{display:inline-flex;align-items:center;text-decoration:none;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-weight:800;padding:10px 13px;border-radius:10px}
    .indigo-status{padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel2);margin:0 0 15px;color:var(--muted)}
    .indigo-status.ok{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 50%,var(--line))}.indigo-status.bad{color:var(--hot);border-color:color-mix(in srgb,var(--hot) 50%,var(--line))}.indigo-status.wait{color:var(--warn)}
    .indigo-summary{grid-template-columns:repeat(4,1fr)}
    .indigo-slots{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:9px;padding:13px}
    .indigo-slot{border:1px solid var(--line);background:var(--panel2);border-radius:12px;padding:13px;min-height:86px;display:flex;flex-direction:column;justify-content:space-between;gap:8px}
    .indigo-slot strong{font-size:21px}.indigo-slot small{color:var(--muted);line-height:1.35}.indigo-slot.available{border-color:var(--ok);box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--ok) 35%,transparent)}
    .indigo-slot.available strong,.indigo-slot.available .indigo-state{color:var(--ok)}.indigo-slot.sold_out .indigo-state{color:var(--hot)}.indigo-slot.error .indigo-state{color:var(--warn)}
    .indigo-state{font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}.indigo-best{font-size:11px;color:var(--ok);font-weight:900}
    .indigo-note{margin-top:12px}.indigo-empty{padding:28px;text-align:center;color:var(--muted)}
    @media(max-width:1100px){.indigo-form{grid-template-columns:repeat(3,1fr)}.indigo-slots{grid-template-columns:repeat(4,1fr)}}
    @media(max-width:700px){.indigo-form{grid-template-columns:1fr 1fr}.indigo-slots{grid-template-columns:repeat(2,1fr)}.indigo-summary{grid-template-columns:repeat(2,1fr)}.indigo-actions>*{flex:1;justify-content:center}.indigo-form .wide{grid-column:1/-1}}
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
      <div><h2>🚗 Indigo · Aeroporto de Guarulhos</h2><div class="sub">Descubra quais horários de entrada liberam vaga. O sistema testa várias combinações diretamente na disponibilidade da Indigo e destaca onde vale tentar a reserva.</div></div>
      <a class="indigo-link" href="${BOOKING_URL}" target="_blank" rel="noopener">Abrir Indigo ↗</a>
    </div>

    <section class="panel indigo-form">
      <div class="indigo-field"><label>Dia de entrada</label><input id="indigoEntryDate" type="date"></div>
      <div class="indigo-field"><label>Dia de saída</label><input id="indigoExitDate" type="date"></div>
      <div class="indigo-field"><label>Hora de saída</label><input id="indigoExitTime" type="time" value="07:00"></div>
      <div class="indigo-field"><label>Estacionamento</label><select id="indigoProduct"><option value="terminal3_garage" selected>T3 Edifício Garagem · coberto</option><option value="terminal3_flex">T3 Flex</option><option value="terminal2_standard">Terminal 2 Standard</option><option value="terminal1">Terminal 1</option><option value="any">Qualquer opção disponível</option></select></div>
      <div class="indigo-field"><label>Testar a partir de</label><input id="indigoFromTime" type="time" value="05:00"></div>
      <div class="indigo-field"><label>Até</label><input id="indigoToTime" type="time" value="14:00"></div>
      <div class="indigo-field"><label>Intervalo</label><select id="indigoStep"><option value="15">15 minutos · detalhado</option><option value="30" selected>30 minutos</option><option value="60">60 minutos · rápido</option></select></div>
      <div class="indigo-field"><label>Exibição</label><select id="indigoShow"><option value="all" selected>Todos os horários</option><option value="available">Só disponíveis</option></select></div>
      <div class="indigo-actions"><button class="indigo-search" id="indigoSearchButton">🔎 Pesquisar horários</button><span class="sub" id="indigoHint">A pesquisa apenas consulta disponibilidade; não faz reserva.</span></div>
    </section>

    <div class="indigo-status" id="indigoStatus">Escolha o dia e a faixa de horários para pesquisar.</div>

    <section class="cards indigo-summary">
      <div class="card"><span>Horários testados</span><b id="indigoTested">—</b></div>
      <div class="card"><span>Disponíveis</span><b id="indigoAvailable">—</b></div>
      <div class="card"><span>Primeiro disponível</span><b id="indigoFirst">—</b></div>
      <div class="card"><span>Última consulta</span><b id="indigoUpdated" style="font-size:16px">—</b></div>
    </section>

    <section class="panel"><div class="indigo-slots" id="indigoSlots"></div><div class="indigo-empty" id="indigoEmpty">Ainda não há resultado para esta pesquisa.</div></section>
    <div class="note indigo-note"><b>Como usar:</b> se o horário que você pretendia entrar estiver esgotado, procure um bloco verde próximo. Ex.: 10:00 esgotado e 10:30 disponível. Aí você abre a Indigo e tenta reservar usando exatamente a combinação indicada. A disponibilidade pode mudar a qualquer momento.</div>
  `;
  const flightsApp = qs('#flightsApp');
  if (flightsApp) flightsApp.after(app); else document.querySelector('.wrap').appendChild(app);

  function localDate(days=0){
    const d=new Date(); d.setDate(d.getDate()+days);
    const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');
    return `${y}-${m}-${day}`;
  }
  qs('#indigoEntryDate').value=localDate(1);
  qs('#indigoExitDate').value=localDate(22);

  async function loadConfig(){
    try{const r=await fetch('./data/flight-search-config.json?t='+Date.now(),{cache:'no-store'});const d=await r.json();apiBase=String(d.api_base||'').trim();}catch{apiBase='';}
  }
  function requestId(){
    const suffix=globalThis.crypto&&crypto.randomUUID?crypto.randomUUID().replace(/-/g,''):Date.now().toString(36)+Math.random().toString(36).slice(2);
    return ('indigo_'+suffix).slice(0,64);
  }
  function formRequest(){return{
    entry_date:qs('#indigoEntryDate').value,
    exit_date:qs('#indigoExitDate').value,
    exit_time:qs('#indigoExitTime').value,
    from_time:qs('#indigoFromTime').value,
    to_time:qs('#indigoToTime').value,
    step_minutes:Number(qs('#indigoStep').value),
    product:qs('#indigoProduct').value,
    request_id:requestId()
  }}
  function validate(r){
    if(!r.entry_date||!r.exit_date)return'Informe as datas de entrada e saída.';
    if(r.exit_date<r.entry_date)return'A saída não pode ser antes da entrada.';
    if(!r.exit_time||!r.from_time||!r.to_time)return'Informe os horários.';
    if(r.to_time<r.from_time)return'O horário final precisa ser depois do inicial.';
    return'';
  }
  function postSearch(r){
    const url=`${apiBase}?route=${encodeURIComponent('api/indigo/search')}&t=${Date.now()}`;
    return fetch(url,{method:'POST',mode:'no-cors',cache:'no-store',headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(r)});
  }
  async function readResult(){
    try{const x=await fetch(RESULT_URL+'?t='+Date.now(),{cache:'no-store'});if(!x.ok)return null;return await x.json();}catch{return null;}
  }
  function sameRequest(data,r){
    const q=data?.request||{};
    return data?.request_id===r.request_id&&q.entry_date===r.entry_date&&q.exit_date===r.exit_date&&q.exit_time===r.exit_time&&q.from_time===r.from_time&&q.to_time===r.to_time&&Number(q.step_minutes)===Number(r.step_minutes)&&q.product===r.product;
  }
  function fmtDateTime(v){try{return new Date(v).toLocaleString('pt-BR')}catch{return'—'}}
  function render(data){
    const all=[...(data.results||[])];
    const show=qs('#indigoShow').value;
    const rows=show==='available'?all.filter(x=>x.available===true):all;
    const available=all.filter(x=>x.available===true);
    qs('#indigoTested').textContent=String(data.stats?.tested_times??all.length);
    qs('#indigoAvailable').textContent=String(data.stats?.available_times??available.length);
    qs('#indigoFirst').textContent=available[0]?.entry_time||'Nenhum';
    qs('#indigoUpdated').textContent=data.generated_at?fmtDateTime(data.generated_at):'—';
    const box=qs('#indigoSlots');box.innerHTML='';
    qs('#indigoEmpty').hidden=rows.length>0;
    if(!rows.length){qs('#indigoEmpty').textContent=show==='available'?'Nenhum horário disponível nesta varredura.':'Nenhum horário retornado.';return;}
    for(const x of rows){
      const div=document.createElement('div');
      const cls=x.available===true?'available':x.status==='error'?'error':'sold_out';
      const label=x.available===true?'DISPONÍVEL':x.status==='error'?'ERRO':x.status==='not_offered'?'NÃO OFERTADO':'ESGOTADO';
      div.className='indigo-slot '+cls;
      div.innerHTML=`<div><strong>${String(x.entry_time||'—')}</strong>${x.available===true?'<div class="indigo-best">✓ vale tentar</div>':''}</div><div><div class="indigo-state">${label}</div><small>${x.available===true?'Entrada encontrada para esta combinação':'Teste concluído para este horário'}</small></div>`;
      box.appendChild(div);
    }
    const status=qs('#indigoStatus');
    status.className='indigo-status '+(available.length?'ok':'bad');
    status.textContent=available.length?`✅ ${available.length} horário(s) liberado(s). Primeiro: ${available[0].entry_time}.`:'Nenhum horário disponível na faixa testada. Tente ampliar a faixa ou alterar o dia.';
  }
  async function poll(r){
    const status=qs('#indigoStatus');
    const started=Date.now();
    for(let i=0;i<120;i++){
      await new Promise(ok=>setTimeout(ok,3000));
      const data=await readResult();
      if(data?.status==='error'&&data.request_id===r.request_id)throw new Error(data.error||'A pesquisa terminou com erro.');
      if(data?.status==='completed'&&sameRequest(data,r)){render(data);return data;}
      const sec=Math.round((Date.now()-started)/1000);
      status.textContent=`🔎 Consultando horários na Indigo… ${sec}s`;
    }
    throw new Error('A pesquisa demorou mais que o esperado. Tente novamente.');
  }
  async function search(){
    if(searching)return;
    const r=formRequest(),err=validate(r),status=qs('#indigoStatus'),btn=qs('#indigoSearchButton');
    if(err){status.className='indigo-status bad';status.textContent=err;return;}
    if(!apiBase)await loadConfig();
    if(!apiBase){status.className='indigo-status bad';status.textContent='Serviço de pesquisa não conectado. Atualize a página e tente novamente.';return;}
    searching=true;btn.disabled=true;btn.textContent='⏳ Pesquisando…';status.className='indigo-status wait';status.textContent='Enviando a varredura de horários…';
    try{await postSearch(r);await poll(r);}catch(e){status.className='indigo-status bad';status.textContent='Não foi possível concluir: '+String(e?.message||e);}finally{searching=false;btn.disabled=false;btn.textContent='🔎 Pesquisar horários';}
  }
  function activate(){
    if(typeof window.setMain==='function') window.setMain('indigo');
    else{qs('#productsApp')&&(qs('#productsApp').hidden=true);qs('#flightsApp')&&(qs('#flightsApp').hidden=true);document.querySelectorAll('.main-tab').forEach(x=>x.classList.toggle('active',x===tab));}
    app.hidden=false;
  }
  tab.addEventListener('click',activate);
  document.querySelectorAll('.main-tab').forEach(b=>{if(b!==tab)b.addEventListener('click',()=>{app.hidden=true;});});
  qs('#indigoSearchButton').addEventListener('click',search);
  qs('#indigoShow').addEventListener('change',async()=>{const d=await readResult();if(d?.status==='completed')render(d);});
  qs('#indigoEntryDate').addEventListener('change',()=>{if(qs('#indigoExitDate').value<qs('#indigoEntryDate').value)qs('#indigoExitDate').value=qs('#indigoEntryDate').value;});

  loadConfig();
})();