from pathlib import Path
import json, re

# ---------------- Apple Apps Script backend ----------------
p = Path('apps-script/Apple.gs')
s = p.read_text(encoding='utf-8')

s = re.sub(
    r"const APPLE_PRODUCTS = \[\s*\{ storage: '256GB', part_number: 'MJW64LL/A', url: 'https://www\.apple\.com/shop/buy-iphone/iphone-18-pro/6\.9-inch-display-256gb-burgundy-unlocked' \}\s*\];",
    "const APPLE_PRODUCTS = [\n  { storage: '256GB', part_number: 'MJW64LL/A', url: 'https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-256gb-burgundy-unlocked' },\n  { storage: '512GB', part_number: 'MJWA4LL/A', url: 'https://www.apple.com/shop/buy-iphone/iphone-18-pro/6.9-inch-display-512gb-burgundy-unlocked' }\n];",
    s,
    count=1,
)

if 'function appleRequestedStorages_(params)' not in s:
    anchor = "function appleAvailability_(params) {"
    helper = """function appleRequestedStorages_(params) {
  const raw = String(params && (params.storages || params.storage) || '').trim();
  const all = APPLE_PRODUCTS.map(function(p) { return p.storage; });
  if (!raw) return all;
  const wanted = raw.split(',').map(function(v) { return String(v || '').trim().toUpperCase(); });
  const valid = all.filter(function(storage) { return wanted.indexOf(storage.toUpperCase()) >= 0; });
  return valid.length ? valid : all;
}

"""
    if anchor not in s:
        raise SystemExit('Apple.gs availability anchor not found')
    s = s.replace(anchor, helper + anchor, 1)

old = "  const location = appleSafeLocation_(params && params.location);\n  const configured = appleConfiguredProducts_();"
new = "  const location = appleSafeLocation_(params && params.location);\n  const requestedStorages = appleRequestedStorages_(params);\n  const configured = appleConfiguredProducts_().filter(function(p) { return requestedStorages.indexOf(p.storage) >= 0; });"
if old not in s:
    raise SystemExit('Apple.gs configured products anchor not found')
s = s.replace(old, new, 1)

old_exact = """      const identityText = [regular && regular.storePickupProductTitle, availability && availability.partNumber, product.storage, APPLE_PRODUCT_NAME].join(' ').toLowerCase();
      const exactVariant = identityText.indexOf('512gb') < 0 || (identityText.indexOf('burgundy') >= 0 && (identityText.indexOf('pro max') >= 0 || identityText.indexOf('iphone 18') >= 0));"""
new_exact = """      const titleText = String(regular && regular.storePickupProductTitle || '').toLowerCase();
      const wantedStorage = String(product.storage || '').toLowerCase();
      const exactVariant = !titleText || (
        titleText.indexOf(wantedStorage) >= 0 &&
        titleText.indexOf('burgundy') >= 0 &&
        (titleText.indexOf('pro max') >= 0 || titleText.indexOf('iphone 18') >= 0)
      );"""
if old_exact not in s:
    raise SystemExit('Apple.gs exact variant anchor not found')
s = s.replace(old_exact, new_exact, 1)

old_missing = "missing_variants: APPLE_PRODUCTS.filter(function(p) { return !configured.some(function(c) { return c.storage === p.storage; }); }).map(function(p) { return p.storage; }),"
new_missing = "missing_variants: APPLE_PRODUCTS.filter(function(p) { return requestedStorages.indexOf(p.storage) >= 0 && !configured.some(function(c) { return c.storage === p.storage; }); }).map(function(p) { return p.storage; }),"
if old_missing not in s:
    raise SystemExit('Apple.gs missing variants anchor not found')
s = s.replace(old_missing, new_missing, 1)

# Return physical store count separately from variant rows.
old_return = """  const availableStores = parsed.filter(function(store) { return store.available; });
  return {
"""
new_return = """  const availableStores = parsed.filter(function(store) { return store.available; });
  const physicalStoreKeys = {};
  parsed.forEach(function(store) { physicalStoreKeys[String(store.store_number || store.name || '')] = true; });
  return {
"""
if old_return not in s:
    raise SystemExit('Apple.gs return anchor not found')
s = s.replace(old_return, new_return, 1)
s = s.replace("    stores_count: parsed.length,", "    stores_count: Object.keys(physicalStoreKeys).length,\n    variant_rows_count: parsed.length,", 1)

p.write_text(s, encoding='utf-8')

# ---------------- Browser monitor frontend ----------------
p = Path('docs/apple-stock.js')
s = p.read_text(encoding='utf-8')

old_top = "  const PRODUCT = 'iPhone 18 Pro Max Burgundy · 256GB';"
new_top = """  const pageParams = new URLSearchParams(location.search);
  const SUPPORTED_STORAGES = ['256GB','512GB'];
  const requestedStorages = String(pageParams.get('storages') || '').split(',').map(x=>x.trim().toUpperCase()).filter(Boolean);
  const ACTIVE_STORAGES = SUPPORTED_STORAGES.filter(x=>!requestedStorages.length || requestedStorages.includes(x.toUpperCase()));
  const PRODUCT = `iPhone 18 Pro Max Burgundy · ${ACTIVE_STORAGES.join(' + ')}`;"""
if old_top not in s:
    raise SystemExit('apple-stock.js product anchor not found')
s = s.replace(old_top, new_top, 1)
# Remove later duplicate declaration.
s = s.replace("  const pageParams = new URLSearchParams(location.search);\n", "", 1)

# Keep query selection all the way to Apps Script.
old_src = "script.src=`${apiBase}?route=${encodeURIComponent('api/apple/availability')}&location=${encodeURIComponent(location)}&callback=${encodeURIComponent(cb)}&t=${Date.now()}`;"
new_src = "script.src=`${apiBase}?route=${encodeURIComponent('api/apple/availability')}&location=${encodeURIComponent(location)}&storages=${encodeURIComponent(ACTIVE_STORAGES.join(','))}&callback=${encodeURIComponent(cb)}&t=${Date.now()}`;"
if old_src not in s:
    raise SystemExit('apple-stock.js JSONP URL anchor not found')
s = s.replace(old_src, new_src, 1)

# Text labels.
s = s.replace("Monitora retirada em loja do <b>${PRODUCT}</b>, somente <b>256GB Burgundy</b>, em todas as lojas do print, <b>exceto a nº 7 (St. Johns Town Center / Jacksonville)</b>.", "Monitora retirada em loja do <b>${PRODUCT}</b>, com <b>256GB e 512GB Burgundy</b> pesquisados na mesma consulta, em todas as lojas do print, <b>exceto a nº 7 (St. Johns Town Center / Jacksonville)</b>.", 1)

# History should identify capacity.
old_names = "const names=[...new Set(stores.map(x=>String(x.name||'Apple Store')).filter(Boolean))].sort();"
new_names = "const names=[...new Set(stores.map(x=>[String(x.name||'Apple Store'),String(x.storage||'')].filter(Boolean).join(' · ')).filter(Boolean))].sort();"
if old_names not in s:
    raise SystemExit('apple-stock.js history names anchor not found')
s = s.replace(old_names, new_names, 1)

old_emit = "      postal_code:String(x.postal_code||''),\n      search_area:String(x.search_area||((regionalPoint&&regionalPoint.label)||''))"
new_emit = "      postal_code:String(x.postal_code||''),\n      storage:String(x.storage||''),\n      search_area:String(x.search_area||((regionalPoint&&regionalPoint.label)||''))"
if old_emit not in s:
    raise SystemExit('apple-stock.js desktop finding anchor not found')
s = s.replace(old_emit, new_emit, 1)

# Separate physical-store identity from variant identity.
old_key = "  function storeKey(x){return [String(x.store_number||x.name||''),String(x.storage||x.part_number||'')].join('|');}"
new_key = """  function storeIdentityKey(x){return String(x.store_number||x.name||'');}
  function storeKey(x){return [storeIdentityKey(x),String(x.storage||x.part_number||'')].join('|');}
  function uniqueStoreCount(stores){return new Set((stores||[]).map(storeIdentityKey).filter(Boolean)).size;}"""
if old_key not in s:
    raise SystemExit('apple-stock.js storeKey anchor not found')
s = s.replace(old_key, new_key, 1)
s = s.replace("const keys=new Set(snap.stores.map(storeKey));", "const keys=new Set(snap.stores.map(storeIdentityKey));", 1)

# Replace renderer with grouped physical-store cards while preserving variant alerts.
render_re = re.compile(r"  function render\(data\)\{.*?\n  \}\n\n  function setStatus", re.S)
new_render = r'''  function render(data){
    checks+=1;
    qs('#appleChecks').textContent=String(checks);
    qs('#appleUpdated').textContent=fmtTime(data.checked_at);
    const stores=Array.isArray(data.stores)?data.stores:[];
    const available=stores.filter(x=>x.available===true);
    qs('#appleStoreCount').textContent=String(uniqueStoreCount(stores));
    qs('#appleAvailableCount').textContent=String(uniqueStoreCount(available));

    const current=new Set(available.map(storeKey));
    const newly=available.filter(x=>!previousAvailable.has(storeKey(x)));
    if(newly.length){
      notifyNew(newly);
      recordFindings(newly,data.checked_at);
    }
    previousAvailable=current;

    const alert=qs('#appleAvailabilityAlert');
    if(available.length){
      alert.hidden=false;
      alert.innerHTML=`<b>✅ ESTOQUE ENCONTRADO!</b><span>${available.map(x=>`Apple ${escapeHtml(x.name)} · ${escapeHtml(x.storage||'')} · ${escapeHtml(x.distance_text||'')}`).join('<br>')}</span><br><a class="apple-buy" href="${APPLE_URL}" target="_blank" rel="noopener">Abrir página de compra ↗</a>`;
    }else{
      alert.hidden=true;alert.innerHTML='';
    }

    const box=qs('#appleStores');box.innerHTML='';
    qs('#appleEmpty').hidden=stores.length>0;
    const groups=new Map();
    for(const x of stores){
      const key=storeIdentityKey(x);
      if(!groups.has(key))groups.set(key,{base:x,variants:[]});
      groups.get(key).variants.push(x);
    }
    const ordered=[...groups.values()].sort((a,b)=>
      (Number(b.variants.some(x=>x.available))-Number(a.variants.some(x=>x.available)))||
      (Number(a.base.distance||9999)-Number(b.base.distance||9999))
    );
    for(const group of ordered){
      const x=group.base;
      const variants=[...group.variants].sort((a,b)=>String(a.storage||'').localeCompare(String(b.storage||''),undefined,{numeric:true}));
      const anyAvailable=variants.some(v=>v.available===true);
      const allKnown=variants.every(v=>v.pickup_display==='available'||v.pickup_display==='unavailable');
      const css=anyAvailable?'available':allKnown?'unavailable':'unknown';
      const lines=variants.map(v=>{
        const known=v.pickup_display==='available'||v.pickup_display==='unavailable';
        const label=v.available?'✅ DISPONÍVEL':known?'ESGOTADO':'⚠️ NÃO CONFIRMADO';
        return `<div class="state">${escapeHtml(v.storage||'')} · ${label}</div><div class="quote">${escapeHtml(v.quote||v.pickup_display||'Sem informação')}</div>`;
      }).join('');
      const div=document.createElement('div');div.className='apple-store '+css;
      div.innerHTML=`
        <div><h3>Apple ${escapeHtml(x.name||'Store')}</h3><div class="where">${escapeHtml([x.address,[x.city,x.state,x.postal_code].filter(Boolean).join(' ')].filter(Boolean).join(' · '))}</div>${x.distance_text?`<div class="distance">${escapeHtml(x.distance_text)}</div>`:''}</div>
        <div>${lines}</div>`;
      box.appendChild(div);
    }
  }

  function setStatus'''
s, n = render_re.subn(new_render, s, count=1)
if n != 1:
    raise SystemExit('apple-stock.js render function replacement failed')

# Regional mode physical-store status/count.
s = s.replace(
"""        const stores=(Array.isArray(data.stores)?data.stores:[]).map(x=>({...x,search_area:target.label,observed_at:data.checked_at}));
        render({...data,stores,stores_count:stores.length,available_count:stores.filter(x=>x.available===true).length});
        const n=stores.filter(x=>x.available===true).length;
        setStatus(n?`✅ ${target.label}: ${n} loja(s) disponível(is) agora.`:`⚡ ${target.label}: ${stores.length} loja(s) retornadas; nenhuma disponível agora. Próxima consulta em ${REGIONAL_QUERY_DELAY/1000}s.`,n?'ok':'live');""",
"""        const stores=(Array.isArray(data.stores)?data.stores:[]).map(x=>({...x,search_area:target.label,observed_at:data.checked_at}));
        const storeCount=uniqueStoreCount(stores);
        const availableRows=stores.filter(x=>x.available===true);
        const n=uniqueStoreCount(availableRows);
        render({...data,stores,stores_count:storeCount,available_count:n});
        setStatus(n?`✅ ${target.label}: ${n} loja(s) com 256GB e/ou 512GB disponível(is) agora.`:`⚡ ${target.label}: ${storeCount} loja(s) retornadas; 256GB/512GB indisponíveis agora. Próxima consulta em ${REGIONAL_QUERY_DELAY/1000}s.`,n?'ok':'live');""",
1)

# Non-regional physical-store coverage.
old_merge = """      const stores=mergeSnapshots();
      const available=stores.filter(x=>x.available===true);
      render({...data,stores,stores_count:stores.length,available_count:available.length,any_available:available.length>0});

      const missing=Array.isArray(data.missing_variants)?data.missing_variants:[];
      if(missing.length){
        setStatus('⚠️ Variante 256GB ainda sem SKU configurado no serviço.','warn');
        schedule(queryDelay());return;
      }

      const n=available.length;"""
new_merge = """      const stores=mergeSnapshots();
      const storeCount=uniqueStoreCount(stores);
      const available=stores.filter(x=>x.available===true);
      const n=uniqueStoreCount(available);
      render({...data,stores,stores_count:storeCount,available_count:n,any_available:available.length>0});

      const missing=Array.isArray(data.missing_variants)?data.missing_variants:[];
      if(missing.length){
        setStatus(`⚠️ Variante(s) ${missing.join(' + ')} ainda sem SKU configurado no serviço.`,'warn');
        schedule(queryDelay());return;
      }"""
if old_merge not in s:
    raise SystemExit('apple-stock.js merge/status anchor not found')
s = s.replace(old_merge, new_merge, 1)

# In the remainder of checkNow, all stores.length references are coverage counts.
check_start = s.index("      const stores=mergeSnapshots();")
check_end = s.index("  function openRegionalWindows(){", check_start)
chunk = s[check_start:check_end].replace('stores.length', 'storeCount')
s = s[:check_start] + chunk + s[check_end:]

# Pass selected capacities into newly opened regional windows.
old_open = "      u.searchParams.set('startDelay',String(index*3500));"
new_open = "      u.searchParams.set('startDelay',String(index*3500));\n      u.searchParams.set('storages',ACTIVE_STORAGES.join(','));"
if old_open not in s:
    raise SystemExit('apple-stock.js regional URL anchor not found')
s = s.replace(old_open, new_open, 1)

p.write_text(s, encoding='utf-8')

# ---------------- Desktop Electron shell ----------------
p = Path('desktop/index.html')
h = p.read_text(encoding='utf-8')

# Add select styling.
h = h.replace(
".interval{display:flex;align-items:center;gap:6px;font-size:12px;color:#9db0c9}.interval input{width:62px;background:#101c2e;color:#fff;border:1px solid #2a405e;border-radius:7px;padding:8px;font-weight:800}",
".interval,.storage{display:flex;align-items:center;gap:6px;font-size:12px;color:#9db0c9}.interval input{width:62px;background:#101c2e;color:#fff;border:1px solid #2a405e;border-radius:7px;padding:8px;font-weight:800}.storage select{background:#101c2e;color:#fff;border:1px solid #2a405e;border-radius:7px;padding:8px;font-weight:800}",
1)

old_topbar = '<div class="top"><div><div class="brand">🍎 Monitor Apple · iPhone 18 Pro Max Burgundy 256GB</div><div class="sub">Miami · Tampa · Orlando · Cape Canaveral</div></div><div class="spacer"></div><label class="soundbox">'
new_topbar = '<div class="top"><div><div class="brand" id="brand">🍎 Monitor Apple · iPhone 18 Pro Max Burgundy 256GB + 512GB</div><div class="sub">Miami · Tampa · Orlando · Cape Canaveral</div></div><div class="spacer"></div><label class="storage">Capacidade <select id="storageSelect"><option value="256GB,512GB" selected>256GB + 512GB</option><option value="256GB">256GB</option><option value="512GB">512GB</option></select></label><label class="soundbox">'
if old_topbar not in h:
    raise SystemExit('desktop topbar anchor not found')
h = h.replace(old_topbar, new_topbar, 1)

# JS bindings and prefs.
h = h.replace(
"const frames=[...document.querySelectorAll('iframe')],secs=document.getElementById('secs'),hist=document.getElementById('history'),volume=document.getElementById('volume'),volText=document.getElementById('volText');",
"const frames=[...document.querySelectorAll('iframe')],secs=document.getElementById('secs'),hist=document.getElementById('history'),volume=document.getElementById('volume'),volText=document.getElementById('volText'),storageSelect=document.getElementById('storageSelect'),brand=document.getElementById('brand');",
1)
h = h.replace(
"const HKEY='appleStockFindHistoryV1',DKEY='appleStockRegionalDelayMsV1',VKEY='appleStockAlertVolumeV1';let lastHist='';",
"const HKEY='appleStockFindHistoryV1',DKEY='appleStockRegionalDelayMsV1',VKEY='appleStockAlertVolumeV1',SKEY='appleStockStoragesV1';let lastHist='',running=false;",
1)
h = h.replace(
"function loadPrefs(){secs.value=String(Math.max(1,Math.round((Number(localStorage.getItem(DKEY))||15000)/1000)));volume.value=localStorage.getItem(VKEY)||'100';volText.textContent=volume.value+'%'}",
"function loadPrefs(){secs.value=String(Math.max(1,Math.round((Number(localStorage.getItem(DKEY))||15000)/1000)));volume.value=localStorage.getItem(VKEY)||'100';volText.textContent=volume.value+'%';storageSelect.value=localStorage.getItem(SKEY)||'256GB,512GB';updateBrand()}",
1)

# History preserves capacity.
h = h.replace(
"function rowKey(x){return String(x.store_number||x.store||x.name||x.location||'').trim().toLowerCase()}",
"function rowKey(x){return [String(x.store_number||x.store||x.name||x.location||'').trim().toLowerCase(),String(x.storage||'').toUpperCase()].join('|')}",
1)
h = h.replace(
"postal_code:x.postal_code||''}}",
"postal_code:x.postal_code||'',storage:x.storage||''}}",
1)
h = h.replace(
"d.textContent=[dt,x.region,store,x.city].filter(Boolean).join(' · ');",
"d.textContent=[dt,x.region,store,x.storage,x.city].filter(Boolean).join(' · ');",
1)
h = h.replace(
"postal_code:String(s.postal_code||'')})),{silent:true})}",
"postal_code:String(s.postal_code||''),storage:String(s.storage||'')})),{silent:true})}",
1)

# URL selection + live restart when capacity selection changes.
old_url = "function url(region,run,delay){return `https://thenights20.github.io/viagens/?appleRegion=${region}&embedded=1&autostart=${run?1:0}&startDelay=${delay}`}\nfunction startAll(){[0,1200,2400,3600].forEach((d,i)=>frames[i].src=url(frames[i].dataset.region,true,d))}function stopAll(){frames.forEach(f=>f.src=url(f.dataset.region,false,0))}"
new_url = "function updateBrand(){brand.textContent='🍎 Monitor Apple · iPhone 18 Pro Max Burgundy '+storageSelect.value.replace(',', ' + ')}\nfunction url(region,run,delay){return `https://thenights20.github.io/viagens/?appleRegion=${region}&embedded=1&autostart=${run?1:0}&startDelay=${delay}&storages=${encodeURIComponent(storageSelect.value)}`}\nfunction startAll(){running=true;[0,1200,2400,3600].forEach((d,i)=>frames[i].src=url(frames[i].dataset.region,true,d))}function stopAll(){running=false;frames.forEach(f=>f.src=url(f.dataset.region,false,0))}"
if old_url not in h:
    raise SystemExit('desktop URL/start anchor not found')
h = h.replace(old_url, new_url, 1)

h = h.replace(
"secs.oninput=()=>{const n=Math.max(1,Math.min(300,Number(secs.value)||15));localStorage.setItem(DKEY,String(Math.round(n*1000)))};volume.oninput=()=>{localStorage.setItem(VKEY,volume.value);volText.textContent=volume.value+'%'};",
"secs.oninput=()=>{const n=Math.max(1,Math.min(300,Number(secs.value)||15));localStorage.setItem(DKEY,String(Math.round(n*1000)))};volume.oninput=()=>{localStorage.setItem(VKEY,volume.value);volText.textContent=volume.value+'%'};storageSelect.onchange=()=>{localStorage.setItem(SKEY,storageSelect.value);updateBrand();if(running)startAll()};",
1)

p.write_text(h, encoding='utf-8')

# Bump desktop version to generate a new portable EXE.
p = Path('desktop/package.json')
pkg = json.loads(p.read_text(encoding='utf-8'))
pkg['version'] = '1.1.3'
pkg['description'] = 'Apple Stock Monitor - iPhone 18 Pro Max Burgundy 256GB/512GB, histórico centralizado e alerta sonoro'
p.write_text(json.dumps(pkg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print('Apple 256GB + 512GB monitor update prepared')
