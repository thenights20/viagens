from pathlib import Path
import json
import re

# --- Web regional monitor: send history/events to the Electron parent ---
p = Path('docs/apple-stock.js')
s = p.read_text(encoding='utf-8')

if 'function emitDesktopFinding(stores,ts)' not in s:
    anchor = 'function recordFindings(stores,checkedAt){'
    idx = s.find(anchor)
    if idx < 0:
        raise SystemExit('recordFindings anchor not found')
    # Preserve indentation from the actual source.
    line_start = s.rfind('\n', 0, idx) + 1
    indent = s[line_start:idx]
    helper = f'''{indent}function emitDesktopMessage(payload){{
{indent}  if(pageParams.get('embedded')!=='1'||window.parent===window)return;
{indent}  try{{window.parent.postMessage(payload,'*');}}catch{{}}
{indent}}}

{indent}function emitDesktopFinding(stores,ts){{
{indent}  emitDesktopMessage({{
{indent}    type:'apple-stock-found',
{indent}    version:1,
{indent}    ts,
{indent}    region:(regionalPoint&&regionalPoint.label)||stores[0]?.search_area||'',
{indent}    stores:stores.map(x=>({{
{indent}      name:String(x.name||'Apple Store'),
{indent}      store_number:String(x.store_number||''),
{indent}      address:String(x.address||''),
{indent}      city:String(x.city||''),
{indent}      state:String(x.state||''),
{indent}      postal_code:String(x.postal_code||''),
{indent}      search_area:String(x.search_area||((regionalPoint&&regionalPoint.label)||''))
{indent}    }}))
{indent}  }});
{indent}}}

{indent}function emitDesktopHistorySnapshot(){{
{indent}  emitDesktopMessage({{
{indent}    type:'apple-history-snapshot',
{indent}    version:1,
{indent}    region:(regionalPoint&&regionalPoint.label)||'',
{indent}    history:Array.isArray(findHistory)?findHistory.slice(0,MAX_FIND_HISTORY):[]
{indent}  }});
{indent}}}

'''
    s = s[:line_start] + helper + s[line_start:]

if 'emitDesktopFinding(stores,ts);' not in s:
    # Insert after the history has been persisted/rendered inside recordFindings.
    m = re.search(r'(function recordFindings\(stores,checkedAt\)\{.*?saveFindHistory\(\);\s*renderFindHistory\(\);)', s, flags=re.S)
    if not m:
        raise SystemExit('recordFindings save/render block not found')
    block = m.group(1)
    block2 = block + '\n  emitDesktopFinding(stores,ts);'
    s = s[:m.start(1)] + block2 + s[m.end(1):]

if 'emitDesktopHistorySnapshot();\n  loadConfig();' not in s:
    anchor = '  renderFindHistory();\n  loadConfig();'
    if anchor not in s:
        raise SystemExit('startup history anchor not found')
    s = s.replace(anchor, '  renderFindHistory();\n  emitDesktopHistorySnapshot();\n  loadConfig();', 1)

p.write_text(s, encoding='utf-8')

# --- Electron shell: centralized persistent history ---
p = Path('desktop/index.html')
html = p.read_text(encoding='utf-8')

new_script = r'''<script>
const frames=[...document.querySelectorAll('iframe')],secs=document.getElementById('secs'),hist=document.getElementById('history'),volume=document.getElementById('volume'),volText=document.getElementById('volText');
const HKEY='appleStockFindHistoryV1',DKEY='appleStockRegionalDelayMsV1',VKEY='appleStockAlertVolumeV1';let lastHist='';
function loadPrefs(){secs.value=String(Math.max(1,Math.round((Number(localStorage.getItem(DKEY))||15000)/1000)));volume.value=localStorage.getItem(VKEY)||'100';volText.textContent=volume.value+'%'}
function loadHistory(){try{const a=JSON.parse(localStorage.getItem(HKEY)||'[]');return Array.isArray(a)?a:[]}catch{return[]}}
function saveHistory(a){try{localStorage.setItem(HKEY,JSON.stringify(a.slice(0,240)))}catch{}}
function alarm(){const C=window.AudioContext||window.webkitAudioContext,ctx=new C(),gain=ctx.createGain();gain.gain.value=Number(volume.value)/100;gain.connect(ctx.destination);const now=ctx.currentTime;[0,.32,.64,1.05,1.37,1.69].forEach((t,i)=>{const o=ctx.createOscillator(),g=ctx.createGain();o.type=i<3?'square':'sawtooth';o.frequency.value=i<3?880:1175;g.gain.setValueAtTime(.0001,now+t);g.gain.exponentialRampToValueAtTime(.9,now+t+.02);g.gain.exponentialRampToValueAtTime(.0001,now+t+.25);o.connect(g);g.connect(gain);o.start(now+t);o.stop(now+t+.28)});setTimeout(()=>ctx.close(),2400)}
function fmtDateTime(v){const n=Date.parse(v||'');if(!Number.isFinite(n))return String(v||'');return new Date(n).toLocaleString('pt-BR',{day:'2-digit',month:'2-digit',year:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'})}
function rowKey(x){return String(x.store_number||x.store||x.name||x.location||'').trim().toLowerCase()}
function normalizeRow(x={}){return{ts:x.ts||x.time||x.date||x.at||x.timestamp||'',region:x.region||x.search_area||'',store:x.store||x.location||x.name||'Apple Store',store_number:x.store_number||'',address:x.address||'',city:x.city||'',state:x.state||'',postal_code:x.postal_code||''}}
function expandHistory(a){const rows=[];a.forEach(x=>{if(Array.isArray(x?.stores)){const regs=Array.isArray(x.regions)?x.regions:[];x.stores.forEach(name=>rows.push(normalizeRow({ts:x.ts||x.time||x.date||'',region:regs.join(' / ')||x.region||'',store:String(name||'Apple Store')})))}else rows.push(normalizeRow(x||{}))});return rows}
function dedupeRows(rows){const out=[];rows.sort((a,b)=>(Date.parse(b.ts||0)||0)-(Date.parse(a.ts||0)||0)).forEach(item=>{const k=rowKey(item),t=Date.parse(item.ts||'');const dup=out.some(x=>rowKey(x)===k&&Number.isFinite(t)&&Number.isFinite(Date.parse(x.ts||''))&&Math.abs(t-Date.parse(x.ts||''))<120000);if(!dup)out.push(item)});return out.slice(0,240)}
function renderHistory(){const rows=dedupeRows(expandHistory(loadHistory()));const sig=JSON.stringify(rows.slice(0,3));if(lastHist&&sig!==lastHist&&rows.length)alarm();lastHist=sig;hist.innerHTML='';if(!rows.length){hist.innerHTML='<div class="empty">Nenhuma disponibilidade registrada ainda.</div>';return}rows.slice(0,120).forEach(x=>{const d=document.createElement('div');d.className='hit';const dt=fmtDateTime(x.ts);let store=String(x.store||'Apple Store');if(store&&!/^Apple\b/i.test(store))store='Apple '+store;d.textContent=[dt,x.region,store,x.city].filter(Boolean).join(' · ');d.title=[x.address,[x.city,x.state,x.postal_code].filter(Boolean).join(' ')].filter(Boolean).join(' · ');hist.appendChild(d)})}
function addRows(rows,{silent=false}={}){if(!Array.isArray(rows)||!rows.length)return;const before=dedupeRows(expandHistory(loadHistory()));const merged=dedupeRows([...rows.map(normalizeRow),...before]);if(JSON.stringify(merged)===JSON.stringify(before))return;saveHistory(merged);if(silent)lastHist=JSON.stringify(merged.slice(0,3));renderHistory()}
function acceptFinding(data){if(!data||data.type!=='apple-stock-found'||!Array.isArray(data.stores)||!data.stores.length)return;const ts=Date.parse(data.ts||'')?new Date(data.ts).toISOString():new Date().toISOString();const region=String(data.region||'');addRows(data.stores.map(s=>({ts,region:region||String(s.search_area||''),store:String(s.name||'Apple Store'),store_number:String(s.store_number||''),address:String(s.address||''),city:String(s.city||''),state:String(s.state||''),postal_code:String(s.postal_code||'')})),{silent:true})}
function acceptSnapshot(data){if(!data||data.type!=='apple-history-snapshot'||!Array.isArray(data.history)||!data.history.length)return;const rows=[];data.history.forEach(item=>{const ts=item.ts||item.time||item.date||'';const regs=Array.isArray(item.regions)&&item.regions.length?item.regions:[data.region||item.region||''];const region=regs.filter(Boolean).join(' / ');if(Array.isArray(item.stores)){item.stores.forEach(name=>rows.push({ts,region,store:String(name||'Apple Store')}))}else rows.push(normalizeRow({...item,region:region||item.region||''}))});addRows(rows,{silent:true})}
function url(region,run,delay){return `https://thenights20.github.io/viagens/?appleRegion=${region}&embedded=1&autostart=${run?1:0}&startDelay=${delay}`}
function startAll(){[0,1200,2400,3600].forEach((d,i)=>frames[i].src=url(frames[i].dataset.region,true,d))}function stopAll(){frames.forEach(f=>f.src=url(f.dataset.region,false,0))}
window.addEventListener('message',e=>{if(e.origin!=='https://thenights20.github.io')return;if(!frames.some(f=>f.contentWindow===e.source))return;if(e.data?.type==='apple-stock-found')acceptFinding(e.data);else if(e.data?.type==='apple-history-snapshot')acceptSnapshot(e.data)});
secs.oninput=()=>{const n=Math.max(1,Math.min(300,Number(secs.value)||15));localStorage.setItem(DKEY,String(Math.round(n*1000)))};volume.oninput=()=>{localStorage.setItem(VKEY,volume.value);volText.textContent=volume.value+'%'};document.getElementById('testSound').onclick=alarm;document.getElementById('start').onclick=startAll;document.getElementById('stop').onclick=stopAll;setInterval(renderHistory,1500);loadPrefs();renderHistory();
</script>'''

html2, n = re.subn(r'<script>.*?</script>', lambda m: new_script, html, count=1, flags=re.S)
if n != 1:
    raise SystemExit('desktop script block not found')
html2 = html2.replace('🕘 Histórico de disponibilidade · horário + local','🕘 Histórico de disponibilidade · data + horário + região + loja')
p.write_text(html2, encoding='utf-8')

# Bump portable app version.
p = Path('desktop/package.json')
pkg = json.loads(p.read_text(encoding='utf-8'))
pkg['version'] = '1.1.2'
pkg['description'] = 'Apple Stock Monitor - quatro regiões, histórico centralizado persistente e alerta sonoro'
p.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print('desktop Apple history fix prepared')
