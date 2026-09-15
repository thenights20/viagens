from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path, replacements):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    for label, old, new in replacements:
        if old not in s:
            raise SystemExit(f'{path}: patch point not found: {label}')
        s = s.replace(old, new, 1)
    p.write_text(s, encoding='utf-8')


patch('parking-indigo/search.mjs', [
    ('limits',
     "const CONFIRMATIONS_REQUIRED = 3;\n",
     "const CONFIRMATIONS_REQUIRED = 3;\nconst MAX_COMBINATIONS = 3000;\nconst MAX_DATE_DAYS = 7;\n"),
    ('date range helper',
     "function targetFor(products, filter) {\n",
     "function dateRange(fromDate,toDate) {\n  const start=new Date(fromDate+'T12:00:00Z'), end=new Date(toDate+'T12:00:00Z');\n  if(end<start) throw new Error('Data final precisa ser igual ou posterior à inicial.');\n  const out=[];\n  for(let d=new Date(start);d<=end;d.setUTCDate(d.getUTCDate()+1)) out.push(d.toISOString().slice(0,10));\n  return out;\n}\nfunction targetFor(products, filter) {\n"),
    ('best sort',
     "    (Number(a.price ?? Infinity)-Number(b.price ?? Infinity)) ||\n    String(a.entry_time).localeCompare(String(b.entry_time)) ||\n    String(a.exit_time).localeCompare(String(b.exit_time))\n",
     "    (Number(a.price ?? Infinity)-Number(b.price ?? Infinity)) ||\n    String(a.entry_date).localeCompare(String(b.entry_date)) ||\n    String(a.entry_time).localeCompare(String(b.entry_time)) ||\n    String(a.exit_date).localeCompare(String(b.exit_date)) ||\n    String(a.exit_time).localeCompare(String(b.exit_time))\n"),
    ('main dates',
     "  const entryDate=assertDate(env('INDIGO_ENTRY_DATE'), 'Data de entrada');\n  const exitDate=assertDate(env('INDIGO_EXIT_DATE'), 'Data de saída');\n",
     "  const entryDateFrom=assertDate(env('INDIGO_ENTRY_DATE_FROM',env('INDIGO_ENTRY_DATE')), 'Data inicial de entrada');\n  const entryDateTo=assertDate(env('INDIGO_ENTRY_DATE_TO',entryDateFrom), 'Data final de entrada');\n  const exitDateFrom=assertDate(env('INDIGO_EXIT_DATE_FROM',env('INDIGO_EXIT_DATE')), 'Data inicial de saída');\n  const exitDateTo=assertDate(env('INDIGO_EXIT_DATE_TO',exitDateFrom), 'Data final de saída');\n"),
    ('date validation',
     "  const entryDay=new Date(entryDate+'T12:00:00');\n  const exitDay=new Date(exitDate+'T12:00:00');\n  if (exitDay < entryDay) throw new Error('Data de saída precisa ser igual ou posterior à entrada.');\n\n  const entryTimes=slotTimes(entryFromTime,entryToTime,step);\n  const exitTimes=slotTimes(exitFromTime,exitToTime,step);\n  const combinations=[];\n  for (const entryTime of entryTimes) {\n    for (const exitTime of exitTimes) {\n      if (entryDate===exitDate && toMinutes(exitTime)<=toMinutes(entryTime)) continue;\n      combinations.push({entryTime,exitTime});\n    }\n  }\n  if (!combinations.length) throw new Error('Nenhuma combinação válida de entrada e saída.');\n  if (combinations.length>250) throw new Error(`A faixa gera ${combinations.length} combinações. Reduza as faixas ou use intervalo de 60 minutos (máximo 250).`);\n",
     "  const entryDates=dateRange(entryDateFrom,entryDateTo);\n  const exitDates=dateRange(exitDateFrom,exitDateTo);\n  if(entryDates.length>MAX_DATE_DAYS || exitDates.length>MAX_DATE_DAYS) throw new Error(`Cada faixa de datas pode ter no máximo ${MAX_DATE_DAYS} dias.`);\n  if(exitDateTo < entryDateFrom) throw new Error('A faixa de saída termina antes da faixa de entrada.');\n\n  const entryTimes=slotTimes(entryFromTime,entryToTime,step);\n  const exitTimes=slotTimes(exitFromTime,exitToTime,step);\n  const combinations=[];\n  for (const entryDate of entryDates) {\n    for (const entryTime of entryTimes) {\n      for (const exitDate of exitDates) {\n        for (const exitTime of exitTimes) {\n          if (`${exitDate}T${exitTime}` <= `${entryDate}T${entryTime}`) continue;\n          combinations.push({entryDate,entryTime,exitDate,exitTime});\n        }\n      }\n    }\n  }\n  if (!combinations.length) throw new Error('Nenhuma combinação válida de entrada e saída.');\n  if (combinations.length>MAX_COMBINATIONS) throw new Error(`A faixa gera ${combinations.length} combinações. O máximo por varredura é ${MAX_COMBINATIONS}. Reduza as datas ou os horários.`);\n"),
    ('query loop',
     "      const {entryTime,exitTime}=combinations[i];\n      const row=await verifyCombination(page,{entryDate,entryTime,exitDate,exitTime,product});\n",
     "      const {entryDate,entryTime,exitDate,exitTime}=combinations[i];\n      const row=await verifyCombination(page,{entryDate,entryTime,exitDate,exitTime,product});\n"),
    ('result sort',
     "  results.sort((a,b)=>String(a.entry_time).localeCompare(String(b.entry_time)) || String(a.exit_time).localeCompare(String(b.exit_time)));\n",
     "  results.sort((a,b)=>String(a.entry_date).localeCompare(String(b.entry_date)) || String(a.entry_time).localeCompare(String(b.entry_time)) || String(a.exit_date).localeCompare(String(b.exit_date)) || String(a.exit_time).localeCompare(String(b.exit_time)));\n"),
    ('payload version',
     "    version:'2.1.0',status:'completed',generated_at:new Date().toISOString(),started_at:startedAt,request_id:requestId,\n",
     "    version:'2.2.0',status:'completed',generated_at:new Date().toISOString(),started_at:startedAt,request_id:requestId,\n"),
    ('payload request stats',
     "    request:{entry_date:entryDate,exit_date:exitDate,entry_from_time:entryFromTime,entry_to_time:entryToTime,exit_from_time:exitFromTime,exit_to_time:exitToTime,step_minutes:step,product,from_time:entryFromTime,to_time:entryToTime,exit_time:exitFromTime},\n    stats:{\n      entry_times:entryTimes.length,exit_times:exitTimes.length,tested_combinations:results.length,\n",
     "    request:{entry_date_from:entryDateFrom,entry_date_to:entryDateTo,exit_date_from:exitDateFrom,exit_date_to:exitDateTo,entry_date:entryDateFrom,exit_date:exitDateFrom,entry_from_time:entryFromTime,entry_to_time:entryToTime,exit_from_time:exitFromTime,exit_to_time:exitToTime,step_minutes:step,product,from_time:entryFromTime,to_time:entryToTime,exit_time:exitFromTime},\n    stats:{\n      entry_days:entryDates.length,exit_days:exitDates.length,entry_times:entryTimes.length,exit_times:exitTimes.length,tested_combinations:results.length,\n"),
    ('best payload',
     "    best_combination:best?{entry_time:best.entry_time,exit_time:best.exit_time,price:best.price,currency:best.currency,product_name:best.product_name,confirmed:true}:null,\n",
     "    best_combination:best?{entry_date:best.entry_date,entry_time:best.entry_time,exit_date:best.exit_date,exit_time:best.exit_time,price:best.price,currency:best.currency,product_name:best.product_name,confirmed:true}:null,\n"),
    ('best log',
     "  if(best) console.log(`Melhor combinação confirmada: entrada ${best.entry_time}, saída ${best.exit_time}, preço ${best.price ?? 'n/d'}.`);\n",
     "  if(best) console.log(`Melhor combinação confirmada: entrada ${best.entry_date} ${best.entry_time}, saída ${best.exit_date} ${best.exit_time}, preço ${best.price ?? 'n/d'}.`);\n"),
    ('error version',
     "  const payload={version:'2.1.0',status:'error',generated_at:new Date().toISOString(),request_id:env('INDIGO_REQUEST_ID','manual'),error:String(err?.stack||err)};\n",
     "  const payload={version:'2.2.0',status:'error',generated_at:new Date().toISOString(),request_id:env('INDIGO_REQUEST_ID','manual'),error:String(err?.stack||err)};\n"),
])

patch('apps-script/Indigo.gs', [
    ('dispatch dates',
     "        entry_date: job.entry_date,\n        exit_date: job.exit_date,\n",
     "        entry_date_from: job.entry_date_from,\n        entry_date_to: job.entry_date_to,\n        exit_date_from: job.exit_date_from,\n        exit_date_to: job.exit_date_to,\n"),
    ('start dates',
     "  const entryDate = String(body.entry_date || '').trim();\n  const exitDate = String(body.exit_date || '').trim();\n",
     "  const entryDateFrom = String(body.entry_date_from || body.entry_date || '').trim();\n  const entryDateTo = String(body.entry_date_to || body.entry_date || entryDateFrom).trim();\n  const exitDateFrom = String(body.exit_date_from || body.exit_date || '').trim();\n  const exitDateTo = String(body.exit_date_to || body.exit_date || exitDateFrom).trim();\n"),
    ('date checks',
     "  if (!validDate_(entryDate) || !validDate_(exitDate)) throw new Error('Datas inválidas.');\n  if (exitDate < entryDate) throw new Error('A data de saída precisa ser igual ou posterior à entrada.');\n",
     "  if (![entryDateFrom,entryDateTo,exitDateFrom,exitDateTo].every(validDate_)) throw new Error('Datas inválidas.');\n  if (entryDateTo < entryDateFrom) throw new Error('A data final de entrada precisa ser igual ou posterior à inicial.');\n  if (exitDateTo < exitDateFrom) throw new Error('A data final de saída precisa ser igual ou posterior à inicial.');\n  if (exitDateTo < entryDateFrom) throw new Error('A faixa de saída termina antes da faixa de entrada.');\n"),
    ('estimate',
     "  const estimated = indigoSlotCount_(entryFromTime, entryToTime, step) * indigoSlotCount_(exitFromTime, exitToTime, step);\n  if (estimated > 250) throw new Error('Essa faixa gera ' + estimated + ' combinações. Reduza uma das faixas ou use intervalo de 60 minutos.');\n",
     "  const dayCount = function(a,b){ return Math.floor((new Date(b + 'T12:00:00Z').getTime() - new Date(a + 'T12:00:00Z').getTime()) / 86400000) + 1; };\n  const entryDays = dayCount(entryDateFrom, entryDateTo);\n  const exitDays = dayCount(exitDateFrom, exitDateTo);\n  if (entryDays > 7 || exitDays > 7) throw new Error('Cada faixa de datas pode ter no máximo 7 dias.');\n  const estimated = entryDays * exitDays * indigoSlotCount_(entryFromTime, entryToTime, step) * indigoSlotCount_(exitFromTime, exitToTime, step);\n  if (estimated > 3000) throw new Error('Essa faixa pode gerar até ' + estimated + ' combinações. O máximo por varredura é 3000. Reduza datas ou horários.');\n"),
    ('job dates',
     "    entry_date: entryDate,\n    exit_date: exitDate,\n",
     "    entry_date_from: entryDateFrom,\n    entry_date_to: entryDateTo,\n    exit_date_from: exitDateFrom,\n    exit_date_to: exitDateTo,\n"),
    ('result date compare',
     "    if (q.entry_date !== job.entry_date || q.exit_date !== job.exit_date) return null;\n",
     "    if (String(q.entry_date_from || q.entry_date || '') !== job.entry_date_from || String(q.entry_date_to || q.entry_date || '') !== job.entry_date_to) return null;\n    if (String(q.exit_date_from || q.exit_date || '') !== job.exit_date_from || String(q.exit_date_to || q.exit_date || '') !== job.exit_date_to) return null;\n"),
    ('job expiry',
     "  if (ageMs > 30 * 60 * 1000) {\n",
     "  if (ageMs > 60 * 60 * 1000) {\n"),
    ('job expiry text',
     "    return { job_id: jobId, status: 'error', error: 'A pesquisa Indigo excedeu 30 minutos.' };\n",
     "    return { job_id: jobId, status: 'error', error: 'A pesquisa Indigo excedeu 60 minutos.' };\n"),
])

patch('docs/indigo-parking.js', [
    ('form date ranges',
     "      <div class=\"indigo-field\"><label>Dia de entrada</label><input id=\"indigoEntryDate\" type=\"date\"></div>\n      <div class=\"indigo-field\"><label>Entrada a partir de</label><input id=\"indigoEntryFrom\" type=\"time\" step=\"1800\" value=\"12:00\"></div>\n      <div class=\"indigo-field\"><label>Entrada até</label><input id=\"indigoEntryTo\" type=\"time\" step=\"1800\" value=\"15:00\"></div>\n      <div class=\"indigo-field\"><label>Estacionamento</label><select id=\"indigoProduct\"><option value=\"terminal3_garage\" selected>T3 Edifício Garagem · coberto</option><option value=\"terminal3_flex\">T3 Flex</option><option value=\"terminal2_standard\">Terminal 2 Standard</option><option value=\"terminal1\">Terminal 1</option><option value=\"any\">Qualquer opção disponível</option></select></div>\n\n      <div class=\"indigo-field\"><label>Dia de saída</label><input id=\"indigoExitDate\" type=\"date\"></div>\n      <div class=\"indigo-field\"><label>Saída a partir de</label><input id=\"indigoExitFrom\" type=\"time\" step=\"1800\" value=\"06:00\"></div>\n      <div class=\"indigo-field\"><label>Saída até</label><input id=\"indigoExitTo\" type=\"time\" step=\"1800\" value=\"09:00\"></div>\n      <div class=\"indigo-field\"><label>Intervalo</label><select id=\"indigoStep\"><option value=\"30\" selected>30 minutos · Indigo</option><option value=\"60\">60 minutos · rápido</option></select></div>\n\n      <div class=\"indigo-field\"><label>Exibição</label><select id=\"indigoShow\"><option value=\"all\" selected>Todas as combinações</option><option value=\"available\">Só disponíveis</option></select></div>\n",
     "      <div class=\"indigo-field\"><label>Entrada · data inicial</label><input id=\"indigoEntryDateFrom\" type=\"date\"></div>\n      <div class=\"indigo-field\"><label>Entrada · data final</label><input id=\"indigoEntryDateTo\" type=\"date\"></div>\n      <div class=\"indigo-field\"><label>Entrada a partir de</label><input id=\"indigoEntryFrom\" type=\"time\" step=\"1800\" value=\"12:00\"></div>\n      <div class=\"indigo-field\"><label>Entrada até</label><input id=\"indigoEntryTo\" type=\"time\" step=\"1800\" value=\"15:00\"></div>\n\n      <div class=\"indigo-field\"><label>Saída · data inicial</label><input id=\"indigoExitDateFrom\" type=\"date\"></div>\n      <div class=\"indigo-field\"><label>Saída · data final</label><input id=\"indigoExitDateTo\" type=\"date\"></div>\n      <div class=\"indigo-field\"><label>Saída a partir de</label><input id=\"indigoExitFrom\" type=\"time\" step=\"1800\" value=\"06:00\"></div>\n      <div class=\"indigo-field\"><label>Saída até</label><input id=\"indigoExitTo\" type=\"time\" step=\"1800\" value=\"09:00\"></div>\n\n      <div class=\"indigo-field\"><label>Estacionamento</label><select id=\"indigoProduct\"><option value=\"terminal3_garage\" selected>T3 Edifício Garagem · coberto</option><option value=\"terminal3_flex\">T3 Flex</option><option value=\"terminal2_standard\">Terminal 2 Standard</option><option value=\"terminal1\">Terminal 1</option><option value=\"any\">Qualquer opção disponível</option></select></div>\n      <div class=\"indigo-field\"><label>Intervalo</label><select id=\"indigoStep\"><option value=\"30\" selected>30 minutos · recomendado</option><option value=\"60\">60 minutos · rápido</option></select></div>\n      <div class=\"indigo-field\"><label>Exibição</label><select id=\"indigoShow\"><option value=\"all\" selected>Todas as combinações</option><option value=\"available\">Só disponíveis</option></select></div>\n"),
    ('defaults',
     "  qs('#indigoEntryDate').value=localDate(1);\n  qs('#indigoExitDate').value=localDate(22);\n",
     "  qs('#indigoEntryDateFrom').value=localDate(1);\n  qs('#indigoEntryDateTo').value=localDate(1);\n  qs('#indigoExitDateFrom').value=localDate(22);\n  qs('#indigoExitDateTo').value=localDate(22);\n"),
    ('request estimator',
     "  function formRequest(){return{\n    entry_date:qs('#indigoEntryDate').value,\n    exit_date:qs('#indigoExitDate').value,\n    entry_from_time:qs('#indigoEntryFrom').value,\n    entry_to_time:qs('#indigoEntryTo').value,\n    exit_from_time:qs('#indigoExitFrom').value,\n    exit_to_time:qs('#indigoExitTo').value,\n    step_minutes:Number(qs('#indigoStep').value),\n    product:qs('#indigoProduct').value,\n    request_id:requestId()\n  };}\n  function estimated(r){return slots(r.entry_from_time,r.entry_to_time,r.step_minutes)*slots(r.exit_from_time,r.exit_to_time,r.step_minutes);}\n  function updateHint(){const r=formRequest(),n=estimated(r);qs('#indigoHint').innerHTML=n?`Serão testadas <strong>${n}</strong> combinações de entrada × saída.`:'Defina faixas válidas.';}\n  function validate(r){\n    if(!r.entry_date||!r.exit_date)return'Informe as datas de entrada e saída.';\n    if(r.exit_date<r.entry_date)return'A saída não pode ser antes da entrada.';\n",
     "  function dates(a,b){if(!a||!b||b<a)return[];const out=[];for(let d=new Date(a+'T12:00:00Z'),end=new Date(b+'T12:00:00Z');d<=end;d.setUTCDate(d.getUTCDate()+1))out.push(d.toISOString().slice(0,10));return out;}\n  function formRequest(){return{\n    entry_date_from:qs('#indigoEntryDateFrom').value,\n    entry_date_to:qs('#indigoEntryDateTo').value,\n    exit_date_from:qs('#indigoExitDateFrom').value,\n    exit_date_to:qs('#indigoExitDateTo').value,\n    entry_from_time:qs('#indigoEntryFrom').value,\n    entry_to_time:qs('#indigoEntryTo').value,\n    exit_from_time:qs('#indigoExitFrom').value,\n    exit_to_time:qs('#indigoExitTo').value,\n    step_minutes:Number(qs('#indigoStep').value),\n    product:qs('#indigoProduct').value,\n    request_id:requestId()\n  };}\n  function timeValues(a,b,step){const out=[];if(!a||!b||mins(b)<mins(a))return out;for(let m=mins(a);m<=mins(b);m+=step)out.push(`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`);return out;}\n  function estimated(r){const ed=dates(r.entry_date_from,r.entry_date_to),xd=dates(r.exit_date_from,r.exit_date_to),et=timeValues(r.entry_from_time,r.entry_to_time,r.step_minutes),xt=timeValues(r.exit_from_time,r.exit_to_time,r.step_minutes);let n=0;for(const a of ed)for(const at of et)for(const b of xd)for(const bt of xt)if(`${b}T${bt}`>`${a}T${at}`)n++;return n;}\n  function updateHint(){const r=formRequest(),n=estimated(r),ed=dates(r.entry_date_from,r.entry_date_to).length,xd=dates(r.exit_date_from,r.exit_date_to).length;qs('#indigoHint').innerHTML=n?`Serão testadas <strong>${n}</strong> combinações · ${ed} dia(s) de entrada × ${xd} dia(s) de saída.`:'Defina faixas válidas.';}\n  function validate(r){\n    if(!r.entry_date_from||!r.entry_date_to||!r.exit_date_from||!r.exit_date_to)return'Informe as quatro datas da faixa.';\n    if(r.entry_date_to<r.entry_date_from)return'A data final de entrada precisa ser igual ou posterior à inicial.';\n    if(r.exit_date_to<r.exit_date_from)return'A data final de saída precisa ser igual ou posterior à inicial.';\n    if(r.exit_date_to<r.entry_date_from)return'A faixa de saída termina antes da faixa de entrada.';\n    if(dates(r.entry_date_from,r.entry_date_to).length>7||dates(r.exit_date_from,r.exit_date_to).length>7)return'Cada faixa de datas pode ter no máximo 7 dias.';\n"),
    ('validation limit',
     "    const n=estimated(r);if(!n)return'Nenhuma combinação válida.';if(n>250)return`Essa faixa gera ${n} combinações. Reduza uma faixa ou use 60 minutos.`;\n",
     "    const n=estimated(r);if(!n)return'Nenhuma combinação válida.';if(n>3000)return`Essa faixa gera ${n} combinações. O máximo por varredura é 3.000; reduza datas ou horários.`;\n"),
    ('same request',
     "  function sameRequest(data,r){const q=data?.request||{};return data?.request_id===r.request_id&&q.entry_date===r.entry_date&&q.exit_date===r.exit_date&&String(q.entry_from_time||q.from_time||'')===r.entry_from_time&&String(q.entry_to_time||q.to_time||'')===r.entry_to_time&&String(q.exit_from_time||q.exit_time||'')===r.exit_from_time&&String(q.exit_to_time||q.exit_time||'')===r.exit_to_time&&Number(q.step_minutes)===Number(r.step_minutes)&&q.product===r.product;}\n",
     "  function sameRequest(data,r){const q=data?.request||{};return data?.request_id===r.request_id&&String(q.entry_date_from||q.entry_date||'')===r.entry_date_from&&String(q.entry_date_to||q.entry_date||'')===r.entry_date_to&&String(q.exit_date_from||q.exit_date||'')===r.exit_date_from&&String(q.exit_date_to||q.exit_date||'')===r.exit_date_to&&String(q.entry_from_time||q.from_time||'')===r.entry_from_time&&String(q.entry_to_time||q.to_time||'')===r.entry_to_time&&String(q.exit_from_time||q.exit_time||'')===r.exit_from_time&&String(q.exit_to_time||q.exit_time||'')===r.exit_to_time&&Number(q.step_minutes)===Number(r.step_minutes)&&q.product===r.product;}\n"),
    ('best fallback sort',
     "  function pickBest(data){if(data?.best_combination)return data.best_combination;return [...(data?.results||[])].filter(x=>x.available===true).sort((a,b)=>(Number(a.price??Infinity)-Number(b.price??Infinity))||String(a.entry_time).localeCompare(String(b.entry_time))||String(a.exit_time).localeCompare(String(b.exit_time)))[0]||null;}\n",
     "  function pickBest(data){if(data?.best_combination)return data.best_combination;return [...(data?.results||[])].filter(x=>x.available===true).sort((a,b)=>(Number(a.price??Infinity)-Number(b.price??Infinity))||String(a.entry_date).localeCompare(String(b.entry_date))||String(a.entry_time).localeCompare(String(b.entry_time))||String(a.exit_date).localeCompare(String(b.exit_date))||String(a.exit_time).localeCompare(String(b.exit_time)))[0]||null;}\n"),
    ('best summary',
     "    qs('#indigoBest').textContent=best?`${best.entry_time} → ${best.exit_time}`:'Nenhuma';\n",
     "    qs('#indigoBest').textContent=best?`${best.entry_date.slice(5).split('-').reverse().join('/')} ${best.entry_time} → ${best.exit_date.slice(5).split('-').reverse().join('/')} ${best.exit_time}`:'Nenhuma';\n"),
    ('best match',
     "      const div=document.createElement('div');const isBest=best&&x.available===true&&x.entry_time===best.entry_time&&x.exit_time===best.exit_time;const cls=x.available===true?'available':x.status==='error'?'error':'sold_out';const label=x.available===true?'DISPONÍVEL':x.status==='error'?'ERRO':x.status==='not_offered'?'NÃO OFERTADO':'ESGOTADO';\n",
     "      const div=document.createElement('div');const isBest=best&&x.available===true&&x.entry_date===best.entry_date&&x.entry_time===best.entry_time&&x.exit_date===best.exit_date&&x.exit_time===best.exit_time;const cls=x.available===true?'available':x.status==='error'?'error':'sold_out';const label=x.available===true?'DISPONÍVEL':x.status==='error'?'ERRO':x.status==='not_offered'?'NÃO OFERTADO':'ESGOTADO';\n"),
    ('slot dates',
     "      div.innerHTML=`<div>${isBest?'<div class=\"indigo-best\">★ MELHOR COMBINAÇÃO</div>':''}<div class=\"indigo-route-time\"><div><span class=\"indigo-time-label\">Entrada</span><strong>${String(x.entry_time||'—')}</strong></div><span class=\"indigo-arrow\">→</span><div><span class=\"indigo-time-label\">Saída</span><strong>${String(x.exit_time||'—')}</strong></div></div></div><div><div class=\"indigo-state\">${label}</div>${x.available===true&&money(x.price)?`<div class=\"indigo-price\">${money(x.price)}</div>`:''}<small>${x.available===true?'Essa combinação liberou vaga':'Combinação testada'}</small></div>`;\n",
     "      const ed=String(x.entry_date||'').slice(5).split('-').reverse().join('/'),xd=String(x.exit_date||'').slice(5).split('-').reverse().join('/');\n      div.innerHTML=`<div>${isBest?'<div class=\"indigo-best\">★ MELHOR COMBINAÇÃO</div>':''}<div class=\"indigo-route-time\"><div><span class=\"indigo-time-label\">Entrada · ${ed}</span><strong>${String(x.entry_time||'—')}</strong></div><span class=\"indigo-arrow\">→</span><div><span class=\"indigo-time-label\">Saída · ${xd}</span><strong>${String(x.exit_time||'—')}</strong></div></div></div><div><div class=\"indigo-state\">${label}</div>${x.available===true&&money(x.price)?`<div class=\"indigo-price\">${money(x.price)}</div>`:''}<small>${x.available===true?'Essa combinação liberou vaga':'Combinação testada'}</small></div>`;\n"),
    ('status best dates',
     "    status.textContent=available.length?`✅ ${available.length} combinação(ões) liberaram vaga. Melhor: entrada ${best.entry_time} · saída ${best.exit_time}${money(best.price)?' · '+money(best.price):''}.`:'Nenhuma combinação disponível nas faixas testadas. Amplie a entrada, a saída ou altere o dia.';\n",
     "    status.textContent=available.length?`✅ ${available.length} combinação(ões) liberaram vaga. Melhor: entrada ${best.entry_date} ${best.entry_time} · saída ${best.exit_date} ${best.exit_time}${money(best.price)?' · '+money(best.price):''}.`:'Nenhuma combinação disponível nas faixas testadas. Amplie as datas ou os horários.';\n"),
    ('poll timeout',
     "    const status=qs('#indigoStatus'),started=Date.now(),timeoutMs=15*60*1000;\n",
     "    const status=qs('#indigoStatus'),started=Date.now(),timeoutMs=45*60*1000;\n"),
    ('timeout text',
     "    throw new Error('A pesquisa excedeu 15 minutos. Tente reduzir as faixas e pesquisar novamente.');\n",
     "    throw new Error('A pesquisa excedeu 45 minutos. Tente reduzir as datas ou horários e pesquisar novamente.');\n"),
    ('date listeners',
     "  qs('#indigoSearchButton').addEventListener('click',search);qs('#indigoShow').addEventListener('change',()=>{if(lastData)render(lastData);});qs('#indigoEntryDate').addEventListener('change',()=>{if(qs('#indigoExitDate').value<qs('#indigoEntryDate').value)qs('#indigoExitDate').value=qs('#indigoEntryDate').value;});\n  ['indigoEntryFrom','indigoEntryTo','indigoExitFrom','indigoExitTo','indigoStep'].forEach(id=>qs('#'+id).addEventListener('change',updateHint));\n",
     "  qs('#indigoSearchButton').addEventListener('click',search);qs('#indigoShow').addEventListener('change',()=>{if(lastData)render(lastData);});\n  ['indigoEntryDateFrom','indigoEntryDateTo','indigoExitDateFrom','indigoExitDateTo','indigoEntryFrom','indigoEntryTo','indigoExitFrom','indigoExitTo','indigoStep'].forEach(id=>qs('#'+id).addEventListener('change',updateHint));\n"),
])

patch('docs/terabyte-live.js', [
    ('cache bust',
     "  s.src = './indigo-parking.js?v=20260914-2';\n",
     "  s.src = './indigo-parking.js?v=20260914-daterange-1';\n"),
])

print('Indigo date-range migration applied.')
