from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
}

SECRET_SOUTH_AMERICA = "https://www.secretflying.com/south-america-flight-deals/"
MELHORES_DESTINOS = "https://www.melhoresdestinos.com.br/"
PASSAGENS_IMPERDIVEIS = "https://passagensimperdiveis.com.br/"

CITY_TO_IATA = {
    "sao paulo": "GRU",
    "são paulo": "GRU",
    "rio de janeiro": "GIG",
    "campinas": "VCP",
    "punta cana": "PUJ",
    "dominican republic": "PUJ",
    "valencia": "VLC",
    "valência": "VLC",
    "chicago": "ORD",
    "new york": "JFK",
    "nova york": "JFK",
    "miami": "MIA",
    "orlando": "MCO",
    "fort lauderdale": "FLL",
    "lisbon": "LIS",
    "lisboa": "LIS",
    "porto": "OPO",
    "madrid": "MAD",
    "madri": "MAD",
    "barcelona": "BCN",
    "paris": "CDG",
    "london": "LHR",
    "londres": "LHR",
    "rome": "FCO",
    "roma": "FCO",
    "frankfurt": "FRA",
    "berlin": "BER",
    "berlim": "BER",
    "zurich": "ZRH",
    "zurique": "ZRH",
    "buenos aires": "EZE",
    "santiago": "SCL",
    "montevideo": "MVD",
    "montevideu": "MVD",
    "lima": "LIM",
    "bogota": "BOG",
    "bogotá": "BOG",
    "cancun": "CUN",
    "cancún": "CUN",
    "mexico city": "MEX",
    "cidade do mexico": "MEX",
    "seoul": "ICN",
    "seul": "ICN",
}

MONITORED_CITY_HINTS = (
    "brazil",
    "brasil",
    "sao paulo",
    "são paulo",
    "rio de janeiro",
    "campinas",
    "dourados",
    "ponta pora",
    "ponta porã",
    "bauru",
    "tres lagoas",
    "três lagoas",
    "aracatuba",
    "araçatuba",
    "presidente prudente",
    "marilia",
    "marília",
)

FLIGHT_WORDS = ("passagem", "passagens", "voo", "voos", "flight", "flights")


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFD", value or "")
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn").lower().strip()


def _price_from_title(title: str) -> tuple[float | None, str | None]:
    patterns = [
        (r"R\$\s*([0-9.]+(?:,[0-9]{1,2})?)", "BRL"),
        (r"\$\s*([0-9,.]+)\s*(?:USD)?", "USD"),
        (r"€\s*([0-9,.]+)", "EUR"),
        (r"£\s*([0-9,.]+)", "GBP"),
    ]
    for pattern, currency in patterns:
        match = re.search(pattern, title, re.I)
        if not match:
            continue
        raw = match.group(1)
        if currency == "BRL":
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
        try:
            return round(float(raw), 2), currency
        except ValueError:
            pass
    return None, None


def _trip_mode(title: str) -> str:
    t = _norm(title)
    if "ida e volta" in t or "roundtrip" in t or "round-trip" in t:
        return "round_trip"
    if "one-way" in t or "somente ida" in t or "so ida" in t:
        return "one_way"
    return "unknown"


def _extract_route_from_title(title: str) -> tuple[str | None, str | None, str | None, str | None]:
    cleaned = re.sub(r"^[^A-Za-zÀ-ÿ]+", "", title).strip()
    patterns = [
        r"(?:Non-stop from\s+)?(.+?),\s*Brazil\s+to\s+(.+?)(?:\s+for\s+only|\s+from\s+only)",
        r"(.+?),\s*Brasil\s+(?:para|→)\s+(.+?)(?:\s+a\s+partir|\s+por\s+R\$)",
        r"(.+?)\s+(?:to|→|para)\s+(.+?)(?:\s+for\s+only|\s+a\s+partir|\s+por\s+R\$)",
    ]
    for pattern in patterns:
        m = re.search(pattern, cleaned, re.I)
        if not m:
            continue
        origin_name = m.group(1).strip(" -–—")
        dest_name = m.group(2).strip(" -–—")
        origin_code = _iata_for_text(origin_name)
        dest_code = _iata_for_text(dest_name)
        return origin_name, dest_name, origin_code, dest_code
    return None, None, None, None


def _iata_for_text(text: str | None) -> str | None:
    if not text:
        return None
    normalized = _norm(text)
    for city, code in CITY_TO_IATA.items():
        if _norm(city) in normalized:
            return code
    direct = re.search(r"\(([A-Z]{3})\)", text)
    return direct.group(1) if direct else None


def _secret_detail(session: requests.Session, url: str, title: str) -> dict:
    detail: dict = {}
    try:
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        lines = [x.strip() for x in soup.stripped_strings if x.strip()]
        joined = "\n".join(lines)
        availability = re.search(r"Availability from\s+([^\n]+)", joined, re.I)
        if availability:
            detail["availability"] = availability.group(1).strip()
        airline = re.search(r"AIRLINES:\s*\n?([^\n]+)", joined, re.I)
        if airline:
            value = airline.group(1).strip()
            if value.upper() not in {"GO TO DEAL", "AIRLINES:"}:
                detail["airline"] = value
        dates: list[str] = []
        for a in soup.find_all("a"):
            text = " ".join(a.stripped_strings)
            if re.search(r"\b\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\s*[–-]\s*\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\b", text):
                dates.append(text)
        detail["example_dates"] = dates[:12]
        h1 = soup.find("h1")
        if h1:
            detail["title"] = " ".join(h1.stripped_strings)
        text_norm = _norm(title + " " + joined[:3000])
        detail["error_fare"] = "error fare" in text_norm or "fuel dump" in text_norm
    except Exception as exc:  # noqa: BLE001
        detail["detail_error"] = str(exc)[:240]
    return detail


def collect_secret_flying(max_details: int = 8) -> tuple[list[dict], dict]:
    session = _session()
    try:
        r = session.get(SECRET_SOUTH_AMERICA, timeout=20, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        rows: list[dict] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(SECRET_SOUTH_AMERICA, a["href"])
            title = " ".join(a.stripped_strings)
            if "/posts/" not in href or not title or href in seen:
                continue
            title_norm = _norm(title)
            if not any(_norm(hint) in title_norm for hint in MONITORED_CITY_HINTS):
                continue
            seen.add(href)
            price, currency = _price_from_title(title)
            origin_name, destination_name, origin_code, destination_code = _extract_route_from_title(title)
            row = {
                "source": "Secret Flying",
                "title": title,
                "url": href,
                "price": price,
                "currency": currency,
                "trip_mode": _trip_mode(title),
                "origin_name": origin_name,
                "destination_name": destination_name,
                "origin": origin_code,
                "destination": destination_code,
                "external_signal": True,
            }
            if len(rows) < max_details:
                row.update(_secret_detail(session, href, title))
            rows.append(row)
        return rows, {"ok": True, "items": len(rows), "status": r.status_code, "url": SECRET_SOUTH_AMERICA, "message": "ok"}
    except Exception as exc:  # noqa: BLE001
        return [], {"ok": False, "items": 0, "url": SECRET_SOUTH_AMERICA, "message": str(exc)[:300]}


def _collect_headline_site(name: str, url: str, max_items: int = 30) -> tuple[list[dict], dict]:
    session = _session()
    try:
        r = session.get(url, timeout=20, allow_redirects=True)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        rows: list[dict] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            title = " ".join(a.stripped_strings)
            if len(title) < 18:
                continue
            title_norm = _norm(title)
            if not any(word in title_norm for word in FLIGHT_WORDS):
                continue
            price, currency = _price_from_title(title)
            if price is None:
                continue
            href = urljoin(url, a["href"])
            if href in seen:
                continue
            seen.add(href)
            origin_name, destination_name, origin_code, destination_code = _extract_route_from_title(title)
            rows.append({
                "source": name,
                "title": title,
                "url": href,
                "price": price,
                "currency": currency,
                "trip_mode": _trip_mode(title),
                "origin_name": origin_name,
                "destination_name": destination_name,
                "origin": origin_code,
                "destination": destination_code,
                "external_signal": True,
            })
            if len(rows) >= max_items:
                break
        return rows, {"ok": True, "items": len(rows), "status": r.status_code, "url": url, "message": "ok"}
    except Exception as exc:  # noqa: BLE001
        return [], {"ok": False, "items": 0, "url": url, "message": str(exc)[:300]}


def _dedupe(rows: Iterable[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for row in rows:
        key = (row.get("source"), row.get("url"), row.get("title"))
        if key not in best:
            best[key] = row
    return list(best.values())


def collect_external_deal_signals() -> tuple[list[dict], dict[str, dict]]:
    secret, h_secret = collect_secret_flying()
    melhores, h_melhores = _collect_headline_site("Melhores Destinos", MELHORES_DESTINOS)
    imperdiveis, h_imperdiveis = _collect_headline_site("Passagens Imperdíveis", PASSAGENS_IMPERDIVEIS)
    rows = _dedupe([*secret, *melhores, *imperdiveis])
    rows.sort(key=lambda x: (0 if x.get("source") == "Secret Flying" else 1, float(x.get("price") or 999999)))
    return rows, {
        "Secret Flying": h_secret,
        "Melhores Destinos": h_melhores,
        "Passagens Imperdíveis": h_imperdiveis,
    }


def feed_payload() -> dict:
    rows, health = collect_external_deal_signals()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "version": "0.1.0",
        "generated_at": now,
        "source": "Sinais públicos de sites especializados em promoções",
        "signal_count": len(rows),
        "responding_source_count": sum(1 for x in health.values() if x.get("ok")),
        "source_count": len(health),
        "sources": health,
        "signals": rows,
    }
