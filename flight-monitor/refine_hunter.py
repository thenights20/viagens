from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "flight-monitor" / "data" / "hunter-state.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "deal-hunter.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def stamp(value: str | None) -> datetime:
    return datetime.fromisoformat(str(value or "1970-01-01T00:00:00+00:00").replace("Z", "+00:00"))


def route_key(row: dict) -> str:
    return f"{row.get('origin', '')}-{row.get('destination', '')}"


def main() -> None:
    state = load(STATE_PATH)
    output = load(OUTPUT_PATH)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=3)
    fresh_cutoff = now - timedelta(minutes=30)

    items = state.setdefault("items", {})
    for key, row in list(items.items()):
        try:
            if stamp(row.get("last_seen")) < cutoff:
                items.pop(key, None)
        except (TypeError, ValueError):
            items.pop(key, None)

    best_by_route: dict[str, dict] = {}
    for row in items.values():
        try:
            row["fresh"] = stamp(row.get("first_seen")) >= fresh_cutoff
        except (TypeError, ValueError):
            row["fresh"] = False
        key = route_key(row)
        current = best_by_route.get(key)
        candidate_rank = (
            int(row.get("hunter_score", 0)),
            -float(row.get("price") or 999999),
            stamp(row.get("last_seen")).timestamp(),
        )
        if current is None:
            best_by_route[key] = row
            continue
        current_rank = (
            int(current.get("hunter_score", 0)),
            -float(current.get("price") or 999999),
            stamp(current.get("last_seen")).timestamp(),
        )
        if candidate_rank > current_rank:
            best_by_route[key] = row

    deals = sorted(
        best_by_route.values(),
        key=lambda x: (-int(x.get("hunter_score", 0)), float(x.get("price") or 999999)),
    )
    output["active_window_hours"] = 3
    output["state_itinerary_count"] = len(items)
    output["active_count"] = len(deals)
    output["exceptional_count"] = sum(1 for x in deals if int(x.get("hunter_score", 0)) >= 80)
    output["very_cheap_count"] = sum(1 for x in deals if int(x.get("hunter_score", 0)) >= 70)
    output["deals"] = deals[:120]
    save(STATE_PATH, state)
    save(OUTPUT_PATH, output)
    print(
        "Deal Hunter refinado:",
        len(items), "itinerários recentes;",
        len(deals), "rotas únicas;",
        output["exceptional_count"], "Score 80+",
    )


if __name__ == "__main__":
    main()
