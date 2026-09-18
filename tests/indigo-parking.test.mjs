import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildCombinations,
  classifyProduct,
  orderResults,
  parseResponse,
  searchFingerprint,
  verifyCombination
} from '../parking-indigo/search.mjs';

function response({soldOut=false,price=593,name='Reserva_Online - Terminal 3 Edificio Garagem',rateId='T3-EDG'}) {
  return JSON.stringify({d:JSON.stringify([{
    DisplayRateList:[{
      RateId:rateId,
      RateName:name,
      GrandTotalAmount:price,
      CurrencyCode:'BRL',
      SoldOut:soldOut,
      ProductType:'Parking',
      RateIcons:[{Description:'Coberto'}]
    }]
  }])});
}

function fakePage(rawResponses) {
  const queue=[...rawResponses];
  return {
    evaluate:async()=>queue.shift(),
    waitForTimeout:async()=>{}
  };
}

test('identifica exatamente o produto T3 Edifício Garagem', () => {
  assert.equal(classifyProduct('Reserva_Online - Terminal 3 Edificio Garagem'),'terminal3_garage');
  assert.notEqual(classifyProduct('Reserva_Online - Terminal 3 Flex'),'terminal3_garage');
});

test('preço não transforma produto esgotado em disponível', () => {
  const row=parseResponse(response({soldOut:true,price:724.5}),'terminal3_garage','2026-09-19','12:00','2026-09-20','07:00');
  assert.equal(row.status,'sold_out');
  assert.equal(row.available,false);
  assert.equal(row.price,724.5);
  assert.equal(row.evidence.sold_out,true);
});

test('respostas repetidas divergentes ficam instáveis e nunca verdes', async () => {
  const page=fakePage([
    {status:200,text:response({soldOut:false,price:593})},
    {status:200,text:response({soldOut:true,price:593})}
  ]);
  const row=await verifyCombination(page,{entryDate:'2026-09-19',entryTime:'12:00',exitDate:'2026-09-20',exitTime:'07:00',product:'terminal3_garage'});
  assert.equal(row.status,'unstable');
  assert.equal(row.available,false);
  assert.equal(row.confirmed,false);
  assert.equal(row.verification.consistent,false);
});

test('verde exige duas confirmações idênticas e todas as evidências', async () => {
  const raw={status:200,text:response({soldOut:false,price:593})};
  const row=await verifyCombination(fakePage([raw,raw]),{entryDate:'2026-09-19',entryTime:'12:00',exitDate:'2026-09-20',exitTime:'07:00',product:'terminal3_garage'});
  assert.equal(row.status,'available');
  assert.equal(row.available,true);
  assert.equal(row.confirmed,true);
  assert.equal(row.verification.attempts,2);
  assert.deepEqual(row.evidence,{product_found:true,sold_out:false,valid_price:true});
});

test('gera apenas combinações em que a saída é posterior à entrada', () => {
  const combinations=buildCombinations(['2026-09-19'],['10:00','10:30'],['2026-09-19'],['10:00','10:30','11:00']);
  assert.equal(combinations.length,3);
  assert.ok(combinations.every(x=>`${x.exitDate}T${x.exitTime}`>`${x.entryDate}T${x.entryTime}`));
});

test('ordena verdes primeiro, por preço e depois proximidade do centro', () => {
  const base={status:'available',available:true,confirmed:true,evidence:{product_found:true,sold_out:false,valid_price:true},entry_date:'2026-09-19',exit_date:'2026-09-20'};
  const rows=orderResults([
    {...base,entry_time:'12:00',exit_time:'07:00',price:600,center_distance_minutes:0},
    {entry_date:'2026-09-19',entry_time:'11:00',exit_date:'2026-09-20',exit_time:'07:00',status:'sold_out',available:false,confirmed:true},
    {...base,entry_time:'13:00',exit_time:'07:30',price:500,center_distance_minutes:90},
    {...base,entry_time:'12:30',exit_time:'07:30',price:500,center_distance_minutes:30}
  ]);
  assert.deepEqual(rows.slice(0,3).map(x=>[x.price,x.center_distance_minutes]),[[500,30],[500,90],[600,0]]);
  assert.equal(rows[3].status,'sold_out');
});

test('fingerprint é estável e independe do request_id', () => {
  const config={entryDateFrom:'2026-09-19',entryDateTo:'2026-09-20',entryFromTime:'10:00',entryToTime:'16:00',exitDateFrom:'2026-10-06',exitDateTo:'2026-10-08',exitFromTime:'05:00',exitToTime:'10:00',product:'terminal3_garage'};
  assert.match(searchFingerprint(config),/^[a-f0-9]{64}$/);
  assert.equal(searchFingerprint({...config,requestId:'um'}),searchFingerprint({...config,requestId:'dois'}));
});
