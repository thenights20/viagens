from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from search_core import query_cheapest

WORKER = Path(__file__).resolve().with_name("swoop_worker.py")


def _run_swoop(payload: dict, timeout: int = 90) -> Any:
    proc = subprocess.run(
        [sys.executable, str(WORKER)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        raise RuntimeError((proc.stderr or "Swoop sem saída").strip()[-800:])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"saída Swoop inválida: {raw[-500:]}") from exc
    if not data.get("ok"):
        raise RuntimeError(str(data.get("error") or "erro desconhecido no Swoop"))
    return data.get("result")


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


def search_swoop(origin: str, destination: str, dep: date, ret: date, params: dict[str, Any]) -> dict | None:
    return _run_swoop({
        "mode": "exact",
        "origin": origin,
        "destination": destination,
        "departure_date": dep.isoformat(),
        "return_date": ret.isoformat(),
        "max_stops": int(params.get("max_stops", 2)),
        "adults": int(params.get("adults", 1)),
    })


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
        rows = _run_swoop({
            "mode": "discovery",
            "origin": origin["code"],
            "max_stops": int(config["scan"].get("max_stops", 2)),
            "min_discount_pct": int(config["scan"].get("discovery_min_discount_pct", 0)),
        }) or []
        for row in rows:
            row["origin_name"] = origin["name"]
        return rows, None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def revalidate_candidate(candidate: dict, config: dict) -> tuple[str, float | None, str | None]:
    """Reconsulta o mesmo itinerário com uma implementação alternativa.

    Os dois coletores consultam Google Flights; a confirmação é técnica por
    implementação independente, não uma confirmação por uma segunda OTA.
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
