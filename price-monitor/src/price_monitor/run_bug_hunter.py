from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .bug_rules import score_product
from .fast_market_scan import revalidate_candidate, scan_markets
from .product_sensors import build_sensor_feed


ROOT = Path(__file__).resolve().parents[3]
CURRENT_PATH = ROOT / "docs" / "data" / "current.json"
BUG_OUTPUT = ROOT / "docs" / "data" / "product-bugs.json"
SENSOR_OUTPUT = ROOT / "docs" / "data" / "product-sensors.json"
STATE_PATH = ROOT / "price-monitor" / "data" / "bug-hunter-state.json"


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(row: dict) -> str:
    url = str(row.get("url") or "").split("?")[0]
    if url:
        return f"url:{url}"
    title = re.sub(r"\W+", " ", str(row.get("title") or "").lower()).strip()
    return f"title:{row.get('source')}:{title[:160]}"


def _from_current(current: dict) -> list[dict]:
    rows: list[dict] = []
    for product in current.get("products", []):
        score = score_product(
            title=str(product.get("title") or ""),
            price=float(product.get("price") or 0),
            reference_price=product.get("reference_price"),
            original_price=product.get("original_price"),
            source=str(product.get("source") or ""),
            trusted=bool(product.get("strict_highlight") or product.get("store_name")),
            revalidated=bool(product.get("strict_highlight")),
        )
        if int(score.get("bug_score", 0)) < 60:
            continue
        rows.append({
            "source": product.get("source"),
            "store_name": product.get("store_name") or product.get("source"),
            "title": product.get("title"),
            "price": product.get("price"),
            "original_price": product.get("original_price"),
            "reference_price": product.get("reference_price"),
            "url": product.get("url"),
            "category": product.get("category") or score.get("category"),
            "available": True,
            "trusted": True,
            "revalidated": bool(product.get("strict_highlight")),
            "collector": "radar-historico",
            "collected_at": product.get("collected_at"),
            **score,
        })
    return rows


def _from_sensors(sensor_feed: dict) -> list[dict]:
    rows: list[dict] = []
    for signal in sensor_feed.get("signals", []):
        if signal.get("kind") != "product" or not signal.get("price"):
            continue
        score = score_product(
            title=str(signal.get("title") or ""),
            price=float(signal.get("price") or 0),
            source=str(signal.get("store_hint") or signal.get("source") or ""),
            external_bug_signal=bool(signal.get("external_bug")),
        )
        # Sensor é pista, não confirmação. Mantém sinais marcados como BUG ou muito extremos.
        if not signal.get("external_bug") and int(score.get("bug_score", 0)) < 70:
            continue
        rows.append({
            "source": signal.get("store_hint") or "Sensor externo",
            "store_name": signal.get("store_hint") or "Sensor externo",
            "title": signal.get("title"),
            "price": signal.get("price"),
            "url": signal.get("url"),
            "post_url": signal.get("post_url"),
            "coupon": signal.get("coupon"),
            "category": score.get("category"),
            "available": True,
            "trusted": False,
            "revalidated": False,
            "collector": "sensor-La-Promotion",
            "external_source": "La Promotion",
            "external_bug": bool(signal.get("external_bug")),
            "published_at": signal.get("published_at"),
            "collected_at": signal.get("collected_at"),
            **score,
        })
    return rows


def _revalidate(rows: list[dict], limit: int = 8) -> tuple[list[dict], list[str]]:
    targets = [x for x in rows if x.get("collector") == "fast-market-scan" and int(x.get("bug_score", 0)) >= 70]
    targets.sort(key=lambda x: (-int(x.get("bug_score", 0)), float(x.get("price") or 999999)))
    selected = targets[:limit]
    if not selected:
        return rows, []
    errors: list[str] = []
    by_key = {_key(x): x for x in rows}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(revalidate_candidate, dict(row)): row for row in selected}
        for future in as_completed(futures):
            original = futures[future]
            try:
                checked, error = future.result()
            except Exception as exc:  # noqa: BLE001
                checked, error = original, f"{type(exc).__name__}: {exc}"
            by_key[_key(original)] = checked
            if error:
                errors.append(f"{original.get('source')} · {original.get('title')}: {error}")
    return list(by_key.values()), errors


def _best_rows(rows: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for row in rows:
        if not row.get("url") or float(row.get("price") or 0) <= 0:
            continue
        key = _key(row)
        old = best.get(key)
        rank = (int(row.get("bug_score", 0)), int(bool(row.get("revalidated"))), -float(row.get("price") or 0))
        old_rank = (-1, -1, 0) if old is None else (int(old.get("bug_score", 0)), int(bool(old.get("revalidated"))), -float(old.get("price") or 0))
        if old is None or rank > old_rank:
            best[key] = row
    out = list(best.values())
    out.sort(key=lambda x: (-int(x.get("bug_score", 0)), not bool(x.get("revalidated")), float(x.get("price") or 999999)))
    return out


def main() -> int:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")
    slot = int(now.timestamp() // (15 * 60))

    current = load_json(CURRENT_PATH, {"products": []})
    state = load_json(STATE_PATH, {"version": "0.1.0", "items": {}, "run_counter": 0})
    state.setdefault("items", {})

    sensor_feed = build_sensor_feed()
    save_json(SENSOR_OUTPUT, sensor_feed)

    scan_rows, source_health = scan_markets(slot)
    combined = [*_from_current(current), *scan_rows, *_from_sensors(sensor_feed)]
    combined, validation_errors = _revalidate(combined)
    current_best = _best_rows(combined)

    for row in current_best:
        key = _key(row)
        previous = state["items"].get(key)
        row["first_seen"] = previous.get("first_seen") if previous else now_iso
        row["last_seen"] = now_iso
        row["sightings"] = int(previous.get("sightings", 0)) + 1 if previous else 1
        row["fresh"] = previous is None
        state["items"][key] = row

    cutoff = now - timedelta(hours=4)
    for key, row in list(state["items"].items()):
        try:
            stamp = datetime.fromisoformat(str(row.get("last_seen") or "").replace("Z", "+00:00"))
        except ValueError:
            state["items"].pop(key, None)
            continue
        if stamp < cutoff:
            state["items"].pop(key, None)

    active = _best_rows(list(state["items"].values()))[:180]
    confirmed = [x for x in active if x.get("revalidated") and int(x.get("bug_score", 0)) >= 70]
    sensor_bugs = [x for x in active if x.get("external_source") == "La Promotion"]

    state["run_counter"] = int(state.get("run_counter", 0)) + 1
    state["last_run"] = now_iso
    output = {
        "version": "0.1.0",
        "generated_at": now_iso,
        "scan_interval_minutes": 15,
        "active_hours": 4,
        "active_count": len(active),
        "strong_count": sum(1 for x in active if int(x.get("bug_score", 0)) >= 70),
        "critical_count": sum(1 for x in active if int(x.get("bug_score", 0)) >= 90),
        "confirmed_count": len(confirmed),
        "sensor_bug_count": len(sensor_bugs),
        "scanner_count": len(scan_rows),
        "queries_this_run": sorted({str(x.get("search_query")) for x in scan_rows if x.get("search_query")}),
        "source_health": source_health,
        "validation_errors": validation_errors[:20],
        "bugs": active,
    }
    save_json(STATE_PATH, state)
    save_json(BUG_OUTPUT, output)
    print(
        f"Bug Hunter: {len(scan_rows)} candidatos do scanner; {len(active)} ativos; "
        f"{output['strong_count']} score 70+; {len(confirmed)} confirmados; "
        f"{sensor_feed.get('signal_count', 0)} sinais externos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
