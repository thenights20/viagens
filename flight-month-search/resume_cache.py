from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import date, datetime, timezone

RESUME_WINDOW_SECONDS = 60 * 60
CHECKPOINT_DIR = "docs/data/flight-search-checkpoints"
CHECKPOINT_SECONDS = 6
CHECKPOINT_RECORDS = 8


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def combo_key(dep: date | str, ret: date | str) -> str:
    dep_s = dep.isoformat() if isinstance(dep, date) else str(dep)
    ret_s = ret.isoformat() if isinstance(ret, date) else str(ret)
    return f"{dep_s}|{ret_s}"


def search_signature(*, origin: str, destination: str, start_date: date, end_date: date, max_stops: int) -> tuple[str, str]:
    raw = "|".join([
        origin.upper(), destination.upper(), start_date.isoformat(), end_date.isoformat(), str(int(max_stops)), "BRL", "economy", "1",
    ])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return raw, digest


class FlightResumeCache:
    """Persist per-combination checkpoints on the flight-live branch.

    A successful query with no fare is a completed combination and can be reused.
    A provider/network error is stored for diagnostics but is intentionally retried.
    Reuse is limited to combinations completed less than one hour ago.
    """

    def __init__(self, publisher, *, origin: str, destination: str, start_date: date, end_date: date, max_stops: int) -> None:
        self.publisher = publisher
        self.signature, self.cache_id = search_signature(
            origin=origin,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            max_stops=max_stops,
        )
        self.path = f"{CHECKPOINT_DIR}/{self.cache_id}.json"
        self.request = {
            "origin": origin,
            "destination": destination,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "max_stops": int(max_stops),
            "currency": "BRL",
        }
        self.data = self._blank()
        self._last_save = 0.0
        self._last_saved_records = 0

    def _blank(self) -> dict:
        now = iso_now()
        return {
            "version": 1,
            "cache_id": self.cache_id,
            "signature": self.signature,
            "created_at": now,
            "updated_at": now,
            "resume_window_minutes": 60,
            "request": self.request,
            "pairs": {},
        }

    def _read_remote(self) -> dict | None:
        if not self.publisher.ensure_branch():
            return None
        code, raw = self.publisher._request("GET", f"/contents/{self.path}?ref={self.publisher.branch}")
        if code != 200 or not raw:
            return None
        try:
            content = base64.b64decode(raw.get("content") or "").decode("utf-8")
            data = json.loads(content)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def load(self) -> dict:
        remote = self._read_remote()
        if remote and remote.get("signature") == self.signature and isinstance(remote.get("pairs"), dict):
            self.data = remote
        else:
            self.data = self._blank()
        self._last_saved_records = len(self.data.get("pairs") or {})
        return self.data

    def _fresh(self, record: dict, now: datetime | None = None) -> bool:
        completed = parse_iso(record.get("completed_at"))
        if not completed:
            return False
        now = now or utc_now()
        return 0 <= (now - completed).total_seconds() <= RESUME_WINDOW_SECONDS

    def reusable_records(self) -> dict[str, dict]:
        now = utc_now()
        reusable: dict[str, dict] = {}
        for key, record in (self.data.get("pairs") or {}).items():
            if record.get("status") not in {"priced", "no_price"}:
                continue
            if self._fresh(record, now):
                reusable[key] = record
        return reusable

    def reusable_rows(self) -> list[dict]:
        rows: list[dict] = []
        for record in self.reusable_records().values():
            row = record.get("row")
            if record.get("status") == "priced" and isinstance(row, dict):
                rows.append(dict(row))
        return rows

    def record(self, dep: date, ret: date, *, row: dict | None, errors: list[str] | None, source: str) -> None:
        errors = [str(e) for e in (errors or []) if e]
        if errors:
            status = "error"
        elif row:
            status = "priced"
        else:
            status = "no_price"
        self.data.setdefault("pairs", {})[combo_key(dep, ret)] = {
            "departure_date": dep.isoformat(),
            "return_date": ret.isoformat(),
            "status": status,
            "completed_at": iso_now(),
            "source": source,
            "row": dict(row) if row and status == "priced" else None,
            "errors": errors[-4:],
        }
        self.data["updated_at"] = iso_now()

    def counts(self) -> dict[str, int]:
        pairs = self.data.get("pairs") or {}
        fresh = self.reusable_records()
        return {
            "saved_records": len(pairs),
            "reusable": len(fresh),
            "priced": sum(1 for r in fresh.values() if r.get("status") == "priced"),
            "no_price": sum(1 for r in fresh.values() if r.get("status") == "no_price"),
            "errors": sum(1 for r in pairs.values() if r.get("status") == "error"),
        }

    def save(self, *, force: bool = False) -> bool:
        if not self.publisher.ensure_branch():
            return False
        now_mono = time.monotonic()
        count = len(self.data.get("pairs") or {})
        if not force and now_mono - self._last_save < CHECKPOINT_SECONDS and count - self._last_saved_records < CHECKPOINT_RECORDS:
            return False
        self.data["updated_at"] = iso_now()
        for _ in range(4):
            code, current = self.publisher._request("GET", f"/contents/{self.path}?ref={self.publisher.branch}")
            sha = current.get("sha") if code == 200 and current else None
            body = {
                "message": f"checkpoint: {self.cache_id} {count} pares",
                "content": base64.b64encode(json.dumps(self.data, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
                "branch": self.publisher.branch,
            }
            if sha:
                body["sha"] = sha
            code, _ = self.publisher._request("PUT", f"/contents/{self.path}", body)
            if code in (200, 201):
                self._last_save = now_mono
                self._last_saved_records = count
                return True
            if code not in (409, 422):
                break
            time.sleep(0.8)
        return False
