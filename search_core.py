from __future__ import annotations

import inspect
import json
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import quote_plus

from airport_catalog import airports_for_regions


APP_NAME = "Flight Deals Local"
APP_VERSION = "0.4.0"
DATA_DIR = Path.home() / "FlightDealsLocal"
DB_PATH = DATA_DIR / "flight_deals.db"


@dataclass(slots=True)
class Deal:
    origin: str
    destination: str
    departure_date: str
    return_date: str
    airline: str
    price_text: str
    price_value: float
    duration: str
    duration_minutes: int
    stops: str
    stops_count: int
    departure: str
    arrival: str
    query_url: str
    badge: str = "MENOR PREÇO DA ROTA"


@dataclass(slots=True)
class SearchPlan:
    routes: list[tuple[str, str]]
    pairs: list[tuple[date, date]]

    @property
    def total(self) -> int:
        return len(self.routes) * len(self.pairs)

    def item(self, index: int) -> tuple[str, str, date, date]:
        if not self.routes or not self.pairs:
            raise IndexError(index)
        pair_index, route_index = divmod(index, len(self.routes))
        dep, ret = self.pairs[pair_index]
        origin, destination = self.routes[route_index]
        return origin, destination, dep, ret


def parse_airports(raw: str) -> list[str]:
    result: list[str] = []
    for item in re.split(r"[,;\s]+", raw.upper().strip()):
        if re.fullmatch(r"[A-Z]{3}", item) and item not in result:
            result.append(item)
    return result


def _days(start: date, end: date, step: int = 1) -> list[date]:
    if end < start:
        raise ValueError("A data final não pode ser anterior à data inicial.")
    return [start + timedelta(days=i) for i in range(0, (end - start).days + 1, step)]


def _month_dates(raw: str) -> list[date]:
    from calendar import monthrange

    result: list[date] = []
    for token in re.split(r"[,;\s]+", raw.strip()):
        if not token:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}", token):
            raise ValueError(f"Mês inválido: {token}. Use AAAA-MM.")
        year, month = map(int, token.split("-"))
        if not 1 <= month <= 12:
            raise ValueError(f"Mês inválido: {token}.")
        result.extend(date(year, month, day) for day in range(1, monthrange(year, month)[1] + 1))
    return sorted(set(result))


def _sample(values: list[Any], step: int) -> list[Any]:
    if step <= 1 or len(values) <= 2:
        return values
    sampled = values[::step]
    if values[-1] not in sampled:
        sampled.append(values[-1])
    return sampled


def build_plan(params: dict[str, Any]) -> SearchPlan:
    origins = parse_airports(params.get("origins", ""))
    destinations = parse_airports(params.get("destinations", ""))
    for code in airports_for_regions(params.get("origin_regions", [])):
        if code not in origins:
            origins.append(code)
    for code in airports_for_regions(params.get("destination_regions", [])):
        if code not in destinations:
            destinations.append(code)

    routes = [(o, d) for o in origins for d in destinations if o != d]
    if not routes:
        raise ValueError("Informe ao menos uma origem e um destino diferentes.")

    depth = params.get("depth", "Profundo")
    day_step = {"Rápido": 7, "Equilibrado": 3, "Profundo": 1, "Máximo": 1}.get(depth, 1)
    night_step = {"Rápido": 4, "Equilibrado": 2, "Profundo": 1, "Máximo": 1}.get(depth, 1)
    mode = params.get("date_mode", "Próximos 12 meses")
    min_nights = max(1, int(params.get("min_nights", 3)))
    max_nights = max(min_nights, int(params.get("max_nights", 14) or min_nights))

    if mode == "Próximos 12 meses":
        # Mantém a data original para que o índice salvo continue apontando para
        # a mesma combinação quando a pesquisa for retomada dias depois.
        start = params.get("dep_start", date.today() + timedelta(days=1))
        end = min(start + timedelta(days=364), params.get("dep_end", start + timedelta(days=364)))
        departures = _days(start, end, day_step)
        nights = _sample(list(range(min_nights, max_nights + 1)), night_step)
        pairs = [(dep, dep + timedelta(days=stay)) for dep in departures for stay in nights]
    else:
        if mode == "Meses flexíveis":
            departures = _month_dates(params.get("dep_months", ""))
            returns = _month_dates(params.get("ret_months", ""))
        else:
            departures = _days(params["dep_start"], params["dep_end"])
            returns = _days(params["ret_start"], params["ret_end"])
        departures = _sample(departures, day_step)
        pairs = []
        for dep in departures:
            compatible = [ret for ret in returns if min_nights <= (ret - dep).days <= max_nights]
            for ret in _sample(compatible, night_step):
                pairs.append((dep, ret))

    pairs = sorted(set(pairs))
    if not pairs:
        raise ValueError("Não existem combinações de ida e volta com as datas e noites informadas.")
    return SearchPlan(routes=routes, pairs=pairs)


class Store:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self._schema()

    def _schema(self) -> None:
        with self.lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS search_jobs_v04 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    cursor INTEGER NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL,
                    errors INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS job_best_v04 (
                    job_id INTEGER NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    airline TEXT NOT NULL,
                    price_text TEXT NOT NULL,
                    price_value REAL NOT NULL,
                    duration TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    stops TEXT NOT NULL,
                    stops_count INTEGER NOT NULL,
                    departure TEXT NOT NULL,
                    arrival TEXT NOT NULL,
                    query_url TEXT NOT NULL,
                    badge TEXT NOT NULL,
                    PRIMARY KEY (job_id, origin, destination)
                );
                CREATE TABLE IF NOT EXISTS deals_history_v04 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    searched_at TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    departure_date TEXT NOT NULL,
                    return_date TEXT NOT NULL,
                    airline TEXT NOT NULL,
                    price_value REAL NOT NULL,
                    query_url TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_history_route_v04
                    ON deals_history_v04(origin, destination, price_value);
                CREATE TABLE IF NOT EXISTS query_cache_v04 (
                    cache_key TEXT PRIMARY KEY,
                    searched_at TEXT NOT NULL,
                    deal_json TEXT
                );
            """)
            self.conn.commit()

    @staticmethod
    def _json_params(params: dict[str, Any]) -> str:
        serializable = dict(params)
        for key in ("dep_start", "dep_end", "ret_start", "ret_end"):
            value = serializable.get(key)
            if isinstance(value, date):
                serializable[key] = value.isoformat()
        return json.dumps(serializable, ensure_ascii=False)

    @staticmethod
    def _params(raw: str) -> dict[str, Any]:
        params = json.loads(raw)
        for key in ("dep_start", "dep_end", "ret_start", "ret_end"):
            if isinstance(params.get(key), str):
                params[key] = date.fromisoformat(params[key])
        return params

    def create_job(self, params: dict[str, Any], total: int) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO search_jobs_v04(created_at,updated_at,status,params_json,total) VALUES(?,?,?,?,?)",
                (now, now, "running", self._json_params(params), total),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def update_job(self, job_id: int, cursor: int, status: str, errors: int) -> None:
        with self.lock:
            self.conn.execute(
                "UPDATE search_jobs_v04 SET updated_at=?,cursor=?,status=?,errors=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), cursor, status, errors, job_id),
            )
            self.conn.commit()

    def job(self, job_id: int) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM search_jobs_v04 WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["params"] = self._params(result.pop("params_json"))
        return result

    def latest_resumable(self) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM search_jobs_v04 WHERE status IN ('running','paused','interrupted') ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["params"] = self._params(result.pop("params_json"))
        return result

    def historical_min(self, origin: str, destination: str) -> float | None:
        with self.lock:
            row = self.conn.execute(
                "SELECT MIN(price_value) AS value FROM deals_history_v04 WHERE origin=? AND destination=?",
                (origin, destination),
            ).fetchone()
        return float(row["value"]) if row and row["value"] is not None else None

    def save_best(self, job_id: int, deal: Deal) -> bool:
        previous = self.historical_min(deal.origin, deal.destination)
        deal.badge = "NOVO RECORDE" if previous is not None and deal.price_value < previous else "MENOR PREÇO DA ROTA"
        values = asdict(deal)
        with self.lock:
            row = self.conn.execute(
                "SELECT price_value FROM job_best_v04 WHERE job_id=? AND origin=? AND destination=?",
                (job_id, deal.origin, deal.destination),
            ).fetchone()
            if row and float(row["price_value"]) <= deal.price_value:
                return False
            columns = ["job_id", *values.keys()]
            placeholders = ",".join("?" for _ in columns)
            updates = ",".join(f"{name}=excluded.{name}" for name in values if name not in {"origin", "destination"})
            self.conn.execute(
                f"INSERT INTO job_best_v04({','.join(columns)}) VALUES({placeholders}) "
                f"ON CONFLICT(job_id,origin,destination) DO UPDATE SET {updates}",
                (job_id, *values.values()),
            )
            self.conn.commit()
        return True

    def best(self, job_id: int, limit: int = 50) -> list[Deal]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT origin,destination,departure_date,return_date,airline,price_text,price_value,duration,"
                "duration_minutes,stops,stops_count,departure,arrival,query_url,badge "
                "FROM job_best_v04 WHERE job_id=? ORDER BY price_value ASC LIMIT ?",
                (job_id, limit),
            ).fetchall()
        return [Deal(**dict(row)) for row in rows]

    def archive(self, job_id: int) -> None:
        with self.lock:
            exists = self.conn.execute("SELECT 1 FROM deals_history_v04 WHERE job_id=? LIMIT 1", (job_id,)).fetchone()
            if exists:
                return
            now = datetime.now().isoformat(timespec="seconds")
            self.conn.execute(
                "INSERT INTO deals_history_v04(job_id,searched_at,origin,destination,departure_date,return_date,airline,price_value,query_url) "
                "SELECT job_id,?,origin,destination,departure_date,return_date,airline,price_value,query_url "
                "FROM job_best_v04 WHERE job_id=?",
                (now, job_id),
            )
            self.conn.commit()

    def cache_get(self, key: str, max_age_hours: int = 6) -> Deal | None | bool:
        with self.lock:
            row = self.conn.execute("SELECT searched_at,deal_json FROM query_cache_v04 WHERE cache_key=?", (key,)).fetchone()
        if not row:
            return False
        searched = datetime.fromisoformat(row["searched_at"])
        if datetime.now() - searched > timedelta(hours=max_age_hours):
            return False
        return Deal(**json.loads(row["deal_json"])) if row["deal_json"] else None

    def cache_put(self, key: str, deal: Deal | None) -> None:
        payload = json.dumps(asdict(deal), ensure_ascii=False) if deal else None
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO query_cache_v04(cache_key,searched_at,deal_json) VALUES(?,?,?)",
                (key, datetime.now().isoformat(timespec="seconds"), payload),
            )
            self.conn.commit()


def google_url(origin: str, destination: str, dep: date, ret: date) -> str:
    query = f"Flights from {origin} to {destination} on {dep.isoformat()} returning {ret.isoformat()}"
    return "https://www.google.com/travel/flights?q=" + quote_plus(query)


def _price(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        cleaned = re.sub(r"[^0-9,.]", "", str(value or ""))
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            head, tail = cleaned.rsplit(",", 1)
            cleaned = head + tail if len(tail) == 3 else head + "." + tail
        elif "." in cleaned:
            head, tail = cleaned.rsplit(".", 1)
            if len(tail) == 3:
                cleaned = head.replace(".", "") + tail
        return float(cleaned or 0)


def _duration_minutes(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value or "")
    hours = re.search(r"(\d+)\s*h", text)
    minutes = re.search(r"(\d+)\s*m", text)
    return (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)


def _deal(flight: Any, origin: str, destination: str, dep: date, ret: date) -> Deal | None:
    price_value = _price(getattr(flight, "price", 0))
    if price_value <= 0:
        return None
    airlines = getattr(flight, "airlines", None)
    airline = ", ".join(map(str, airlines)) if isinstance(airlines, list) else str(
        getattr(flight, "name", getattr(flight, "airline", "Não informado"))
    )
    legs = list(getattr(flight, "flights", []) or [])
    if legs:
        duration_minutes = sum(int(getattr(item, "duration", 0) or 0) for item in legs)
        stops_count = max(0, len(legs) - 1)
        departure = str(getattr(legs[0], "departure", ""))
        arrival = str(getattr(legs[-1], "arrival", ""))
    else:
        duration_minutes = _duration_minutes(getattr(flight, "duration", ""))
        stops_raw = str(getattr(flight, "stops", ""))
        match = re.search(r"\d+", stops_raw)
        stops_count = int(match.group()) if match else 0
        departure = str(getattr(flight, "departure", ""))
        arrival = str(getattr(flight, "arrival", ""))
    return Deal(
        origin=origin,
        destination=destination,
        departure_date=dep.isoformat(),
        return_date=ret.isoformat(),
        airline=airline or "Não informado",
        price_text=f"R$ {price_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        price_value=price_value,
        duration=f"{duration_minutes // 60}h {duration_minutes % 60:02d}min" if duration_minutes else "",
        duration_minutes=duration_minutes,
        stops="Direto" if stops_count == 0 else f"{stops_count} escala" + ("s" if stops_count != 1 else ""),
        stops_count=stops_count,
        departure=departure,
        arrival=arrival,
        query_url=google_url(origin, destination, dep, ret),
    )


def _supported(func: Any, values: dict[str, Any]) -> dict[str, Any]:
    allowed = inspect.signature(func).parameters
    return {key: value for key, value in values.items() if key in allowed and value is not None}


def query_cheapest(origin: str, destination: str, dep: date, ret: date, params: dict[str, Any]) -> Deal | None:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights

    outbound = FlightQuery(**_supported(FlightQuery, {
        "date": dep.isoformat(), "from_airport": origin, "to_airport": destination,
        "max_stops": params.get("max_stops", 2),
    }))
    inbound = FlightQuery(**_supported(FlightQuery, {
        "date": ret.isoformat(), "from_airport": destination, "to_airport": origin,
        "max_stops": params.get("max_stops", 2),
    }))
    query = create_query(**_supported(create_query, {
        "flights": [outbound, inbound], "seat": params.get("seat", "economy"),
        "trip": "round-trip", "passengers": Passengers(adults=params.get("adults", 1)),
        "language": "pt-BR", "currency": params.get("currency", "BRL"),
        "max_price": params.get("max_price") or None,
    }))
    response = get_flights(query)
    items = response if isinstance(response, list) else list(getattr(response, "flights", []) or [])
    deals = [deal for item in items if (deal := _deal(item, origin, destination, dep, ret))]
    return min(deals, key=lambda item: item.price_value, default=None)


class SearchEngine:
    def __init__(self, store: Store, events: Any, pause_event: threading.Event, cancel_event: threading.Event) -> None:
        self.store = store
        self.events = events
        self.pause_event = pause_event
        self.cancel_event = cancel_event

    @staticmethod
    def _cache_key(origin: str, destination: str, dep: date, ret: date, params: dict[str, Any]) -> str:
        return "|".join(map(str, (
            origin, destination, dep, ret, params.get("seat"), params.get("adults"),
            params.get("max_stops"), params.get("currency"), params.get("max_price"),
        )))

    @staticmethod
    def _keep_awake(enable: bool) -> None:
        try:
            import ctypes
            if enable:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
            else:
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        except (AttributeError, OSError):
            pass

    def run(self, params: dict[str, Any], job_id: int | None = None) -> None:
        try:
            plan = build_plan(params)
        except Exception as exc:
            self.events.put(("error", str(exc)))
            return
        if job_id is None:
            job_id = self.store.create_job(params, plan.total)
            cursor = 0
            errors = 0
        else:
            job = self.store.job(job_id)
            if not job:
                self.events.put(("error", "A pesquisa salva não foi encontrada."))
                return
            cursor = min(int(job["cursor"]), plan.total)
            errors = int(job["errors"])
            self.store.update_job(job_id, cursor, "running", errors)

        self.events.put(("started", (job_id, cursor, plan.total, len(plan.routes), len(plan.pairs))))
        delay = {"Rápido": 0.2, "Equilibrado": 0.35, "Profundo": 0.6, "Máximo": 0.9}.get(params.get("depth"), 0.6)
        started = time.monotonic()
        processed_session = 0
        self._keep_awake(True)
        try:
            for index in range(cursor, plan.total):
                if self.cancel_event.is_set():
                    self.store.update_job(job_id, index, "cancelled", errors)
                    self.events.put(("cancelled", (job_id, self.store.best(job_id, 50))))
                    return
                if self.pause_event.is_set():
                    self.store.update_job(job_id, index, "paused", errors)
                    self.events.put(("paused", (job_id, self.store.best(job_id, 50))))
                    return

                origin, destination, dep, ret = plan.item(index)
                next_cursor = index + 1
                cached = self.store.cache_get(self._cache_key(origin, destination, dep, ret, params))
                try:
                    if cached is False:
                        cheapest = query_cheapest(origin, destination, dep, ret, params)
                        self.store.cache_put(self._cache_key(origin, destination, dep, ret, params), cheapest)
                    else:
                        cheapest = cached
                    if isinstance(cheapest, Deal) and self.store.save_best(job_id, cheapest):
                        self.events.put(("new_best", (job_id, cheapest)))
                except Exception as exc:
                    errors += 1
                    self.events.put(("log", f"Falha em {origin}–{destination} {dep:%d/%m}: {exc}"))

                self.store.update_job(job_id, next_cursor, "running", errors)
                processed_session += 1
                elapsed = max(time.monotonic() - started, 0.001)
                speed = processed_session / elapsed
                remaining_seconds = int((plan.total - next_cursor) / speed) if speed else 0
                self.events.put(("progress", (
                    job_id, next_cursor, plan.total, errors, remaining_seconds,
                    f"{origin} → {destination} | {dep:%d/%m/%Y}–{ret:%d/%m/%Y}",
                )))
                if cached is False:
                    time.sleep(delay)

            self.store.update_job(job_id, plan.total, "complete", errors)
            self.store.archive(job_id)
            self.events.put(("complete", (job_id, self.store.best(job_id, 50))))
        finally:
            self._keep_awake(False)
