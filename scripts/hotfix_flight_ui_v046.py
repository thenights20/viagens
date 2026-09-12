from pathlib import Path
import re

p = Path('docs/flight-explorer.js')
s = p.read_text(encoding='utf-8')

s = s.replace('Buscar passagens · v0.4.4', 'Buscar passagens · v0.4.6', 1)

# 1) Filtro de mês nas buscas salvas.
old = '<div><label for="resultDestination">Filtrar destino</label><select id="resultDestination"><option value="">Todos os destinos</option></select></div>\n      <div><label for="resultSort">Ordenar por</label><select id="resultSort"><option value="price_asc">Menor preço primeiro</option><option value="price_desc">Maior preço primeiro</option><option value="date_asc">Data de ida</option></select></div>'
new = '<div><label for="resultDestination">Filtrar destino</label><select id="resultDestination"><option value="">Todos os destinos</option></select></div>\n      <div><label for="resultMonth">Mês</label><select id="resultMonth"><option value="">Todos os meses</option></select></div>\n      <div><label for="resultSort">Ordenar por</label><select id="resultSort"><option value="price_asc">Menor preço primeiro</option><option value="price_desc">Maior preço primeiro</option><option value="date_asc">Data de ida</option></select></div>'
if old in s:
    s = s.replace(old, new, 1)

old_filter = "function filterRows(rows,origin,destination,sort){\n    return rows.filter(x=>(!origin||x.origin===origin)&&(!destination||x.destination===destination)).sort((a,b)=>sort==='date_asc'?a.departure_date.localeCompare(b.departure_date)||Number(a.price)-Number(b.price):sort==='price_desc'?Number(b.price)-Number(a.price):Number(a.price)-Number(b.price));\n  }"
new_filter = "function filterRows(rows,origin,destination,sort,month){\n    return rows.filter(x=>(!origin||x.origin===origin)&&(!destination||x.destination===destination)&&(!month||String(x.departure_date||'').slice(0,7)===month)).sort((a,b)=>sort==='date_asc'?a.departure_date.localeCompare(b.departure_date)||Number(a.price)-Number(b.price):sort==='price_desc'?Number(b.price)-Number(a.price):Number(a.price)-Number(b.price));\n  }"
if old_filter in s:
    s = s.replace(old_filter, new_filter, 1)

marker = "  function calendarRows(rows){"
if 'function resultMonthOptions(' not in s and marker in s:
    insert = "  function monthLabel(key){if(!/^\\d{4}-\\d{2}$/.test(key||''))return key||'';const[y,m]=key.split('-').map(Number);const text=new Intl.DateTimeFormat('pt-BR',{month:'long',year:'numeric'}).format(new Date(y,m-1,1));return text.charAt(0).toUpperCase()+text.slice(1);}\n  function resultMonthOptions(rows){const el=q('#resultMonth');if(!el)return;const selected=el.value,months=[...new Set(rows.map(x=>String(x.departure_date||'').slice(0,7)).filter(x=>/^\\d{4}-\\d{2}$/.test(x)))].sort();el.innerHTML='<option value=\"\">Todos os meses</option>'+months.map(m=>`<option value=\"${esc(m)}\">${esc(monthLabel(m))}</option>`).join('');el.value=months.includes(selected)?selected:'';}\n"
    s = s.replace(marker, insert + marker, 1)

old_render = "    const available=availableRows();resultOptions(available);\n    const filtered=filterRows(available,q('#resultOrigin').value,q('#resultDestination').value,q('#resultSort').value),rows=filtered.slice(0,100),stats=data.stats||{},req=data.request||{},hist=data.history_summary||{};"
new_render = "    const available=availableRows();resultOptions(available);resultMonthOptions(available);\n    const allScope=q('#resultScope').value==='all',filtered=filterRows(available,q('#resultOrigin').value,q('#resultDestination').value,q('#resultSort').value,q('#resultMonth')?.value||''),rows=filtered.slice(0,100),stats=data.stats||{},req=data.request||{},hist=data.history_summary||{};"
if old_render in s:
    s = s.replace(old_render, new_render, 1)

old_cards = "    q('#monthLowest').textContent=money(stats.lowest_price);\n    const processed=stats.processed_combinations??stats.combinations;q('#monthCombos').textContent=stats.combinations!=null?`${processed}/${stats.combinations}`:'—';\n    q('#monthPriced').textContent=stats.priced_combinations!=null?`${stats.priced_combinations} · ${stats.coverage_pct||0}%`:'—';q('#monthCount').textContent=data.results?.length?`${data.results.length}/100`:'—';q('#monthHistory').textContent=(hist.compared||hist.cheaper||hist.higher)?`↓${hist.cheaper||0} ↑${hist.higher||0}`:'sem comparação';"
new_cards = "    if(allScope){const histPrices=filtered.map(x=>Math.min(Number(x.price)||Infinity,Number(x.historical_min)||Infinity)).filter(Number.isFinite);q('#monthLowest').textContent=money(histPrices.length?Math.min(...histPrices):null);q('#monthLowest').parentElement.querySelector('span').textContent='Menor histórico salvo';q('#monthCombos').textContent=String(filtered.length);q('#monthPriced').textContent=filtered.length?'dados salvos':'0';q('#monthCount').textContent=filtered.length?`${Math.min(filtered.length,100)}/${filtered.length}`:'—';q('#monthHistory').textContent=filtered.length?'histórico preservado':'sem dados';}else{q('#monthLowest').parentElement.querySelector('span').textContent='Menor preço';q('#monthLowest').textContent=money(stats.lowest_price);const processed=stats.processed_combinations??stats.combinations;q('#monthCombos').textContent=stats.combinations!=null?`${processed}/${stats.combinations}`:'—';q('#monthPriced').textContent=stats.priced_combinations!=null?`${stats.priced_combinations} · ${stats.coverage_pct||0}%`:'—';q('#monthCount').textContent=data.results?.length?`${data.results.length}/100`:'—';q('#monthHistory').textContent=(hist.compared||hist.cheaper||hist.higher)?`↓${hist.cheaper||0} ↑${hist.higher||0}`:'sem comparação';}"
if old_cards in s:
    s = s.replace(old_cards, new_cards, 1)

old_events = "for(const id of ['#resultScope','#resultOrigin','#resultDestination','#resultSort'])q(id).addEventListener('change',()=>{render();if(id==='#resultScope'&&q(id).value==='all')loadSavedPairs().then(render)});"
new_events = "for(const id of ['#resultScope','#resultOrigin','#resultDestination','#resultMonth','#resultSort'])q(id).addEventListener('change',()=>{render();if(id==='#resultScope'&&q(id).value==='all')loadSavedPairs().then(render)});"
if old_events in s:
    s = s.replace(old_events, new_events, 1)

# 2) Progresso: não inventar 1/2/3/15%; usar o progresso publicado pelo motor.
s = s.replace("function showProgress(total){q('#monthProgress').hidden=false;q('#monthStopButton').disabled=false;updateProgress({pct:1,stage:'Enviando solicitação…'", "function showProgress(total){q('#monthProgress').hidden=false;q('#monthStopButton').disabled=false;updateProgress({pct:0,stage:'Enviando solicitação…'", 1)

pat = re.compile(r"  function liveProgress\(live,elapsed\)\{.*?\n    return\{pct,stage:label,done,total,priced:Number\(s\.priced_combinations\|\|0\),remaining:Math\.max\(0,total-done\),elapsed,detail\};\}\n", re.S)
repl = '''  function liveProgress(live,elapsed){const s=live.stats||{},stage=live.stage||'starting',total=Number(s.combinations||0),primary=Number(s.primary_completed??s.processed_combinations??0),primaryTotal=Number(s.primary_total||total),fb=Number(s.fallback_done||0),fbTotal=Number(s.fallback_total||0),priced=Number(s.priced_combinations||0);let pct=0,label='Preparando pesquisa…',done=Math.min(primary,total),remaining=Math.max(0,total-done),detail='aguardando primeiro lote';if(stage==='google'){pct=primaryTotal?primary/primaryTotal*100:0;label=`Etapa 1/2 · Google Flights · ${primary}/${primaryTotal}`;remaining=Math.max(0,primaryTotal-primary);detail=live.current_pair?`Consultando ${fmtDate(live.current_pair.departure_date)} → ${fmtDate(live.current_pair.return_date)} · salvo automaticamente`:`${priced} com preço · salvo automaticamente`;}else if(stage==='fallback'){pct=fbTotal?fb/fbTotal*100:0;label=`Etapa 2/2 · Confirmação · ${fb}/${fbTotal}`;done=total;remaining=Math.max(0,fbTotal-fb);detail=`${priced} combinações com preço · resultados salvos`;}else if(stage==='completed'){pct=100;label='Pesquisa concluída';done=total;remaining=0;detail='Resultado e histórico salvos';}else if(stage==='interrupted'){pct=primaryTotal?primary/primaryTotal*100:0;label='Pesquisa interrompida · parcial preservado';detail='Tudo o que foi encontrado continua salvo';}return{pct,stage:label,done,total,priced,remaining,elapsed,detail};}\n'''
s, n = pat.subn(repl, s, count=1)
if n != 1:
    raise SystemExit('liveProgress atual não encontrado')

s = s.replace("if(run.status==='queued')return{pct:3,stage:'Aguardando executor do GitHub…'", "if(run.status==='queued')return{pct:0,stage:'Na fila do GitHub Actions…'", 1)
s = s.replace("if(run.conclusion==='success')return{pct:98,stage:'Finalizando resultado…'", "if(run.conclusion==='success')return{pct:100,stage:'Execução concluída · carregando resultado…'", 1)
s = s.replace("return{pct:name==='Pesquisar matriz completa do período'?15:8,stage:name==='Dependências'?'Preparando motor de pesquisa…':'Preparando pesquisa…',done:0,total,priced:0,detail:name,run};", "return{pct:0,stage:name==='Pesquisar matriz completa do período'?'Motor iniciado · aguardando primeiro lote…':name==='Dependências'?'Preparando motor de pesquisa…':'Preparando pesquisa…',done:0,total,priced:0,detail:name,run};", 1)
s = s.replace("state={pct:Number(bridge.percent||3),stage:bs==='queued'?'Pesquisa recebida pelo serviço…':bs==='completed'||bs==='done'?'Finalizando resultado…':'Pesquisa confirmada pelo serviço…'", "state={pct:(bs==='completed'||bs==='done')?100:0,stage:bs==='queued'?'Pesquisa recebida · aguardando GitHub Actions…':bs==='completed'||bs==='done'?'Finalizando resultado…':'Pesquisa confirmada pelo serviço…'", 1)
s = s.replace("updateProgress({pct:2,stage:'Aguardando confirmação do serviço…'", "updateProgress({pct:0,stage:'Aguardando confirmação do serviço…'", 1)

p.write_text(s, encoding='utf-8')

# Cache bust do navegador.
loader = Path('docs/terabyte-live.js')
t = loader.read_text(encoding='utf-8')
t = re.sub(r"\./flight-explorer\.js\?v=[^'\"]+", "./flight-explorer.js?v=20260912-9", t, count=1)
t = re.sub(r"\./flight-explorer-enhancements\.js\?v=[^'\"]+", "./flight-explorer-enhancements.js?v=20260912-2", t, count=1)
loader.write_text(t, encoding='utf-8')
