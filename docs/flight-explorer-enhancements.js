(() => {
  const LIVE_RAW = 'https://raw.githubusercontent.com/thenights20/viagens/flight-live/docs/data/flight-search-live.json';
  const q = s => document.querySelector(s);
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  let lastExact = null;
  let applying = false;

  function fmt(v){
    if(!v) return '';
    const [y,m,d] = String(v).slice(0,10).split('-').map(Number);
    return new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'2-digit'}).format(new Date(y,m-1,d));
  }

  function resolveDestination(){
    const raw = String(q('#monthDestination')?.value || '').trim();
    if(/^[A-Za-z]{3}$/.test(raw)) return raw.toUpperCase();
    const list = q('#monthDestinations');
    if(!list) return '';
    const opt = [...list.options].find(o => String(o.value).trim().toLowerCase() === raw.toLowerCase());
    const candidate = String(opt?.label || opt?.textContent || '').trim();
    return /^[A-Za-z]{3}$/.test(candidate) ? candidate.toUpperCase() : '';
  }

  function currentMonth(){
    const range = q('#monthPeriodMode')?.value === 'range';
    return range ? String(q('#rangeStart')?.value || '').slice(0,7) : String(q('#monthValue')?.value || '');
  }

  function matchesCurrent(live){
    const r = live?.request || {};
    const origin = String(q('#monthOrigin')?.value || '').toUpperCase();
    const dest = resolveDestination();
    const month = currentMonth();
    return !!(r.origin && r.destination && r.month && r.origin === origin && r.destination === dest && r.month === month);
  }

  function isSearching(){
    const b = q('#monthSearchButton');
    return !!b && (b.disabled || /pesquisando/i.test(b.textContent || ''));
  }

  function exactProgress(live){
    const s = live.stats || {};
    const stage = String(live.stage || 'starting');
    const total = Number(s.combinations || 0);
    const primary = Number(s.primary_completed ?? s.processed_combinations ?? 0);
    const primaryTotal = Number(s.primary_total || total);
    const fb = Number(s.fallback_done || 0);
    const fbTotal = Number(s.fallback_total || 0);
    const priced = Number(s.priced_combinations || 0);
    let pct = 0, title = 'Preparando pesquisa…', done = primary, remaining = Math.max(0,total-primary), detail = 'aguardando primeiro lote';
    if(stage === 'google'){
      pct = primaryTotal ? primary / primaryTotal * 100 : 0;
      title = `Etapa 1/2 · Google Flights · ${primary}/${primaryTotal}`;
      remaining = Math.max(0, primaryTotal-primary);
      detail = live.current_pair ? `Consultando ${fmt(live.current_pair.departure_date)} → ${fmt(live.current_pair.return_date)} · salvando automaticamente` : 'Resultados sendo salvos automaticamente';
    }else if(stage === 'fallback'){
      pct = fbTotal ? fb / fbTotal * 100 : 0;
      title = `Etapa 2/2 · Confirmação · ${fb}/${fbTotal}`;
      done = total;
      remaining = Math.max(0, fbTotal-fb);
      detail = `${priced} combinações com preço · resultados salvos`;
    }else if(stage === 'completed'){
      pct = 100; title = 'Pesquisa concluída'; done = total; remaining = 0; detail = 'Resultado e histórico salvos';
    }else if(stage === 'interrupted'){
      pct = primaryTotal ? primary / primaryTotal * 100 : 0; title = 'Pesquisa interrompida · parcial salvo'; detail = 'Tudo o que foi encontrado continua disponível';
    }
    return {pct,title,done,total,remaining,priced,detail,stage};
  }

  function applyProgress(p){
    if(!p || applying) return;
    applying = true;
    lastExact = p;
    const pct = Math.max(0,Math.min(100,Math.round(Number(p.pct)||0)));
    const fill=q('#monthProgressFill'), pctEl=q('#monthProgressPct'), stage=q('#monthProgressStage');
    const combos=q('#monthProgressCombos'), priced=q('#monthProgressPriced'), remaining=q('#monthProgressRemaining'), saved=q('#monthProgressSaved');
    if(fill) fill.style.width = pct+'%';
    if(pctEl) pctEl.textContent = pct+'%';
    if(stage) stage.textContent = p.title;
    if(combos) combos.textContent = `${p.done} / ${p.total} combinações`;
    if(priced) priced.textContent = `${p.priced} com preço`;
    if(remaining) remaining.textContent = p.stage === 'fallback' ? `faltam ${p.remaining} confirmações` : `faltam ${p.remaining}`;
    if(saved) saved.textContent = '✓ ' + p.detail;
    applying = false;
  }

  function showWaitingReal(){
    if(!isSearching() || lastExact) return;
    const pct=q('#monthProgressPct'), fill=q('#monthProgressFill'), stage=q('#monthProgressStage');
    if(pct) pct.textContent='0%';
    if(fill) fill.style.width='0%';
    if(stage && /aguardando|enviando|preparando|github/i.test(stage.textContent||'')) stage.textContent='Aguardando início no GitHub Actions · 0%';
  }

  function installSavedButtons(){
    if(q('#monthViewSavedButton')) return;
    const stop=q('#monthStopButton');
    if(!stop) return;
    const saved=document.createElement('button');
    saved.id='monthViewSavedButton'; saved.className='month-saved-live-btn'; saved.type='button'; saved.textContent='📚 Ver buscas salvas';
    const current=document.createElement('button');
    current.id='monthViewCurrentButton'; current.className='month-saved-live-btn'; current.type='button'; current.textContent='🔎 Voltar à busca atual'; current.hidden=true;
    stop.parentElement?.insertBefore(saved, stop);
    stop.parentElement?.insertBefore(current, stop);
    const style=document.createElement('style');
    style.textContent='.month-saved-live-btn{border:1px solid var(--line);background:var(--panel2);color:var(--text);font-weight:800;border-radius:8px;padding:6px 9px;cursor:pointer;font-size:11px;white-space:nowrap;margin-right:5px}.month-saved-live-btn:hover{border-color:var(--accent);color:var(--accent)}';
    document.head.appendChild(style);
    const sync=()=>{const all=q('#resultScope')?.value==='all';saved.hidden=all;current.hidden=!all;};
    saved.addEventListener('click',()=>{const scope=q('#resultScope');if(scope){scope.value='all';scope.dispatchEvent(new Event('change',{bubbles:true}));}sync();setTimeout(()=>q('#resultCaption')?.scrollIntoView({behavior:'smooth',block:'center'}),150);});
    current.addEventListener('click',()=>{const scope=q('#resultScope');if(scope){scope.value='current';scope.dispatchEvent(new Event('change',{bubbles:true}));}sync();setTimeout(()=>q('#resultCaption')?.scrollIntoView({behavior:'smooth',block:'center'}),150);});
    q('#resultScope')?.addEventListener('change',sync); sync();
  }

  async function readLive(){
    try{
      const r=await fetch(LIVE_RAW+'?t='+Date.now(),{cache:'no-store'});
      if(!r.ok) return null;
      return await r.json();
    }catch{return null;}
  }

  async function loop(){
    while(true){
      installSavedButtons();
      if(isSearching()){
        const live=await readLive();
        if(live && matchesCurrent(live)){
          lastExact=exactProgress(live); applyProgress(lastExact);
        }else{
          lastExact=null; showWaitingReal();
        }
      }else{
        lastExact=null;
      }
      await sleep(2500);
    }
  }

  const observer=new MutationObserver(()=>{installSavedButtons();if(lastExact) setTimeout(()=>applyProgress(lastExact),0);else showWaitingReal();});
  observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true});
  loop();
})();
