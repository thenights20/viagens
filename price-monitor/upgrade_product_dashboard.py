from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs" / "index.html"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marcador não encontrado: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    html = PATH.read_text(encoding="utf-8")
    if 'data-view="bugs"' in html and 'id="productBugPanel"' in html:
        print("Painel de produtos Bug Hunter já aplicado.")
        return

    html = replace_once(
        html,
        '.external-title{max-width:620px}.external-title b{display:block}.external-title small{color:var(--muted)}',
        '.external-title{max-width:620px}.external-title b{display:block}.external-title small{color:var(--muted)}.product-bug-filters{grid-template-columns:1.2fr 1.1fr 1fr 1fr 1fr}.sensor-filters{grid-template-columns:1.2fr 2fr 1fr}.bug-reason{max-width:360px;color:var(--muted);font-size:11px;line-height:1.5}.bug-reason b{color:var(--text)}.trust-note{font-size:10px;color:var(--muted)}.coupon-code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:14px;font-weight:900;color:var(--warn)}',
        "css",
    )
    html = html.replace(
        '@media(max-width:1100px){.filters,.flight-filters,.airline-filters,.hunter-filters,.external-filters{grid-template-columns:repeat(3,1fr)}',
        '@media(max-width:1100px){.filters,.flight-filters,.airline-filters,.hunter-filters,.external-filters,.product-bug-filters,.sensor-filters{grid-template-columns:repeat(3,1fr)}',
        1,
    )
    html = html.replace(
        '@media(max-width:700px){.cards{grid-template-columns:repeat(2,1fr)}.filters,.flight-filters,.airline-filters,.hunter-filters,.external-filters{grid-template-columns:1fr 1fr}',
        '@media(max-width:700px){.cards{grid-template-columns:repeat(2,1fr)}.filters,.flight-filters,.airline-filters,.hunter-filters,.external-filters,.product-bug-filters,.sensor-filters{grid-template-columns:1fr 1fr}',
        1,
    )

    old_header = '<div class="flight-head"><div></div><div class="flight-actions"><div class="pill"><span class="dot"></span><span id="productUpdated">Carregando…</span></div><a class="manual-btn secondary" href="https://github.com/thenights20/viagens/actions/workflows/price-monitor.yml" target="_blank" rel="noopener">↻ Atualizar produtos</a></div></div>'
    new_header = '<div class="flight-head"><div><h2>Produtos · Bug Hunter</h2><div class="sub">Varredura rápida de preços absurdamente baixos + radar histórico + sensores públicos. O scanner rápido roda separado do monitor amplo.</div></div><div class="flight-actions"><div class="pill"><span class="dot"></span><span id="productBugUpdated">Aguardando caça</span></div><a class="manual-btn" href="https://github.com/thenights20/viagens/actions/workflows/product-bug-hunter.yml" target="_blank" rel="noopener">🔥 Rodar Bug Hunter</a><a class="manual-btn secondary" href="https://github.com/thenights20/viagens/actions/workflows/price-monitor.yml" target="_blank" rel="noopener">↻ Radar profundo</a></div></div>'
    html = replace_once(html, old_header, new_header, "cabeçalho produtos")

    old_tabs = '<nav class="tabs"><button class="tab active" data-view="all">Todos os produtos</button><button class="tab" data-view="highlights">Destaques</button><button class="tab" data-view="tracked">Em vistoria</button><button class="tab" data-view="watchlist">Lista de vistoria</button></nav>'
    new_tabs = '<nav class="tabs" id="productTabs"><button class="tab active" data-view="bugs">🔥 Bug Hunter</button><button class="tab" data-view="radar">Radar de preços</button><button class="tab" data-view="coupons">Cupons</button><button class="tab" data-view="sensors">Sensores externos</button><button class="tab" data-view="all">Todas as ofertas</button><button class="tab" data-view="watchlist">Lista de vistoria</button></nav>'
    html = replace_once(html, old_tabs, new_tabs, "abas produtos")

    panels = '''
  <div id="productBugPanel">
    <section class="cards"><div class="card"><span>Bugs ativos</span><b id="productBugCount">—</b></div><div class="card"><span>Score 70+</span><b id="productBugStrong">—</b></div><div class="card"><span>Score 90+</span><b id="productBugCritical">—</b></div><div class="card"><span>Revalidados</span><b id="productBugConfirmed">—</b></div></section>
    <section class="panel filters product-bug-filters"><select id="productBugSource"><option value="">Todas as fontes</option></select><select id="productBugCategory"><option value="">Todas as categorias</option></select><select id="productBugMinScore"><option value="60">60+ Suspeito</option><option value="70" selected>70+ Bug forte</option><option value="80">80+ Fora da curva</option><option value="90">90+ Bug provável</option></select><input id="productBugMaxPrice" type="number" min="0" step="50" placeholder="Preço máx. R$"><select id="productBugTrust"><option value="">Qualquer confiança</option><option value="confirmed">Preço revalidado</option><option value="trusted">Vendedor/loja confiável</option><option value="sensor">Sensor externo</option></select></section>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>Produto</th><th>Preço</th><th>Referência</th><th>Por que entrou</th><th>Fonte / confiança</th><th>Bug Score</th><th></th></tr></thead><tbody id="productBugRows"></tbody></table></div><div class="empty" id="productBugEmpty" hidden><strong>Nenhum bug forte neste filtro.</strong>Isso é bom: a aba foi feita para ser seletiva.</div></section>
    <div class="source-row" id="productBugSources"></div><div class="note"><b>Como funciona:</b> o Bug Hunter não exige economia de R$ 1.000. Uma Air Fryer a R$ 14, um micro-ondas a R$ 79 ou um PS5 a R$ 449 entram pela relação preço/categoria, mesmo sendo produtos com preços normais bem abaixo de R$ 3.000.</div>
  </div>
  <div id="productCouponPanel" hidden>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>Oferta / cupom</th><th>Código</th><th>Loja</th><th>Preço citado</th><th></th></tr></thead><tbody id="productCouponRows"></tbody></table></div><div class="empty" id="productCouponEmpty" hidden><strong>Nenhum cupom capturado nesta rodada.</strong></div></section>
  </div>
  <div id="productSensorPanel" hidden>
    <section class="cards"><div class="card"><span>Sinais recentes</span><b id="productSensorCount">—</b></div><div class="card"><span>Marcados BUG</span><b id="productSensorBugCount">—</b></div><div class="card"><span>Cupons</span><b id="productSensorCouponCount">—</b></div><div class="card"><span>Fonte</span><b>La Promotion</b></div></section>
    <section class="panel filters sensor-filters"><select id="productSensorKind"><option value="">Produtos + cupons</option><option value="product">Somente produtos</option><option value="coupon">Somente cupons</option></select><input id="productSensorQuery" placeholder="Produto, loja ou cupom…"><select id="productSensorBug"><option value="">Todos os sinais</option><option value="bug">Somente marcados BUG</option></select></section>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>Publicação</th><th>Preço</th><th>Cupom</th><th>Destino do link</th><th>Status</th><th></th></tr></thead><tbody id="productSensorRows"></tbody></table></div><div class="empty" id="productSensorEmpty" hidden><strong>Nenhum sinal neste filtro.</strong></div></section>
    <div class="note"><b>Benchmark:</b> a La Promotion entra como sensor público. Um post externo não vira confirmação automática; ele serve para medir onde nosso scanner ainda está cego e para reagir rapidamente a uma oferta nova.</div>
  </div>
'''
    html = replace_once(html, '  <section class="panel filters" id="filters">', panels + '  <section class="panel filters" id="filters" hidden>', "painéis produtos")

    old_state = "let data={products:[],watchlist:[],active:[]},flightData={deals:[],origins:[]},airlineData={offers:[],sources:{}},hunterData={deals:[]},externalData={signals:[],sources:{}},view='all',mainView='products',flightView='hunter';"
    new_state = "let data={products:[],watchlist:[],active:[]},productBugData={bugs:[],source_health:{}},productSensorData={signals:[],sources:{}},flightData={deals:[],origins:[]},airlineData={offers:[],sources:{}},hunterData={deals:[]},externalData={signals:[],sources:{}},view='bugs',mainView='products',flightView='hunter';"
    html = replace_once(html, old_state, new_state, "estado JS")

    old_products_filter = "rows=rows.filter(x=>{if(view==='highlights'&&!x.highlighted)return false;if(view==='tracked'&&!x.tracked)return false;let hay=[x.title,x.source,x.store_name,x.category,...(x.watch_terms||[])].join(' ').toLowerCase();return(!q||hay.includes(q))&&(!src||x.source===src)&&(!cat||x.category===cat)&&Number(x.price)>=min&&(!max||Number(x.price)<=max)&&Number(x.difference_pct||0)>=dif});"
    new_products_filter = "rows=rows.filter(x=>{if(view==='radar'&&Number(x.difference_pct||0)<=0&&!x.highlighted)return false;let hay=[x.title,x.source,x.store_name,x.category,...(x.watch_terms||[])].join(' ').toLowerCase();return(!q||hay.includes(q))&&(!src||x.source===src)&&(!cat||x.category===cat)&&Number(x.price)>=min&&(!max||Number(x.price)<=max)&&Number(x.difference_pct||0)>=dif});"
    html = replace_once(html, old_products_filter, new_products_filter, "filtro radar")

    marker = 'function hunterRegionLabel(x){'
    extra_js = r'''function hideProductPanels(){['productBugPanel','productCouponPanel','productSensorPanel','productsPanel','watchPanel','filters'].forEach(id=>{$('#'+id).hidden=true})}
function filteredProductBugs(){let rows=[...(productBugData.bugs||[])],src=$('#productBugSource').value,cat=$('#productBugCategory').value,min=Number($('#productBugMinScore').value||0),max=Number($('#productBugMaxPrice').value||0),trust=$('#productBugTrust').value;return rows.filter(x=>(!src||x.source===src)&&(!cat||x.category===cat)&&Number(x.bug_score||0)>=min&&(!max||Number(x.price)<=max)&&(!trust||(trust==='confirmed'&&x.revalidated)||(trust==='trusted'&&x.trusted)||(trust==='sensor'&&x.external_source))).sort((a,b)=>(Number(b.bug_score||0)-Number(a.bug_score||0))||(Number(a.price||0)-Number(b.price||0)))}
function renderProductBugs(){hideProductPanels();$('#productBugPanel').hidden=false;let rows=filteredProductBugs(),tb=$('#productBugRows');tb.innerHTML='';$('#productBugEmpty').hidden=rows.length>0;for(const x of rows){let score=Number(x.bug_score||0),reasons=(x.reasons||[]).slice(0,3),trust=x.revalidated?'Preço revalidado':x.trusted?'Loja/vendedor confiável':x.external_source?'Sensor externo':'Verificar vendedor',tr=document.createElement('tr');tr.innerHTML=`<td class="prod"><b>${esc(x.title||'Produto')}</b><small>${esc(x.category||x.category_rule||'')}</small></td><td class="hunter-price">${money(x.price)}</td><td class="ref">${money(x.baseline_price||x.reference_price||x.original_price)}<br><small>${esc(x.baseline_kind||'')}</small></td><td class="bug-reason"><b>${esc(reasons[0]||'preço muito baixo')}</b>${reasons.slice(1).map(v=>'<br>'+esc(v)).join('')}</td><td><span class="badge ${x.revalidated?'strict':x.external_source?'official':''}">${esc(x.source||'')}</span><br><span class="trust-note">${esc(trust)}</span></td><td><span class="score ${score>=80?'high':score>=60?'good':''}">${score}</span><br><span class="badge ${score>=90?'super':score>=80?'hot':score>=70?'deal':'strict'}">${esc(x.bug_status||'')}</span></td><td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Abrir</a>${x.post_url?`<br><a class="official-note" href="${safe(x.post_url)}" target="_blank" rel="noopener">ver sensor</a>`:''}</td>`;tb.appendChild(tr)}}
function renderProductSensors(){hideProductPanels();$('#productSensorPanel').hidden=false;let kind=$('#productSensorKind').value,q=$('#productSensorQuery').value.trim().toLowerCase(),bug=$('#productSensorBug').value,rows=[...(productSensorData.signals||[])].filter(x=>(!kind||x.kind===kind)&&(!bug||x.external_bug)&&(!q||[x.title,x.text,x.store_hint,x.coupon].join(' ').toLowerCase().includes(q)));let tb=$('#productSensorRows');tb.innerHTML='';$('#productSensorEmpty').hidden=rows.length>0;for(const x of rows){let tr=document.createElement('tr');tr.innerHTML=`<td class="prod"><b>${esc(x.title||'Sinal')}</b><small>${x.published_at?new Date(x.published_at).toLocaleString('pt-BR'):''}</small></td><td class="price">${money(x.price)}</td><td>${x.coupon?`<span class="coupon-code">${esc(x.coupon)}</span>`:'—'}</td><td>${esc(x.store_hint||'')}</td><td>${x.external_bug?'<span class="badge super">BUG EXTERNO</span>':'<span class="badge">SINAL</span>'}</td><td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Abrir</a></td>`;tb.appendChild(tr)}}
function renderProductCoupons(){hideProductPanels();$('#productCouponPanel').hidden=false;let rows=[...(productSensorData.signals||[])].filter(x=>x.kind==='coupon'||x.coupon),tb=$('#productCouponRows');tb.innerHTML='';$('#productCouponEmpty').hidden=rows.length>0;for(const x of rows){let tr=document.createElement('tr');tr.innerHTML=`<td class="prod"><b>${esc(x.title||'Cupom')}</b><small>${esc((x.text||'').slice(0,180))}</small></td><td>${x.coupon?`<span class="coupon-code">${esc(x.coupon)}</span>`:'consulte a publicação'}</td><td>${esc(x.store_hint||'')}</td><td class="price">${money(x.price)}</td><td><a class="btn" href="${safe(x.url)}" target="_blank" rel="noopener">Abrir</a></td>`;tb.appendChild(tr)}}
function productBugMetrics(){$('#productBugCount').textContent=productBugData.active_count??(productBugData.bugs||[]).length;$('#productBugStrong').textContent=productBugData.strong_count??0;$('#productBugCritical').textContent=productBugData.critical_count??0;$('#productBugConfirmed').textContent=productBugData.confirmed_count??0;let stamp=productBugData.generated_at?new Date(productBugData.generated_at).toLocaleString('pt-BR'):'aguardando primeira varredura';$('#productBugUpdated').textContent=productBugData.generated_at?'Bug Hunter '+stamp:stamp;fillSelect($('#productBugSource'),(productBugData.bugs||[]).map(x=>x.source),'Todas as fontes');fillSelect($('#productBugCategory'),(productBugData.bugs||[]).map(x=>x.category),'Todas as categorias');let box=$('#productBugSources');box.innerHTML='';for(const [name,info] of Object.entries(productBugData.source_health||{})){let e=document.createElement('span');e.className='source-pill '+(info?.ok?'ok':'bad');e.textContent=`${info?.ok?'●':'○'} ${name}: ${info?.items||0}`;if(info?.message)e.title=info.message;box.appendChild(e)}}
function productSensorMetrics(){$('#productSensorCount').textContent=productSensorData.signal_count??(productSensorData.signals||[]).length;$('#productSensorBugCount').textContent=productSensorData.bug_marked_count??0;$('#productSensorCouponCount').textContent=productSensorData.coupon_count??0}
function renderProductMode(){if(view==='bugs')return renderProductBugs();if(view==='sensors')return renderProductSensors();if(view==='coupons')return renderProductCoupons();hideProductPanels();if(view==='watchlist')return renderWatch();$('#productsPanel').hidden=false;$('#filters').hidden=false;renderProducts()}
async function bootProductBugs(){try{let r=await fetch('./data/product-bugs.json?t='+Date.now(),{cache:'no-store'});productBugData=await r.json()}catch(e){productBugData={bugs:[],source_health:{}}}try{let r=await fetch('./data/product-sensors.json?t='+Date.now(),{cache:'no-store'});productSensorData=await r.json()}catch(e){productSensorData={signals:[],sources:{}}}productBugMetrics();productSensorMetrics();if(mainView==='products')renderProductMode()}
'''
    html = replace_once(html, marker, extra_js + marker, "JS produtos")

    html = replace_once(html, "else renderProducts()}", "else renderProductMode()}", "setMain produtos")
    html = replace_once(html, "productMetrics();if(mainView==='products')renderProducts()}", "productMetrics();if(mainView==='products')renderProductMode()}", "boot produtos")

    old_events = "document.querySelectorAll('#productsApp .tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('#productsApp .tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;renderProducts()});"
    new_events = "document.querySelectorAll('#productTabs .tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('#productTabs .tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');view=b.dataset.view;renderProductMode()});"
    html = replace_once(html, old_events, new_events, "eventos abas produtos")
    html = replace_once(html, "['q','source','category','minPrice','maxPrice','minDiff','sort'].forEach(id=>$('#'+id).addEventListener('input',renderProducts));", "['q','source','category','minPrice','maxPrice','minDiff','sort'].forEach(id=>$('#'+id).addEventListener('input',renderProductMode));['productBugSource','productBugCategory','productBugMinScore','productBugMaxPrice','productBugTrust'].forEach(id=>$('#'+id).addEventListener('input',renderProductBugs));['productSensorKind','productSensorQuery','productSensorBug'].forEach(id=>$('#'+id).addEventListener('input',renderProductSensors));", "eventos filtros produtos")
    html = replace_once(html, "bootProducts();bootFlights();bootAirlines();bootHunter();bootExternal()", "bootProducts();bootProductBugs();bootFlights();bootAirlines();bootHunter();bootExternal()", "visibility")
    html = replace_once(html, "bootProducts();bootFlights();bootAirlines();bootHunter();bootExternal();setInterval(()=>{bootProducts();bootFlights();bootAirlines();bootHunter();bootExternal()},60000);", "bootProducts();bootProductBugs();bootFlights();bootAirlines();bootHunter();bootExternal();setInterval(()=>{bootProducts();bootProductBugs();bootFlights();bootAirlines();bootHunter();bootExternal()},60000);", "boot inicial")

    PATH.write_text(html, encoding="utf-8")
    print("Painel de produtos atualizado com Bug Hunter.")


if __name__ == "__main__":
    main()
