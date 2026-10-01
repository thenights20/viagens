(()=>{
  const $=s=>document.querySelector(s);
  if($('#rentcarsApp')) return;

  const API_CONFIG='./data/flight-search-config.json';
  const RENTCARS_URL='https://www.rentcars.com/pt-br/';
  let apiBase='';
  let activeJob='';
  let pollTimer=null;
  let lastResult=null;

  const style=document.createElement('style');
  style.textContent=`
    .rc-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap;margin:5px 0 16px}
    .rc-head h2{margin:0 0 5px;font-size:24px}.rc-head .sub{max-width:900px}
    .rc-form{padding:15px;display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:11px;margin-bottom:15px}
    .rc-field label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 5px}
    .rc-actions{display:flex;gap:9px;align-items:center;grid-column:1/-1;flex-wrap:wrap}
    .rc-search{border:0;cursor:pointer;background:var(--accent);color:#07111f;font-weight:900;padding:11px 16px;border-radius:10px;min-width:220px}
    .rc-search:disabled{opacity:.55;cursor:wait}.rc-link{display:inline-flex;align-items:center;text-decoration:none;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-weight:800;padding:10px 13px;border-radius:10px}
    .rc-status{padding:12px 14px;border:1px solid var(--line);border-radius:12px;background:var(--panel2);margin:0 0 14px;color:var(--muted);line-height:1.45}
    .rc-status.ok{color:var(--ok);border-color:color-mix(in srgb,var(--ok) 50%,var(--line))}.rc-status.bad{color:var(--hot);border-color:color-mix(in srgb,var(--hot) 50%,var(--line))}.rc-status.wait{color:var(--warn)}
    .rc-best{padding:16px 18px;margin:0 0 15px;border:1px solid var(--ok);border-radius:14px;background:color-mix(in srgb,var(--ok) 8%,var(--panel));display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
    .rc-best .title{font-size:11px;font-weight:900;color:var(--ok);text-transform:uppercase;letter-spacing:.06em}.rc-best .route{font-size:20px;font-weight:950;margin-top:4px}.rc-best .price{font-size:25px;font-weight:950;color:var(--ok)}
    .rc-summary{grid-template-columns:repeat(4,1fr)}.rc-money{font-size:18px;font-weight:900;white-space:nowrap}.rc-cheapest td{background:color-mix(in srgb,var(--ok) 6%,transparent)}
    .rc-source{color:var(--accent);font-weight:850}.rc-note{margin-top:13px}.rc-inline{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.rc-inline input[type=checkbox]{width:auto}
    @media(max-width:1100px){.rc-form{grid-template-columns:repeat(2,1fr)}.rc-summary{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:700px){.rc-form{grid-template-columns:1fr}.rc-form .wide{grid-column:auto}.rc-actions>*{width:100%;justify-content:center}.rc-summary{grid-template-columns:repeat(2,1fr)}}
  `;
  document.head.appendChild(style);

  function money(v,c='BRL'){
    const n=Number(v); if(!Number.isFinite(n)) return '—';
    try{return new Intl.NumberFormat('pt-BR',{style:'currency',currency:c||'BRL'}).format(n)}catch{return `${c||''} ${n.toFixed(2)}`}
  }
  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function localDate(days=0){const d=new Date();d.setDate(d.getDate()+days);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
  function mins(v){const p=String(v||'').split(':').map(Number);return p[0]*60+p[1];}
  function validHalfHour(v){return /^(?:[01]\d|2[0-3]):(?:00|30)$/.test(String(v||''));}
  function slots(a,b){if(!validHalfHour(a)||!validHalfHour(b)||mins(b)<mins(a))return[];const out=[];for(let m=mins(a);m<=mins(b);m+=30)out.push(`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`);return out;}

  const tab=document.createElement('button');
  tab.className='main-tab'; tab.dataset.main='rentcars'; tab.textContent='🚗 Aluguel de carros';
  $('.main-tabs')?.appendChild(tab);

  const app=document.createElement('main');
  app.id='rentcarsApp'; app.hidden=true;
  app.innerHTML=`
    <div class="rc-head">
      <div><h2>🚗 Rentcars · Caçador do horário mais barato</h2><div class="sub">Compara o <b>preço total</b> da mesma locação em vários horários de retirada e/ou devolução, sempre usando somente a Rentcars como fonte.</div></div>
      <a class="rc-link" href="${RENTCARS_URL}" target="_blank" rel="noopener">Abrir Rentcars ↗</a>
    </div>
    <section class="panel rc-form">
      <div class="rc-field wide"><label>Local de retirada</label><input id="rcPickup" value="Port Canaveral, Cape Canaveral, FL" placeholder="Cidade, aeroporto ou endereço"></div>
      <div class="rc-field wide"><label>Local de devolução</label><input id="rcDropoff" value="Orlando International Airport (MCO)" placeholder="Cidade, aeroporto ou endereço"></div>
      <div class="rc-field"><label>Data da retirada</label><input id="rcPickupDate" type="date"></div>
      <div class="rc-field"><label>Data da devolução</label><input id="rcDropoffDate" type="date"></div>
      <div class="rc-field"><label>Moeda</label><select id="rcCurrency"><option value="BRL">BRL · Real</option><option value="USD">USD · Dólar</option></select></div>
      <div class="rc-field"><label>Idade do motorista</label><input id="rcAge" type="number" min="18" max="80" value="30"></div>
      <div class="rc-field"><label>Modo</label><select id="rcMode"><option value="pickup">Otimizar só retirada</option><option value="both">Otimizar retirada + devolução</option></select></div>
      <div class="rc-field"><label>Intervalo</label><select id="rcStep"><option value="30">30 minutos</option></select></div>
      <div class="rc-field"><label>Retirada · de</label><input id="rcPickupFrom" type="time" step="1800" value="08:00"></div>
      <div class="rc-field"><label>Retirada · até</label><input id="rcPickupTo" type="time" step="1800" value="12:00"></div>
      <div class="rc-field"><label>Devolução · de</label><input id="rcDropoffFrom" type="time" step="1800" value="10:00"></div>
      <div class="rc-field"><label>Devolução · até</label><input id="rcDropoffTo" type="time" step="1800" value="10:00"></div>
      <div class="rc-actions"><button class="rc-search" id="rcSearch">🔎 Encontrar horário mais barato</button><span id="rcEstimate" class="sub">—</span></div>
    </section>
    <div class="rc-status" id="rcStatus">Preencha os locais, datas e a faixa de horários.</div>
    <section class="rc-best" id="rcBest" hidden><div><div class="title">⭐ Melhor combinação encontrada na Rentcars</div><div class="route" id="rcBestRoute">—</div><div class="sub" id="rcBestSupplier">—</div></div><div><div class="price" id="rcBestPrice">—</div><div class="sub" id="rcBestSave"></div></div></section>
    <section class="cards rc-summary">
      <div class="card"><span>Combinações</span><b id="rcCount">—</b></div>
      <div class="card"><span>Com preço</span><b id="rcPriced">—</b></div>
      <div class="card"><span>Menor total</span><b id="rcMin">—</b></div>
      <div class="card"><span>Maior total</span><b id="rcMax">—</b></div>
    </section>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>Retirada</th><th>Devolução</th><th>Preço total</th><th>Locadora</th><th>Carro / categoria</th><th>Status</th><th></th></tr></thead><tbody id="rcRows"></tbody></table></div><div class="empty" id="rcEmpty"><strong>Ainda não há comparação.</strong>Faça uma pesquisa para ordenar os horários do mais barato para o mais caro.</div></section>
    <div class="note rc-note"><b>Fonte:</b> somente Rentcars. O painel não mistura tarifas de Kayak, DiscoverCars, Rentalcars.com ou outras plataformas. Como a Rentcars usa proteção anti-automação, uma consulta pode ser marcada como “bloqueada” quando o site exigir verificação humana; nesse caso nenhum preço é inventado.</div>
  `;
  const flights=$('#flightsApp'); if(flights) flights.after(app); else $('.wrap')?.appendChild(app);

  $('#rcPickupDate').value=localDate(1); $('#rcDropoffDate').value=localDate(2);

  async function loadConfig(){try{const r=await fetch(API_CONFIG+'?t='+Date.now(),{cache:'no-store'});const d=await r.json();apiBase=String(d.api_base||'').trim();}catch{apiBase='';}}
  function readForm(){
    const mode=$('#rcMode').value;
    const value={pickup_location:$('#rcPickup').value.trim(),dropoff_location:$('#rcDropoff').value.trim(),pickup_date:$('#rcPickupDate').value,dropoff_date:$('#rcDropoffDate').value,pickup_from_time:$('#rcPickupFrom').value,pickup_to_time:$('#rcPickupTo').value,dropoff_from_time:$('#rcDropoffFrom').value,dropoff_to_time:mode==='pickup'?$('#rcDropoffFrom').value:$('#rcDropoffTo').value,mode,currency:$('#rcCurrency').value,driver_age:Number($('#rcAge').value||30),step_minutes:30};
    return value;
  }
  function estimate(){const r=readForm(),p=slots(r.pickup_from_time,r.pickup_to_time),d=slots(r.dropoff_from_time,r.dropoff_to_time);const n=p.length*d.length;$('#rcEstimate').textContent=n?`${n} combinação${n===1?'':'ões'} de horário`: 'Faixa de horário inválida';return n;}
  function validate(r){
    if(!r.pickup_location||!r.dropoff_location)return 'Informe retirada e devolução.';
    if(!r.pickup_date||!r.dropoff_date||r.dropoff_date<r.pickup_date)return 'Confira as datas de retirada e devolução.';
    if(![r.pickup_from_time,r.pickup_to_time,r.dropoff_from_time,r.dropoff_to_time].every(validHalfHour))return 'Use horários terminados em :00 ou :30.';
    if(mins(r.pickup_to_time)<mins(r.pickup_from_time)||mins(r.dropoff_to_time)<mins(r.dropoff_from_time))return 'O horário final não pode ser anterior ao inicial.';
    const n=estimate(); if(!n)return 'Nenhuma combinação válida.'; if(n>49)return 'Limite de 49 combinações por pesquisa. Reduza a faixa de horários.';
    return '';
  }
  function apiUrl(route){return apiBase.replace(/\/$/,'')+'?route='+encodeURIComponent(route);}
  async function start(r){const res=await fetch(apiUrl('api/rentcars/search'),{method:'POST',headers:{'Content-Type':'text/plain;charset=utf-8'},body:JSON.stringify(r)});const txt=await res.text();let d;try{d=JSON.parse(txt)}catch{throw new Error('Resposta inválida do serviço de pesquisa.')}if(d.error)throw new Error(d.error);return d;}
  async function poll(job){const res=await fetch(apiUrl('api/rentcars/search/'+encodeURIComponent(job))+'&t='+Date.now(),{cache:'no-store'});const txt=await res.text();let d;try{d=JSON.parse(txt)}catch{throw new Error('Resposta de progresso inválida.')}return d;}

  function render(data){
    lastResult=data||{}; const results=[...(data?.results||[])];
    results.sort((a,b)=>(a.price_total==null)-(b.price_total==null)||(Number(a.price_total||1e99)-Number(b.price_total||1e99)));
    const priced=results.filter(x=>Number.isFinite(Number(x.price_total))&&Number(x.price_total)>0); const cur=data?.currency||$('#rcCurrency').value;
    $('#rcCount').textContent=results.length||data?.progress?.total||'—'; $('#rcPriced').textContent=priced.length;
    $('#rcMin').textContent=priced.length?money(priced[0].price_total,priced[0].currency||cur):'—'; $('#rcMax').textContent=priced.length?money(priced[priced.length-1].price_total,priced[priced.length-1].currency||cur):'—';
    const best=priced[0]; const bestBox=$('#rcBest'); bestBox.hidden=!best;
    if(best){$('#rcBestRoute').textContent=`${best.pickup_time} → ${best.dropoff_time}`;$('#rcBestSupplier').textContent=[best.supplier,best.vehicle].filter(Boolean).join(' · ')||'Menor preço total encontrado';$('#rcBestPrice').textContent=money(best.price_total,best.currency||cur);const max=Number(priced[priced.length-1]?.price_total||best.price_total);const save=max-Number(best.price_total);$('#rcBestSave').textContent=save>0?`Até ${money(save,best.currency||cur)} menos que o horário mais caro testado`:'';}
    const tb=$('#rcRows');tb.innerHTML='';$('#rcEmpty').hidden=results.length>0;
    results.forEach((x,i)=>{const tr=document.createElement('tr');if(best&&x===best)tr.className='rc-cheapest';const status=x.status==='ok'?'Preço encontrado':x.status==='blocked'?'Bloqueado pela Rentcars':x.status==='unavailable'?'Sem oferta':x.status==='error'?'Erro':'Não confirmado';const link=x.url||RENTCARS_URL;tr.innerHTML=`<td><b>${esc(x.pickup_time||'—')}</b><small class="statline">${esc(x.pickup_date||'')}</small></td><td><b>${esc(x.dropoff_time||'—')}</b><small class="statline">${esc(x.dropoff_date||'')}</small></td><td class="rc-money">${x.price_total!=null?money(x.price_total,x.currency||cur):'—'}</td><td><span class="rc-source">${esc(x.supplier||'Rentcars')}</span></td><td>${esc(x.vehicle||x.category||'—')}</td><td>${esc(status)}</td><td><a class="btn" href="${esc(link)}" target="_blank" rel="noopener">Abrir</a></td>`;tb.appendChild(tr);});
  }
  function setStatus(text,kind=''){const el=$('#rcStatus');el.className='rc-status'+(kind?' '+kind:'');el.textContent=text;}
  async function runSearch(){
    const req=readForm(),err=validate(req); if(err){setStatus(err,'bad');return;} if(!apiBase)await loadConfig();if(!apiBase){setStatus('Serviço de pesquisa não conectado. Atualize a página e tente novamente.','bad');return;}
    const btn=$('#rcSearch');btn.disabled=true;btn.textContent='⏳ Consultando Rentcars…';setStatus('Enviando as combinações para comparação. O resultado usa somente preços que a Rentcars realmente devolver.','wait');$('#rcRows').innerHTML='';$('#rcEmpty').hidden=false;$('#rcBest').hidden=true;
    try{const started=await start(req);activeJob=started.job_id;setStatus(`Pesquisa iniciada: ${started.combinations||estimate()} combinações.`, 'wait');
      const tick=async()=>{try{const d=await poll(activeJob);const result=d.result;if(result)render(result);if(d.status==='done'){setStatus(result?.stats?.priced?`Concluído: ${result.stats.priced} combinações com preço. Melhor horário destacado abaixo.`:'Pesquisa concluída, mas nenhuma tarifa foi confirmada.','ok');btn.disabled=false;btn.textContent='🔎 Encontrar horário mais barato';return;}if(d.status==='blocked'){setStatus(d.error||'A Rentcars exigiu verificação humana e bloqueou a consulta automatizada. Nenhum preço foi estimado.','bad');btn.disabled=false;btn.textContent='🔎 Tentar novamente';return;}if(d.status==='error'){setStatus(d.error||'A pesquisa terminou com erro.','bad');btn.disabled=false;btn.textContent='🔎 Tentar novamente';return;}setStatus(`Consultando Rentcars… ${result?.progress?.completed||0}/${result?.progress?.total||started.combinations||'—'} combinações.`, 'wait');pollTimer=setTimeout(tick,5000);}catch(e){setStatus('Falha ao acompanhar a pesquisa: '+String(e?.message||e),'bad');btn.disabled=false;btn.textContent='🔎 Tentar novamente';}};tick();
    }catch(e){setStatus('Não foi possível iniciar: '+String(e?.message||e),'bad');btn.disabled=false;btn.textContent='🔎 Tentar novamente';}
  }
  function activate(){if(typeof window.setMain==='function')window.setMain('rentcars');else{$('#productsApp')&&($('#productsApp').hidden=true);$('#flightsApp')&&($('#flightsApp').hidden=true);document.querySelectorAll('.main-tab').forEach(x=>x.classList.toggle('active',x===tab));}app.hidden=false;}
  tab.addEventListener('click',activate);document.querySelectorAll('.main-tab').forEach(b=>{if(b!==tab)b.addEventListener('click',()=>{app.hidden=true;});});
  $('#rcSearch').addEventListener('click',runSearch);['rcPickup','rcDropoff','rcPickupDate','rcDropoffDate','rcPickupFrom','rcPickupTo','rcDropoffFrom','rcDropoffTo','rcMode'].forEach(id=>{$('#'+id)?.addEventListener('input',estimate);$('#'+id)?.addEventListener('change',estimate);});
  $('#rcMode').addEventListener('change',()=>{const pickupOnly=$('#rcMode').value==='pickup';$('#rcDropoffTo').disabled=pickupOnly;if(pickupOnly)$('#rcDropoffTo').value=$('#rcDropoffFrom').value;estimate();});
  $('#rcDropoffFrom').addEventListener('input',()=>{if($('#rcMode').value==='pickup')$('#rcDropoffTo').value=$('#rcDropoffFrom').value;});
  $('#rcDropoffTo').disabled=true;estimate();loadConfig();
})();