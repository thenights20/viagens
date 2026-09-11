from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import quote, quote_plus, urlparse, urlunparse

from selenium.webdriver.common.by import By

from .browser import build_driver
from .bug_rules import score_product
from .utils import extract_brl_prices, pick_current_and_original, similar_price


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
                    if "R$" not in text:
                        continue
                    prices = extract_brl_prices(text)
                    current, original = pick_current_and_original(prices)
                    title = _title(anchor, text)
                    if not current or not title:
                        continue
                    score = score_product(title=title, price=current, original_price=original, source=name)
                    # O scanner rápido guarda apenas candidatos; preços comuns não justificam abrir PDP.
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
    return rows[:35], {
        "ok": not bool(errors) or bool(rows),
        "items": len(rows),
        "message": "scanner rápido" if rows else ("; ".join(errors[:4]) or "nenhum candidato extremo nesta rodada"),
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
