from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceRule:
    name: str
    pattern: re.Pattern[str]
    conservative_floor: float
    category: str


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return " ".join(value.lower().split())


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.I)


# Pisos deliberadamente conservadores. Eles não tentam estimar o preço normal exato;
# servem apenas para reconhecer valores tão baixos que merecem rechecagem imediata.
RULES = [
    PriceRule("RTX 5090", _rx(r"rtx\s*5090", r"geforce\s*5090"), 8500, "Placas de vídeo"),
    PriceRule("RTX 5080", _rx(r"rtx\s*5080"), 6000, "Placas de vídeo"),
    PriceRule("RTX 5070 Ti", _rx(r"rtx\s*5070\s*ti"), 3800, "Placas de vídeo"),
    PriceRule("RTX 5070", _rx(r"rtx\s*5070"), 2900, "Placas de vídeo"),
    PriceRule("RTX 5060 Ti", _rx(r"rtx\s*5060\s*ti"), 2200, "Placas de vídeo"),
    PriceRule("Notebook gamer premium", _rx(r"notebook.*(rtx\s*4070|rtx\s*5070|i9[- ]?14900hx|rog\s*strix|predator\s*helios)"), 5000, "Notebooks"),
    PriceRule("Notebook gamer", _rx(r"notebook\s*gamer", r"nitro\s*v15", r"rog\s*strix", r"predator"), 2800, "Notebooks"),
    PriceRule("PlayStation 5", _rx(r"playstation\s*5", r"ps5"), 2400, "Consoles"),
    PriceRule("Xbox Series X", _rx(r"xbox\s*series\s*x"), 2500, "Consoles"),
    PriceRule("Nintendo Switch 2", _rx(r"nintendo\s*switch\s*2"), 2200, "Consoles"),
    PriceRule("iPhone 17 Pro/Max", _rx(r"iphone\s*17.*(pro|max)"), 5200, "Smartphones"),
    PriceRule("iPhone 17", _rx(r"iphone\s*17"), 3800, "Smartphones"),
    PriceRule("iPhone 16 Pro/Max", _rx(r"iphone\s*16.*(pro|max)"), 4200, "Smartphones"),
    PriceRule("Galaxy S Ultra", _rx(r"galaxy\s*s\d+\s*ultra"), 3000, "Smartphones"),
    PriceRule("TV 65 polegadas", _rx(r"(smart\s*)?tv.*65\s*(polegadas|\"|pol)", r"65.*(qled|oled|uhd|4k)"), 1800, "TVs"),
    PriceRule("TV 55 polegadas", _rx(r"(smart\s*)?tv.*55\s*(polegadas|\"|pol)", r"55.*(qled|oled|uhd|4k)"), 1400, "TVs"),
    PriceRule("TV 50 polegadas", _rx(r"(smart\s*)?tv.*(49|50)\s*(polegadas|\"|pol)", r"(49|50).*(qled|oled|uhd|4k|fhd)"), 1000, "TVs"),
    PriceRule("Micro-ondas", _rx(r"micro[- ]?ondas"), 320, "Eletrodomésticos"),
    PriceRule("Air Fryer 5L", _rx(r"air\s*fryer.*5\s*l", r"fritadeira.*5\s*l"), 220, "Eletrodomésticos"),
    PriceRule("Air Fryer", _rx(r"air\s*fryer", r"fritadeira\s*(sem\s*oleo|eletrica)"), 160, "Eletrodomésticos"),
    PriceRule("Geladeira", _rx(r"geladeira", r"refrigerador"), 1400, "Eletrodomésticos"),
    PriceRule("Lava e seca", _rx(r"lava\s*e\s*seca"), 1700, "Eletrodomésticos"),
    PriceRule("Ar-condicionado", _rx(r"ar[- ]?condicionado.*(9000|12000|18000|24000)", r"split.*inverter"), 1000, "Climatização"),
    PriceRule("Monitor gamer", _rx(r"monitor.*(144hz|165hz|180hz|240hz|300hz|oled|mini\s*led)"), 750, "Monitores"),
    PriceRule("SSD NVMe 2TB", _rx(r"ssd.*(2\s*tb|2tb).*(nvme|m\.2)", r"(nvme|m\.2).*2\s*tb"), 650, "Armazenamento"),
    PriceRule("DJI", _rx(r"dji\s*(mini|air|mavic)"), 1600, "Drones e câmeras"),
    PriceRule("JBL Boombox/PartyBox", _rx(r"jbl.*(boombox|partybox)"), 1200, "Áudio"),
    PriceRule("Estante/Painel de TV", _rx(r"estante.*tv", r"painel.*tv"), 220, "Casa"),
]


def matching_rule(title: str) -> PriceRule | None:
    text = _norm(title)
    matches = [rule for rule in RULES if rule.pattern.search(text)]
    return max(matches, key=lambda rule: rule.conservative_floor) if matches else None


def _ratio_points(ratio: float) -> int:
    if ratio <= 0.08:
        return 62
    if ratio <= 0.15:
        return 57
    if ratio <= 0.22:
        return 52
    if ratio <= 0.30:
        return 46
    if ratio <= 0.40:
        return 38
    if ratio <= 0.50:
        return 30
    if ratio <= 0.65:
        return 20
    if ratio <= 0.75:
        return 12
    return 0


def score_product(
    *,
    title: str,
    price: float,
    reference_price: float | None = None,
    original_price: float | None = None,
    source: str = "",
    trusted: bool = False,
    revalidated: bool = False,
    external_bug_signal: bool = False,
) -> dict:
    price = float(price or 0)
    if price <= 0:
        return {"bug_score": 0, "bug_status": "NORMAL", "reasons": []}

    rule = matching_rule(title)
    candidates: list[tuple[str, float, float]] = []
    if rule and rule.conservative_floor > price:
        candidates.append(("piso conservador da categoria", float(rule.conservative_floor), 1.0))
    if reference_price and float(reference_price) > price:
        candidates.append(("histórico/mercado", float(reference_price), 1.0))
    if original_price and float(original_price) > price:
        # Preço riscado pode ser inflado, então vale menos quando é a única referência.
        candidates.append(("preço anterior anunciado", float(original_price), 0.72))

    if not candidates:
        bonus = 18 if external_bug_signal else 0
        return {
            "bug_score": bonus,
            "bug_status": "SINAL EXTERNO" if bonus else "NORMAL",
            "category_rule": rule.name if rule else None,
            "category": rule.category if rule else None,
            "baseline_price": None,
            "baseline_kind": None,
            "drop_pct": 0.0,
            "savings": 0.0,
            "reasons": ["marcado como BUG por sensor externo"] if external_bug_signal else [],
        }

    kind, baseline, confidence_weight = max(candidates, key=lambda item: item[1] * item[2])
    ratio = price / baseline
    drop_pct = max(0.0, (1.0 - ratio) * 100.0)
    score = _ratio_points(ratio)
    reasons = [f"{drop_pct:.0f}% abaixo de {kind}"]

    if rule:
        floor_ratio = price / rule.conservative_floor
        if floor_ratio <= 0.25:
            score += 18
            reasons.append(f"preço muito abaixo do piso conservador de {rule.name}")
        elif floor_ratio <= 0.45:
            score += 10
            reasons.append(f"abaixo do piso conservador de {rule.name}")

    if external_bug_signal:
        score += 10
        reasons.append("também apareceu como BUG em sensor externo")
    if revalidated:
        score += 10
        reasons.append("preço reaberto e confirmado")
    if trusted:
        score += 6
        reasons.append("vendedor/loja com sinal de confiança")

    # Evita que um único preço riscado transforme uma oferta comum em BUG confirmado.
    if kind == "preço anterior anunciado" and not rule and not revalidated:
        score = min(score, 69)

    score = max(0, min(100, int(round(score))))
    if score >= 90:
        status = "🚨 BUG PROVÁVEL"
    elif score >= 80:
        status = "🔥🔥 PREÇO FORA DA CURVA"
    elif score >= 70:
        status = "🔥 BUG FORTE"
    elif score >= 60:
        status = "🟢 SUSPEITO"
    else:
        status = "NORMAL"

    return {
        "bug_score": score,
        "bug_status": status,
        "category_rule": rule.name if rule else None,
        "category": rule.category if rule else None,
        "baseline_price": round(baseline, 2),
        "baseline_kind": kind,
        "drop_pct": round(drop_pct, 1),
        "savings": round(baseline - price, 2),
        "reasons": reasons,
    }
