from __future__ import annotations

from datetime import date
from typing import Any

from search_core import query_cheapest


def _google_query_url(origin: str, destination: str, dep: date, ret: date) -> str:
    from search_core import google_url
    return google_url(origin, destination, dep, ret)


def search_fast_flights(origin: str, destination: str, dep: date, ret: date, params: dict[str, Any]) -> dict | None:
    deal = query_cheapest(origin, destination, dep, ret, params)
    if not deal:
        return None
    return {
        "origin": origin,
        "destination": destination,
        "departure_date": deal.departure_date,
        "return_date": deal.return_date,
        "airline": deal.airline,
        "price": round(float(deal.price_value), 2),
        "duration": deal.duration,
        "duration_minutes": int(deal.duration_minutes or 0),
        "stops": deal.stops,
        "stops_count": int(deal.stops_count or 0),
        "departure": deal.departure,
        "arrival": deal.arrival,
        "url": deal.query_url,
        "provider": "fast-flights",
    }


def _swoop_airline(option: Any) -> str:
    names: list[str] = []
    for leg in getattr(option, "legs", []) or []:
        itinerary = getattr(leg, "itinerary", None)
        if itinerary is None:
            continue
        for name in getattr(itinerary, "airline_names", []) or []:
            if name and name not in names:
                names.append(str(name))
    return ", ".join(names) if names else "Google Flights"


def _swoop_duration_and_stops(option: Any) -> tuple[int, int]:
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


def search_swoop(origin: str, destination: str, dep: date, ret: date, params: dict[str, Any]) -> dict | None:
    from swoop import Passengers, SORT_CHEAPEST, TransportConfig, search

    result = search(
        origin,
        destination,
        dep.isoformat(),
        return_date=ret.isoformat(),
        cabin="economy",
        passengers=Passengers(adults=int(params.get("adults", 1))),
        max_stops=int(params.get("max_stops", 2)),
        sort=SORT_CHEAPEST,
        include_basic_economy=True,
        transport=TransportConfig(country="BR", timeout=70, retries=1),
    )
    options = [x for x in (result.results or []) if getattr(x, "price", None)]
    if not options:
        return None
    option = min(options, key=lambda x: int(x.price))
    duration, stops = _swoop_duration_and_stops(option)
    return {
        "origin": origin,
        "destination": destination,
        "departure_date": dep.isoformat(),
        "return_date": ret.isoformat(),
        "airline": _swoop_airline(option),
        "price": round(float(option.price), 2),
        "duration": f"{duration // 60}h {duration % 60:02d}min" if duration else "",
        "duration_minutes": duration,
        "stops": "Direto" if stops == 0 else f"{stops} escala" + ("s" if stops != 1 else ""),
        "stops_count": stops,
        "departure": "",
        "arrival": "",
        "url": _google_query_url(origin, destination, dep, ret),
        "provider": "swoop",
    }


def search_with_fallback(origin: str, destination: str, dep: date, ret: date, params: dict[str, Any], config: dict) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    providers = config.get("providers", {})
    if providers.get("fast_flights", True):
        try:
            result = search_fast_flights(origin, destination, dep, ret, params)
            if result:
                return result, errors
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fast-flights: {exc}")

    if providers.get("swoop_fallback", True):
        try:
            result = search_swoop(origin, destination, dep, ret, params)
            if result:
                result["fallback_used"] = True
                return result, errors
        except Exception as exc:  # noqa: BLE001
            errors.append(f"swoop: {exc}")
    return None, errors


def discover_swoop_deals(origin: dict, config: dict) -> tuple[list[dict], str | None]:
    if not config.get("providers", {}).get("swoop_discovery", True):
        return [], None
    try:
        from swoop import Passengers, TransportConfig, deals

        result = deals(
            origin["code"],
            cabin="economy",
            max_stops=int(config["scan"].get("max_stops", 2)),
            passengers=Passengers(adults=1),
            include_basic_economy=bool(config.get("providers", {}).get("include_basic_economy", True)),
            min_discount_pct=int(config["scan"].get("discovery_min_discount_pct", 0)) or None,
            transport=TransportConfig(country="BR", timeout=70, retries=1),
        )
        rows: list[dict] = []
        for item in result.deals or []:
            if not item.destination or not item.departure_date or not item.return_date or not item.price:
                continue
            rows.append({
                "origin": item.origin or origin["code"],
                "origin_name": origin["name"],
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
                "url": item.booking_url or _google_query_url(origin["code"], item.destination, date.fromisoformat(item.departure_date), date.fromisoformat(item.return_date)),
                "provider": "swoop-deals",
                "provider_typical_price": float(item.typical_price) if item.typical_price else None,
                "provider_discount_pct": float(item.discount_pct) if item.discount_pct is not None else None,
                "discovered": True,
            })
        return rows, None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def revalidate_candidate(candidate: dict, config: dict) -> tuple[str, float | None, str | None]:
    """Reconsulta o mesmo itinerário com a implementação alternativa.

    Retorna (status, preço, erro). Ambos os coletores consultam Google Flights,
    portanto isto confirma por uma segunda implementação, não por uma segunda OTA.
    """
    if not config.get("providers", {}).get("swoop_confirm", True):
        return "none", None, None
    origin = candidate["origin"]
    destination = candidate["destination"]
    dep = date.fromisoformat(candidate["departure_date"])
    ret = date.fromisoformat(candidate["return_date"])
    params = {"max_stops": int(config["scan"].get("max_stops", 2)), "adults": 1, "currency": "BRL"}
    primary = str(candidate.get("provider", ""))
    try:
        if primary.startswith("swoop"):
            alt = search_fast_flights(origin, destination, dep, ret, params)
        else:
            alt = search_swoop(origin, destination, dep, ret, params)
        if not alt:
            return "none", None, None
        current = float(candidate["price"])
        checked = float(alt["price"])
        tolerance = float(config["scan"].get("confirmation_tolerance_pct", 8)) / 100.0
        if current > 0 and abs(checked - current) / current <= tolerance:
            return "second_collector", checked, None
        return "price_mismatch", checked, None
    except Exception as exc:  # noqa: BLE001
        return "none", None, str(exc)
