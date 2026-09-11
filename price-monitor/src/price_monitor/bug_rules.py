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
    exclude: tuple[str, ...] = ()
    require_any: tuple[str, ...] = ()


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return " ".join(value.lower().split())


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.I)


CONSOLE_ACCESSORIES = (
    "case", "carrying", "capa", "bolsa", "estojo", "suporte", "base vertical",
    "skin", "pelicula", "thumb grip", "cooler", "dock", "cabo", "carregador",
    "volante", "adaptador", "faceplate",
)
NOTEBOOK_ACCESSORIES = (
    "carregador", "fonte para", "bateria para", "teclado para", "capa para", "case para",
    "cooler para", "suporte para", "tela para", "dobradica", "memoria para",
)
TV_ACCESSORIES = (
    "suporte para tv", "painel para tv", "controle remoto", "capa para tv", "base para tv",
    "pedestal para tv", "placa principal", "placa fonte", "barra de led",
)
APPLIANCE_PARTS = (
    "peca para", "peça para", "reposicao", "reposição", "resistencia", "resistência",
    "cesto", "cesta", "grade", "prato de vidro", "placa de vidro", "porta para",
    "borracha", "gaveta", "prateleira", "filtro para", "motor para", "painel de controle",
)


RULES = [
    PriceRule("RTX 5090", _rx(r"rtx\s*5090", r"geforce\s*5090"), 8500, "Placas de vídeo", ("water block", "backplate", "suporte", "cabo", "fan ")),
    PriceRule("RTX 5080", _rx(r"rtx\s*5080"), 6000, "Placas de vídeo", ("water block", "backplate", "suporte", "cabo", "fan ")),
    PriceRule("RTX 5070 Ti", _rx(r"rtx\s*5070\s*ti"), 3800, "Placas de vídeo", ("water block", "backplate", "suporte", "cabo")),
    PriceRule("RTX 5070", _rx(r"rtx\s*5070"), 2900, "Placas de vídeo", ("water block", "backplate", "suporte", "cabo")),
    PriceRule("RTX 5060 Ti", _rx(r"rtx\s*5060\s*ti"), 2200, "Placas de vídeo", ("water block", "backplate", "suporte", "cabo")),
    PriceRule("Notebook gamer premium", _rx(r"notebook.*(rtx\s*4070|rtx\s*5070|i9[- ]?14900hx|rog\s*strix|predator\s*helios)"), 5000, "Notebooks", NOTEBOOK_ACCESSORIES),
    PriceRule("Notebook gamer", _rx(r"notebook\s*gamer", r"nitro\s*v15", r"rog\s*strix", r"predator"), 2800, "Notebooks", NOTEBOOK_ACCESSORIES),
    PriceRule(
        "PlayStation 5", _rx(r"playstation\s*5", r"ps5"), 2400, "Consoles", CONSOLE_ACCESSORIES,
        ("console", "slim", "825gb", "825 gb", "1tb", "1 tb", "edicao digital", "digital edition", "playstation 5 pro", "ps5 pro"),
    ),
    PriceRule(
        "Xbox Series X", _rx(r"xbox\s*series\s*x"), 2500, "Consoles", CONSOLE_ACCESSORIES,
        ("console", "1tb", "1 tb", "2tb", "2 tb", "digital edition", "special edition"),
    ),
    PriceRule(
        "Nintendo Switch 2", _rx(r"nintendo\s*switch\s*2"), 2200, "Consoles",
        CONSOLE_ACCESSORIES + ("game traveler", "screen protector", "memory card"),
        ("console", "bundle", "mario kart", "256gb", "256 gb"),
    ),
    PriceRule("iPhone 17 Pro/Max", _rx(r"iphone\s*17.*(pro|max)"), 5200, "Smartphones", ("capa", "case", "pelicula", "carregador", "cabo", "bateria", "display", "tela")),
    PriceRule("iPhone 17", _rx(r"iphone\s*17"), 3800, "Smartphones", ("capa", "case", "pelicula", "carregador", "cabo", "bateria", "display", "tela")),
    PriceRule("iPhone 16 Pro/Max", _rx(r"iphone\s*16.*(pro|max)"), 4200, "Smartphones", ("capa", "case", "pelicula", "carregador", "cabo", "bateria", "display", "tela")),
    PriceRule("Galaxy S Ultra", _rx(r"galaxy\s*s\d+\s*ultra"), 3000, "Smartphones", ("capa", "case", "pelicula", "carregador", "cabo", "bateria", "display", "tela")),
    PriceRule("TV 65 polegadas", _rx(r"(smart\s*)?tv.*65\s*(polegadas|\"|pol)", r"65.*(qled|oled|uhd|4k)"), 1800, "TVs", TV_ACCESSORIES),
    PriceRule("TV 55 polegadas", _rx(r"(smart\s*)?tv.*55\s*(polegadas|\"|pol)", r"55.*(qled|oled|uhd|4k)"), 1400, "TVs", TV_ACCESSORIES),
    PriceRule("TV 50 polegadas", _rx(r"(smart\s*)?tv.*(49|50)\s*(polegadas|\"|pol)", r"(49|50).*(qled|oled|uhd|4k|fhd)"), 1000, "TVs", TV_ACCESSORIES),
    PriceRule("Micro-ondas", _rx(r"micro[- ]?ondas"), 320, "Eletrodomésticos", APPLIANCE_PARTS),
    PriceRule("Air Fryer 5L", _rx(r"air\s*fryer.*5\s*l", r"fritadeira.*5\s*l"), 220, "Eletrodomésticos", APPLIANCE_PARTS),
    PriceRule("Air Fryer", _rx(r"air\s*fryer", r"fritadeira\s*(sem\s*oleo|eletrica)"), 160, "Eletrodomésticos", APPLIANCE_PARTS),
    PriceRule("Geladeira", _rx(r"geladeira", r"refrigerador"), 1400, "Eletrodomésticos", APPLIANCE_PARTS),
    PriceRule("Lava e seca", _rx(r"lava\s*e\s*seca"), 1700, "Eletrodomésticos", APPLIANCE_PARTS),
    PriceRule("Ar-condicionado", _rx(r"ar[- ]?condicionado.*(9000|12000|18000|24000)", r"split.*inverter"), 1000, "Climatização", ("controle remoto", "placa", "motor", "capacitor", "suporte", "capa")),
    PriceRule("Monitor gamer", _rx(r"monitor.*(144hz|165hz|180hz|240hz|300hz|oled|mini\s*led)"), 750, "Monitores", ("suporte para monitor", "braco para monitor", "braço para monitor", "cabo", "fonte para")),
    PriceRule("SSD NVMe 2TB", _rx(r"ssd.*(2\s*tb|2tb).*(nvme|m\.2)", r"(nvme|m\.2).*2\s*tb"), 650, "Armazenamento", ("case", "adaptador", "dissipador", "enclosure")),
    PriceRule("DJI", _rx(r"dji\s*(mini|air|mavic)"), 1600, "Drones e câmeras", ("helice", "hélice", "bateria", "capa", "case", "bolsa", "filtro nd", "controle", "carregador", "protetor")),
    PriceRule("JBL Boombox/PartyBox", _rx(r"jbl.*(boombox|partybox)"), 1200, "Áudio", ("capa", "case", "bateria", "carregador", "placa", "alca", "alça")),
    PriceRule("Estante/Painel de TV", _rx(r"estante.*tv", r"painel.*tv"), 220, "Casa"),
]


def matching_rule(title: str) -> PriceRule | None:
    text = _norm(title)
    matches: list[PriceRule] = []
    for rule in RULES:
        if not rule.pattern.search(text):
            continue
        if rule.require_any and not any(_norm(term) in text for term in rule.require_any):
            continue
        if any(_norm(term) in text for term in rule.exclude):
            continue
        matches.append(rule)
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

    kind, baseline, _confidence_weight = max(candidates, key=lambda item: item[1] * item[2])
    ratio = price / baseline
    drop_pct = max(0.0, (1.0 - ratio) * 100.0)
    score = _ratio_points(ratio)
    reasons = [f"{drop_pct:.0f}% abaixo de {kind}"]

    if rule:
        floor_ratio = price / rule.conservative_floor
        if floor_ratio <= 0.25:
            score += 35
            reasons.append(f"preço impossível para a faixa de {rule.name}")
        elif floor_ratio <= 0.45:
            score += 20
            reasons.append(f"muito abaixo do piso conservador de {rule.name}")
        elif floor_ratio <= 0.65:
            score += 8
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

    if kind == "preço anterior anunciado" and not rule:
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
