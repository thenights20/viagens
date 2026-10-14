"""Combined flight search: multiple airports and explicit outbound/return dates.

The original multisource.py remains the engine for a single normal route.
This runner shares its price collector, history and resumable checkpoints,
but searches all requested routes inside one GitHub Actions run.
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

from multisource import MAX_ERRORS, SOURCE_CATALOG, preflight_sources, query_one
from resume_cache import FlightResumeCache, combo_key
from search import (
    GitHubLivePublisher,
    HISTORY_PATH,
    OUTPUT_PATH,
    build_combinations,
    dedupe,
    load_history,
    make_payload,
    merge_rows_into_history,
    month_bounds,
)


def iata_list(value: str) -> list[str]:
    codes = list(dict.fromkeys(x.strip().upper() for x in value.split(",") if x.strip()))
    if not codes or any(not re.fullmatch(r"[A-Z]{3}", x) for x in codes):
        raise ValueError("Informe aeroportos IATA válidos, separados por vírgula.")
    return codes


def date_list(value: str) -> list[date]:
    values = list(dict.fromkeys(x.strip() for x in value.split(",") if x.strip()))
    if not values:
        raise ValueError("Informe ao menos uma data válida.")
    return sorted(date.fromisoformat(x) for x in values)


def date_pairs(mode: str, month: str, start_raw: str, end_raw: str, today: date):
    if mode == "dates":
        departures = date_list(start_raw)
        returns = date_list(end_raw)
        pairs = [(d, r) for d in departures for r in returns if d > today and r > d]
        return sorted(set(pairs)), departures, returns
    if mode == "range":
        first, last = date.fromisoformat(start_raw), date.fromisoformat(end_raw)
        if first >= last:
            raise ValueError("A data final precisa ser posterior à inicial.")
    elif mode == "month":
        first, last = month_bounds(month)
    else:
        raise ValueError("Tipo de período desconhecido.")
    return build_combinations(first, last, today), [], []


def main() -> None:
    origins = iata_list(os.environ.get("SEARCH_ORIGIN", "GRU"))
    destinations = iata_list(os.environ.get("SEARCH_DESTINATION", "MIA"))
    month = os.environ.get("SEARCH_MONTH", "2026-10").strip()
    mode = os.environ.get("SEARCH_PERIOD_MODE", "month").strip().lower()
    start_raw = os.environ.get("SEARCH_START_DATE", "").strip()
    end_raw = os.environ.get("SEARCH_END_DATE", "").strip()
    max_stops = int(os.environ.get("SEARCH_MAX_STOPS", "2"))
    request_id = os.environ.get("SEARCH_REQUEST_ID", "manual").strip()[:80]
    if not 0 <= max_stops <= 2:
        raise SystemExit("Número de escalas inválido.")

    started = datetime.now(timezone.utc)
    started_at = started.isoformat().replace("+00:00", "Z")
    date_combos, dep_dates, ret_dates = date_pairs(mode, month, start_raw, end_raw, started.date())
    routes = [(o, d) for o in origins for d in destinations if o != d]
    if not routes:
        raise SystemExit("Nenhuma rota válida: origem e destino não podem ser iguais.")
    if not date_combos:
        raise SystemExit("Nenhuma combinação de ida e volta em datas futuras.")

    first_day = min(d for d, _ in date_combos)
    last_day = max(r for _, r in date_combos)
    month = first_day.strftime("%Y-%m") if mode == "dates" else month
    publisher = GitHubLivePublisher()
    history = load_history()
    active_sources, source_health = preflight_sources(
        routes[0][0], routes[0][1], date_combos[0][0], date_combos[0][1], max_stops
    )
    caches: dict[tuple[str, str], FlightResumeCache] = {}
    reused_rows: list[dict] = []
    pending: list[tuple[str, str, date, date]] = []
    reused_count = 0

    for origin, destination in routes:
        cache = FlightResumeCache(
            publisher, origin=origin, destination=destination,
            start_date=first_day, end_date=last_day, max_stops=max_stops
        )
        cache.load()
        caches[(origin, destination)] = cache
        reusable = cache.reusable_records()
        for dep, ret in date_combos:
            existing = reusable.get(combo_key(dep, ret))
            if existing:
                reused_count += 1
                if existing.get("status") == "priced" and isinstance(existing.get("row"), dict):
                    row = dict(existing["row"])
                    row["origin"] = origin
                    row["destination"] = destination
                    reused_rows.append(row)
            else:
                pending.append((origin, destination, dep, ret))

    total = len(routes) * len(date_combos)
    all_rows = list(reused_rows)
    errors: list[str] = []
    attempted = 0
    counts = {key: 0 for key in SOURCE_CATALOG}
    origin_text, destination_text = ",".join(origins), ",".join(destinations)

    def snapshot(status: str, stage: str) -> dict:
        payload = make_payload(
            request_id=request_id, origin=origin_text, destination=destination_text,
            month=month, max_stops=max_stops, start_date=first_day, end_date=last_day,
            mode=mode, all_rows=all_rows, history=history, total=total,
            primary_completed=reused_count + attempted, primary_total=total,
            fallback_done=0, fallback_total=0, status=status, stage=stage,
            started_at=started_at, errors=errors
        )
        payload["request"].update({
            "origins": origins,
            "destinations": destinations,
            "departure_dates": [x.isoformat() for x in dep_dates],
            "return_dates": [x.isoformat() for x in ret_dates],
        })
        saved = [c.counts() for c in caches.values()]
        payload.update({
            "currency": "BRL",
            "source_strategy": "google_flights_with_ita_verification",
            "sources": SOURCE_CATALOG,
            "source_health": source_health,
            "active_sources": active_sources,
            "source_counts": counts,
            "resume": {
                "enabled": True, "window_minutes": 60,
                "cache_id": "multi-" + request_id,
                "reused_combinations": reused_count,
                "searched_this_run": attempted,
                "remaining_this_run": max(0, len(pending) - attempted),
                "reusable_now": sum(x["reusable"] for x in saved),
                "retryable_for_next_run": max(0, total - sum(x["reusable"] for x in saved)),
                "saved_records": sum(x["saved_records"] for x in saved),
                "saved_errors": sum(x["errors"] for x in saved),
                "checkpoint_path": next(iter(caches.values())).path,
                "checkpoint_paths": [c.path for c in caches.values()],
            },
        })
        return payload

    publisher.publish(snapshot("running", "multisource"),
                      "live: iniciar busca combinada " + request_id, force=True, completed=reused_count)

    try:
        workers = max(2, min(6, int(os.environ.get("SEARCH_MULTI_WORKERS", "4"))))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(query_one, "google", o, d, dep, ret, max_stops): (o, d, dep, ret)
                for o, d, dep, ret in pending
            }
            for future in as_completed(futures):
                origin, destination, dep, ret = futures[future]
                try:
                    row, problems, source = future.result()
                except Exception as exc:
                    row, problems, source = None, [f"{type(exc).__name__}: {exc}"], "google"
                    traceback.print_exc(file=sys.stderr)
                attempted += 1
                counts[source] = counts.get(source, 0) + 1
                if row:
                    row = dict(row)
                    row["origin"], row["destination"] = origin, destination
                    all_rows.append(row)
                for problem in problems:
                    if len(errors) < MAX_ERRORS:
                        errors.append(f"{origin}->{destination} {dep}->{ret}: {problem}")
                cache = caches[(origin, destination)]
                cache.record(dep, ret, row=row, errors=problems, source=source)
                cache.save()
                payload = snapshot("running", "multisource")
                payload["current_pair"] = {
                    "origin": origin, "destination": destination,
                    "departure_date": dep.isoformat(), "return_date": ret.isoformat()
                }
                publisher.publish(
                    payload, f"live: {request_id} combinada {reused_count + attempted}/{total}",
                    completed=reused_count + attempted
                )

        for cache in caches.values():
            cache.save(force=True)
        all_rows = dedupe(all_rows)
        final = snapshot("completed", "completed")
        observed = str(final.get("updated_at") or started_at)
        history = merge_rows_into_history(
            history, all_rows, origin_text, destination_text, max_stops, observed
        )
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        publisher.publish(final, "live: concluir busca combinada " + request_id,
                          force=True, completed=total)
        print(f"Busca combinada {request_id}: {len(routes)} rotas × "
              f"{len(date_combos)} pares = {total} combinações; "
              f"{len(all_rows)} com preço, {reused_count} reaproveitadas.")
    except BaseException as exc:
        for cache in caches.values():
            cache.save(force=True)
        errors.append(f"{type(exc).__name__}: {exc}")
        publisher.publish(snapshot("partial", "interrupted"),
                          "live: parcial busca combinada " + request_id,
                          force=True, completed=reused_count + attempted)
        raise


if __name__ == "__main__":
    main()
