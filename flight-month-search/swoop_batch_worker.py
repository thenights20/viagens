from __future__ import annotations

import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus


def google_url(origin: str, destination: str, dep: str, ret: str) -> str:
    q = f"Flights from {origin} to {destination} on {dep} returning {ret}"
    return "https://www.google.com/travel/flights?q=" + quote_plus(q)


def airline(option) -> str:
    names: list[str] = []
    for leg in getattr(option, "legs", []) or []:
        itinerary = getattr(leg, "itinerary", None)
        if itinerary is None:
            continue
        for name in getattr(itinerary, "airline_names", []) or []:
            if name and str(name) not in names:
                names.append(str(name))
    return ", ".join(names) if names else "Google Flights"


def duration_stops(option) -> tuple[int, int]:
    duration = 0
    stops = 0
    for leg in getattr(option, "legs", []) or []:
        itinerary = getattr(leg, "itinerary", None)
        if itinerary is None:
            continue
        segments = list(getattr(itinerary, "segments", []) or [])
        if segments:
            stops += max(0, len(segments) - 1)
        try:
            duration += int(getattr(itinerary, "duration_minutes", None) or getattr(itinerary, "duration", None) or 0)
        except (TypeError, ValueError):
            pass
    return duration, stops


def one(payload: dict, query: dict) -> tuple[dict | None, str | None]:
    from swoop import Passengers, SORT_CHEAPEST, TransportConfig, search

    try:
        result = search(
            payload["origin"],
            payload["destination"],
            query["departure_date"],
            return_date=query["return_date"],
            cabin="economy",
            passengers=Passengers(adults=1),
            max_stops=int(payload.get("max_stops", 2)),
            sort=SORT_CHEAPEST,
            include_basic_economy=True,
            transport=TransportConfig(country="BR", timeout=35, retries=0),
        )
        options = [x for x in (result.results or []) if getattr(x, "price", None)]
        if not options:
            return None, None
        option = min(options, key=lambda x: float(x.price))
        duration, stops = duration_stops(option)
        dep, ret = query["departure_date"], query["return_date"]
        return {
            "origin": payload["origin"],
            "destination": payload["destination"],
            "departure_date": dep,
            "return_date": ret,
            "airline": airline(option),
            "price": round(float(option.price), 2),
            "duration": f"{duration // 60}h {duration % 60:02d}min" if duration else "",
            "duration_minutes": duration,
            "stops": "Direto" if stops == 0 else f"{stops} escala" + ("s" if stops != 1 else ""),
            "stops_count": stops,
            "departure": "",
            "arrival": "",
            "url": google_url(payload["origin"], payload["destination"], dep, ret),
            "provider": "swoop",
        }, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{query['departure_date']}->{query['return_date']}: {type(exc).__name__}: {exc}"


def send_progress(payload: dict, done: int, total: int, priced: int, query: dict) -> None:
    url = str(payload.get("progress_url") or "").strip()
    request_id = str(payload.get("request_id") or "").strip()
    if not url or not request_id:
        return
    total_combos = int(payload.get("total_combos") or 0)
    fast_priced = int(payload.get("fast_priced") or 0)
    pct = 76 + round((done / max(1, total)) * 18)
    body = {
        "request_id": request_id,
        "status": "running",
        "stage": "fallback",
        "percent": min(94, pct),
        "total": total_combos,
        "completed": total_combos,
        "remaining": 0,
        "priced": fast_priced + priced,
        "fallback_done": done,
        "fallback_total": total,
        "current_pair": f"{query.get('departure_date','')}→{query.get('return_date','')}",
        "message": "Complementando datas sem preço na primeira fonte.",
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "text/plain;charset=UTF-8", "User-Agent": "flight-search-swoop-progress/0.3"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as response:  # noqa: S310
            response.read(32)
    except Exception:
        pass


def main() -> None:
    payload = json.loads(sys.stdin.read())
    queries = list(payload.get("queries") or [])
    workers = max(1, min(6, int(payload.get("workers", 4))))
    results: list[dict] = []
    errors: list[str] = []
    done = 0
    last_sent_at = 0.0
    last_sent_done = -1
    step = max(3, len(queries) // 45)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, payload, query): query for query in queries}
        for future in as_completed(futures):
            query = futures[future]
            row, error = future.result()
            done += 1
            if row:
                results.append(row)
            if error and len(errors) < 30:
                errors.append(error)
            now = time.monotonic()
            if done == len(queries) or done - last_sent_done >= step or now - last_sent_at >= 3.0:
                send_progress(payload, done, len(queries), len(results), query)
                last_sent_at = now
                last_sent_done = done
    sys.stdout.write(json.dumps({"results": results, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
