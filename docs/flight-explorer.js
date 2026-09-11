(() => {
  const q = s => document.querySelector(s);
  const money = v => v == null ? '—' : new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v));
  const esc = (s='') => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));
  const safe = (u='') => { try { const x=new URL(u); return x.protocol==='https:'?x.href:'#'; } catch { return '#'; } };
  const fmtDate = v => { if(!v) return '—'; const [y,m,d]=v.split('-').map(Number); return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date(y,m-1,d)); };
  const ORIGINS = [
    ['DOU','Dourados'],['PMG','Ponta Porã'],['JTC','Bauru'],['GRU','Guarulhos'],['CGH','São Paulo / Congonhas'],['VCP','Campinas / Viracopos'],['GIG','Rio de Janeiro / Galeão'],['TJL','Três Lagoas'],['ARU','Araçatuba'],['PPB','Presidente Prudente / Pres. Venceslau'],['MII','Marília']
  ];
  const DESTINATIONS = [
    ['CGR','Campo Grande'],['CGB','Cuiabá'],['BSB','Brasília'],['GYN','Goiânia'],['CWB','Curitiba'],['LDB','Londrina'],['MGF','Maringá'],['IGU','Foz do Iguaçu'],['FLN','Florianópolis'],['NVT','Navegantes'],['POA','Porto Alegre'],['VCP','Campinas'],['CGH','São Paulo / Congonhas'],['GRU','São Paulo / Guarulhos'],['SJP','São José do Rio Preto'],['RAO','Ribeirão Preto'],['UDI','Uberlândia'],['CNF','Belo Horizonte'],['GIG','Rio de Janeiro / Galeão'],['SDU','Rio de Janeiro / Santos Dumont'],['VIX','Vitória'],['SSA','Salvador'],['REC','Recife'],['FOR','Fortaleza'],['NAT','Natal'],['MCZ','Maceió'],['AJU','Aracaju'],['JPA','João Pessoa'],['THE','Teresina'],['SLZ','São Luís'],['BEL','Belém'],['MAO','Manaus'],['PVH','Porto Velho'],['BVB','Boa Vista'],['MCP','Macapá'],['PMW','Palmas'],['JDO','Juazeiro do Norte'],['IOS','Ilhéus'],['BPS','Porto Seguro'],['PNZ','Petrolina'],['RBR','Rio Branco'],['STM','Santarém'],['IMP','Imperatriz'],['MOC','Montes Claros'],['JOI','Joinville'],['XAP','Chapecó'],['PFB','Passo Fundo'],['ROO','Rondonópolis'],['FEN','Fernando de Noronha'],['CAC','Cascavel'],
    ['EZE','Buenos Aires / Ezeiza'],['AEP','Buenos Aires / Aeroparque'],['SCL','Santiago'],['ASU','Assunção'],['MVD','Montevidéu'],['LIM','Lima'],['BOG','Bogotá'],['UIO','Quito'],['GYE','Guayaquil'],['VVI','Santa Cruz de la Sierra'],['PTY','Cidade do Panamá'],['SJO','San José'],['GUA','Cidade da Guatemala'],['MEX','Cidade do México'],['CUN','Cancún'],['PUJ','Punta Cana'],['SDQ','Santo Domingo'],['MIA','Miami'],['FLL','Fort Lauderdale'],['MCO','Orlando'],['JFK','Nova York / JFK'],['EWR','Nova York / Newark'],['BOS','Boston'],['IAD','Washington / Dulles'],['ATL','Atlanta'],['ORD','Chicago'],['DFW','Dallas / Fort Worth'],['IAH','Houston'],['LAX','Los Angeles'],['SFO','San Francisco'],['LAS','Las Vegas'],['YYZ','Toronto'],['YUL','Montreal'],['YVR','Vancouver'],['LIS','Lisboa'],['OPO','Porto'],['MAD','Madri'],['BCN','Barcelona'],['CDG','Paris'],['LHR','Londres / Heathrow'],['FCO','Roma'],['MXP','Milão'],['FRA','Frankfurt'],['AMS','Amsterdã'],['ZRH','Zurique'],['VIE','Viena'],['ATH','Atenas'],['IST','Istambul'],['DXB','Dubai'],['DOH','Doha']
  ];

  let data = {request:{},stats:{},results:[],daily_min:[]};
  const tabs = q('#flightTabs');
  const app = q('#flightsApp');
  if (!tabs || !app || q('#flightMonthPanel')) return;

  const style = document.createElement('style');
  style.textContent = `
    .month-search-grid{display:grid;grid-template-columns:1.15fr 1.35fr 1fr .75fr .75fr .85fr auto;gap:9px;align-items:end;padding:13px}
    .month-search-grid label{display:block;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;margin:0 0 5px}
    .month-search-btn{border:0;background:var(--accent);color:#07111f;font-weight:900;border-radius:10px;padding:11px 16px;cursor:pointer;min-height:41px;white-space:nowrap}
    .month-search-btn:hover{filter:brightness(1.07)}
    .month-search-status{padding:10px 13px;border-top:1px solid var(--line);color:var(--muted);font-size:12px;line-height:1.5}
    .month-search-status.wait{color:var(--warn)} .month-search-status.ok{color:var(--ok)}
    .month-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:7px;padding:12px}
    .month-day{min-height:66px;border:1px solid var(--line);background:var(--panel2);border-radius:10px;padding:8px}
    .month-day b{display:block;font-size:11px;color:var(--muted);margin-bottom:5px}.month-day strong{font-size:13px}.month-day.hot{border-color:var(--ok)}.month-day.hot strong{color:var(--ok)}
    .month-result-price{font-size:20px;font-weight:900;white-space:nowrap}.month-rank{font-size:18px;font-weight:900;color:var(--accent)}
    @media(max-width:1100px){.month-search-grid{grid-template-columns:repeat(3,1fr)}.month-search-grid .month-search-action{grid-column:1/-1}.month-search-btn{width:100%}}
    @media(max-width:700px){.month-search-grid{grid-template-columns:1fr 1fr}.month-calendar{grid-template-columns:repeat(4,1fr)}.month-search-grid .dest-field{grid-column:1/-1}}
  `;
  document.head.appendChild(style);

  const btn = document.createElement('button');
  btn.className = 'tab';
  btn.dataset.flightView = 'monthsearch';
  btn.textContent = '📅 Buscar passagem';
  tabs.insertBefore(btn, tabs.children[1] || null);

  const panel = document.createElement('div');
  panel.id = 'flightMonthPanel';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="flight-head">
      <div><h3 class="section-title">📅 Busca por mês</h3><div class="sub">Escolha origem, destino e o mês da ida. O motor testa todas as combinações de ida e volta dentro da faixa de duração escolhida e lista as 100 mais baratas.</div></div>
      <div class="flight-actions"><div class="pill"><span class="dot"></span><span id="monthSearchUpdated">Aguardando busca</span></div></div>
    </div>
    <section class="panel">
      <div class="month-search-grid">
        <div><label>Origem</label><select id="monthOrigin"></select></div>
        <div class="dest-field"><label>Destino</label><input id="monthDestination" list="monthDestinations" maxlength="3" placeholder="Ex.: MIA"><datalist id="monthDestinations"></datalist></div>
        <div><label>Mês da ida</label><input id="monthValue" type="month"></div>
        <div><label>Mín. dias</label><input id="monthMinStay" type="number" min="2" max="21" value="4"></div>
        <div><label>Máx. dias</label><input id="monthMaxStay" type="number" min="2" max="21" value="10"></div>
        <div><label>Escalas</label><select id="monthStops"><option value="0">Direto</option><option value="1">Até 1</option><option value="2" selected>Até 2</option></select></div>
        <div class="month-search-action"><button class="month-search-btn" id="monthSearchButton">🔎 Pesquisar mês</button></div>
      </div>
      <div class="month-search-status" id="monthSearchStatus">Escolha a rota e o mês. A busca pode levar alguns minutos porque percorre a matriz de datas.</div>
    </section>
    <section class="cards">
      <div class="card"><span>Menor preço</span><b id="monthLowest">—</b></div>
      <div class="card"><span>Combinações consultadas</span><b id="monthCombos">—</b></div>
      <div class="card"><span>Com preço</span><b id="monthPriced">—</b></div>
      <div class="card"><span>Resultados</span><b id="monthCount">—</b></div>
    </section>
    <section class="panel" id="monthCalendarPanel" hidden><h3 class="section-title" style="padding:0 12px">Menor preço por dia de ida</h3><div class="month-calendar" id="monthCalendar"></div></section>
    <section class="panel" style="margin-top:14px"><div class="table-wrap"><table><thead><tr><th>#</th><th>Ida</th><th>Volta</th><th>Dias</th><th>Companhia / escalas</th><th>Preço</th><th>Fonte</th><th></th></tr></thead><tbody id="monthRows"></tbody></table></div><div class="empty" id="monthEmpty"><strong>Nenhuma busca mensal carregada.</strong>Faça uma pesquisa para ver as 100 combinações mais baratas.</div></section>
    <div class="note"><b>Importante:</b> o mês selecionado é o mês da ida. A volta pode cair no mês seguinte. Os valores são dinâmicos e devem ser confirmados antes da emissão.</div>
  `;
  const firstPanel = q('#hunterPanel');
  app.insertBefore(panel, firstPanel || null);

  q('#monthOrigin').innerHTML = ORIGINS.map(([c,n])=>`<option value="${c}">${c} · ${esc(n)}</option>`).join('');
  q('#monthDestinations').innerHTML = DESTINATIONS.map(([c,n])=>`<option value="${c}">${esc(n)}</option>`).join('');

  const monthInput = q('#monthValue');
  const now = new Date();
  const pad = n => String(n).padStart(2,'0');
  const monthKey = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}`;
  const minMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  const maxMonth = new Date(now.getFullYear(), now.getMonth()+6, 1);
  monthInput.min = monthKey(minMonth); monthInput.max = monthKey(maxMonth);
  monthInput.value = monthKey(new Date(now.getFullYear(), now.getMonth()+1, 1));

  function formRequest(){
    return {
      origin:q('#monthOrigin').value.trim().toUpperCase(),
      destination:q('#monthDestination').value.trim().toUpperCase(),
      month:q('#monthValue').value,
      min_stay:Number(q('#monthMinStay').value||4),
      max_stay:Number(q('#monthMaxStay').value||10),
      max_stops:Number(q('#monthStops').value||2)
    };
  }
  function sameRequest(a,b){return a&&b&&a.origin===b.origin&&a.destination===b.destination&&a.month===b.month&&Number(a.min_stay)===Number(b.min_stay)&&Number(a.max_stay)===Number(b.max_stay)&&Number(a.max_stops)===Number(b.max_stops)}

  function render(){
    const rows = data.results || [];
    const stats = data.stats || {};
    const req = data.request || {};
    q('#monthRows').innerHTML = rows.map((x,i)=>`<tr>
      <td><span class="month-rank">${i+1}</span></td>
      <td><b>${fmtDate(x.departure_date)}</b></td>
      <td><b>${fmtDate(x.return_date)}</b></td>
      <td>${Number(x.trip_days||0)} dias</td>
      <td><b>${esc(x.airline||'Google Flights')}</b><small class="statline">${esc(x.stops||'')} ${x.duration?'· '+esc(x.duration):''}</small></td>
      <td class="month-result-price">${money(x.price)}</td>
      <td><span class="badge official">${esc(x.source_kind==='swoop'?'Swoop':'Google')}</span></td>
      <td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Ver voo</a></td></tr>`).join('');
    q('#monthEmpty').hidden = rows.length>0;
    q('#monthLowest').textContent = money(stats.lowest_price);
    q('#monthCombos').textContent = stats.combinations ?? '—';
    q('#monthPriced').textContent = stats.priced_combinations != null ? `${stats.priced_combinations} · ${stats.coverage_pct||0}%` : '—';
    q('#monthCount').textContent = rows.length ? `${rows.length}/100` : '—';
    if(data.generated_at){ q('#monthSearchUpdated').textContent = `Atualizado ${new Date(data.generated_at).toLocaleString('pt-BR')} · ${req.origin||''}→${req.destination||''}`; }

    const daily = data.daily_min || [];
    const cal = q('#monthCalendar');
    if(daily.length){
      const low = Math.min(...daily.map(x=>Number(x.price)||Infinity));
      cal.innerHTML = daily.map(x=>{const d=Number((x.departure_date||'').slice(-2));const hot=Number(x.price)<=low*1.06?' hot':'';return `<div class="month-day${hot}"><b>Dia ${d}</b><strong>${money(x.price)}</strong><small class="statline">${Number(x.trip_days||0)} dias</small></div>`}).join('');
      q('#monthCalendarPanel').hidden=false;
    } else { cal.innerHTML=''; q('#monthCalendarPanel').hidden=true; }

    const pending = JSON.parse(localStorage.getItem('flightMonthPending')||'null');
    const status=q('#monthSearchStatus');
    if(pending && sameRequest(pending, req) && rows.length){status.className='month-search-status ok';status.textContent='✅ Busca concluída. Estes são os resultados da pesquisa que você solicitou.';localStorage.removeItem('flightMonthPending');}
  }

  async function boot(){
    try{const r=await fetch('./data/flight-month-search.json?t='+Date.now(),{cache:'no-store'}); if(r.ok)data=await r.json();}
    catch{}
    if(!panel.hidden) render();
  }

  function activate(){
    document.querySelectorAll('#flightTabs .tab').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    ['hunterPanel','radarPanel','externalPanel','airlinesPanel'].forEach(id=>{const el=q('#'+id);if(el)el.hidden=true});
    panel.hidden=false; render();
  }

  q('#monthSearchButton').addEventListener('click',()=>{
    const r=formRequest();
    const status=q('#monthSearchStatus');
    if(!/^[A-Z]{3}$/.test(r.destination)){status.className='month-search-status wait';status.textContent='Informe um aeroporto de destino com código IATA de 3 letras, por exemplo MIA, MCO, LIS ou REC.';return;}
    if(!r.month){status.className='month-search-status wait';status.textContent='Escolha o mês da viagem.';return;}
    if(r.min_stay<2||r.max_stay>21||r.min_stay>r.max_stay){status.className='month-search-status wait';status.textContent='A duração precisa ficar entre 2 e 21 dias, com o mínimo menor que o máximo.';return;}
    localStorage.setItem('flightMonthPending',JSON.stringify(r));
    const title=`FLIGHT_SEARCH|ORIGIN=${r.origin}|DEST=${r.destination}|MONTH=${r.month}|MIN=${r.min_stay}|MAX=${r.max_stay}|STOPS=${r.max_stops}`;
    const body=`Solicitação automática do painel de passagens.\n\nRota: ${r.origin} → ${r.destination}\nMês da ida: ${r.month}\nDuração: ${r.min_stay}–${r.max_stay} dias\nMáximo de escalas: ${r.max_stops}\n\nNão altere o título; o robô usa esses dados para executar a busca.`;
    const url=`https://github.com/thenights20/viagens/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
    status.className='month-search-status wait';status.textContent='⏳ A solicitação está pronta. Na aba do GitHub, clique em “Submit new issue”. Depois volte aqui: o painel verificará o resultado automaticamente.';
    window.open(url,'_blank','noopener');
  });

  btn.addEventListener('click',activate);
  document.querySelectorAll('#flightTabs .tab').forEach(b=>{if(b!==btn)b.addEventListener('click',()=>{panel.hidden=true})});
  const productsMain=document.querySelector('.main-tab[data-main="products"]'); if(productsMain)productsMain.addEventListener('click',()=>{panel.hidden=true});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)boot()});
  boot(); setInterval(boot,15000);
})();
