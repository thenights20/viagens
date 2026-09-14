import { chromium } from 'playwright-core';

const URL = 'https://indigoneo.com.br/pt/booking/99980448';
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
  args: ['--no-sandbox','--disable-dev-shm-usage','--disable-blink-features=AutomationControlled']
});
const context = await browser.newContext({
  locale: 'pt-BR',
  timezoneId: 'America/Sao_Paulo',
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36'
});
const page = await context.newPage();
const seen = new Set();
const interesting = [];
page.on('request', req => {
  const u = req.url();
  if (seen.has(u)) return;
  seen.add(u);
  if (/api|booking|rate|tariff|avail|product|parking|price|quote|reservation/i.test(u)) {
    interesting.push({method:req.method(), type:req.resourceType(), url:u, post:req.postData() || ''});
  }
});
page.on('response', async res => {
  const u = res.url();
  if (/api|booking|rate|tariff|avail|product|parking|price|quote|reservation/i.test(u)) {
    console.log('RESPONSE', res.status(), u);
  }
});
try {
  const resp = await page.goto(URL, {waitUntil:'domcontentloaded', timeout:60000});
  console.log('NAV_STATUS', resp?.status());
  await page.waitForTimeout(12000);
  for (const text of ['Aceitar todos','Aceitar','Concordar']) {
    const b = page.getByText(text, {exact:false}).first();
    if (await b.count()) { try { await b.click({timeout:1500}); break; } catch {} }
  }
  await page.waitForTimeout(5000);
  console.log('TITLE', await page.title());
  const body = (await page.locator('body').innerText()).replace(/\s+/g,' ').slice(0,5000);
  console.log('BODY', body);
  console.log('REQUESTS_JSON', JSON.stringify(interesting, null, 2));
  const inputs = await page.locator('input').evaluateAll(xs => xs.map(x => ({type:x.type,name:x.name,id:x.id,placeholder:x.placeholder,value:x.value,aria:x.getAttribute('aria-label')})));
  console.log('INPUTS_JSON', JSON.stringify(inputs, null, 2));
  const buttons = await page.locator('button').evaluateAll(xs => xs.slice(0,80).map(x => ({text:(x.innerText||'').trim(),disabled:x.disabled,aria:x.getAttribute('aria-label'),cls:x.className})));
  console.log('BUTTONS_JSON', JSON.stringify(buttons, null, 2));
} finally {
  await browser.close();
}
