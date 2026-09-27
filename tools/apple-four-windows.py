from pathlib import Path

p = Path('docs/apple-stock.js')
s = p.read_text()

def rep(old, new, count=1):
    global s
    if old not in s:
        raise SystemExit('Anchor not found:\n' + old[:220])
    s = s.replace(old, new, count)

rep("  const MAX_FIND_HISTORY = 80;\n", """  const MAX_FIND_HISTORY = 80;
  const REGIONAL_QUERY_DELAY = 15000;
  const REGIONAL_POINTS = {
    miami: { label: 'Miami', location: 'Miami, FL' },
    tampa: { label: 'Tampa', location: 'Tampa, FL' },
    orlando: { label: 'Orlando', location: 'Orlando, FL' },
    cape: { label: 'Cape Canaveral', location: 'Cape Canaveral, FL' }
  };
""")

rep("  const citySnapshots = new Map();\n", """  const citySnapshots = new Map();
  const pageParams = new URLSearchParams(location.search);
  const regionalKey = String(pageParams.get('appleRegion') || '').toLowerCase();
  const regionalPoint = REGIONAL_POINTS[regionalKey] || null;
  const regionalMode = !!regionalPoint;
  const regionalStartDelay = Math.max(0, Number(pageParams.get('startDelay') || 0));
""")

rep("  function queryDelay(){\n    if(discoveryMode)return DISCOVERY_DELAY;", """  function queryDelay(){
    if(regionalMode)return REGIONAL_QUERY_DELAY;
    if(discoveryMode)return DISCOVERY_DELAY;""")

rep("    .apple-note{margin-top:7px;padding:8px 10px;font-size:10px;line-height:1.4}\n", """    .apple-note{margin-top:7px;padding:8px 10px;font-size:10px;line-height:1.4}
    .apple-regional-window .main-tabs{display:none!important}
    .apple-regional-window #productsApp,.apple-regional-window #flightsApp,.apple-regional-window #indigoApp{display:none!important}
    .apple-regional-window .apple-history,.apple-regional-window .apple-note{display:none!important}
    .apple-regional-window .apple-head{position:sticky;top:0;z-index:4;background:var(--bg);padding:6px 0;margin:0 0 6px}
    .apple-regional-window .apple-head .sub{display:none}
    .apple-regional-window .apple-head h2{font-size:17px;margin:0}
    .apple-regional-window .apple-form{grid-template-columns:1fr 1fr;padding:8px;margin-bottom:6px}
    .apple-regional-window .apple-form .apple-field:first-child{grid-column:1/-1}
    .apple-regional-window .apple-actions{grid-column:1/-1}
    .apple-regional-window .apple-actions .sub{font-size:9px}
    .apple-regional-window .apple-summary{grid-template-columns:repeat(2,1fr);margin:6px 0}
    .apple-regional-window .apple-summary .card:nth-child(3),.apple-regional-window .apple-summary .card:nth-child(4){display:none}
    .apple-regional-window .apple-stores{grid-template-columns:1fr;padding:6px;gap:6px}
    .apple-regional-window .apple-store{min-height:92px;padding:9px}
""")

rep("      <div><h2>🍎 Monitor de estoque · ${TARGET_STORE_COUNT} Apple Stores na Flórida</h2><div class=\"sub\">Monitora retirada em loja do <b>${PRODUCT}</b>, somente <b>256GB Burgundy</b>, em todas as lojas do print, <b>exceto a nº 7 (St. Johns Town Center / Jacksonville)</b>. O modo rápido aprende quais pontos cobrem as mesmas ${TARGET_STORE_COUNT} lojas e reduz consultas redundantes.</div></div>", """      <div><h2>${regionalMode?`🍎 ${regionalPoint.label} · monitor dedicado`:`🍎 Monitor de estoque · ${TARGET_STORE_COUNT} Apple Stores na Flórida`}</h2><div class=\"sub\">${regionalMode?`Consulta exclusivamente o ponto <b>${regionalPoint.label}</b> para detectar o <b>${PRODUCT}</b> o mais rápido possível.`:`Monitora retirada em loja do <b>${PRODUCT}</b>, somente <b>256GB Burgundy</b>, em todas as lojas do print, <b>exceto a nº 7 (St. Johns Town Center / Jacksonville)</b>.`}</div></div>""")

rep("      <div class=\"apple-field\"><label>Lojas monitoradas</label><div class=\"apple-fixed\">${TARGET_STORE_COUNT} lojas · Flórida</div></div>", """      <div class=\"apple-field\"><label>${regionalMode?'Ponto dedicado':'Lojas monitoradas'}</label><div class=\"apple-fixed\">${regionalMode?regionalPoint.label:`${TARGET_STORE_COUNT} lojas · Flórida`}</div></div>""")

rep("        <button id=\"appleStart\" class=\"apple-start\">▶ Monitorar agora</button>", """        <button id=\"appleStart\" class=\"apple-start\">${regionalMode?`▶ Iniciar ${regionalPoint.label}`:'▶ Iniciar pesquisa · 4 janelas'}</button>""")

rep("        <span class=\"sub\" id=\"appleHint\">Modo rápido: mantém as 18 lojas, mas consulta apenas os pontos necessários para cobri-las.</span>", """        <span class=\"sub\" id=\"appleHint\">${regionalMode?`Janela dedicada a ${regionalPoint.label}: nova consulta a cada ${REGIONAL_QUERY_DELAY/1000}s, com desaceleração automática se a Apple limitar.`:'Abre Miami, Tampa, Orlando e Cape Canaveral em quatro janelas compactas lado a lado.'}</span>""")

rep("      const storesText=names.slice(0,2).join(' · ')+(names.length>2?' +'+(names.length-2):'');\n      return `<div class=\"apple-time-chip\"><b>${escapeHtml(fmtFound(item.ts))}</b><span>${escapeHtml(storesText||`${item.count||1} loja(s)`)}</span></div>`;", """      const storesText=names.slice(0,2).join(' · ')+(names.length>2?' +'+(names.length-2):'');
      const regions=Array.isArray(item.regions)?item.regions:[];
      const detail=[regions.join(' / '),storesText||`${item.count||1} loja(s)`].filter(Boolean).join(' · ');
      return `<div class=\"apple-time-chip\"><b>${escapeHtml(fmtFound(item.ts))}</b><span>${escapeHtml(detail)}</span></div>`;""")

rep("    const key=names.join('|');\n    const latest=findHistory[0];", """    const regions=[...new Set(stores.map(x=>String(x.search_area||(regionalPoint&&regionalPoint.label)||'').trim()).filter(Boolean))].sort();
    const key=regions.join('|')+'::'+names.join('|');
    const latest=findHistory[0];""")
rep("      const latestKey=(Array.isArray(latest.stores)?[...latest.stores].sort():[]).join('|');", """      const latestRegions=(Array.isArray(latest.regions)?[...latest.regions].sort():[]).join('|');
      const latestStores=(Array.isArray(latest.stores)?[...latest.stores].sort():[]).join('|');
      const latestKey=latestRegions+'::'+latestStores;""")
rep("    findHistory.unshift({ts,count:stores.length,stores:names});", "    findHistory.unshift({ts,count:stores.length,stores:names,regions});")

anchor = "  async function checkNow(){\n    if(!active)return;\n    if(document.hidden){setStatus('⏸ Monitor ativo, mas a aba está em segundo plano. Retomarei ao voltar para esta página.','warn');return;}\n"
insert = anchor + """

    if(regionalMode){
      const target=regionalPoint;
      setStatus(`🔎 ${target.label} · consultando estoque oficial da Apple…`,'live');
      try{
        const data=await jsonpAvailability(target.location,45000);
        if(!active)return;
        if(!data||data.ok!==true){
          if(data&&data.blocked){
            blockStreak+=1;
            const delay=blockStreak>=3?60000:blockStreak===2?30000:15000;
            setStatus(`⚠️ ${target.label}: Apple limitou consultas (HTTP ${data.http_status||'—'}). Nova tentativa em ${delay/1000}s.`,'warn');
            schedule(delay);return;
          }
          blockStreak=0;
          setStatus(`⚠️ ${target.label}: ${String(data&&data.error||'resposta não confirmada')}. Nova tentativa em 10s.`,'warn');
          schedule(10000);return;
        }
        blockStreak=0;
        const stores=(Array.isArray(data.stores)?data.stores:[]).map(x=>({...x,search_area:target.label,observed_at:data.checked_at}));
        render({...data,stores,stores_count:stores.length,available_count:stores.filter(x=>x.available===true).length});
        const n=stores.filter(x=>x.available===true).length;
        setStatus(n?`✅ ${target.label}: ${n} loja(s) disponível(is) agora.`:`⚡ ${target.label}: ${stores.length} loja(s) retornadas; nenhuma disponível agora. Próxima consulta em ${REGIONAL_QUERY_DELAY/1000}s.`,n?'ok':'live');
        schedule(REGIONAL_QUERY_DELAY);
      }catch(err){
        if(!active)return;
        setStatus(`⚠️ ${target.label}: ${String(err&&err.message||err)}. Tentarei novamente em 10s.`,'warn');
        schedule(10000);
      }
      return;
    }
"""
rep(anchor, insert)

start_anchor = "  async function start(){\n    if(active)return;\n"
start_insert = """  function openRegionalWindows(){
    const entries=Object.entries(REGIONAL_POINTS);
    const availW=Math.max(1200,screen.availWidth||window.innerWidth||1600);
    const availH=Math.max(650,screen.availHeight||window.innerHeight||850);
    const width=Math.max(300,Math.floor(availW/4));
    const top=screen.availTop||0;
    const baseLeft=screen.availLeft||0;
    let opened=0;
    entries.forEach(([key,point],index)=>{
      const u=new URL(location.href);
      u.searchParams.set('appleRegion',key);
      u.searchParams.set('autostart','1');
      u.searchParams.set('startDelay',String(index*3500));
      const left=baseLeft+(index*width);
      const features=`popup=yes,width=${width},height=${availH},left=${left},top=${top},resizable=yes,scrollbars=yes`;
      const w=window.open(u.toString(),`apple_${key}`,features);
      if(w)opened+=1;
    });
    if(opened<entries.length){
      setStatus(`⚠️ O navegador abriu ${opened}/${entries.length} janelas. Permita pop-ups para este site e clique novamente.`,'warn');
    }else{
      setStatus('✅ 4 monitores abertos: Miami · Tampa · Orlando · Cape Canaveral.','ok');
    }
  }

  async function start(){
    if(!regionalMode){openRegionalWindows();return;}
    if(active)return;
"""
rep(start_anchor, start_insert)

rep("    active=true;blockStreak=0;previousAvailable=new Set();locationIndex=0;discoveryIndex=0;steadyChecks=0;citySnapshots.clear();\n    activeLocations=restoreFastPlan();", """    active=true;blockStreak=0;previousAvailable=new Set();locationIndex=0;discoveryIndex=0;steadyChecks=0;citySnapshots.clear();
    if(regionalMode){
      qs('#appleStart').disabled=true;qs('#appleStop').disabled=false;
      qs('#appleFrequency').textContent=(REGIONAL_QUERY_DELAY/1000)+' segundos';
      setStatus(`▶ ${regionalPoint.label}: monitor dedicado iniciado. Primeira consulta agora.`,'live');
      checkNow();
      return;
    }
    activeLocations=restoreFastPlan();""")

rep("  document.addEventListener('visibilitychange',()=>{", """  window.addEventListener('storage',event=>{
    if(event.key===FIND_HISTORY_KEY){findHistory=loadFindHistory();renderFindHistory();}
  });

  document.addEventListener('visibilitychange',()=>{""")

rep("  renderFindHistory();\n  loadConfig();\n})();", """  renderFindHistory();
  loadConfig();
  if(regionalMode){
    document.body.classList.add('apple-regional-window');
    app.hidden=false;
    qs('#productsApp')&&(qs('#productsApp').hidden=true);
    qs('#flightsApp')&&(qs('#flightsApp').hidden=true);
    qs('#indigoApp')&&(qs('#indigoApp').hidden=true);
    document.title=`🍎 ${regionalPoint.label} · iPhone`;
    if(pageParams.get('autostart')==='1')setTimeout(()=>start(),regionalStartDelay);
  }
})();""")

p.write_text(s)
