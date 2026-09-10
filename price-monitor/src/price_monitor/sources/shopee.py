from __future__ import annotations

import re
import time
from collections import Counter

from selenium.webdriver.common.by import By

from ..browser import build_driver
from ..models import Offer
from ..normalize import product_key
from ..utils import absolute_url, extract_brl_prices, pick_current_and_original, similar_price
from .base import Source


PRODUCT_RE = re.compile(r"-i\.(\d+)\.(\d+)", re.I)


class ShopeeSource(Source):
    name = "Shopee"

    def __init__(self, shops: list[dict], scrolls: int = 5):
        super().__init__()
        self.shops = [x for x in shops if x.get("verified_official")]
        self.scrolls = max(1, min(scrolls, 12))

    @staticmethod
    def _dominant_shop_id(hrefs: list[str]) -> str | None:
        ids = [m.group(1) for href in hrefs if (m := PRODUCT_RE.search(href or ""))]
        return Counter(ids).most_common(1)[0][0] if ids else None

    def collect(self) -> list[Offer]:
        offers: list[Offer] = []; seen: set[str] = set(); errors: list[str] = []
        driver = None
        try:
            driver = build_driver()
            for shop in self.shops:
                url = str(shop.get("url") or ""); name = str(shop.get("name") or "Loja Oficial")
                if not url:
                    continue
                try:
                    driver.get(url); time.sleep(3)
                    for _ in range(self.scrolls):
                        driver.execute_script("window.scrollBy(0, 1500)"); time.sleep(0.7)
                    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
                    hrefs = [a.get_attribute("href") or "" for a in anchors]
                    shop_id = str(shop.get("shop_id") or self._dominant_shop_id(hrefs) or "")
                    if not shop_id:
                        errors.append(f"{name}: nenhum produto do shop carregou")
                        continue
                    for anchor, href in zip(anchors, hrefs):
                        m = PRODUCT_RE.search(href)
                        if not m or m.group(1) != shop_id:
                            continue
                        href = absolute_url("https://shopee.com.br/", href)
                        if href in seen:
                            continue
                        text = anchor.text.strip()
                        if "R$" not in text:
                            text = driver.execute_script(
                                """let e=arguments[0]; for(let i=0;i<5&&e;i++,e=e.parentElement){const t=(e.innerText||'').trim(); if(t.includes('R$')&&t.length<1400)return t;} return '';""", anchor
                            ) or ""
                        prices = extract_brl_prices(text); current, original = pick_current_and_original(prices)
                        lines = [x.strip() for x in text.splitlines() if x.strip()]
                        title = anchor.get_attribute("title") or next((x for x in lines if "R$" not in x and len(x) >= 14), "")
                        if not current or not title:
                            continue
                        seen.add(href)
                        offer = Offer(
                            source=self.name, title=title[:260], price=current, original_price=original,
                            url=href, store_name=name, official=True,
                            available="esgotado" not in text.lower(), product_id=m.group(2),
                            metadata={
                                "shop_id": shop_id,
                                "official_store_url": url,
                                "official_verified_at": shop.get("verified_at"),
                                "official_allowlist": True,
                            },
                        )
                        offer.product_key = product_key(offer.title); offers.append(offer)
                except Exception as exc:
                    errors.append(f"{name}: {type(exc).__name__}")
        finally:
            if driver is not None:
                try: driver.quit()
                except Exception: pass
        self.health = {
            "ok": bool(offers),
            "message": "lojas oficiais por allowlist + shop id" if offers else "; ".join(errors[:5]) or "nenhum item carregado",
            "items": len(offers),
        }
        return offers

    def revalidate(self, offer: Offer) -> tuple[bool, str]:
        expected_shop = str(offer.metadata.get("shop_id") or "")
        m = PRODUCT_RE.search(offer.url)
        if not m or not expected_shop or m.group(1) != expected_shop:
            return False, "shop id não corresponde à loja oficial verificada"
        driver = None
        try:
            driver = build_driver(); driver.get(offer.url); time.sleep(3)
            body = driver.find_element(By.TAG_NAME, "body").text; low = body.lower()
            if "esgotado" in low or "produto indispon" in low or "produto não encontrado" in low:
                return False, "produto esgotado/indisponível"
            prices = extract_brl_prices(body)
            if not any(similar_price(p, offer.price, 0.04) for p in prices):
                return False, "preço não coincide na segunda leitura"
            return True, "shop id oficial e preço confirmados novamente"
        except Exception as exc:
            return False, f"falha ao revalidar: {type(exc).__name__}"
        finally:
            if driver is not None:
                try: driver.quit()
                except Exception: pass
