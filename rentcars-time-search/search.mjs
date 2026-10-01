import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { chromium } from 'playwright-core';

const HOME='https://www.rentcars.com/pt-br/';
const env=process.env;
const req={
  pickup_location:String(env.RENTCARS_PICKUP_LOCATION||'').trim(),
  dropoff_location:String(env.RENTCARS_DROPOFF_LOCATION||'').trim(),
  pickup_date:String(env.RENTCARS_PICKUP_DATE||'').trim(),
  dropoff_date:String(env.RENTCARS_DROPOFF_DATE||'').trim(),
  pickup_from_time:String(env.RENTCARS_PICKUP_FROM_TIME||'08:00').trim(),
  pickup_to_time:String(env.RENTCARS_PICKUP_TO_TIME||'12:00').trim(),
  dropoff_from_time:String(env.RENTCARS_DROPOFF_FROM_TIME||'10:00').trim(),
  dropoff_to_time:String(env.RENTCARS_DROPOFF_TO_TIME||'10:00').trim(),
  mode:String(env.RENTCARS_MODE||'pickup').trim(),
  currency:String(env.RENTCARS_CURRENCY||'BRL').trim().toUpperCase(),
  driver_age:Number(env.RENTCARS_DRIVER_AGE||30),
  step_minutes:30
};
const requestId=String(env.RENTCARS_REQUEST_ID||'manual').trim();
const searchKey=String(env.RENTCARS_SEARCH_KEY||'').trim()||crypto.createHash('sha256').update(JSON.stringify(req)).digest('hex');
const outDir=path.join('docs','data','rentcars');
const outFile=path.join(outDir,searchKey+'.json');
fs.mkdirSync(outDir,{recursive:true});

const half=/^(?:[01]\d|2[0-3]):(?:00|30)$/;
const dateRe=/^20\d\d-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$/;
function minutes(v){const [h,m]=String(v).split(':').map(Number);return h*60+m;}
function timeSlots(a,b){const out=[];for(let m=minutes(a);m<=minutes(b);m+=30)out.push(`${String(Math.floor(m/60)).padStart(2,'0')}:${String(m%60).padStart(2,'0')}`);return out;}
function validate(){
  if(!req.pickup_location||!req.dropoff_location)throw new Error('Locais de retirada/devolução obrigatórios.');
  if(!dateRe.test(req.pickup_date)||!dateRe.test(req.dropoff_date)||req.dropoff_date<req.pickup_date)throw new Error('Datas inválidas.');
  if(![req.pickup_from_time,req.pickup_to_time,req.dropoff_from_time,req.dropoff_to_time].every(x=>half.test(x)))throw new Error('Horários precisam terminar em :00 ou :30.');
  if(minutes(req.pickup_to_time)<minutes(req.pickup_from_time)||minutes(req.dropoff_to_time)<minutes(req.dropoff_from_time))throw new Error('Faixa de horários inválida.');
  if(!['pickup','both'].includes(req.mode))throw new Error('Modo inválido.');
  if(!['BRL','USD'].includes(req.currency))throw new Error('Moeda inválida.');
  if(req.driver_age<18||req.driver_age>80)throw new Error('Idade inválida.');
}
validate();
const pickupTimes=timeSlots(req.pickup_from_time,req.pickup_to_time);
const dropoffTimes=req.mode==='pickup'?[req.dropoff_from_time]:timeSlots(req.dropoff_from_time,req.dropoff_to_time);
const combinations=pickupTimes.flatMap(p=>dropoffTimes.map(d=>({pickup_time:p,dropoff_time:d})));
if(combinations.length>49)throw new Error('Máximo de 49 combinações por execução.');

const result={
  version:'1.0.0',source:'Rentcars',request_id:requestId,search_key:searchKey,request:req,currency:req.currency,
  status:'running',generated_at:new Date().toISOString(),progress:{completed:0,total:combinations.length},results:[],stats:{tested:0,priced:0,blocked:0,errors:0},best_combination:null
};
function save(){result.generated_at=new Date().toISOString();fs.writeFileSync(outFile,JSON.stringify(result,null,2)+'\n');fs.writeFileSync(path.join('docs','data','rentcars-search.json'),JSON.stringify(result,null,2)+'\n');}
function blockedText(text){return /just a moment|verify you are human|performing security verification|cloudflare|challenge-platform|cf-chl|security verification/i.test(String(text||''));}
function parseMoney(text,currency){
  const patterns=currency==='BRL'?[/R\$\s*([\d.]+(?:,\d{2})?)/g,/BRL\s*([\d.]+(?:,\d{2})?)/gi]:[/US\$\s*([\d,]+(?:\.\d{2})?)/g,/USD\s*([\d,]+(?:\.\d{2})?)/gi,/\$\s*([\d,]+(?:\.\d{2})?)/g];
  const vals=[];
  for(const re of patterns){let m;while((m=re.exec(text))){let s=m[1];if(currency==='BRL')s=s.replace(/\./g,'').replace(',','.');else s=s.replace(/,/g,'');const n=Number(s);if(Number.isFinite(n)&&n>10&&n<100000)vals.push(n);}}
  return vals.length?Math.min(...vals):null;
}
async function visibleText(page){return await page.locator('body').innerText({timeout:10000}).catch(()=> '');}
async function firstVisible(locators){for(const l of locators){try{const x=l.first();if(await x.isVisible({timeout:500}))return x;}catch{}}return null;}
async function chooseSuggestion(page,input,value){
  await input.fill(value);await page.waitForTimeout(900);
  const option=await firstVisible([
    page.getByRole('option'),
    page.locator('[role="listbox"] [role="option"]'),
    page.locator('[data-testid*="suggest" i]'),
    page.locator('li').filter({hasText:value.split(',')[0]})
  ]);
  if(option)await option.click(); else await input.press('ArrowDown').then(()=>input.press('Enter')).catch(()=>{});
}
async function setDate(page,label,date,index){
  const dateInputs=page.locator('input[type="date"]');
  if(await dateInputs.count()>index){await dateInputs.nth(index).fill(date);return true;}
  const named=page.locator(`input[name*="${label}" i], input[id*="${label}" i]`);
  if(await named.count()){try{await named.first().fill(date);return true;}catch{}}
  const trigger=await firstVisible([
    page.getByText(label==='pickup' ? /retirada|pick.?up date/i : /devolu|drop.?off date/i),
    page.locator('button').filter({hasText:label==='pickup'?/retirada|pick.?up/i:/devolu|drop.?off/i})
  ]);
  if(!trigger)return false;
  await trigger.click();await page.waitForTimeout(300);
  const [y,m,d]=date.split('-');
  const aria=page.locator(`button[aria-label*="${date}"],button[data-date="${date}"], [role="gridcell"][data-date="${date}"]`);
  if(await aria.count()){await aria.first().click();return true;}
  const day=page.getByRole('button',{name:new RegExp(`^${Number(d)}$`)});
  if(await day.count()){await day.last().click();return true;}
  return false;
}
async function setTime(page,label,time,index){
  const timeInputs=page.locator('input[type="time"]');
  if(await timeInputs.count()>index){await timeInputs.nth(index).fill(time);return true;}
  const named=page.locator(`input[name*="${label}" i], input[id*="${label}" i]`);
  if(await named.count()){try{await named.first().fill(time);return true;}catch{}}
  const triggers=label==='pickup' ? page.getByText(/horário.*retirada|pick.?up time/i) : page.getByText(/horário.*devolu|drop.?off time/i);
  if(await triggers.count()){await triggers.first().click();await page.waitForTimeout(250);const opt=page.getByRole('button',{name:time});if(await opt.count()){await opt.first().click();return true;}}
  const exact=page.getByText(time,{exact:true});if(await exact.count()){try{await exact.last().click();return true;}catch{}}
  return false;
}
async function searchOne(context,combo){
  const page=await context.newPage();
  try{
    await page.goto(HOME,{waitUntil:'domcontentloaded',timeout:45000});await page.waitForTimeout(1800);
    let text=await visibleText(page);if(blockedText(text))return {status:'blocked',error:'A Rentcars solicitou verificação de segurança/Cloudflare.',url:page.url()};
    const inputs=page.locator('input');
    const pickup=await firstVisible([
      page.locator('input[placeholder*="destino" i]'),page.locator('input[placeholder*="destination" i]'),page.locator('input[name*="pickup" i]'),inputs
    ]);
    if(!pickup)return {status:'error',error:'Campo de retirada não encontrado.',url:page.url()};
    await chooseSuggestion(page,pickup,req.pickup_location);
    const diff=await firstVisible([page.getByText(/devolver.*outro|drop.?off at different location/i),page.getByRole('checkbox')]);if(diff){try{await diff.click();}catch{}}
    await page.waitForTimeout(300);
    const visibleInputs=[];for(let i=0;i<await inputs.count();i++){const el=inputs.nth(i);if(await el.isVisible().catch(()=>false))visibleInputs.push(el);}
    let drop=visibleInputs.find(x=>x!==pickup);if(!drop){drop=await firstVisible([page.locator('input[name*="dropoff" i]'),page.locator('input[placeholder*="destino" i]').nth(1),page.locator('input[placeholder*="destination" i]').nth(1)]);}
    if(drop)await chooseSuggestion(page,drop,req.dropoff_location);
    const datesOk=(await setDate(page,'pickup',req.pickup_date,0))&&(await setDate(page,'dropoff',req.dropoff_date,1));
    const timesOk=(await setTime(page,'pickup',combo.pickup_time,0))&&(await setTime(page,'dropoff',combo.dropoff_time,1));
    const search=await firstVisible([page.getByRole('button',{name:/buscar|search/i}),page.locator('button[type="submit"]')]);
    if(!search)return {status:'error',error:'Botão de busca não encontrado.',url:page.url(),diagnostic:{dates_ok:datesOk,times_ok:timesOk}};
    await Promise.all([page.waitForLoadState('domcontentloaded',{timeout:30000}).catch(()=>{}),search.click()]);
    await page.waitForTimeout(5000);text=await visibleText(page);if(blockedText(text))return {status:'blocked',error:'A Rentcars bloqueou a consulta automatizada durante a pesquisa.',url:page.url()};
    const price=parseMoney(text,req.currency);
    if(!price)return {status:'unavailable',error:'Nenhum preço total identificável na página de resultados.',url:page.url()};
    const suppliers=['Budget','Alamo','Hertz','Avis','Dollar','Thrifty','Enterprise','National','Sixt','Fox','Payless','Ace'];
    const supplier=suppliers.find(s=>new RegExp(`\\b${s}\\b`,'i').test(text))||'Rentcars';
    return {status:'ok',price_total:price,currency:req.currency,supplier,url:page.url()};
  }catch(e){return {status:'error',error:String(e?.message||e).slice(0,500),url:page.url()};}
  finally{await page.close().catch(()=>{});}
}

let browser;
try{
  browser=await chromium.launch({headless:true,executablePath:env.CHROME_PATH||'/usr/bin/google-chrome',args:['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']});
  const context=await browser.newContext({locale:'pt-BR',timezoneId:'America/New_York',viewport:{width:1365,height:900},userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'});
  for(const combo of combinations){
    const row={pickup_date:req.pickup_date,dropoff_date:req.dropoff_date,pickup_time:combo.pickup_time,dropoff_time:combo.dropoff_time,...await searchOne(context,combo)};
    result.results.push(row);result.progress.completed++;result.stats.tested++;
    if(row.status==='ok')result.stats.priced++;else if(row.status==='blocked')result.stats.blocked++;else if(row.status==='error')result.stats.errors++;
    save();
    if(row.status==='blocked'){
      result.status='blocked';result.error='A proteção de segurança da Rentcars impediu a automação. Nenhum preço foi estimado ou inventado.';break;
    }
  }
  const priced=result.results.filter(x=>x.status==='ok'&&Number.isFinite(Number(x.price_total))).sort((a,b)=>a.price_total-b.price_total);
  if(priced.length)result.best_combination=priced[0];
  if(result.status!=='blocked')result.status='completed';
}catch(e){result.status='error';result.error=String(e?.stack||e).slice(0,1500);}
finally{if(browser)await browser.close().catch(()=>{});save();}
console.log(JSON.stringify({status:result.status,tested:result.stats.tested,priced:result.stats.priced,blocked:result.stats.blocked,best:result.best_combination},null,2));
