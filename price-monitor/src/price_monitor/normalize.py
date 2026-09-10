from __future__ import annotations

import re

from .utils import normalize_text


BRANDS = (
    "apple samsung lg acer lenovo dell asus motorola philips electrolux brastemp "
    "consul jbl sony xiaomi positivo vaio philco britania panasonic midea samsung "
    "tcl aoc canon nikon dji gopro microsoft xbox playstation nintendo"
).split()

STOP = {
    "smart", "tv", "televisor", "notebook", "laptop", "smartphone", "celular",
    "com", "de", "da", "do", "e", "para", "novo", "bivolt", "preto", "branco",
    "cinza", "azul", "verde", "vermelho", "windows", "linux", "ram", "ssd",
    "tela", "polegadas", "geracao", "processador", "camera", "wifi", "wi",
    "fi", "full", "hd", "uhd", "4k", "5g", "4g",
}

FAMILY_PATTERNS = (
    r"\biphone\s+\d{1,2}(?:\s+pro)?(?:\s+max)?",
    r"\bgalaxy\s+[asfz]\d{1,3}(?:\s+\w+)?",
    r"\bmoto\s+g\d{1,3}",
    r"\bedge\s+\d{1,3}(?:\s+\w+)?",
    r"\bmacbook\s+(?:air|pro)(?:\s+m\d)?",
    r"\bipad(?:\s+(?:air|pro|mini))?",
    r"\bpredator\s+[\w-]+",
    r"\bnitro\s+[\w-]+",
    r"\binspiron\s+[\w-]+",
    r"\bideapad\s+[\w-]+",
    r"\bvivobook\s+[\w-]+",
    r"\baspire\s+[\w-]+",
    r"\blegion\s+[\w-]+",
)

MODEL_TOKEN_RE = re.compile(r"\b(?=[a-z0-9-]{4,}\b)(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)[a-z0-9-]+\b")
CAPACITY_RE = re.compile(r"\b(?:128|256|512)\s*gb\b|\b[1248]\s*tb\b")
SCREEN_RE = re.compile(r"\b(?:4[0-9]|5[0-9]|6[0-9]|7[0-9]|8[0-9])\s*(?:pol|polegadas|\"|p)\b")


def product_key(title: str) -> str:
    text = normalize_text(title)
    brand = next((b for b in BRANDS if re.search(rf"\b{re.escape(b)}\b", text)), "sem-marca")

    family = ""
    for pattern in FAMILY_PATTERNS:
        m = re.search(pattern, text)
        if m:
            family = m.group(0)
            break

    model_tokens = [
        t for t in MODEL_TOKEN_RE.findall(text)
        if t not in {"1080p", "2160p", "120hz", "144hz", "165hz", "180hz"}
        and not re.fullmatch(r"(?:128|256|512)gb|[1248]tb", t)
    ]
    model_tokens = sorted(set(model_tokens), key=lambda t: (-len(t), t))[:2]

    capacities = [re.sub(r"\s+", "", x) for x in CAPACITY_RE.findall(text)]
    screen = SCREEN_RE.search(text)

    parts = [brand]
    if family:
        parts.append(family)
    parts.extend(model_tokens)
    parts.extend(capacities[:1])
    if screen:
        parts.append(screen.group(0))

    if len(parts) <= 1:
        tokens = [t for t in text.split() if t not in STOP and len(t) >= 3]
        parts.extend(tokens[:6])

    return "|".join(normalize_text(p).replace(" ", "-") for p in parts if p)


def expensive_product_hint(title: str) -> bool:
    text = normalize_text(title)
    keywords = (
        "iphone", "macbook", "notebook gamer", "predator", "nitro", "rtx",
        "oled", "qned", "mini led", "geladeira", "refrigerador", "lava e seca",
        "ar condicionado", "playstation", "ps5", "xbox series", "drone dji",
        "camera canon", "camera sony", "camera nikon", "aspirador robo",
        "robot vacuum", "fogao", "cooktop inducao",
    )
    return any(k in text for k in keywords)
