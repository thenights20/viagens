from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from .config import load_config
from .detector import detect_anomalies
from .history import historical_median, load_history, save_history, update_history
from .models import Offer
from .sources import CasasBahiaSource, MercadoLivreSource, RetailerSource, ShopeeSource
from .utils import normalize_text


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ferramenta pessoal de acompanhamento de ofertas públicas.")
    p.add_argument("--config", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--history", required=True)
    p.add_argument("--skip-browser", action="store_true")
    return p.parse_args()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        value = str(value or "").strip()
        key = normalize_text(value)
        if value and key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def build_sources(config: dict, skip_browser: bool):
    broad_queries = [str(x) for x in config.get("queries", []) if x]
    watchlist = [x for x in config.get("watchlist", []) if isinstance(x, dict)]
    ml_cfg = config.get("mercadolivre", {})
    priority_limit = int(ml_cfg.get("priority_watchlist_limit", 12))
    priority_queries = [
        str(x.get("query") or x.get("name") or "")
        for x in watchlist
        if x.get("priority")
    ][:priority_limit]
    ml_queries = _unique(priority_queries + broad_queries)[: int(ml_cfg.get("max_queries", 30))]

    sources = [
        MercadoLivreSource(
            queries=ml_queries,
            official_stores=ml_cfg.get("official_stores", []),
            limit_per_query=int(ml_cfg.get("limit_per_query", 40)),
        )
    ]
    if not skip_browser:
        cb_cfg = config.get("casas_bahia", {})
        sources.extend(
            [
                ShopeeSource(
                    shops=config.get("shopee", {}).get("official_shops", []),
                    scrolls=int(config.get("shopee", {}).get("scrolls", 5)),
                ),
                CasasBahiaSource(
                    queries=cb_cfg.get("queries", broad_queries),
                    max_candidates_per_query=int(cb_cfg.get("max_candidates_per_query", 6)),
                ),
            ]
        )
        for retailer in config.get("retailers", []):
            if retailer.get("enabled", True):
                sources.append(RetailerSource(retailer))
    return sources


def category_for(title: str) -> str:
    text = normalize_text(title)
    rules = [
        ("Smartphones", ("iphone", "smartphone", "galaxy s", "galaxy a", "moto g", "motorola edge")),
        ("Notebooks", ("notebook", "macbook", "laptop", "predator", "nitro v")),
        ("Placas de vídeo", ("rtx ", "geforce", "radeon rx", "placa de video")),
        ("Processadores", ("ryzen", "core i5", "core i7", "core i9", "processador")),
        ("Monitores", ("monitor",)),
        ("TVs", ("smart tv", " tv ", "oled", "qned", "qled", "mini led")),
        ("Consoles", ("playstation", "ps5", "xbox series", "steam deck", "nintendo switch")),
        ("Smartwatches", ("watch", "smartwatch")),
        ("Armazenamento", ("ssd", "nvme", "hd externo")),
        ("Áudio", ("boombox", "partybox", "caixa de som", "soundbar")),
        ("Climatização", ("ar condicionado", "climatizador")),
        ("Eletrodomésticos", ("geladeira", "refrigerador", "lava e seca", "lavadora", "cooktop", "fogao")),
        ("Drones e câmeras", ("dji", "drone", "camera canon", "camera sony", "gopro")),
        ("Casa", ("aspirador robo", "robot vacuum")),
        ("Eletrônicos", ("starlink",)),
    ]
    padded = f" {text} "
    for category, words in rules:
        if any(word in padded for word in words):
            return category
    return "Outros"


def watch_matches(title: str, watchlist: list[dict]) -> list[dict]:
    text = normalize_text(title)
    text_tokens = set(text.split())
    matches: list[dict] = []
    ignored = {"de", "da", "do", "com", "e", "para", "polegadas"}
    for item in watchlist:
        query = normalize_text(str(item.get("query") or item.get("name") or ""))
        if not query:
            continue
        tokens = [t for t in query.split() if t not in ignored and len(t) > 1]
        # SKU/modelos exatos continuam fortes; para nomes longos tolera até um termo ausente.
        required = len(tokens) if len(tokens) <= 3 else len(tokens) - 1
        score = sum(1 for token in tokens if token in text_tokens or token in text)
        if query in text or (tokens and score >= required):
            matches.append(item)
    return matches


def product_rows(offers: list[Offer], history: dict, active_urls: set[str], watchlist: list[dict], limit: int) -> list[dict]:
    groups: dict[str, list[float]] = defaultdict(list)
    for offer in offers:
        if offer.official and offer.available and offer.price > 0 and offer.product_key:
            groups[offer.product_key].append(float(offer.price))

    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for offer in offers:
        if not offer.official or not offer.available or offer.price <= 0:
            continue
        ident = (offer.source, offer.url)
        if ident in seen:
            continue
        seen.add(ident)

        reference = None
        reference_kind = None
        samples = 0
        market_prices = groups.get(offer.product_key, [])
        if len(market_prices) >= 3:
            reference = float(median(market_prices))
            reference_kind = "referência atual"
            samples = len(market_prices)

        hist, hist_samples = historical_median(history, offer.product_key, min_samples=5)
        if hist and (reference is None or hist > reference):
            reference = hist
            reference_kind = "histórico observado"
            samples = hist_samples

        if offer.original_price and offer.original_price > offer.price and (reference is None or offer.original_price > reference):
            reference = float(offer.original_price)
            reference_kind = "preço anterior anunciado"
            samples = 1

        difference_pct = 0.0
        savings = 0.0
        if reference and reference > offer.price:
            savings = reference - offer.price
            difference_pct = (1.0 - offer.price / reference) * 100.0

        matches = watch_matches(offer.title, watchlist)
        tracked = bool(matches)
        highlighted = offer.url in active_urls or (difference_pct >= 30 and savings >= 200)
        rows.append(
            {
                "title": offer.title,
                "source": offer.source,
                "store_name": offer.store_name,
                "price": round(float(offer.price), 2),
                "original_price": round(float(offer.original_price), 2) if offer.original_price else None,
                "reference_price": round(float(reference), 2) if reference else None,
                "reference_kind": reference_kind,
                "reference_samples": samples,
                "difference_pct": round(difference_pct, 1),
                "savings": round(savings, 2),
                "url": offer.url,
                "category": category_for(offer.title),
                "tracked": tracked,
                "watch_terms": [str(x.get("name") or x.get("query")) for x in matches[:3]],
                "highlighted": highlighted,
                "strict_highlight": offer.url in active_urls,
                "collected_at": offer.collected_at,
            }
        )

    rows.sort(key=lambda x: (not x["strict_highlight"], not x["highlighted"], not x["tracked"], -x["difference_pct"], x["price"]))
    return rows[: max(1, limit)]


def public_watchlist(config: dict) -> list[dict]:
    return [
        {
            "name": str(x.get("name") or x.get("query") or ""),
            "query": str(x.get("query") or ""),
            "category": str(x.get("category") or "Outros"),
        }
        for x in config.get("watchlist", [])
        if isinstance(x, dict) and (x.get("name") or x.get("query"))
    ]


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
            offers.extend(source.collect())
        except Exception as exc:
            source.health = {"ok": False, "message": f"erro não tratado: {type(exc).__name__}: {exc}", "items": 0}
        source_health[source.name] = source.health
        print(f"[{source.name}] {source.health}", flush=True)

    anomalies = detect_anomalies(offers, history, **config.get("thresholds", {}))
    active: list[dict] = []
    for anomaly in anomalies[: int(config.get("revalidation_limit", 24))]:
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
    watch_public = public_watchlist(config)

    save_history(history_path, update_history(history, offers))
    now = datetime.now(timezone.utc)
    sources = sorted({x["source"] for x in products})
    categories = sorted({x["category"] for x in products})
    payload = {
        "version": "0.4.0",
        "generated_at": now.isoformat(),
        "timezone_hint": "America/Campo_Grande",
        "preview": False,
        "active_count": len(active),
        "observed_count": len(offers),
        "product_count": len(products),
        "tracked_count": sum(1 for x in products if x["tracked"]),
        "source_health": source_health,
        "thresholds": config.get("thresholds", {}),
        "filters": {"sources": sources, "categories": categories},
        "watchlist": watch_public,
        "products": products,
        "active": active,
        "notes": [
            "A página principal reúne os produtos observados e permite aplicar filtros locais.",
            "Itens da lista de vistoria recebem prioridade, mas a coleta também procura famílias próximas.",
            "Os destaques mais fortes continuam passando por uma segunda verificação antes de receber confirmação adicional.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Concluído: {len(offers)} observados; {len(products)} listados; {len(active)} destaques revalidados.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
