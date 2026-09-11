from __future__ import annotations

import calendar
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
MONITOR = ROOT / "flight-monitor"
if str(MONITOR) not in sys.path:
    sys.path.insert(0, str(MONITOR))

from providers import search_fast_flights  # noqa: E402

OUTPUT_PATH = ROOT / "docs" / "data" / "flight-month-search.json"
VERSION = "0.1.0"
MAX_RESULTS = 100


def google_url(origin: str, destination: str, dep: str, ret: str) -> str:
    q = f"Flights from {origin} to {destination} on {dep} returning {ret}"
    return "https://www.google.com/travel/flights?q=" + quote_plus(q)


def parse_month(value: str) -> tuple[int, int]:
    try:
        year_s, month_s = value.split("-", 1)
        year, month = int(year_s), int(month_s)
    except Exception as exc:
        raise SystemExit("MONTH precisa estar no formato YYYY-MM") from exc
    if year < 2026 or not 1 <= month <= 12:
        raise SystemExit("MONTH inválido")
    return year, month


def month_bounds(value: str) -> tuple[date, date]:
    year, month = parse_month(value)
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def build_combinations(month: str, min_stay: int, max_stay: int, today: date) -> list[tuple[date, date]]:
    first, last = month_bounds(month)
    dep = max(first, today + timedelta(days=1))
    combos: list[tuple[date, date]] = []
    while dep <= last:
        for stay in range(min_stay, max_stay + 1):
            combos.append((dep, dep + timedelta(days=stay)))
        dep += timedelta(days=1)
    return combos


def provider_params(max_stops: int) -> dict[str, Any]:
    return {"max_stops": max_stops, "seat": "economy", "adults": 1, "currency": "BRL", "max_price": None}


def fast_query(origin: str, destination: str, dep: date, ret: date, max_stops: int) -> tuple[dict | None, str | None]:
    try:
        row = search_fast_flights(origin, destination, dep, ret, provider_params(max_stops))
        if not row:
            return None, None
        row = dict(row)
        row["source_kind"] = "fast-flights"
        row["trip_days"] = (ret - dep).days
        row["url"] = row.get("url") or google_url(origin, destination, dep.isoformat(), ret.isoformat())
        return row, None
    except Exception as exc:  # noqa: BLE001
        return None, f"{dep.isoformat()}->{ret.isoformat()}: {type(exc).__name__}: {exc}"


def run_fast(origin: str, destination: str, combos: list[tuple[date, date]], max_stops: int, workers: int) -> tuple[list[dict], list[tuple[date, date]], list[str]]:
    rows: list[dict] = []
    missing: list[tuple[date, date]] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(fast_query, origin, destination, dep, ret, max_stops): (dep, ret) for dep, ret in combos}
        for future in as_completed(future_map):
            dep, ret = future_map[future]
            row, error = future.result()
            if row:
                rows.append(row)
            else:
                missing.append((dep, ret))
            if error and len(errors) < 30:
                errors.append(error)
    return rows, missing, errors


def run_swoop_batch(origin: str, destination: str, combos: list[tuple[date, date]], max_stops: int, workers: int) -> tuple[list[dict], list[str]]:
    if not combos:
        return [], []
    worker = Path(__file__).with_name("swoop_batch_worker.py")
    payload = {
        "origin": origin,
        "destination": destination,
        "max_stops": max_stops,
        "workers": workers,
        "queries": [{"departure_date": dep.isoformat(), "return_date": ret.isoformat()} for dep, ret in combos],
    }
    proc = subprocess.run(
        [sys.executable, str(worker)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=max(180, min(1200, len(combos) * 5)),
        check=False,
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        return [], [(proc.stderr or "Swoop batch sem saída")[-1000:]]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], ["Swoop batch retornou JSON inválido: " + raw[-700:]]
    rows = list(data.get("results") or [])
    errors = list(data.get("errors") or [])[:30]
    for row in rows:
        row["source_kind"] = "swoop"
        try:
            row["trip_days"] = (date.fromisoformat(row["return_date"]) - date.fromisoformat(row["departure_date"])).days
        except Exception:
            row["trip_days"] = 0
        row["url"] = row.get("url") or google_url(origin, destination, row["departure_date"], row["return_date"])
    return rows, errors


def dedupe(rows: list[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for row in rows:
        if not row.get("price"):
            continue
        key = (str(row.get("departure_date")), str(row.get("return_date")))
        current = best.get(key)
        if current is None or float(row["price"]) < float(current["price"]):
            best[key] = row
    return list(best.values())


def daily_min(rows: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for row in rows:
        dep = str(row.get("departure_date") or "")
        current = best.get(dep)
        if not current or float(row["price"]) < float(current["price"]):
            best[dep] = row
    return [best[key] for key in sorted(best)]


def main() -> None:
    origin = str(os.environ.get("SEARCH_ORIGIN") or "GRU").strip().upper()
    destination = str(os.environ.get("SEARCH_DESTINATION") or "MIA").strip().upper()
    month = str(os.environ.get("SEARCH_MONTH") or "2026-10").strip()
    min_stay = int(os.environ.get("SEARCH_MIN_STAY") or 4)
    max_stay = int(os.environ.get("SEARCH_MAX_STAY") or 10)
    max_stops = int(os.environ.get("SEARCH_MAX_STOPS") or 2)
    fast_workers = int(os.environ.get("SEARCH_FAST_WORKERS") or 10)
    swoop_workers = int(os.environ.get("SEARCH_SWOOP_WORKERS") or 4)
    force_swoop = str(os.environ.get("SEARCH_FORCE_SWOOP") or "").lower() in {"1", "true", "yes"}

    if len(origin) != 3 or len(destination) != 3 or not origin.isalpha() or not destination.isalpha():
        raise SystemExit("Origem e destino precisam ser códigos IATA de 3 letras")
    if origin == destination:
        raise SystemExit("Origem e destino não podem ser iguais")
    if not (2 <= min_stay <= max_stay <= 21):
        raise SystemExit("Duração deve ficar entre 2 e 21 dias")

    now = datetime.now(timezone.utc)
    combos = build_combinations(month, min_stay, max_stay, now.date())
    if not combos:
        raise SystemExit("O mês selecionado não possui datas futuras")

    fast_rows, missing, fast_errors = run_fast(origin, destination, combos, max_stops, fast_workers)
    fast_ratio = len(fast_rows) / len(combos)

    regional = origin in {"DOU", "PMG", "JTC", "TJL", "ARU", "PPB", "MII"}
    use_swoop = force_swoop or regional or fast_ratio < 0.18
    swoop_rows: list[dict] = []
    swoop_errors: list[str] = []
    if use_swoop and missing:
        swoop_rows, swoop_errors = run_swoop_batch(origin, destination, missing, max_stops, swoop_workers)

    rows = dedupe(fast_rows + swoop_rows)
    rows.sort(key=lambda row: (float(row.get("price") or 10**12), str(row.get("departure_date")), str(row.get("return_date"))))
    top = rows[:MAX_RESULTS]
    for rank, row in enumerate(top, start=1):
        row["rank"] = rank

    payload = {
        "version": VERSION,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "request": {
            "origin": origin,
            "destination": destination,
            "month": month,
            "min_stay": min_stay,
            "max_stay": max_stay,
            "max_stops": max_stops,
        },
        "stats": {
            "combinations": len(combos),
            "priced_combinations": len(rows),
            "coverage_pct": round((len(rows) / len(combos)) * 100, 1),
            "fast_results": len(fast_rows),
            "fast_missing": len(missing),
            "swoop_used": use_swoop,
            "swoop_results": len(swoop_rows),
            "lowest_price": round(float(top[0]["price"]), 2) if top else None,
            "result_count": len(top),
        },
        "daily_min": daily_min(rows),
        "results": top,
        "errors": (fast_errors + swoop_errors)[:40],
        "notes": [
            "O mês selecionado é o mês da ida; a volta pode cair no mês seguinte conforme a duração escolhida.",
            "A matriz inclui todas as combinações entre a duração mínima e máxima selecionadas para cada dia de ida disponível no mês.",
            "Os preços são dinâmicos e precisam ser confirmados antes da emissão.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Busca mensal {origin}->{destination} {month}: {len(rows)}/{len(combos)} combinações com preço, "
        f"top {len(top)}, menor R$ {payload['stats']['lowest_price'] if top else '-'}"
    )


if __name__ == "__main__":
    main()
