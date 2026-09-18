import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const LOCATION_ID = '99980448';
const BOOKING_URL = `https://indigoneo.com.br/pt/booking/${LOCATION_ID}`;
const OUTPUT_PATH = path.resolve(process.env.INDIGO_OUTPUT_PATH || 'docs/data/indigo-parking-search.json');
const ALLOWED_PRODUCTS = new Set(['terminal3_garage','terminal3_flex','terminal2_standard','terminal1','any']);
const CONFIRMATIONS_REQUIRED = 2;
const CHECKPOINT_TTL_MS = 60 * 60 * 1000;
const CHECKPOINT_BATCH_SIZE = Math.max(1, Number(process.env.INDIGO_CHECKPOINT_BATCH_SIZE || 25));
const LIVE_BRANCH = String(process.env.INDIGO_LIVE_BRANCH || 'indigo-live').trim();

function env(name, fallback='') { const value=String(process.env[name] ?? '').trim(); return value || String(fallback).trim(); }
function isoDayOffset(days) { return new Date(Date.now() + days * 86400000).toISOString().slice(0,10); }
function assertDate(v, label) { if (!/^20\d\d-\d{2}-\d{2}$/.test(v) || Number.isNaN(Date.parse(v+'T12:00:00Z'))) throw new Error(`${label} inválida`); return v; }
function assertTime(v, label) { if (!/^(?:[01]\d|2[0-3]):(?:00|30)$/.test(v)) throw new Error(`${label} deve terminar em :00 ou :30`); return v; }
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
    product_type: String(rate.ProductType || '')
  };
}
function slotTimes(fromTime, toTime) {
  const start=toMinutes(fromTime), end=toMinutes(toTime);
  if (end < start) throw new Error('Horário final da faixa precisa ser igual ou posterior ao inicial.');
  const out=[];
  for(let m=start;m<=end;m+=30) out.push(fromMinutes(m));
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
  const wrapped=Object.prototype.hasOwnProperty.call(outer||{},'d') ? outer.d : outer;
  const decoded=typeof wrapped==='string'?JSON.parse(wrapped):wrapped;
  const root=Array.isArray(decoded)?decoded[0]:decoded;
  const products=(root?.DisplayRateList||[]).map(cleanRate).filter(x=>x.name && x.product_type!=='MonthlyPass');
  const target=targetFor(products,product);
  const validPrice=Boolean(target && Number.isFinite(Number(target.price)) && Number(target.price)>0);
  const base={
    entry_date:entryDate,entry_time:entryTime,exit_date:exitDate,exit_time:exitTime,
    product_key:product,product_name:target?.name||null,rate_id:target?.rate_id||null,
    price:target?.price??null,currency:target?.currency||'BRL',covered:Boolean(target?.covered),sold_out:target?target.sold_out:null,
    booking_url:BOOKING_URL,alternatives:alternativesFor(products),
    evidence:{product_found:Boolean(target),sold_out:target?Boolean(target.sold_out):null,valid_price:validPrice}
  };
  if(!target) return {...base,status:'not_offered',available:false};
  if(target.sold_out) return {...base,status:'sold_out',available:false};
  if(!validPrice) return {...base,status:'unstable',available:false};
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
    return {entry_date:entryDate,entry_time:entryTime,exit_date:exitDate,exit_time:exitTime,status:'error',available:null,confirmed:false,error:raw.error||`HTTP ${raw.status}`,booking_url:BOOKING_URL,alternatives:[],evidence:{product_found:false,sold_out:null,valid_price:false}};
  }
  try{return parseResponse(raw.text,product,entryDate,entryTime,exitDate,exitTime);}
  catch(e){return {entry_date:entryDate,entry_time:entryTime,exit_date:exitDate,exit_time:exitTime,status:'error',available:null,confirmed:false,error:`Resposta inválida: ${e}`,booking_url:BOOKING_URL,alternatives:[],evidence:{product_found:false,sold_out:null,valid_price:false}};}
}
function observationSignature(row){
  return JSON.stringify([row.status,row.product_name||null,row.rate_id||null,row.sold_out??null,Number(row.price)||null]);
}
async function verifyCombination(page,args){
  const checks=[];
  for(let attempt=1;attempt<=CONFIRMATIONS_REQUIRED;attempt++){
    if(attempt>1) await page.waitForTimeout(450);
    checks.push(await queryOnce(page,args));
  }
  const signatures=checks.map(observationSignature);
  const observations=checks.map(x=>x.status);
  const representative=checks.find(x=>x.status!=='error') || checks[checks.length-1];
  const verification={attempts:checks.length,required:CONFIRMATIONS_REQUIRED,observations,consistent:new Set(signatures).size===1};
  if(!verification.consistent){
    return {...representative,status:'unstable',available:false,confirmed:false,price:null,verification,note:'A Indigo respondeu de forma diferente ao repetir a mesma combinação; não considerada disponível.'};
  }
  if(representative.status==='available'){
    const green=representative.evidence?.product_found===true && representative.evidence?.sold_out===false && representative.evidence?.valid_price===true;
    if(!green) return {...representative,status:'unstable',available:false,confirmed:false,price:null,verification,note:'A resposta não comprovou todos os critérios de disponibilidade.'};
    return {...representative,status:'available',available:true,confirmed:true,verification,note:'Produto, estoque e preço confirmados novamente pela Indigo.'};
  }
  if(['sold_out','not_offered'].includes(representative.status)){
    return {...representative,available:false,confirmed:true,verification,note:'Resposta confirmada novamente pela Indigo.'};
  }
  return {...representative,available:false,confirmed:false,verification,note:representative.status==='error'?'Não foi possível confirmar esta combinação.':'A combinação não cumpriu todos os critérios de disponibilidade.'};
}

function combinationKey(x){return `${x.entryDate||x.entry_date}T${x.entryTime||x.entry_time}|${x.exitDate||x.exit_date}T${x.exitTime||x.exit_time}`;}
function buildCombinations(entryDates,entryTimes,exitDates,exitTimes){
  const combinations=[];
  for (const entryDate of entryDates) for (const entryTime of entryTimes) for (const exitDate of exitDates) for (const exitTime of exitTimes) {
    if (`${exitDate}T${exitTime}` > `${entryDate}T${entryTime}`) combinations.push({entryDate,entryTime,exitDate,exitTime});
  }
  return combinations;
}
function midpoint(fromDate,fromTime,toDate,toTime){return (Date.parse(`${fromDate}T${fromTime}:00Z`)+Date.parse(`${toDate}T${toTime}:00Z`))/2;}
function centerDistance(row,centers){
  const entry=Date.parse(`${row.entry_date}T${row.entry_time}:00Z`), exit=Date.parse(`${row.exit_date}T${row.exit_time}:00Z`);
  return Math.round((Math.abs(entry-centers.entry)+Math.abs(exit-centers.exit))/60000);
}
function chronological(a,b){return String(a.entry_date).localeCompare(String(b.entry_date)) || String(a.entry_time).localeCompare(String(b.entry_time)) || String(a.exit_date).localeCompare(String(b.exit_date)) || String(a.exit_time).localeCompare(String(b.exit_time));}
function availableOrder(a,b){return (Number(a.price??Infinity)-Number(b.price??Infinity)) || (Number(a.center_distance_minutes??Infinity)-Number(b.center_distance_minutes??Infinity)) || chronological(a,b);}
function orderResults(rows){
  const available=rows.filter(x=>x.available===true&&x.confirmed===true).sort(availableOrder);
  const rank={unstable:0,error:1,sold_out:2,not_offered:3};
  const other=rows.filter(x=>!(x.available===true&&x.confirmed===true)).sort((a,b)=>(rank[a.status]??9)-(rank[b.status]??9) || chronological(a,b));
  return [...available,...other];
}
function searchFingerprint(config){
  const canonical=['v3',config.entryDateFrom,config.entryDateTo,config.entryFromTime,config.entryToTime,config.exitDateFrom,config.exitDateTo,config.exitFromTime,config.exitToTime,'30',config.product].join('|');
  return crypto.createHash('sha256').update(canonical).digest('hex');
}
function reusableRow(row){return row?.confirmed===true && ['available','sold_out','not_offered'].includes(row.status);}

class CheckpointStore {
  constructor(searchKey){
    this.searchKey=searchKey;
    this.repository=env('GITHUB_REPOSITORY');
    this.token=env('GITHUB_TOKEN');
    this.filePath=`docs/data/indigo-checkpoints/${searchKey}.json`;
    this.sha=null;
    this.enabled=Boolean(this.repository&&this.token&&LIVE_BRANCH);
  }
  headers(){return {'Accept':'application/vnd.github+json','Authorization':`Bearer ${this.token}`,'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'};}
  async api(apiPath,options={}){
    const response=await fetch(`https://api.github.com/repos/${this.repository}${apiPath}`,{...options,headers:{...this.headers(),...(options.headers||{})}});
    const text=await response.text();
    const data=text?JSON.parse(text):null;
    if(!response.ok){const error=new Error(`GitHub checkpoint HTTP ${response.status}`);error.status=response.status;error.data=data;throw error;}
    return data;
  }
  async ensureBranch(){
    try{await this.api(`/git/ref/heads/${encodeURIComponent(LIVE_BRANCH)}`);return;}
    catch(error){if(error.status!==404)throw error;}
    const main=await this.api('/git/ref/heads/main');
    try{await this.api('/git/refs',{method:'POST',body:JSON.stringify({ref:`refs/heads/${LIVE_BRANCH}`,sha:main.object.sha})});}
    catch(error){if(error.status!==422)throw error;}
  }
  async metadata(){
    try{
      const meta=await this.api(`/contents/${this.filePath}?ref=${encodeURIComponent(LIVE_BRANCH)}`);
      this.sha=meta.sha||null;
      return meta;
    }catch(error){if(error.status===404){this.sha=null;return null;}throw error;}
  }
  async load(){
    if(!this.enabled)return null;
    await this.ensureBranch();
    const meta=await this.metadata();
    if(!meta)return null;
    const response=await fetch(`https://raw.githubusercontent.com/${this.repository}/${LIVE_BRANCH}/${this.filePath}?t=${Date.now()}`,{cache:'no-store'});
    if(!response.ok)return null;
    try{return await response.json();}catch{return null;}
  }
  async save(payload){
    if(!this.enabled)return;
    const body={message:`checkpoint: Indigo ${this.searchKey.slice(0,12)} [skip ci]`,content:Buffer.from(JSON.stringify(payload)).toString('base64'),branch:LIVE_BRANCH};
    if(this.sha)body.sha=this.sha;
    for(let attempt=1;attempt<=2;attempt++){
      try{
        const saved=await this.api(`/contents/${this.filePath}`,{method:'PUT',body:JSON.stringify(body)});
        this.sha=saved?.content?.sha||this.sha;
        return;
      }catch(error){
        if(![409,422].includes(error.status)||attempt===2)throw error;
        await this.metadata();
        if(this.sha)body.sha=this.sha;else delete body.sha;
      }
    }
  }
}

function statsFor(rows,total,shape){
  const available=rows.filter(x=>x.available===true&&x.confirmed===true);
  const unstable=rows.filter(x=>x.status==='unstable');
  const errors=rows.filter(x=>x.status==='error');
  const soldOut=rows.filter(x=>x.status==='sold_out');
  const notOffered=rows.filter(x=>x.status==='not_offered');
  const confirmed=rows.filter(x=>x.confirmed===true);
  const prices=available.map(x=>Number(x.price)).filter(x=>Number.isFinite(x)&&x>0);
  return {...shape,total_combinations:total,tested_combinations:rows.length,processed_combinations:rows.length,remaining_combinations:Math.max(0,total-rows.length),confirmed_combinations:confirmed.length,available_combinations:available.length,sold_out_combinations:soldOut.length,not_offered_combinations:notOffered.length,unstable_combinations:unstable.length,unconfirmed_combinations:unstable.length+errors.length+notOffered.length,error_combinations:errors.length,lowest_price:prices.length?Math.min(...prices):null};
}
function payloadFor({status,requestId,searchKey,startedAt,config,shape,total,rows,reused,searched}){
  const ordered=orderResults(rows);
  const stats=statsFor(ordered,total,shape);
  const best=ordered.find(x=>x.available===true&&x.confirmed===true)||null;
  const percent=total?Math.min(100,Number(((stats.processed_combinations/total)*100).toFixed(1))):100;
  return {
    version:'3.0.0',status,generated_at:new Date().toISOString(),started_at:startedAt,request_id:requestId,search_key:searchKey,
    reliability:{mode:'sequential-double-confirmation',confirmations_required:CONFIRMATIONS_REQUIRED,green_means:'produto correto presente, SoldOut=false, preço válido e a mesma resposta confirmada novamente pela Indigo'},
    checkpoint:{enabled:true,branch:LIVE_BRANCH,window_minutes:60,batch_size:CHECKPOINT_BATCH_SIZE},
    resume:{enabled:true,window_minutes:60,reused_combinations:reused,searched_this_run:searched,retryable_for_next_run:(total-ordered.length)+ordered.filter(x=>!reusableRow(x)).length},
    progress:{completed:stats.processed_combinations,total,remaining:stats.remaining_combinations,percent},
    location:{id:LOCATION_ID,name:'Aeroporto de Guarulhos (GRU)',booking_url:BOOKING_URL,timezone:'America/Sao_Paulo'},
    request:{entry_date_from:config.entryDateFrom,entry_date_to:config.entryDateTo,exit_date_from:config.exitDateFrom,exit_date_to:config.exitDateTo,entry_from_time:config.entryFromTime,entry_to_time:config.entryToTime,exit_from_time:config.exitFromTime,exit_to_time:config.exitToTime,step_minutes:30,product:config.product},
    stats,
    best_combination:best?{entry_date:best.entry_date,entry_time:best.entry_time,exit_date:best.exit_date,exit_time:best.exit_time,price:best.price,currency:best.currency,product_name:best.product_name,confirmed:true,center_distance_minutes:best.center_distance_minutes}:null,
    results:ordered
  };
}
async function writeOutput(payload){await fs.mkdir(path.dirname(OUTPUT_PATH),{recursive:true});await fs.writeFile(OUTPUT_PATH,JSON.stringify(payload,null,2),'utf8');}

async function main() {
  const defaultEntry=isoDayOffset(1), defaultExit=isoDayOffset(2);
  const config={
    entryDateFrom:assertDate(env('INDIGO_ENTRY_DATE_FROM',env('INDIGO_ENTRY_DATE',defaultEntry)), 'Data inicial de entrada'),
    entryDateTo:'',exitDateFrom:'',exitDateTo:'',
    entryFromTime:assertTime(env('INDIGO_ENTRY_FROM_TIME',env('INDIGO_FROM_TIME','12:00')), 'Horário inicial de entrada'),
    entryToTime:assertTime(env('INDIGO_ENTRY_TO_TIME',env('INDIGO_TO_TIME','15:00')), 'Horário final de entrada'),
    exitFromTime:assertTime(env('INDIGO_EXIT_FROM_TIME',env('INDIGO_EXIT_TIME','06:00')), 'Horário inicial de saída'),
    exitToTime:assertTime(env('INDIGO_EXIT_TO_TIME',env('INDIGO_EXIT_TIME','09:00')), 'Horário final de saída'),
    product:env('INDIGO_PRODUCT','terminal3_garage')
  };
  config.entryDateTo=assertDate(env('INDIGO_ENTRY_DATE_TO',config.entryDateFrom),'Data final de entrada');
  config.exitDateFrom=assertDate(env('INDIGO_EXIT_DATE_FROM',env('INDIGO_EXIT_DATE',defaultExit)),'Data inicial de saída');
  config.exitDateTo=assertDate(env('INDIGO_EXIT_DATE_TO',config.exitDateFrom),'Data final de saída');
  const step=Number(env('INDIGO_STEP_MINUTES','30'));
  if(step!==30)throw new Error('A Indigo oferece esta busca somente em intervalos de 30 minutos.');
  if(!ALLOWED_PRODUCTS.has(config.product))throw new Error('Produto Indigo inválido.');
  if(config.entryDateTo<config.entryDateFrom)throw new Error('A data final de entrada precisa ser igual ou posterior à inicial.');
  if(config.exitDateTo<config.exitDateFrom)throw new Error('A data final de saída precisa ser igual ou posterior à inicial.');
  if(config.exitDateTo<config.entryDateFrom)throw new Error('A faixa de saída termina antes da faixa de entrada.');

  const entryDates=dateRange(config.entryDateFrom,config.entryDateTo), exitDates=dateRange(config.exitDateFrom,config.exitDateTo);
  const entryTimes=slotTimes(config.entryFromTime,config.entryToTime), exitTimes=slotTimes(config.exitFromTime,config.exitToTime);
  const combinations=buildCombinations(entryDates,entryTimes,exitDates,exitTimes);
  if(!combinations.length)throw new Error('Nenhuma combinação válida de entrada e saída.');

  const requestId=env('INDIGO_REQUEST_ID','manual').slice(0,80)||'manual';
  const computedSearchKey=searchFingerprint(config);
  const suppliedSearchKey=env('INDIGO_SEARCH_KEY');
  const searchKey=/^[a-f0-9]{64}$/.test(suppliedSearchKey)?suppliedSearchKey:computedSearchKey;
  if(searchKey!==computedSearchKey)throw new Error('Identificador da pesquisa não corresponde aos parâmetros recebidos.');
  const centers={entry:midpoint(config.entryDateFrom,config.entryFromTime,config.entryDateTo,config.entryToTime),exit:midpoint(config.exitDateFrom,config.exitFromTime,config.exitDateTo,config.exitToTime)};
  const shape={entry_days:entryDates.length,exit_days:exitDates.length,entry_times:entryTimes.length,exit_times:exitTimes.length};
  const startedAt=new Date().toISOString();
  const store=new CheckpointStore(searchKey);
  let previous=null;
  try{previous=await store.load();}catch(error){console.warn(`Checkpoint anterior indisponível: ${error.message}`);}
  const previousFresh=previous?.search_key===searchKey && Date.now()-Date.parse(previous.generated_at||0)<=CHECKPOINT_TTL_MS;
  const resultsByKey=new Map();
  if(previousFresh){
    for(const row of previous.results||[])if(reusableRow(row))resultsByKey.set(combinationKey(row),row);
  }
  const reused=resultsByKey.size;
  let searched=0;
  let lastCheckpointAt=0;
  const total=combinations.length;
  const currentRows=()=>[...resultsByKey.values()].map(row=>({...row,center_distance_minutes:Number.isFinite(Number(row.center_distance_minutes))?Number(row.center_distance_minutes):centerDistance(row,centers)}));
  const persist=async status=>{
    const payload=payloadFor({status,requestId,searchKey,startedAt,config,shape,total,rows:currentRows(),reused,searched});
    await writeOutput(payload);
    try{await store.save(payload);}catch(error){console.warn(`Não foi possível publicar o checkpoint: ${error.message}`);}
    lastCheckpointAt=Date.now();
    return payload;
  };
  await persist('running');

  const remaining=combinations.filter(combo=>!resultsByKey.has(combinationKey(combo)));
  if(remaining.length){
    const { chromium }=await import('playwright-core');
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
    try{
      const nav=await page.goto(BOOKING_URL,{waitUntil:'domcontentloaded',timeout:60000});
      if(!nav||nav.status()>=400)throw new Error(`Indigo respondeu HTTP ${nav?.status()??'sem resposta'}`);
      await page.waitForFunction(()=>!document.title.toLowerCase().includes('just a moment'),null,{timeout:30000}).catch(()=>{});
      await page.waitForResponse(r=>r.url().includes('/brApi/GetLocationDataBind')&&r.status()===200,{timeout:30000}).catch(()=>{});
      await page.waitForTimeout(2200);

      // Uma única sessão e uma única combinação por vez evitam bloqueios e falsos positivos.
      for(let offset=0;offset<remaining.length;offset+=CHECKPOINT_BATCH_SIZE){
        const batch=remaining.slice(offset,offset+CHECKPOINT_BATCH_SIZE);
        for(let i=0;i<batch.length;i++){
          const combo=batch[i];
          const row=await verifyCombination(page,{...combo,product:config.product});
          row.center_distance_minutes=centerDistance(row,centers);
          resultsByKey.set(combinationKey(combo),row);
          searched++;
          // Uma vaga confirmada aparece rapidamente, sem gerar um commit para cada resposta.
          if(row.available===true&&row.confirmed===true&&Date.now()-lastCheckpointAt>=5000)await persist('running');
          if(offset+i+1<remaining.length)await page.waitForTimeout(180);
        }
        await persist('running');
        console.log(`Checkpoint Indigo: ${resultsByKey.size}/${total} combinações processadas.`);
      }
    }finally{await browser.close();}
  }

  const payload=await persist('completed');
  console.log(`Indigo GRU: ${payload.stats.available_combinations}/${total} combinações confirmadas; ${payload.stats.unstable_combinations} instáveis; ${reused} reaproveitadas.`);
  if(payload.best_combination)console.log(`Melhor combinação confirmada: entrada ${payload.best_combination.entry_date} ${payload.best_combination.entry_time}, saída ${payload.best_combination.exit_date} ${payload.best_combination.exit_time}, preço ${payload.best_combination.price}.`);
}

export { buildCombinations, centerDistance, classifyProduct, orderResults, parseResponse, searchFingerprint, statsFor, verifyCombination };

if(process.argv[1] && import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href){
  main().catch(async err=>{
    const payload={version:'3.0.0',status:'error',generated_at:new Date().toISOString(),request_id:env('INDIGO_REQUEST_ID','manual'),error:String(err?.stack||err)};
    await writeOutput(payload).catch(()=>{});
    console.error(err);
    process.exitCode=1;
  });
}
