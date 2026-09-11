from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from providers import discover_swoop_deals, revalidate_candidate, search_with_fallback
from radar import booking_bucket, choose_baseline, departure_season, score_candidate, should_repeat_alert

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


def selected_slice(config: dict, state: dict) -> tuple[list[dict], list[dict], dict, int]:
    scan = config["scan"]
    origin_groups = chunks(config["origins"], int(scan["origins_per_run"]))
    destination_groups = chunks(config["destinations"], int(scan["destinations_per_run"]))
    profiles = list(scan["date_profiles"])
    slot = max(0, int(state.get("scan_counter", 0)))
    origin_group = slot % len(origin_groups)
    destination_group = (slot // len(origin_groups)) % len(destination_groups)
    profile_index = (slot // (len(origin_groups) * len(destination_groups))) % len(profiles)
    return origin_groups[origin_group], destination_groups[destination_group], profiles[profile_index], slot


def make_queries(origins: list[dict], destinations: list[dict], profile: dict, config: dict) -> list[tuple]:
    scan = config["scan"]
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
            for offset in profile["offsets"]:
                dep = today + timedelta(days=int(offset))
                for stay in profile["stays"]:
                    ret = dep + timedelta(days=int(stay))
                    result.append((origin, destination, dep, ret, params))
    return result


def route_key(row: dict) -> str:
    return f"{row['origin']}-{row['destination']}"


def itinerary_key(row: dict) -> str:
    return "|".join((row["origin"], row["destination"], row["departure_date"], row["return_date"]))


def annotate(row: dict, *, now: datetime, scan_id: str, names: dict[str, str]) -> dict:
    result = dict(row)
    result["origin_name"] = result.get("origin_name") or names.get(result["origin"], result["origin"])
    result["destination_name"] = result.get("destination_name") or names.get(result["destination"], result["destination"])
    result["observed_at"] = now.isoformat().replace("+00:00", "Z")
    result["scan_id"] = scan_id
    dep = date.fromisoformat(result["departure_date"])
    ret = date.fromisoformat(result["return_date"])
    advance = max(0, (dep - now.date()).days)
    result["days_before_departure"] = advance
    result["booking_bucket"] = booking_bucket(advance)
    result["departure_season"] = departure_season(result["departure_date"])
    result["trip_days"] = max(0, (ret - dep).days)
    return result


def merge_observations(rows: list[dict]) -> list[dict]:
    """Deduplica o mesmo itinerário, mantendo o menor preço e sinais auxiliares."""
    merged: dict[str, dict] = {}
    for row in rows:
        key = itinerary_key(row)
        current = merged.get(key)
        if current is None or float(row["price"]) < float(current["price"]):
            if current:
                if not row.get("provider_typical_price") and current.get("provider_typical_price"):
                    row["provider_typical_price"] = current["provider_typical_price"]
                if row.get("provider_discount_pct") is None and current.get("provider_discount_pct") is not None:
                    row["provider_discount_pct"] = current["provider_discount_pct"]
            merged[key] = row
        else:
            if not current.get("provider_typical_price") and row.get("provider_typical_price"):
                current["provider_typical_price"] = row["provider_typical_price"]
            if current.get("provider_discount_pct") is None and row.get("provider_discount_pct") is not None:
                current["provider_discount_pct"] = row["provider_discount_pct"]
    return list(merged.values())


def fetch_regular(item: tuple, config: dict) -> tuple[dict | None, list[str]]:
    origin, destination, dep, ret, params = item
    row, provider_errors = search_with_fallback(origin["code"], destination["code"], dep, ret, params, config)
    if row:
        row["origin_name"] = origin["name"]
        row["destination_name"] = destination["name"]
    errors = [f"{origin['code']}-{destination['code']} {dep}/{ret}: {msg}" for msg in provider_errors]
    return row, errors


def prune_state(state: dict, now: datetime, config: dict) -> None:
    cutoff = now - timedelta(days=int(config["scan"]["history_days"]))
    max_obs = int(config["scan"].get("max_route_observations", 180))
    routes = state.setdefault("routes", {})
    for key, route in list(routes.items()):
        kept: list[dict] = []
        for obs in route.get("observations", []):
            try:
                stamp = datetime.fromisoformat(str(obs["observed_at"]).replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                continue
            if stamp >= cutoff:
                kept.append(obs)
        route["observations"] = kept[-max_obs:]
        if not kept:
            routes.pop(key, None)


def existing_history(state: dict, candidate: dict) -> list[dict]:
    return list(state.get("routes", {}).get(route_key(candidate), {}).get("observations", []))


def score_rows(rows: list[dict], state: dict, config: dict, scan_id: str) -> list[dict]:
    scan = config["scan"]
    scored: list[dict] = []
    for row in rows:
        history = existing_history(state, row)
        stats, baseline_scope = choose_baseline(
            history,
            row,
            exclude_run_id=scan_id,
            min_bucket_samples=int(scan.get("min_bucket_samples", 5)),
            min_season_samples=int(scan.get("min_season_samples", 5)),
            scale_floor=float(scan.get("mad_scale_floor", 0.03)),
        )
        metrics = score_candidate(
            row,
            history,
            stats,
            external_typical_price=row.get("provider_typical_price"),
            confirmation="none",
        )
        row.update(metrics)
        row["baseline_scope"] = baseline_scope
        scored.append(row)
    return scored


def revalidate_top(rows: list[dict], state: dict, config: dict, scan_id: str) -> tuple[int, list[str]]:
    scan = config["scan"]
    threshold = int(scan.get("revalidate_min_score", 70))
    limit = int(scan.get("max_revalidations_per_run", 8))
    candidates = sorted(
        [x for x in rows if int(x.get("deal_score", 0)) >= threshold],
        key=lambda x: (-int(x.get("deal_score", 0)), -float(x.get("discount_pct", 0))),
    )[:limit]
    errors: list[str] = []
    confirmed = 0
    for row in candidates:
        status, checked_price, error = revalidate_candidate(row, config)
        if error:
            errors.append(f"revalidação {route_key(row)}: {error}")
        if checked_price is not None:
            row["checked_price"] = round(float(checked_price), 2)
        row["confirmation_detail"] = status
        if status == "second_collector":
            confirmed += 1
            history = existing_history(state, row)
            stats, baseline_scope = choose_baseline(
                history,
                row,
                exclude_run_id=scan_id,
                min_bucket_samples=int(scan.get("min_bucket_samples", 5)),
                min_season_samples=int(scan.get("min_season_samples", 5)),
                scale_floor=float(scan.get("mad_scale_floor", 0.03)),
            )
            row.update(score_candidate(
                row,
                history,
                stats,
                external_typical_price=row.get("provider_typical_price"),
                confirmation="second_source",
            ))
            row["baseline_scope"] = baseline_scope
            row["confirmation"] = "segunda implementação confirmou"
        elif status == "price_mismatch":
            row["confirmation"] = "reconsulta encontrou preço diferente"
            row["deal_score"] = max(0, int(row.get("deal_score", 0)) - 12)
            if int(row["deal_score"]) < 70:
                row["status"] = "🟢 BOM PREÇO" if int(row["deal_score"]) >= 60 else "NORMAL"
    return confirmed, errors


def persist_rows(state: dict, rows: list[dict], config: dict) -> None:
    routes = state.setdefault("routes", {})
    max_obs = int(config["scan"].get("max_route_observations", 180))
    for row in rows:
        key = route_key(row)
        route = routes.setdefault(key, {
            "origin": row["origin"],
            "origin_name": row["origin_name"],
            "destination": row["destination"],
            "destination_name": row["destination_name"],
            "observations": [],
        })
        previous_prices = [float(x["price"]) for x in route.get("observations", []) if x.get("price")]
        row["record"] = not previous_prices or float(row["price"]) < min(previous_prices)
        route["origin_name"] = row["origin_name"]
        route["destination_name"] = row["destination_name"]
        route.setdefault("observations", []).append(row)
        route["observations"] = route["observations"][-max_obs:]


def update_alert_state(state: dict, rows: list[dict], config: dict, today: date) -> list[dict]:
    alerts = state.setdefault("alerts", {})
    new_alerts: list[dict] = []
    scan = config["scan"]
    for row in sorted(rows, key=lambda x: int(x.get("deal_score", 0)), reverse=True):
        if int(row.get("deal_score", 0)) < int(scan.get("alert_min_score", 70)):
            continue
        key = route_key(row)
        previous = alerts.get(key)
        if should_repeat_alert(
            previous,
            current_price=float(row["price"]),
            current_score=int(row["deal_score"]),
            today=today,
            improvement_pct=float(scan.get("repeat_improvement_pct", 5)),
            cooldown_days=int(scan.get("repeat_cooldown_days", 7)),
        ):
            alert = {
                "origin": row["origin"],
                "destination": row["destination"],
                "price": float(row["price"]),
                "score": int(row["deal_score"]),
                "date": today.isoformat(),
                "departure_date": row["departure_date"],
                "return_date": row["return_date"],
            }
            alerts[key] = alert
            row["new_alert"] = True
            new_alerts.append(dict(row))
        else:
            row["new_alert"] = False
    return new_alerts


def best_active_deals(state: dict, config: dict, now: datetime) -> list[dict]:
    cutoff = now - timedelta(days=int(config["scan"]["active_days"]))
    today_iso = now.date().isoformat()
    output: list[dict] = []
    for route in state.get("routes", {}).values():
        valid: list[dict] = []
        for obs in route.get("observations", []):
            try:
                stamp = datetime.fromisoformat(str(obs["observed_at"]).replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                continue
            if stamp >= cutoff and str(obs.get("departure_date", "")) >= today_iso:
                valid.append(obs)
        if not valid:
            continue
        best = max(
            valid,
            key=lambda x: (int(x.get("deal_score", 0)), float(x.get("discount_pct", 0)), -float(x.get("price", 0))),
        )
        if int(best.get("deal_score", 0)) >= int(config["scan"].get("min_output_score", 55)):
            output.append(dict(best))
    output.sort(key=lambda x: (-int(x.get("deal_score", 0)), -float(x.get("discount_pct", 0)), float(x["price"])))
    return output[: int(config["scan"]["max_output_deals"])]


def main() -> None:
    config = load_json(CONFIG_PATH, {})
    if not config:
        raise SystemExit("flight-monitor/config.json não encontrado")
    state = load_json(STATE_PATH, {"version": config.get("version", "0.2.0"), "routes": {}, "alerts": {}, "scan_counter": 0})
    state.setdefault("routes", {})
    state.setdefault("alerts", {})
    now = datetime.now(timezone.utc)
    prune_state(state, now, config)

    origins, destinations, profile, slot = selected_slice(config, state)
    scan_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{slot + 1}"
    names = {x["code"]: x["name"] for x in config["destinations"]}
    names.update({x["code"]: x["name"] for x in config["origins"]})
    queries = make_queries(origins, destinations, profile, config)

    observations: list[dict] = []
    errors: list[str] = []
    fallback_results = 0
    with ThreadPoolExecutor(max_workers=max(1, int(config["scan"].get("workers", 4)))) as pool:
        futures = [pool.submit(fetch_regular, item, config) for item in queries]
        for future in as_completed(futures):
            row, row_errors = future.result()
            errors.extend(row_errors)
            if row:
                if row.get("fallback_used"):
                    fallback_results += 1
                observations.append(annotate(row, now=now, scan_id=scan_id, names=names))

    discovery_rows: list[dict] = []
    discovery_errors: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, int(config["scan"].get("discovery_workers", 2)))) as pool:
        futures = {pool.submit(discover_swoop_deals, origin, config): origin for origin in origins}
        for future in as_completed(futures):
            origin = futures[future]
            rows, error = future.result()
            if error:
                discovery_errors.append(f"discovery {origin['code']}: {error}")
            for row in rows:
                names.setdefault(row["destination"], row.get("destination_name") or row["destination"])
                discovery_rows.append(annotate(row, now=now, scan_id=scan_id, names=names))

    observations = merge_observations(observations + discovery_rows)
    observations = score_rows(observations, state, config, scan_id)
    revalidated, revalidation_errors = revalidate_top(observations, state, config, scan_id)
    errors.extend(discovery_errors)
    errors.extend(revalidation_errors)
    new_alerts = update_alert_state(state, observations, config, now.date())
    persist_rows(state, observations, config)

    state["version"] = config.get("version", "0.2.0")
    state["scan_counter"] = slot + 1
    state["last_scan_at"] = now.isoformat().replace("+00:00", "Z")
    state["last_scan"] = {
        "scan_number": slot + 1,
        "scan_id": scan_id,
        "origin_codes": [x["code"] for x in origins],
        "destination_codes": [x["code"] for x in destinations],
        "date_profile": profile["name"],
        "queries": len(queries),
        "regular_results": len(observations) - len(discovery_rows),
        "discovery_results": len(discovery_rows),
        "fallback_results": fallback_results,
        "results": len(observations),
        "revalidated": revalidated,
        "errors": len(errors),
    }

    deals = best_active_deals(state, config, now)
    configured_codes = {x["code"] for x in config["destinations"]}
    discovered_codes = {
        x.get("destination") for route in state.get("routes", {}).values() for x in route.get("observations", []) if x.get("destination")
    }
    strong = [x for x in deals if int(x.get("deal_score", 0)) >= 70]
    payload = {
        "version": config.get("version", "0.2.0"),
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": "Google Flights via fast-flights + Swoop",
        "algorithm": "Radar robusto: mediana + MAD + percentis + z-score + booking window + histórico + revalidação",
        "origin_count": len(config["origins"]),
        "destination_count": len(configured_codes | discovered_codes),
        "configured_destination_count": len(configured_codes),
        "route_count": len(state.get("routes", {})),
        "deal_count": len(deals),
        "strong_deal_count": len(strong),
        "new_alert_count": len(new_alerts),
        "origins": config["origins"],
        "deals": deals,
        "new_alerts": new_alerts[:30],
        "scan": state["last_scan"],
        "errors": errors[:40],
    }
    save_json(STATE_PATH, state)
    save_json(OUTPUT_PATH, payload)
    print(
        f"Passagens: {len(observations)} observações ({len(discovery_rows)} discovery), "
        f"{len(deals)} rotas exibidas, {len(strong)} deals 70+, {revalidated} revalidados, {len(errors)} erros."
    )


if __name__ == "__main__":
    main()
