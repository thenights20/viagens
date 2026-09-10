from __future__ import annotations

import argparse
import copy
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


def _rotate(values: list, take: int, slot: int) -> list:
    if not values or take <= 0 or len(values) <= take:
        return list(values)
    start = (slot * take) % len(values)
    return [values[(start + i) % len(values)] for i in range(take)]


def tune_for_online(config: dict) -> dict:
    """Mantém cobertura ampla, mas divide buscas pesadas entre as execuções horárias."""
    tuned = copy.deepcopy(config)
    slot = int(datetime.now(timezone.utc).timestamp() // 3600)

    ml = tuned.setdefault("mercadolivre", {})
    ml["max_queries"] = min(int(ml.get("max_queries", 30)), 12)
    ml["priority_watchlist_limit"] = min(int(ml.get("priority_watchlist_limit", 14)), 7)
    ml["limit_per_query"] = min(int(ml.get("limit_per_query", 40)), 30)

    shopee = tuned.setdefault("shopee", {})
    shopee["scrolls"] = min(int(shopee.get("scrolls", 6)), 3)

    casas = tuned.setdefault("casas_bahia", {})
    casas_queries = list(casas.get("queries", tuned.get("queries", [])))
    casas["queries"] = _rotate(casas_queries, 6, slot)
    casas["max_candidates_per_query"] = min(int(casas.get("max_candidates_per_query", 5)), 4)

    for index, retailer in enumerate(tuned.get("retailers", [])):
        retailer["scrolls"] = min(int(retailer.get("scrolls", 3)), 2)
        retailer["max_items"] = min(int(retailer.get("max_items", 90)), 80)
        retailer["max_seller_checks"] = min(int(retailer.get("max_seller_checks", 36)), 12)
        queries = list(retailer.get("queries", []))
        if queries:
            selected = _rotate(queries, min(6, len(queries)), slot + index)
            retailer["queries"] = selected
            retailer["max_queries"] = len(selected)

    tuned["revalidation_limit"] = min(int(tuned.get("revalidation_limit", 24)), 8)
    return tuned


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

    original_config = load_config(config_path)
    config = tune_for_online(original_config)
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
    for anomaly in anomalies[: int(config.get("revalidation_limit", 8))]:
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
    watchlist = [x for x in original_config.get("watchlist", []) if isinstance(x, dict)]
    products = product_rows(
        offers,
        history,
        active_urls,
        watchlist,
        int(original_config.get("product_output_limit", 600)),
    )

    save_history(history_path, update_history(history, offers))
    now = datetime.now(timezone.utc)
    configured = [str(x) for x in original_config.get("configured_sources", []) if x]
    found_sources = sorted({x["source"] for x in products})
    categories = sorted({x["category"] for x in products})

    for name in configured:
        source_health.setdefault(name, {"ok": False, "message": "sem resultado nesta execução", "items": 0})

    payload = {
        "version": "0.5.1",
        "generated_at": now.isoformat(),
        "timezone_hint": "America/Campo_Grande",
        "preview": False,
        "online": True,
        "rotation": True,
        "active_count": len(active),
        "observed_count": len(offers),
        "product_count": len(products),
        "tracked_count": sum(1 for x in products if x["tracked"]),
        "configured_source_count": len(configured),
        "responding_source_count": sum(1 for v in source_health.values() if v.get("ok")),
        "source_health": source_health,
        "thresholds": original_config.get("thresholds", {}),
        "filters": {"sources": configured or found_sources, "categories": categories},
        "watchlist": public_watchlist(original_config),
        "products": products,
        "active": active,
        "notes": [
            "Atualização executada inteiramente nos servidores do GitHub.",
            "As buscas mais pesadas são rotacionadas entre as execuções horárias para manter boa cobertura sem travar a rodada.",
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
