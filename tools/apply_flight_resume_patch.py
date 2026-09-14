from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MULTI=ROOT/'flight-month-search/multisource.py'
UI=ROOT/'docs/flight-explorer.js'
LOADER=ROOT/'docs/terabyte-live.js'


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f'Patch point not found: {label}')
    return text.replace(old,new,1)

s=MULTI.read_text(encoding='utf-8')
s=replace_once(s,
'''    merge_rows_into_history,
)

USER_AGENT''',
'''    merge_rows_into_history,
)
from resume_cache import FlightResumeCache, combo_key

USER_AGENT''','resume import')
s=replace_once(s,
'''    progress: Callable[[int, list[dict], list[str], tuple[date, date], dict[str, int]], None],
''',
'''    progress: Callable[..., None],
''','progress annotation')
s=replace_once(s,
'''                progress(completed, rows, errors, (dep, ret), dict(source_counts))
''',
'''                progress(
                    completed, rows, errors, (dep, ret), dict(source_counts),
                    {"row": dict(row) if row else None, "errors": list(worker_errors), "assigned_source": assigned},
                )
''','progress event')

old='''    publisher = GitHubLivePublisher()
    history = load_history()
    all_rows: list[dict] = []
    all_errors: list[str] = []
    completed = 0
    source_counts = {key: 0 for key in SOURCE_CATALOG}
    workers = max(4, min(14, int(os.environ.get("SEARCH_MULTI_WORKERS") or 10)))

    def decorate(payload: dict, counts: dict[str, int]) -> dict:
        payload["currency"] = "BRL"
        payload["source_strategy"] = "google_flights_with_ita_verification"
        payload["sources"] = SOURCE_CATALOG
        payload["source_health"] = source_health
        payload["active_sources"] = active_sources
        payload["source_counts"] = counts
        return payload
'''
new='''    publisher = GitHubLivePublisher()
    history = load_history()
    resume_cache = FlightResumeCache(
        publisher,
        origin=origin,
        destination=destination,
        start_date=period_start,
        end_date=period_end,
        max_stops=max_stops,
    )
    resume_cache.load()
    reusable_records = resume_cache.reusable_records()
    reused_keys = set(reusable_records)
    reused_rows = resume_cache.reusable_rows()
    pending_combos = [(dep, ret) for dep, ret in combos if combo_key(dep, ret) not in reused_keys]

    all_rows: list[dict] = list(reused_rows)
    all_errors: list[str] = []
    completed = len(reused_keys)
    attempted_this_run = 0
    source_counts = {key: 0 for key in SOURCE_CATALOG}
    workers = max(2, min(6, int(os.environ.get("SEARCH_MULTI_WORKERS") or 4)))

    def decorate(payload: dict, counts: dict[str, int]) -> dict:
        cache_counts = resume_cache.counts()
        payload["currency"] = "BRL"
        payload["source_strategy"] = "google_flights_with_ita_verification"
        payload["sources"] = SOURCE_CATALOG
        payload["source_health"] = source_health
        payload["active_sources"] = active_sources
        payload["source_counts"] = counts
        payload["resume"] = {
            "enabled": True,
            "window_minutes": 60,
            "cache_id": resume_cache.cache_id,
            "reused_combinations": len(reused_keys),
            "searched_this_run": attempted_this_run,
            "remaining_this_run": max(0, len(pending_combos) - attempted_this_run),
            "reusable_now": cache_counts["reusable"],
            "retryable_for_next_run": max(0, len(combos) - cache_counts["reusable"]),
            "saved_records": cache_counts["saved_records"],
            "saved_errors": cache_counts["errors"],
            "checkpoint_path": resume_cache.path,
        }
        return payload
'''
s=replace_once(s,old,new,'resume initialization')

s=replace_once(s,
'''            start_date=period_start, end_date=period_end, mode=period_mode, all_rows=[], history=history,
            total=len(combos), primary_completed=0, primary_total=len(combos), fallback_done=0, fallback_total=0,
''',
'''            start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
            total=len(combos), primary_completed=completed, primary_total=len(combos), fallback_done=0, fallback_total=0,
''','initial reused progress')
s=replace_once(s,
'''    publisher.publish(initial, f"live: iniciar busca multifonte {request_id}", force=True, completed=0)
''',
'''    publisher.publish(initial, f"live: iniciar busca Google+ITA {request_id}", force=True, completed=completed)
''','initial publish')

old='''    def publish_progress(
        done: int,
        rows: list[dict],
        errors: list[str],
        current_pair: tuple[date, date],
        counts: dict[str, int],
    ) -> None:
        nonlocal completed, all_rows, all_errors, source_counts
        completed = done
        all_rows = list(rows)
        all_errors = list(errors)[-MAX_ERRORS:]
        source_counts = counts
        payload = decorate(
            make_payload(
                request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
                start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
                total=len(combos), primary_completed=done, primary_total=len(combos), fallback_done=0, fallback_total=0,
                status="running", stage="multisource", started_at=started_iso, errors=all_errors,
            ),
            counts,
        )
        payload["current_pair"] = {
            "departure_date": current_pair[0].isoformat(),
            "return_date": current_pair[1].isoformat(),
        }
        publisher.publish(payload, f"live: {request_id} multifonte {done}/{len(combos)}", completed=done)
'''
new='''    def publish_progress(
        done: int,
        rows: list[dict],
        errors: list[str],
        current_pair: tuple[date, date],
        counts: dict[str, int],
        event: dict,
    ) -> None:
        nonlocal completed, attempted_this_run, all_rows, all_errors, source_counts
        attempted_this_run = done
        completed = len(reused_keys) + done
        resume_cache.record(
            current_pair[0], current_pair[1],
            row=event.get("row"),
            errors=event.get("errors") or [],
            source=str(event.get("assigned_source") or "google"),
        )
        resume_cache.save()
        all_rows = list(reused_rows) + list(rows)
        all_errors = list(errors)[-MAX_ERRORS:]
        source_counts = counts
        payload = decorate(
            make_payload(
                request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
                start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
                total=len(combos), primary_completed=completed, primary_total=len(combos), fallback_done=0, fallback_total=0,
                status="running", stage="multisource", started_at=started_iso, errors=all_errors,
            ),
            counts,
        )
        payload["current_pair"] = {
            "departure_date": current_pair[0].isoformat(),
            "return_date": current_pair[1].isoformat(),
        }
        publisher.publish(payload, f"live: {request_id} Google+ITA {completed}/{len(combos)}", completed=completed)
'''
s=replace_once(s,old,new,'progress resume')

s=replace_once(s,
'''        rows, errors, source_counts = run_sharded(
            origin, destination, combos, max_stops, workers, active_sources, publish_progress
        )
        all_rows = dedupe(rows)
        all_errors = errors[-MAX_ERRORS:]

        final = decorate(
''',
'''        rows, errors, source_counts = run_sharded(
            origin, destination, pending_combos, max_stops, workers, active_sources, publish_progress
        )
        attempted_this_run = len(pending_combos)
        completed = len(reused_keys) + len(pending_combos)
        all_rows = dedupe(list(reused_rows) + list(rows))
        all_errors = errors[-MAX_ERRORS:]
        resume_cache.save(force=True)

        final = decorate(
''','run pending only')

s=replace_once(s,
'''        publisher.publish(final, f"live: concluir busca multifonte {request_id}", force=True, completed=len(combos))

        print(
            f"Busca Google+ITA {request_id} {origin}->{destination} "
            f"{period_start.isoformat()}..{period_end.isoformat()}: "
            f"{len(all_rows)}/{len(combos)} combinações com preço; "
            f"ativas={active_sources}; fontes={source_counts}; moeda=BRL"
        )
''',
'''        publisher.publish(final, f"live: concluir busca Google+ITA {request_id}", force=True, completed=len(combos))

        print(
            f"Busca Google+ITA {request_id} {origin}->{destination} "
            f"{period_start.isoformat()}..{period_end.isoformat()}: "
            f"{len(all_rows)}/{len(combos)} combinações com preço; "
            f"reaproveitadas={len(reused_keys)}; pesquisadas_agora={len(pending_combos)}; "
            f"ativas={active_sources}; fontes={source_counts}; moeda=BRL"
        )
''','final message')
s=replace_once(s,
'''    except BaseException as exc:
        partial = decorate(
''',
'''    except BaseException as exc:
        resume_cache.save(force=True)
        partial = decorate(
''','force checkpoint on failure')
MULTI.write_text(s,encoding='utf-8')

u=UI.read_text(encoding='utf-8')
old="""  function liveProgress(live,elapsed){const s=live.stats||{},stage=live.stage||'starting',total=Number(s.combinations||0),primary=Number(s.primary_completed??s.processed_combinations??0),primaryTotal=Number(s.primary_total||total),fb=Number(s.fallback_done||0),fbTotal=Number(s.fallback_total||0),priced=Number(s.priced_combinations||0);let pct=0,label='Preparando pesquisa…',done=Math.min(primary,total),remaining=Math.max(0,total-done),detail='aguardando primeiro lote';if(stage==='google'){pct=primaryTotal?primary/primaryTotal*100:0;label=`Etapa 1/2 · Google Flights · ${primary}/${primaryTotal}`;remaining=Math.max(0,primaryTotal-primary);detail=live.current_pair?`Consultando ${fmtDate(live.current_pair.departure_date)} → ${fmtDate(live.current_pair.return_date)} · salvo automaticamente`:`${priced} com preço · salvo automaticamente`;}else if(stage==='fallback'){pct=fbTotal?fb/fbTotal*100:0;label=`Etapa 2/2 · Confirmação · ${fb}/${fbTotal}`;done=total;remaining=Math.max(0,fbTotal-fb);detail=`${priced} combinações com preço · resultados salvos`;}else if(stage==='completed'){pct=100;label='Pesquisa concluída';done=total;remaining=0;detail='Resultado e histórico salvos';}else if(stage==='interrupted'){pct=primaryTotal?primary/primaryTotal*100:0;label='Pesquisa interrompida · parcial preservado';detail='Tudo o que foi encontrado continua salvo';}return{pct,stage:label,done,total,priced,remaining,elapsed,detail};}
"""
new="""  function liveProgress(live,elapsed){const s=live.stats||{},stage=live.stage||'starting',total=Number(s.combinations||0),primary=Number(s.primary_completed??s.processed_combinations??0),primaryTotal=Number(s.primary_total||total),fb=Number(s.fallback_done||0),fbTotal=Number(s.fallback_total||0),priced=Number(s.priced_combinations||0),resume=live.resume||{},reused=Number(resume.reused_combinations||0);let pct=0,label='Preparando pesquisa…',done=Math.min(primary,total),remaining=Math.max(0,total-done),detail=reused?`${reused} combinações reaproveitadas da última hora`:'aguardando primeiro lote';if(stage==='multisource'){pct=total?done/total*100:0;label=`Google Flights · ${done}/${total}`;remaining=Math.max(0,total-done);detail=`${reused?reused+' reaproveitadas · ':''}${Number(resume.searched_this_run||0)} pesquisadas agora · ${priced} com preço · checkpoint automático`;}else if(stage==='google'){pct=primaryTotal?primary/primaryTotal*100:0;label=`Etapa 1/2 · Google Flights · ${primary}/${primaryTotal}`;remaining=Math.max(0,primaryTotal-primary);detail=live.current_pair?`Consultando ${fmtDate(live.current_pair.departure_date)} → ${fmtDate(live.current_pair.return_date)} · salvo automaticamente`:`${priced} com preço · salvo automaticamente`;}else if(stage==='fallback'){pct=fbTotal?fb/fbTotal*100:0;label=`Etapa 2/2 · Confirmação · ${fb}/${fbTotal}`;done=total;remaining=Math.max(0,fbTotal-fb);detail=`${priced} combinações com preço · resultados salvos`;}else if(stage==='completed'){pct=100;label='Pesquisa concluída';done=total;remaining=0;detail=`Resultado salvo${reused?' · '+reused+' combinações reaproveitadas da última hora':''}`;}else if(stage==='interrupted'){pct=primaryTotal?primary/primaryTotal*100:0;label='Pesquisa interrompida · parcial preservado';detail=`Checkpoint salvo${reused?' · '+reused+' combinações reaproveitadas':''}`;}return{pct,stage:label,done,total,priced,remaining,elapsed,detail};}
"""
u=replace_once(u,old,new,'UI resume progress')
UI.write_text(u,encoding='utf-8')

l=LOADER.read_text(encoding='utf-8')
l=replace_once(l,"./flight-explorer.js?v=20260913-airports-1","./flight-explorer.js?v=20260914-resume-1",'flight explorer cache bust')
LOADER.write_text(l,encoding='utf-8')
print('Flight resume patch applied')
