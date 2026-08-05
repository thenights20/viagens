"""Compatibilidade entre a interface v0.1 e fast-flights 3.x.

O fast-flights 3.x retorna diretamente uma lista de itinerários. A primeira
interface esperava um objeto com atributo ``flights`` e campos simplificados.
Este runtime hook adapta a resposta sem alterar a biblioteca de terceiros.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import fast_flights

_original_get_flights = fast_flights.get_flights


def _format_minutes(value: Any) -> str:
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return ""
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins:02d}min" if hours else f"{mins}min"


def _format_datetime(value: Any) -> str:
    if value is None:
        return ""
    date_value = getattr(value, "date", None)
    time_value = getattr(value, "time", None)
    try:
        year, month, day = date_value
        hour, minute = time_value
        return f"{day:02d}/{month:02d}/{year} {hour:02d}:{minute:02d}"
    except (TypeError, ValueError):
        return str(value)


@dataclass
class _FlightAdapter:
    price: str
    name: str
    airline: str
    duration: str
    stops: str
    departure: str
    arrival: str


class _ResponseAdapter:
    def __init__(self, items: Any) -> None:
        self.raw = items
        self.flights = [self._adapt(item) for item in (items or [])]

    @staticmethod
    def _adapt(item: Any) -> _FlightAdapter:
        segments = list(getattr(item, "flights", []) or [])
        airline_codes = list(getattr(item, "airlines", []) or [])
        airline = ", ".join(str(code) for code in airline_codes) or "Não informado"
        total_minutes = sum(int(getattr(seg, "duration", 0) or 0) for seg in segments)
        stops_count = max(0, len(segments) - 1)
        stops = "Direto" if stops_count == 0 else f"{stops_count} escala" + ("s" if stops_count != 1 else "")
        first = segments[0] if segments else None
        last = segments[-1] if segments else None
        price = getattr(item, "price", "")
        return _FlightAdapter(
            price=str(price),
            name=airline,
            airline=airline,
            duration=_format_minutes(total_minutes),
            stops=stops,
            departure=_format_datetime(getattr(first, "departure", None)),
            arrival=_format_datetime(getattr(last, "arrival", None)),
        )


def _compatible_get_flights(*args: Any, **kwargs: Any) -> _ResponseAdapter:
    result = _original_get_flights(*args, **kwargs)
    if hasattr(result, "flights"):
        return result
    return _ResponseAdapter(result)


fast_flights.get_flights = _compatible_get_flights
