from __future__ import annotations

import os
import re
import time
from urllib.parse import quote

import requests
from selenium.webdriver.common.by import By

from ..browser import build_driver
from ..models import Offer
from ..normalize import product_key
from ..utils import extract_brl_prices, normalize_text, pick_current_and_original, similar_price
from .base import Source


class MercadoLivreSource(Source):
    name = "Mercado Livre"

    def __init__(self, queries: list[str], official_stores: list[dict] | None = None, limit_per_query: int = 50, timeout: int = 20):
        super().__init__()
        self.queries = queries
        self.official_stores = [x for x in (official_stores or []) if x.get("verified_official")]
        self.limit_per_query = min(max(limit_per_query, 1), 50)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "PriceMonitor/0.2"})
        token = os.getenv("MELI_ACCESS_TOKEN", "").strip()
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    @staticmethod
    def _official_store_api(row: dict) -> tuple[bool, str]:
        seller = row.get("seller") or {}
        official_id = row.get("official_store_id") or seller.get("official_store_id")
        official_name = row.get("official_store_name") or seller.get("official_store_name")
        return bool(official_id or official_name), str(official_name or seller.get("nickname") or "Loja Oficial")

    def _collect_api(self) -> tuple[list[Offer], list[str]]:
        offers: list[Offer] = []
        errors: list[str] = []
        seen: set[str] = set()
        for query in self.queries:
            try:
                r = self.session.get(
                    "https://api.mercadolibre.com/sites/MLB/search",
                    params={"q": query, "limit": self.limit_per_query}, timeout=self.timeout,
                )
                if r.status_code in (401, 403):
                    errors.append(f"API {r.status_code}; usando navegador")
                    return [], errors
                r.raise_for_status()
                payload = r.json()
            except Exception as exc:
                errors.append(f"API {query}: {type(exc).__name__}")
                return [], errors
            for row in payload.get("results", []):
                official, store_name = self._official_store_api(row)
                if not official:
                    continue
                url, title, price = row.get("permalink"), row.get("title"), row.get("price")
                if not url or not title or not isinstance(price, (int, float)) or url in seen:
                    continue
                seen.add(url)
                offer = Offer(
                    source=self.name, title=str(title), price=float(price), url=str(url),
                    store_name=store_name, official=True,
                    original_price=float(row["original_price"]) if isinstance(row.get("original_price"), (int, float)) else None,
                    available=bool(row.get("available_quantity", 1)), product_id=str(row.get("id") or ""),
                    metadata={"collector": "api"},
                )
                offer.product_key = product_key(offer.title)
                offers.append(offer)
        return offers, errors

    @staticmethod
    def _card_store(text: str, stores: list[dict]) -> str | None:
        lines = [normalize_text(x) for x in (text or "").splitlines() if x.strip()]
        full = normalize_text(text)
        for store in stores:
            name = normalize_text(str(store.get("name") or ""))
            marker = normalize_text(str(store.get("marker") or store.get("name") or ""))
            if not marker:
                continue
            if f"loja oficial {marker}" in full:
                return str(store.get("name"))
            for line in lines:
                if line == marker or re.fullmatch(rf"{re.escape(marker)}\s+[0-5](?:[.,]\d)?", line):
                    return str(store.get("name"))
        return None

    def _collect_browser(self) -> tuple[list[Offer], list[str]]:
        offers: list[Offer] = []
        errors: list[str] = []
        seen: set[str] = set()
        driver = None
        try:
            driver = build_driver()
            for query in self.queries:
                try:
                    slug = quote(query.strip().replace(" ", "-"))
                    driver.get(f"https://lista.mercadolivre.com.br/{slug}")
                    time.sleep(2.8)
                    for _ in range(3):
                        driver.execute_script("window.scrollBy(0, 1600)")
                        time.sleep(0.5)
                    for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                        href = anchor.get_attribute("href") or ""
                        if "mercadolivre.com.br" not in href or href in seen:
                            continue
                        text = driver.execute_script(
                            """let e=arguments[0]; for(let i=0;i<6&&e;i++,e=e.parentElement){const t=(e.innerText||'').trim(); if(t.includes('R$')&&t.length<1800)return t;} return '';""",
                            anchor,
                        ) or ""
                        store_name = self._card_store(text, self.official_stores)
                        if not store_name:
                            continue
                        prices = extract_brl_prices(text)
                        current, original = pick_current_and_original(prices)
                        lines = [x.strip() for x in text.splitlines() if x.strip()]
                        title = anchor.get_attribute("title") or next((x for x in lines if "R$" not in x and len(x) >= 18 and "loja oficial" not in x.lower()), "")
                        if not current or not title:
                            continue
                        seen.add(href)
                        offer = Offer(
                            source=self.name, title=title[:260], price=current, original_price=original,
                            url=href, store_name=store_name, official=True, available=True,
                            metadata={"collector": "browser", "official_store_allowlist": True},
                        )
                        offer.product_key = product_key(offer.title)
                        offers.append(offer)
                except Exception as exc:
                    errors.append(f"web {query}: {type(exc).__name__}")
        finally:
            if driver is not None:
                try: driver.quit()
                except Exception: pass
        return offers, errors

    def collect(self) -> list[Offer]:
        api_offers, api_errors = self._collect_api()
        if api_offers:
            self.health = {"ok": True, "message": "API", "items": len(api_offers)}
            return api_offers
        web_offers, web_errors = self._collect_browser()
        errors = api_errors + web_errors
        self.health = {
            "ok": bool(web_offers),
            "message": "navegador" if web_offers else "; ".join(errors[:5]) or "nenhum item oficial encontrado",
            "items": len(web_offers),
        }
        return web_offers

    def revalidate(self, offer: Offer) -> tuple[bool, str]:
        if offer.metadata.get("collector") == "api" and offer.product_id:
            try:
                r = self.session.get(f"https://api.mercadolibre.com/items/{offer.product_id}", timeout=self.timeout)
                r.raise_for_status(); row = r.json()
                current = row.get("price")
                if str(row.get("status", "")).lower() != "active" or not isinstance(current, (int, float)):
                    return False, "anúncio não está ativo"
                if not similar_price(float(current), offer.price, 0.03):
                    return False, f"preço mudou para R$ {float(current):.2f}"
                return True, "ativo e preço reconfirmado pela API"
            except Exception as exc:
                return False, f"falha API: {type(exc).__name__}"

        driver = None
        try:
            driver = build_driver(); driver.get(offer.url); time.sleep(2.8)
            body = driver.find_element(By.TAG_NAME, "body").text
            low = normalize_text(body); store = normalize_text(offer.store_name)
            unavailable = ("anuncio pausado", "produto indisponivel", "sem estoque")
            if any(x in low for x in unavailable):
                return False, "anúncio indisponível"
            official_ok = f"loja oficial {store}" in low or f"vendido por {store}" in low or f"vendido e entregue por {store}" in low
            if not official_ok:
                return False, "loja oficial não reconfirmada na página"
            prices = extract_brl_prices(body)
            if not any(similar_price(p, offer.price, 0.04) for p in prices):
                return False, "preço mudou antes da segunda confirmação"
            return True, "página reaberta; vendedor oficial e preço confirmados"
        except Exception as exc:
            return False, f"falha ao revalidar: {type(exc).__name__}"
        finally:
            if driver is not None:
                try: driver.quit()
                except Exception: pass
