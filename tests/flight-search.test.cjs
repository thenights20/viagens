const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const source=fs.readFileSync('docs/flight-explorer.js','utf8');
function section(from,to){return source.slice(source.indexOf(from),source.indexOf(to))}
const request={request_id:'web_current',origin:'DOU',dispatch_origin:'QJG',destination:'GRU',month:'2026-10',max_stops:2,period_mode:'range',start_date:'2026-10-10',end_date:'2026-10-15'};
test('results from earlier identical searches are ignored',()=>{
 const ctx=vm.createContext({});vm.runInContext(section('  function resultMatches','  function liveProgress'),ctx);
 const result={request,request_id:'web_old',started_at:new Date().toISOString()};
 assert.equal(ctx.resultMatches(result,request,Date.now()),false);
 result.request_id=request.request_id;assert.equal(ctx.resultMatches(result,request,Date.now()),true);
});
test('dispatch never waits for a stalled redirect and sends once with a stable ID',()=>{
 const calls=[];const ctx=vm.createContext({postBridge:(...args)=>{calls.push(args);return new Promise(()=>{})}});
 vm.runInContext(section('  function dispatchWithoutCors','  async function stopSearch'),ctx);
 assert.equal(ctx.dispatchWithoutCors(request),undefined);assert.equal(calls.length,1);assert.equal(calls[0][1].request_id,request.request_id);
});
test('old live data cannot suppress progress and missing acceptance terminates',async()=>{
 let now=1000000;const progress=[];
 const ctx=vm.createContext({Date:{now:()=>now},stopRequested:false,activeRun:null,q:()=>({}),sleep:async()=>{now+=31000},fetchJson:async()=>({request_id:'old'}),resultMatches:()=>false,fetchRunState:async()=>null,bridgeProgress:async()=>null,updateProgress:p=>progress.push(p),LIVE_RAW:'live',RESULT_RAW:'final',data:{stats:{},results:[]}});
 vm.runInContext(section('  async function pollSearch','  function postBridge'),ctx);
 await assert.rejects(ctx.pollSearch(request,1000000,15),/não confirmou/);
 assert.ok(progress.length>0);assert.ok(progress.every(p=>p.stage.includes('confirmação')));
});
test('bridge rejection is displayed rather than treated as a queued job',async()=>{
 const ctx=vm.createContext({Date,stopRequested:false,activeRun:null,q:()=>({}),sleep:async()=>{},fetchJson:async()=>null,resultMatches:()=>false,fetchRunState:async()=>null,bridgeProgress:async()=>({status:'error',error:'GitHub recusou a pesquisa (401)'}),LIVE_RAW:'live',RESULT_RAW:'final',data:{stats:{},results:[]}});
 vm.runInContext(section('  async function pollSearch','  function postBridge'),ctx);
 await assert.rejects(ctx.pollSearch(request,Date.now(),15),/401/);
});
test('failed workflow preserves partial results with partial status',async()=>{
 const ctx=vm.createContext({Date,stopRequested:false,activeRun:null,q:()=>({}),sleep:async()=>{},fetchJson:async()=>null,resultMatches:()=>false,fetchRunState:async()=>({failed:true,error:'failed'}),bridgeProgress:async()=>null,LIVE_RAW:'live',RESULT_RAW:'final',data:{status:'running',stats:{},results:[{price:200}]}});
 vm.runInContext(section('  async function pollSearch','  function postBridge'),ctx);
 const result=await ctx.pollSearch(request,Date.now(),15);assert.equal(result.status,'partial');assert.equal(result.results.length,1);
});
test('Apps Script routes root URL requests with query parameters',()=>{
 const bridge=fs.readFileSync('apps-script/Code.gs','utf8');
 const ctx=vm.createContext({});vm.runInContext(bridge,ctx);
 ctx.json_=x=>x;ctx.startSearch_=x=>({accepted:x.request_id});ctx.progressUpdate_=x=>x;ctx.cancelSearch_=x=>({cancelled:x.request_id});ctx.getProgress_=id=>({request_id:id,status:'queued'});ctx.jsonp_=(x,callback)=>({payload:x,callback});
 const post=ctx.doPost({parameter:{route:'api/search'},postData:{contents:JSON.stringify({request_id:'web_test_request'})}});
 assert.equal(post.accepted,'web_test_request');
 const progress=ctx.doGet({parameter:{route:'api/progress/web_test_request',callback:'flightCallback'}});
 assert.equal(progress.payload.request_id,'web_test_request');assert.equal(progress.callback,'flightCallback');
 assert.equal(ctx.doPost({parameter:{route:'api/cancel'},postData:{contents:'{"request_id":"web_test_request"}'}}).cancelled,'web_test_request');
 assert.equal(ctx.doGet({parameter:{}}).version,'0.3.1');
});
test('transport sends to exec query instead of appending a path',async()=>{
 let url;const ctx=vm.createContext({apiBase:'https://script.google.com/macros/s/test/exec',AbortController,setTimeout,clearTimeout,fetch:async u=>{url=u;return {type:'opaque'}}});
 vm.runInContext(section('  function postBridge','  function dispatchWithoutCors'),ctx);
 await ctx.postBridge('api/search',{});const parsed=new URL(url);assert.equal(parsed.pathname,'/macros/s/test/exec');assert.equal(parsed.searchParams.get('route'),'api/search');
});
test('route filters and ascending/descending prices work independently of input order',()=>{
 const ctx=vm.createContext({});vm.runInContext(section('  function filterRows','  function resultOptions'),ctx);
 const rows=[{origin:'DOU',destination:'GRU',price:400},{origin:'DOU',destination:'MIA',price:200},{origin:'GRU',destination:'MIA',price:100},{origin:'DOU',destination:'GRU',price:300}];
 assert.deepEqual(Array.from(ctx.filterRows(rows,'DOU','GRU','price_asc'),x=>x.price),[300,400]);
 assert.deepEqual(Array.from(ctx.filterRows(rows,'DOU','','price_desc'),x=>x.price),[400,300,200]);
 assert.equal(ctx.filterRows(rows,'GRU','GRU','price_asc').length,0);
});
test('calendar keeps the cheapest return for each origin, destination and full date',()=>{
 const ctx=vm.createContext({});vm.runInContext(section('  function calendarRows','  function render'),ctx);
 const rows=[{origin:'DOU',destination:'GRU',departure_date:'2026-10-10',return_date:'2026-10-15',price:400},{origin:'DOU',destination:'GRU',departure_date:'2026-10-10',return_date:'2026-10-12',price:300},{origin:'DOU',destination:'MIA',departure_date:'2026-10-10',price:900}];
 const result=ctx.calendarRows(rows);assert.equal(result.length,2);assert.equal(result[0].return_date,'2026-10-12');
});
test('calendar and price table render route names and links with matching travel dates',()=>{
 const elements=new Map(),q=id=>{if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',parentElement:{querySelector:()=>({textContent:''})}});return elements.get(id)};
 q('#resultScope').value='current';q('#resultSort').value='price_asc';
 const ctx=vm.createContext({q,URL,ORIGINS:[['DOU','Dourados']],DESTINATIONS:[['GRU','Guarulhos']],savedPairs:{},data:{request:{origin:'DOU',destination:'GRU',max_stops:2},results:[{price:1114,departure_date:'2026-10-14',return_date:'2026-10-15',trip_days:1}]},safe:u=>u.startsWith('https:')?u:'#',esc:s=>String(s),dateKey:()=> '2026-09-12',fmtDate:x=>x,money:x=>String(x),trendHtml:()=>'',setResultView:()=>{},resultView:'calendar'});
 vm.runInContext(section('  function airportName','  function clearForSearch'),ctx);ctx.render();
 assert.match(q('#monthRows').innerHTML,/Dourados/);assert.match(q('#monthRows').innerHTML,/Guarulhos/);
 assert.match(q('#monthCalendar').innerHTML,/<a class="month-day/);
 assert.match(decodeURIComponent(q('#monthCalendar').innerHTML),/Flights from DOU to GRU on 2026-10-14 returning 2026-10-15/);
});

test('stage percentages are calculated from each real stage',()=>{
 const ctx=vm.createContext({fmtDate:x=>x});vm.runInContext(section('  function liveProgress','  async function fetchRunState'),ctx);
 const stats={combinations:465,primary_completed:456,primary_total:465,priced_combinations:10};
 assert.equal(Math.round(ctx.liveProgress({stage:'google',stats},1).pct),98);
 assert.equal(ctx.liveProgress({stage:'fallback',stats:{...stats,fallback_done:120,fallback_total:300}},1).pct,40);
});
test('request IDs match despite a client clock offset',()=>{
 const ctx=vm.createContext({});vm.runInContext(section('  function resultMatches','  function liveProgress'),ctx);
 assert.equal(ctx.resultMatches({request,request_id:request.request_id,started_at:'2026-09-12T00:00:00Z'},request,Date.now()+86400000),true);
});
test('saved routes can be filtered by month during another search',()=>{
 const ctx=vm.createContext({});vm.runInContext(section('  function filterRows','  function resultOptions'),ctx);
 const rows=['2026-10','2026-11','2026-12','2027-01'].map((m,i)=>({origin:'DOU',destination:'GRU',departure_date:m+'-13',price:680+i}));
 assert.deepEqual(Array.from(ctx.filterRows(rows,'DOU','GRU','price_desc','2026-11'),x=>x.price),[681]);
});
test('unknown bridge job never pretends to be queued',()=>{
 const ctx=vm.createContext({PropertiesService:{getScriptProperties:()=>({getProperty:()=>null})}});
 vm.runInContext(fs.readFileSync('apps-script/Code.gs','utf8'),ctx);
 assert.equal(ctx.getProgress_('web_unreceived').status,'unknown');
});
