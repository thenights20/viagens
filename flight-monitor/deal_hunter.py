from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from providers import discover_swoop_deals, search_swoop

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "flight-monitor" / "config.json"
EXTERNAL_PATH = ROOT / "docs" / "data" / "external-deals.json"
STATE_PATH = ROOT / "flight-monitor" / "data" / "hunter-state.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "deal-hunter.json"

HUB_CODES = ["GRU", "VCP", "GIG", "CGH"]
REGIONAL_CODES = ["DOU", "PMG", "JTC", "TJL", "ARU", "PPB", "MII"]

DOMESTIC = {
    "DOU", "PMG", "JTC", "GRU", "CGH", "VCP", "GIG", "TJL", "ARU", "PPB", "MII", "CGR", "CGB", "BSB", "GYN", "CWB", "LDB", "MGF", "IGU", "FLN", "NVT", "POA", "SJP", "RAO", "UDI", "CNF", "SDU", "VIX", "SSA", "REC", "FOR", "NAT", "MCZ", "AJU", "JPA", "THE", "SLZ", "BEL", "MAO", "PVH", "BVB", "MCP", "PMW", "JDO", "IOS", "BPS", "PNZ", "RBR", "STM", "IMP", "CLV", "MOC", "CFB", "MEA", "PFB", "JOI", "XAP", "JJG", "ROO"
}
SOUTH_AMERICA = {"EZE", "AEP", "SCL", "ASU", "MVD", "LIM", "BOG", "UIO", "CTG", "LPB", "VVI", "GYE"}
CARIBBEAN_MEXICO = {"PUJ", "CUN", "AUA", "SJU", "SDQ", "MBJ", "NAS", "MEX"}
USA_CANADA = {"MIA", "FLL", "MCO", "TPA", "JFK", "EWR", "LAX", "LAS", "BOS", "ORD", "IAD", "ATL", "YYZ", "YUL", "YVR"}
EUROPE = {"LIS", "OPO", "MAD", "BCN", "CDG", "ORY", "LHR", "LGW", "FCO", "MXP", "AMS", "FRA", "BER", "ZRH", "VLC", "DUB", "VIE", "PRG"}

PRICE_THRESHOLDS = {
    "domestic": [(400, 45), (600, 36), (800, 27), (1000, 16)],
    "south_america": [(900, 45), (1200, 36), (1500, 27), (1800, 16)],
    "caribbean_mexico": [(1700, 45), (2100, 36), (2600, 27), (3100, 16)],
    "usa_canada": [(1900, 45), (2300, 36), (2800, 27), (3300, 16)],
    "europe": [(2300, 45), (2800, 36), (3300, 27), (3900, 16)],
    "long_haul": [(3800, 45), (4600, 36), (5500, 27), (6500, 16)],
}

MONTHS = {
    "jan": 1, "january": 1, "fev": 2, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def load_json(path: Path, fallback: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def region_for(destination: str, country: str = "") -> str:
    code = (destination or "").upper()
    c = (country or "").lower()
    if code in DOMESTIC or c in {"brazil", "brasil"}:
        return "domestic"
    if code in SOUTH_AMERICA or any(x in c for x in ("argentina", "chile", "uruguay", "paraguay", "peru", "colombia", "ecuador", "bolivia")):
        return "south_america"
    if code in CARIBBEAN_MEXICO or any(x in c for x in ("mexico", "dominican", "jamaica", "bahamas", "aruba", "caribbean")):
        return "caribbean_mexico"
    if code in USA_CANADA or any(x in c for x in ("united states", "usa", "canada")):
        return "usa_canada"
    if code in EUROPE or any(x in c for x in ("spain", "portugal", "france", "italy", "germany", "netherlands", "united kingdom", "ireland", "switzerland", "austria", "czech")):
        return "europe"
    return "long_haul"


def absolute_price_points(region: str, price: float) -> int:
    for ceiling, points in PRICE_THRESHOLDS[region]:
        if price <= ceiling:
            return points
    return 0


def discount_points(discount: float) -> int:
    if discount >= 65:
        return 45
    if discount >= 55:
        return 40
    if discount >= 45:
        return 35
    if discount >= 35:
        return 28
    if discount >= 25:
        return 20
    if discount >= 15:
        return 12
    return 0


def hunter_score(row: dict) -> dict:
    price = float(row.get("price") or 0)
    region = region_for(row.get("destination", ""), row.get("destination_country", ""))
    absolute = absolute_price_points(region, price)
    discount = float(row.get("provider_discount_pct") or 0)
    relative = discount_points(discount)
    stops = int(row.get("stops_count") or 0)
    itinerary = 8 if stops == 0 else 4 if stops == 1 else 0
    external_bonus = 20 if row.get("external_verified") else 0
    score = min(100, absolute + relative + itinerary + external_bonus)
    if score >= 90:
        label = "🚨 TARIFA FORA DA CURVA"
    elif score >= 80:
        label = "🔥🔥 EXCEPCIONAL"
    elif score >= 70:
        label = "🔥 MUITO BARATA"
    elif score >= 60:
        label = "🟢 BOA OPORTUNIDADE"
    else:
        label = "NORMAL"
    return {
        "hunter_score": score,
        "hunter_status": label,
        "price_region": region,
        "absolute_price_points": absolute,
        "relative_discount_points": relative,
        "itinerary_points": itinerary,
        "external_signal_points": external_bonus,
    }


def parse_example_date(text: str, year: int) -> tuple[date, date] | None:
    m = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s*[–-]\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)",
        text,
        re.I,
    )
    if not m:
        return None
    m1 = MONTHS.get(m.group(2).lower())
    m2 = MONTHS.get(m.group(4).lower())
    if not m1 or not m2:
        return None
    dep = date(year, m1, int(m.group(1)))
    ret_year = year + 1 if m2 < m1 else year
    ret = date(ret_year, m2, int(m.group(3)))
    return dep, ret


def external_targets(external: dict, limit: int = 8) -> list[dict]:
    targets: list[dict] = []
    for signal in external.get("signals", []):
        if signal.get("source") != "Secret Flying":
            continue
        if not signal.get("origin") or not signal.get("destination"):
            continue
        availability = str(signal.get("availability") or "")
        year_match = re.search(r"(20\d{2})", availability)
        year = int(year_match.group(1)) if year_match else date.today().year
        examples = signal.get("example_dates") or []
        for example in examples[:2]:
            pair = parse_example_date(str(example), year)
            if not pair or pair[0] <= date.today():
                continue
            targets.append({"signal": signal, "dep": pair[0], "ret": pair[1]})
            break
        if len(targets) >= limit:
            break
    return targets


def verify_external(target: dict, config: dict) -> tuple[dict | None, str | None]:
    signal = target["signal"]
    params = {"max_stops": 2, "adults": 1, "currency": "BRL"}
    try:
        row = search_swoop(signal["origin"], signal["destination"], target["dep"], target["ret"], params)
        if not row:
            return None, None
        row["external_verified"] = True
        row["external_source"] = signal.get("source")
        row["external_title"] = signal.get("title")
        row["external_url"] = signal.get("url")
        row["external_advertised_price"] = signal.get("price")
        row["external_advertised_currency"] = signal.get("currency")
        row["provider"] = "swoop-external-recheck"
        return row, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{signal.get('origin')}-{signal.get('destination')}: {exc}"


def itinerary_key(row: dict) -> str:
    return "|".join((str(row.get("origin")), str(row.get("destination")), str(row.get("departure_date")), str(row.get("return_date"))))


def main() -> None:
    config = load_json(CONFIG_PATH, {})
    external = load_json(EXTERNAL_PATH, {"signals": []})
    state = load_json(STATE_PATH, {"version": "0.1.0", "run_counter": 0, "items": {}})
    state.setdefault("items", {})
    run_counter = int(state.get("run_counter", 0))
    names = {x["code"]: x["name"] for x in config.get("origins", [])}

    selected = [x for x in config.get("origins", []) if x["code"] in HUB_CODES]
    if REGIONAL_CODES:
        regional_code = REGIONAL_CODES[run_counter % len(REGIONAL_CODES)]
        selected.extend(x for x in config.get("origins", []) if x["code"] == regional_code)

    hunter_config = json.loads(json.dumps(config))
    hunter_config.setdefault("scan", {})["discovery_min_discount_pct"] = 15
    observations: list[dict] = []
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(discover_swoop_deals, origin, hunter_config): origin for origin in selected}
        for future in as_completed(futures):
            origin = futures[future]
            rows, error = future.result()
            if error:
                errors.append(f"discovery {origin['code']}: {error}")
            for row in rows:
                row["origin_name"] = origin["name"]
                row.update(hunter_score(row))
                if int(row["hunter_score"]) >= 60:
                    observations.append(row)

    targets = external_targets(external)
    verified_external = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(verify_external, target, hunter_config) for target in targets]
        for future in as_completed(futures):
            row, error = future.result()
            if error:
                errors.append("externo " + error)
            if row:
                verified_external += 1
                row["origin_name"] = names.get(row["origin"], row["origin"])
                row.update(hunter_score(row))
                if int(row["hunter_score"]) >= 60:
                    observations.append(row)

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")
    for row in observations:
        key = itinerary_key(row)
        old = state["items"].get(key)
        first_seen = old.get("first_seen") if old else now_iso
        sightings = int(old.get("sightings", 0)) + 1 if old else 1
        row["first_seen"] = first_seen
        row["last_seen"] = now_iso
        row["sightings"] = sightings
        row["fresh"] = not old
        state["items"][key] = row

    cutoff = now - timedelta(hours=12)
    for key, row in list(state["items"].items()):
        try:
            last_seen = datetime.fromisoformat(str(row.get("last_seen", "")).replace("Z", "+00:00"))
        except ValueError:
            state["items"].pop(key, None)
            continue
        if last_seen < cutoff:
            state["items"].pop(key, None)

    active = list(state["items"].values())
    active.sort(key=lambda x: (-int(x.get("hunter_score", 0)), float(x.get("price") or 999999)))
    state["run_counter"] = run_counter + 1
    state["last_run"] = now_iso

    output = {
        "version": "0.1.0",
        "generated_at": now_iso,
        "source": "Deal Hunter: Google Flights Explore/Swoop + rechecagem de sinais externos",
        "scan_interval_minutes": 15,
        "origin_codes": [x["code"] for x in selected],
        "hub_codes": HUB_CODES,
        "regional_rotation": REGIONAL_CODES,
        "current_observations": len(observations),
        "active_count": len(active),
        "exceptional_count": sum(1 for x in active if int(x.get("hunter_score", 0)) >= 80),
        "very_cheap_count": sum(1 for x in active if int(x.get("hunter_score", 0)) >= 70),
        "external_targets": len(targets),
        "external_verified": verified_external,
        "errors": errors[:30],
        "benchmarks": PRICE_THRESHOLDS,
        "deals": active[:160],
    }
    save_json(STATE_PATH, state)
    save_json(OUTPUT_PATH, output)
    print(
        "Deal Hunter:", len(observations), "achados nesta rodada;",
        len(active), "ativos;",
        output["exceptional_count"], "Score 80+;",
        verified_external, "sinais externos rechecados;",
        len(errors), "erros",
    )


if __name__ == "__main__":
    main()
