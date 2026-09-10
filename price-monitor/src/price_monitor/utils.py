from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin


BRL_RE = re.compile(r"R\$\s*([\d.]+(?:,\d{2})?)", re.I)


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


def _is_auxiliary_money_value(text: str, start: int, end: int) -> bool:
    """Detecta valores monetários que não são o preço total do produto.

    Exemplos descartados: parcela, economia, desconto, cashback, cupom e frete.
    Isso evita interpretar `Economize R$ 255,92` como se o item custasse R$ 255,92.
    """
    prefix_raw = text[max(0, start - 55) : start]
    suffix_raw = text[end : min(len(text), end + 45)]
    prefix = normalize_text(prefix_raw)
    suffix = normalize_text(suffix_raw)

    prefix_patterns = (
        r"(?:^| )\d{1,2}\s*x(?:\s+de)?$",
        r"(?:^| )(?:parcela|parcelas)(?:\s+de)?$",
        r"(?:^| )(?:economize|economia|poupe)(?:\s+de)?$",
        r"(?:^| )(?:desconto|cashback|cupom|bonus|bônus|ganhe)(?:\s+de)?$",
        r"(?:^| )frete(?:\s+por)?$",
    )
    if any(re.search(pattern, prefix, re.I) for pattern in prefix_patterns):
        return True

    # Também cobre textos como `R$ 200 de desconto`.
    if re.match(r"^(?:de\s+)?(?:desconto|cashback|economia|economize|bonus|cupom)\b", suffix, re.I):
        return True

    return False


def extract_brl_prices(text: str) -> list[float]:
    """Extrai preços totais e ignora parcelas/benefícios monetários auxiliares."""
    text = text or ""
    out: list[float] = []
    for match in BRL_RE.finditer(text):
        if _is_auxiliary_money_value(text, match.start(), match.end()):
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
