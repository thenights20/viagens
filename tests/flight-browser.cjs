const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const server=spawn('python',['-m','http.server','8765','--directory','docs'],{stdio:'ignore'});
 let browser;
 try {
  browser=await chromium.launch({headless:true});
  const page=await browser.newPage();
  let request=null,stage='google',cancelled=0,posts=0;
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const saved=JSON.parse(fs.readFileSync('docs/data/flight-price-history.json','utf8'));
  const final=JSON.parse(fs.readFileSync('docs/data/flight-month-search.json','utf8'));
  await page.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.hostname==='script.google.com'){
    if(route.request().method()==='POST'){
     const body=JSON.parse(route.request().postData());
     if(u.searchParams.get('route')==='api/search'){request=body;posts++}else if(u.searchParams.get('route')==='api/cancel')cancelled++;
     return route.fulfill({body:'{}',contentType:'application/json'});
    }
    return route.fulfill({body:(u.searchParams.get('callback')||'noop')+'('+JSON.stringify({status:'queued'})+');',contentType:'text/javascript'});
   }
   if(u.pathname.endsWith('flight-search-config.json'))return route.fulfill({json:{api_base:'https://script.google.com/macros/s/test/exec'}});
   if(u.pathname.endsWith('flight-price-history.json'))return route.fulfill({json:saved});
   if(u.pathname.endsWith('flight-search-live.json')){
    const data=request?{request:{...request,period_mode:'month'},request_id:request.request_id,status:'running',stage,updated_at:stage,stats:{combinations:465,primary_total:465,primary_completed:stage==='google'?456:465,fallback_total:300,fallback_done:120,priced_combinations:1},results:[{origin:'DOU',destination:'GRU',departure_date:'2027-01-13',return_date:'2027-01-15',price:1265}]}:final;
    return route.fulfill({json:data});
   }
   if(u.pathname.endsWith('flight-month-search.json'))return route.fulfill({json:final});
   if(u.hostname==='api.github.com')return route.fulfill({json:{workflow_runs:[]}});
   if(u.hostname==='127.0.0.1')return route.continue();
   return route.fulfill({json:{}});
  });
  for(let i=0;i<30;i++){try{await page.goto('http://127.0.0.1:8765');break}catch{await new Promise(r=>setTimeout(r,100))}}
  await page.locator('.main-tab[data-main="flights"]').click();
  await page.locator('[data-flight-view="monthsearch"]').click();
  await page.locator('#showSavedSearches').click();
  await page.locator('#resultMonth').selectOption('2026-11');
  await page.locator('#resultOrigin').selectOption('DOU');
  await page.locator('#resultDestination').selectOption('GRU');
  await page.locator('#resultSort').selectOption('price_asc');
  assert.match(await page.locator('#monthLowest').innerText(),/680/);
  const href=await page.locator('#monthCalendar a').first().getAttribute('href');
  assert.match(href,/google.com/);
  await page.locator('#showCurrentSearch').click();
  await page.locator('#monthOrigin').selectOption('DOU');
  await page.locator('#monthDestination').fill('GRU');
  await page.locator('#monthValue').fill('2027-01');
  await page.locator('#monthSearchButton').click();
  await page.waitForFunction(()=>document.querySelector('#monthProgressPct').textContent==='98%',{},{timeout:20000});
  assert.equal(posts,1);
  stage='fallback';
  await page.waitForFunction(()=>document.querySelector('#monthProgressPct').textContent==='40%',{},{timeout:20000});
  await page.locator('#showSavedSearches').click();
  await page.locator('#resultMonth').selectOption('2026-11');
  assert.match(await page.locator('#monthLowest').innerText(),/680/);
  await page.locator('#showCurrentSearch').click();
  await page.locator('#monthStopButton').click();
  await page.waitForFunction(()=>!document.querySelector('#monthSearchButton').disabled,{},{timeout:20000});
  assert.equal(cancelled,1);
  assert.deepEqual(errors,[]);
  console.log('BROWSER PASS: links, saved November, route/month filters, live 98% and 40%, responsive controls, single dispatch and stop.');
 }finally{if(browser)await browser.close();server.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
