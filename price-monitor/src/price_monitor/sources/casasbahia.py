from __future__ import annotations

import time

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from ..browser import build_driver
from ..models import Offer
from ..normalize import expensive_product_hint, product_key
from ..utils import extract_brl_prices, pick_current_and_original, similar_price
from .base import Source


class CasasBahiaSource(Source):
    name = "Casas Bahia"

    def __init__(self, queries: list[str], max_candidates_per_query: int = 8):
        super().__init__()
        self.queries = queries
        self.max_candidates_per_query = max(1, min(max_candidates_per_query, 15))

    @staticmethod
    def _find_search_input(driver):
        selectors = [
            "input[type='search']",
            "input[placeholder*='Busc']",
            "input[placeholder*='busc']",
            "input[aria-label*='Busc']",
            "input[aria-label*='busc']",
        ]
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        return el
            except Exception:
                continue
        return None

    @staticmethod
    def _seller_is_casas_bahia(body: str) -> bool:
        text = " ".join((body or "").lower().split())
        markers = (
            "vendido e entregue por casas bahia",
            "vendido por casas bahia",
            "vendido e entregue pela casas bahia",
        )
        return any(m in text for m in markers)

    @staticmethod
    def _candidate_score(title: str, price: float, original: float | None) -> float:
        score = 0.0
        if original and original >= 1500 and price < original:
            score += (1 - price / original) * 100
        if expensive_product_hint(title):
            score += 35
            if price <= 1500:
                score += 30
            if price <= 500:
                score += 30
        return score

    def collect(self) -> list[Offer]:
        driver = None
        offers: list[Offer] = []
        seen: set[str] = set()
        errors: list[str] = []

        try:
            driver = build_driver()
            driver.get("https://www.casasbahia.com.br/")
            time.sleep(3)

            for query in self.queries:
                try:
                    search = self._find_search_input(driver)
                    if search is None:
                        driver.get("https://www.casasbahia.com.br/")
                        time.sleep(2)
                        search = self._find_search_input(driver)
                    if search is None:
                        errors.append(f"{query}: campo de busca não encontrado")
                        continue

                    search.click()
                    search.send_keys(Keys.CONTROL, "a")
                    search.send_keys(query)
                    search.send_keys(Keys.ENTER)
                    time.sleep(4)
                    driver.execute_script("window.scrollTo(0, Math.min(document.body.scrollHeight, 2600));")
                    time.sleep(1)

                    raw_candidates = []
                    for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                        href = anchor.get_attribute("href") or ""
                        if "casasbahia.com.br" not in href or href in seen:
                            continue

                        text = anchor.text.strip()
                        if "R$" not in text:
                            text = driver.execute_script(
                                """
                                let e = arguments[0];
                                for (let i=0; i<4 && e; i++, e=e.parentElement) {
                                  const t=(e.innerText||'').trim();
                                  if (t.includes('R$') && t.length < 1200) return t;
                                }
                                return '';
                                """,
                                anchor,
                            ) or ""
                        if "R$" not in text:
                            continue
                        prices = extract_brl_prices(text)
                        current, original = pick_current_and_original(prices)
                        lines = [x.strip() for x in text.splitlines() if x.strip()]
                        title = next((x for x in lines if "R$" not in x and len(x) >= 12), "")
                        if not current or not title:
                            continue
                        score = self._candidate_score(title, current, original)
                        if score < 45:
                            continue
                        raw_candidates.append((score, href, title, current, original))

                    raw_candidates.sort(reverse=True, key=lambda row: row[0])
                    for _, href, title, current, original in raw_candidates[: self.max_candidates_per_query]:
                        if href in seen:
                            continue
                        seen.add(href)
                        try:
                            driver.get(href)
                            time.sleep(2.5)
                            body = driver.find_element(By.TAG_NAME, "body").text
                        except Exception:
                            continue

                        if not self._seller_is_casas_bahia(body):
                            continue
                        if "indispon" in body.lower() or "esgotado" in body.lower():
                            continue

                        body_prices = extract_brl_prices(body)
                        page_current = next(
                            (p for p in body_prices if similar_price(p, current, 0.08)),
                            current,
                        )
                        offer = Offer(
                            source=self.name,
                            title=title[:240],
                            price=page_current,
                            original_price=original,
                            url=href,
                            store_name="Casas Bahia",
                            official=True,
                            available=True,
                            metadata={"query": query, "seller_verified_on_pdp": True},
                        )
                        offer.product_key = product_key(offer.title)
                        offers.append(offer)

                    driver.get("https://www.casasbahia.com.br/")
                    time.sleep(1.5)

                except Exception as exc:
                    errors.append(f"{query}: {type(exc).__name__}")
                    try:
                        driver.get("https://www.casasbahia.com.br/")
                        time.sleep(1)
                    except Exception:
                        pass
        except Exception as exc:
            errors.append(f"inicialização: {type(exc).__name__}")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        self.health = {
            "ok": bool(offers) or not errors,
            "message": "ok" if not errors else "; ".join(errors[:5]),
            "items": len(offers),
        }
        return offers

    def revalidate(self, offer: Offer) -> tuple[bool, str]:
        driver = None
        try:
            driver = build_driver()
            driver.get(offer.url)
            time.sleep(3)
            body = driver.find_element(By.TAG_NAME, "body").text
            low = body.lower()
            if "indispon" in low or "esgotado" in low:
                return False, "produto indisponível"
            if not self._seller_is_casas_bahia(body):
                return False, "vendedor não é a própria Casas Bahia"
            prices = extract_brl_prices(body)
            if not any(similar_price(p, offer.price, 0.05) for p in prices):
                return False, "preço mudou antes da segunda confirmação"
            return True, "página reaberta; vendido pela Casas Bahia e preço confirmado"
        except WebDriverException as exc:
            return False, f"navegador bloqueado: {type(exc).__name__}"
        except Exception as exc:
            return False, f"falha ao revalidar: {type(exc).__name__}"
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
