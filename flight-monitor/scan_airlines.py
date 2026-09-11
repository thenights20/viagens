from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from airlines import collect_official_airline_offers

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "flight-monitor" / "config.json"
OUTPUT_PATH = ROOT / "docs" / "data" / "airlines.json"


def load_json(path: Path, fallback: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    config = load_json(CONFIG_PATH, {})
    if not config:
        raise SystemExit("flight-monitor/config.json não encontrado")

    now = datetime.now(timezone.utc)
    offers, health = collect_official_airline_offers(config)
    payload = {
        "version": "0.1.0",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": "Páginas públicas oficiais GOL + Azul + LATAM",
        "offer_count": len(offers),
        "domestic_count": sum(1 for x in offers if x.get("scope") == "domestic"),
        "international_count": sum(1 for x in offers if x.get("scope") == "international"),
        "source_count": len(health),
        "responding_source_count": sum(1 for x in health.values() if x.get("ok")),
        "sources": health,
        "offers": offers,
    }
    save_json(OUTPUT_PATH, payload)
    summary = ", ".join(
        f"{name}: {info.get('items', 0)}" + ("" if info.get("ok") else " (indisponível)")
        for name, info in health.items()
    )
    print(f"Companhias: {len(offers)} ofertas monitoradas. {summary}")


if __name__ == "__main__":
    main()
