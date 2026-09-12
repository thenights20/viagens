from __future__ import annotations

import calendar
import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
MONITOR = ROOT / "flight-monitor"
if str(MONITOR) not in sys.path:
    sys.path.insert(0, str(MONITOR))

from providers import search_fast_flights  # noqa: E402

OUTPUT_PATH = Path(os.environ.get("SEARCH_OUTPUT_PATH") or (ROOT / "docs" / "data" / "flight-month-search.json"))
VERSION = "0.3.0"
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


def build_combinations(month: str, today: date) -> list[tuple[date, date]]:
    """Gera a matriz completa dentro do mês: 01→02, 01→03 ... 30→31."""
    first, last = month_bounds(month)
    first_departure = max(first, today + timedelta(days=1))
    combos: list[tuple[date, date]] = []
    dep = first_departure
    while dep < last:
        ret = dep + timedelta(days=1)
        while ret <= last:
            combos.append((dep, ret))
            ret += timedelta(days=1)
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


def send_progress(url: str, request_id: str, payload: dict[str, Any]) -> None:
    if not url or not request_id:
        return
    body = dict(payload)
    body["request_id"] = request_id
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "text/plain;charset=UTF-8", "User-Agent": "flight-search-progress/0.3"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as response:  # noqa: S310
            response.read(32)
    except Exception:
        pass


def run_fast(
    origin: str,
    destination: str,
    combos: list[tuple[date, date]],
    max_stops: int,
    workers: int,
    on_progress: Callable[[int, int, int, date, date], None] | None = None,
) -> tuple[list[dict], list[tuple[date, date]], list[str]]:
    rows: list[dict] = []
    missing: list[tuple[date, date]] = []
    errors: list[str] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(fast_query, origin, destination, dep, ret, max_stops): (dep, ret) for dep, ret in combos}
        for future in as_completed(future_map):
            dep, ret = future_map[future]
            row, error = future.result()
            done += 1
            if row:
                rows.append(row)
            else:
                missing.append((dep, ret))
            if error and len(errors) < 40:
                errors.append(error)
            if on_progress:
                on_progress(done, len(combos), len(rows), dep, ret)
    return rows, missing, errors


def run_swoop_batch(
    origin: str,
    destination: str,
    combos: list[tuple[date, date]],
    max_stops: int,
    workers: int,
    progress_url: str,
    request_id: str,
    total_combos: int,
    fast_priced: int,
) -> tuple[list[dict], list[str]]:
    if not combos:
        return [], []
    worker = Path(__file__).with_name("swoop_batch_worker.py")
    payload = {
        "origin": origin,
        "destination": destination,
        "max_stops": max_stops,
        "workers": workers,
        "queries": [{"departure_date": dep.isoformat(), "return_date": ret.isoformat()} for dep, ret in combos],
        "progress_url": progress_url,
        "request_id": request_id,
        "total_combos": total_combos,
        "fast_priced": fast_priced,
    }
    proc = subprocess.run(
        [sys.executable, str(worker)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=max(240, min(1800, len(combos) * 5)),
        check=False,
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        return [], [(proc.stderr or "Swoop batch sem saída")[-1000:]]
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return [], ["Swoop batch retornou JSON inválido: " + raw[-700:]]
    rows = list(result.get("results") or [])
    errors = list(result.get("errors") or [])[:40]
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
    max_stops = int(os.environ.get("SEARCH_MAX_STOPS") or 2)
    request_id = str(os.environ.get("SEARCH_REQUEST_ID") or "manual").strip()[:80]
    progress_url = str(os.environ.get("SEARCH_PROGRESS_URL") or "").strip()
    fast_workers = int(os.environ.get("SEARCH_FAST_WORKERS") or 12)
    swoop_workers = int(os.environ.get("SEARCH_SWOOP_WORKERS") or 6)
    force_swoop = str(os.environ.get("SEARCH_FORCE_SWOOP") or "").lower() in {"1", "true", "yes"}

    if len(origin) != 3 or len(destination) != 3 or not origin.isalpha() or not destination.isalpha():
        raise SystemExit("Origem e destino precisam ser códigos IATA de 3 letras")
    if origin == destination:
        raise SystemExit("Origem e destino não podem ser iguais")
    if not 0 <= max_stops <= 2:
        raise SystemExit("Escalas precisa ficar entre 0 e 2")

    started = datetime.now(timezone.utc)
    combos = build_combinations(month, started.date())
    if not combos:
        raise SystemExit("O mês selecionado não possui pares de datas futuras")

    total = len(combos)
    send_progress(progress_url, request_id, {
        "status": "running", "stage": "starting", "percent": 3,
        "total": total, "completed": 0, "remaining": total, "priced": 0,
        "message": "Preparando consultas da matriz completa.",
    })

    last_sent_at = 0.0
    last_sent_done = -1
    step = max(4, total // 55)

    def fast_progress(done: int, count: int, priced: int, dep: date, ret: date) -> None:
        nonlocal last_sent_at, last_sent_done
        now_m = time.monotonic()
        if done != count and done - last_sent_done < step and now_m - last_sent_at < 2.5:
            return
        last_sent_at = now_m
        last_sent_done = done
        pct = 5 + round((done / max(1, count)) * 70)
        send_progress(progress_url, request_id, {
            "status": "running", "stage": "searching", "percent": min(75, pct),
            "total": count, "completed": done, "remaining": max(0, count - done), "priced": priced,
            "current_pair": f"{dep.strftime('%d/%m')}→{ret.strftime('%d/%m')}",
            "message": "Consultando combinações de ida e volta.",
        })

    fast_rows, missing, fast_errors = run_fast(origin, destination, combos, max_stops, fast_workers, fast_progress)
    fast_ratio = len(fast_rows) / total

    regional = origin in {"DOU", "PMG", "JTC", "TJL", "ARU", "PPB", "MII"}
    use_swoop = force_swoop or regional or fast_ratio < 0.18
    swoop_rows: list[dict] = []
    swoop_errors: list[str] = []
    if use_swoop and missing:
        send_progress(progress_url, request_id, {
            "status": "running", "stage": "fallback", "percent": 76,
            "total": total, "completed": total, "remaining": 0, "priced": len(fast_rows),
            "fallback_done": 0, "fallback_total": len(missing),
            "message": "Complementando datas que não retornaram preço na primeira fonte.",
        })
        swoop_rows, swoop_errors = run_swoop_batch(
            origin, destination, missing, max_stops, swoop_workers,
            progress_url, request_id, total, len(fast_rows),
        )

    send_progress(progress_url, request_id, {
        "status": "running", "stage": "ranking", "percent": 96,
        "total": total, "completed": total, "remaining": 0,
        "priced": len(fast_rows) + len(swoop_rows),
        "message": "Ordenando e removendo resultados duplicados.",
    })

    rows = dedupe(fast_rows + swoop_rows)
    rows.sort(key=lambda row: (float(row.get("price") or 10**12), str(row.get("departure_date")), str(row.get("return_date"))))
    top = rows[:MAX_RESULTS]
    for rank, row in enumerate(top, start=1):
        row["rank"] = rank

    finished = datetime.now(timezone.utc)
    payload = {
        "version": VERSION,
        "generated_at": finished.isoformat().replace("+00:00", "Z"),
        "mode": "full_month_matrix",
        "request_id": request_id,
        "request": {
            "origin": origin,
            "destination": destination,
            "month": month,
            "max_stops": max_stops,
        },
        "stats": {
            "combinations": total,
            "priced_combinations": len(rows),
            "coverage_pct": round((len(rows) / total) * 100, 1),
            "fast_results": len(fast_rows),
            "fast_missing": len(missing),
            "swoop_used": use_swoop,
            "swoop_results": len(swoop_rows),
            "lowest_price": round(float(top[0]["price"]), 2) if top else None,
            "result_count": len(top),
            "elapsed_seconds": round((finished - started).total_seconds(), 1),
        },
        "daily_min": daily_min(rows),
        "results": top,
        "errors": (fast_errors + swoop_errors)[:50],
        "notes": [
            "A busca é executada sob demanda quando o usuário clica no botão Pesquisar agora.",
            "O mês selecionado apenas delimita o período: são testados todos os pares de ida e volta possíveis dentro dele.",
            "Exemplo: 01→02, 01→03, 01→04 ... 02→03, 02→04 ... até o último par possível do mês.",
            "Em um mês completo de 31 dias são 465 combinações possíveis.",
            "Os preços são dinâmicos e precisam ser confirmados antes da emissão.",
        ],
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    send_progress(progress_url, request_id, {
        "status": "running", "stage": "publishing", "percent": 98,
        "total": total, "completed": total, "remaining": 0, "priced": len(rows),
        "message": "Salvando e publicando os resultados no painel.",
    })
    print(
        f"Busca {request_id} {origin}->{destination} {month}: {len(rows)}/{total} combinações com preço, "
        f"top {len(top)}, menor R$ {payload['stats']['lowest_price'] if top else '-'}"
    )


if __name__ == "__main__":
    main()
