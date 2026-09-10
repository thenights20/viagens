from __future__ import annotations

import time

import requests

from ..models import Offer
from ..normalize import product_key
from .base import Source


class MercadoLivreSource(Source):
    name = "Mercado Livre"

    def __init__(self, queries: list[str], limit_per_query: int = 50, timeout: int = 20):
        super().__init__()
        self.queries = queries
        self.limit_per_query = min(max(limit_per_query, 1), 50)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "PriceMonitor/0.1 (+personal price anomaly monitor)",
            }
        )

    @staticmethod
    def _official_store(row: dict) -> tuple[bool, str]:
        official_id = row.get("official_store_id")
        official_name = row.get("official_store_name")
        seller = row.get("seller") or {}
        official_id = official_id or seller.get("official_store_id")
        official_name = official_name or seller.get("official_store_name")
        return bool(official_id or official_name), str(
            official_name or seller.get("nickname") or "Loja Oficial"
        )

    def collect(self) -> list[Offer]:
        offers: list[Offer] = []
        seen: set[str] = set()
        errors: list[str] = []

        for query in self.queries:
            try:
                response = self.session.get(
                    "https://api.mercadolibre.com/sites/MLB/search",
                    params={"q": query, "limit": self.limit_per_query},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                errors.append(f"{query}: {type(exc).__name__}")
                continue

            for row in payload.get("results", []):
                official, store_name = self._official_store(row)
                if not official:
                    continue
                url = row.get("permalink")
                title = row.get("title")
                price = row.get("price")
                if not url or not title or not isinstance(price, (int, float)):
                    continue
                if url in seen:
                    continue
                seen.add(url)

                offer = Offer(
                    source=self.name,
                    title=str(title),
                    price=float(price),
                    original_price=float(row["original_price"])
                    if isinstance(row.get("original_price"), (int, float))
                    else None,
                    url=str(url),
                    store_name=store_name,
                    official=True,
                    available=bool(row.get("available_quantity", 1)),
                    product_id=str(row.get("id") or ""),
                    metadata={
                        "official_store_id": row.get("official_store_id"),
                        "query": query,
                    },
                )
                offer.product_key = product_key(offer.title)
                offers.append(offer)

            time.sleep(0.15)

        self.health = {
            "ok": bool(offers) or not errors,
            "message": "ok" if not errors else "; ".join(errors[:4]),
            "items": len(offers),
        }
        return offers

    def revalidate(self, offer: Offer) -> tuple[bool, str]:
        if not offer.product_id:
            return False, "sem id do anúncio"
        try:
            response = self.session.get(
                f"https://api.mercadolibre.com/items/{offer.product_id}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            row = response.json()
        except Exception as exc:
            return False, f"falha ao revalidar: {type(exc).__name__}"

        status = str(row.get("status", "")).lower()
        if status != "active":
            return False, f"status {status or 'desconhecido'}"

        current = row.get("price")
        if not isinstance(current, (int, float)):
            return False, "preço atual ausente"

        if abs(float(current) - offer.price) / max(offer.price, 1) > 0.03:
            return False, f"preço mudou para R$ {float(current):.2f}"

        return True, "ativo e preço confirmado novamente pela API"
