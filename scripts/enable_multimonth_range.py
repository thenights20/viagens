from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js_path = ROOT / 'docs' / 'flight-explorer.js'
py_path = ROOT / 'flight-month-search' / 'search.py'
test_path = ROOT / 'tests' / 'flight-search.test.cjs'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f'Padrão não encontrado: {label}')
    return text.replace(old, new, 1)


# Front-end: intervalo pode atravessar meses e envia as datas reais ao Apps Script.
s = js_path.read_text(encoding='utf-8')
s = s.replace('Buscar passagens · v0.6.0', 'Buscar passagens · v0.6.1')
s = replace_once(
    s,
    "return{origin,destination,period_mode:'range',start_date:start,end_date:end,month,max_stops,dispatch_origin:encodeRangeOrigin(origin,start,end)};",
    "return{origin,destination,period_mode:'range',start_date:start,end_date:end,month,max_stops,dispatch_origin:origin};",
    'formRequest range',
)
s = replace_once(
    s,
    "if(request.start_date.slice(0,7)!==request.end_date.slice(0,7))return'O intervalo precisa ficar dentro do mesmo mês.';",
    "",
    'validação de mesmo mês',
)
s = replace_once(
    s,
    "postBridge('api/search',{origin:request.dispatch_origin,destination:request.destination,month:request.month,max_stops:request.max_stops,request_id:request.request_id}).catch(()=>{});",
    "postBridge('api/search',{origin:request.dispatch_origin,destination:request.destination,month:request.month,period_mode:request.period_mode,start_date:request.start_date,end_date:request.end_date,max_stops:request.max_stops,request_id:request.request_id}).catch(()=>{});",
    'payload de dispatch',
)
# O request_id é único; não dependa do texto do período no título do Actions.
s = replace_once(
    s,
    "return title.startsWith(`Busca ${request.request_id} ·`)&&title.includes(`${request.dispatch_origin} → ${request.destination}`)&&title.includes(request.month)",
    "return title.startsWith(`Busca ${request.request_id} ·`)&&title.includes(`${request.dispatch_origin} → ${request.destination}`)",
    'localização do workflow',
)
js_path.write_text(s, encoding='utf-8')

# Motor: aceita start/end explícitos de qualquer mês, mantendo compatibilidade com o hack antigo.
p = py_path.read_text(encoding='utf-8')
old = '''    origin, period_start, period_end, period_mode = decode_origin_and_period(raw_origin, month)\n\n    if len(origin) != 3 or len(destination) != 3 or not origin.isalpha() or not destination.isalpha():\n'''
new = '''    requested_mode = str(os.environ.get("SEARCH_PERIOD_MODE") or "month").strip().lower()\n    requested_start = str(os.environ.get("SEARCH_START_DATE") or "").strip()\n    requested_end = str(os.environ.get("SEARCH_END_DATE") or "").strip()\n\n    if requested_mode == "range" and requested_start and requested_end:\n        try:\n            period_start = date.fromisoformat(requested_start)\n            period_end = date.fromisoformat(requested_end)\n        except ValueError as exc:\n            raise SystemExit("Datas do intervalo inválidas") from exc\n        if period_end <= period_start:\n            raise SystemExit("A data final precisa ser posterior à data inicial")\n        origin = raw_origin\n        period_mode = "range"\n        month = period_start.strftime("%Y-%m")\n    else:\n        # Compatibilidade com chamadas antigas que codificavam um intervalo dentro da origem.\n        origin, period_start, period_end, period_mode = decode_origin_and_period(raw_origin, month)\n\n    if len(origin) != 3 or len(destination) != 3 or not origin.isalpha() or not destination.isalpha():\n'''
p = replace_once(p, old, new, 'período explícito no motor')
py_path.write_text(p, encoding='utf-8')

# Teste de regressão: faixa multi-mês deve ser aceita e enviada com as datas explícitas.
t = test_path.read_text(encoding='utf-8')
append = r'''

test('multi-month range is accepted and dispatched with explicit dates',()=>{
 const source=fs.readFileSync('docs/flight-explorer.js','utf8');
 const validateSource=source.slice(source.indexOf('  function validateRequest'),source.indexOf('  async function searchInsidePage'));
 const ctx=vm.createContext({});vm.runInContext(validateSource,ctx);
 const req={origin:'DOU',destination:'GRU',period_mode:'range',start_date:'2026-10-01',end_date:'2027-03-31',month:'2026-10',max_stops:2};
 assert.equal(ctx.validateRequest(req),'');
 const dispatchSource=source.slice(source.indexOf('  function dispatchWithoutCors'),source.indexOf('  async function stopSearch'));
 const calls=[];const dctx=vm.createContext({postBridge:(...args)=>{calls.push(args);return Promise.resolve()}});vm.runInContext(dispatchSource,dctx);
 req.dispatch_origin='DOU';req.request_id='web_multimonth';dctx.dispatchWithoutCors(req);
 assert.equal(calls[0][1].period_mode,'range');
 assert.equal(calls[0][1].start_date,'2026-10-01');
 assert.equal(calls[0][1].end_date,'2027-03-31');
});
'''
if 'multi-month range is accepted and dispatched with explicit dates' not in t:
    t += append
test_path.write_text(t, encoding='utf-8')
