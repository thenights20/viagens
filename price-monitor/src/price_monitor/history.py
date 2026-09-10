from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from .models import Offer


def load_history(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "products": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "products": {}}
    if not isinstance(data, dict):
        return {"version": 1, "products": {}}
    data.setdefault("version", 1)
    data.setdefault("products", {})
    return data


def historical_prices(history: dict, key: str) -> list[float]:
    values = []
    for row in history.get("products", {}).get(key, []):
        try:
            price = float(row.get("price"))
        except (TypeError, ValueError):
            continue
        if price > 0:
            values.append(price)
    return values


def historical_median(history: dict, key: str, min_samples: int = 5) -> tuple[float | None, int]:
    prices = historical_prices(history, key)
    if len(prices) < min_samples:
        return None, len(prices)
    return float(median(prices)), len(prices)


def update_history(history: dict, offers: list[Offer], retention_days: int = 35) -> dict:
    products = history.setdefault("products", {})
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=retention_days)

    for key in list(products):
        kept = []
        for row in products[key]:
            try:
                ts = datetime.fromisoformat(str(row.get("ts")).replace("Z", "+00:00"))
            except Exception:
                continue
            if ts >= cutoff:
                kept.append(row)
        if kept:
            products[key] = kept[-150:]
        else:
            products.pop(key, None)

    seen = set()
    for offer in offers:
        if not offer.official or not offer.available or not offer.product_key:
            continue
        ident = (offer.product_key, offer.source, offer.url)
        if ident in seen:
            continue
        seen.add(ident)
        products.setdefault(offer.product_key, []).append(
            {
                "ts": offer.collected_at,
                "price": round(offer.price, 2),
                "source": offer.source,
                "store": offer.store_name,
                "url": offer.url,
            }
        )
        products[offer.product_key] = products[offer.product_key][-150:]

    history["updated_at"] = now.isoformat()
    return history


def save_history(path: Path, history: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
