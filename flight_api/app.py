from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
SEARCH_SCRIPT = ROOT / "flight-month-search" / "search.py"

app = FastAPI(title="Flight Month Search API", version="1.0.0")

allowed = [
    "https://thenights20.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
extra_origin = os.environ.get("ALLOWED_ORIGIN", "").strip()
if extra_origin:
    allowed.append(extra_origin.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    min_stay: int = Field(default=4, ge=2, le=21)
    max_stay: int = Field(default=10, ge=2, le=21)
    max_stops: int = Field(default=2, ge=0, le=2)


LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}
KEY_TO_JOB: dict[str, str] = {}
CACHE_TTL = int(os.environ.get("SEARCH_CACHE_TTL", "1800"))
MAX_JOBS = int(os.environ.get("SEARCH_MAX_JOBS", "80"))


def _normalize(req: SearchRequest) -> dict[str, Any]:
    origin = req.origin.strip().upper()
    destination = req.destination.strip().upper()
    if not origin.isalpha() or not destination.isalpha():
        raise HTTPException(status_code=400, detail="Origem e destino precisam ser códigos IATA de 3 letras.")
    if origin == destination:
        raise HTTPException(status_code=400, detail="Origem e destino não podem ser iguais.")
    if req.min_stay > req.max_stay:
        raise HTTPException(status_code=400, detail="A duração mínima não pode ser maior que a máxima.")
    try:
        year_s, month_s = req.month.split("-", 1)
        year, month = int(year_s), int(month_s)
        selected = date(year, month, 1)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Mês inválido.") from exc
    today = date.today().replace(day=1)
    max_year = today.year + ((today.month - 1 + 6) // 12)
    max_month = ((today.month - 1 + 6) % 12) + 1
    max_allowed = date(max_year, max_month, 1)
    if selected < today or selected > max_allowed:
        raise HTTPException(status_code=400, detail="Escolha um mês entre o atual e os próximos 6 meses.")
    return {
        "origin": origin,
        "destination": destination,
        "month": req.month,
        "min_stay": int(req.min_stay),
        "max_stay": int(req.max_stay),
        "max_stops": int(req.max_stops),
    }


def _key(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _cleanup() -> None:
    now = time.time()
    removable = []
    for job_id, job in JOBS.items():
        finished = float(job.get("finished_epoch") or 0)
        if finished and now - finished > CACHE_TTL:
            removable.append(job_id)
    for job_id in removable:
        job = JOBS.pop(job_id, None)
        if job:
            KEY_TO_JOB.pop(job.get("key", ""), None)
    if len(JOBS) > MAX_JOBS:
        ordered = sorted(JOBS.items(), key=lambda kv: float(kv[1].get("created_epoch") or 0))
        for job_id, job in ordered[: len(JOBS) - MAX_JOBS]:
            JOBS.pop(job_id, None)
            KEY_TO_JOB.pop(job.get("key", ""), None)


def _run_job(job_id: str, payload: dict[str, Any]) -> None:
    with LOCK:
        if job_id not in JOBS:
            return
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["started_at"] = datetime.utcnow().isoformat() + "Z"

    fd, out_name = tempfile.mkstemp(prefix=f"flight-{job_id}-", suffix=".json")
    os.close(fd)
    out_path = Path(out_name)
    env = os.environ.copy()
    env.update(
        {
            "SEARCH_ORIGIN": payload["origin"],
            "SEARCH_DESTINATION": payload["destination"],
            "SEARCH_MONTH": payload["month"],
            "SEARCH_MIN_STAY": str(payload["min_stay"]),
            "SEARCH_MAX_STAY": str(payload["max_stay"]),
            "SEARCH_MAX_STOPS": str(payload["max_stops"]),
            "SEARCH_FAST_WORKERS": os.environ.get("SEARCH_FAST_WORKERS", "10"),
            "SEARCH_SWOOP_WORKERS": os.environ.get("SEARCH_SWOOP_WORKERS", "4"),
            "SEARCH_OUTPUT_PATH": str(out_path),
            "PYTHONPATH": str(ROOT / "flight-monitor") + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )
    timeout = int(os.environ.get("SEARCH_JOB_TIMEOUT", "1500"))
    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(SEARCH_SCRIPT)],
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "Falha na pesquisa")[-1500:])
        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError("A pesquisa terminou sem gerar resultado.")
        result = json.loads(out_path.read_text(encoding="utf-8"))
        with LOCK:
            JOBS[job_id].update(
                {
                    "status": "done",
                    "result": result,
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "finished_epoch": time.time(),
                    "elapsed_seconds": round(time.time() - started, 1),
                }
            )
    except subprocess.TimeoutExpired:
        with LOCK:
            JOBS[job_id].update(
                {
                    "status": "error",
                    "error": "A pesquisa excedeu o tempo máximo. Tente uma faixa menor de dias.",
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "finished_epoch": time.time(),
                }
            )
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(
                {
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                    "finished_epoch": time.time(),
                }
            )
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.get("/health")
def health() -> dict[str, Any]:
    with LOCK:
        running = sum(1 for j in JOBS.values() if j.get("status") in {"queued", "running"})
    return {"ok": True, "service": "flight-month-search", "running": running}


@app.post("/api/search")
def start_search(req: SearchRequest) -> dict[str, Any]:
    payload = _normalize(req)
    key = _key(payload)
    with LOCK:
        _cleanup()
        existing_id = KEY_TO_JOB.get(key)
        if existing_id and existing_id in JOBS:
            existing = JOBS[existing_id]
            if existing.get("status") in {"queued", "running", "done"}:
                return {
                    "job_id": existing_id,
                    "status": existing.get("status"),
                    "cached": existing.get("status") == "done",
                }
        job_id = uuid.uuid4().hex[:16]
        JOBS[job_id] = {
            "job_id": job_id,
            "key": key,
            "status": "queued",
            "request": payload,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "created_epoch": time.time(),
        }
        KEY_TO_JOB[key] = job_id
    thread = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    thread.start()
    return {"job_id": job_id, "status": "queued", "cached": False}


@app.get("/api/search/{job_id}")
def get_search(job_id: str) -> dict[str, Any]:
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Pesquisa não encontrada ou expirada.")
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
        if job.get("status") == "error":
            response["error"] = job.get("error")
        return response
