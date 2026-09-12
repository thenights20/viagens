from pathlib import Path
import re

js_path = Path('docs/flight-explorer.js')
loader_path = Path('docs/terabyte-live.js')
index_path = Path('docs/index.html')

js = js_path.read_text(encoding='utf-8')

# Versão visível.
js = js.replace('Buscar passagens · v0.4.7', 'Buscar passagens · v0.4.8')

# Horizonte mais folgado para pesquisas futuras; janeiro/2027 e meses seguintes ficam liberados.
js = js.replace(
    "monthInput.max=monthKey(new Date(now.getFullYear(),now.getMonth()+6,1))",
    "monthInput.max=monthKey(new Date(now.getFullYear(),now.getMonth()+18,1))"
)
js = js.replace(
    "q('#rangeStart').max=dateKey(new Date(now.getFullYear(),now.getMonth()+7,0))",
    "q('#rangeStart').max=dateKey(new Date(now.getFullYear(),now.getMonth()+19,0))"
)

# Botão explicitamente não-submit.
js = js.replace(
    '<button class="month-search-btn" id="monthSearchButton">🔎 Pesquisar agora</button>',
    '<button type="button" class="month-search-btn" id="monthSearchButton">🔎 Pesquisar agora</button>'
)

# ID compatível mesmo em navegadores sem crypto.randomUUID().
old_id = "request.request_id='web_'+crypto.randomUUID().replace(/-/g,'');"
new_id = "request.request_id='web_'+(globalThis.crypto&&typeof globalThis.crypto.randomUUID==='function'?globalThis.crypto.randomUUID().replace(/-/g,''):(Date.now().toString(36)+Math.random().toString(36).slice(2)+Math.random().toString(36).slice(2))).slice(0,64);"
if old_id in js:
    js = js.replace(old_id, new_id)

# Se a configuração ainda estiver carregando, tenta carregá-la no clique em vez de simplesmente desistir.
old_api = "if(!apiBase){status.className='month-search-status bad';status.textContent='O serviço de pesquisa ainda não está conectado.';return}"
new_api = "if(!apiBase)await loadConfig();if(!apiBase){status.className='month-search-status bad';status.textContent='O serviço de pesquisa ainda não está conectado. Atualize a página e tente novamente.';return}"
if old_api in js:
    js = js.replace(old_api, new_api)

# Não falhar silenciosamente se houver exceção síncrona no clique. Também remove o listener duplicado em captura.
old_bindings = """  const searchBtn=q('#monthSearchButton');if(searchBtn)searchBtn.addEventListener('click',e=>{e.preventDefault();searchInsidePage();});
  const stopBtn=q('#monthStopButton');if(stopBtn)stopBtn.addEventListener('click',e=>{e.preventDefault();stopSearch();});
  const periodMode=q('#monthPeriodMode');if(periodMode)periodMode.addEventListener('change',periodModeChanged);
  const rangeStartEl=q('#rangeStart');if(rangeStartEl)rangeStartEl.addEventListener('change',()=>{const end=q('#rangeEnd');if(end&&end.value<rangeStartEl.value)end.value=rangeStartEl.value});
  document.querySelectorAll('.month-view-btn').forEach(b=>b.addEventListener('click',()=>setResultView(b.dataset.resultView)));
  document.addEventListener('click',e=>{const t=e.target&&e.target.closest?e.target.closest('#monthSearchButton'):null;if(!t||t.disabled)return;if(!searching){e.preventDefault();searchInsidePage();}},true);
"""
new_bindings = """  const reportStartError=e=>{const status=q('#monthSearchStatus');if(status){status.className='month-search-status bad';status.textContent='Não foi possível iniciar a pesquisa: '+String(e&&e.message?e.message:e||'erro desconhecido');}console.error('flight-search-start',e);};
  const searchBtn=q('#monthSearchButton');if(searchBtn)searchBtn.addEventListener('click',e=>{e.preventDefault();if(searching){const status=q('#monthSearchStatus');if(status){status.className='month-search-status wait';status.textContent='Já existe uma pesquisa em andamento. Aguarde a conclusão ou use Parar pesquisa.';}return;}Promise.resolve(searchInsidePage()).catch(reportStartError);});
  const stopBtn=q('#monthStopButton');if(stopBtn)stopBtn.addEventListener('click',e=>{e.preventDefault();Promise.resolve(stopSearch()).catch(reportStartError);});
  const periodMode=q('#monthPeriodMode');if(periodMode)periodMode.addEventListener('change',periodModeChanged);
  const rangeStartEl=q('#rangeStart');if(rangeStartEl)rangeStartEl.addEventListener('change',()=>{const end=q('#rangeEnd');if(end&&end.value<rangeStartEl.value)end.value=rangeStartEl.value});
  document.querySelectorAll('.month-view-btn').forEach(b=>b.addEventListener('click',()=>setResultView(b.dataset.resultView)));
"""
if old_bindings in js:
    js = js.replace(old_bindings, new_bindings)
else:
    raise SystemExit('Bloco de eventos esperado não encontrado em flight-explorer.js')

# Mensagem clara ao escolher mês.
needle = "const monthInput=q('#monthValue');"
if needle in js and "monthInput.addEventListener('change'" not in js:
    js = js.replace(
        "q('#rangeEnd').min=q('#rangeStart').min;q('#rangeEnd').max=q('#rangeStart').max;q('#rangeEnd').value=dateKey(defaultRangeEnd);",
        "q('#rangeEnd').min=q('#rangeStart').min;q('#rangeEnd').max=q('#rangeStart').max;q('#rangeEnd').value=dateKey(defaultRangeEnd);monthInput.addEventListener('change',()=>{const s=q('#monthSearchStatus');if(s&&monthInput.value)s.textContent='Mês selecionado: '+monthLabel(monthInput.value)+'. Clique em Pesquisar agora para iniciar.';});"
    )

js_path.write_text(js, encoding='utf-8')

loader = loader_path.read_text(encoding='utf-8')
loader = re.sub(r"flight-explorer\.js\?v=[0-9-]+", "flight-explorer.js?v=20260912-12", loader)
loader_path.write_text(loader, encoding='utf-8')

# Bust do carregador principal, se index.html carregar terabyte-live.js diretamente.
index = index_path.read_text(encoding='utf-8')
index = re.sub(r"terabyte-live\.js(?:\?v=[^\"']+)?", "terabyte-live.js?v=20260912-12", index)
index_path.write_text(index, encoding='utf-8')
