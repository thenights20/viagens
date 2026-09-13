from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AIRPORT_DATA = ROOT / "docs/data/airports-world.json"
FLIGHT_JS = ROOT / "docs/flight-explorer.js"
TERABYTE_JS = ROOT / "docs/terabyte-live.js"
INDEX_HTML = ROOT / "docs/index.html"
SOURCE_URL = "https://raw.githubusercontent.com/mwgg/Airports/master/airports.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Patch point not found: {label}")
    return text.replace(old, new, 1)


def build_airport_database() -> int:
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "viagens-airport-database/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        source = json.load(response)

    by_code: dict[str, dict] = {}
    for item in source.values():
        code = str(item.get("iata") or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", code):
            continue
        rec = {
            "code": code,
            "name": str(item.get("name") or "").strip(),
            "city": str(item.get("city") or "").strip(),
            "state": str(item.get("state") or "").strip(),
            "country": str(item.get("country") or "").strip().upper(),
        }
        old = by_code.get(code)
        if old is None or sum(bool(rec[k]) for k in ("city", "name", "state")) > sum(
            bool(old[k]) for k in ("city", "name", "state")
        ):
            by_code[code] = rec

    airports = sorted(
        by_code.values(),
        key=lambda x: (x["country"], x["city"].lower(), x["name"].lower(), x["code"]),
    )
    if len(airports) < 5000:
        raise SystemExit(f"Airport database unexpectedly small: {len(airports)}")

    AIRPORT_DATA.parent.mkdir(parents=True, exist_ok=True)
    AIRPORT_DATA.write_text(
        json.dumps(airports, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return len(airports)


def patch_flight_explorer() -> None:
    s = FLIGHT_JS.read_text(encoding="utf-8")

    s = replace_once(
        s,
        "  const ACTIONS_RUN = id => `https://api.github.com/repos/thenights20/viagens/actions/runs/${id}/jobs?per_page=10`;\n",
        "  const ACTIONS_RUN = id => `https://api.github.com/repos/thenights20/viagens/actions/runs/${id}/jobs?per_page=10`;\n  const AIRPORTS_WORLD = './data/airports-world.json';\n",
        "airport database constant",
    )

    s = replace_once(
        s,
        "  let resultView = 'calendar';\n",
        "  let resultView = 'calendar';\n  let worldAirports = [];\n  let worldAirportByCode = new Map();\n  let airportSuggestIndex = -1;\n",
        "airport state",
    )

    style_old = (
        "    .month-search-grid{display:grid;grid-template-columns:1.05fr 1.25fr .85fr 1.25fr .68fr auto;gap:7px;align-items:end;padding:9px}"
        ".month-search-grid label{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.07em;font-weight:800;margin:0 0 4px}"
        ".month-search-grid input,.month-search-grid select{padding:8px 9px;border-radius:9px;min-height:37px}\n"
    )
    style_new = style_old + (
        "    .dest-field{position:relative}.airport-suggest{position:absolute;z-index:80;left:0;right:0;top:calc(100% + 4px);max-height:330px;overflow:auto;"
        "background:var(--panel2);border:1px solid var(--line);border-radius:11px;box-shadow:0 18px 45px rgba(0,0,0,.42);padding:4px}"
        ".airport-suggest[hidden]{display:none}.airport-option{display:block;width:100%;border:0;background:transparent;color:var(--text);text-align:left;padding:8px 9px;"
        "border-radius:8px;cursor:pointer}.airport-option:hover,.airport-option.active{background:rgba(119,167,255,.13)}.airport-option b{display:block;font-size:12px}"
        ".airport-option small{display:block;color:var(--muted);font-size:10px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".airport-loading{padding:9px;color:var(--muted);font-size:10px}\n"
    )
    s = replace_once(s, style_old, style_new, "airport autocomplete styles")

    s = replace_once(
        s,
        '<div class="dest-field"><label>Destino</label><input id="monthDestination" list="monthDestinations" placeholder="Ex.: Miami ou MIA"><datalist id="monthDestinations"></datalist></div>',
        '<div class="dest-field"><label>Destino</label><input id="monthDestination" placeholder="Digite cidade, aeroporto ou IATA..." autocomplete="off" spellcheck="false"><div id="monthAirportSuggest" class="airport-suggest" hidden></div></div>',
        "destination input",
    )

    s = replace_once(
        s,
        "  q('#monthDestinations').innerHTML=DESTINATIONS.map(([c,n])=>`<option value=\"${esc(n)}\">${c}</option><option value=\"${c}\">${esc(n)}</option>`).join('');\n",
        "  setupAirportAutocomplete();\n",
        "old datalist initialization",
    )

    old_resolve = "  function resolveDestination(raw){const value=String(raw||'').trim();if(/^[a-z]{3}$/i.test(value))return value.toUpperCase();const n=norm(value);const exact=DESTINATIONS.find(([c,name])=>norm(name)===n||norm(`${name} (${c})`)===n);if(exact)return exact[0];const partial=DESTINATIONS.filter(([c,name])=>norm(name).includes(n)||norm(c)===n);return partial.length===1?partial[0][0]:'';}\n"
    new_block = r'''  function fallbackAirports(){return DESTINATIONS.map(([code,name])=>({code,name,city:name,state:'',country:''}));}
  function setWorldAirports(list){
    const seen=new Set(),clean=[];
    for(const raw of (Array.isArray(list)?list:[])){
      const code=String(raw.code||raw.iata||'').trim().toUpperCase();
      if(!/^[A-Z]{3}$/.test(code)||seen.has(code))continue;
      seen.add(code);clean.push({code,name:String(raw.name||'').trim(),city:String(raw.city||'').trim(),state:String(raw.state||'').trim(),country:String(raw.country||'').trim().toUpperCase()});
    }
    worldAirports=clean.length?clean:fallbackAirports();worldAirportByCode=new Map(worldAirports.map(a=>[a.code,a]));
  }
  function airportDisplay(a){
    const place=a.city||a.name||a.code,name=a.name&&norm(a.name)!==norm(place)?` — ${a.name}`:'',where=[a.state,a.country].filter(Boolean).join(', ');
    return `${place}${name}${where?` · ${where}`:''} (${a.code})`;
  }
  function airportMatches(term){
    const n=norm(term);if(!n)return[];const source=worldAirports.length?worldAirports:fallbackAirports();
    return source.map(a=>{const c=norm(a.code),city=norm(a.city),name=norm(a.name),state=norm(a.state),country=norm(a.country),hay=`${c} ${city} ${name} ${state} ${country}`;let score=99;if(c===n)score=0;else if(c.startsWith(n))score=1;else if(city===n)score=2;else if(city.startsWith(n))score=3;else if(name.startsWith(n))score=4;else if(state.startsWith(n)||country===n)score=5;else if(hay.includes(n))score=6;return{a,score};}).filter(x=>x.score<99).sort((x,y)=>x.score-y.score||String(x.a.city||x.a.name).localeCompare(String(y.a.city||y.a.name),'pt-BR')).slice(0,12).map(x=>x.a);
  }
  function hideAirportSuggestions(){const box=q('#monthAirportSuggest');if(box){box.hidden=true;box.innerHTML='';}airportSuggestIndex=-1;}
  function chooseAirport(a){const input=q('#monthDestination');if(!input)return;input.value=airportDisplay(a);input.dataset.iata=a.code;hideAirportSuggestions();}
  function renderAirportSuggestions(term){
    const box=q('#monthAirportSuggest');if(!box)return;const matches=airportMatches(term);airportSuggestIndex=-1;
    if(!String(term||'').trim()){hideAirportSuggestions();return;}
    if(!matches.length){box.innerHTML='<div class="airport-loading">Nenhum aeroporto encontrado. Você também pode informar diretamente um código IATA de 3 letras.</div>';box.hidden=false;return;}
    box.innerHTML=matches.map((a,i)=>`<button type="button" class="airport-option" data-airport-index="${i}" data-airport-code="${esc(a.code)}"><b>${esc(a.code)} · ${esc(a.city||a.name||a.code)}</b><small>${esc([a.name,a.state,a.country].filter(Boolean).join(' · '))}</small></button>`).join('');box.hidden=false;
    box.querySelectorAll('.airport-option').forEach((el,i)=>el.addEventListener('pointerdown',e=>{e.preventDefault();chooseAirport(matches[i]);}));
  }
  async function loadWorldAirports(){
    setWorldAirports(fallbackAirports());const input=q('#monthDestination');if(input)input.title='Carregando base mundial de aeroportos…';
    try{const r=await fetch(AIRPORTS_WORLD,{cache:'force-cache'});if(!r.ok)throw new Error(`HTTP ${r.status}`);const list=await r.json();if(!Array.isArray(list)||list.length<5000)throw new Error('base incompleta');setWorldAirports(list);if(input)input.title=`Base mundial carregada: ${worldAirports.length.toLocaleString('pt-BR')} aeroportos com IATA`;}catch(e){if(input)input.title='Base mundial indisponível; usando lista principal de aeroportos.';console.warn('airport-database',e);}
  }
  function setupAirportAutocomplete(){
    const input=q('#monthDestination'),box=q('#monthAirportSuggest');if(!input||!box)return;setWorldAirports(fallbackAirports());loadWorldAirports();
    input.addEventListener('input',()=>{input.dataset.iata='';renderAirportSuggestions(input.value);});
    input.addEventListener('focus',()=>{if(input.value.trim())renderAirportSuggestions(input.value);});
    input.addEventListener('blur',()=>setTimeout(hideAirportSuggestions,140));
    input.addEventListener('keydown',e=>{const opts=[...box.querySelectorAll('.airport-option')];if(e.key==='Escape'){hideAirportSuggestions();return;}if(!opts.length)return;if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();airportSuggestIndex=e.key==='ArrowDown'?Math.min(opts.length-1,airportSuggestIndex+1):Math.max(0,airportSuggestIndex<0?opts.length-1:airportSuggestIndex-1);opts.forEach((o,i)=>o.classList.toggle('active',i===airportSuggestIndex));opts[airportSuggestIndex]?.scrollIntoView({block:'nearest'});return;}if(e.key==='Enter'&&airportSuggestIndex>=0){e.preventDefault();const code=opts[airportSuggestIndex]?.dataset.airportCode,a=worldAirportByCode.get(code);if(a)chooseAirport(a);}});
  }
  function resolveDestination(raw){const input=q('#monthDestination'),selected=String(input?.dataset?.iata||'').toUpperCase();if(/^[A-Z]{3}$/.test(selected))return selected;const value=String(raw||'').trim();if(/^[a-z]{3}$/i.test(value))return value.toUpperCase();const suffix=value.match(/\(([A-Z]{3})\)\s*$/i);if(suffix)return suffix[1].toUpperCase();const n=norm(value);const legacy=DESTINATIONS.find(([c,name])=>norm(name)===n||norm(`${name} (${c})`)===n);if(legacy)return legacy[0];const exact=(worldAirports.length?worldAirports:fallbackAirports()).filter(a=>norm(a.city)===n||norm(a.name)===n||norm(airportDisplay(a))===n);return exact.length===1?exact[0].code:'';}
'''
    s = replace_once(s, old_resolve, new_block, "resolveDestination")

    s = replace_once(
        s,
        "  function airportName(code){return [...ORIGINS,...DESTINATIONS].find(x=>x[0]===code)?.[1]||code||'—'}\n",
        "  function airportName(code){const world=worldAirportByCode.get(String(code||'').toUpperCase());return (world&&(world.city||world.name))||[...ORIGINS,...DESTINATIONS].find(x=>x[0]===code)?.[1]||code||'—'}\n",
        "airport name lookup",
    )

    if "🔎 Buscar passagens · v0.6.1" in s:
        s = s.replace("🔎 Buscar passagens · v0.6.1", "🔎 Buscar passagens · v0.6.2", 1)
    elif "🔎 Buscar passagens · v0.6.2" not in s:
        raise SystemExit("Version marker not found")

    FLIGHT_JS.write_text(s, encoding="utf-8")


def bust_cache() -> None:
    s = TERABYTE_JS.read_text(encoding="utf-8")
    old = "./flight-explorer.js?v=20260912-audit-1"
    new = "./flight-explorer.js?v=20260913-airports-1"
    if old in s:
        s = s.replace(old, new, 1)
    elif new not in s:
        raise SystemExit("flight-explorer cache key not found")
    TERABYTE_JS.write_text(s, encoding="utf-8")

    s = INDEX_HTML.read_text(encoding="utf-8")
    old = "./terabyte-live.js?v=20260912-audit-1"
    new = "./terabyte-live.js?v=20260913-airports-1"
    if old in s:
        s = s.replace(old, new, 1)
    INDEX_HTML.write_text(s, encoding="utf-8")


def validate(count: int) -> None:
    airports = json.loads(AIRPORT_DATA.read_text(encoding="utf-8"))
    assert len(airports) == count and count >= 5000
    codes = {a["code"] for a in airports}
    for code in ("MIA", "LHR", "CDG", "HND", "NRT", "DXB", "SYD", "JNB", "BKK", "SIN", "AKL"):
        assert code in codes, code
    js = FLIGHT_JS.read_text(encoding="utf-8")
    assert "airport-suggest" in js
    assert "AIRPORTS_WORLD" in js
    assert "v0.6.2" in js
    assert "monthDestinations" not in js


def main() -> None:
    count = build_airport_database()
    patch_flight_explorer()
    bust_cache()
    validate(count)
    print(f"Autocomplete mundial preparado: {count} aeroportos IATA; {AIRPORT_DATA.stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
