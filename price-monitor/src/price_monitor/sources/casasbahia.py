from __future__ import annotations

import time
from urllib.parse import quote, quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from ..browser import build_driver
from ..models import Offer
from ..normalize import expensive_product_hint, product_key
from ..utils import extract_brl_prices, pick_current_and_original, similar_price
from .base import Source


class CasasBahiaSource(Source):
    name = "Casas Bahia"

    def __init__(self, queries: list[str], max_candidates_per_query: int = 6):
        super().__init__(); self.queries = queries
        self.max_candidates_per_query = max(1, min(max_candidates_per_query, 12))

    @staticmethod
    def _find_search_input(driver):
        selectors = [
            "input[type='search']", "input[name*='search' i]", "input[id*='search' i]",
            "input[placeholder*='busc' i]", "input[aria-label*='busc' i]", "input[type='text']",
        ]
        for selector in selectors:
            try:
                for el in driver.find_elements(By.CSS_SELECTOR, selector):
                    if el.is_displayed() and el.is_enabled():
                        return el
            except Exception:
                pass
        return None

    @staticmethod
    def _seller_is_casas_bahia(body: str) -> bool:
        text = " ".join((body or "").lower().split())
        return any(m in text for m in (
            "vendido e entregue por casas bahia", "vendido por casas bahia",
            "vendido e entregue pela casas bahia", "loja casas bahia",
        ))

    @staticmethod
    def _candidate_score(title: str, price: float, original: float | None) -> float:
        score = 0.0
        if original and original >= 1500 and price < original:
            score += (1 - price / original) * 100
        if expensive_product_hint(title):
            score += 35
            if price <= 1500: score += 30
            if price <= 500: score += 30
        return score

    def _open_search(self, driver, query: str) -> bool:
        driver.get("https://www.casasbahia.com.br/"); time.sleep(2.5)
        search = self._find_search_input(driver)
        if search is not None:
            try:
                search.click(); search.send_keys(Keys.CONTROL, "a"); search.send_keys(query); search.send_keys(Keys.ENTER)
                time.sleep(3.2)
                if "R$" in driver.find_element(By.TAG_NAME, "body").text:
                    return True
            except Exception:
                pass
        slug = quote(query.strip().replace(" ", "-"))
        candidates = [
            f"https://www.casasbahia.com.br/busca/{slug}",
            f"https://www.casasbahia.com.br/busca?q={quote_plus(query)}",
            f"https://www.casasbahia.com.br/?q={quote_plus(query)}",
        ]
        for url in candidates:
            try:
                driver.get(url); time.sleep(2.7)
                if "R$" in driver.find_element(By.TAG_NAME, "body").text:
                    return True
            except Exception:
                continue
        return False

    def collect(self) -> list[Offer]:
        driver = None; offers: list[Offer] = []; seen: set[str] = set(); errors: list[str] = []
        try:
            driver = build_driver()
            for query in self.queries:
                try:
                    if not self._open_search(driver, query):
                        errors.append(f"{query}: busca não carregou")
                        continue
                    driver.execute_script("window.scrollBy(0, 2200)"); time.sleep(0.8)
                    candidates = []
                    for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                        href = anchor.get_attribute("href") or ""
                        if "casasbahia.com.br" not in href or href in seen or "/busca" in href:
                            continue
                        text = driver.execute_script(
                            """let e=arguments[0]; for(let i=0;i<5&&e;i++,e=e.parentElement){const t=(e.innerText||'').trim(); if(t.includes('R$')&&t.length<1500)return t;} return '';""", anchor
                        ) or ""
                        prices = extract_brl_prices(text); current, original = pick_current_and_original(prices)
                        lines = [x.strip() for x in text.splitlines() if x.strip()]
                        title = anchor.get_attribute("title") or next((x for x in lines if "R$" not in x and len(x) >= 14), "")
                        if not current or not title:
                            continue
                        score = self._candidate_score(title, current, original)
                        if score >= 42:
                            candidates.append((score, href, title, current, original))
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    for _, href, title, current, original in candidates[: self.max_candidates_per_query]:
                        if href in seen: continue
                        seen.add(href)
                        try:
                            driver.get(href); time.sleep(2.2); body = driver.find_element(By.TAG_NAME, "body").text
                        except Exception: continue
                        if not self._seller_is_casas_bahia(body): continue
                        low = body.lower()
                        if "indispon" in low or "esgotado" in low: continue
                        page_prices = extract_brl_prices(body)
                        page_current = next((p for p in page_prices if similar_price(p, current, 0.08)), current)
                        offer = Offer(
                            source=self.name, title=title[:260], price=page_current, original_price=original,
                            url=href, store_name="Casas Bahia", official=True, available=True,
                            metadata={"query": query, "seller_verified_on_pdp": True},
                        )
                        offer.product_key = product_key(offer.title); offers.append(offer)
                except Exception as exc:
                    errors.append(f"{query}: {type(exc).__name__}")
        except Exception as exc:
            errors.append(f"navegador: {type(exc).__name__}")
        finally:
            if driver is not None:
                try: driver.quit()
                except Exception: pass
        self.health = {
            "ok": bool(offers),
            "message": "PDP confirma vendedor Casas Bahia" if offers else "; ".join(errors[:5]) or "nenhum candidato oficial",
            "items": len(offers),
        }
        return offers

    def revalidate(self, offer: Offer) -> tuple[bool, str]:
        driver = None
        try:
            driver = build_driver(); driver.get(offer.url); time.sleep(2.7)
            body = driver.find_element(By.TAG_NAME, "body").text; low = body.lower()
            if "indispon" in low or "esgotado" in low: return False, "produto indisponível"
            if not self._seller_is_casas_bahia(body): return False, "vendedor não é a própria Casas Bahia"
            if not any(similar_price(p, offer.price, 0.05) for p in extract_brl_prices(body)):
                return False, "preço mudou antes da segunda confirmação"
            return True, "PDP reaberta; Casas Bahia e preço confirmados"
        except Exception as exc:
            return False, f"falha ao revalidar: {type(exc).__name__}"
        finally:
            if driver is not None:
                try: driver.quit()
                except Exception: pass
