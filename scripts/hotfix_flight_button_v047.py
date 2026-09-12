from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js_path = ROOT / 'docs' / 'flight-explorer.js'
loader_path = ROOT / 'docs' / 'terabyte-live.js'

s = js_path.read_text(encoding='utf-8')

# Versão visível.
s = s.replace('Buscar passagens · v0.4.8', 'Buscar passagens · v0.4.9')

# O Apps Script que está efetivamente implantado aceita /api/search via pathInfo.
# A versão anterior da interface passou a enviar ?route=api/search, que depende de
# uma versão mais nova do Code.gs ainda não necessariamente implantada e fazia o
# clique parecer morto. Volta para a rota compatível com a implantação existente.
old_post = """  function postBridge(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    return fetch(`${apiBase}?route=${encodeURIComponent(path)}`,{method:'POST',mode:'no-cors',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(body)}).finally(()=>clearTimeout(timer));
  }
"""
new_post = """  function postBridge(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    let targetPath=path,payload=body;
    if(path==='api/cancel'){
      targetPath='api/search';
      payload={origin:'QZZ',destination:'QZX',month:(activeRequest&&activeRequest.month)||new Date().toISOString().slice(0,7),max_stops:2,request_id:'cancel_'+Date.now().toString(36)};
    }
    const url=`${apiBase}/${targetPath.replace(/^\\/+|\\/+$/g,'')}`;
    return fetch(url,{method:'POST',mode:'no-cors',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(payload)}).finally(()=>clearTimeout(timer));
  }
"""
if old_post not in s:
    raise SystemExit('função postBridge esperada não encontrada')
s = s.replace(old_post, new_post, 1)

# Não dependa do endpoint JSONP de progresso do Code.gs mais novo. O progresso
# real já é lido do arquivo live e do GitHub Actions público.
start = s.find('  function bridgeProgress(request){')
end = s.find('  async function loadSavedPairs()', start)
if start < 0 or end < 0:
    raise SystemExit('bloco bridgeProgress não encontrado')
s = s[:start] + "  async function bridgeProgress(request){return null;}\n" + s[end:]

# Verifique o Actions em frequência suficiente sem estourar a cota pública.
s = s.replace('if(Date.now()-lastActionsCheck>30000)', 'if(Date.now()-lastActionsCheck>20000)')

# Mensagem mais fiel logo após o clique.
s = s.replace("status.textContent='🔎 Enviando pesquisa. Os achados começarão a aparecer assim que forem encontrados.';", "status.textContent='🔎 Solicitação enviada. Aguardando o GitHub Actions iniciar a pesquisa.';")

js_path.write_text(s, encoding='utf-8')

loader = loader_path.read_text(encoding='utf-8')
loader = loader.replace('./flight-explorer.js?v=20260912-12', './flight-explorer.js?v=20260912-13')
loader_path.write_text(loader, encoding='utf-8')
