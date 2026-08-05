from __future__ import annotations

import csv
import json
import queue
import re
import sqlite3
import threading
import time
import webbrowser
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, X, Y, BooleanVar, IntVar, StringVar, Tk, Toplevel, filedialog, messagebox
from tkinter import ttk
from typing import Any, Iterable

from fast_flights import FlightQuery, Passengers, create_query, get_flights

APP_NAME = "Flight Deals Local"
APP_VERSION = "0.1.0"
DATA_DIR = Path.home() / "FlightDealsLocal"
DB_PATH = DATA_DIR / "flight_deals.db"
CONFIG_PATH = DATA_DIR / "config.json"


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
    stops: str
    departure: str
    arrival: str
    query_url: str
    score: float = 0.0


class Store:
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                searched_at TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                departure_date TEXT NOT NULL,
                return_date TEXT NOT NULL,
                airline TEXT,
                price_text TEXT,
                price_value REAL,
                duration TEXT,
                stops TEXT,
                departure TEXT,
                arrival TEXT,
                query_url TEXT,
                score REAL
            )
            """
        )
        self.conn.commit()

    def save(self, deals: Iterable[Deal]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        rows = [
            (
                now,
                d.origin,
                d.destination,
                d.departure_date,
                d.return_date,
                d.airline,
                d.price_text,
                d.price_value,
                d.duration,
                d.stops,
                d.departure,
                d.arrival,
                d.query_url,
                d.score,
            )
            for d in deals
        ]
        self.conn.executemany(
            """
            INSERT INTO deals (
                searched_at, origin, destination, departure_date, return_date,
                airline, price_text, price_value, duration, stops, departure,
                arrival, query_url, score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    def route_stats(self, origin: str, destination: str) -> tuple[float | None, float | None]:
        row = self.conn.execute(
            "SELECT AVG(price_value), MIN(price_value) FROM deals WHERE origin=? AND destination=? AND price_value>0",
            (origin, destination),
        ).fetchone()
        return (row[0], row[1]) if row else (None, None)


class SearchEngine:
    def __init__(self, store: Store, status: queue.Queue[tuple[str, Any]], stop_event: threading.Event) -> None:
        self.store = store
        self.status = status
        self.stop_event = stop_event

    @staticmethod
    def parse_airports(raw: str) -> list[str]:
        items = re.split(r"[,;\s]+", raw.upper().strip())
        airports = []
        for item in items:
            if re.fullmatch(r"[A-Z]{3}", item) and item not in airports:
                airports.append(item)
        return airports

    @staticmethod
    def parse_price(text: str) -> float:
        cleaned = re.sub(r"[^0-9,\.]", "", text or "")
        if not cleaned:
            return 0.0
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    @staticmethod
    def dates(start: date, end: date) -> list[date]:
        return [start + timedelta(days=i) for i in range((end - start).days + 1)]

    @staticmethod
    def google_url(origin: str, destination: str, dep: str, ret: str) -> str:
        q = f"Flights from {origin} to {destination} on {dep} returning {ret}"
        return "https://www.google.com/travel/flights?q=" + q.replace(" ", "+")

    def build_pairs(self, dep_start: date, dep_end: date, ret_start: date, ret_end: date, min_nights: int, max_nights: int) -> list[tuple[date, date]]:
        pairs: list[tuple[date, date]] = []
        for dep in self.dates(dep_start, dep_end):
            for ret in self.dates(ret_start, ret_end):
                nights = (ret - dep).days
                if ret > dep and (min_nights == 0 or nights >= min_nights) and (max_nights == 0 or nights <= max_nights):
                    pairs.append((dep, ret))
        return pairs

    def search(self, params: dict[str, Any]) -> None:
        origins = self.parse_airports(params["origins"])
        destinations = self.parse_airports(params["destinations"])
        pairs = self.build_pairs(
            params["dep_start"], params["dep_end"], params["ret_start"], params["ret_end"], params["min_nights"], params["max_nights"]
        )
        total = len(origins) * len(destinations) * len(pairs)
        if not origins or not destinations or not pairs:
            self.status.put(("error", "Informe aeroportos e um período válido."))
            return
        self.status.put(("total", total))
        found: list[Deal] = []
        done = 0
        for origin in origins:
            for destination in destinations:
                if origin == destination:
                    continue
                avg_price, min_price = self.store.route_stats(origin, destination)
                for dep, ret in pairs:
                    if self.stop_event.is_set():
                        self.status.put(("stopped", found))
                        return
                    done += 1
                    self.status.put(("progress", (done, total, f"{origin} → {destination} | {dep:%d/%m}–{ret:%d/%m}")))
                    try:
                        query = create_query(
                            flights=[
                                FlightQuery(date=dep.isoformat(), from_airport=origin, to_airport=destination, max_stops=params["max_stops"]),
                                FlightQuery(date=ret.isoformat(), from_airport=destination, to_airport=origin, max_stops=params["max_stops"]),
                            ],
                            seat=params["seat"],
                            trip="round-trip",
                            passengers=Passengers(adults=params["adults"]),
                            language="pt-BR",
                            currency=params["currency"],
                            max_price=params["max_price"] or None,
                        )
                        response = get_flights(query)
                        flights = getattr(response, "flights", []) or []
                        for flight in flights[: params["per_query"]]:
                            price_text = str(getattr(flight, "price", ""))
                            price_value = self.parse_price(price_text)
                            if not price_value:
                                continue
                            airline = str(getattr(flight, "name", getattr(flight, "airline", "Não informado")))
                            duration = str(getattr(flight, "duration", ""))
                            stops = str(getattr(flight, "stops", ""))
                            departure = str(getattr(flight, "departure", ""))
                            arrival = str(getattr(flight, "arrival", ""))
                            score = 100.0
                            if avg_price and avg_price > 0:
                                score += max(-30.0, min(60.0, ((avg_price - price_value) / avg_price) * 100))
                            if min_price and price_value <= min_price:
                                score += 20
                            if "nonstop" in stops.lower() or "direto" in stops.lower() or stops.strip() in {"0", ""}:
                                score += 8
                            found.append(
                                Deal(
                                    origin, destination, dep.isoformat(), ret.isoformat(), airline, price_text, price_value,
                                    duration, stops, departure, arrival,
                                    self.google_url(origin, destination, dep.isoformat(), ret.isoformat()), score,
                                )
                            )
                    except Exception as exc:
                        self.status.put(("log", f"Falha em {origin}-{destination} {dep}/{ret}: {exc}"))
                    time.sleep(params["delay"])
        unique: dict[tuple[Any, ...], Deal] = {}
        for deal in found:
            key = (deal.origin, deal.destination, deal.departure_date, deal.return_date, deal.airline, round(deal.price_value, 2))
            if key not in unique or deal.score > unique[key].score:
                unique[key] = deal
        ranked = sorted(unique.values(), key=lambda d: (-d.score, d.price_value))[: params["top_n"]]
        self.store.save(ranked)
        self.status.put(("complete", ranked))


class App:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1280x760")
        self.store = Store()
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.stop_event = threading.Event()
        self.results: list[Deal] = []
        self.worker: threading.Thread | None = None
        self._vars()
        self._ui()
        self.root.after(150, self._poll)

    def _vars(self) -> None:
        today = date.today()
        self.origins = StringVar(value="CGR, GRU, VCP")
        self.destinations = StringVar(value="MIA, FLL, MCO")
        self.dep_start = StringVar(value=(today + timedelta(days=60)).isoformat())
        self.dep_end = StringVar(value=(today + timedelta(days=67)).isoformat())
        self.ret_start = StringVar(value=(today + timedelta(days=67)).isoformat())
        self.ret_end = StringVar(value=(today + timedelta(days=80)).isoformat())
        self.min_nights = IntVar(value=0)
        self.max_nights = IntVar(value=0)
        self.adults = IntVar(value=1)
        self.max_stops = IntVar(value=2)
        self.max_price = IntVar(value=0)
        self.top_n = IntVar(value=20)
        self.seat = StringVar(value="economy")
        self.currency = StringVar(value="BRL")
        self.depth = StringVar(value="Equilibrado")
        self.status_text = StringVar(value="Pronto.")
        self.progress_value = IntVar(value=0)

    def _ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=BOTH, expand=True)
        form = ttk.LabelFrame(frame, text="Pesquisa ampla", padding=10)
        form.pack(fill=X)
        fields = [
            ("Origens (IATA)", self.origins, 0, 0, 45), ("Destinos (IATA)", self.destinations, 0, 2, 45),
            ("Ida inicial", self.dep_start, 1, 0, 16), ("Ida final", self.dep_end, 1, 2, 16),
            ("Volta inicial", self.ret_start, 2, 0, 16), ("Volta final", self.ret_end, 2, 2, 16),
        ]
        for label, var, row, col, width in fields:
            ttk.Label(form, text=label).grid(row=row, column=col, sticky="w", padx=5, pady=4)
            ttk.Entry(form, textvariable=var, width=width).grid(row=row, column=col+1, sticky="ew", padx=5, pady=4)
        options = ttk.Frame(form)
        options.grid(row=3, column=0, columnspan=4, sticky="ew", pady=8)
        for text, var, values in [
            ("Noites mín.", self.min_nights, None), ("Noites máx. (0=livre)", self.max_nights, None),
            ("Adultos", self.adults, None), ("Escalas máx.", self.max_stops, None), ("Preço máx. (0=livre)", self.max_price, None),
        ]:
            ttk.Label(options, text=text).pack(side=LEFT, padx=(4, 2))
            ttk.Spinbox(options, from_=0, to=99999, textvariable=var, width=6).pack(side=LEFT, padx=(0, 8))
        ttk.Label(options, text="Classe").pack(side=LEFT, padx=(4, 2))
        ttk.Combobox(options, textvariable=self.seat, values=["economy", "premium-economy", "business", "first"], width=16, state="readonly").pack(side=LEFT)
        ttk.Label(options, text="Moeda").pack(side=LEFT, padx=(8, 2))
        ttk.Combobox(options, textvariable=self.currency, values=["BRL", "USD", "EUR"], width=6, state="readonly").pack(side=LEFT)
        controls = ttk.Frame(form)
        controls.grid(row=4, column=0, columnspan=4, sticky="ew", pady=4)
        ttk.Label(controls, text="Profundidade").pack(side=LEFT, padx=4)
        ttk.Combobox(controls, textvariable=self.depth, values=["Rápido", "Equilibrado", "Profundo", "Máximo"], width=12, state="readonly").pack(side=LEFT)
        ttk.Label(controls, text="Resultados finais").pack(side=LEFT, padx=(14, 4))
        ttk.Combobox(controls, textvariable=self.top_n, values=[5, 10, 20, 30, 50], width=6, state="readonly").pack(side=LEFT)
        ttk.Button(controls, text="Pesquisar", command=self.start).pack(side=LEFT, padx=12)
        ttk.Button(controls, text="Parar", command=self.stop).pack(side=LEFT)
        ttk.Button(controls, text="Exportar CSV", command=self.export_csv).pack(side=RIGHT)
        progress = ttk.Frame(frame)
        progress.pack(fill=X, pady=8)
        ttk.Progressbar(progress, variable=self.progress_value, maximum=100).pack(side=LEFT, fill=X, expand=True)
        ttk.Label(progress, textvariable=self.status_text, width=58).pack(side=RIGHT, padx=8)
        cols = ("score", "price", "route", "dates", "airline", "stops", "duration")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        headings = {"score":"Nota", "price":"Preço", "route":"Rota", "dates":"Datas", "airline":"Companhia", "stops":"Escalas", "duration":"Duração"}
        widths = {"score":70, "price":110, "route":110, "dates":180, "airline":260, "stops":120, "duration":120}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="center" if c != "airline" else "w")
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<Double-1>", self.open_selected)
        ttk.Label(frame, text="Duplo clique em um resultado para confirmar no Google Flights.").pack(anchor="w", pady=4)

    def _date(self, value: str) -> date:
        return date.fromisoformat(value.strip())

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Já existe uma pesquisa em andamento.")
            return
        try:
            depth_cfg = {
                "Rápido": (1, 0.2), "Equilibrado": (2, 0.5), "Profundo": (4, 0.8), "Máximo": (8, 1.0)
            }
            per_query, delay = depth_cfg[self.depth.get()]
            params = {
                "origins": self.origins.get(), "destinations": self.destinations.get(),
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
        self.results.clear()
        self.tree.delete(*self.tree.get_children())
        self.worker = threading.Thread(target=SearchEngine(self.store, self.events, self.stop_event).search, args=(params,), daemon=True)
        self.worker.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.status_text.set("Solicitando interrupção…")

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "total":
                    self.status_text.set(f"{payload:,} combinações válidas serão avaliadas.")
                elif kind == "progress":
                    done, total, text = payload
                    self.progress_value.set(int(done * 100 / max(total, 1)))
                    self.status_text.set(f"{done:,}/{total:,} — {text}")
                elif kind == "complete":
                    self.results = payload
                    self._show(payload)
                    self.status_text.set(f"Concluído: {len(payload)} melhores resultados.")
                    self.progress_value.set(100)
                elif kind == "stopped":
                    self.results = payload
                    self.status_text.set("Pesquisa interrompida.")
                elif kind == "error":
                    messagebox.showerror(APP_NAME, str(payload))
                elif kind == "log":
                    self.status_text.set(str(payload)[:160])
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    def _show(self, deals: list[Deal]) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, d in enumerate(deals):
            dates = f"{d.departure_date} → {d.return_date}"
            self.tree.insert("", END, iid=str(i), values=(f"{d.score:.0f}", d.price_text, f"{d.origin}–{d.destination}", dates, d.airline, d.stops, d.duration))

    def open_selected(self, _event: Any = None) -> None:
        selected = self.tree.selection()
        if selected:
            webbrowser.open(self.results[int(selected[0])].query_url)

    def export_csv(self) -> None:
        if not self.results:
            messagebox.showinfo(APP_NAME, "Ainda não há resultados.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="flight_deals.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(asdict(self.results[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(d) for d in self.results)
        messagebox.showinfo(APP_NAME, "Arquivo exportado com sucesso.")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
