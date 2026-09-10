from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin


BRL_RE = re.compile(r"R\$\s*([\d.]+(?:,\d{2})?)", re.I)
INSTALLMENT_RE = re.compile(r"(?:\d+\s*x(?:\s+de)?\s*)$", re.I)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_brl(value: str) -> float | None:
    if not value:
        return None
    raw = value.replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        amount = float(raw)
    except ValueError:
        return None
    return amount if amount > 0 else None


def extract_brl_prices(text: str) -> list[float]:
    """Extrai preços à vista e ignora valores de parcelas do tipo 10x R$ 299,90."""
    out: list[float] = []
    for match in BRL_RE.finditer(text or ""):
        prefix = (text[max(0, match.start() - 28) : match.start()]).lower()
        if INSTALLMENT_RE.search(prefix.strip()) or re.search(r"\d+\s*x\s*(?:de\s*)?$", prefix):
            continue
        price = parse_brl(match.group(1))
        if price is not None:
            out.append(price)
    return out


def pick_current_and_original(prices: list[float]) -> tuple[float | None, float | None]:
    if not prices:
        return None, None
    current = min(prices)
    original = max(prices) if len(prices) > 1 and max(prices) > current * 1.03 else None
    return current, original


def absolute_url(base: str, href: str) -> str:
    return urljoin(base, href)


def similar_price(a: float, b: float, tolerance: float = 0.03) -> bool:
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(a, b) <= tolerance
