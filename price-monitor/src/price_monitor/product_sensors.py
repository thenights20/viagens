from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


LA_PROMOTION_URL = "https://t.me/s/LaPromotion"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}


def _parse_brl(text: str) -> float | None:
    patterns = [
        r"Pre[cç]o\s*:\s*R\$\s*([0-9.]+(?:,[0-9]{1,2})?)",
        r"(?:^|\s)-?\s*R\$\s*([0-9.]+(?:,[0-9]{1,2})?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I | re.M)
        if not m:
            continue
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            return round(float(raw), 2)
        except ValueError:
            pass
    return None


def _coupon(text: str) -> str | None:
    m = re.search(r"Cupom\s*:\s*[`'\"]?([A-Z0-9_-]{4,24})", text, re.I)
    if m:
        return m.group(1).upper()
    # Alguns posts de cupom não usam "Cupom:" antes do código.
    if "cupom" in text.lower():
        codes = re.findall(r"`([A-Z0-9_-]{4,24})`", text, re.I)
        if codes:
            return codes[0].upper()
    return None


def _store_for_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "amazon.com.br" in host or "amzn.to" in host:
        return "Amazon Brasil"
    if "mercadolivre" in host or "meli.la" in host:
        return "Mercado Livre"
    if "shopee" in host:
        return "Shopee"
    if "magazineluiza" in host or "magalu" in host:
        return "Magalu"
    if "kabum" in host:
        return "KaBuM!"
    if "pichau" in host:
        return "Pichau"
    if "terabyte" in host:
        return "TerabyteShop"
    if "casasbahia" in host:
        return "Casas Bahia"
    if "tidd.ly" in host:
        return "Awin / link afiliado"
    if "lapromotion.com.br" in host:
        return "La Promotion / redirecionador"
    return host or "link externo"


def _product_link(links: list[str]) -> str | None:
    blocked = ("t.me/", "telegram.org/", "lapromotion.com.br/grupos")
    candidates = [u for u in links if u.startswith("http") and not any(x in u for x in blocked)]
    if not candidates:
        return None
    # Prefere links de produto/resgate e deixa o redirecionador próprio como fallback.
    direct = [u for u in candidates if any(x in u for x in ("amazon.com.br", "mercadolivre", "meli.la", "shopee", "magazineluiza", "magalu", "kabum", "pichau", "terabyte", "casasbahia", "tidd.ly"))]
    return (direct or candidates)[-1]


def _title_from_text(text: str) -> str:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    for line in lines:
        low = line.lower()
        if low.startswith(("preço", "preco", "cupom", "resgate", "link ", "frete", "⭐", "🎟", "🛒")):
            continue
        line = re.sub(r"^[🔥⚠️🚨\s]+", "", line).strip()
        line = re.sub(r"^BUG\s*[-:]?\s*", "", line, flags=re.I).strip()
        if len(line) >= 8:
            return line[:300]
    return lines[0][:300] if lines else "Oferta"


def collect_la_promotion(timeout: int = 20) -> tuple[list[dict], dict]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        response = requests.get(LA_PROMOTION_URL, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return [], {"ok": False, "items": 0, "message": f"{type(exc).__name__}: {exc}", "url": LA_PROMOTION_URL}

    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[dict] = []
    seen: set[str] = set()
    for message in soup.select("div.tgme_widget_message"):
        text_el = message.select_one("div.tgme_widget_message_text")
        if not text_el:
            continue
        text = "\n".join(x.strip() for x in text_el.stripped_strings if x.strip())
        if not text:
            continue
        links = [str(a.get("href") or "") for a in text_el.select("a[href]")]
        post_id = str(message.get("data-post") or "")
        post_url = f"https://t.me/{post_id}" if post_id else LA_PROMOTION_URL
        product_url = _product_link(links)
        key = post_url + "|" + text[:120]
        if key in seen:
            continue
        seen.add(key)
        price = _parse_brl(text)
        coupon = _coupon(text)
        is_coupon_only = price is None and "cupom" in text.lower()
        is_bug = bool(re.search(r"\bBUG\b", text, re.I))
        time_el = message.select_one("time[datetime]")
        published_at = str(time_el.get("datetime")) if time_el else None
        rows.append({
            "source": "La Promotion",
            "title": _title_from_text(text),
            "text": text[:1800],
            "price": price,
            "currency": "BRL" if price is not None else None,
            "coupon": coupon,
            "kind": "coupon" if is_coupon_only else "product",
            "external_bug": is_bug,
            "url": product_url or post_url,
            "post_url": post_url,
            "store_hint": _store_for_url(product_url or ""),
            "published_at": published_at,
            "collected_at": now,
        })

    return rows, {
        "ok": True,
        "items": len(rows),
        "status": response.status_code,
        "message": "página pública do Telegram lida com sucesso",
        "url": LA_PROMOTION_URL,
    }


def build_sensor_feed() -> dict:
    rows, health = collect_la_promotion()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "version": "0.1.0",
        "generated_at": now,
        "sources": {"La Promotion": health},
        "signal_count": len(rows),
        "product_count": sum(1 for x in rows if x.get("kind") == "product"),
        "coupon_count": sum(1 for x in rows if x.get("kind") == "coupon" or x.get("coupon")),
        "bug_marked_count": sum(1 for x in rows if x.get("external_bug")),
        "signals": rows,
    }
