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
    """Detecta valores monetários que não representam o preço total do item.

    Descarta parcelas, economia, desconto, cashback, cupom, bônus e frete.
    Sites brasileiros frequentemente juntam texto sem espaços, por exemplo
    `R$ 3.999,00 em10x de R$ 399,90`; por isso a detecção usa também o trecho
    bruto imediatamente antes do valor.
    """
    prefix_raw = text[max(0, start - 90) : start].replace("\xa0", " ").lower()
    suffix_raw = text[end : min(len(text), end + 60)].replace("\xa0", " ").lower()
    prefix_compact = re.sub(r"\s+", " ", prefix_raw).strip()
    suffix_compact = re.sub(r"\s+", " ", suffix_raw).strip()
    prefix = normalize_text(prefix_raw)
    suffix = normalize_text(suffix_raw)

    # Parcelas: 10x R$, 10x de R$, em 10x de R$, em10x de R$.
    installment_patterns_raw = (
        r"(?:^|\s|em)\d{1,2}\s*x\s*(?:de\s*)?$",
        r"(?:^|\s)em\s*\d{1,2}\s*x\s*(?:de\s*)?$",
        r"(?:^|\s)(?:parcela|parcelas)\s*(?:de\s*)?$",
        r"(?:^|\s)(?:a partir de\s+)?\d{1,2}\s*x\s*(?:de\s*)?$",
    )
    if any(re.search(pattern, prefix_compact, re.I) for pattern in installment_patterns_raw):
        return True

    # Forma normalizada, útil quando pontuação/quebras de linha variam.
    installment_patterns_norm = (
        r"(?:^| )em\s*\d{1,2}\s*x(?:\s+de)?$",
        r"(?:^| )em\d{1,2}\s*x(?:\s+de)?$",
        r"(?:^| )\d{1,2}\s*x(?:\s+de)?$",
        r"(?:^| )(?:parcela|parcelas)(?:\s+de)?$",
    )
    if any(re.search(pattern, prefix, re.I) for pattern in installment_patterns_norm):
        return True

    auxiliary_prefix_patterns = (
        r"(?:^| )(?:economize|economia|poupe)(?:\s+de)?$",
        r"(?:^| )(?:desconto|cashback|cupom|bonus|ganhe)(?:\s+de)?$",
        r"(?:^| )frete(?:\s+por)?$",
        r"(?:^| )(?:vale|credito|crédito)(?:\s+de)?$",
    )
    if any(re.search(pattern, prefix, re.I) for pattern in auxiliary_prefix_patterns):
        return True

    # Também cobre `R$ 200 de desconto`, `R$ 50 cashback` etc.
    if re.match(
        r"^(?:de\s+)?(?:desconto|cashback|economia|economize|bonus|cupom|frete|credito)\b",
        suffix,
        re.I,
    ):
        return True

    # Defesa extra: valor seguido de "sem juros" normalmente é parcela quando
    # há um Nx próximo antes dele, mesmo se o HTML tiver colado palavras.
    if re.match(r"^sem\s+juros\b", suffix_compact, re.I):
        nearby = re.sub(r"\s+", " ", prefix_raw[-45:])
        if re.search(r"\d{1,2}\s*x(?:\s+de)?\s*$", nearby, re.I):
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
