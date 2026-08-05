from pathlib import Path

path = Path("app.py")
text = path.read_text(encoding="utf-8")

text = text.replace('APP_VERSION = "0.1.0"', 'APP_VERSION = "0.2.0"')

text = text.replace(
    '    score: float = 0.0\n',
    '    score: float = 0.0\n    badge: str = ""\n',
)

old_rank = '''        ranked = sorted(unique.values(), key=lambda d: (-d.score, d.price_value))[: params["top_n"]]\n        self.store.save(ranked)\n        self.status.put(("complete", ranked))'''

new_rank = '''        candidates = list(unique.values())
        if not candidates:
            self.status.put(("complete", []))
            return

        prices = sorted(d.price_value for d in candidates if d.price_value > 0)
        median_price = prices[len(prices) // 2]
        cheapest_price = min(prices)

        def stop_count(value: str) -> int:
            lower = (value or "").lower().strip()
            if lower in {"", "0", "direto", "nonstop", "non-stop"} or "direto" in lower or "nonstop" in lower:
                return 0
            match = re.search(r"\\d+", lower)
            return int(match.group()) if match else 2

        def duration_minutes(value: str) -> int:
            lower = (value or "").lower()
            hours = re.search(r"(\\d+)\\s*h", lower)
            minutes = re.search(r"(\\d+)\\s*min", lower)
            if hours or minutes:
                return (int(hours.group(1)) * 60 if hours else 0) + (int(minutes.group(1)) if minutes else 0)
            numeric = re.search(r"\\d+", lower)
            return int(numeric.group()) if numeric else 99999

        durations = [duration_minutes(d.duration) for d in candidates]
        shortest_duration = min(durations) if durations else 0

        for deal in candidates:
            stops_n = stop_count(deal.stops)
            duration_n = duration_minutes(deal.duration)

            # Preço representa 70% da nota; qualidade e tempo, 30%.
            price_component = 60.0 * (cheapest_price / max(deal.price_value, 1.0))
            median_component = 10.0 * min(1.0, median_price / max(deal.price_value, 1.0))
            quality_component = 20.0 - (stops_n * 4.0)
            if stops_n == 0:
                quality_component += 3.0
            time_penalty = min(13.0, max(0.0, (duration_n - shortest_duration) / 60.0 * 1.5))
            history_bonus = 0.0
            avg_price, historical_min = self.store.route_stats(deal.origin, deal.destination)
            if avg_price and deal.price_value < avg_price:
                history_bonus += min(5.0, ((avg_price - deal.price_value) / avg_price) * 20.0)
            if historical_min and deal.price_value <= historical_min:
                history_bonus += 2.0

            deal.score = max(0.0, min(100.0, price_component + median_component + quality_component - time_penalty + history_bonus))
            deal.badge = ""

        cheapest = min(candidates, key=lambda d: d.price_value)
        shortest = min(candidates, key=lambda d: duration_minutes(d.duration))
        direct_options = [d for d in candidates if stop_count(d.stops) == 0]
        best_direct = min(direct_options, key=lambda d: d.price_value) if direct_options else None
        best_value = max(candidates, key=lambda d: (d.score, -d.price_value))

        labels: dict[int, list[str]] = {}
        def mark(deal: Deal | None, label: str) -> None:
            if deal is not None:
                labels.setdefault(id(deal), []).append(label)

        mark(cheapest, "MENOR PREÇO")
        mark(best_value, "MELHOR GERAL")
        mark(best_direct, "MELHOR DIRETO")
        mark(shortest, "MAIS RÁPIDO")
        for deal in candidates:
            deal.badge = " • ".join(labels.get(id(deal), []))

        ranked = sorted(candidates, key=lambda d: (-d.score, d.price_value))[: params["top_n"]]
        self.store.save(ranked)
        self.status.put(("complete", ranked))'''

if old_rank not in text:
    raise SystemExit("Bloco de ranking não encontrado em app.py")
text = text.replace(old_rank, new_rank)

text = text.replace(
    'cols = ("score", "price", "route", "dates", "airline", "stops", "duration")',
    'cols = ("badge", "score", "price", "route", "dates", "airline", "stops", "duration")',
)
text = text.replace(
    'headings = {"score":"Nota", "price":"Preço", "route":"Rota", "dates":"Datas", "airline":"Companhia", "stops":"Escalas", "duration":"Duração"}',
    'headings = {"badge":"Destaque", "score":"Nota", "price":"Preço", "route":"Rota", "dates":"Datas", "airline":"Companhia", "stops":"Escalas", "duration":"Duração"}',
)
text = text.replace(
    'widths = {"score":70, "price":110, "route":110, "dates":180, "airline":260, "stops":120, "duration":120}',
    'widths = {"badge":190, "score":65, "price":95, "route":100, "dates":175, "airline":220, "stops":100, "duration":100}',
)
text = text.replace(
    'values=(f"{d.score:.0f}", d.price_text, f"{d.origin}–{d.destination}", dates, d.airline, d.stops, d.duration)',
    'values=(d.badge, f"{d.score:.0f}", d.price_text, f"{d.origin}–{d.destination}", dates, d.airline, d.stops, d.duration)',
)

path.write_text(text, encoding="utf-8")
print("Upgrade v0.2 aplicado com sucesso")
