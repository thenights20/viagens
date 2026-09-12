from __future__ import annotations

import base64
import calendar
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
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
HISTORY_PATH = ROOT / "docs" / "data" / "flight-price-history.json"
LIVE_PATH = "docs/data/flight-search-live.json"
LIVE_BRANCH = os.environ.get("SEARCH_LIVE_BRANCH", "flight-live")
VERSION = "0.4.0"
MAX_RESULTS = 100
HISTORY_OBSERVATIONS = 8
HISTORY_MAX_PAIRS = 12000
CHECKPOINT_SECONDS = 18
CHECKPOINT_COMPLETIONS = 24

REAL_ORIGINS = ["DOU", "PMG", "JTC", "GRU", "CGH", "VCP", "GIG", "TJL", "ARU", "PPB", "MII"]
DESTINATION_CODES = {
    "CGR","CGB","BSB","GYN","CWB","LDB","MGF","IGU","FLN","NVT","POA","VCP","CGH","GRU","SJP","RAO","UDI","CNF","GIG","SDU","VIX",
    "SSA","REC","FOR","NAT","MCZ","AJU","JPA","THE","SLZ","BEL","MAO","PVH","BVB","MCP","PMW","JDO","IOS","BPS","PNZ","RBR","STM","IMP",
    "MOC","JOI","XAP","PFB","ROO","FEN","CAC","EZE","AEP","SCL","ASU","MVD","LIM","BOG","UIO","GYE","VVI","PTY","SJO","GUA","MEX","CUN",
    "PUJ","SDQ","MIA","FLL","MCO","JFK","EWR","BOS","IAD","ATL","ORD","DFW","IAH","LAX","SFO","LAS","YYZ","YUL","YVR","LIS","OPO","MAD",
    "BCN","CDG","LHR","FCO","MXP","FRA","AMS","ZRH","VIE","ATH","IST","DXB","DOH"
}
SPECIAL_RESERVED = set(REAL_ORIGINS) | DESTINATION_CODES | {"QZZ", "QZX"}
RANGE_PAIR_COUNT = 465


def _range_codes() -> list[str]:
    codes: list[str] = []
    for a in "QRSTUVWXYZ":
        for b in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                code = a + b + c
                if code not in SPECIAL_RESERVED:
                    codes.append(code)
    return codes


RANGE_CODES = _range_codes()
RANGE_CODE_INDEX = {code: i for i, code in enumerate(RANGE_CODES)}


def _pair_from_index(index: int) -> tuple[int, int]:
    pos = 0
    for start_day in range(1, 31):
        for end_day in range(start_day + 1, 32):
            if pos == index:
                return start_day, end_day
            pos += 1
    raise ValueError("Índice de intervalo inválido")


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


def decode_origin_and_period(raw_origin: str, month: str) -> tuple[str, date, date, str]:
    first, last = month_bounds(month)
    idx = RANGE_CODE_INDEX.get(raw_origin)
    if idx is not None and idx < len(REAL_ORIGINS) * RANGE_PAIR_COUNT:
        origin_index, pair_index = divmod(idx, RANGE_PAIR_COUNT)
        start_day, end_day = _pair_from_index(pair_index)
        if start_day > last.day or end_day > last.day:
            raise SystemExit("Intervalo não existe no mês selecionado")
        return (
            REAL_ORIGINS[origin_index],
            date(first.year, first.month, start_day),
            date(first.year, first.month, end_day),
            "range",
        )
    return raw_origin, first, last, "month"


def build_combinations(start_date: date, end_date: date, today: date) -> list[tuple[date, date]]:
    first_departure = max(start_date, today + timedelta(days=1))
    combos: list[tuple[date, date]] = []
    dep = first_departure
    while dep < end_date:
        ret = dep + timedelta(days=1)
        while ret <= end_date:
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


def run_fast_streaming(
    origin: str,
    destination: str,
    combos: list[tuple[date, date]],
    max_stops: int,
    workers: int,
    progress: Callable[[int, list[dict], list[tuple[date, date]], list[str], tuple[date, date]], None],
) -> tuple[list[dict], list[tuple[date, date]], list[str]]:
    rows: list[dict] = []
    missing: list[tuple[date, date]] = []
    errors: list[str] = []
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(fast_query, origin, destination, dep, ret, max_stops): (dep, ret) for dep, ret in combos}
        for future in as_completed(future_map):
            dep, ret = future_map[future]
            row, error = future.result()
            completed += 1
            if row:
                rows.append(row)
            else:
                missing.append((dep, ret))
            if error and len(errors) < 60:
                errors.append(error)
            progress(completed, rows, missing, errors, (dep, ret))
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
        timeout=max(180, min(900, len(combos) * 6)),
        check=False,
    )
    raw = (proc.stdout or "").strip()
    if not raw:
        return [], [(proc.stderr or "Swoop batch sem saída")[-1200:]]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], ["Swoop batch retornou JSON inválido: " + raw[-900:]]
    rows = list(data.get("results") or [])
    errors = list(data.get("errors") or [])[:60]
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


def pair_key(origin: str, destination: str, row: dict, max_stops: int) -> str:
    return "|".join([origin, destination, str(row.get("departure_date") or ""), str(row.get("return_date") or ""), str(max_stops)])


def load_history() -> dict:
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("pairs"), dict):
            return data
    except Exception:
        pass
    return {"version": 1, "updated_at": None, "pairs": {}}


def enrich_with_history(rows: list[dict], history: dict, origin: str, destination: str, max_stops: int) -> list[dict]:
    pairs = history.get("pairs") or {}
    enriched: list[dict] = []
    for original in rows:
        row = dict(original)
        old = pairs.get(pair_key(origin, destination, row, max_stops))
        if old and old.get("last_price") is not None:
            previous = float(old["last_price"])
            current = float(row["price"])
            change = current - previous
            pct = (change / previous * 100) if previous else 0.0
            row["previous_price"] = round(previous, 2)
            row["change_amount"] = round(change, 2)
            row["change_pct"] = round(pct, 1)
            row["trend"] = "down" if change < -0.01 else "up" if change > 0.01 else "same"
            row["historical_min"] = round(float(old.get("min_price", previous)), 2)
            row["history_samples"] = int(old.get("samples", 1))
            row["previous_seen_at"] = old.get("last_seen")
        else:
            row["previous_price"] = None
            row["change_amount"] = None
            row["change_pct"] = None
            row["trend"] = "new"
            row["historical_min"] = None
            row["history_samples"] = 0
            row["previous_seen_at"] = None
        enriched.append(row)
    return enriched


def merge_rows_into_history(history: dict, rows: list[dict], origin: str, destination: str, max_stops: int, observed_at: str) -> dict:
    pairs = history.setdefault("pairs", {})
    for row in dedupe(rows):
        if row.get("price") is None:
            continue
        key = pair_key(origin, destination, row, max_stops)
        price = round(float(row["price"]), 2)
        old = dict(pairs.get(key) or {})
        observations = list(old.get("observations") or [])
        if observations and observations[-1].get("at") == observed_at:
            continue
        observations.append({"at": observed_at, "price": price, "source": row.get("source_kind") or row.get("provider") or "Google"})
        observations = observations[-HISTORY_OBSERVATIONS:]
        samples = int(old.get("samples", 0)) + 1
        min_price = min(float(old.get("min_price", price)), price) if old else price
        max_price = max(float(old.get("max_price", price)), price) if old else price
        pairs[key] = {
            "origin": origin,
            "destination": destination,
            "departure_date": row.get("departure_date"),
            "return_date": row.get("return_date"),
            "max_stops": max_stops,
            "last_price": price,
            "last_seen": observed_at,
            "min_price": round(min_price, 2),
            "max_price": round(max_price, 2),
            "samples": samples,
            "observations": observations,
        }
    if len(pairs) > HISTORY_MAX_PAIRS:
        keep = sorted(pairs.items(), key=lambda kv: str(kv[1].get("last_seen") or ""), reverse=True)[:HISTORY_MAX_PAIRS]
        history["pairs"] = dict(keep)
    history["updated_at"] = observed_at
    history["version"] = 1
    return history


class GitHubLivePublisher:
    def __init__(self) -> None:
        self.token = os.environ.get("GITHUB_TOKEN", "").strip()
        self.repo = os.environ.get("GITHUB_REPOSITORY", "thenights20/viagens").strip()
        self.branch = LIVE_BRANCH
        self.path = LIVE_PATH
        self.enabled = bool(self.token and "/" in self.repo)
        self._branch_ready = False
        self._last_publish = 0.0
        self._last_completed = -1

    def _request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict | None]:
        if not self.enabled:
            return 0, None
        url = f"https://api.github.com/repos/{self.repo}{path}"
        body = None
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "flight-search-live",
        }
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {"message": raw[-500:]}
            return exc.code, data
        except Exception:
            return 0, None

    def ensure_branch(self) -> bool:
        if not self.enabled:
            return False
        if self._branch_ready:
            return True
        code, _ = self._request("GET", f"/git/ref/heads/{urllib.parse.quote(self.branch)}")
        if code == 200:
            self._branch_ready = True
            return True
        code, main = self._request("GET", "/git/ref/heads/main")
        if code != 200 or not main:
            return False
        sha = (((main.get("object") or {}).get("sha")) or "").strip()
        if not sha:
            return False
        code, _ = self._request("POST", "/git/refs", {"ref": f"refs/heads/{self.branch}", "sha": sha})
        self._branch_ready = code in (201, 422)
        return self._branch_ready

    def get_current(self) -> dict | None:
        if not self.ensure_branch():
            return None
        code, data = self._request("GET", f"/contents/{self.path}?ref={urllib.parse.quote(self.branch)}")
        if code != 200 or not data:
            return None
        try:
            content = base64.b64decode(data.get("content") or "").decode("utf-8")
            return json.loads(content)
        except Exception:
            return None

    def publish(self, payload: dict, message: str, force: bool = False, completed: int | None = None) -> bool:
        if not self.ensure_branch():
            return False
        now = time.monotonic()
        completed = int(completed or 0)
        if not force and now - self._last_publish < CHECKPOINT_SECONDS and completed - self._last_completed < CHECKPOINT_COMPLETIONS:
            return False
        for _ in range(4):
            code, current = self._request("GET", f"/contents/{self.path}?ref={urllib.parse.quote(self.branch)}")
            sha = current.get("sha") if code == 200 and current else None
            body = {
                "message": message,
                "content": base64.b64encode(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
                "branch": self.branch,
            }
            if sha:
                body["sha"] = sha
            code, _ = self._request("PUT", f"/contents/{self.path}", body)
            if code in (200, 201):
                self._last_publish = now
                self._last_completed = completed
                return True
            if code not in (409, 422):
                break
            time.sleep(1.0)
        return False


def history_summary(rows: list[dict]) -> dict:
    compared = [r for r in rows if r.get("previous_price") is not None]
    return {
        "compared": len(compared),
        "cheaper": sum(1 for r in compared if r.get("trend") == "down"),
        "higher": sum(1 for r in compared if r.get("trend") == "up"),
        "same": sum(1 for r in compared if r.get("trend") == "same"),
        "new": sum(1 for r in rows if r.get("trend") == "new"),
    }


def make_payload(
    *, request_id: str, origin: str, destination: str, month: str, max_stops: int,
    start_date: date, end_date: date, mode: str, all_rows: list[dict], history: dict,
    total: int, primary_completed: int, primary_total: int, fallback_done: int, fallback_total: int,
    status: str, stage: str, started_at: str, errors: list[str],
) -> dict:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    unique = dedupe(all_rows)
    enriched = enrich_with_history(unique, history, origin, destination, max_stops)
    enriched.sort(key=lambda row: (float(row.get("price") or 10**12), str(row.get("departure_date")), str(row.get("return_date"))))
    top = enriched[:MAX_RESULTS]
    for rank, row in enumerate(top, start=1):
        row["rank"] = rank
    priced = len(unique)
    return {
        "version": VERSION,
        "generated_at": now,
        "updated_at": now,
        "started_at": started_at,
        "status": status,
        "stage": stage,
        "mode": "full_month_matrix" if mode == "month" else "date_range_matrix",
        "request_id": request_id,
        "request": {
            "origin": origin,
            "destination": destination,
            "month": month,
            "period_mode": mode,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "max_stops": max_stops,
        },
        "stats": {
            "combinations": total,
            "processed_combinations": min(primary_completed, total),
            "primary_completed": min(primary_completed, primary_total),
            "primary_total": primary_total,
            "fallback_done": fallback_done,
            "fallback_total": fallback_total,
            "priced_combinations": priced,
            "coverage_pct": round((priced / total) * 100, 1) if total else 0.0,
            "lowest_price": round(float(top[0]["price"]), 2) if top else None,
            "result_count": len(top),
        },
        "history_summary": history_summary(enriched),
        "daily_min": daily_min(enriched),
        "results": top,
        "errors": errors[-60:],
    }


def main() -> None:
    raw_origin = str(os.environ.get("SEARCH_ORIGIN") or "GRU").strip().upper()
    destination = str(os.environ.get("SEARCH_DESTINATION") or "MIA").strip().upper()
    month = str(os.environ.get("SEARCH_MONTH") or "2026-10").strip()
    max_stops = int(os.environ.get("SEARCH_MAX_STOPS") or 2)
    request_id = str(os.environ.get("SEARCH_REQUEST_ID") or "manual").strip()[:80]
    fast_workers = int(os.environ.get("SEARCH_FAST_WORKERS") or 12)
    swoop_workers = int(os.environ.get("SEARCH_SWOOP_WORKERS") or 6)
    force_swoop = str(os.environ.get("SEARCH_FORCE_SWOOP") or "").lower() in {"1", "true", "yes"}

    origin, period_start, period_end, period_mode = decode_origin_and_period(raw_origin, month)

    if len(origin) != 3 or len(destination) != 3 or not origin.isalpha() or not destination.isalpha():
        raise SystemExit("Origem e destino precisam ser códigos IATA de 3 letras")
    if origin == destination:
        raise SystemExit("Origem e destino não podem ser iguais")
    if not 0 <= max_stops <= 2:
        raise SystemExit("Escalas precisa ficar entre 0 e 2")

    started = datetime.now(timezone.utc)
    started_iso = started.isoformat().replace("+00:00", "Z")
    combos = build_combinations(period_start, period_end, started.date())
    if not combos:
        raise SystemExit("O período selecionado não possui pares de datas futuras")

    publisher = GitHubLivePublisher()
    history = load_history()

    prior_live = publisher.get_current()
    if prior_live and isinstance(prior_live.get("results"), list):
        prior_req = prior_live.get("request") or {}
        try:
            prior_origin = str(prior_req.get("origin") or "")
            prior_destination = str(prior_req.get("destination") or "")
            if prior_origin and prior_destination:
                merge_rows_into_history(
                    history,
                    prior_live["results"],
                    prior_origin,
                    prior_destination,
                    int(prior_req.get("max_stops", 2)),
                    str(prior_live.get("updated_at") or prior_live.get("generated_at") or started_iso),
                )
        except Exception:
            pass

    all_rows: list[dict] = []
    all_errors: list[str] = []
    primary_completed = 0
    fallback_done = 0
    fallback_total = 0

    initial = make_payload(
        request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
        start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
        total=len(combos), primary_completed=0, primary_total=len(combos), fallback_done=0, fallback_total=0,
        status="running", stage="starting", started_at=started_iso, errors=[],
    )
    publisher.publish(initial, f"live: iniciar busca {request_id}", force=True, completed=0)

    def fast_progress(completed: int, rows: list[dict], missing: list[tuple[date, date]], errors: list[str], current_pair: tuple[date, date]) -> None:
        nonlocal primary_completed, all_rows, all_errors
        primary_completed = completed
        all_rows = list(rows)
        all_errors = list(errors)
        payload = make_payload(
            request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
            start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
            total=len(combos), primary_completed=completed, primary_total=len(combos), fallback_done=0, fallback_total=0,
            status="running", stage="google", started_at=started_iso, errors=all_errors,
        )
        payload["current_pair"] = {"departure_date": current_pair[0].isoformat(), "return_date": current_pair[1].isoformat()}
        publisher.publish(payload, f"live: {request_id} Google {completed}/{len(combos)}", completed=completed)

    try:
        fast_rows, missing, fast_errors = run_fast_streaming(origin, destination, combos, max_stops, fast_workers, fast_progress)
        all_rows = list(fast_rows)
        all_errors = list(fast_errors)
        primary_completed = len(combos)

        fast_ratio = len(fast_rows) / len(combos)
        regional = origin in {"DOU", "PMG", "JTC", "TJL", "ARU", "PPB", "MII"}
        use_swoop = force_swoop or regional or fast_ratio < 0.18
        swoop_rows: list[dict] = []
        swoop_errors: list[str] = []

        if use_swoop and missing:
            fallback_total = len(missing)
            batch_size = 30
            for offset in range(0, len(missing), batch_size):
                chunk = missing[offset: offset + batch_size]
                rows_chunk, errors_chunk = run_swoop_batch(origin, destination, chunk, max_stops, swoop_workers)
                swoop_rows.extend(rows_chunk)
                swoop_errors.extend(errors_chunk)
                fallback_done = min(len(missing), offset + len(chunk))
                all_rows = fast_rows + swoop_rows
                all_errors = (fast_errors + swoop_errors)[-60:]
                payload = make_payload(
                    request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
                    start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
                    total=len(combos), primary_completed=len(combos), primary_total=len(combos),
                    fallback_done=fallback_done, fallback_total=fallback_total, status="running", stage="fallback",
                    started_at=started_iso, errors=all_errors,
                )
                publisher.publish(payload, f"live: {request_id} confirmação {fallback_done}/{fallback_total}", force=True, completed=len(combos) + fallback_done)

        all_rows = dedupe(fast_rows + swoop_rows)
        all_errors = (fast_errors + swoop_errors)[-60:]

        final = make_payload(
            request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
            start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
            total=len(combos), primary_completed=len(combos), primary_total=len(combos), fallback_done=fallback_done,
            fallback_total=fallback_total, status="completed", stage="completed", started_at=started_iso, errors=all_errors,
        )

        observed_at = final["generated_at"]
        history = merge_rows_into_history(history, all_rows, origin, destination, max_stops, observed_at)
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
        publisher.publish(final, f"live: concluir busca {request_id}", force=True, completed=len(combos) + fallback_done)

        print(
            f"Busca {request_id} {origin}->{destination} {period_start.isoformat()}..{period_end.isoformat()}: "
            f"{len(all_rows)}/{len(combos)} combinações com preço, top {len(final['results'])}, "
            f"menor R$ {final['stats']['lowest_price'] if final['results'] else '-'}"
        )
    except BaseException as exc:
        partial = make_payload(
            request_id=request_id, origin=origin, destination=destination, month=month, max_stops=max_stops,
            start_date=period_start, end_date=period_end, mode=period_mode, all_rows=all_rows, history=history,
            total=len(combos), primary_completed=primary_completed, primary_total=len(combos), fallback_done=fallback_done,
            fallback_total=fallback_total, status="partial", stage="interrupted", started_at=started_iso,
            errors=all_errors + [f"{type(exc).__name__}: {exc}"],
        )
        publisher.publish(partial, f"live: parcial salvo {request_id}", force=True, completed=primary_completed + fallback_done)
        raise


if __name__ == "__main__":
    main()
