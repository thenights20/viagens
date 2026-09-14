import { chromium } from 'playwright-core';

const URL = 'https://indigoneo.com.br/pt/booking/99980448';
const payload = {
  Criteria: [{
    LotId: '99980448',
    ParkingBeginDateTime: '2026/09/15 12:00:0',
    ParkingEndDateTime: '2026/10/06 07:00:0',
    SalesChannelKey: 'Web',
    CustomerFlowType: 'RAD',
    ISOLangCode: 'PT'
  }],
  SalesChannelKey: 'Web',
  ISOLangCode: 'PT'
};

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
const apiBodies = [];
page.on('response', async res => {
  const u = res.url();
  if (u.includes('/brApi/')) {
    try {
      const txt = await res.text();
      apiBodies.push({status:res.status(), url:u, body:txt.slice(0,20000)});
    } catch (e) {
      apiBodies.push({status:res.status(), url:u, body:'<unreadable '+e+'>'});
    }
  }
});
try {
  const resp = await page.goto(URL, {waitUntil:'domcontentloaded', timeout:60000});
  console.log('NAV_STATUS', resp?.status());
  await page.waitForTimeout(12000);

  const sameOrigin = await page.evaluate(async (body) => {
    const r = await fetch('/brApi/GetMultipleRates', {
      method:'POST',
      credentials:'include',
      headers:{'Content-Type':'application/json','Accept':'application/json, text/plain, */*'},
      body:JSON.stringify(body)
    });
    return {status:r.status, text:await r.text()};
  }, payload);
  console.log('SAME_ORIGIN_RATE_STATUS', sameOrigin.status);
  console.log('SAME_ORIGIN_RATE_BODY', sameOrigin.text.slice(0,50000));

  try {
    const direct = await fetch('https://indigoneo.com.br/brApi/GetMultipleRates', {
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'Accept':'application/json, text/plain, */*',
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36',
        'Referer':URL,
        'Origin':'https://indigoneo.com.br'
      },
      body:JSON.stringify(payload)
    });
    console.log('DIRECT_RATE_STATUS', direct.status);
    console.log('DIRECT_RATE_BODY', (await direct.text()).slice(0,50000));
  } catch (e) {
    console.log('DIRECT_RATE_ERROR', String(e));
  }

  await page.waitForTimeout(2000);
  console.log('API_BODIES', JSON.stringify(apiBodies, null, 2));
} finally {
  await browser.close();
}
