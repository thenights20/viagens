from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs" / "index.html"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marcador não encontrado ao atualizar painel: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    html = PATH.read_text(encoding="utf-8")
    if 'data-flight-view="hunter"' in html:
        print("Painel Deal Hunter já aplicado.")
        return

    html = replace_once(
        html,
        '.section-title{margin:18px 0 7px;font-size:18px}.official-note{color:var(--accent);font-size:11px;font-weight:700}',
        '.section-title{margin:18px 0 7px;font-size:18px}.official-note{color:var(--accent);font-size:11px;font-weight:700}.hunter-filters{grid-template-columns:1fr 1fr 1fr 1fr 1fr 1fr}.external-filters{grid-template-columns:1fr 1fr 2fr}.why{max-width:310px;color:var(--muted);font-size:11px;line-height:1.5}.why b{color:var(--text)}.fresh{color:var(--warn);font-size:10px;font-weight:900}.hunter-price{font-size:20px;font-weight:900;white-space:nowrap}.external-title{max-width:620px}.external-title b{display:block}.external-title small{color:var(--muted)}',
        "css",
    )
    html = html.replace(
        '@media(max-width:1100px){.filters,.flight-filters,.airline-filters{grid-template-columns:repeat(3,1fr)}',
        '@media(max-width:1100px){.filters,.flight-filters,.airline-filters,.hunter-filters,.external-filters{grid-template-columns:repeat(3,1fr)}',
        1,
    )
    html = html.replace(
        '@media(max-width:700px){.cards{grid-template-columns:repeat(2,1fr)}.filters,.flight-filters,.airline-filters{grid-template-columns:1fr 1fr}',
        '@media(max-width:700px){.cards{grid-template-columns:repeat(2,1fr)}.filters,.flight-filters,.airline-filters,.hunter-filters,.external-filters{grid-template-columns:1fr 1fr}',
        1,
    )

    old_head = '''  <div class="flight-head"><div><h2>Radar de passagens</h2><div class="sub">Procura tarifas anormalmente baixas sem exigir destino ou data fixa. O Deal Score usa histórico da rota; as páginas oficiais de GOL, Azul e LATAM entram como descoberta e sinal adicional.</div></div><div class="flight-actions"><div class="pill"><span class="dot"></span><span id="flightUpdated">Aguardando varredura</span></div><a class="manual-btn" href="https://github.com/thenights20/viagens/actions/workflows/flight-monitor.yml" target="_blank" rel="noopener">↻ Buscar passagens agora</a></div></div>
  <section class="cards"><div class="card"><span>Deals com Score 70+</span><b id="flightDealCount">—</b></div><div class="card"><span>Origens monitoradas</span><b id="flightOriginCount">11</b></div><div class="card"><span>Destinos conhecidos</span><b id="flightDestinationCount">—</b></div><div class="card"><span>Rotas com histórico</span><b id="flightRouteCount">—</b></div></section>

  <nav class="tabs" id="flightTabs"><button class="tab active" data-flight-view="radar">Radar estatístico</button><button class="tab" data-flight-view="airlines">Ofertas diretas · GOL / Azul / LATAM</button></nav>

  <div id="radarPanel">'''
    new_head = '''  <div class="flight-head"><div><h2>Passagens · Deal Hunter</h2><div class="sub">Duas buscas trabalham juntas: o Deal Hunter procura preços realmente excepcionais e o Radar contínuo mantém histórico para detectar quedas novas.</div></div><div class="flight-actions"><div class="pill"><span class="dot"></span><span id="hunterUpdated">Aguardando caça</span></div><a class="manual-btn" href="https://github.com/thenights20/viagens/actions/workflows/deal-hunter.yml" target="_blank" rel="noopener">🔥 Rodar Deal Hunter</a><a class="manual-btn secondary" href="https://github.com/thenights20/viagens/actions/workflows/flight-monitor.yml" target="_blank" rel="noopener">↻ Radar profundo</a></div></div>

  <nav class="tabs" id="flightTabs"><button class="tab active" data-flight-view="hunter">🔥 Deal Hunter</button><button class="tab" data-flight-view="radar">Radar contínuo</button><button class="tab" data-flight-view="external">Fontes externas</button><button class="tab" data-flight-view="airlines">Companhias</button></nav>

  <div id="hunterPanel">
    <section class="cards"><div class="card"><span>Achados ativos</span><b id="hunterActiveCount">—</b></div><div class="card"><span>Muito baratos · 70+</span><b id="hunterCheapCount">—</b></div><div class="card"><span>Excepcionais · 80+</span><b id="hunterExceptionalCount">—</b></div><div class="card"><span>Sinais externos rechecados</span><b id="hunterVerifiedCount">—</b></div></section>
    <section class="panel filters hunter-filters">
      <select id="hunterOrigin"><option value="">Todas as origens</option></select>
      <select id="hunterTripType"><option value="">Doméstico + Internacional</option><option value="domestic">Somente doméstico</option><option value="international">Somente internacional</option></select>
      <select id="hunterRegion"><option value="">Todas as regiões</option><option value="domestic">Brasil</option><option value="south_america">América do Sul</option><option value="caribbean_mexico">Caribe / México</option><option value="usa_canada">EUA / Canadá</option><option value="europe">Europa</option><option value="long_haul">Ásia / África / Oceania</option></select>
      <select id="hunterMinScore"><option value="60">60+ Boa oportunidade</option><option value="70" selected>70+ Muito barata</option><option value="80">80+ Excepcional</option><option value="90">90+ Fora da curva</option></select>
      <input id="hunterMaxPrice" type="number" min="0" step="100" placeholder="Preço máx. R$">
      <select id="hunterStops"><option value="">Qualquer escala</option><option value="0">Somente direto</option><option value="1">Até 1 escala</option><option value="2">Até 2 escalas</option></select>
    </section>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>Rota</th><th>Datas</th><th>Companhia</th><th>Preço</th><th>Por que entrou</th><th>Hunter Score</th><th></th></tr></thead><tbody id="hunterRows"></tbody></table></div><div class="empty" id="hunterEmpty" hidden><strong>Nenhuma tarifa passou pela régua agora.</strong>Isso é intencional: preço apenas “abaixo da média” não entra aqui.</div></section>
    <div class="note"><b>Deal Hunter:</b> combina desconto relativo com preço absoluto por região. Exemplo: uma tarifa nacional de R$ 1.173 pode estar 60% abaixo da média e ainda assim ficar fora desta aba. A busca rápida roda a cada ~15 minutos nos hubs GRU/VCP/GIG/CGH e alterna uma origem regional a cada rodada.</div>
  </div>

  <div id="radarPanel" hidden>
    <div class="flight-head"><div><h3 class="section-title">Radar contínuo e histórico</h3><div class="sub">Mantém a busca estatística ampla, inclusive preços que ainda não são excepcionais, para aprender o comportamento das rotas e detectar novas quedas.</div></div><div class="pill"><span class="dot"></span><span id="flightUpdated">Aguardando varredura</span></div></div>
    <section class="cards"><div class="card"><span>Deals com Score 70+</span><b id="flightDealCount">—</b></div><div class="card"><span>Origens monitoradas</span><b id="flightOriginCount">11</b></div><div class="card"><span>Destinos conhecidos</span><b id="flightDestinationCount">—</b></div><div class="card"><span>Rotas com histórico</span><b id="flightRouteCount">—</b></div></section>'''
    html = replace_once(html, old_head, new_head, "cabeçalho das passagens")

    external_panel = '''
  <div id="externalPanel" hidden>
    <div class="flight-head"><div><h3 class="section-title">Fontes externas · sensores de oportunidade</h3><div class="sub">Acompanha sinais públicos do Secret Flying, Melhores Destinos e Passagens Imperdíveis. Eles servem como sensores; quando há rota e datas utilizáveis, o Deal Hunter tenta reconsultar a tarifa.</div></div><div class="pill"><span class="dot"></span><span id="externalUpdated">Aguardando coleta</span></div></div>
    <section class="cards"><div class="card"><span>Sinais encontrados</span><b id="externalSignalCount">—</b></div><div class="card"><span>Fontes respondendo</span><b id="externalSourceCount">—</b></div><div class="card"><span>Secret Flying</span><b id="externalSecretCount">—</b></div><div class="card"><span>Brasil</span><b id="externalBrazilCount">—</b></div></section>
    <section class="panel filters external-filters"><select id="externalSource"><option value="">Todas as fontes</option><option value="Secret Flying">Secret Flying</option><option value="Melhores Destinos">Melhores Destinos</option><option value="Passagens Imperdíveis">Passagens Imperdíveis</option></select><select id="externalMode"><option value="">Ida / ida e volta</option><option value="round_trip">Ida e volta</option><option value="one_way">Somente ida</option></select><input id="externalQuery" placeholder="Destino, origem ou palavra-chave…"></section>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>Oferta publicada</th><th>Fonte</th><th>Preço divulgado</th><th>Tipo</th><th>Rota reconhecida</th><th></th></tr></thead><tbody id="externalRows"></tbody></table></div><div class="empty" id="externalEmpty" hidden><strong>Nenhum sinal neste filtro.</strong>Uma fonte pode estar temporariamente bloqueando leitura automatizada.</div></section>
    <div class="source-row" id="externalSources"></div>
    <div class="note"><b>Importante:</b> esta aba não assume que uma publicação antiga continua disponível. O objetivo é descobrir padrões e rotas rapidamente; os achados confirmados aparecem no Deal Hunter com preço reconsultado.</div>
  </div>

'''
    html = replace_once(html, '  <div id="airlinesPanel" hidden>', external_panel + '  <div id="airlinesPanel" hidden>', "aba fontes externas")

    html = replace_once(
        html,
        "let data={products:[],watchlist:[],active:[]},flightData={deals:[],origins:[]},airlineData={offers:[],sources:{}},view='all',mainView='products',flightView='radar';",
        "let data={products:[],watchlist:[],active:[]},flightData={deals:[],origins:[]},airlineData={offers:[],sources:{}},hunterData={deals:[]},externalData={signals:[],sources:{}},view='all',mainView='products',flightView='hunter';",
        "estado javascript",
    )

    marker = 'function offerOrigins(x){return Array.isArray(x.origin_candidates)&&x.origin_candidates.length?x.origin_candidates:[x.origin]}'
    extra_js = r'''function hunterRegionLabel(x){return({domestic:'Brasil',south_america:'América do Sul',caribbean_mexico:'Caribe / México',usa_canada:'EUA / Canadá',europe:'Europa',long_haul:'Longa distância'})[x]||x||'—'}
function filteredHunter(){let rows=[...(hunterData.deals||[])],origin=$('#hunterOrigin').value,trip=$('#hunterTripType').value,region=$('#hunterRegion').value,min=Number($('#hunterMinScore').value||0),max=Number($('#hunterMaxPrice').value||0),stops=$('#hunterStops').value;return rows.filter(x=>(!origin||x.origin===origin)&&(!trip||flightScope(x)===trip)&&(!region||x.price_region===region)&&Number(x.hunter_score||0)>=min&&(!max||Number(x.price)<=max)&&(stops===''||Number(x.stops_count||0)<=Number(stops))).sort((a,b)=>(Number(b.hunter_score||0)-Number(a.hunter_score||0))||(Number(a.price||0)-Number(b.price||0)))}
function renderHunter(){let rows=filteredHunter(),tb=$('#hunterRows');tb.innerHTML='';$('#hunterEmpty').hidden=rows.length>0;for(const x of rows){let score=Number(x.hunter_score||0),scoreClass=score>=80?'high':score>=60?'good':'',disc=Number(x.provider_discount_pct||0),fresh=x.fresh?'<span class="fresh">NOVO · </span>':'',why=[];if(Number(x.absolute_price_points||0)>0)why.push(`preço absoluto +${Number(x.absolute_price_points)}`);if(disc>0)why.push(`${disc.toFixed(0)}% abaixo do típico`);if(Number(x.itinerary_points||0)>0)why.push(x.stops_count===0?'voo direto':'itinerário bom');if(x.external_verified)why.push(`rechecado após ${esc(x.external_source||'sinal externo')}`);let ext=x.external_url?`<br><a class="official-note" href="${safe(x.external_url)}" target="_blank" rel="noopener">ver sinal externo</a>`:'',tr=document.createElement('tr');tr.innerHTML=`<td class="route"><b>${esc(x.origin)} → ${esc(x.destination)}</b><small>${esc(x.origin_name||x.origin)} → ${esc(x.destination_name||x.destination)} · ${hunterRegionLabel(x.price_region)}</small></td><td class="date-stack"><b>${fmtDate(x.departure_date)} → ${fmtDate(x.return_date)}</b><small>${x.trip_days?x.trip_days+' dias':''}</small></td><td><b>${esc(x.airline||'Não informado')}</b><small class="ref">${esc(x.stops||'')} ${x.duration?'· '+esc(x.duration):''}</small></td><td class="hunter-price">${money(x.price)}<span class="statline">${disc>0?disc.toFixed(0)+'% abaixo do preço típico':''}</span></td><td class="why">${fresh}<b>${esc((why[0]||'preço excepcional'))}</b>${why.slice(1).map(v=>'<br>'+esc(v)).join('')}${ext}</td><td><span class="score ${scoreClass}">${score}</span><br><span class="badge ${score>=90?'super':score>=80?'hot':score>=70?'deal':'strict'}">${esc(x.hunter_status||'')}</span></td><td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Ver voo</a></td>`;tb.appendChild(tr)}}
function hunterMetrics(){$('#hunterActiveCount').textContent=hunterData.active_count??(hunterData.deals||[]).length;$('#hunterCheapCount').textContent=hunterData.very_cheap_count??(hunterData.deals||[]).filter(x=>Number(x.hunter_score||0)>=70).length;$('#hunterExceptionalCount').textContent=hunterData.exceptional_count??(hunterData.deals||[]).filter(x=>Number(x.hunter_score||0)>=80).length;$('#hunterVerifiedCount').textContent=hunterData.external_verified??0;let stamp=hunterData.generated_at?new Date(hunterData.generated_at).toLocaleString('pt-BR'):'aguardando primeira caça';$('#hunterUpdated').textContent=hunterData.generated_at?'Deal Hunter '+stamp:stamp;let vals=(hunterData.deals||[]).map(x=>`${x.origin} · ${x.origin_name||x.origin}`);fillSelect($('#hunterOrigin'),vals,'Todas as origens');for(const opt of $('#hunterOrigin').options){let match=(hunterData.deals||[]).find(x=>opt.textContent.startsWith(x.origin+' ·'));if(match)opt.value=match.origin}}
function fmtExternalPrice(x){if(x.price==null)return'—';if(x.currency==='BRL')return money(x.price);let sym=x.currency==='USD'?'$':x.currency==='EUR'?'€':x.currency==='GBP'?'£':'';return `${sym}${Number(x.price).toLocaleString('pt-BR')} ${esc(x.currency||'')}`}
function filteredExternal(){let rows=[...(externalData.signals||[])],source=$('#externalSource').value,mode=$('#externalMode').value,q=$('#externalQuery').value.trim().toLowerCase();return rows.filter(x=>{let hay=[x.title,x.origin_name,x.destination_name,x.origin,x.destination].join(' ').toLowerCase();return(!source||x.source===source)&&(!mode||x.trip_mode===mode)&&(!q||hay.includes(q))})}
function renderExternal(){let rows=filteredExternal(),tb=$('#externalRows');tb.innerHTML='';$('#externalEmpty').hidden=rows.length>0;for(const x of rows){let route=x.origin||x.destination?`${x.origin||'?'} → ${x.destination||'?'}`:'não identificada',tr=document.createElement('tr');tr.innerHTML=`<td class="external-title"><b>${esc(x.title||'Oferta')}</b><small>${x.availability?esc(x.availability):''}${x.airline?' · '+esc(x.airline):''}</small></td><td><span class="badge official">${esc(x.source)}</span>${x.error_fare?'<br><span class="badge super">ERROR FARE</span>':''}</td><td class="price">${fmtExternalPrice(x)}</td><td>${esc(modeLabel(x.trip_mode))}</td><td class="route"><b>${esc(route)}</b><small>${esc(x.origin_name||'')} ${x.destination_name?'→ '+esc(x.destination_name):''}</small></td><td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Abrir fonte</a></td>`;tb.appendChild(tr)}}
function externalMetrics(){$('#externalSignalCount').textContent=externalData.signal_count??(externalData.signals||[]).length;$('#externalSourceCount').textContent=`${externalData.responding_source_count??0}/${externalData.source_count??3}`;$('#externalSecretCount').textContent=(externalData.signals||[]).filter(x=>x.source==='Secret Flying').length;$('#externalBrazilCount').textContent=(externalData.signals||[]).filter(x=>/brazil|brasil|sao paulo|são paulo|rio de janeiro|campinas/i.test([x.title,x.origin_name].join(' '))).length;let stamp=externalData.generated_at?new Date(externalData.generated_at).toLocaleString('pt-BR'):'aguardando primeira coleta';$('#externalUpdated').textContent=externalData.generated_at?'Atualizado '+stamp:stamp;let box=$('#externalSources');box.innerHTML='';for(const name of ['Secret Flying','Melhores Destinos','Passagens Imperdíveis']){let info=(externalData.sources||{})[name],e=document.createElement('span');e.className='source-pill '+(info?.ok?'ok':'bad');e.textContent=info?`${info.ok?'●':'○'} ${name}: ${info.items||0}${info.ok?'':' · indisponível'}`:`○ ${name} · aguardando`;if(info?.message)e.title=info.message;box.appendChild(e)}}
'''
    html = replace_once(html, marker, extra_js + marker, "funções Deal Hunter")

    old_set = "function setFlightView(mode){flightView=mode;$('#radarPanel').hidden=mode!=='radar';$('#airlinesPanel').hidden=mode!=='airlines';document.querySelectorAll('#flightTabs .tab').forEach(b=>b.classList.toggle('active',b.dataset.flightView===mode));if(mode==='airlines')renderAirlines();else renderFlights()}"
    new_set = "function setFlightView(mode){flightView=mode;$('#hunterPanel').hidden=mode!=='hunter';$('#radarPanel').hidden=mode!=='radar';$('#externalPanel').hidden=mode!=='external';$('#airlinesPanel').hidden=mode!=='airlines';document.querySelectorAll('#flightTabs .tab').forEach(b=>b.classList.toggle('active',b.dataset.flightView===mode));if(mode==='hunter')renderHunter();else if(mode==='external')renderExternal();else if(mode==='airlines')renderAirlines();else renderFlights()}"
    html = replace_once(html, old_set, new_set, "troca de aba")

    old_main = "function setMain(mode){mainView=mode;$('#productsApp').hidden=mode!=='products';$('#flightsApp').hidden=mode!=='flights';document.querySelectorAll('.main-tab').forEach(b=>b.classList.toggle('active',b.dataset.main===mode));if(mode==='flights'){if(flightView==='airlines')renderAirlines();else renderFlights()}else renderProducts()}"
    new_main = "function setMain(mode){mainView=mode;$('#productsApp').hidden=mode!=='products';$('#flightsApp').hidden=mode!=='flights';document.querySelectorAll('.main-tab').forEach(b=>b.classList.toggle('active',b.dataset.main===mode));if(mode==='flights')setFlightView(flightView);else renderProducts()}"
    html = replace_once(html, old_main, new_main, "troca principal")

    old_boot = "async function bootAirlines(){try{let r=await fetch('./data/airlines.json?t='+Date.now(),{cache:'no-store'});airlineData=await r.json()}catch(e){airlineData={offers:[],sources:{},source_count:3,responding_source_count:0}}airlineMetrics();if(mainView==='flights'){if(flightView==='airlines')renderAirlines();else renderFlights()}}"
    new_boot = old_boot + "\nasync function bootHunter(){try{let r=await fetch('./data/deal-hunter.json?t='+Date.now(),{cache:'no-store'});hunterData=await r.json()}catch(e){hunterData={deals:[]}}hunterMetrics();if(mainView==='flights'&&flightView==='hunter')renderHunter()}\nasync function bootExternal(){try{let r=await fetch('./data/external-deals.json?t='+Date.now(),{cache:'no-store'});externalData=await r.json()}catch(e){externalData={signals:[],sources:{},source_count:3,responding_source_count:0}}externalMetrics();if(mainView==='flights'&&flightView==='external')renderExternal()}"
    html = replace_once(html, old_boot, new_boot, "boots")

    old_events = "document.querySelectorAll('.main-tab').forEach(b=>b.onclick=()=>setMain(b.dataset.main));document.querySelectorAll('#productsApp .tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('#productsApp .tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;renderProducts()});document.querySelectorAll('#flightTabs .tab').forEach(b=>b.onclick=()=>setFlightView(b.dataset.flightView));['q','source','category','minPrice','maxPrice','minDiff','sort'].forEach(id=>$('#'+id).addEventListener('input',renderProducts));['flightOrigin','flightTripType','flightSource','flightDestination','flightMaxPrice','flightMinScore','flightMinDiscount','flightStops','flightSort'].forEach(id=>$('#'+id).addEventListener('input',renderFlights));['airlineSource','airlineTripType','airlineOrigin','airlineMode','airlineMaxPrice'].forEach(id=>$('#'+id).addEventListener('input',renderAirlines));document.addEventListener('visibilitychange',()=>{if(!document.hidden){bootProducts();bootFlights();bootAirlines()}});bootProducts();bootFlights();bootAirlines();setInterval(()=>{bootProducts();bootFlights();bootAirlines()},120000);"
    new_events = "document.querySelectorAll('.main-tab').forEach(b=>b.onclick=()=>setMain(b.dataset.main));document.querySelectorAll('#productsApp .tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('#productsApp .tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;renderProducts()});document.querySelectorAll('#flightTabs .tab').forEach(b=>b.onclick=()=>setFlightView(b.dataset.flightView));['q','source','category','minPrice','maxPrice','minDiff','sort'].forEach(id=>$('#'+id).addEventListener('input',renderProducts));['flightOrigin','flightTripType','flightSource','flightDestination','flightMaxPrice','flightMinScore','flightMinDiscount','flightStops','flightSort'].forEach(id=>$('#'+id).addEventListener('input',renderFlights));['hunterOrigin','hunterTripType','hunterRegion','hunterMinScore','hunterMaxPrice','hunterStops'].forEach(id=>$('#'+id).addEventListener('input',renderHunter));['externalSource','externalMode','externalQuery'].forEach(id=>$('#'+id).addEventListener('input',renderExternal));['airlineSource','airlineTripType','airlineOrigin','airlineMode','airlineMaxPrice'].forEach(id=>$('#'+id).addEventListener('input',renderAirlines));document.addEventListener('visibilitychange',()=>{if(!document.hidden){bootProducts();bootFlights();bootAirlines();bootHunter();bootExternal()}});bootProducts();bootFlights();bootAirlines();bootHunter();bootExternal();setInterval(()=>{bootProducts();bootFlights();bootAirlines();bootHunter();bootExternal()},60000);"
    html = replace_once(html, old_events, new_events, "eventos")

    PATH.write_text(html, encoding="utf-8")
    print("Painel atualizado com Deal Hunter, Radar contínuo, Fontes externas e Companhias.")


if __name__ == "__main__":
    main()
