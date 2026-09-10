from __future__ import annotations

import re
import time

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By

from ..browser import build_driver
from ..models import Offer
from ..normalize import product_key
from ..utils import absolute_url, extract_brl_prices, pick_current_and_original, similar_price
from .base import Source


PRODUCT_HREF_RE = re.compile(r"-i\.\d+\.\d+", re.I)


class ShopeeSource(Source):
    name = "Shopee"

    def __init__(self, shops: list[dict], scrolls: int = 5):
        super().__init__()
        self.shops = shops
        self.scrolls = max(1, min(scrolls, 12))
        self.driver = None

    def _driver(self):
        if self.driver is None:
            self.driver = build_driver()
        return self.driver

    @staticmethod
    def _shop_is_official(body: str, expected_name: str) -> bool:
        text = body.lower()
        expected = expected_name.lower().strip()
        return "loja oficial" in text and (expected in text or "oficial" in expected)

    def collect(self) -> list[Offer]:
        offers: list[Offer] = []
        seen: set[str] = set()
        errors: list[str] = []

        try:
            driver = self._driver()
            for shop in self.shops:
                url = str(shop.get("url") or "")
                name = str(shop.get("name") or "Loja Oficial")
                if not url:
                    continue
                try:
                    driver.get(url)
                    time.sleep(3)
                    body = driver.find_element(By.TAG_NAME, "body").text
                    if not self._shop_is_official(body, name):
                        errors.append(f"{name}: selo oficial não confirmado")
                        continue

                    for _ in range(self.scrolls):
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(1.0)

                    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
                    for anchor in anchors:
                        href = anchor.get_attribute("href") or ""
                        if not PRODUCT_HREF_RE.search(href):
                            continue
                        href = absolute_url("https://shopee.com.br/", href)
                        if href in seen:
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
                        prices = extract_brl_prices(text)
                        current, original = pick_current_and_original(prices)
                        lines = [x.strip() for x in text.splitlines() if x.strip()]
                        title = next(
                            (x for x in lines if "R$" not in x and len(x) >= 12),
                            anchor.get_attribute("title") or "",
                        )
                        if not current or not title:
                            continue

                        seen.add(href)
                        m = PRODUCT_HREF_RE.search(href)
                        offer = Offer(
                            source=self.name,
                            title=title[:240],
                            price=current,
                            original_price=original,
                            url=href,
                            store_name=name,
                            official=True,
                            available="esgotado" not in text.lower(),
                            product_id=m.group(0) if m else None,
                            metadata={"shop_url": url},
                        )
                        offer.product_key = product_key(offer.title)
                        offers.append(offer)
                except Exception as exc:
                    errors.append(f"{name}: {type(exc).__name__}")
                    continue
        finally:
            if self.driver is not None:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None

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
            if "esgotado" in low or "produto indispon" in low:
                return False, "produto esgotado/indisponível"
            if "loja oficial" not in low and "mall" not in low:
                return False, "selo de loja oficial não confirmado na página"
            prices = extract_brl_prices(body)
            if not any(similar_price(p, offer.price, 0.04) for p in prices):
                return False, "preço encontrado não coincide na revalidação"
            return True, "página reaberta; loja oficial e preço confirmados"
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
