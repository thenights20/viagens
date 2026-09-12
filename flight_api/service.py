from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SEARCH_PATH = ROOT / "flight-month-search" / "search.py"
spec = importlib.util.spec_from_file_location("flight_month_engine", SEARCH_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Não foi possível carregar o motor de busca mensal")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

app = FastAPI(title="Busca mensal de passagens", version="2.0.0")
origins = ["https://thenights20.github.io", "http://localhost:8000", "http://127.0.0.1:8000"]
extra = os.environ.get("ALLOWED_ORIGIN", "").strip().rstrip("/")
if extra:
    origins.append(extra)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    max_stops: int = Field(default=2, ge=0, le=2)


LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}
KEYS: dict[str, str] = {}
EXECUTOR = ThreadPoolExecutor(max_workers=int(os.environ.get("SEARCH_CONCURRENCY", "2")))
CACHE_TTL = int(os.environ.get("SEARCH_CACHE_TTL", "1800"))


def _month_limit() -> date:
    today = date.today().replace(day=1)
    month0 = today.month - 1 + 6
    return date(today.year + month0 // 12, month0 % 12 + 1, 1)


def _normalize(req: SearchRequest) -> dict[str, Any]:
    origin = req.origin.strip().upper()
    destination = req.destination.strip().upper()
    if not origin.isalpha() or not destination.isalpha():
        raise HTTPException(400, "Origem e destino precisam ser códigos IATA de 3 letras.")
    if origin == destination:
        raise HTTPException(400, "Origem e destino não podem ser iguais.")
    try:
        y, m = (int(x) for x in req.month.split("-", 1))
        selected = date(y, m, 1)
    except Exception as exc:
        raise HTTPException(400, "Mês inválido.") from exc
    if selected < date.today().replace(day=1) or selected > _month_limit():
        raise HTTPException(400, "Escolha o mês atual ou um dos próximos 6 meses.")
    return {
        "origin": origin,
        "destination": destination,
        "month": req.month,
        "max_stops": int(req.max_stops),
    }


def _cache_key(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _purge() -> None:
    now = time.time()
    expired = [jid for jid, job in JOBS.items() if job.get("finished_epoch") and now - float(job["finished_epoch"]) > CACHE_TTL]
    for jid in expired:
        job = JOBS.pop(jid, None)
        if job:
            KEYS.pop(str(job.get("key") or ""), None)


def _search(payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    combos = engine.build_combinations(payload["month"], now.date())
    if not combos:
        raise RuntimeError("O mês selecionado não possui pares de datas futuras.")

    fast_workers = int(os.environ.get("SEARCH_FAST_WORKERS", "12"))
    swoop_workers = int(os.environ.get("SEARCH_SWOOP_WORKERS", "6"))
    fast_rows, missing, fast_errors = engine.run_fast(
        payload["origin"], payload["destination"], combos, payload["max_stops"], fast_workers
    )
    fast_ratio = len(fast_rows) / len(combos)
    regional = payload["origin"] in {"DOU", "PMG", "JTC", "TJL", "ARU", "PPB", "MII"}
    use_swoop = regional or fast_ratio < 0.18
    swoop_rows: list[dict] = []
    swoop_errors: list[str] = []
    if use_swoop and missing:
        swoop_rows, swoop_errors = engine.run_swoop_batch(
            payload["origin"], payload["destination"], missing, payload["max_stops"], swoop_workers
        )

    rows = engine.dedupe(fast_rows + swoop_rows)
    rows.sort(key=lambda row: (float(row.get("price") or 10**12), str(row.get("departure_date")), str(row.get("return_date"))))
    top = rows[:100]
    for rank, row in enumerate(top, 1):
        row["rank"] = rank
    return {
        "version": "2.0.0",
        "mode": "full_month_matrix",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "request": payload,
        "stats": {
            "combinations": len(combos),
            "priced_combinations": len(rows),
            "coverage_pct": round((len(rows) / len(combos)) * 100, 1),
            "fast_results": len(fast_rows),
            "fast_missing": len(missing),
            "swoop_used": use_swoop,
            "swoop_results": len(swoop_rows),
            "lowest_price": round(float(top[0]["price"]), 2) if top else None,
            "result_count": len(top),
        },
        "daily_min": engine.daily_min(rows),
        "results": top,
        "errors": (fast_errors + swoop_errors)[:50],
    }


def _execute(job_id: str, payload: dict[str, Any]) -> None:
    with LOCK:
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["started_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    started = time.time()
    try:
        result = _search(payload)
        with LOCK:
            JOBS[job_id].update({
                "status": "done",
                "result": result,
                "elapsed_seconds": round(time.time() - started, 1),
                "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "finished_epoch": time.time(),
            })
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update({
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "finished_epoch": time.time(),
            })


@app.get("/")
def root() -> dict[str, Any]:
    return {"ok": True, "service": "flight-month-search", "mode": "full_month_matrix"}


@app.get("/health")
def health() -> dict[str, Any]:
    with LOCK:
        running = sum(1 for job in JOBS.values() if job.get("status") in {"queued", "running"})
    return {"ok": True, "running": running, "mode": "full_month_matrix"}


@app.post("/api/search")
def start_search(req: SearchRequest) -> dict[str, Any]:
    payload = _normalize(req)
    key = _cache_key(payload)
    with LOCK:
        _purge()
        existing_id = KEYS.get(key)
        if existing_id and existing_id in JOBS:
            existing = JOBS[existing_id]
            if existing.get("status") in {"queued", "running", "done"}:
                return {"job_id": existing_id, "status": existing["status"], "cached": existing["status"] == "done"}
        job_id = uuid.uuid4().hex[:16]
        JOBS[job_id] = {
            "job_id": job_id,
            "key": key,
            "status": "queued",
            "request": payload,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "created_epoch": time.time(),
        }
        KEYS[key] = job_id
    EXECUTOR.submit(_execute, job_id, payload)
    return {"job_id": job_id, "status": "queued", "cached": False}


@app.get("/api/search/{job_id}")
def get_search(job_id: str) -> dict[str, Any]:
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(404, "Pesquisa não encontrada ou expirada.")
        response = {
            "job_id": job_id,
            "status": job.get("status"),
            "request": job.get("request"),
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "elapsed_seconds": job.get("elapsed_seconds"),
        }
        if job.get("status") == "done":
            response["result"] = job.get("result")
        elif job.get("status") == "error":
            response["error"] = job.get("error")
        return response
