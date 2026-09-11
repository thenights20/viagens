from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from airport_catalog import AIRPORTS_BY_REGION

AIRLINE_URLS = {
    "GOL": "https://www.voegol.com.br/web/guest/nh/ofertas",
    "Azul": "https://passagens.voeazul.com.br/pt/buscador-de-precos",
    "LATAM": "https://www.latamairlines.com/br/pt/ofertas/promocoes-latam?origin=all",
}

BRAZIL_AIRPORTS = {
    code
    for region, codes in AIRPORTS_BY_REGION.items()
    if region.startswith("BR-")
    for code in codes
}
BRAZIL_AIRPORTS.update({"PMG", "SAO"})

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
}


def _text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _price(value: str) -> float:
    clean = re.sub(r"[^0-9,.]", "", value or "")
    if not clean:
        raise ValueError("preço vazio")
    if "," in clean:
        clean = clean.replace(".", "").replace(",", ".")
    return round(float(clean), 2)


def _date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _scope(destination: str) -> str:
    return "domestic" if destination.upper() in BRAZIL_AIRPORTS else "international"


def _clean_place_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    # Algumas páginas da Azul colam metadados do card antes da cidade.
    value = re.split(r"\b(?:Reserve agora|down)\b", value, flags=re.I)[-1].strip()
    value = re.sub(r"^(?:\d+\s+)?(?:minuto|minutos|hora|horas)\s+atrás\s+", "", value, flags=re.I).strip()
    return value


def _offer(*, source: str, origin: str, destination: str, origin_name: str, destination_name: str,
           price: float, departure_date: str | None = None, return_date: str | None = None,
           trip_mode: str = "unknown", url: str, origin_candidates: list[str] | None = None) -> dict:
    return {
        "source": source,
        "origin": origin,
        "origin_candidates": origin_candidates or [origin],
        "origin_name": _clean_place_name(origin_name),
        "destination": destination,
        "destination_name": _clean_place_name(destination_name),
        "departure_date": departure_date,
        "return_date": return_date,
        "trip_mode": trip_mode,
        "price": round(float(price), 2),
        "scope": _scope(destination),
        "url": url,
    }


def parse_gol(html: str) -> list[dict]:
    text = _text(html)
    pattern = re.compile(
        r"Origem\s+([A-Z]{3})\s*-\s*(.+?)\s+Destino\s+([A-Z]{3})\s*-\s*(.+?)\s+"
        r"trechos?\s+a\s+partir\s+de.*?R\$\s*([0-9.]+,[0-9]{2})",
        re.I,
    )
    rows: list[dict] = []
    for match in pattern.finditer(text):
        rows.append(_offer(
            source="GOL",
            origin=match.group(1).upper(),
            origin_name=match.group(2),
            destination=match.group(3).upper(),
            destination_name=match.group(4),
            price=_price(match.group(5)),
            trip_mode="one_way_or_return",
            url=AIRLINE_URLS["GOL"],
        ))
    return rows


def parse_azul(html: str) -> list[dict]:
    text = _text(html)
    pattern = re.compile(
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ./'-]{1,55}?)\s*\(([A-Z]{3})\)\s*Para\s*"
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ./'-]{1,55}?)\s*\(([A-Z]{3})\)\s*"
        r"(?:Ida:\s*)?(\d{2}/\d{2}/\d{4})(?:\s*-\s*(\d{2}/\d{2}/\d{4}))?"
        r".{0,140}?A\s+partir\s+de\s+R\$\s*([0-9.]+,[0-9]{2})",
        re.I,
    )
    rows: list[dict] = []
    for match in pattern.finditer(text):
        dep = _date(match.group(5))
        ret = _date(match.group(6))
        rows.append(_offer(
            source="Azul",
            origin=match.group(2).upper(),
            origin_name=match.group(1),
            destination=match.group(4).upper(),
            destination_name=match.group(3),
            departure_date=dep,
            return_date=ret,
            price=_price(match.group(7)),
            trip_mode="round_trip" if ret else "one_way",
            url=AIRLINE_URLS["Azul"],
        ))
    return rows


def _latam_origin(text: str) -> tuple[str, str, list[str]]:
    match = re.search(r"Origem:\s*([^\n]+?)(?:\s+Destinos|\s+Ver ofertas|\s+Filtrar por:)", text, re.I)
    label = match.group(1).strip() if match else "São Paulo - Todos os aeroportos"
    direct = re.search(r"\(([A-Z]{3})\)", label)
    if direct:
        code = direct.group(1).upper()
        return code, label, [code]
    normalized = label.lower()
    if "são paulo" in normalized or "sao paulo" in normalized:
        return "SAO", "São Paulo (GRU/CGH)", ["GRU", "CGH"]
    if "rio de janeiro" in normalized:
        return "RIO", "Rio de Janeiro (GIG/SDU)", ["GIG", "SDU"]
    return "SAO", label, ["GRU", "CGH"]


def parse_latam(html: str) -> list[dict]:
    text = _text(html)
    origin, origin_name, candidates = _latam_origin(text)
    pattern = re.compile(
        r"(?:Voo\s+direto\s+|Voo\s+com\s+conex[aã]o\s+)?Viaja\s+em\s+.+?\s+"
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ ./'-]{1,60}?)\s*\(([A-Z]{3})\)\s*"
        r"(?:Somente\s+ida|Ida\s+e\s+volta).*?(\d{2}/\d{2}/\d{2,4}).{0,100}?"
        r"Pre[cç]o\s+a\s+partir\s+de(?:\s+~~BRL\s*[0-9.,]+~~)?\s*BRL\s*([0-9.]+,[0-9]{2})",
        re.I,
    )
    rows: list[dict] = []
    for match in pattern.finditer(text):
        rows.append(_offer(
            source="LATAM",
            origin=origin,
            origin_candidates=candidates,
            origin_name=origin_name,
            destination=match.group(2).upper(),
            destination_name=match.group(1),
            departure_date=_date(match.group(3)),
            price=_price(match.group(4)),
            trip_mode="one_way",
            url=AIRLINE_URLS["LATAM"],
        ))
    return rows


PARSERS = {"GOL": parse_gol, "Azul": parse_azul, "LATAM": parse_latam}


def _dedupe(rows: Iterable[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for row in rows:
        key = (row["source"], tuple(row.get("origin_candidates") or [row["origin"]]), row["destination"], row.get("departure_date"), row.get("return_date"), row.get("trip_mode"))
        current = best.get(key)
        if current is None or float(row["price"]) < float(current["price"]):
            best[key] = row
    return sorted(best.values(), key=lambda x: (float(x["price"]), x["source"], x["origin"], x["destination"]))


def collect_official_airline_offers(config: dict) -> tuple[list[dict], dict[str, dict]]:
    settings = config.get("airline_sources", {})
    if not settings.get("enabled", True):
        return [], {}
    monitored = {x["code"] for x in config.get("origins", [])}
    timeout = int(settings.get("timeout_seconds", 25))
    max_per_source = int(settings.get("max_offers_per_source", 80))
    session = requests.Session()
    session.headers.update(HEADERS)
    offers: list[dict] = []
    health: dict[str, dict] = {}

    for source in ("GOL", "Azul", "LATAM"):
        url = AIRLINE_URLS[source]
        source_timeout = max(timeout, 45) if source == "LATAM" else timeout
        try:
            response = session.get(url, timeout=source_timeout, allow_redirects=True)
            response.raise_for_status()
            parsed = PARSERS[source](response.text)
            filtered = [
                row for row in parsed
                if monitored.intersection(set(row.get("origin_candidates") or [row["origin"]]))
            ]
            filtered = _dedupe(filtered)[:max_per_source]
            offers.extend(filtered)
            health[source] = {
                "ok": bool(parsed),
                "items": len(filtered),
                "parsed": len(parsed),
                "status": response.status_code,
                "url": url,
                "message": "ok" if parsed else "página respondeu, mas nenhum preço reconhecido",
            }
        except Exception as exc:  # noqa: BLE001
            health[source] = {"ok": False, "items": 0, "parsed": 0, "url": url, "message": str(exc)[:300]}

    return _dedupe(offers), health


def add_airline_matches(deals: list[dict], offers: list[dict], tolerance_pct: float = 10.0) -> int:
    """Anexa sinais das páginas oficiais às oportunidades do radar.

    Só chama de confirmação de preço quando o site oficial publica ida e volta
    nas mesmas datas e o valor fica dentro da tolerância. Ofertas só de ida ou
    sem data entram apenas como presença da rota na companhia.
    """
    matched = 0
    tolerance = max(0.0, float(tolerance_pct)) / 100.0
    for deal in deals:
        signals: list[dict] = []
        for offer in offers:
            if deal.get("destination") != offer.get("destination"):
                continue
            if deal.get("origin") not in set(offer.get("origin_candidates") or [offer.get("origin")]):
                continue
            signal = {
                "source": offer["source"],
                "price": offer["price"],
                "trip_mode": offer.get("trip_mode"),
                "departure_date": offer.get("departure_date"),
                "return_date": offer.get("return_date"),
                "url": offer.get("url"),
                "kind": "route",
            }
            same_dates = (
                offer.get("trip_mode") == "round_trip"
                and offer.get("departure_date") == deal.get("departure_date")
                and offer.get("return_date") == deal.get("return_date")
            )
            if same_dates and float(deal.get("price") or 0) > 0:
                delta = abs(float(offer["price"]) - float(deal["price"])) / float(deal["price"])
                signal["kind"] = "price_confirmation" if delta <= tolerance else "same_dates_other_price"
                signal["difference_pct"] = round(delta * 100, 1)
            signals.append(signal)
        if signals:
            deal["airline_signals"] = signals
            deal["airline_sources"] = sorted({x["source"] for x in signals})
            if any(x["kind"] == "price_confirmation" for x in signals):
                deal["airline_confirmation"] = "preço encontrado também no site oficial"
                matched += 1
            else:
                deal["airline_confirmation"] = "rota encontrada em oferta oficial"
    return matched
