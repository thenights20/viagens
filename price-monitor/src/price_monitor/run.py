from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .detector import detect_anomalies
from .history import load_history, save_history, update_history
from .models import Offer
from .sources import CasasBahiaSource, MercadoLivreSource, ShopeeSource


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Monitor de preços anormalmente baixos em lojas oficiais.")
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--history", required=True)
    p.add_argument("--skip-browser", action="store_true")
    return p.parse_args()


def build_sources(config: dict, skip_browser: bool):
    queries = config.get("queries", [])
    sources = [
        MercadoLivreSource(
            queries=queries,
            limit_per_query=int(config.get("mercadolivre", {}).get("limit_per_query", 50)),
        )
    ]
    if not skip_browser:
        sources.extend(
            [
                ShopeeSource(
                    shops=config.get("shopee", {}).get("official_shops", []),
                    scrolls=int(config.get("shopee", {}).get("scrolls", 5)),
                ),
                CasasBahiaSource(
                    queries=queries,
                    max_candidates_per_query=int(
                        config.get("casas_bahia", {}).get("max_candidates_per_query", 6)
                    ),
                ),
            ]
        )
    return sources


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    output_path = Path(args.output)
    history_path = Path(args.history)

    config = load_config(config_path)
    history = load_history(history_path)

    offers: list[Offer] = []
    source_health: dict[str, dict] = {}
    source_objects = {}

    for source in build_sources(config, args.skip_browser):
        source_objects[source.name] = source
        try:
            found = source.collect()
            offers.extend(found)
        except Exception as exc:
            source.health = {
                "ok": False,
                "message": f"erro não tratado: {type(exc).__name__}: {exc}",
                "items": 0,
            }
        source_health[source.name] = source.health
        print(f"[{source.name}] {source.health}", flush=True)

    thresholds = config.get("thresholds", {})
    anomalies = detect_anomalies(offers, history, **thresholds)

    active: list[dict] = []
    revalidation_limit = int(config.get("revalidation_limit", 12))
    for anomaly in anomalies[:revalidation_limit]:
        source = source_objects.get(anomaly.offer.source)
        if source is None:
            continue
        try:
            ok, note = source.revalidate(anomaly.offer)
        except Exception as exc:
            ok, note = False, f"erro ao revalidar: {type(exc).__name__}"
        anomaly.revalidated = ok
        anomaly.verification_note = note
        anomaly.offer.available = anomaly.offer.available and ok
        if ok:
            active.append(anomaly.to_dict())

    history = update_history(history, offers)
    save_history(history_path, history)

    now = datetime.now(timezone.utc)
    payload = {
        "version": "0.1.0",
        "generated_at": now.isoformat(),
        "timezone_hint": "America/Campo_Grande",
        "active_count": len(active),
        "observed_count": len(offers),
        "source_health": source_health,
        "thresholds": thresholds,
        "active": active,
        "notes": [
            "A lista mostra somente anomalias revalidadas como ativas.",
            "Loja oficial é requisito obrigatório; se a verificação falhar, o item não aparece.",
            "Possível bug é uma anomalia estatística, não uma confirmação de erro pela loja.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"Concluído: {len(offers)} ofertas oficiais observadas; "
        f"{len(active)} possíveis bugs ativos revalidados.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
