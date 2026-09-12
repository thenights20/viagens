"""Parser for the fast-flights 3.1 Google response consumed by this project.

Empty groups and incomplete offers are normal missing results. An unrecognized
document/schema raises ProviderResponseError and remains visible in diagnostics.
"""
import json
from types import SimpleNamespace
from selectolax.lexbor import LexborHTMLParser


class ProviderResponseError(ValueError):
    pass


def at(value, index):
    if value is None:
        return None
    if not isinstance(value, list):
        raise ProviderResponseError(f"Expected array at index {index}, got {type(value).__name__}")
    return value[index] if index < len(value) else None


def parse_payload(payload):
    if payload is None:
        return []
    if not isinstance(payload, list) or len(payload) < 4:
        raise ProviderResponseError("Google response does not contain flight groups")
    offers = []
    # Google separates preferred itineraries (2) and other itineraries (3).
    for group_index in (2, 3):
        group = at(payload, group_index)
        entries = at(group, 0)
        if entries is None:
            continue
        if not isinstance(entries, list):
            raise ProviderResponseError("Google itinerary group is not an array")
        for entry in entries:
            flight = at(entry, 0)
            price = at(at(at(entry, 1), 0), 1)
            segments = at(flight, 2)
            if flight is None or price is None or not segments:
                continue
            if not isinstance(price, (int, float)) or isinstance(price, bool):
                raise ProviderResponseError("Google price is not numeric")
            if price <= 0:
                continue
            if not isinstance(segments, list):
                raise ProviderResponseError("Google segments are not an array")
            legs = []
            for segment in segments:
                if segment is None:
                    break
                if not at(segment, 3) or not at(segment, 6):
                    break
                legs.append(SimpleNamespace(
                    duration=at(segment, 11) or 0,
                    departure=str(at(segment, 20) or "")+" "+str(at(segment, 8) or ""),
                    arrival=str(at(segment, 21) or "")+" "+str(at(segment, 10) or ""),
                ))
            if len(legs) != len(segments):
                continue
            offers.append(SimpleNamespace(price=price, airlines=at(flight, 1) or [], flights=legs))
    return offers


def parse_html(html):
    script = LexborHTMLParser(html).css_first(r"script.ds\:1")
    if script is None:
        raise ProviderResponseError("Google document has no flight data script")
    js = script.text()
    if "data:" not in js:
        raise ProviderResponseError("Google flight script has no data field")
    raw = js.split("data:", 1)[1].rsplit(",", 1)[0]
    if raw.endswith("errorHasStatus: true"):
        raise ProviderResponseError("Google returned a provider error")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError("Google flight data is not valid JSON") from exc
    return parse_payload(payload)


def get_flights(query):
    from fast_flights.fetcher import fetch_flights_html
    return parse_html(fetch_flights_html(query))
