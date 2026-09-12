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
