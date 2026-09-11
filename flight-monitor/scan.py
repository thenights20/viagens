from __future__ import annotations

import json
import math
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from search_core import query_cheapest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "flight-monitor" / "config.json"
STATE_PATH = ROOT / "flight-monitor" / "data" / "state.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "flights.json"


def load_json(path: Path, fallback: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def chunks(items: list[dict], size: int) -> list[list[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def selected_slice(config: dict, now: datetime) -> tuple[list[dict], list[dict], int]:
    scan = config["scan"]
    origin_groups = chunks(config["origins"], int(scan["origins_per_run"]))
    destination_groups = chunks(config["destinations"], int(scan["destinations_per_run"]))
    slot = int(now.timestamp() // 3600)
    origin_group = slot % len(origin_groups)
    destination_group = (slot // len(origin_groups)) % len(destination_groups)
    phase = (slot // (len(origin_groups) * len(destination_groups))) % int(scan["date_phases"])
    return origin_groups[origin_group], destination_groups[destination_group], phase


def make_queries(origins: list[dict], destinations: list[dict], phase: int, config: dict) -> list[tuple]:
    scan = config["scan"]
    base_offsets = [int(v) for v in scan["departure_offsets_days"]]
    stays = [int(v) for v in scan["stay_lengths_days"]]
    today = date.today()
    params = {
        "max_stops": int(scan["max_stops"]),
        "seat": "economy",
        "adults": 1,
        "currency": "BRL",
        "max_price": None,
    }
    result: list[tuple] = []
    for origin in origins:
        for destination in destinations:
            if origin["code"] == destination["code"]:
                continue
            for base in base_offsets:
                dep = today + timedelta(days=base + phase * 7)
                for stay in stays:
                    ret = dep + timedelta(days=stay)
                    result.append((origin, destination, dep, ret, params))
    return result


def fetch_one(item: tuple) -> tuple[dict | None, str | None]:
    origin, destination, dep, ret, params = item
    try:
        deal = query_cheapest(origin["code"], destination["code"], dep, ret, params)
        if not deal:
            return None, None
        return {
            "origin": origin["code"],
            "origin_name": origin["name"],
            "destination": destination["code"],
            "destination_name": destination["name"],
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
        }, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{origin['code']}-{destination['code']} {dep}/{ret}: {exc}"


def prune_and_update(state: dict, observations: list[dict], now: datetime, config: dict) -> None:
    routes = state.setdefault("routes", {})
    cutoff = now - timedelta(days=int(config["scan"]["history_days"]))

    for key, route in list(routes.items()):
        kept = []
        for obs in route.get("observations", []):
            try:
                stamp = datetime.fromisoformat(obs["observed_at"].replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                continue
            if stamp >= cutoff:
                kept.append(obs)
        route["observations"] = kept[-80:]
        if not kept:
            routes.pop(key, None)

    for obs in observations:
        key = f"{obs['origin']}-{obs['destination']}"
        route = routes.setdefault(
            key,
            {
                "origin": obs["origin"],
                "origin_name": obs["origin_name"],
                "destination": obs["destination"],
                "destination_name": obs["destination_name"],
                "observations": [],
            },
        )
        previous_prices = [float(x["price"]) for x in route.get("observations", []) if x.get("price")]
        obs["record"] = not previous_prices or float(obs["price"]) < min(previous_prices)
        obs["observed_at"] = now.isoformat().replace("+00:00", "Z")
        route.setdefault("observations", []).append(obs)
        route["observations"] = route["observations"][-80:]


def build_output(state: dict, config: dict, now: datetime, scan_meta: dict, errors: list[str]) -> dict:
    active_cutoff = now - timedelta(days=int(config["scan"]["active_days"]))
    today = date.today().isoformat()
    deals: list[dict] = []

    for route in state.get("routes", {}).values():
        observations = route.get("observations", [])
        valid = []
        for obs in observations:
            try:
                stamp = datetime.fromisoformat(obs["observed_at"].replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                continue
            if stamp >= active_cutoff and obs.get("departure_date", "") >= today:
                valid.append(obs)
        if not valid:
            continue

        best = min(valid, key=lambda x: float(x["price"]))
        prices = [float(x["price"]) for x in observations if x.get("price")]
        baseline = statistics.median(prices) if len(prices) >= 3 else None
        discount = 0.0
        if baseline and baseline > 0 and baseline > float(best["price"]):
            discount = (baseline - float(best["price"])) / baseline * 100

        status = "MELHOR ENCONTRADA"
        if best.get("record"):
            status = "NOVO MENOR PREÇO"
        if discount >= 20:
            status = "DEAL FORTE"
        elif discount >= 10:
            status = "DEAL"

        row = dict(best)
        row.update(
            {
                "baseline_price": round(baseline, 2) if baseline else None,
                "discount_pct": round(discount, 1),
                "history_count": len(prices),
                "lowest_observed": round(min(prices), 2) if prices else None,
                "status": status,
                "trip_days": (date.fromisoformat(best["return_date"]) - date.fromisoformat(best["departure_date"])).days,
            }
        )
        deals.append(row)

    deals.sort(key=lambda x: (-float(x.get("discount_pct", 0)), float(x["price"])))
    deals = deals[: int(config["scan"]["max_output_deals"])]

    return {
        "version": config.get("version", "0.1.0"),
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": "Google Flights",
        "origin_count": len(config["origins"]),
        "destination_count": len(config["destinations"]),
        "route_count": len(state.get("routes", {})),
        "deal_count": len(deals),
        "origins": config["origins"],
        "deals": deals,
        "scan": scan_meta,
        "errors": errors[:25],
    }


def main() -> None:
    config = load_json(CONFIG_PATH, {})
    if not config:
        raise SystemExit("flight-monitor/config.json não encontrado")
    state = load_json(STATE_PATH, {"version": config.get("version", "0.1.0"), "routes": {}})
    now = datetime.now(timezone.utc)
    origins, destinations, phase = selected_slice(config, now)
    queries = make_queries(origins, destinations, phase, config)
    workers = max(1, int(config["scan"].get("workers", 3)))

    observations: list[dict] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_one, item) for item in queries]
        for future in as_completed(futures):
            observation, error = future.result()
            if observation:
                observations.append(observation)
            if error:
                errors.append(error)

    prune_and_update(state, observations, now, config)
    state["version"] = config.get("version", "0.1.0")
    state["last_scan_at"] = now.isoformat().replace("+00:00", "Z")
    state["last_scan"] = {
        "origin_codes": [x["code"] for x in origins],
        "destination_codes": [x["code"] for x in destinations],
        "date_phase": phase,
        "queries": len(queries),
        "results": len(observations),
        "errors": len(errors),
    }
    save_json(STATE_PATH, state)

    payload = build_output(state, config, now, state["last_scan"], errors)
    save_json(OUTPUT_PATH, payload)
    print(
        f"Passagens: {len(observations)} resultados em {len(queries)} consultas; "
        f"{len(payload['deals'])} rotas ativas; {len(errors)} erros."
    )


if __name__ == "__main__":
    main()
