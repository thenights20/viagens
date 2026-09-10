from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .detector import detect_anomalies
from .history import load_history, save_history, update_history
from .models import Offer
from .run import build_sources, product_rows, public_watchlist


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Atualização online do acompanhamento pessoal.")
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--history", required=True)
    p.add_argument("--workers", type=int, default=3)
    return p.parse_args()


def collect_one(source):
    try:
        found = source.collect()
        return source, found, source.health
    except Exception as exc:
        source.health = {
            "ok": False,
            "message": f"erro não tratado: {type(exc).__name__}: {exc}",
            "items": 0,
        }
        return source, [], source.health


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    output_path = Path(args.output)
    history_path = Path(args.history)

    config = load_config(config_path)
    history = load_history(history_path)
    sources = build_sources(config, skip_browser=False)

    offers: list[Offer] = []
    source_health: dict[str, dict] = {}
    source_objects = {source.name: source for source in sources}

    workers = max(1, min(int(args.workers), 4))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(collect_one, source): source.name for source in sources}
        for future in as_completed(futures):
            source, found, health = future.result()
            offers.extend(found)
            source_health[source.name] = health
            print(f"[{source.name}] {health}", flush=True)

    anomalies = detect_anomalies(offers, history, **config.get("thresholds", {}))
    active: list[dict] = []
    revalidation_limit = min(int(config.get("revalidation_limit", 24)), 12)
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

    active_urls = {str(x.get("url")) for x in active if x.get("url")}
    watchlist = [x for x in config.get("watchlist", []) if isinstance(x, dict)]
    products = product_rows(
        offers,
        history,
        active_urls,
        watchlist,
        int(config.get("product_output_limit", 600)),
    )

    save_history(history_path, update_history(history, offers))
    now = datetime.now(timezone.utc)
    configured = [str(x) for x in config.get("configured_sources", []) if x]
    found_sources = sorted({x["source"] for x in products})
    categories = sorted({x["category"] for x in products})

    # Inclui no diagnóstico fontes configuradas que, por algum motivo, não chegaram a ser instanciadas.
    for name in configured:
        source_health.setdefault(name, {"ok": False, "message": "sem resultado nesta execução", "items": 0})

    payload = {
        "version": "0.5.0",
        "generated_at": now.isoformat(),
        "timezone_hint": "America/Campo_Grande",
        "preview": False,
        "online": True,
        "active_count": len(active),
        "observed_count": len(offers),
        "product_count": len(products),
        "tracked_count": sum(1 for x in products if x["tracked"]),
        "configured_source_count": len(configured),
        "responding_source_count": sum(1 for v in source_health.values() if v.get("ok")),
        "source_health": source_health,
        "thresholds": config.get("thresholds", {}),
        "filters": {"sources": configured or found_sources, "categories": categories},
        "watchlist": public_watchlist(config),
        "products": products,
        "active": active,
        "notes": [
            "Atualização executada inteiramente nos servidores do GitHub.",
            "Uma fonte que bloqueie a consulta não impede a atualização das demais.",
            "Os destaques mais fortes passam por uma segunda verificação antes da confirmação adicional.",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Concluído: {len(offers)} observados; {len(products)} listados; "
        f"{payload['responding_source_count']}/{len(configured)} fontes responderam; "
        f"{len(active)} destaques revalidados.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
