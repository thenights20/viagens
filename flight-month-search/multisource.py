from __future__ import annotations

import json
import os
import re
import sys
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from html import unescape
from typing import Callable
from urllib.parse import quote_plus

import requests

from search import (
    GitHubLivePublisher,
    HISTORY_PATH,
    OUTPUT_PATH,
    build_combinations,
    decode_origin_and_period,
    dedupe,
    fast_query,
    load_history,
    make_payload,
    merge_rows_into_history,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0 Safari/537.36"
)
REQUEST_TIMEOUT = 14
MAX_ERRORS = 60

SOURCE_CATALOG = {
    "google": {"label": "Google Flights", "auto_candidate": True},
    "ita": {"label": "ITA Matrix", "auto_candidate": False},
}

AUTO_CANDIDATES = []


def google_url(origin: str, destination: str, dep: str, ret: str) -> str:
    query = f"Flights from {origin} to {destination} on {dep} returning {ret}"
    return f"https://www.google.com/travel/flights?q={quote_plus(query)}&curr=BRL&hl=pt-BR"


def decolar_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return (
        "https://www.decolar.com/shop/flights/results/roundtrip/"
        f"{origin}/{destination}/{dep}/{ret}/1/0/0"
        "?from=SB&di=1-0&reSearch=true&currency=BRL"
    )


def kayak_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return f"https://www.kayak.com.br/flights/{origin}-{destination}/{dep}/{ret}?sort=bestflight_a&currency=BRL"


def momondo_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return f"https://www.momondo.com.br/flight-search/{origin}-{destination}/{dep}/{ret}?sort=bestflight_a&currency=BRL"


def skyscanner_url(origin: str, destination: str, dep: str, ret: str) -> str:
    d1 = dep[2:].replace("-", "")
    d2 = ret[2:].replace("-", "")
    return (
        f"https://www.skyscanner.com.br/transporte/voos/{origin.lower()}/{destination.lower()}/{d1}/{d2}/"
        "?adultsv2=1&cabinclass=economy&rtn=1&currency=BRL&locale=pt-BR&market=BR"
    )


def vaidepromo_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return (
        "https://www.vaidepromo.com.br/passagens-aereas/"
        f"?origem={origin}&destino={destination}&ida={dep}&volta={ret}"
    )


def viajanet_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return f"https://www.viajanet.com.br/?origem={origin}&destino={destination}&ida={dep}&volta={ret}"


def cvc_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return (
        "https://www.cvc.com.br/passagens-aereas"
        f"?origem={origin}&destino={destination}&ida={dep}&volta={ret}"
    )


def edestinos_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return (
        "https://www.edestinos.com.br/"
        f"?origin={origin}&destination={destination}&departure={dep}&return={ret}&currency=BRL"
    )


def trip_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return (
        "https://br.trip.com/flights/"
        f"?dcity={origin.lower()}&acity={destination.lower()}&ddate={dep}&rdate={ret}&triptype=rt&curr=BRL"
    )


def ita_url(origin: str, destination: str, dep: str, ret: str) -> str:
    return (
        "https://matrix.itasoftware.com/search"
        f"#from={origin}&to={destination}&depart={dep}&return={ret}&currency=BRL"
    )


URL_BUILDERS = {
    "google": google_url,
    "ita": ita_url,
}


def search_links(origin: str, destination: str, dep: str, ret: str) -> dict[str, str]:
    return {key: builder(origin, destination, dep, ret) for key, builder in URL_BUILDERS.items()}


def _brl_number(raw: str) -> float | None:
    value = raw.strip().replace("\xa0", " ").replace("R$", "").replace("BRL", "").strip()
    value = re.sub(r"[^0-9,.-]", "", value)
    if not value:
        return None
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", value):
        value = value.replace(".", "")
    try:
        number = float(value)
    except ValueError:
        return None
    return round(number, 2) if 40 <= number <= 200000 else None


def _looks_like_translation_context(context: str) -> bool:
    return bool(re.search(
        r"(?:WIZARD_|PLACEHOLDER|PROMPT_|SUGGESTION_|AUTOCOMPLETE_|\\\"ui\.|ui\.[a-z0-9_.-]+)",
        context,
        flags=re.I,
    ))


def extract_brl_prices(text: str) -> list[float]:
    """Extract only BRL values with local currency evidence.

    Generic JSON keys such as `price: 50` are intentionally ignored because
    meta-search pages contain many unrelated values (cars, hotels, examples,
    baggage, ads). Visible R$ examples inside translation dictionaries are also
    ignored. When no trustworthy fare remains, the shard falls back to Google.
    """
    text = unescape(text or "")
    candidates: list[float] = []

    for match in re.finditer(
        r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*(?:,[0-9]{2})?|[0-9]+(?:,[0-9]{2})?)",
        text,
        flags=re.I,
    ):
        context = text[max(0, match.start() - 240): min(len(text), match.end() + 240)]
        if _looks_like_translation_context(context):
            continue
        value = _brl_number(match.group(1))
        if value is not None:
            candidates.append(value)

    currency_patterns = [
        r'"currency"\s*:\s*"BRL".{0,180}?"(?:amount|price|value|totalPrice|farePrice)"\s*:\s*"?([0-9]+(?:\.[0-9]{1,2})?)"?',
        r'"(?:amount|price|value|totalPrice|farePrice)"\s*:\s*"?([0-9]+(?:\.[0-9]{1,2})?)"?.{0,180}?"currency"\s*:\s*"BRL"',
    ]
    for pattern in currency_patterns:
        for match in re.finditer(pattern, text, flags=re.I | re.S):
            context = text[max(0, match.start() - 120): min(len(text), match.end() + 120)]
            if _looks_like_translation_context(context):
                continue
            value = _brl_number(match.group(1))
            if value is not None:
                candidates.append(value)

    return sorted(set(candidates))


def _date_tokens(value: str) -> set[str]:
    return {value, value.replace("-", ""), value[2:].replace("-", "")}


def _page_matches_query(response: requests.Response, origin: str, destination: str, dep_s: str, ret_s: str) -> bool:
    combined = (str(response.url) + "\n" + (response.text or "")).upper()
    if origin.upper() not in combined or destination.upper() not in combined:
        return False
    dep_ok = any(token.upper() in combined for token in _date_tokens(dep_s))
    ret_ok = any(token.upper() in combined for token in _date_tokens(ret_s))
    if not dep_ok or not ret_ok:
        return False
    lower = combined.lower()
    return any(word in lower for word in ("flight", "voo", "passagem", "fare", "airfare"))


def _page_probe(
    source: str,
    origin: str,
    destination: str,
    dep: date,
    ret: date,
    max_stops: int,
) -> tuple[dict | None, str | None]:
    if max_stops < 2:
        return None, f"{source}: filtro de escalas exige coletor estruturado"

    dep_s, ret_s = dep.isoformat(), ret.isoformat()
    url = URL_BUILDERS[source](origin, destination, dep_s, ret_s)
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Cache-Control": "no-cache",
            },
        )
        if response.status_code >= 400:
            return None, f"{source}: HTTP {response.status_code}"
        if not _page_matches_query(response, origin, destination, dep_s, ret_s):
            return None, f"{source}: página não confirmou rota/datas exatas"
        prices = extract_brl_prices(response.text)
        if not prices:
            return None, f"{source}: nenhum preço BRL confiável no HTML público"
        price = prices[0]
        label = SOURCE_CATALOG[source]["label"]
        return {
            "origin": origin,
            "destination": destination,
            "departure_date": dep_s,
            "return_date": ret_s,
            "airline": label,
            "price": price,
            "duration": "",
            "duration_minutes": 0,
            "stops": "consulte no site",
            "stops_count": None,
            "departure": "",
            "arrival": "",
            "url": url,
            "provider": label,
            "source_kind": source,
            "trip_days": (ret - dep).days,
            "currency": "BRL",
            "price_source_confidence": "exact-route-date-page",
            "search_links": search_links(origin, destination, dep_s, ret_s),
        }, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{source}: {type(exc).__name__}: {exc}"


def _google_probe(
    origin: str,
    destination: str,
    dep: date,
    ret: date,
    max_stops: int,
) -> tuple[dict | None, str | None]:
    row, error = fast_query(origin, destination, dep, ret, max_stops)
    if row:
        row = dict(row)
        row["provider"] = "Google Flights"
        row["source_kind"] = "google"
        row["currency"] = "BRL"
        row["price_source_confidence"] = "structured"
        row["url"] = google_url(origin, destination, dep.isoformat(), ret.isoformat())
        row["search_links"] = search_links(origin, destination, dep.isoformat(), ret.isoformat())
    return row, error


def preflight_sources(
    origin: str,
    destination: str,
    dep: date,
    ret: date,
    max_stops: int,
) -> tuple[list[str], dict[str, dict]]:
    """Only Google Flights may create automatic fare rows.

    ITA Matrix remains available as a route/date verification link. Generic
    agency HTML is intentionally excluded because unrelated promotional values
    can be mistaken for airfare.
    """
    health = {
        "google": {
            "enabled": True,
            "label": SOURCE_CATALOG["google"]["label"],
            "reason": "structured fare collector",
        },
        "ita": {
            "enabled": False,
            "label": SOURCE_CATALOG["ita"]["label"],
            "reason": "verification/search link only; no stable public fare API",
        },
    }
    return ["google"], health

def query_one(
    assigned: str,
    origin: str,
    destination: str,
    dep: date,
    ret: date,
    max_stops: int,
) -> tuple[dict | None, list[str], str]:
    errors: list[str] = []
    if assigned == "google":
        row, error = _google_probe(origin, destination, dep, ret, max_stops)
    else:
        row, error = _page_probe(assigned, origin, destination, dep, ret, max_stops)
    if error:
        errors.append(error)
    if row:
        row["assigned_source"] = assigned
        return row, errors, assigned

    row, error = _google_probe(origin, destination, dep, ret, max_stops)
    if error:
        errors.append(f"fallback Google: {error}")
    if row:
        row["assigned_source"] = assigned
        row["fallback_used"] = assigned != "google"
        row["fallback_from"] = SOURCE_CATALOG[assigned]["label"]
    return row, errors, assigned


def run_sharded(
    origin: str,
    destination: str,
    combos: list[tuple[date, date]],
    max_stops: int,
    workers: int,
    active_sources: list[str],
    progress: Callable[[int, list[dict], list[str], tuple[date, date], dict[str, int]], None],
) -> tuple[list[dict], list[str], dict[str, int]]:
    rows: list[dict] = []
    errors: list[str] = []
    source_counts = {key: 0 for key in SOURCE_CATALOG}
    lock = threading.Lock()
    completed = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for index, (dep, ret) in enumerate(combos):
            assigned = active_sources[index % len(active_sources)]
            futures[pool.submit(query_one, assigned, origin, destination, dep, ret, max_stops)] = (dep, ret)

        for future in as_completed(futures):
            dep, ret = futures[future]
            try:
                row, worker_errors, assigned = future.result()
            except Exception as exc:  # noqa: BLE001
                row, worker_errors, assigned = None, [f"worker: {type(exc).__name__}: {exc}"], "google"
                traceback.print_exc(file=sys.stderr)
            with lock:
                completed += 1
                source_counts[assigned] = source_counts.get(assigned, 0) + 1
                if row:
                    rows.append(row)
                for error in worker_errors:
                    if len(errors) < MAX_ERRORS:
                        errors.append(f"{dep.isoformat()}->{ret.isoformat()} {error}")
                progress(completed, rows, errors, (dep, ret), dict(source_counts))

    return rows, errors, source_counts


def main() -> None:
    raw_origin = str(os.environ.get("SEARCH_ORIGIN") or "GRU").strip().upper()
    destination = str(os.environ.get("SEARCH_DESTINATION") or "MIA").strip().upper()
    month = str(os.environ.get("SEARCH_MONTH") or "2026-10").strip()
    max_stops = int(os.environ.get("SEARCH_MAX_STOPS") or 2)
    request_id = str(os.environ.get("SEARCH_REQUEST_ID") or "manual").strip()[:80]
    requested_mode = str(os.environ.get("SEARCH_PERIOD_MODE") or "month").strip().lower()
    requested_start = str(os.environ.get("SEARCH_START_DATE") or "").strip()
    requested_end = str(os.environ.get("SEARCH_END_DATE") or "").strip()

    if requested_mode == "range" and requested_start and requested_end:
        try:
            period_start = date.fromisoformat(requested_start)
            period_end = date.fromisoformat(requested_end)
        except ValueError as exc:
            raise SystemExit("Datas do intervalo inválidas") from exc
        if period_end <= period_start:
            raise SystemExit("A data final precisa ser posterior à data inicial")
        origin = raw_origin
        period_mode = "range"
        month = period_start.strftime("%Y-%m")
    else:
        origin, period_start, period_end, period_mode = decode_origin_and_period(raw_origin, month)

    if len(origin) != 3 or len(destination) != 3 or not origin.isalpha() or not destination.isalpha():
        raise SystemExit("Origem e destino precisam ser códigos IATA de 3 letras")
    if origin == destination:
        raise SystemExit("Origem e destino não podem ser iguais")
    if not 0 <= max_stops <= 2:
        raise SystemExit("Escalas precisa ficar entre 0 e 2")

    started = datetime.now(timezone.utc)
    started_iso = started.isoformat().replace("+00:00", "Z")
    combos = build_combinations(period_start, period_end, started.date())
    if not combos:
        raise SystemExit("O período selecionado não possui pares de datas futuras")

    # One concurrent health check decides which public sources are worth using
    # for this exact route. Blocked/dynamic sources do not slow every date.
    active_sources, source_health = preflight_sources(
        origin, destination, combos[0][0], combos[0][1], max_stops
    )

    publisher = GitHubLivePublisher()
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

    initial = decorate(
        make_payload(
            request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
            start_date=period_start, end_date=period_end, mode=period_mode, all_rows=[], history=history,
            total=len(combos), primary_completed=0, primary_total=len(combos), fallback_done=0, fallback_total=0,
            status="running", stage="multisource", started_at=started_iso, errors=[],
        ),
        source_counts,
    )
    publisher.publish(initial, f"live: iniciar busca multifonte {request_id}", force=True, completed=0)

    def publish_progress(
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

    try:
        rows, errors, source_counts = run_sharded(
            origin, destination, combos, max_stops, workers, active_sources, publish_progress
        )
        all_rows = dedupe(rows)
        all_errors = errors[-MAX_ERRORS:]

        final = decorate(
            make_payload(
                request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
                start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
                total=len(combos), primary_completed=len(combos), primary_total=len(combos), fallback_done=0,
                fallback_total=0, status="completed", stage="completed", started_at=started_iso, errors=all_errors,
            ),
            source_counts,
        )

        observed_at = str(final.get("updated_at") or final.get("generated_at") or started_iso)
        history = merge_rows_into_history(history, all_rows, origin, destination, max_stops, observed_at)
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        publisher.publish(final, f"live: concluir busca multifonte {request_id}", force=True, completed=len(combos))

        print(
            f"Busca Google+ITA {request_id} {origin}->{destination} "
            f"{period_start.isoformat()}..{period_end.isoformat()}: "
            f"{len(all_rows)}/{len(combos)} combinações com preço; "
            f"ativas={active_sources}; fontes={source_counts}; moeda=BRL"
        )
    except BaseException as exc:
        partial = decorate(
            make_payload(
                request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
                start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
                total=len(combos), primary_completed=completed, primary_total=len(combos), fallback_done=0,
                fallback_total=0, status="partial", stage="interrupted", started_at=started_iso,
                errors=all_errors + [f"{type(exc).__name__}: {exc}"],
            ),
            source_counts,
        )
        publisher.publish(partial, f"live: parcial multifonte {request_id}", force=True, completed=completed)
        raise


if __name__ == "__main__":
    main()
