from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus, urlparse, urlunparse

from selenium.webdriver.common.by import By

from .browser import build_driver
from .bug_rules import score_product
from .utils import extract_brl_prices, normalize_text, parse_brl, pick_current_and_original, similar_price


FIXED_QUERIES = ["notebook gamer", "playstation 5", "smart tv", "placa de video"]
ROTATING_QUERIES = [
    "microondas", "air fryer", "smart tv 50", "smart tv 65", "rtx 5090", "rtx 5080",
    "rtx 5070", "iphone 17", "galaxy s ultra", "xbox series x", "nintendo switch 2",
    "geladeira", "lava e seca", "ar condicionado inverter", "monitor gamer", "ssd nvme 2tb",
    "jbl boombox", "jbl partybox", "dji mini", "aspirador robo", "estante tv", "painel tv",
]

SOURCES = {
    "Mercado Livre": {
        "host": "mercadolivre.com.br",
        "search": lambda q: f"https://lista.mercadolivre.com.br/{quote(q.strip().replace(' ', '-'))}",
        "product": re.compile(r"(?:/MLB-\d+|/p/MLB\d+|/up/MLBU\d+)", re.I),
        "trust": ("loja oficial", "mercadolíder", "mercado lider"),
    },
    "Amazon Brasil": {
        "host": "amazon.com.br",
        "search": lambda q: f"https://www.amazon.com.br/s?k={quote_plus(q)}",
        "product": re.compile(r"/(?:dp|gp/product)/[A-Z0-9]{8,14}", re.I),
        "trust": ("vendido por amazon.com.br", "enviado por amazon.com.br"),
    },
    "Magalu": {
        "host": "magazineluiza.com.br",
        "search": lambda q: f"https://www.magazineluiza.com.br/busca/{quote(q.strip().replace(' ', '-'))}/",
        "product": re.compile(r"/p/", re.I),
        "trust": ("vendido por magalu", "vendido e entregue por magalu"),
    },
    "Shopee": {
        "host": "shopee.com.br",
        "search": lambda q: f"https://shopee.com.br/search?keyword={quote_plus(q)}",
        "product": re.compile(r"-i\.\d+\.\d+", re.I),
        "trust": ("loja oficial", "preferido+", "preferido"),
    },
}


def _canon(url: str) -> str:
    try:
        p = urlparse(url)
        return urlunparse((p.scheme or "https", p.netloc, p.path, "", "", ""))
    except Exception:
        return url


def _same_domain(url: str, host: str) -> bool:
    try:
        actual = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return False
    return actual == host or actual.endswith("." + host)


def _card_text(driver, anchor) -> str:
    text = (anchor.text or "").strip()
    if "R$" in text and len(text) < 1800:
        return text
    return driver.execute_script(
        """let e=arguments[0]; for(let i=0;i<6&&e;i++,e=e.parentElement){const t=(e.innerText||'').trim(); if(t.includes('R$')&&t.length<1800)return t;} return '';""",
        anchor,
    ) or ""


def _title(anchor, text: str) -> str:
    attr = (anchor.get_attribute("title") or anchor.get_attribute("aria-label") or "").strip()
    if len(attr) >= 10 and "R$" not in attr:
        return attr[:300]
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    ignored = ("r$", "frete", "cupom", "desconto", "patrocinado", "mais vendido", "vendidos")
    candidates = [x for x in lines if len(x) >= 10 and not any(x.lower().startswith(v) for v in ignored)]
    candidates = [x for x in candidates if not re.fullmatch(r"[0-9.,%x ]+", x)]
    return max(candidates, key=len)[:300] if candidates else ""


def _query_relevant(query: str, title: str) -> bool:
    q = normalize_text(query)
    t = normalize_text(title)
    families = {
        "placa de video": ("placa de video", "geforce", "radeon", "rtx ", "rx ", "gpu"),
        "playstation 5": ("playstation 5", "ps5"),
        "smart tv": ("smart tv", "televisor", " tv "),
        "notebook gamer": ("notebook", "laptop", "rog strix", "predator", "nitro"),
        "microondas": ("micro ondas", "microondas"),
        "air fryer": ("air fryer", "fritadeira"),
        "nintendo switch 2": ("nintendo switch 2", "switch 2"),
        "geladeira": ("geladeira", "refrigerador"),
        "lava e seca": ("lava e seca",),
        "ar condicionado inverter": ("ar condicionado", "split inverter"),
        "monitor gamer": ("monitor",),
        "ssd nvme 2tb": ("ssd", "nvme", "m 2"),
        "jbl boombox": ("jbl", "boombox"),
        "jbl partybox": ("jbl", "partybox"),
        "dji mini": ("dji",),
        "aspirador robo": ("aspirador", "robo"),
        "estante tv": ("estante", "tv"),
        "painel tv": ("painel", "tv"),
    }
    for prefix, markers in families.items():
        if q.startswith(prefix):
            if prefix in {"ssd nvme 2tb", "jbl boombox", "jbl partybox", "aspirador robo", "estante tv", "painel tv"}:
                return all(marker in t for marker in markers)
            return any(marker in t for marker in markers)
    if q.startswith("rtx "):
        model = q.replace(" ", "")
        return model in t.replace(" ", "")
    if q.startswith("smart tv 50"):
        return "tv" in t and ("50" in t or "49" in t)
    if q.startswith("smart tv 65"):
        return "tv" in t and "65" in t
    if q.startswith("iphone 17"):
        return "iphone 17" in t
    if q.startswith("galaxy s ultra"):
        return "galaxy" in t and "ultra" in t
    if q.startswith("xbox series x"):
        return "xbox series x" in t
    return True


def _amazon_card(anchor) -> tuple[str | None, float | None, float | None]:
    try:
        card = anchor.find_element(By.XPATH, "./ancestor::div[@data-component-type='s-search-result'][1]")
    except Exception:
        return None, None, None
    title = ""
    for selector in ("h2 span", "h2 a span"):
        try:
            title = (card.find_element(By.CSS_SELECTOR, selector).text or "").strip()
        except Exception:
            continue
        if title:
            break
    current: float | None = None
    for selector in (".a-price:not(.a-text-price) .a-offscreen", ".a-price .a-offscreen"):
        try:
            elements = card.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []
        for element in elements:
            value = parse_brl(element.get_attribute("textContent") or element.text or "")
            if value:
                current = value
                break
        if current:
            break
    originals: list[float] = []
    try:
        elements = card.find_elements(By.CSS_SELECTOR, ".a-text-price .a-offscreen")
    except Exception:
        elements = []
    for element in elements:
        value = parse_brl(element.get_attribute("textContent") or element.text or "")
        if value and (not current or value > current * 1.03):
            originals.append(value)
    original = max(originals) if originals else None
    return title[:300] if title else None, current, original


def _amazon_pdp_prices(driver) -> list[float]:
    selectors = (
        "#corePrice_feature_div .a-price .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#apex_desktop .a-price .a-offscreen",
        "#price_inside_buybox",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
    )
    values: list[float] = []
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for element in elements:
            value = parse_brl(element.get_attribute("textContent") or element.text or "")
            if value and value not in values:
                values.append(value)
    return values


def selected_queries(slot: int) -> list[str]:
    if not ROTATING_QUERIES:
        return list(FIXED_QUERIES)
    start = (slot * 4) % len(ROTATING_QUERIES)
    rotating = [ROTATING_QUERIES[(start + i) % len(ROTATING_QUERIES)] for i in range(4)]
    return list(dict.fromkeys([*FIXED_QUERIES, *rotating]))


def scan_source(name: str, cfg: dict, queries: list[str]) -> tuple[list[dict], dict]:
    driver = None
    rows: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()
    try:
        driver = build_driver()
        driver.set_page_load_timeout(30)
        for query in queries:
            try:
                driver.get(cfg["search"](query))
                time.sleep(2.0)
                for _ in range(2):
                    driver.execute_script("window.scrollBy(0, 1500)")
                    time.sleep(0.35)
                for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
                    href = anchor.get_attribute("href") or ""
                    if not _same_domain(href, cfg["host"]) or not cfg["product"].search(urlparse(href).path):
                        continue
                    href = _canon(href)
                    if href in seen:
                        continue
                    text = _card_text(driver, anchor)
                    if name == "Amazon Brasil":
                        amz_title, current, original = _amazon_card(anchor)
                        title = amz_title or _title(anchor, text)
                        if current is None:
                            prices = extract_brl_prices(text)
                            current, original = pick_current_and_original(prices)
                    else:
                        if "R$" not in text:
                            continue
                        prices = extract_brl_prices(text)
                        current, original = pick_current_and_original(prices)
                        title = _title(anchor, text)
                    if not current or not title or not _query_relevant(query, title):
                        continue
                    score = score_product(title=title, price=current, original_price=original, source=name)
                    if int(score.get("bug_score", 0)) < 55:
                        continue
                    seen.add(href)
                    rows.append({
                        "source": name,
                        "store_name": name,
                        "title": title,
                        "price": round(float(current), 2),
                        "original_price": round(float(original), 2) if original else None,
                        "url": href,
                        "search_query": query,
                        "available": True,
                        "trusted": False,
                        "revalidated": False,
                        "collector": "fast-market-scan",
                        **score,
                    })
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{query}: {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"navegador: {type(exc).__name__}: {exc}")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    rows.sort(key=lambda x: (-int(x.get("bug_score", 0)), float(x.get("price", 0))))
    returned = rows[:35]
    return returned, {
        "ok": not bool(errors) or bool(returned),
        "items": len(returned),
        "candidates_seen": len(rows),
        "message": "scanner rápido" if returned else ("; ".join(errors[:4]) or "nenhum candidato extremo nesta rodada"),
        "errors": errors[:8],
    }


def scan_markets(slot: int, workers: int = 4) -> tuple[list[dict], dict[str, dict]]:
    queries = selected_queries(slot)
    all_rows: list[dict] = []
    health: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(SOURCES)))) as pool:
        futures = {pool.submit(scan_source, name, cfg, queries): name for name, cfg in SOURCES.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                rows, status = future.result()
            except Exception as exc:  # noqa: BLE001
                rows, status = [], {"ok": False, "items": 0, "message": f"{type(exc).__name__}: {exc}"}
            all_rows.extend(rows)
            health[name] = status
    return all_rows, health


def revalidate_candidate(row: dict) -> tuple[dict, str | None]:
    cfg = SOURCES.get(str(row.get("source")))
    if not cfg:
        return row, "fonte sem revalidador"
    driver = None
    try:
        driver = build_driver()
        driver.set_page_load_timeout(30)
        driver.get(str(row.get("url")))
        time.sleep(2.3)
        body = driver.find_element(By.TAG_NAME, "body").text
        low = " ".join(body.lower().split())
        if any(x in low for x in ("produto indisponível", "produto indisponivel", "esgotado", "anúncio pausado", "anuncio pausado")):
            row["available"] = False
            return row, "produto indisponível na rechecagem"
        if str(row.get("source")) == "Amazon Brasil":
            prices = _amazon_pdp_prices(driver)
        else:
            prices = extract_brl_prices(body)
        current = float(row.get("price") or 0)
        if not any(similar_price(p, current, 0.05) for p in prices):
            return row, "preço não apareceu novamente na página"
        trusted = any(marker in low for marker in cfg.get("trust", ()))
        row["trusted"] = bool(trusted)
        row["revalidated"] = True
        rescored = score_product(
            title=str(row.get("title") or ""),
            price=current,
            original_price=row.get("original_price"),
            source=str(row.get("source") or ""),
            trusted=bool(trusted),
            revalidated=True,
        )
        row.update(rescored)
        row["verification_note"] = "preço confirmado" + ("; sinal de vendedor confiável" if trusted else "; vendedor precisa conferência manual")
        return row, None
    except Exception as exc:  # noqa: BLE001
        return row, f"{type(exc).__name__}: {exc}"
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def scan_stamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
