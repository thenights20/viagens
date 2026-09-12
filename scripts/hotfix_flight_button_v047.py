from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js_path = ROOT / 'docs' / 'flight-explorer.js'
loader_path = ROOT / 'docs' / 'terabyte-live.js'

s = js_path.read_text(encoding='utf-8')

s = s.replace('Buscar passagens · v0.4.6', 'Buscar passagens · v0.4.7')

old_clear = "function clearForSearch(request,total){q('#resultScope').value='current';q('#resultOrigin').value='';q('#resultDestination').value='';data="
new_clear = "function clearForSearch(request,total){q('#resultScope').value='current';q('#resultOrigin').value='';q('#resultDestination').value='';if(q('#resultMonth'))q('#resultMonth').value='';data="
if old_clear in s:
    s = s.replace(old_clear, new_clear, 1)

old_bind = "for(const id of ['#resultScope','#resultOrigin','#resultDestination','#resultMonth','#resultSort'])q(id).addEventListener('change',()=>{render();if(id==='#resultScope'&&q(id).value==='all')loadSavedPairs().then(render)});\n  q('#monthSearchButton').addEventListener('click',searchInsidePage);q('#monthStopButton').addEventListener('click',stopSearch);q('#monthPeriodMode').addEventListener('change',periodModeChanged);q('#rangeStart').addEventListener('change',()=>{if(q('#rangeEnd').value<q('#rangeStart').value)q('#rangeEnd').value=q('#rangeStart').value});document.querySelectorAll('.month-view-btn').forEach(b=>b.addEventListener('click',()=>setResultView(b.dataset.resultView)));"
new_bind = "for(const id of ['#resultScope','#resultOrigin','#resultDestination','#resultMonth','#resultSort']){const el=q(id);if(el)el.addEventListener('change',()=>{render();if(id==='#resultScope'&&el.value==='all')loadSavedPairs().then(render)});}\n  const searchBtn=q('#monthSearchButton');if(searchBtn)searchBtn.addEventListener('click',e=>{e.preventDefault();searchInsidePage();});\n  const stopBtn=q('#monthStopButton');if(stopBtn)stopBtn.addEventListener('click',e=>{e.preventDefault();stopSearch();});\n  const periodMode=q('#monthPeriodMode');if(periodMode)periodMode.addEventListener('change',periodModeChanged);\n  const rangeStartEl=q('#rangeStart');if(rangeStartEl)rangeStartEl.addEventListener('change',()=>{const end=q('#rangeEnd');if(end&&end.value<rangeStartEl.value)end.value=rangeStartEl.value});\n  document.querySelectorAll('.month-view-btn').forEach(b=>b.addEventListener('click',()=>setResultView(b.dataset.resultView)));"
if old_bind not in s:
    raise SystemExit('bloco de eventos esperado não encontrado')
s = s.replace(old_bind, new_bind, 1)

# Fallback global: mesmo que algum plugin interfira no listener direto, o clique continua funcionando.
anchor = "btn.addEventListener('click',activate);"
if anchor not in s:
    raise SystemExit('âncora de ativação não encontrada')
fallback = "document.addEventListener('click',e=>{const t=e.target&&e.target.closest?e.target.closest('#monthSearchButton'):null;if(!t||t.disabled)return;if(!searching){e.preventDefault();searchInsidePage();}},true);\n  "
s = s.replace(anchor, fallback + anchor, 1)

js_path.write_text(s, encoding='utf-8')

loader = loader_path.read_text(encoding='utf-8')
loader = loader.replace('./flight-explorer.js?v=20260912-9', './flight-explorer.js?v=20260912-10')
loader_path.write_text(loader, encoding='utf-8')
