from __future__ import annotations

from collections import defaultdict
from statistics import median

from .history import historical_median
from .models import Anomaly, Offer


def detect_anomalies(
    offers: list[Offer],
    history: dict,
    *,
    max_ratio: float = 0.55,
    min_savings: float = 1000.0,
    min_baseline: float = 2000.0,
    weak_max_ratio: float = 0.35,
    weak_min_savings: float = 2000.0,
    weak_min_baseline: float = 3000.0,
) -> list[Anomaly]:
    groups: dict[str, list[Offer]] = defaultdict(list)
    for offer in offers:
        if offer.official and offer.available and offer.price > 0 and offer.product_key:
            groups[offer.product_key].append(offer)

    anomalies: list[Anomaly] = []

    for offer in offers:
        if not offer.official or not offer.available or offer.price <= 0 or not offer.product_key:
            continue

        current_group = groups.get(offer.product_key, [])
        market_prices = [x.price for x in current_group if x.price > 0]
        market_baseline = float(median(market_prices)) if len(market_prices) >= 3 else None
        hist_baseline, hist_samples = historical_median(history, offer.product_key, min_samples=5)

        baseline = None
        kind = ""
        samples = 0
        confidence = "baixa"
        candidates = []
        if market_baseline is not None:
            candidates.append(("mercado_atual", market_baseline, len(market_prices), 2))
        if hist_baseline is not None:
            candidates.append(("historico", hist_baseline, hist_samples, 2))

        if candidates:
            kind, baseline, samples, _ = max(candidates, key=lambda row: row[1])
            confidence = "alta" if len(candidates) == 2 else "media"
        elif offer.original_price and offer.original_price > offer.price:
            baseline = float(offer.original_price)
            kind = "preco_de"
            samples = 1
            confidence = "baixa"

        if not baseline or baseline <= offer.price:
            continue

        ratio = offer.price / baseline
        savings = baseline - offer.price
        drop_pct = (1.0 - ratio) * 100.0

        strong = (
            baseline >= min_baseline
            and savings >= min_savings
            and ratio <= max_ratio
            and kind != "preco_de"
        )
        weak_but_extreme = (
            kind == "preco_de"
            and baseline >= weak_min_baseline
            and savings >= weak_min_savings
            and ratio <= weak_max_ratio
        )

        if strong or weak_but_extreme:
            anomalies.append(
                Anomaly(
                    offer=offer,
                    baseline_price=baseline,
                    baseline_kind=kind,
                    baseline_samples=samples,
                    drop_pct=drop_pct,
                    savings=savings,
                    confidence=confidence,
                )
            )

    anomalies.sort(key=lambda a: (-a.drop_pct, -a.savings, a.offer.price))
    return anomalies
