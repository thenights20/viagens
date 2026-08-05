from __future__ import annotations

import csv
import queue
import re
import sqlite3
import statistics
import threading
import time
import webbrowser
from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, IntVar, Listbox, MULTIPLE, StringVar, Tk, Toplevel, filedialog, messagebox
from tkinter import ttk
from typing import Any, Iterable

from airport_catalog import AIRPORTS_BY_REGION, airports_for_regions
from fast_flights import FlightQuery, Passengers, create_query, get_flights

APP_NAME = "Flight Deals Local"
APP_VERSION = "0.3.0"
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
    score: float = 0.0
    badge: str = ""


class Store:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS deals_v03 (
                id INTEGER PRIMARY KEY AUTOINCREMENT, searched_at TEXT NOT NULL,
                origin TEXT, destination TEXT, departure_date TEXT, return_date TEXT,
                airline TEXT, price_text TEXT, price_value REAL, duration TEXT,
                duration_minutes INTEGER, stops TEXT, stops_count INTEGER,
                departure TEXT, arrival TEXT, query_url TEXT, score REAL, badge TEXT
            )
        """)
        self.conn.commit()

    def save(self, deals: Iterable[Deal]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        rows = [(now, *asdict(d).values()) for d in deals]
        self.conn.executemany("""
            INSERT INTO deals_v03 (
                searched_at, origin, destination, departure_date, return_date,
                airline, price_text, price_value, duration, duration_minutes,
                stops, stops_count, departure, arrival, query_url, score, badge
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        self.conn.commit()

    def route_stats(self, origin: str, destination: str) -> tuple[float | None, float | None]:
        row = self.conn.execute(
            "SELECT AVG(price_value), MIN(price_value) FROM deals_v03 WHERE origin=? AND destination=? AND price_value>0",
            (origin, destination),
        ).fetchone()
        return (row[0], row[1]) if row else (None, None)


class RegionPicker:
    def __init__(self, parent: Tk, title: str, selected: list[str], callback) -> None:
        self.top = Toplevel(parent)
        self.top.title(title)
        self.top.geometry("520x560")
        self.callback = callback
        ttk.Label(self.top, text="Selecione um ou vários estados/regiões:").pack(anchor="w", padx=12, pady=(12, 4))
        self.listbox = Listbox(self.top, selectmode=MULTIPLE, exportselection=False)
        self.listbox.pack(fill=BOTH, expand=True, padx=12, pady=6)
        keys = list(AIRPORTS_BY_REGION)
        for idx, item in enumerate(keys):
            self.listbox.insert(END, item)
            if item in selected:
                self.listbox.selection_set(idx)
        bar = ttk.Frame(self.top)
        bar.pack(fill=X, padx=12, pady=10)
        ttk.Button(bar, text="Limpar", command=lambda: self.listbox.selection_clear(0, END)).pack(side=LEFT)
        ttk.Button(bar, text="Aplicar", command=self.apply).pack(side=RIGHT)

    def apply(self) -> None:
        chosen = [self.listbox.get(i) for i in self.listbox.curselection()]
        self.callback(chosen)
        self.top.destroy()


class SearchEngine:
    def __init__(self, store: Store, events: queue.Queue[tuple[str, Any]], stop_event: threading.Event) -> None:
        self.store = store
        self.events = events
        self.stop_event = stop_event

    @staticmethod
    def parse_airports(raw: str) -> list[str]:
        result: list[str] = []
        for item in re.split(r"[,;\s]+", raw.upper().strip()):
            if re.fullmatch(r"[A-Z]{3}", item) and item not in result:
                result.append(item)
        return result

    @staticmethod
    def dates(start: date, end: date) -> list[date]:
        return [start + timedelta(days=i) for i in range((end - start).days + 1)]

    @staticmethod
    def month_dates(raw: str) -> list[date]:
        result: list[date] = []
        for token in re.split(r"[,;\s]+", raw.strip()):
            if not token:
                continue
            if not re.fullmatch(r"\d{4}-\d{2}", token):
                raise ValueError(f"Mês inválido: {token}. Use AAAA-MM.")
            year, month = map(int, token.split("-"))
            if month < 1 or month > 12:
                raise ValueError(f"Mês inválido: {token}.")
            days = monthrange(year, month)[1]
            result.extend(date(year, month, day) for day in range(1, days + 1))
        return sorted(set(result))

    @staticmethod
    def build_pairs(dep_dates: list[date], ret_dates: list[date], min_nights: int, max_nights: int) -> list[tuple[date, date]]:
        pairs = []
        for dep in dep_dates:
            for ret in ret_dates:
                nights = (ret - dep).days
                if nights <= 0:
                    continue
                if min_nights and nights < min_nights:
                    continue
                if max_nights and nights > max_nights:
                    continue
                pairs.append((dep, ret))
        return pairs

    @staticmethod
    def google_url(origin: str, destination: str, dep: str, ret: str) -> str:
        query = f"Flights from {origin} to {destination} on {dep} returning {ret}"
        return "https://www.google.com/travel/flights?q=" + query.replace(" ", "+")

    @staticmethod
    def parse_duration_minutes(value: Any) -> int:
        if isinstance(value, int):
            return value
        text = str(value or "")
        h = re.search(r"(\d+)\s*h", text)
        m = re.search(r"(\d+)\s*m", text)
        return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)

    @staticmethod
    def duration_text(minutes: int) -> str:
        return f"{minutes // 60}h {minutes % 60:02d}min" if minutes else ""

    @staticmethod
    def response_items(response: Any) -> list[Any]:
        if isinstance(response, list):
            return response
        return list(getattr(response, "flights", []) or [])

    def convert_flight(self, flight: Any, origin: str, destination: str, dep: date, ret: date) -> Deal | None:
        price = getattr(flight, "price", 0)
        try:
            price_value = float(price)
        except (TypeError, ValueError):
            cleaned = re.sub(r"[^0-9,.]", "", str(price))
            cleaned = cleaned.replace(".", "").replace(",", ".") if "," in cleaned else cleaned
            price_value = float(cleaned or 0)
        if price_value <= 0:
            return None

        airlines_raw = getattr(flight, "airlines", None)
        if isinstance(airlines_raw, list):
            airline = ", ".join(str(x) for x in airlines_raw)
        else:
            airline = str(getattr(flight, "name", getattr(flight, "airline", "Não informado")))

        legs = list(getattr(flight, "flights", []) or [])
        if legs:
            duration_minutes = sum(int(getattr(x, "duration", 0) or 0) for x in legs)
            stops_count = max(0, len(legs) - 1)
            first, last = legs[0], legs[-1]
            departure = str(getattr(first, "departure", ""))
            arrival = str(getattr(last, "arrival", ""))
        else:
            duration_minutes = self.parse_duration_minutes(getattr(flight, "duration", ""))
            stops_value = str(getattr(flight, "stops", ""))
            match = re.search(r"\d+", stops_value)
            stops_count = int(match.group()) if match else (0 if "direto" in stops_value.lower() else 0)
            departure = str(getattr(flight, "departure", ""))
            arrival = str(getattr(flight, "arrival", ""))

        stops = "Direto" if stops_count == 0 else f"{stops_count} escala" + ("s" if stops_count > 1 else "")
        return Deal(
            origin=origin, destination=destination, departure_date=dep.isoformat(), return_date=ret.isoformat(),
            airline=airline, price_text=f"{price_value:.0f}", price_value=price_value,
            duration=self.duration_text(duration_minutes), duration_minutes=duration_minutes,
            stops=stops, stops_count=stops_count, departure=departure, arrival=arrival,
            query_url=self.google_url(origin, destination, dep.isoformat(), ret.isoformat()),
        )

    def rank(self, deals: list[Deal], top_n: int) -> list[Deal]:
        if not deals:
            return []
        prices = [d.price_value for d in deals]
        durations = [d.duration_minutes for d in deals if d.duration_minutes > 0]
        min_price, max_price = min(prices), max(prices)
        min_duration, max_duration = (min(durations), max(durations)) if durations else (0, 0)
        median_price = statistics.median(prices)

        for d in deals:
            price_component = 70.0 if max_price == min_price else 70.0 * (max_price - d.price_value) / (max_price - min_price)
            duration_component = 18.0
            if d.duration_minutes and max_duration > min_duration:
                duration_component = 18.0 * (max_duration - d.duration_minutes) / (max_duration - min_duration)
            stop_component = max(0.0, 12.0 - d.stops_count * 5.0)
            historical_avg, historical_min = self.store.route_stats(d.origin, d.destination)
            history_bonus = 0.0
            if historical_avg and d.price_value < historical_avg:
                history_bonus += min(4.0, ((historical_avg - d.price_value) / historical_avg) * 10)
            if historical_min and d.price_value <= historical_min:
                history_bonus += 2.0
            d.score = max(0.0, min(100.0, price_component + duration_component + stop_component + history_bonus))
            if d.price_value > median_price * 1.75:
                d.score = max(0.0, d.score - 8.0)

        cheapest = min(deals, key=lambda x: x.price_value)
        fastest = min((d for d in deals if d.duration_minutes > 0), key=lambda x: x.duration_minutes, default=cheapest)
        direct = min((d for d in deals if d.stops_count == 0), key=lambda x: x.price_value, default=None)
        best = max(deals, key=lambda x: (x.score, -x.price_value))
        for d in deals:
            badges = []
            if d is cheapest: badges.append("MENOR PREÇO")
            if d is best: badges.append("MELHOR GERAL")
            if direct is not None and d is direct: badges.append("MELHOR DIRETO")
            if d is fastest: badges.append("MAIS RÁPIDO")
            d.badge = " • ".join(badges)

        unique: dict[tuple[Any, ...], Deal] = {}
        for d in deals:
            key = (d.origin, d.destination, d.departure_date, d.return_date, d.airline, round(d.price_value, 2))
            if key not in unique or d.score > unique[key].score:
                unique[key] = d
        return sorted(unique.values(), key=lambda x: (-x.score, x.price_value))[:top_n]

    def search(self, params: dict[str, Any]) -> None:
        origins = self.parse_airports(params["origins"])
        destinations = self.parse_airports(params["destinations"])
        for code in airports_for_regions(params["origin_regions"]):
            if code not in origins: origins.append(code)
        for code in airports_for_regions(params["destination_regions"]):
            if code not in destinations: destinations.append(code)

        if params["date_mode"] == "Meses flexíveis":
            dep_dates = self.month_dates(params["dep_months"])
            ret_dates = self.month_dates(params["ret_months"])
        else:
            dep_dates = self.dates(params["dep_start"], params["dep_end"])
            ret_dates = self.dates(params["ret_start"], params["ret_end"])
        pairs = self.build_pairs(dep_dates, ret_dates, params["min_nights"], params["max_nights"])
        total = sum(1 for o in origins for d in destinations if o != d) * len(pairs)
        if not origins or not destinations or not pairs:
            self.events.put(("error", "Informe origens, destinos e datas válidas."))
            return
        self.events.put(("summary", (len(origins), len(destinations), len(dep_dates), len(ret_dates), len(pairs), total)))

        found: list[Deal] = []
        done = 0
        for origin in origins:
            for destination in destinations:
                if origin == destination:
                    continue
                for dep, ret in pairs:
                    if self.stop_event.is_set():
                        ranked = self.rank(found, params["top_n"])
                        self.store.save(ranked)
                        self.events.put(("stopped", ranked))
                        return
                    done += 1
                    self.events.put(("progress", (done, total, f"{origin} → {destination} | {dep:%d/%m}–{ret:%d/%m}")))
                    try:
                        query = create_query(
                            flights=[
                                FlightQuery(date=dep.isoformat(), from_airport=origin, to_airport=destination, max_stops=params["max_stops"]),
                                FlightQuery(date=ret.isoformat(), from_airport=destination, to_airport=origin, max_stops=params["max_stops"]),
                            ],
                            seat=params["seat"], trip="round-trip",
                            passengers=Passengers(adults=params["adults"]), language="pt-BR",
                            currency=params["currency"], max_price=params["max_price"] or None,
                        )
                        response = get_flights(query)
                        for flight in self.response_items(response)[:params["per_query"]]:
                            deal = self.convert_flight(flight, origin, destination, dep, ret)
                            if deal:
                                found.append(deal)
                    except Exception as exc:
                        self.events.put(("log", f"Falha em {origin}-{destination} {dep}/{ret}: {exc}"))
                    time.sleep(params["delay"])
        ranked = self.rank(found, params["top_n"])
        self.store.save(ranked)
        self.events.put(("complete", ranked))


class App:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1380x820")
        self.store = Store()
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.results: list[Deal] = []
        self.origin_regions: list[str] = []
        self.destination_regions: list[str] = []
        self._vars()
        self._ui()
        self.root.after(150, self._poll)

    def _vars(self) -> None:
        today = date.today()
        self.origins = StringVar(value="CGR, GRU, VCP")
        self.destinations = StringVar(value="MIA, FLL, MCO")
        self.origin_regions_text = StringVar(value="Nenhum estado selecionado")
        self.destination_regions_text = StringVar(value="Nenhum estado selecionado")
        self.date_mode = StringVar(value="Datas/Intervalo")
        self.dep_start = StringVar(value=(today + timedelta(days=60)).isoformat())
        self.dep_end = StringVar(value=(today + timedelta(days=67)).isoformat())
        self.ret_start = StringVar(value=(today + timedelta(days=68)).isoformat())
        self.ret_end = StringVar(value=(today + timedelta(days=80)).isoformat())
        self.dep_months = StringVar(value=f"{today.year + 1}-01")
        self.ret_months = StringVar(value=f"{today.year + 1}-02")
        self.min_nights = IntVar(value=0)
        self.max_nights = IntVar(value=0)
        self.adults = IntVar(value=1)
        self.max_stops = IntVar(value=2)
        self.max_price = IntVar(value=0)
        self.top_n = IntVar(value=20)
        self.seat = StringVar(value="economy")
        self.currency = StringVar(value="BRL")
        self.depth = StringVar(value="Rápido")
        self.status_text = StringVar(value="Pronto.")
        self.summary_text = StringVar(value="")
        self.progress_value = IntVar(value=0)

    def _ui(self) -> None:
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(fill=BOTH, expand=True)
        form = ttk.LabelFrame(frame, text="Pesquisa de preços", padding=10)
        form.pack(fill=X)

        ttk.Label(form, text="Origens (IATA)").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(form, textvariable=self.origins, width=42).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(form, text="Selecionar estados", command=lambda: self.pick_regions(True)).grid(row=0, column=2, padx=4)
        ttk.Label(form, textvariable=self.origin_regions_text, width=38).grid(row=0, column=3, sticky="w", padx=4)

        ttk.Label(form, text="Destinos (IATA)").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(form, textvariable=self.destinations, width=42).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Button(form, text="Selecionar estados", command=lambda: self.pick_regions(False)).grid(row=1, column=2, padx=4)
        ttk.Label(form, textvariable=self.destination_regions_text, width=38).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(form, text="Modo de datas").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        mode = ttk.Combobox(form, textvariable=self.date_mode, values=["Datas/Intervalo", "Meses flexíveis"], state="readonly", width=20)
        mode.grid(row=2, column=1, sticky="w", padx=4)
        mode.bind("<<ComboboxSelected>>", lambda _e: self.update_date_mode())

        self.date_frame = ttk.Frame(form)
        self.date_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=4)
        self.update_date_mode()

        opts = ttk.Frame(form)
        opts.grid(row=4, column=0, columnspan=4, sticky="ew", pady=6)
        for label, var, max_value in [
            ("Noites mín.", self.min_nights, 365), ("Noites máx. (0=livre)", self.max_nights, 365),
            ("Adultos", self.adults, 9), ("Escalas máx.", self.max_stops, 4), ("Preço máx. (0=livre)", self.max_price, 99999),
        ]:
            ttk.Label(opts, text=label).pack(side=LEFT, padx=(3, 2))
            ttk.Spinbox(opts, from_=0, to=max_value, textvariable=var, width=6).pack(side=LEFT, padx=(0, 7))
        ttk.Label(opts, text="Classe").pack(side=LEFT, padx=(4, 2))
        ttk.Combobox(opts, textvariable=self.seat, values=["economy", "premium-economy", "business", "first"], state="readonly", width=16).pack(side=LEFT)
        ttk.Label(opts, text="Moeda").pack(side=LEFT, padx=(8, 2))
        ttk.Combobox(opts, textvariable=self.currency, values=["BRL", "USD", "EUR"], state="readonly", width=6).pack(side=LEFT)

        controls = ttk.Frame(form)
        controls.grid(row=5, column=0, columnspan=4, sticky="ew", pady=6)
        ttk.Label(controls, text="Profundidade").pack(side=LEFT)
        ttk.Combobox(controls, textvariable=self.depth, values=["Rápido", "Equilibrado", "Profundo", "Máximo"], state="readonly", width=12).pack(side=LEFT, padx=4)
        ttk.Label(controls, text="Resultados finais").pack(side=LEFT, padx=(12, 3))
        ttk.Combobox(controls, textvariable=self.top_n, values=[5, 10, 20, 30, 50], state="readonly", width=6).pack(side=LEFT)
        ttk.Button(controls, text="Pesquisar", command=self.start).pack(side=LEFT, padx=12)
        ttk.Button(controls, text="Parar", command=self.stop).pack(side=LEFT)
        ttk.Button(controls, text="Exportar CSV", command=self.export_csv).pack(side=RIGHT)

        ttk.Label(frame, textvariable=self.summary_text).pack(anchor="w", pady=(7, 2))
        pbar = ttk.Frame(frame)
        pbar.pack(fill=X)
        ttk.Progressbar(pbar, variable=self.progress_value, maximum=100).pack(side=LEFT, fill=X, expand=True)
        ttk.Label(pbar, textvariable=self.status_text, width=60).pack(side=RIGHT, padx=8)

        cols = ("badge", "score", "price", "route", "dates", "airline", "stops", "duration")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        headings = {"badge":"Destaque", "score":"Nota", "price":"Preço", "route":"Rota", "dates":"Datas", "airline":"Companhia", "stops":"Escalas", "duration":"Duração"}
        widths = {"badge":220, "score":65, "price":90, "route":100, "dates":190, "airline":240, "stops":100, "duration":100}
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w" if col in {"badge", "airline"} else "center")
        self.tree.pack(fill=BOTH, expand=True, pady=(8, 0))
        self.tree.bind("<Double-1>", self.open_selected)
        ttk.Label(frame, text="Duplo clique para confirmar o preço no Google Flights.").pack(anchor="w", pady=4)

    def update_date_mode(self) -> None:
        for child in self.date_frame.winfo_children():
            child.destroy()
        if self.date_mode.get() == "Meses flexíveis":
            ttk.Label(self.date_frame, text="Meses da ida (AAAA-MM, separados por vírgula)").grid(row=0, column=0, sticky="w", padx=4)
            ttk.Entry(self.date_frame, textvariable=self.dep_months, width=32).grid(row=0, column=1, padx=4)
            ttk.Label(self.date_frame, text="Meses da volta").grid(row=0, column=2, sticky="w", padx=4)
            ttk.Entry(self.date_frame, textvariable=self.ret_months, width=32).grid(row=0, column=3, padx=4)
        else:
            fields = [("Ida inicial", self.dep_start), ("Ida final", self.dep_end), ("Volta inicial", self.ret_start), ("Volta final", self.ret_end)]
            for idx, (label, var) in enumerate(fields):
                ttk.Label(self.date_frame, text=label).grid(row=0, column=idx * 2, sticky="w", padx=4)
                ttk.Entry(self.date_frame, textvariable=var, width=14).grid(row=0, column=idx * 2 + 1, padx=4)

    def pick_regions(self, origin: bool) -> None:
        selected = self.origin_regions if origin else self.destination_regions
        def apply(chosen: list[str]) -> None:
            if origin:
                self.origin_regions = chosen
                self.origin_regions_text.set(f"{len(chosen)} selecionado(s) — {len(airports_for_regions(chosen))} aeroportos")
            else:
                self.destination_regions = chosen
                self.destination_regions_text.set(f"{len(chosen)} selecionado(s) — {len(airports_for_regions(chosen))} aeroportos")
        RegionPicker(self.root, "Estados/regiões de origem" if origin else "Estados/regiões de destino", selected, apply)

    @staticmethod
    def _date(value: str) -> date:
        return date.fromisoformat(value.strip())

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Já existe uma pesquisa em andamento.")
            return
        try:
            per_query, delay = {"Rápido": (1, 0.15), "Equilibrado": (2, 0.35), "Profundo": (4, 0.6), "Máximo": (8, 0.8)}[self.depth.get()]
            params = {
                "origins": self.origins.get(), "destinations": self.destinations.get(),
                "origin_regions": list(self.origin_regions), "destination_regions": list(self.destination_regions),
                "date_mode": self.date_mode.get(), "dep_months": self.dep_months.get(), "ret_months": self.ret_months.get(),
                "dep_start": self._date(self.dep_start.get()), "dep_end": self._date(self.dep_end.get()),
                "ret_start": self._date(self.ret_start.get()), "ret_end": self._date(self.ret_end.get()),
                "min_nights": self.min_nights.get(), "max_nights": self.max_nights.get(), "adults": max(1, self.adults.get()),
                "max_stops": self.max_stops.get(), "max_price": self.max_price.get(), "top_n": self.top_n.get(),
                "seat": self.seat.get(), "currency": self.currency.get(), "per_query": per_query, "delay": delay,
            }
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Configuração inválida: {exc}")
            return
        self.stop_event.clear()
        self.results = []
        self.tree.delete(*self.tree.get_children())
        self.progress_value.set(0)
        self.worker = threading.Thread(target=SearchEngine(self.store, self.events, self.stop_event).search, args=(params,), daemon=True)
        self.worker.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.status_text.set("Solicitando interrupção…")

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "summary":
                    o, d, idates, rdates, pairs, total = payload
                    self.summary_text.set(f"{o} origens × {d} destinos | {idates} datas de ida | {rdates} datas de volta | {pairs:,} pares válidos | {total:,} consultas")
                elif kind == "progress":
                    done, total, text = payload
                    self.progress_value.set(int(done * 100 / max(total, 1)))
                    self.status_text.set(f"{done:,}/{total:,} — {text}")
                elif kind in {"complete", "stopped"}:
                    self.results = payload
                    self.show_results(payload)
                    self.progress_value.set(100 if kind == "complete" else self.progress_value.get())
                    self.status_text.set(("Concluído" if kind == "complete" else "Interrompido") + f": {len(payload)} resultados.")
                elif kind == "error":
                    messagebox.showerror(APP_NAME, str(payload))
                elif kind == "log":
                    self.status_text.set(str(payload)[:180])
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    def show_results(self, deals: list[Deal]) -> None:
        self.tree.delete(*self.tree.get_children())
        for idx, d in enumerate(deals):
            self.tree.insert("", END, iid=str(idx), values=(d.badge, f"{d.score:.0f}", d.price_text, f"{d.origin}–{d.destination}", f"{d.departure_date} → {d.return_date}", d.airline, d.stops, d.duration))

    def open_selected(self, _event: Any = None) -> None:
        selected = self.tree.selection()
        if selected:
            webbrowser.open(self.results[int(selected[0])].query_url)

    def export_csv(self) -> None:
        if not self.results:
            messagebox.showinfo(APP_NAME, "Ainda não há resultados.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="flight_deals_v03.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(self.results[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(d) for d in self.results)
        messagebox.showinfo(APP_NAME, "Arquivo exportado com sucesso.")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
