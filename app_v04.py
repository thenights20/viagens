from __future__ import annotations

import csv
import queue
import threading
import webbrowser
from dataclasses import asdict
from datetime import date, timedelta
from tkinter import BOTH, END, LEFT, RIGHT, X, IntVar, Listbox, MULTIPLE, StringVar, Tk, Toplevel, filedialog, messagebox
from tkinter import ttk
from typing import Any

from airport_catalog import AIRPORTS_BY_REGION, airports_for_regions
from search_core import APP_NAME, APP_VERSION, Deal, SearchEngine, Store, build_plan


class RegionPicker:
    def __init__(self, parent: Tk, title: str, selected: list[str], callback: Any) -> None:
        self.top = Toplevel(parent)
        self.top.title(title)
        self.top.geometry("570x620")
        self.top.transient(parent)
        self.callback = callback
        ttk.Label(self.top, text="Selecione um ou vários estados/regiões:").pack(anchor="w", padx=12, pady=(12, 4))
        self.listbox = Listbox(self.top, selectmode=MULTIPLE, exportselection=False)
        self.listbox.pack(fill=BOTH, expand=True, padx=12, pady=6)
        self.keys = list(AIRPORTS_BY_REGION)
        for index, item in enumerate(self.keys):
            self.listbox.insert(END, item)
            if item in selected:
                self.listbox.selection_set(index)
        bar = ttk.Frame(self.top)
        bar.pack(fill=X, padx=12, pady=10)
        ttk.Button(bar, text="Brasil inteiro", command=self.select_brazil).pack(side=LEFT)
        ttk.Button(bar, text="Limpar", command=lambda: self.listbox.selection_clear(0, END)).pack(side=LEFT, padx=6)
        ttk.Button(bar, text="Aplicar", command=self.apply).pack(side=RIGHT)

    def select_brazil(self) -> None:
        self.listbox.selection_clear(0, END)
        for index, key in enumerate(self.keys):
            if key.startswith("BR-"):
                self.listbox.selection_set(index)

    def apply(self) -> None:
        self.callback([self.listbox.get(i) for i in self.listbox.curselection()])
        self.top.destroy()


class App:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1420x850")
        self.root.minsize(1050, 680)
        self.store = Store()
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.pause_event = threading.Event()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.current_job_id: int | None = None
        self.results: list[Deal] = []
        self.origin_regions: list[str] = []
        self.destination_regions: list[str] = []
        self._vars()
        self._style()
        self._ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(150, self._poll)
        self.root.after(500, self._show_resumable)

    def _vars(self) -> None:
        today = date.today()
        self.origins = StringVar(value="CGR, DOU, GRU, VCP")
        self.destinations = StringVar(value="")
        self.origin_regions_text = StringVar(value="Nenhum estado selecionado")
        self.destination_regions_text = StringVar(value="Nenhum estado selecionado")
        self.date_mode = StringVar(value="Próximos 12 meses")
        self.dep_start = StringVar(value=(today + timedelta(days=1)).isoformat())
        self.dep_end = StringVar(value=(today + timedelta(days=365)).isoformat())
        self.ret_start = StringVar(value=(today + timedelta(days=8)).isoformat())
        self.ret_end = StringVar(value=(today + timedelta(days=379)).isoformat())
        self.dep_months = StringVar(value=f"{today.year + 1}-01")
        self.ret_months = StringVar(value=f"{today.year + 1}-02")
        self.min_nights = IntVar(value=3)
        self.max_nights = IntVar(value=14)
        self.adults = IntVar(value=1)
        self.max_stops = IntVar(value=2)
        self.max_price = IntVar(value=0)
        self.result_limit = IntVar(value=50)
        self.seat = StringVar(value="economy")
        self.currency = StringVar(value="BRL")
        self.depth = StringVar(value="Profundo")
        self.status_text = StringVar(value="Pronto para pesquisar.")
        self.summary_text = StringVar(value="Selecione os destinos ou use “Brasil inteiro”.")
        self.progress_text = StringVar(value="0%")
        self.progress_value = IntVar(value=0)

    def _style(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=BOTH, expand=True)
        ttk.Label(frame, text="Pesquisa profunda de passagens", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="O programa pesquisa no seu computador e conserva apenas o menor preço encontrado para cada rota.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        form = ttk.LabelFrame(frame, text="Definição da pesquisa", padding=10)
        form.pack(fill=X)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Origens (IATA)").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(form, textvariable=self.origins, width=42).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(form, text="Selecionar estados", command=lambda: self.pick_regions(True)).grid(row=0, column=2, padx=4)
        ttk.Button(form, text="Brasil inteiro", command=lambda: self.select_brazil(True)).grid(row=0, column=3, padx=4)
        ttk.Label(form, textvariable=self.origin_regions_text, width=34).grid(row=0, column=4, sticky="w", padx=4)

        ttk.Label(form, text="Destinos (IATA)").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(form, textvariable=self.destinations, width=42).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Button(form, text="Selecionar estados", command=lambda: self.pick_regions(False)).grid(row=1, column=2, padx=4)
        ttk.Button(form, text="Brasil inteiro", command=lambda: self.select_brazil(False)).grid(row=1, column=3, padx=4)
        ttk.Label(form, textvariable=self.destination_regions_text, width=34).grid(row=1, column=4, sticky="w", padx=4)

        ttk.Label(form, text="Período").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        mode = ttk.Combobox(
            form,
            textvariable=self.date_mode,
            values=["Próximos 12 meses", "Datas/Intervalo", "Meses flexíveis"],
            state="readonly",
            width=22,
        )
        mode.grid(row=2, column=1, sticky="w", padx=4)
        mode.bind("<<ComboboxSelected>>", lambda _event: self.update_date_mode())
        ttk.Label(
            form,
            text="Profundo/Máximo verificam todos os dias; os demais usam amostragem para terminar antes.",
        ).grid(row=2, column=2, columnspan=3, sticky="w", padx=4)

        self.date_frame = ttk.Frame(form)
        self.date_frame.grid(row=3, column=0, columnspan=5, sticky="ew", pady=4)
        self.update_date_mode()

        options = ttk.Frame(form)
        options.grid(row=4, column=0, columnspan=5, sticky="ew", pady=6)
        for label, variable, minimum, maximum in [
            ("Noites mín.", self.min_nights, 1, 365),
            ("Noites máx.", self.max_nights, 1, 365),
            ("Adultos", self.adults, 1, 9),
            ("Escalas máx.", self.max_stops, 0, 4),
            ("Preço máximo (0=livre)", self.max_price, 0, 99999),
        ]:
            ttk.Label(options, text=label).pack(side=LEFT, padx=(3, 2))
            ttk.Spinbox(options, from_=minimum, to=maximum, textvariable=variable, width=6).pack(side=LEFT, padx=(0, 8))
        ttk.Label(options, text="Classe").pack(side=LEFT, padx=(5, 2))
        ttk.Combobox(
            options,
            textvariable=self.seat,
            values=["economy", "premium-economy", "business", "first"],
            state="readonly",
            width=16,
        ).pack(side=LEFT)

        controls = ttk.Frame(form)
        controls.grid(row=5, column=0, columnspan=5, sticky="ew", pady=(5, 0))
        ttk.Label(controls, text="Profundidade").pack(side=LEFT)
        ttk.Combobox(
            controls,
            textvariable=self.depth,
            values=["Rápido", "Equilibrado", "Profundo", "Máximo"],
            state="readonly",
            width=13,
        ).pack(side=LEFT, padx=4)
        ttk.Label(controls, text="Rotas exibidas").pack(side=LEFT, padx=(10, 2))
        ttk.Combobox(controls, textvariable=self.result_limit, values=[10, 20, 50], state="readonly", width=5).pack(side=LEFT)
        ttk.Button(controls, text="Iniciar pesquisa", style="Accent.TButton", command=self.start).pack(side=LEFT, padx=(14, 4))
        ttk.Button(controls, text="Pausar", command=self.pause).pack(side=LEFT, padx=4)
        ttk.Button(controls, text="Continuar última", command=self.continue_last).pack(side=LEFT, padx=4)
        ttk.Button(controls, text="Cancelar", command=self.cancel).pack(side=LEFT, padx=4)
        ttk.Button(controls, text="Exportar CSV", command=self.export_csv).pack(side=RIGHT)

        ttk.Label(frame, textvariable=self.summary_text).pack(anchor="w", pady=(8, 2))
        progress = ttk.Frame(frame)
        progress.pack(fill=X)
        ttk.Progressbar(progress, variable=self.progress_value, maximum=100).pack(side=LEFT, fill=X, expand=True)
        ttk.Label(progress, textvariable=self.progress_text, width=8).pack(side=LEFT, padx=6)
        ttk.Label(progress, textvariable=self.status_text, width=72).pack(side=RIGHT)

        columns = ("badge", "price", "route", "dates", "airline", "stops", "duration")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        headings = {
            "badge": "Resultado", "price": "Menor preço", "route": "Rota", "dates": "Datas",
            "airline": "Companhia", "stops": "Escalas", "duration": "Duração",
        }
        widths = {"badge": 150, "price": 120, "route": 110, "dates": 220, "airline": 260, "stops": 100, "duration": 100}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w" if column in {"badge", "airline"} else "center")
        self.tree.pack(fill=BOTH, expand=True, pady=(8, 0))
        self.tree.bind("<Double-1>", self.open_selected)
        ttk.Label(
            frame,
            text="Cada rota aparece uma única vez. Dê duplo clique para conferir a tarifa no Google Flights.",
        ).pack(anchor="w", pady=4)

    def update_date_mode(self) -> None:
        for child in self.date_frame.winfo_children():
            child.destroy()
        if self.date_mode.get() == "Próximos 12 meses":
            ttk.Label(self.date_frame, text="Início (AAAA-MM-DD)").grid(row=0, column=0, sticky="w", padx=4)
            ttk.Entry(self.date_frame, textvariable=self.dep_start, width=14).grid(row=0, column=1, padx=4)
            ttk.Label(self.date_frame, text="A busca cobre até 365 dias a partir dessa data.").grid(row=0, column=2, sticky="w", padx=8)
        elif self.date_mode.get() == "Meses flexíveis":
            ttk.Label(self.date_frame, text="Meses da ida (AAAA-MM)").grid(row=0, column=0, sticky="w", padx=4)
            ttk.Entry(self.date_frame, textvariable=self.dep_months, width=35).grid(row=0, column=1, padx=4)
            ttk.Label(self.date_frame, text="Meses da volta").grid(row=0, column=2, sticky="w", padx=4)
            ttk.Entry(self.date_frame, textvariable=self.ret_months, width=35).grid(row=0, column=3, padx=4)
        else:
            fields = [
                ("Ida inicial", self.dep_start), ("Ida final", self.dep_end),
                ("Volta inicial", self.ret_start), ("Volta final", self.ret_end),
            ]
            for index, (label, variable) in enumerate(fields):
                ttk.Label(self.date_frame, text=label).grid(row=0, column=index * 2, sticky="w", padx=4)
                ttk.Entry(self.date_frame, textvariable=variable, width=14).grid(row=0, column=index * 2 + 1, padx=4)

    def select_brazil(self, origin: bool) -> None:
        selected = [key for key in AIRPORTS_BY_REGION if key.startswith("BR-")]
        if origin:
            self.origin_regions = selected
            self.origin_regions_text.set(f"Brasil inteiro — {len(airports_for_regions(selected))} aeroportos")
        else:
            self.destination_regions = selected
            self.destination_regions_text.set(f"Brasil inteiro — {len(airports_for_regions(selected))} aeroportos")

    def pick_regions(self, origin: bool) -> None:
        selected = self.origin_regions if origin else self.destination_regions

        def apply(chosen: list[str]) -> None:
            airports = len(airports_for_regions(chosen))
            text = f"{len(chosen)} região(ões) — {airports} aeroportos" if chosen else "Nenhum estado selecionado"
            if origin:
                self.origin_regions = chosen
                self.origin_regions_text.set(text)
            else:
                self.destination_regions = chosen
                self.destination_regions_text.set(text)

        RegionPicker(self.root, "Estados/regiões de origem" if origin else "Estados/regiões de destino", selected, apply)

    @staticmethod
    def _date(value: str) -> date:
        return date.fromisoformat(value.strip())

    def _params(self) -> dict[str, Any]:
        start = self._date(self.dep_start.get())
        return {
            "origins": self.origins.get(),
            "destinations": self.destinations.get(),
            "origin_regions": list(self.origin_regions),
            "destination_regions": list(self.destination_regions),
            "date_mode": self.date_mode.get(),
            "dep_months": self.dep_months.get(),
            "ret_months": self.ret_months.get(),
            "dep_start": start,
            "dep_end": self._date(self.dep_end.get()) if self.date_mode.get() != "Próximos 12 meses" else start + timedelta(days=364),
            "ret_start": self._date(self.ret_start.get()),
            "ret_end": self._date(self.ret_end.get()),
            "min_nights": self.min_nights.get(),
            "max_nights": self.max_nights.get(),
            "adults": max(1, self.adults.get()),
            "max_stops": self.max_stops.get(),
            "max_price": self.max_price.get(),
            "seat": self.seat.get(),
            "currency": self.currency.get(),
            "depth": self.depth.get(),
        }

    def start(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Já existe uma pesquisa em andamento.")
            return
        try:
            params = self._params()
            plan = build_plan(params)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Configuração inválida: {exc}")
            return
        if plan.total > 100_000:
            answer = messagebox.askyesno(
                APP_NAME,
                f"Esta pesquisa possui {plan.total:,} consultas e poderá levar vários dias.\n\n"
                "O progresso será salvo e você poderá pausar ou continuar depois. Deseja iniciar?",
            )
            if not answer:
                return
        self.results = []
        self.tree.delete(*self.tree.get_children())
        self._start_worker(params, None)

    def _start_worker(self, params: dict[str, Any], job_id: int | None) -> None:
        self.pause_event.clear()
        self.cancel_event.clear()
        self.progress_value.set(0)
        self.status_text.set("Preparando a pesquisa…")
        engine = SearchEngine(self.store, self.events, self.pause_event, self.cancel_event)
        self.worker = threading.Thread(target=engine.run, args=(params, job_id), daemon=True)
        self.worker.start()

    def pause(self) -> None:
        if not self.worker or not self.worker.is_alive():
            self.status_text.set("Não existe pesquisa ativa para pausar.")
            return
        self.pause_event.set()
        self.status_text.set("Salvando o ponto de retomada…")

    def cancel(self) -> None:
        if not self.worker or not self.worker.is_alive():
            self.status_text.set("Não existe pesquisa ativa para cancelar.")
            return
        if messagebox.askyesno(APP_NAME, "Cancelar esta pesquisa? Os menores preços já encontrados serão preservados."):
            self.cancel_event.set()
            self.status_text.set("Cancelando com segurança…")

    def continue_last(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Já existe uma pesquisa em andamento.")
            return
        job = self.store.latest_resumable()
        if not job:
            messagebox.showinfo(APP_NAME, "Não há pesquisa pausada para continuar.")
            return
        self.current_job_id = int(job["id"])
        self.results = self.store.best(self.current_job_id, self.result_limit.get())
        self.show_results(self.results)
        self._start_worker(job["params"], self.current_job_id)

    def _show_resumable(self) -> None:
        job = self.store.latest_resumable()
        if job:
            percent = int(int(job["cursor"]) * 100 / max(int(job["total"]), 1))
            self.summary_text.set(f"Pesquisa #{job['id']} disponível para continuar: {percent}% concluída.")

    @staticmethod
    def _eta(seconds: int) -> str:
        if seconds <= 0:
            return "calculando tempo…"
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes = remainder // 60
        if days:
            return f"aprox. {days}d {hours}h restantes"
        if hours:
            return f"aprox. {hours}h {minutes}min restantes"
        return f"aprox. {max(1, minutes)}min restantes"

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "started":
                    job_id, cursor, total, routes, pairs = payload
                    self.current_job_id = job_id
                    self.summary_text.set(f"{routes:,} rotas × {pairs:,} combinações de datas = {total:,} consultas")
                    self.progress_value.set(int(cursor * 100 / max(total, 1)))
                elif kind == "progress":
                    job_id, done, total, errors, remaining, text = payload
                    self.current_job_id = job_id
                    percent = int(done * 100 / max(total, 1))
                    self.progress_value.set(percent)
                    self.progress_text.set(f"{percent}%")
                    self.status_text.set(f"{done:,}/{total:,} — {text} — {self._eta(remaining)} — {errors} falhas")
                elif kind == "new_best":
                    job_id, _deal = payload
                    self.results = self.store.best(job_id, self.result_limit.get())
                    self.show_results(self.results)
                elif kind in {"complete", "paused", "cancelled"}:
                    job_id, results = payload
                    self.current_job_id = job_id
                    self.results = results[: self.result_limit.get()]
                    self.show_results(self.results)
                    labels = {"complete": "Pesquisa concluída", "paused": "Pesquisa pausada", "cancelled": "Pesquisa cancelada"}
                    self.status_text.set(f"{labels[kind]}. {len(self.results)} menores preços exibidos.")
                    if kind == "complete":
                        self.progress_value.set(100)
                        self.progress_text.set("100%")
                elif kind == "error":
                    messagebox.showerror(APP_NAME, str(payload))
                    self.status_text.set("A pesquisa não pôde ser iniciada.")
                elif kind == "log":
                    self.status_text.set(str(payload)[:200])
        except queue.Empty:
            pass
        self.root.after(150, self._poll)

    def show_results(self, deals: list[Deal]) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, deal in enumerate(deals):
            self.tree.insert(
                "", END, iid=str(index),
                values=(
                    deal.badge, deal.price_text, f"{deal.origin}–{deal.destination}",
                    f"{deal.departure_date} → {deal.return_date}", deal.airline, deal.stops, deal.duration,
                ),
            )

    def open_selected(self, _event: Any = None) -> None:
        selected = self.tree.selection()
        if selected:
            webbrowser.open(self.results[int(selected[0])].query_url)

    def export_csv(self) -> None:
        if not self.results:
            messagebox.showinfo(APP_NAME, "Ainda não há resultados para exportar.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="menores_precos_v04.csv"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(asdict(self.results[0]).keys()))
            writer.writeheader()
            writer.writerows(asdict(item) for item in self.results)
        messagebox.showinfo(APP_NAME, "Arquivo exportado com sucesso.")

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(
                APP_NAME,
                "Existe uma pesquisa ativa. Fechar o programa interromperá a execução, mas o progresso já salvo poderá ser continuado depois. Fechar?",
            ):
                return
            self.pause_event.set()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    App().run()

