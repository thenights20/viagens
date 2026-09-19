from __future__ import annotations

import calendar
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "miles-search.json"
API_URL = "https://seats.aero/partnerapi/search"
VERSION = "0.2.0"

PROGRAMS = {
    "Smiles": {
        "source": "smiles",
        "url": "https://www.smiles.com.br/home",
        "automated": True,
    },
    "Azul Fidelidade": {
        "source": "azul",
        "url": "https://www.voeazul.com.br/br/pt/home",
        "automated": True,
    },
    "AAdvantage": {
        "source": "american",
        "url": "https://www.aa.com/booking/search/find-flights?anchorEvent=false&from=comp_nav&locale=pt_BR",
        "automated": True,
    },
    "LATAM Pass": {
        "source": None,
        "url": "https://www.latamairlines.com/br/pt",
        "automated": False,
    },
}
SOURCE_TO_PROGRAM = {
    info["source"]: name
    for name, info in PROGRAMS.items()
    if info.get("source")
}
CABINS = {
    "economy": ("Y", "economy"),
    "premium_economy": ("W", "premium"),
    "business": ("J", "business"),
    "first": ("F", "first"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(payload: dict[str, Any]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fail_payload(request: dict[str, Any], message: str, *, code: str = "search_error") -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": "error",
        "generated_at": utc_now(),
        "request_id": request["request_id"],
        "request": request,
        "provider": "Seats.aero cached award availability",
        "results": [],
        "result_count": 0,
        "error": message,
        "error_code": code,
        "sources": source_health(error=message),
    }


def source_health(*, rows: list[dict[str, Any]] | None = None, error: str | None = None) -> dict[str, Any]:
    rows = rows or []
    counts = {name: 0 for name in PROGRAMS}
    for row in rows:
        program = str(row.get("program") or "")
        if program in counts:
            counts[program] += 1

    out: dict[str, Any] = {}
    for name, info in PROGRAMS.items():
        if not info["automated"]:
            out[name] = {
                "ok": False,
                "items": 0,
                "automated": False,
                "message": "LATAM Pass não está disponível na fonte automatizada atual; use o acesso oficial para conferir o resgate.",
            }
        elif error:
            out[name] = {
                "ok": False,
                "items": 0,
                "automated": True,
                "message": error,
            }
        else:
            out[name] = {
                "ok": True,
                "items": counts[name],
                "automated": True,
                "message": (
                    f"Consulta concluída: {counts[name]} disponibilidade(s) encontrada(s)."
                    if counts[name]
                    else "Consulta concluída; nenhuma disponibilidade encontrada para os filtros informados."
                ),
            }
    return out


def parse_request() -> dict[str, Any]:
    origin = str(os.environ.get("MILES_ORIGIN") or "").strip().upper()
    destination = str(os.environ.get("MILES_DESTINATION") or "").strip().upper()
    period_mode = str(os.environ.get("MILES_PERIOD_MODE") or "month").strip().lower()
    month = str(os.environ.get("MILES_MONTH") or "").strip()
    start_date = str(os.environ.get("MILES_START_DATE") or "").strip()
    end_date = str(os.environ.get("MILES_END_DATE") or "").strip()
    program = str(os.environ.get("MILES_PROGRAM") or "").strip()
    cabin = str(os.environ.get("MILES_CABIN") or "economy").strip()
    request_id = str(os.environ.get("MILES_REQUEST_ID") or "manual").strip()[:80]

    if len(origin) != 3 or not origin.isalpha() or len(destination) != 3 or not destination.isalpha():
        raise ValueError("Origem e destino precisam ser códigos IATA de 3 letras.")
    if origin == destination:
        raise ValueError("Origem e destino não podem ser iguais.")
    if period_mode not in {"month", "range"}:
        raise ValueError("Tipo de período inválido.")
    if program and program not in PROGRAMS:
        raise ValueError("Programa de milhas inválido.")
    if cabin and cabin not in CABINS:
        raise ValueError("Cabine inválida.")
    if not request_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in request_id):
        raise ValueError("request_id inválido.")

    if period_mode == "range":
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise ValueError("Datas do intervalo inválidas.") from exc
        if end < start:
            raise ValueError("A data final precisa ser igual ou posterior à data inicial.")
        month = start.strftime("%Y-%m")
    else:
        try:
            year_s, month_s = month.split("-", 1)
            year, month_n = int(year_s), int(month_s)
            if not 1 <= month_n <= 12:
                raise ValueError
        except Exception as exc:
            raise ValueError("Mês inválido.") from exc
        start = date(year, month_n, 1)
        end = date(year, month_n, calendar.monthrange(year, month_n)[1])
        start_date = start.isoformat()
        end_date = end.isoformat()

    return {
        "origin": origin,
        "destination": destination,
        "period_mode": period_mode,
        "month": month,
        "start_date": start_date,
        "end_date": end_date,
        "program": program,
        "cabin": cabin,
        "request_id": request_id,
    }


def to_int(value: Any) -> int | None:
    if value is None or value is False:
        return None
    raw = str(value).replace(",", "").strip()
    if not raw:
        return None
    try:
        number = int(float(raw))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def api_search(request: dict[str, Any], api_key: str) -> list[dict[str, Any]]:
    selected_names = [request["program"]] if request["program"] else [
        name for name, info in PROGRAMS.items() if info["automated"]
    ]
    source_codes = [PROGRAMS[name]["source"] for name in selected_names if PROGRAMS[name]["source"]]
    if not source_codes:
        return []

    params = {
        "origin_airport": request["origin"],
        "destination_airport": request["destination"],
        "start_date": request["start_date"],
        "end_date": request["end_date"],
        "sources": ",".join(source_codes),
        "take": "1000",
        "order_by": "lowest_mileage",
    }
    if request["cabin"]:
        params["cabins"] = CABINS[request["cabin"]][1]

    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Partner-Authorization": api_key,
            "Accept": "application/json",
            "User-Agent": "thenights20-viagens/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            detail = str(parsed.get("message") or parsed.get("error") or "").strip()
        except Exception:
            pass
        if exc.code == 401:
            raise RuntimeError("Chave Seats.aero ausente, inválida ou sem acesso à Partner API.") from None
        if exc.code == 429:
            raise RuntimeError("Limite diário da API de milhas atingido. Tente novamente após a renovação da cota.") from None
        raise RuntimeError(f"Fonte de milhas respondeu HTTP {exc.code}" + (f": {detail}" if detail else ".")) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Não foi possível conectar à fonte de milhas: {exc.reason}") from None

    rows = payload.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("A fonte de milhas devolveu um formato inesperado.")
    return rows


def normalize(raw_rows: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = [request["cabin"]] if request["cabin"] else list(CABINS)
    output: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for item in raw_rows:
        route = item.get("Route") or {}
        origin = str(route.get("OriginAirport") or item.get("OriginAirport") or "").upper()
        destination = str(route.get("DestinationAirport") or item.get("DestinationAirport") or "").upper()
        source = str(item.get("Source") or route.get("Source") or "").lower()
        program = SOURCE_TO_PROGRAM.get(source)
        departure_date = str(item.get("Date") or "")[:10]
        if not program or origin != request["origin"] or destination != request["destination"] or not departure_date:
            continue

        for cabin in wanted:
            prefix, _ = CABINS[cabin]
            if item.get(prefix + "Available") is not True:
                continue
            miles = to_int(item.get(prefix + "MileageCost"))
            if not miles:
                continue
            key = (program, origin, destination, departure_date, cabin, miles)
            if key in seen:
                continue
            seen.add(key)
            output.append({
                "program": program,
                "source": program,
                "source_code": source,
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": None,
                "cabin": cabin,
                "miles": miles,
                "seats": to_int(item.get(prefix + "RemainingSeats")) or 0,
                "direct": bool(item.get(prefix + "Direct")),
                "airlines": str(item.get(prefix + "Airlines") or ""),
                "availability_id": str(item.get("ID") or ""),
                "updated_at": item.get("ComputedLastSeen") or item.get("UpdatedAt"),
                "url": PROGRAMS[program]["url"],
            })

    output.sort(key=lambda row: (int(row["miles"]), row["departure_date"], row["program"], row["cabin"]))
    return output


def main() -> None:
    try:
        request = parse_request()
    except ValueError as exc:
        fallback = {
            "origin": "",
            "destination": "",
            "period_mode": "month",
            "month": "",
            "start_date": "",
            "end_date": "",
            "program": "",
            "cabin": "economy",
            "request_id": str(os.environ.get("MILES_REQUEST_ID") or "manual")[:80],
        }
        write(fail_payload(fallback, str(exc), code="invalid_request"))
        return

    selected = request["program"]
    if selected and not PROGRAMS[selected]["automated"]:
        payload = {
            "version": VERSION,
            "status": "completed",
            "generated_at": utc_now(),
            "request_id": request["request_id"],
            "request": request,
            "provider": "Seats.aero cached award availability",
            "cached_data": True,
            "results": [],
            "result_count": 0,
            "sources": source_health(rows=[]),
            "notice": "O programa selecionado não possui coleta automatizada na fonte atual.",
        }
        write(payload)
        return

    api_key = str(os.environ.get("SEATS_AERO_API_KEY") or "").strip()
    if not api_key:
        write(fail_payload(
            request,
            "A busca por milhas foi conectada, mas o segredo SEATS_AERO_API_KEY ainda não está configurado no GitHub Actions.",
            code="missing_api_key",
        ))
        return

    try:
        raw_rows = api_search(request, api_key)
        rows = normalize(raw_rows, request)
        payload = {
            "version": VERSION,
            "status": "completed",
            "generated_at": utc_now(),
            "request_id": request["request_id"],
            "request": request,
            "provider": "Seats.aero cached award availability",
            "cached_data": True,
            "results": rows,
            "result_count": len(rows),
            "sources": source_health(rows=rows),
        }
    except RuntimeError as exc:
        payload = fail_payload(request, str(exc))
    write(payload)


if __name__ == "__main__":
    main()
