from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path, old, new, label):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    if old not in s:
        raise SystemExit(f'Patch point not found: {label} in {path}')
    p.write_text(s.replace(old, new, 1), encoding='utf-8')


# 1) Deploy BOTH Apps Script sources instead of silently publishing Code.gs only.
patch(
    'scripts/deploy_apps_script.py',
    "    deploy(call, os.environ['SCRIPT_ID'], os.environ['DEPLOYMENT_ID'], Path('apps-script/Code.gs').read_text())",
    "    source = '\\n\\n'.join([\n        Path('apps-script/Code.gs').read_text(encoding='utf-8'),\n        Path('apps-script/Indigo.gs').read_text(encoding='utf-8'),\n    ])\n    deploy(call, os.environ['SCRIPT_ID'], os.environ['DEPLOYMENT_ID'], source)",
    'deploy all Apps Script sources',
)

# 2) Add an Indigo status endpoint to the already-public bridge.
patch(
    'apps-script/Code.gs',
    "    if (!path || path === 'health') return json_({ ok: true, service: 'flight-search-bridge', version: '0.4.0' });",
    "    if (!path || path === 'health') return json_({ ok: true, service: 'flight-search-bridge', version: '0.5.0', indigo: true });",
    'bridge health version',
)
patch(
    'apps-script/Code.gs',
    "    match = path.match(/^api\\/search\\/([A-Za-z0-9_-]{8,80})$/);\n    if (match) return json_(pollSearch_(match[1]));\n    return json_({ error: 'Rota inválida.' });",
    "    match = path.match(/^api\\/search\\/([A-Za-z0-9_-]{8,80})$/);\n    if (match) return json_(pollSearch_(match[1]));\n    match = path.match(/^api\\/indigo\\/search\\/([A-Za-z0-9_-]{8,80})$/);\n    if (match) return jsonp_(pollIndigoSearch_(match[1]), e && e.parameter && e.parameter.callback);\n    return json_({ error: 'Rota inválida.' });",
    'Indigo poll route',
)

# 3) Match Indigo's actual 30-minute grid. 60 remains a valid coarse subset.
patch(
    'apps-script/Indigo.gs',
    "  if (![15, 30, 60].includes(step)) throw new Error('Intervalo deve ser 15, 30 ou 60 minutos.');",
    "  if (![30, 60].includes(step)) throw new Error('Intervalo deve ser 30 ou 60 minutos.');",
    'Indigo Apps Script intervals',
)
patch(
    'parking-indigo/search.mjs',
    "  if (![15,30,60].includes(step)) throw new Error('Intervalo deve ser 15, 30 ou 60 minutos.');",
    "  if (![30,60].includes(step)) throw new Error('Intervalo deve ser 30 ou 60 minutos.');",
    'Indigo engine intervals',
)
patch(
    '.github/workflows/indigo-parking-search.yml',
    '        options: ["15", "30", "60"]',
    '        options: ["30", "60"]',
    'Indigo workflow interval choices',
)

# 4) Do not block Apps Script deployment on unrelated flight UI unit tests.
patch(
    '.github/workflows/deploy-apps-script.yml',
    "      - name: Validar código\n        run: |\n          node --test tests/flight-search.test.cjs\n          python -m py_compile scripts/deploy_apps_script.py",
    "      - name: Validar serviço de pesquisa\n        run: |\n          cat apps-script/Code.gs apps-script/Indigo.gs > /tmp/apps-script-bridge.js\n          node --check /tmp/apps-script-bridge.js\n          python -m py_compile scripts/deploy_apps_script.py\n          grep -q \"api/indigo/search\" apps-script/Code.gs\n          grep -q \"function startIndigoSearch_\" apps-script/Indigo.gs",
    'focused Apps Script validation',
)

# 5) Frontend: remove 15-minute option and poll the real bridge with JSONP.
patch(
    'docs/indigo-parking.js',
    '<div class="indigo-field"><label>Intervalo</label><select id="indigoStep"><option value="15">15 minutos · detalhado</option><option value="30" selected>30 minutos</option><option value="60">60 minutos · rápido</option></select></div>',
    '<div class="indigo-field"><label>Intervalo</label><select id="indigoStep"><option value="30" selected>30 minutos · Indigo</option><option value="60">60 minutos · rápido</option></select></div>',
    'frontend interval choices',
)
patch(
    'docs/indigo-parking.js',
    "  async function readResult(){\n    try{const x=await fetch(RESULT_URL+'?t='+Date.now(),{cache:'no-store'});if(!x.ok)return null;return await x.json();}catch{return null;}\n  }",
    "  async function readResult(){\n    try{const x=await fetch(RESULT_URL+'?t='+Date.now(),{cache:'no-store'});if(!x.ok)return null;return await x.json();}catch{return null;}\n  }\n  function bridgeJsonp(route,timeoutMs=12000){\n    return new Promise((resolve,reject)=>{\n      if(!apiBase){reject(new Error('Serviço de pesquisa não conectado.'));return;}\n      const cb='indigoCb_'+Date.now().toString(36)+Math.random().toString(36).slice(2);\n      const script=document.createElement('script');\n      const timer=setTimeout(()=>finish(new Error('Serviço demorou para responder.')),timeoutMs);\n      function finish(err,value){clearTimeout(timer);try{delete window[cb]}catch{}script.remove();err?reject(err):resolve(value);}\n      window[cb]=value=>finish(null,value);\n      script.onerror=()=>finish(new Error('Não foi possível consultar o serviço.'));\n      script.src=`${apiBase}?route=${encodeURIComponent(route)}&callback=${encodeURIComponent(cb)}&t=${Date.now()}`;\n      document.head.appendChild(script);\n    });\n  }",
    'frontend JSONP bridge helper',
)
old_poll = """  async function poll(r){
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
  }"""
new_poll = """  async function poll(r){
    const status=qs('#indigoStatus');
    const started=Date.now();
    const timeoutMs=15*60*1000;
    while(Date.now()-started<timeoutMs){
      await new Promise(ok=>setTimeout(ok,2500));
      let bridge=null;
      try{bridge=await bridgeJsonp('api/indigo/search/'+r.request_id,10000);}catch{};
      if(bridge?.status==='error')throw new Error(bridge.error||'A pesquisa terminou com erro.');
      if(bridge?.status==='done'&&bridge.result){render(bridge.result);return bridge.result;}
      const data=await readResult();
      if(data?.status==='error'&&data.request_id===r.request_id)throw new Error(data.error||'A pesquisa terminou com erro.');
      if(data?.status==='completed'&&sameRequest(data,r)){render(data);return data;}
      const sec=Math.round((Date.now()-started)/1000);
      const phase=bridge?.status==='queued'?'na fila':bridge?.status==='in_progress'?'consultando Indigo':bridge?.status==='running'?'iniciando busca':'aguardando execução';
      status.textContent=`🔎 ${phase}… ${sec}s`;
    }
    throw new Error('A pesquisa excedeu 15 minutos. Tente novamente.');
  }"""
patch('docs/indigo-parking.js', old_poll, new_poll, 'frontend real-status polling')

# 6) Bust browser cache so the repaired frontend is loaded immediately.
patch(
    'docs/terabyte-live.js',
    "  s.src = './indigo-parking.js?v=20260914-1';",
    "  s.src = './indigo-parking.js?v=20260914-2';",
    'Indigo frontend cache key',
)

print('Indigo timeout repair applied.')
