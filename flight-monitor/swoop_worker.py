from __future__ import annotations

import json
import sys
from datetime import date


def _google_url(origin: str, destination: str, dep: str, ret: str) -> str:
    from urllib.parse import quote_plus
    query = f"Flights from {origin} to {destination} on {dep} returning {ret}"
    return "https://www.google.com/travel/flights?q=" + quote_plus(query)


def _airline(option) -> str:
    names: list[str] = []
    for leg in getattr(option, "legs", []) or []:
        itinerary = getattr(leg, "itinerary", None)
        if itinerary is None:
            continue
        for name in getattr(itinerary, "airline_names", []) or []:
            if name and name not in names:
                names.append(str(name))
    return ", ".join(names) if names else "Google Flights"


def _duration_stops(option) -> tuple[int, int]:
    duration = 0
    stops = 0
    for leg in getattr(option, "legs", []) or []:
        itinerary = getattr(leg, "itinerary", None)
        if itinerary is None:
            continue
        segments = list(getattr(itinerary, "segments", []) or [])
        if segments:
            stops += max(0, len(segments) - 1)
        value = getattr(itinerary, "duration_minutes", None)
        if value is None:
            value = getattr(itinerary, "duration", None)
        try:
            duration += int(value or 0)
        except (TypeError, ValueError):
            pass
    return duration, stops


def exact(payload: dict) -> dict | None:
    from swoop import Passengers, SORT_CHEAPEST, TransportConfig, search

    result = search(
        payload["origin"],
        payload["destination"],
        payload["departure_date"],
        return_date=payload["return_date"],
        cabin="economy",
        passengers=Passengers(adults=int(payload.get("adults", 1))),
        max_stops=int(payload.get("max_stops", 2)),
        sort=SORT_CHEAPEST,
        include_basic_economy=True,
        transport=TransportConfig(country="BR", timeout=70, retries=1),
    )
    options = [x for x in (result.results or []) if getattr(x, "price", None)]
    if not options:
        return None
    option = min(options, key=lambda x: int(x.price))
    duration, stops = _duration_stops(option)
    return {
        "origin": payload["origin"],
        "destination": payload["destination"],
        "departure_date": payload["departure_date"],
        "return_date": payload["return_date"],
        "airline": _airline(option),
        "price": round(float(option.price), 2),
        "duration": f"{duration // 60}h {duration % 60:02d}min" if duration else "",
        "duration_minutes": duration,
        "stops": "Direto" if stops == 0 else f"{stops} escala" + ("s" if stops != 1 else ""),
        "stops_count": stops,
        "departure": "",
        "arrival": "",
        "url": _google_url(payload["origin"], payload["destination"], payload["departure_date"], payload["return_date"]),
        "provider": "swoop",
    }


def discovery(payload: dict) -> list[dict]:
    from swoop import Passengers, TransportConfig, deals

    result = deals(
        payload["origin"],
        cabin="economy",
        max_stops=int(payload.get("max_stops", 2)),
        passengers=Passengers(adults=1),
        include_basic_economy=True,
        min_discount_pct=int(payload.get("min_discount_pct", 0)) or None,
        transport=TransportConfig(country="BR", timeout=70, retries=1),
    )
    rows: list[dict] = []
    for item in result.deals or []:
        if not item.destination or not item.departure_date or not item.return_date or not item.price:
            continue
        rows.append({
            "origin": item.origin or payload["origin"],
            "destination": item.destination,
            "destination_name": item.destination_city or item.destination,
            "destination_country": item.destination_country or "",
            "departure_date": item.departure_date,
            "return_date": item.return_date,
            "airline": ", ".join(item.airline_names or []) or ", ".join(item.airlines or []) or "Google Flights",
            "price": round(float(item.price), 2),
            "duration": f"{int(item.duration_minutes) // 60}h {int(item.duration_minutes) % 60:02d}min" if item.duration_minutes else "",
            "duration_minutes": int(item.duration_minutes or 0),
            "stops": "Direto" if item.stops == 0 else (f"{item.stops} escala" + ("s" if item.stops != 1 else "") if item.stops is not None else ""),
            "stops_count": int(item.stops or 0),
            "departure": "",
            "arrival": "",
            "url": item.booking_url or _google_url(payload["origin"], item.destination, item.departure_date, item.return_date),
            "provider": "swoop-deals",
            "provider_typical_price": float(item.typical_price) if item.typical_price else None,
            "provider_discount_pct": float(item.discount_pct) if item.discount_pct is not None else None,
            "discovered": True,
        })
    return rows


def main() -> None:
    payload = json.loads(sys.stdin.read())
    mode = payload.pop("mode")
    if mode == "exact":
        result = exact(payload)
    elif mode == "discovery":
        result = discovery(payload)
    else:
        raise SystemExit(f"modo desconhecido: {mode}")
    sys.stdout.write(json.dumps({"ok": True, "result": result}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        sys.stdout.write(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        raise SystemExit(0)
