from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

BOOKING_URL = "https://indigoneo.com.br/pt/booking/99980448"
OUTPUT_PATH = Path(os.environ.get("INDIGO_OUTPUT_PATH", "docs/data/indigo-parking.json"))
MAX_COMBINATIONS = 48


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def parse_hhmm(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError(f"Horário inválido: {value}")
    h, m = value.split(":")
    return int(h), int(m)


def minutes(value: str) -> int:
    h, m = parse_hhmm(value)
    return h * 60 + m


def fmt_minutes(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def time_range(start: str, end: str, step: int) -> list[str]:
    a, b = minutes(start), minutes(end)
    if b < a:
        raise ValueError("O horário final precisa ser igual ou posterior ao inicial.")
    return [fmt_minutes(v) for v in range(a, b + 1, step)]


def valid_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Data inválida: {value}") from exc


def parse_money(text: str) -> float | None:
    match = re.search(r"R\$\s*([\d\.]+(?:,\d{2})?)", text or "", re.I)
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def normalize(text: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in value if unicodedata.category(c) != "Mn").lower().strip()


def is_t3_covered(text: str) -> bool:
    n = normalize(text)
    terminal3 = "terminal 3" in n or re.search(r"\bt3\b", n) is not None
    garage = any(k in n for k in ["edificio garagem", "ed. garagem", "garagem", "coberto", "premium"])
    return bool(terminal3 and garage)


def unavailable_text(text: str) -> bool:
    n = normalize(text)
    return any(k in n for k in [
        "indisponivel", "esgotado", "lotado", "sem vaga", "nao disponivel",
        "nenhuma vaga", "vagas esgotadas", "nao ha disponibilidade",
    ])


def available_text(text: str) -> bool:
    n = normalize(text)
    return any(k in n for k in ["reservar", "selecionar", "disponivel", "comprar", "escolher"]) and not unavailable_text(text)


@dataclass
class SearchRequest:
    request_id: str
    entry_date: str
    exit_date: str
    entry_from: str
    entry_to: str
    exit_from: str
    exit_to: str
    step_minutes: int
    parking_mode: str

    @classmethod
    def from_env(cls) -> "SearchRequest":
        req = cls(
            request_id=env("INDIGO_REQUEST_ID", "manual")[:80],
            entry_date=env("INDIGO_ENTRY_DATE"),
            exit_date=env("INDIGO_EXIT_DATE"),
            entry_from=env("INDIGO_ENTRY_FROM", "08:00"),
            entry_to=env("INDIGO_ENTRY_TO", "14:00"),
            exit_from=env("INDIGO_EXIT_FROM", "07:00"),
            exit_to=env("INDIGO_EXIT_TO", "07:00"),
            step_minutes=int(env("INDIGO_STEP_MINUTES", "60")),
            parking_mode=env("INDIGO_PARKING_MODE", "t3_covered"),
        )
        req.validate()
        return req

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.request_id):
            raise ValueError("request_id inválido")
        start, end = valid_iso_date(self.entry_date), valid_iso_date(self.exit_date)
        if end < start:
            raise ValueError("A saída não pode ser anterior à entrada.")
        if (end - start).days > 60:
            raise ValueError("A permanência máxima desta busca é 60 dias.")
        if self.step_minutes not in {30, 60, 120}:
            raise ValueError("Intervalo precisa ser 30, 60 ou 120 minutos.")
        if self.parking_mode not in {"t3_covered", "all"}:
            raise ValueError("Modo de estacionamento inválido.")
        entry_times = time_range(self.entry_from, self.entry_to, self.step_minutes)
        exit_times = time_range(self.exit_from, self.exit_to, self.step_minutes)
        if len(entry_times) * len(exit_times) > MAX_COMBINATIONS:
            raise ValueError(f"Máximo de {MAX_COMBINATIONS} combinações por pesquisa.")

    def combinations(self) -> list[tuple[str, str]]:
        return [
            (entry, exit_)
            for entry in time_range(self.entry_from, self.entry_to, self.step_minutes)
            for exit_ in time_range(self.exit_from, self.exit_to, self.step_minutes)
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "airport": "GRU",
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "entry_from": self.entry_from,
            "entry_to": self.entry_to,
            "exit_from": self.exit_from,
            "exit_to": self.exit_to,
            "step_minutes": self.step_minutes,
            "parking_mode": self.parking_mode,
        }


def control_meta(locator: Locator) -> dict[str, str]:
    try:
        return locator.evaluate(
            """el => ({
              tag:(el.tagName||'').toLowerCase(), type:el.type||'', name:el.name||'', id:el.id||'',
              placeholder:el.placeholder||'', value:el.value||'', aria:el.getAttribute('aria-label')||'',
              role:el.getAttribute('role')||'', text:(el.innerText||el.textContent||'').trim(),
              parent:(el.parentElement?.innerText||'').trim().slice(0,180)
            })"""
        )
    except Exception:
        return {}


def visible_controls(page: Page) -> list[tuple[Locator, dict[str, str]]]:
    out: list[tuple[Locator, dict[str, str]]] = []
    loc = page.locator("input:visible, select:visible, [role=combobox]:visible")
    for i in range(loc.count()):
        item = loc.nth(i)
        meta = control_meta(item)
        if meta:
            out.append((item, meta))
    return out


def control_text(meta: dict[str, str]) -> str:
    return normalize(" ".join(str(meta.get(k, "")) for k in ["name", "id", "placeholder", "aria", "text", "parent", "type"]))


def classify_controls(page: Page) -> tuple[list[Locator], list[Locator], list[dict[str, str]]]:
    controls = visible_controls(page)
    date_controls: list[Locator] = []
    time_controls: list[Locator] = []
    metas: list[dict[str, str]] = []
    for loc, meta in controls:
        metas.append(meta)
        text = control_text(meta)
        typ = normalize(meta.get("type", ""))
        val = meta.get("value", "")
        if typ == "date" or "dd/mm" in text or "data" in text or re.fullmatch(r"\d{2}/\d{2}/\d{4}", val or ""):
            date_controls.append(loc)
        elif typ == "time" or "hora" in text or "horario" in text or re.fullmatch(r"\d{2}:\d{2}", val or ""):
            time_controls.append(loc)
    if len(date_controls) < 2:
        likely = [(loc, meta) for loc, meta in controls if meta.get("tag") in {"input", "select"}]
        date_controls = [loc for loc, meta in likely if meta.get("type") not in {"time"}][:2]
    if len(time_controls) < 2:
        likely = [loc for loc, meta in controls if meta.get("type") == "time" or re.fullmatch(r"\d{2}:\d{2}", meta.get("value", "") or "")]
        if len(likely) >= 2:
            time_controls = likely[:2]
        else:
            ordered = [loc for loc, _ in controls]
            time_controls = [ordered[i] for i in (1, 3) if i < len(ordered)]
    return date_controls[:2], time_controls[:2], metas


def set_native_value(locator: Locator, value: str) -> bool:
    try:
        tag = locator.evaluate("el => (el.tagName||'').toLowerCase()")
        if tag == "select":
            locator.select_option(value=value)
            return True
        locator.click(timeout=1500)
        try:
            locator.fill(value, timeout=1500)
            locator.press("Tab", timeout=800)
            return True
        except Exception:
            pass
        locator.evaluate("el => el.removeAttribute('readonly')")
        locator.fill(value, timeout=1500)
        locator.press("Tab", timeout=800)
        return True
    except Exception:
        try:
            locator.evaluate(
                """(el, value) => {
                  const desc = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value');
                  if (desc && desc.set) desc.set.call(el, value); else el.value=value;
                  el.dispatchEvent(new Event('input',{bubbles:true}));
                  el.dispatchEvent(new Event('change',{bubbles:true}));
                  el.dispatchEvent(new Event('blur',{bubbles:true}));
                }""",
                value,
            )
            return True
        except Exception:
            return False


def set_date(locator: Locator, iso: str) -> bool:
    br = datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    typ = locator.get_attribute("type") or ""
    for value in ([iso, br] if typ == "date" else [br, iso]):
        if set_native_value(locator, value):
            try:
                current = locator.input_value(timeout=500)
                if iso in current or br in current or current:
                    return True
            except Exception:
                return True
    return False


def choose_from_popup(page: Page, value: str) -> bool:
    for label in [value, value.lstrip("0"), value.replace(":00", "h")]:
        if not label:
            continue
        opt = page.get_by_text(label, exact=True)
        try:
            for i in range(opt.count() - 1, -1, -1):
                if opt.nth(i).is_visible():
                    opt.nth(i).click(timeout=1200)
                    return True
        except Exception:
            pass
    return False


def set_time(page: Page, locator: Locator, value: str) -> bool:
    if set_native_value(locator, value):
        try:
            current = locator.input_value(timeout=500)
            if value in current or current:
                return True
        except Exception:
            return True
    try:
        locator.click(timeout=1200)
        return choose_from_popup(page, value)
    except Exception:
        return False


def accept_cookies(page: Page) -> None:
    for pattern in [r"aceitar", r"aceito", r"permitir", r"concordo"]:
        try:
            button = page.get_by_role("button", name=re.compile(pattern, re.I))
            if button.count() and button.first.is_visible():
                button.first.click(timeout=1200)
                page.wait_for_timeout(250)
                return
        except Exception:
            continue


def advance(page: Page) -> None:
    candidates = [
        page.get_by_role("button", name=re.compile(r"pr[oó]ximo|continuar|buscar|consultar", re.I)),
        page.get_by_text(re.compile(r"^\s*pr[oó]ximo\s*$", re.I)),
    ]
    for loc in candidates:
        try:
            if loc.count() and loc.first.is_visible():
                loc.first.click(timeout=2500)
                return
        except Exception:
            continue
    raise RuntimeError("Botão PRÓXIMO/CONTINUAR não localizado.")


def wait_for_options(page: Page) -> str:
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    for _ in range(20):
        text = page.locator("body").inner_text(timeout=3000)
        n = normalize(text)
        if any(k in n for k in ["terminal 3", "edificio garagem", "indisponivel", "esgotado", "estacionamento"]):
            return text
        page.wait_for_timeout(500)
    return page.locator("body").inner_text(timeout=3000)


def extract_cards(page: Page) -> list[str]:
    selectors = [
        "article:visible", "[class*=card]:visible", "[class*=product]:visible", "[class*=parking]:visible",
        "[class*=option]:visible", "[role=option]:visible",
    ]
    texts: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        loc = page.locator(selector)
        for i in range(min(loc.count(), 80)):
            try:
                txt = re.sub(r"\s+", " ", loc.nth(i).inner_text(timeout=500)).strip()
            except Exception:
                continue
            key = normalize(txt)
            if len(txt) >= 8 and key not in seen:
                seen.add(key)
                texts.append(txt)
    if not any(is_t3_covered(t) for t in texts):
        try:
            body = page.locator("body").inner_text(timeout=1500)
            chunks = [re.sub(r"\s+", " ", c).strip() for c in re.split(r"\n{2,}", body)]
            for txt in chunks:
                key = normalize(txt)
                if ("terminal" in key or "garagem" in key or "estacionamento" in key) and key not in seen:
                    seen.add(key)
                    texts.append(txt)
        except Exception:
            pass
    return texts


def pick_results(cards: list[str], parking_mode: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for text in cards:
        n = normalize(text)
        relevant = is_t3_covered(text) if parking_mode == "t3_covered" else any(k in n for k in ["terminal", "estacionamento", "garagem", "premium", "economy", "standard"])
        if not relevant:
            continue
        unavailable = unavailable_text(text)
        available = (not unavailable) and (available_text(text) or parse_money(text) is not None)
        terminal = "T3" if ("terminal 3" in n or re.search(r"\bt3\b", n)) else ""
        name_match = re.search(r"((?:Terminal\s*3[^\n\r]{0,80})|(?:Edif[ií]cio\s+Garagem[^\n\r]{0,80})|(?:Premium[^\n\r]{0,80}))", text, re.I)
        name = re.sub(r"\s+", " ", name_match.group(1)).strip() if name_match else ("Terminal 3 · Edifício Garagem" if is_t3_covered(text) else text[:100])
        out.append({
            "parking_name": name,
            "terminal": terminal,
            "covered": is_t3_covered(text),
            "available": bool(available),
            "price": parse_money(text),
            "currency": "BRL",
            "message": "Indisponível" if unavailable else ("Disponível" if available else "Verificar no site"),
            "raw_text": text[:700],
        })
    dedup: dict[tuple[str, bool, float | None], dict[str, Any]] = {}
    for row in sorted(out, key=lambda x: len(x.get("raw_text", ""))):
        key = (normalize(row["parking_name"]), row["available"], row["price"])
        dedup.setdefault(key, row)
    return list(dedup.values())


def fill_search_form(page: Page, req: SearchRequest, entry_time: str, exit_time: str) -> list[dict[str, str]]:
    date_controls, time_controls, metas = classify_controls(page)
    if len(date_controls) < 2 or len(time_controls) < 2:
        raise RuntimeError(f"Não foi possível identificar os quatro controles de data/hora. Controles: {metas[:12]}")
    if not set_date(date_controls[0], req.entry_date):
        raise RuntimeError("Não foi possível preencher a data de entrada.")
    if not set_time(page, time_controls[0], entry_time):
        raise RuntimeError("Não foi possível preencher o horário de entrada.")
    if not set_date(date_controls[1], req.exit_date):
        raise RuntimeError("Não foi possível preencher a data de saída.")
    if not set_time(page, time_controls[1], exit_time):
        raise RuntimeError("Não foi possível preencher o horário de saída.")
    return metas


def run_one(page: Page, req: SearchRequest, entry_time: str, exit_time: str) -> dict[str, Any]:
    started = time.time()
    page.goto(BOOKING_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(900)
    accept_cookies(page)
    metas = fill_search_form(page, req, entry_time, exit_time)
    page.wait_for_timeout(250)
    advance(page)
    text = wait_for_options(page)
    options = pick_results(extract_cards(page), req.parking_mode)
    if not options and req.parking_mode == "t3_covered" and unavailable_text(text):
        options = [{
            "parking_name": "Terminal 3 · Edifício Garagem",
            "terminal": "T3", "covered": True, "available": False,
            "price": None, "currency": "BRL", "message": "Indisponível",
            "raw_text": re.sub(r"\s+", " ", text)[:700],
        }]
    return {
        "entry_datetime": f"{req.entry_date}T{entry_time}:00",
        "exit_datetime": f"{req.exit_date}T{exit_time}:00",
        "options": options,
        "available": any(o.get("available") for o in options),
        "booking_url": BOOKING_URL,
        "elapsed_seconds": round(time.time() - started, 1),
        "control_snapshot": metas[:8],
    }


def main() -> int:
    req = SearchRequest.from_env()
    combos = req.combinations()
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    checks: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    available_rows: list[dict[str, Any]] = []
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            locale="pt-BR", timezone_id="America/Sao_Paulo", viewport={"width": 1365, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
        )
        page = context.new_page()
        page.set_default_timeout(5000)
        for index, (entry_time, exit_time) in enumerate(combos, 1):
            try:
                row = run_one(page, req, entry_time, exit_time)
                checks.append(row)
                for option in row.get("options", []):
                    if option.get("available"):
                        available_rows.append({"entry_datetime": row["entry_datetime"], "exit_datetime": row["exit_datetime"], "booking_url": BOOKING_URL, **option})
                print(f"[{index}/{len(combos)}] {entry_time} → {exit_time}: {'VAGA' if row['available'] else 'sem vaga'}", flush=True)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:1200]
                errors.append({"entry_time": entry_time, "exit_time": exit_time, "error": error})
                checks.append({
                    "entry_datetime": f"{req.entry_date}T{entry_time}:00", "exit_datetime": f"{req.exit_date}T{exit_time}:00",
                    "options": [], "available": False, "booking_url": BOOKING_URL, "error": error,
                })
                print(f"[{index}/{len(combos)}] erro: {exc}", flush=True)
            if index < len(combos):
                time.sleep(0.7)
        context.close()
        browser.close()

    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in available_rows:
        key = (row["entry_datetime"], row["exit_datetime"], normalize(row.get("parking_name", "")), row.get("price"))
        unique.setdefault(key, row)
    results = sorted(unique.values(), key=lambda x: (x["entry_datetime"], x["exit_datetime"], x.get("price") if x.get("price") is not None else 10**9))
    payload = {
        "version": "0.1.0", "status": "completed", "request_id": req.request_id, "generated_at": generated,
        "request": req.as_dict(),
        "stats": {
            "combinations": len(combos), "tested": len(checks),
            "available_combinations": len({(r["entry_datetime"], r["exit_datetime"]) for r in results}),
            "available_options": len(results), "errors": len(errors),
        },
        "results": results, "checks": checks, "errors": errors[:30], "booking_url": BOOKING_URL,
        "notice": "Consulta informativa. A disponibilidade pode mudar até a conclusão da reserva no site da Indigo Neo.",
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["stats"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
