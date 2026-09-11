from __future__ import annotations

import json
import math
import re
import statistics
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .bug_rules import score_product
from .utils import extract_brl_prices, pick_current_and_original


ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "price-monitor" / "data" / "terabyte-state.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "terabyte-live.json"

BASE = "https://www.terabyteshop.com.br"
SITEMAPS = (
    f"{BASE}/sitemap-manus.xml",
    f"{BASE}/sitemap.xml",
)

HOT_PAGES = (
    (f"{BASE}/", "Home"),
    (f"{BASE}/promocoes", "Promoções"),
    (f"{BASE}/open-box", "Open Box"),
    (f"{BASE}/hardware/", "Hardware"),
    (f"{BASE}/pc-gamer/", "PC Gamer"),
    (f"{BASE}/kit-upgrade/", "Kit Upgrade"),
)

ROOT_CATEGORY_PATHS = (
    "/hardware/",
    "/pc-gamer/",
    "/perifericos/",
    "/monitores/",
    "/notebooks/",
    "/smartphones/",
    "/gabinetes/",
    "/refrigeracao/",
    "/fontes/",
    "/cadeira/",
    "/mesa-gamer/",
    "/kit-upgrade/",
    "/redes-e-wireless/",
    "/espaco-gamer/",
    "/games",
)

CATEGORY_PREFIXES = tuple(p.rstrip("/") for p in ROOT_CATEGORY_PATHS)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0 Safari/537.36"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    s.mount("https://", HTTPAdapter(max_retries=retry, pool_connections=24, pool_maxsize=24))
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.6",
            "Cache-Control": "no-cache",
        }
    )
    return s


def canonical(url: str) -> str:
    try:
        p = urlparse(url)
        return urlunparse((p.scheme or "https", p.netloc.lower(), p.path.rstrip("/"), "", "", ""))
    except Exception:
        return url


def is_product_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.netloc.lower().endswith("terabyteshop.com.br") and p.path.lower().startswith("/produto/")
    except Exception:
        return False


def is_category_url(url: str) -> bool:
    try:
        p = urlparse(url)
        if not p.netloc.lower().endswith("terabyteshop.com.br"):
            return False
        path = p.path.rstrip("/").lower()
        if path in ("", "/promocoes", "/open-box"):
            return True
        return any(path == prefix or path.startswith(prefix + "/") for prefix in CATEGORY_PREFIXES)
    except Exception:
        return False


def fetch_text(s: requests.Session, url: str, timeout: int = 20) -> str:
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    ctype = r.headers.get("content-type", "").lower()
    if "text" not in ctype and "xml" not in ctype:
        raise ValueError(f"conteúdo inesperado: {ctype}")
    return r.text


def _title_from_anchor(anchor, text: str) -> str:
    for attr in ("title", "aria-label"):
        value = (anchor.get(attr) or "").strip()
        if len(value) >= 12 and "R$" not in value:
            return re.sub(r"\s+", " ", value)[:320]
    own = " ".join(anchor.stripped_strings).strip()
    if len(own) >= 12 and "R$" not in own:
        return re.sub(r"\s+", " ", own)[:320]
    lines = [x.strip() for x in re.split(r"[\r\n]+", text) if x.strip()]
    candidates = [
        x for x in lines
        if len(x) >= 12
        and "R$" not in x
        and not re.fullmatch(r"[\d\s.,%xX+-]+", x)
        and not x.lower().startswith(("frete", "off", "independ", "termina em", "de:"))
    ]
    return max(candidates, key=len)[:320] if candidates else ""


def _card_text(anchor) -> str:
    node = anchor
    best = ""
    for _ in range(7):
        node = node.parent
        if node is None:
            break
        text = node.get_text("\n", strip=True)
        if "R$" in text and len(text) <= 2600:
            best = text
            if len(text) >= 40:
                break
    return best


def extract_products(html: str, page_url: str, page_label: str = "") -> list[dict]:
    soup = BeautifulSoup(html or "", "html.parser")
    out: dict[str, dict] = {}
    for anchor in soup.select('a[href*="/produto/"]'):
        href = canonical(urljoin(page_url, anchor.get("href") or ""))
        if not is_product_url(href):
            continue
        card_text = _card_text(anchor)
        if "R$" not in card_text:
            continue
        prices = extract_brl_prices(card_text)
        current, original = pick_current_and_original(prices)
        title = _title_from_anchor(anchor, card_text)
        if not current or not title:
            continue
        item = {
            "url": href,
            "title": title,
            "price": round(float(current), 2),
            "original_price": round(float(original), 2) if original else None,
            "page": page_label or urlparse(page_url).path or "Home",
            "source": "TerabyteShop",
        }
        previous = out.get(href)
        if previous is None or item["price"] < previous["price"]:
            out[href] = item
    return list(out.values())


def discover_category_urls(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    urls = set()
    for a in soup.select("a[href]"):
        href = canonical(urljoin(BASE, a.get("href") or ""))
        if is_category_url(href) and not is_product_url(href):
            urls.add(href)
    return sorted(urls)


def _xml_locs(xml_text: str) -> tuple[str, list[str]]:
    root = ET.fromstring(xml_text)
    tag = root.tag.split("}")[-1].lower()
    locs = []
    for el in root.iter():
        if el.tag.split("}")[-1].lower() == "loc" and el.text:
            locs.append(el.text.strip())
    return tag, locs


def discover_catalog_urls(s: requests.Session, max_urls: int = 12000, max_sitemaps: int = 30) -> list[str]:
    queue = list(SITEMAPS)
    seen_maps: set[str] = set()
    products: set[str] = set()
    while queue and len(seen_maps) < max_sitemaps and len(products) < max_urls:
        url = queue.pop(0)
        if url in seen_maps:
            continue
        seen_maps.add(url)
        try:
            text = fetch_text(s, url, timeout=28)
            kind, locs = _xml_locs(text)
        except Exception:
            continue
        if kind == "sitemapindex":
            for loc in locs:
                if loc not in seen_maps and len(queue) < max_sitemaps * 2:
                    queue.append(loc)
        else:
            for loc in locs:
                if is_product_url(loc):
                    products.add(canonical(loc))
                    if len(products) >= max_urls:
                        break
    return sorted(products)


def fetch_listing_page(url: str, label: str) -> tuple[list[dict], dict]:
    s = session()
    started = time.time()
    try:
        html = fetch_text(s, url)
        rows = extract_products(html, url, label)
        return rows, {
            "url": url,
            "label": label,
            "ok": True,
            "items": len(rows),
            "ms": int((time.time() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        return [], {
            "url": url,
            "label": label,
            "ok": False,
            "items": 0,
            "message": f"{type(exc).__name__}: {exc}",
            "ms": int((time.time() - started) * 1000),
        }


def extract_product_page(html: str, url: str) -> dict | None:
    soup = BeautifulSoup(html or "", "html.parser")
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = " ".join(h1.stripped_strings)
    if not title:
        title = (soup.title.get_text(" ", strip=True) if soup.title else "").split("|")[0].strip()
    body = soup.get_text("\n", strip=True)
    prices = extract_brl_prices(body[:18000])
    current, original = pick_current_and_original(prices)
    if not title or not current:
        return None
    return {
        "url": canonical(url),
        "title": re.sub(r"\s+", " ", title)[:320],
        "price": round(float(current), 2),
        "original_price": round(float(original), 2) if original else None,
        "page": "Catálogo rotativo",
        "source": "TerabyteShop",
    }


def fetch_product_page(url: str) -> tuple[dict | None, str | None]:
    s = session()
    try:
        html = fetch_text(s, url, timeout=18)
        return extract_product_page(html, url), None
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _median(values: list[float]) -> float | None:
    vals = [float(x) for x in values if x and float(x) > 0]
    return round(float(statistics.median(vals)), 2) if vals else None


def _pct_drop(price: float, baseline: float | None) -> float:
    if not baseline or baseline <= price:
        return 0.0
    return round((baseline - price) / baseline * 100.0, 1)


def compute_live_score(row: dict, state_item: dict | None) -> dict:
    price = float(row.get("price") or 0)
    previous_price = float(state_item.get("last_price") or 0) if state_item else 0.0
    history_values = []
    if state_item:
        history_values = [float(x.get("price") or 0) for x in state_item.get("observations", []) if float(x.get("price") or 0) > 0]
    baseline = _median(history_values[-32:]) if len(history_values) >= 2 else None
    history_drop = _pct_drop(price, baseline)
    sudden_drop = _pct_drop(price, previous_price)
    original = row.get("original_price")
    advertised_drop = _pct_drop(price, float(original)) if original else 0.0

    generic = score_product(
        title=str(row.get("title") or ""),
        price=price,
        reference_price=baseline,
        original_price=original,
        source="TerabyteShop",
    )
    score = int(generic.get("bug_score", 0))
    reasons = list(generic.get("reasons") or [])

    if sudden_drop >= 50:
        score = max(score, 98)
        reasons.insert(0, f"queda de {sudden_drop:.0f}% desde a última varredura")
    elif sudden_drop >= 35:
        score = max(score, 90)
        reasons.insert(0, f"queda de {sudden_drop:.0f}% desde a última varredura")
    elif sudden_drop >= 25:
        score = max(score, 82)
        reasons.insert(0, f"queda de {sudden_drop:.0f}% desde a última varredura")
    elif sudden_drop >= 15:
        score = max(score, 72)
        reasons.insert(0, f"queda de {sudden_drop:.0f}% desde a última varredura")
    elif sudden_drop >= 8:
        score = max(score, 62)
        reasons.insert(0, f"queda recente de {sudden_drop:.0f}%")

    if len(history_values) >= 3:
        if history_drop >= 50:
            score = max(score, 96)
        elif history_drop >= 35:
            score = max(score, 88)
        elif history_drop >= 25:
            score = max(score, 78)
        elif history_drop >= 15:
            score = max(score, 68)
        if history_drop >= 10:
            reasons.append(f"{history_drop:.0f}% abaixo da mediana histórica")

    if advertised_drop >= 60:
        score = max(score, 74)
        reasons.append(f"{advertised_drop:.0f}% abaixo do preço anterior anunciado")
    elif advertised_drop >= 45:
        score = max(score, 64)

    score = max(0, min(100, score))
    if score >= 90:
        status = "🚨 ALERTA TERABYTE"
    elif score >= 80:
        status = "🔥 QUEDA FORTE"
    elif score >= 70:
        status = "⚡ PREÇO MUITO BAIXO"
    elif score >= 60:
        status = "🟢 ABAIXO DO NORMAL"
    else:
        status = "OBSERVADO"

    return {
        "score": score,
        "status": status,
        "baseline_price": baseline,
        "history_count": len(history_values),
        "history_drop_pct": history_drop,
        "sudden_drop_pct": sudden_drop,
        "advertised_drop_pct": advertised_drop,
        "previous_price": round(previous_price, 2) if previous_price else None,
        "reasons": list(dict.fromkeys(reasons))[:4],
        "category": generic.get("category"),
        "category_rule": generic.get("category_rule"),
    }


def merge_observation(state: dict, row: dict, now_iso: str) -> dict:
    key = canonical(str(row["url"]))
    item = state.setdefault("items", {}).get(key, {})
    scored = compute_live_score(row, item)
    observations = list(item.get("observations", []))
    current = float(row["price"])
    if not observations or float(observations[-1].get("price") or 0) != current:
        observations.append({"at": now_iso, "price": current})
    elif observations:
        observations[-1]["at"] = now_iso
    observations = observations[-40:]

    first_seen = item.get("first_seen") or now_iso
    payload = {
        **row,
        **scored,
        "first_seen": first_seen,
        "last_seen": now_iso,
        "last_price": current,
        "lowest_seen": round(min([current, *[float(x.get("price") or current) for x in observations]]), 2),
        "observations": observations,
    }
    state["items"][key] = payload
    return payload


def cleanup_state(state: dict, now: datetime) -> None:
    cutoff = now - timedelta(days=14)
    for key, row in list(state.get("items", {}).items()):
        try:
            stamp = datetime.fromisoformat(str(row.get("last_seen") or "").replace("Z", "+00:00"))
        except ValueError:
            state["items"].pop(key, None)
            continue
        if stamp < cutoff:
            state["items"].pop(key, None)


def main() -> int:
    now = utc_now()
    now_iso = iso(now)
    state = load_json(
        STATE_PATH,
        {
            "version": "0.1.0",
            "run_counter": 0,
            "category_cursor": 0,
            "catalog_cursor": 0,
            "category_urls": [],
            "catalog_urls": [],
            "items": {},
        },
    )
    state.setdefault("items", {})
    run_counter = int(state.get("run_counter", 0))

    s = session()
    try:
        home_html = fetch_text(s, BASE + "/")
        discovered_categories = discover_category_urls(home_html)
    except Exception:
        discovered_categories = []

    category_urls = sorted(set(state.get("category_urls", [])) | set(discovered_categories) | {BASE + p for p in ROOT_CATEGORY_PATHS})
    state["category_urls"] = category_urls[:500]

    if not state.get("catalog_urls") or run_counter % 12 == 0:
        catalog = discover_catalog_urls(s)
        if catalog:
            state["catalog_urls"] = catalog
            state["catalog_refreshed_at"] = now_iso

    listing_targets: list[tuple[str, str]] = list(HOT_PAGES)
    hot_urls = {x[0] for x in HOT_PAGES}
    rotating = [u for u in state.get("category_urls", []) if u not in hot_urls]
    if rotating:
        cursor = int(state.get("category_cursor", 0)) % len(rotating)
        batch = [rotating[(cursor + i) % len(rotating)] for i in range(min(18, len(rotating)))]
        state["category_cursor"] = (cursor + len(batch)) % len(rotating)
        listing_targets.extend((u, "Categoria rotativa") for u in batch)

    listing_rows: list[dict] = []
    page_health: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(fetch_listing_page, url, label): (url, label) for url, label in listing_targets}
        for future in as_completed(futures):
            rows, health = future.result()
            listing_rows.extend(rows)
            page_health.append(health)

    catalog_urls = list(state.get("catalog_urls", []))
    catalog_rows: list[dict] = []
    catalog_errors = 0
    if catalog_urls:
        cursor = int(state.get("catalog_cursor", 0)) % len(catalog_urls)
        batch_size = min(48, len(catalog_urls))
        batch_urls = [catalog_urls[(cursor + i) % len(catalog_urls)] for i in range(batch_size)]
        state["catalog_cursor"] = (cursor + batch_size) % len(catalog_urls)
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = {pool.submit(fetch_product_page, url): url for url in batch_urls}
            for future in as_completed(futures):
                row, error = future.result()
                if row:
                    catalog_rows.append(row)
                elif error:
                    catalog_errors += 1

    priority = {"Home": 5, "Promoções": 5, "Open Box": 5, "Hardware": 4, "PC Gamer": 4, "Kit Upgrade": 4, "Categoria rotativa": 2, "Catálogo rotativo": 1}
    best: dict[str, dict] = {}
    for row in [*listing_rows, *catalog_rows]:
        key = canonical(str(row["url"]))
        old = best.get(key)
        if old is None or float(row["price"]) < float(old["price"]) or priority.get(row.get("page"), 0) > priority.get(old.get("page"), 0):
            best[key] = row

    observed: list[dict] = []
    for row in best.values():
        observed.append(merge_observation(state, row, now_iso))

    cleanup_state(state, now)

    active = []
    recent_cutoff = now - timedelta(hours=6)
    for row in state.get("items", {}).values():
        try:
            seen = datetime.fromisoformat(str(row.get("last_seen") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if seen < recent_cutoff:
            continue
        if int(row.get("score", 0)) >= 55 or float(row.get("sudden_drop_pct", 0)) >= 5 or float(row.get("history_drop_pct", 0)) >= 10:
            active.append({k: v for k, v in row.items() if k != "observations"})

    active.sort(
        key=lambda x: (
            -int(x.get("score", 0)),
            -float(x.get("sudden_drop_pct", 0)),
            -float(x.get("history_drop_pct", 0)),
            float(x.get("price", math.inf)),
        )
    )

    state["run_counter"] = run_counter + 1
    state["last_run"] = now_iso
    state["last_observed_count"] = len(observed)

    output = {
        "version": "0.1.0",
        "generated_at": now_iso,
        "scan_interval_minutes": 5,
        "strategy": "hot-pages-e-catalogo-rotativo",
        "observed_this_run": len(observed),
        "listing_pages_scanned": len(listing_targets),
        "listing_pages_ok": sum(1 for x in page_health if x.get("ok")),
        "catalog_batch_size": min(48, len(catalog_urls)) if catalog_urls else 0,
        "catalog_errors": catalog_errors,
        "catalog_total": len(catalog_urls),
        "catalog_cursor": int(state.get("catalog_cursor", 0)),
        "tracked_products": len(state.get("items", {})),
        "active_count": len(active),
        "strong_count": sum(1 for x in active if int(x.get("score", 0)) >= 70),
        "critical_count": sum(1 for x in active if int(x.get("score", 0)) >= 90),
        "sudden_drop_count": sum(1 for x in active if float(x.get("sudden_drop_pct", 0)) >= 15),
        "page_health": sorted(page_health, key=lambda x: (not x.get("ok"), x.get("label", ""))),
        "deals": active[:250],
    }
    save_json(STATE_PATH, state)
    save_json(OUTPUT_PATH, output)
    print(
        f"Terabyte Live: {len(observed)} produtos observados; "
        f"{output['strong_count']} alertas 70+; {output['critical_count']} críticos; "
        f"{output['listing_pages_ok']}/{len(listing_targets)} páginas OK; "
        f"catálogo {output['catalog_cursor']}/{output['catalog_total']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
