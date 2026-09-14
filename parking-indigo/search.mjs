import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright-core';

const LOCATION_ID = '99980448';
const BOOKING_URL = `https://indigoneo.com.br/pt/booking/${LOCATION_ID}`;
const OUTPUT_PATH = path.resolve('docs/data/indigo-parking-search.json');
const ALLOWED_PRODUCTS = new Set(['terminal3_garage','terminal3_flex','terminal2_standard','terminal1','any']);

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
    available: !Boolean(rate.SoldOut),
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
function targetFor(products, filter) {
  const hourly=products.filter(x=>x.product_type !== 'MonthlyPass');
  if (filter === 'any') return hourly.filter(x=>x.available).sort((a,b)=>(a.price??Infinity)-(b.price??Infinity))[0] || null;
  return hourly.find(x=>x.key===filter) || null;
}
function bestAvailable(rows) {
  return [...rows].filter(x=>x.available===true).sort((a,b)=>
    (Number(a.price ?? Infinity)-Number(b.price ?? Infinity)) ||
    String(a.entry_time).localeCompare(String(b.entry_time)) ||
    String(a.exit_time).localeCompare(String(b.exit_time))
  )[0] || null;
}

async function main() {
  const requestId=env('INDIGO_REQUEST_ID','manual').slice(0,80) || 'manual';
  const entryDate=assertDate(env('INDIGO_ENTRY_DATE'), 'Data de entrada');
  const exitDate=assertDate(env('INDIGO_EXIT_DATE'), 'Data de saída');
  const entryFromTime=assertTime(env('INDIGO_ENTRY_FROM_TIME', env('INDIGO_FROM_TIME','06:00')), 'Horário inicial de entrada');
  const entryToTime=assertTime(env('INDIGO_ENTRY_TO_TIME', env('INDIGO_TO_TIME','18:00')), 'Horário final de entrada');
  const exitFromTime=assertTime(env('INDIGO_EXIT_FROM_TIME', env('INDIGO_EXIT_TIME','07:00')), 'Horário inicial de saída');
  const exitToTime=assertTime(env('INDIGO_EXIT_TO_TIME', env('INDIGO_EXIT_TIME','07:00')), 'Horário final de saída');
  const step=Number(env('INDIGO_STEP_MINUTES','30'));
  const product=env('INDIGO_PRODUCT','terminal3_garage');
  if (![30,60].includes(step)) throw new Error('Intervalo deve ser 30 ou 60 minutos.');
  if (!ALLOWED_PRODUCTS.has(product)) throw new Error('Produto Indigo inválido.');
  const entryDay=new Date(entryDate+'T12:00:00');
  const exitDay=new Date(exitDate+'T12:00:00');
  if (exitDay < entryDay) throw new Error('Data de saída precisa ser igual ou posterior à entrada.');

  const entryTimes=slotTimes(entryFromTime,entryToTime,step);
  const exitTimes=slotTimes(exitFromTime,exitToTime,step);
  const combinations=[];
  for (const entryTime of entryTimes) {
    for (const exitTime of exitTimes) {
      if (entryDate===exitDate && toMinutes(exitTime)<=toMinutes(entryTime)) continue;
      combinations.push({entryTime,exitTime});
    }
  }
  if (!combinations.length) throw new Error('Nenhuma combinação válida de entrada e saída.');
  if (combinations.length>250) throw new Error(`A faixa gera ${combinations.length} combinações. Reduza as faixas ou use intervalo de 60 minutos (máximo 250).`);

  const startedAt=new Date().toISOString();
  const browser=await chromium.launch({
    headless:true,
    executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args:['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']
  });
  const context=await browser.newContext({
    locale:'pt-BR',
    timezoneId:'America/Sao_Paulo',
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

    const BATCH=8;
    for(let i=0;i<combinations.length;i+=BATCH){
      const batch=combinations.slice(i,i+BATCH);
      const payloads=batch.map(({entryTime,exitTime})=>({
        entryTime,exitTime,
        body:{
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
        }
      }));
      const raw=await page.evaluate(async payloads=>Promise.all(payloads.map(async item=>{
        try{
          const r=await fetch('/brApi/GetMultipleRates',{
            method:'POST',credentials:'include',
            headers:{'Content-Type':'application/json','Accept':'application/json, text/plain, */*'},
            body:JSON.stringify(item.body)
          });
          return {entryTime:item.entryTime,exitTime:item.exitTime,status:r.status,text:await r.text()};
        }catch(e){return {entryTime:item.entryTime,exitTime:item.exitTime,status:0,error:String(e),text:''};}
      })),payloads);

      for(const item of raw){
        if(item.status!==200){
          results.push({entry_date:entryDate,entry_time:item.entryTime,exit_date:exitDate,exit_time:item.exitTime,status:'error',available:null,error:item.error||`HTTP ${item.status}`,booking_url:BOOKING_URL,products:[],alternatives:[]});
          continue;
        }
        try{
          const outer=JSON.parse(item.text);
          const decoded=typeof outer.d==='string'?JSON.parse(outer.d):outer.d;
          const root=Array.isArray(decoded)?decoded[0]:decoded;
          const products=(root?.DisplayRateList||[]).map(cleanRate).filter(x=>x.name && x.product_type!=='MonthlyPass');
          const target=targetFor(products,product);
          const alternatives=products.filter(x=>x.available).sort((a,b)=>(a.price??Infinity)-(b.price??Infinity)).map(x=>({key:x.key,name:x.name,price:x.price,covered:x.covered}));
          results.push({
            entry_date:entryDate,entry_time:item.entryTime,exit_date:exitDate,exit_time:item.exitTime,
            status:target?(target.available?'available':'sold_out'):'not_offered',
            available:target?target.available:false,
            product_key:product,
            product_name:target?.name || null,
            rate_id:target?.rate_id || null,
            price:target?.price ?? null,
            currency:'BRL',
            covered:Boolean(target?.covered),
            sold_out:target?target.sold_out:null,
            icons:target?.icons || [],
            description:target?.description || '',
            booking_url:BOOKING_URL,
            alternatives,
            products
          });
        }catch(e){
          results.push({entry_date:entryDate,entry_time:item.entryTime,exit_date:exitDate,exit_time:item.exitTime,status:'error',available:null,error:`Resposta inválida: ${e}`,booking_url:BOOKING_URL,products:[],alternatives:[]});
        }
      }
      if(i+BATCH<combinations.length) await page.waitForTimeout(250);
    }
  } finally {
    await browser.close();
  }

  results.sort((a,b)=>String(a.entry_time).localeCompare(String(b.entry_time)) || String(a.exit_time).localeCompare(String(b.exit_time)));
  const available=results.filter(x=>x.available===true);
  const valid=results.filter(x=>x.status!=='error');
  const prices=valid.map(x=>Number(x.price)).filter(x=>Number.isFinite(x)&&x>0);
  const best=bestAvailable(results);
  const payload={
    version:'2.0.0',status:'completed',generated_at:new Date().toISOString(),started_at:startedAt,request_id:requestId,
    location:{id:LOCATION_ID,name:'Aeroporto de Guarulhos (GRU)',booking_url:BOOKING_URL,timezone:'America/Sao_Paulo'},
    request:{
      entry_date:entryDate,exit_date:exitDate,
      entry_from_time:entryFromTime,entry_to_time:entryToTime,
      exit_from_time:exitFromTime,exit_to_time:exitToTime,
      step_minutes:step,product,
      from_time:entryFromTime,to_time:entryToTime,exit_time:exitFromTime
    },
    stats:{
      entry_times:entryTimes.length,exit_times:exitTimes.length,
      tested_combinations:results.length,available_combinations:available.length,
      unavailable_combinations:valid.length-available.length,error_combinations:results.length-valid.length,
      tested_times:results.length,available_times:available.length,
      lowest_price:prices.length?Math.min(...prices):null
    },
    best_combination:best?{entry_time:best.entry_time,exit_time:best.exit_time,price:best.price,currency:best.currency,product_name:best.product_name}:null,
    results
  };
  await fs.mkdir(path.dirname(OUTPUT_PATH),{recursive:true});
  await fs.writeFile(OUTPUT_PATH,JSON.stringify(payload,null,2),'utf8');
  console.log(`Indigo GRU: ${available.length}/${results.length} combinações disponíveis para ${product}.`);
  if(best) console.log(`Melhor combinação: entrada ${best.entry_time}, saída ${best.exit_time}, preço ${best.price ?? 'n/d'}.`);
}

main().catch(async err=>{
  const payload={version:'2.0.0',status:'error',generated_at:new Date().toISOString(),request_id:env('INDIGO_REQUEST_ID','manual'),error:String(err?.stack||err)};
  await fs.mkdir(path.dirname(OUTPUT_PATH),{recursive:true}).catch(()=>{});
  await fs.writeFile(OUTPUT_PATH,JSON.stringify(payload,null,2),'utf8').catch(()=>{});
  console.error(err);
  process.exitCode=1;
});
