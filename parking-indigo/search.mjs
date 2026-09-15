import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright-core';

const LOCATION_ID = '99980448';
const BOOKING_URL = `https://indigoneo.com.br/pt/booking/${LOCATION_ID}`;
const OUTPUT_PATH = path.resolve('docs/data/indigo-parking-search.json');
const ALLOWED_PRODUCTS = new Set(['terminal3_garage','terminal3_flex','terminal2_standard','terminal1','any']);
const CONFIRMATIONS_REQUIRED = 3;
const MAX_COMBINATIONS = 3000;
const MAX_DATE_DAYS = 7;

function env(name, fallback='') { return String(process.env[name] ?? fallback).trim(); }
function assertDate(v, label) { if (!/^20\d\d-\d{2}-\d{2}$/.test(v) || Number.isNaN(Date.parse(v+'T12:00:00'))) throw new Error(`${label} inválida`); return v; }
function assertTime(v, label) { if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(v)) throw new Error(`${label} inválido`); return v; }
function toMinutes(v) { const [h,m]=v.split(':').map(Number); return h*60+m; }
function fromMinutes(v) { return `${String(Math.floor(v/60)).padStart(2,'0')}:${String(v%60).padStart(2,'0')}`; }
function indigoDate(date, time) { return `${date.replaceAll('-','/')} ${time}:0`; }
function normalize(s='') { return String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim(); }
function classifyProduct(name='') {
  const n=normalize(name);
  if (n.includes('terminal 3 edificio garagem')) return 'terminal3_garage';
  if (n.includes('terminal 3 flex')) return 'terminal3_flex';
  if (n.includes('terminal 2 standard')) return 'terminal2_standard';
  if (/terminal 1(?:\s|$)/.test(n)) return 'terminal1';
  if (n.includes('valet') && n.includes('t3')) return 'valet_t3';
  if (n.includes('valet') && n.includes('t2')) return 'valet_t2';
  return 'other';
}
function cleanRate(rate={}) {
  const icons=(rate.RateIcons||[]).map(x=>String(x?.Description||'').trim()).filter(Boolean);
  return {
    key: classifyProduct(rate.RateName),
    rate_id: String(rate.RateId ?? ''),
    name: String(rate.RateName || '').trim(),
    price: Number(rate.GrandTotalAmount ?? rate.Amount ?? 0) || null,
    currency: String(rate.CurrencyCode || 'BRL'),
    sold_out: Boolean(rate.SoldOut),
    covered: icons.some(x=>/coberto/i.test(x)),
    icons,
    description: String(rate.ShortDescription || '').trim(),
    image: String(rate.RateImage || ''),
    product_type: String(rate.ProductType || ''),
    from_iso: String(rate.FromDateISO || ''),
    to_iso: String(rate.ToDateISO || ''),
  };
}
function slotTimes(fromTime, toTime, step) {
  const start=toMinutes(fromTime), end=toMinutes(toTime);
  if (end < start) throw new Error('Horário final da faixa precisa ser igual ou posterior ao inicial.');
  const out=[];
  for(let m=start;m<=end;m+=step) out.push(fromMinutes(m));
  return out;
}
function dateRange(fromDate,toDate) {
  const start=new Date(fromDate+'T12:00:00Z'), end=new Date(toDate+'T12:00:00Z');
  if(end<start) throw new Error('Data final precisa ser igual ou posterior à inicial.');
  const out=[];
  for(let d=new Date(start);d<=end;d.setUTCDate(d.getUTCDate()+1)) out.push(d.toISOString().slice(0,10));
  return out;
}
function targetFor(products, filter) {
  const hourly=products.filter(x=>x.product_type !== 'MonthlyPass');
  if (filter === 'any') {
    return hourly.filter(x=>!x.sold_out && Number(x.price)>0).sort((a,b)=>(a.price??Infinity)-(b.price??Infinity))[0] || null;
  }
  return hourly.find(x=>x.key===filter) || null;
}
function alternativesFor(products) {
  return products.filter(x=>!x.sold_out && Number(x.price)>0).sort((a,b)=>(a.price??Infinity)-(b.price??Infinity)).map(x=>({key:x.key,name:x.name,price:x.price,covered:x.covered}));
}
function bestAvailable(rows) {
  return [...rows].filter(x=>x.available===true && x.confirmed===true).sort((a,b)=>
    (Number(a.price ?? Infinity)-Number(b.price ?? Infinity)) ||
    String(a.entry_date).localeCompare(String(b.entry_date)) ||
    String(a.entry_time).localeCompare(String(b.entry_time)) ||
    String(a.exit_date).localeCompare(String(b.exit_date)) ||
    String(a.exit_time).localeCompare(String(b.exit_time))
  )[0] || null;
}
function makeBody(entryDate,entryTime,exitDate,exitTime){
  return {
    Criteria:[{
      LotId:LOCATION_ID,
      ParkingBeginDateTime:indigoDate(entryDate,entryTime),
      ParkingEndDateTime:indigoDate(exitDate,exitTime),
      SalesChannelKey:'Web',
      CustomerFlowType:'RAD',
      ISOLangCode:'PT'
    }],
    SalesChannelKey:'Web',
    ISOLangCode:'PT'
  };
}
function parseResponse(text,product,entryDate,entryTime,exitDate,exitTime){
  const outer=JSON.parse(text);
  const decoded=typeof outer.d==='string'?JSON.parse(outer.d):outer.d;
  const root=Array.isArray(decoded)?decoded[0]:decoded;
  const products=(root?.DisplayRateList||[]).map(cleanRate).filter(x=>x.name && x.product_type!=='MonthlyPass');
  const target=targetFor(products,product);
  const base={
    entry_date:entryDate,entry_time:entryTime,exit_date:exitDate,exit_time:exitTime,
    product_key:product,product_name:target?.name||null,rate_id:target?.rate_id||null,
    price:target?.price??null,currency:'BRL',covered:Boolean(target?.covered),sold_out:target?target.sold_out:null,
    icons:target?.icons||[],description:target?.description||'',booking_url:BOOKING_URL,
    alternatives:alternativesFor(products),products
  };
  if(!target) return {...base,status:'not_offered',available:false};
  // Reproduce the visible Indigo rule conservatively: product must exist, not be SoldOut and have a real price.
  if(target.sold_out) return {...base,status:'sold_out',available:false};
  if(!(Number(target.price)>0)) return {...base,status:'unstable',available:false};
  return {...base,status:'available',available:true};
}
async function queryOnce(page,{entryDate,entryTime,exitDate,exitTime,product}){
  const body=makeBody(entryDate,entryTime,exitDate,exitTime);
  const raw=await page.evaluate(async body=>{
    try{
      const r=await fetch('/brApi/GetMultipleRates',{
        method:'POST',credentials:'include',cache:'no-store',
        headers:{'Content-Type':'application/json','Accept':'application/json, text/plain, */*','Cache-Control':'no-cache'},
        body:JSON.stringify(body)
      });
      return {status:r.status,text:await r.text()};
    }catch(e){return {status:0,error:String(e),text:''};}
  },body);
  if(raw.status!==200){
    return {entry_date:entryDate,entry_time:entryTime,exit_date:exitDate,exit_time:exitTime,status:'error',available:null,error:raw.error||`HTTP ${raw.status}`,booking_url:BOOKING_URL,products:[],alternatives:[]};
  }
  try{return parseResponse(raw.text,product,entryDate,entryTime,exitDate,exitTime);}
  catch(e){return {entry_date:entryDate,entry_time:entryTime,exit_date:exitDate,exit_time:exitTime,status:'error',available:null,error:`Resposta inválida: ${e}`,booking_url:BOOKING_URL,products:[],alternatives:[]};}
}
async function verifyCombination(page,args){
  const observations=[];
  const first=await queryOnce(page,args);
  observations.push(first.status);
  if(first.status!=='available') return {...first,confirmed:false,verification:{attempts:1,required:CONFIRMATIONS_REQUIRED,observations}};

  let latest=first;
  for(let attempt=2;attempt<=CONFIRMATIONS_REQUIRED;attempt++){
    await page.waitForTimeout(550);
    const check=await queryOnce(page,args);
    observations.push(check.status);
    latest=check;
    if(check.status!=='available'){
      return {
        ...first,
        status:'unstable',available:false,confirmed:false,
        price:null,
        verification:{attempts:attempt,required:CONFIRMATIONS_REQUIRED,observations},
        note:'A Indigo respondeu de forma diferente ao repetir a mesma combinação; não considerada disponível.'
      };
    }
  }
  return {
    ...latest,
    status:'available',available:true,confirmed:true,
    verification:{attempts:CONFIRMATIONS_REQUIRED,required:CONFIRMATIONS_REQUIRED,observations},
    note:`Disponibilidade confirmada ${CONFIRMATIONS_REQUIRED} vezes seguidas.`
  };
}

async function main() {
  const requestId=env('INDIGO_REQUEST_ID','manual').slice(0,80) || 'manual';
  const entryDateFrom=assertDate(env('INDIGO_ENTRY_DATE_FROM',env('INDIGO_ENTRY_DATE')), 'Data inicial de entrada');
  const entryDateTo=assertDate(env('INDIGO_ENTRY_DATE_TO',entryDateFrom), 'Data final de entrada');
  const exitDateFrom=assertDate(env('INDIGO_EXIT_DATE_FROM',env('INDIGO_EXIT_DATE')), 'Data inicial de saída');
  const exitDateTo=assertDate(env('INDIGO_EXIT_DATE_TO',exitDateFrom), 'Data final de saída');
  const entryFromTime=assertTime(env('INDIGO_ENTRY_FROM_TIME', env('INDIGO_FROM_TIME','06:00')), 'Horário inicial de entrada');
  const entryToTime=assertTime(env('INDIGO_ENTRY_TO_TIME', env('INDIGO_TO_TIME','18:00')), 'Horário final de entrada');
  const exitFromTime=assertTime(env('INDIGO_EXIT_FROM_TIME', env('INDIGO_EXIT_TIME','07:00')), 'Horário inicial de saída');
  const exitToTime=assertTime(env('INDIGO_EXIT_TO_TIME', env('INDIGO_EXIT_TIME','07:00')), 'Horário final de saída');
  const step=Number(env('INDIGO_STEP_MINUTES','30'));
  const product=env('INDIGO_PRODUCT','terminal3_garage');
  if (![30,60].includes(step)) throw new Error('Intervalo deve ser 30 ou 60 minutos.');
  if (!ALLOWED_PRODUCTS.has(product)) throw new Error('Produto Indigo inválido.');
  const entryDates=dateRange(entryDateFrom,entryDateTo);
  const exitDates=dateRange(exitDateFrom,exitDateTo);
  if(entryDates.length>MAX_DATE_DAYS || exitDates.length>MAX_DATE_DAYS) throw new Error(`Cada faixa de datas pode ter no máximo ${MAX_DATE_DAYS} dias.`);
  if(exitDateTo < entryDateFrom) throw new Error('A faixa de saída termina antes da faixa de entrada.');

  const entryTimes=slotTimes(entryFromTime,entryToTime,step);
  const exitTimes=slotTimes(exitFromTime,exitToTime,step);
  const combinations=[];
  for (const entryDate of entryDates) {
    for (const entryTime of entryTimes) {
      for (const exitDate of exitDates) {
        for (const exitTime of exitTimes) {
          if (`${exitDate}T${exitTime}` <= `${entryDate}T${entryTime}`) continue;
          combinations.push({entryDate,entryTime,exitDate,exitTime});
        }
      }
    }
  }
  if (!combinations.length) throw new Error('Nenhuma combinação válida de entrada e saída.');
  if (combinations.length>MAX_COMBINATIONS) throw new Error(`A faixa gera ${combinations.length} combinações. O máximo por varredura é ${MAX_COMBINATIONS}. Reduza as datas ou os horários.`);

  const startedAt=new Date().toISOString();
  const browser=await chromium.launch({
    headless:true,
    executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']
  });
  const context=await browser.newContext({
    locale:'pt-BR',timezoneId:'America/Sao_Paulo',
    userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36'
  });
  const page=await context.newPage();
  const results=[];
  try {
    const nav=await page.goto(BOOKING_URL,{waitUntil:'domcontentloaded',timeout:60000});
    if (!nav || nav.status()>=400) throw new Error(`Indigo respondeu HTTP ${nav?.status() ?? 'sem resposta'}`);
    await page.waitForFunction(()=>!document.title.toLowerCase().includes('just a moment'),null,{timeout:30000}).catch(()=>{});
    await page.waitForResponse(r=>r.url().includes('/brApi/GetLocationDataBind') && r.status()===200,{timeout:30000}).catch(()=>{});
    await page.waitForTimeout(2200);

    // Important: no parallel availability requests. Indigo can return inconsistent results when many combinations share the same browser session concurrently.
    for(let i=0;i<combinations.length;i++){
      const {entryDate,entryTime,exitDate,exitTime}=combinations[i];
      const row=await verifyCombination(page,{entryDate,entryTime,exitDate,exitTime,product});
      results.push(row);
      if(i+1<combinations.length) await page.waitForTimeout(180);
    }
  } finally {
    await browser.close();
  }

  results.sort((a,b)=>String(a.entry_date).localeCompare(String(b.entry_date)) || String(a.entry_time).localeCompare(String(b.entry_time)) || String(a.exit_date).localeCompare(String(b.exit_date)) || String(a.exit_time).localeCompare(String(b.exit_time)));
  const available=results.filter(x=>x.available===true && x.confirmed===true);
  const unstable=results.filter(x=>x.status==='unstable');
  const valid=results.filter(x=>x.status!=='error');
  const prices=available.map(x=>Number(x.price)).filter(x=>Number.isFinite(x)&&x>0);
  const best=bestAvailable(results);
  const payload={
    version:'2.2.0',status:'completed',generated_at:new Date().toISOString(),started_at:startedAt,request_id:requestId,
    reliability:{mode:'sequential-confirmed',confirmations_required:CONFIRMATIONS_REQUIRED,green_means:`produto presente, não esgotado, com preço, confirmado ${CONFIRMATIONS_REQUIRED} vezes seguidas`},
    location:{id:LOCATION_ID,name:'Aeroporto de Guarulhos (GRU)',booking_url:BOOKING_URL,timezone:'America/Sao_Paulo'},
    request:{entry_date_from:entryDateFrom,entry_date_to:entryDateTo,exit_date_from:exitDateFrom,exit_date_to:exitDateTo,entry_date:entryDateFrom,exit_date:exitDateFrom,entry_from_time:entryFromTime,entry_to_time:entryToTime,exit_from_time:exitFromTime,exit_to_time:exitToTime,step_minutes:step,product,from_time:entryFromTime,to_time:entryToTime,exit_time:exitFromTime},
    stats:{
      entry_days:entryDates.length,exit_days:exitDates.length,entry_times:entryTimes.length,exit_times:exitTimes.length,tested_combinations:results.length,
      available_combinations:available.length,unstable_combinations:unstable.length,
      unavailable_combinations:valid.length-available.length-unstable.length,error_combinations:results.length-valid.length,
      tested_times:results.length,available_times:available.length,lowest_price:prices.length?Math.min(...prices):null
    },
    best_combination:best?{entry_date:best.entry_date,entry_time:best.entry_time,exit_date:best.exit_date,exit_time:best.exit_time,price:best.price,currency:best.currency,product_name:best.product_name,confirmed:true}:null,
    results
  };
  await fs.mkdir(path.dirname(OUTPUT_PATH),{recursive:true});
  await fs.writeFile(OUTPUT_PATH,JSON.stringify(payload,null,2),'utf8');
  console.log(`Indigo GRU: ${available.length}/${results.length} combinações confirmadas para ${product}; ${unstable.length} instáveis descartadas.`);
  if(best) console.log(`Melhor combinação confirmada: entrada ${best.entry_date} ${best.entry_time}, saída ${best.exit_date} ${best.exit_time}, preço ${best.price ?? 'n/d'}.`);
}

main().catch(async err=>{
  const payload={version:'2.2.0',status:'error',generated_at:new Date().toISOString(),request_id:env('INDIGO_REQUEST_ID','manual'),error:String(err?.stack||err)};
  await fs.mkdir(path.dirname(OUTPUT_PATH),{recursive:true}).catch(()=>{});
  await fs.writeFile(OUTPUT_PATH,JSON.stringify(payload,null,2),'utf8').catch(()=>{});
  console.error(err);
  process.exitCode=1;
});
