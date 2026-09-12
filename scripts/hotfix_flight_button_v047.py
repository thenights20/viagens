from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js_path = ROOT / 'docs' / 'flight-explorer.js'
loader_path = ROOT / 'docs' / 'terabyte-live.js'

s = js_path.read_text(encoding='utf-8')

# Volta ao transporte que funcionou nas buscas de outubro/novembro/dezembro:
# Apps Script pela URL raiz + ?route=..., sem usar /exec/api/... .
s = s.replace('Buscar passagens · v0.4.9', 'Buscar passagens · v0.5.0')

old_post = """  function postBridge(path,body){
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
new_post = """  function postBridge(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    const url=`${apiBase}?route=${encodeURIComponent(path)}&t=${Date.now()}`;
    return fetch(url,{method:'POST',mode:'no-cors',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'text/plain;charset=UTF-8'},body:JSON.stringify(body)}).finally(()=>clearTimeout(timer));
  }
"""
if old_post not in s:
    raise SystemExit('postBridge atual não encontrado; abortando para não aplicar patch inseguro')
s = s.replace(old_post, new_post, 1)

old_progress = "  async function bridgeProgress(request){return null;}\n"
new_progress = """  function bridgeProgress(request){
    return new Promise(resolve=>{
      if(!apiBase){resolve(null);return;}
      const callback='flightProgress_'+String(request.request_id||'').replace(/[^A-Za-z0-9_$]/g,'_');
      const script=document.createElement('script');
      let finished=false;
      const finish=value=>{if(finished)return;finished=true;clearTimeout(timer);try{script.remove()}catch{};try{delete window[callback]}catch{};resolve(value)};
      const timer=setTimeout(()=>finish(null),8000);
      window[callback]=value=>finish(value);
      script.onerror=()=>finish(null);
      script.src=`${apiBase}?route=${encodeURIComponent(`api/progress/${request.request_id}`)}&callback=${encodeURIComponent(callback)}&t=${Date.now()}`;
      document.head.appendChild(script);
    });
  }
"""
if old_progress not in s:
    raise SystemExit('bridgeProgress atual não encontrado; abortando para não aplicar patch inseguro')
s = s.replace(old_progress, new_progress, 1)

# Mensagem inicial deixa claro que o envio foi feito; confirmação vem pelo JSONP/GitHub.
s = s.replace("status.textContent='🔎 Solicitação enviada. Aguardando o GitHub Actions iniciar a pesquisa.';", "status.textContent='🔎 Pesquisa enviada. Confirmando recebimento pelo serviço…';")

js_path.write_text(s, encoding='utf-8')

loader = loader_path.read_text(encoding='utf-8')
for old in [
    './flight-explorer.js?v=20260912-13',
    './flight-explorer.js?v=20260912-14',
]:
    loader = loader.replace(old, './flight-explorer.js?v=20260912-15')
loader_path.write_text(loader, encoding='utf-8')
