from __future__ import annotations

import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from providers import discover_swoop_deals, search_fast_flights

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "flight-monitor" / "config.json"
CATALOG_PATH = ROOT / "flight-explorer" / "catalog.json"
STATE_PATH = ROOT / "flight-explorer" / "data" / "state.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "flight-explorer.json"

VERSION = "0.1.0"
HORIZON_DAYS = 183
STATE_TTL_HOURS = 30
MAX_ROWS_PER_SCOPE = 100
DATE_PHASES = [
    {"offset": 21, "stay": 4, "label": "~3 semanas"},
    {"offset": 45, "stay": 7, "label": "~1,5 mês"},
    {"offset": 75, "stay": 7, "label": "~2,5 meses"},
    {"offset": 105, "stay": 8, "label": "~3,5 meses"},
    {"offset": 135, "stay": 10, "label": "~4,5 meses"},
    {"offset": 165, "stay": 12, "label": "~5,5 meses"},
]


def load_json(path: Path, fallback: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_country(value: str | None) -> str:
    return (value or "").strip().lower()


def scope_for(row: dict, catalog_by_code: dict[str, dict]) -> str:
    code = str(row.get("destination") or "").upper()
    known = catalog_by_code.get(code)
    if known:
        return str(known["scope"])
    country = normalize_country(row.get("destination_country"))
    if country in {"brasil", "brazil", "br"}:
        return "domestic"
    return "international"


def google_url(origin: str, destination: str, dep: str, ret: str) -> str:
    from urllib.parse import quote_plus

    q = f"Flights from {origin} to {destination} on {dep} returning {ret}"
    return "https://www.google.com/travel/flights?q=" + quote_plus(q)


def option_key(row: dict) -> str:
    return "|".join(
        (
            str(row.get("origin") or ""),
            str(row.get("destination") or ""),
            str(row.get("departure_date") or ""),
            str(row.get("return_date") or ""),
        )
    )


def annotate(
    row: dict,
    *,
    origin: dict,
    catalog_by_code: dict[str, dict],
    now: datetime,
    source_kind: str,
) -> dict:
    result = dict(row)
    destination = str(result.get("destination") or "").upper()
    meta = catalog_by_code.get(destination, {})
    result["origin"] = origin["code"]
    result["origin_name"] = origin["name"]
    result["destination"] = destination
    result["destination_name"] = result.get("destination_name") or meta.get("name") or destination
    result["destination_country"] = result.get("destination_country") or meta.get("country") or ""
    result["scope"] = scope_for(result, catalog_by_code)
    result["price"] = round(float(result["price"]), 2)
    result["observed_at"] = now.isoformat().replace("+00:00", "Z")
    result["source_kind"] = source_kind
    result["provider"] = result.get("provider") or source_kind
    result["url"] = result.get("url") or google_url(
        result["origin"],
        destination,
        str(result.get("departure_date") or ""),
        str(result.get("return_date") or ""),
    )
    try:
        dep = date.fromisoformat(str(result["departure_date"]))
        ret = date.fromisoformat(str(result["return_date"]))
        result["trip_days"] = max(0, (ret - dep).days)
        result["days_ahead"] = max(0, (dep - now.date()).days)
    except Exception:  # noqa: BLE001
        result["trip_days"] = 0
        result["days_ahead"] = 0
    return result


def select_origin(config: dict, state: dict) -> dict:
    origins = list(config["origins"])
    override = str(os.environ.get("EXPLORER_ORIGIN") or "").strip().upper()
    if override:
        for origin in origins:
            if origin["code"] == override:
                return origin
        raise SystemExit(f"EXPLORER_ORIGIN inválida: {override}")
    counter = max(0, int(state.get("scan_counter", 0)))
    return origins[counter % len(origins)]


def selected_phase(origin_code: str, state: dict) -> tuple[int, dict]:
    phases = state.setdefault("origin_phases", {})
    index = int(phases.get(origin_code, 0)) % len(DATE_PHASES)
    return index, DATE_PHASES[index]


def fast_query(origin: dict, destination: dict, dep: date, ret: date, max_stops: int) -> tuple[dict | None, str | None]:
    if origin["code"] == destination["code"]:
        return None, None
    params: dict[str, Any] = {
        "max_stops": max_stops,
        "seat": "economy",
        "adults": 1,
        "currency": "BRL",
        "max_price": None,
    }
    try:
        row = search_fast_flights(origin["code"], destination["code"], dep, ret, params)
        if row:
            row["destination_name"] = destination["name"]
            row["destination_country"] = destination["country"]
        return row, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{origin['code']}-{destination['code']}: {type(exc).__name__}: {exc}"


def within_horizon(row: dict, today: date, horizon: date) -> bool:
    try:
        dep = date.fromisoformat(str(row.get("departure_date") or ""))
        ret = date.fromisoformat(str(row.get("return_date") or ""))
    except ValueError:
        return False
    return today <= dep <= horizon and dep <= ret <= horizon + timedelta(days=14)


def prune_state(state: dict, now: datetime) -> None:
    cutoff = now - timedelta(hours=STATE_TTL_HOURS)
    today = now.date()
    horizon = today + timedelta(days=HORIZON_DAYS)
    all_origins = state.setdefault("options", {})
    for origin_code, rows in list(all_origins.items()):
        kept: dict[str, dict] = {}
        for key, row in dict(rows).items():
            try:
                observed = datetime.fromisoformat(str(row.get("observed_at") or "").replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                continue
            if observed < cutoff or not within_horizon(row, today, horizon):
                continue
            kept[key] = row
        if kept:
            all_origins[origin_code] = kept
        else:
            all_origins.pop(origin_code, None)


def persist_options(state: dict, rows: list[dict]) -> None:
    options = state.setdefault("options", {})
    for row in rows:
        bucket = options.setdefault(row["origin"], {})
        key = option_key(row)
        current = bucket.get(key)
        if current is None or float(row["price"]) <= float(current.get("price") or 10**12):
            bucket[key] = row
        else:
            # Mantém o preço atual mesmo quando subiu, evitando mostrar tarifa antiga como se ainda estivesse disponível.
            bucket[key] = row


def rows_for_origin(state: dict, origin_code: str) -> list[dict]:
    return list(state.get("options", {}).get(origin_code, {}).values())


def top_rows(rows: list[dict], scope: str, limit: int = MAX_ROWS_PER_SCOPE) -> list[dict]:
    scoped = [dict(x) for x in rows if x.get("scope") == scope and float(x.get("price") or 0) > 0]
    scoped.sort(
        key=lambda x: (
            float(x.get("price") or 10**12),
            str(x.get("departure_date") or ""),
            str(x.get("destination_name") or x.get("destination") or ""),
        )
    )
    for i, row in enumerate(scoped[:limit], start=1):
        row["rank"] = i
    return scoped[:limit]


def build_payload(config: dict, catalog: dict, state: dict, now: datetime, scan: dict, errors: list[str]) -> dict:
    result_rows: list[dict] = []
    coverage: dict[str, dict] = {}
    for origin in config["origins"]:
        rows = rows_for_origin(state, origin["code"])
        domestic = top_rows(rows, "domestic")
        international = top_rows(rows, "international")
        result_rows.extend(domestic)
        result_rows.extend(international)
        coverage[origin["code"]] = {
            "origin_name": origin["name"],
            "domestic": {
                "options": len(domestic),
                "unique_destinations": len({x["destination"] for x in domestic}),
            },
            "international": {
                "options": len(international),
                "unique_destinations": len({x["destination"] for x in international}),
            },
            "last_scan_at": state.get("last_scan_by_origin", {}).get(origin["code"]),
        }
    return {
        "version": VERSION,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "title": "Busca flexível · 100 menores opções",
        "horizon_days": HORIZON_DAYS,
        "horizon_end": (now.date() + timedelta(days=HORIZON_DAYS)).isoformat(),
        "catalog_count": len(catalog["destinations"]),
        "max_rows_per_scope": MAX_ROWS_PER_SCOPE,
        "origins": config["origins"],
        "coverage": coverage,
        "results": result_rows,
        "scan": scan,
        "errors": errors[:40],
        "notes": [
            "Valores são os menores encontrados nas rodadas flexíveis; tarifas mudam até a emissão.",
            "O sistema percorre seis janelas de datas entre ~3 semanas e ~5,5 meses e mantém até 100 opções por origem e tipo.",
            "Swoop Deals complementa a busca com datas flexíveis do Google Flights; a varredura dirigida usa fast-flights.",
        ],
    }


def main() -> None:
    config = load_json(CONFIG_PATH, {})
    catalog = load_json(CATALOG_PATH, {})
    if not config or not catalog.get("destinations"):
        raise SystemExit("Configuração da busca flexível ausente")
    if len(catalog["destinations"]) != 100:
        raise SystemExit(f"O catálogo precisa ter 100 destinos; encontrado: {len(catalog['destinations'])}")

    state = load_json(
        STATE_PATH,
        {"version": VERSION, "scan_counter": 0, "origin_phases": {}, "options": {}, "last_scan_by_origin": {}},
    )
    state.setdefault("origin_phases", {})
    state.setdefault("options", {})
    state.setdefault("last_scan_by_origin", {})
    now = datetime.now(timezone.utc)
    prune_state(state, now)

    origin = select_origin(config, state)
    phase_index, phase = selected_phase(origin["code"], state)
    today = now.date()
    dep = today + timedelta(days=int(phase["offset"]))
    ret = dep + timedelta(days=int(phase["stay"]))
    horizon = today + timedelta(days=HORIZON_DAYS)
    catalog_by_code = {x["code"]: x for x in catalog["destinations"]}
    max_stops = int(config.get("scan", {}).get("max_stops", 2))

    observations: list[dict] = []
    errors: list[str] = []
    fast_results = 0
    workers = min(8, max(2, int(config.get("scan", {}).get("workers", 4)) + 2))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {
            pool.submit(fast_query, origin, destination, dep, ret, max_stops): destination
            for destination in catalog["destinations"]
            if destination["code"] != origin["code"]
        }
        for future in as_completed(future_map):
            row, error = future.result()
            if error:
                errors.append(error)
            if row and within_horizon(row, today, horizon):
                fast_results += 1
                observations.append(
                    annotate(row, origin=origin, catalog_by_code=catalog_by_code, now=now, source_kind="fast-flights")
                )

    discovery_config = copy.deepcopy(config)
    discovery_config.setdefault("scan", {})["discovery_min_discount_pct"] = 0
    discovery_rows, discovery_error = discover_swoop_deals(origin, discovery_config)
    if discovery_error:
        errors.append(f"Swoop Deals {origin['code']}: {discovery_error}")
    accepted_discovery = 0
    for row in discovery_rows:
        if not within_horizon(row, today, horizon):
            continue
        accepted_discovery += 1
        observations.append(
            annotate(row, origin=origin, catalog_by_code=catalog_by_code, now=now, source_kind="swoop-deals")
        )

    # Deduplica a mesma combinação de rota/datas, preservando o menor preço da rodada.
    merged: dict[str, dict] = {}
    for row in observations:
        key = option_key(row)
        current = merged.get(key)
        if current is None or float(row["price"]) < float(current["price"]):
            merged[key] = row
    observations = list(merged.values())
    persist_options(state, observations)

    state["version"] = VERSION
    state["scan_counter"] = int(state.get("scan_counter", 0)) + 1
    state["origin_phases"][origin["code"]] = int(state["origin_phases"].get(origin["code"], 0)) + 1
    stamp = now.isoformat().replace("+00:00", "Z")
    state["last_scan_by_origin"][origin["code"]] = stamp
    scan = {
        "origin": origin["code"],
        "origin_name": origin["name"],
        "phase": phase_index + 1,
        "phase_label": phase["label"],
        "departure_date": dep.isoformat(),
        "return_date": ret.isoformat(),
        "directed_queries": len(catalog["destinations"]) - (1 if origin["code"] in catalog_by_code else 0),
        "fast_results": fast_results,
        "discovery_results": accepted_discovery,
        "observations": len(observations),
        "errors": len(errors),
    }
    state["last_scan"] = scan

    payload = build_payload(config, catalog, state, now, scan, errors)
    save_json(STATE_PATH, state)
    save_json(OUTPUT_PATH, payload)
    print(
        f"Explorer {origin['code']}: fase {phase_index + 1}/6, {fast_results} fast, "
        f"{accepted_discovery} discovery, {len(payload['results'])} opções publicadas, {len(errors)} erros."
    )


if __name__ == "__main__":
    main()
