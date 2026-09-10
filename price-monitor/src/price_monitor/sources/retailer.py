from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse

from selenium.webdriver.common.by import By

from ..browser import build_driver
from ..models import Offer
from ..normalize import expensive_product_hint, product_key
from ..utils import extract_brl_prices, pick_current_and_original, similar_price
from .base import Source


class RetailerSource(Source):
    """Coletor genérico para varejistas que vendem diretamente no próprio domínio."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.name = str(config.get("name") or "Varejista")
        self.base_url = str(config.get("base_url") or "")
        self.catalog_urls = [str(x) for x in config.get("catalog_urls", []) if x]
        self.max_items = max(10, min(int(config.get("max_items", 90)), 180))
        self.scrolls = max(0, min(int(config.get("scrolls", 3)), 10))
        self.direct_retailer = bool(config.get("direct_retailer", True))
        self.product_path_regex = re.compile(str(config.get("product_path_regex") or r".+"), re.I)
        self._catalog_keys = {self._url_key(x) for x in [self.base_url, *self.catalog_urls] if x}

    @staticmethod
    def _url_key(url: str) -> tuple[str, str, str]:
        p = urlparse(url)
        host = p.netloc.lower().removeprefix("www.")
        path = p.path.rstrip("/") or "/"
        return host, path, p.query

    @property
    def _host(self) -> str:
        return urlparse(self.base_url).netloc.lower().removeprefix("www.")

    def _same_store_domain(self, url: str) -> bool:
        try:
            host = urlparse(url).netloc.lower().removeprefix("www.")
        except Exception:
            return False
        return bool(host and (host == self._host or host.endswith("." + self._host)))

    def _allowed_product_url(self, url: str) -> bool:
        if not self._same_store_domain(url):
            return False
        key = self._url_key(url)
        if key in self._catalog_keys or key[1] == "/":
            return False
        return bool(self.product_path_regex.search(key[1]))

    @staticmethod
    def _card_text(driver, anchor) -> str:
        text = (anchor.text or "").strip()
        if "R$" in text and len(text) < 1800:
            return text
        return driver.execute_script(
            """
            let e=arguments[0];
            for(let i=0;i<6&&e;i++,e=e.parentElement){
              const t=(e.innerText||'').trim();
              if(t.includes('R$') && t.length<1800) return t;
            }
            return '';
            """,
            anchor,
        ) or ""

    @staticmethod
    def _title(anchor, text: str) -> str:
        attr = (anchor.get_attribute("title") or "").strip()
        if len(attr) >= 12:
            return attr
        lines = [x.strip() for x in (text or "").splitlines() if x.strip()]
        ignored = ("comprar", "adicionar ao carrinho", "frete", "economize")
        for line in lines:
            low = line.lower()
            if "R$" in line or any(x in low for x in ignored):
                continue
            if len(line) >= 14:
                return line
        return ""

    @staticmethod
    def _jsonld_prices(driver) -> list[float]:
        prices: list[float] = []
        try:
            scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
        except Exception:
            return prices

        def walk(obj):
            if isinstance(obj, dict):
                if obj.get("@type") in ("Offer", "AggregateOffer"):
                    for key in ("price", "lowPrice", "highPrice"):
                        try:
                            value = float(str(obj.get(key)).replace(",", "."))
                        except Exception:
                            continue
                        if value > 0:
                            prices.append(value)
                for value in obj.values():
                    walk(value)
            elif isinstance(obj, list):
                for value in obj:
                    walk(value)

        for script in scripts[:30]:
            raw = script.get_attribute("innerHTML") or ""
            if not raw.strip():
                continue
            try:
                walk(json.loads(raw))
            except Exception:
                continue
        return prices

    def collect(self) -> list[Offer]:
        if not self.direct_retailer or not self.base_url or not self.catalog_urls:
            self.health = {"ok": False, "message": "fonte sem configuração de varejista direto", "items": 0}
            return []

        driver = None
        offers: list[Offer] = []
        seen: set[str] = set()
        errors: list[str] = []
        try:
            driver = build_driver()
            for catalog_url in self.catalog_urls:
                try:
                    driver.get(catalog_url)
                    time.sleep(2.5)
                    for _ in range(self.scrolls):
                        driver.execute_script("window.scrollBy(0, 1700)")
                        time.sleep(0.55)
                    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href]")
                    for anchor in anchors:
                        if len(offers) >= self.max_items:
                            break
                        href = anchor.get_attribute("href") or ""
                        if not href or href in seen or not self._allowed_product_url(href):
                            continue
                        text = self._card_text(driver, anchor)
                        if "R$" not in text:
                            continue
                        prices = extract_brl_prices(text)
                        current, original = pick_current_and_original(prices)
                        title = self._title(anchor, text)
                        if not current or not title:
                            continue
                        if current < 900 and not expensive_product_hint(title):
                            continue
                        seen.add(href)
                        offer = Offer(
                            source=self.name,
                            title=title[:260],
                            price=current,
                            original_price=original,
                            url=href,
                            store_name=self.name,
                            official=True,
                            available="indispon" not in text.lower() and "esgotado" not in text.lower(),
                            metadata={"collector": "retailer", "direct_retailer": True, "catalog_url": catalog_url},
                        )
                        offer.product_key = product_key(offer.title)
                        offers.append(offer)
                except Exception as exc:
                    errors.append(f"{catalog_url}: {type(exc).__name__}")
        except Exception as exc:
            errors.append(f"navegador: {type(exc).__name__}")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        self.health = {
            "ok": bool(offers),
            "message": "varejista direto" if offers else "; ".join(errors[:4]) or "nenhum item carregado",
            "items": len(offers),
        }
        return offers

    def revalidate(self, offer: Offer) -> tuple[bool, str]:
        if not self._allowed_product_url(offer.url):
            return False, "produto fora do domínio configurado"
        driver = None
        try:
            driver = build_driver()
            driver.get(offer.url)
            time.sleep(2.8)
            body = driver.find_element(By.TAG_NAME, "body").text
            low = body.lower()
            if any(x in low for x in ("produto indisponível", "produto indisponivel", "esgotado", "sem estoque")):
                return False, "produto indisponível"
            prices = self._jsonld_prices(driver) + extract_brl_prices(body)
            if not any(similar_price(p, offer.price, 0.05) for p in prices):
                return False, "preço mudou antes da segunda confirmação"
            return True, f"{self.name}: domínio e preço confirmados novamente"
        except Exception as exc:
            return False, f"falha ao revalidar: {type(exc).__name__}"
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
