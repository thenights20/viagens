from __future__ import annotations

import json
from pathlib import Path


DEFAULTS = {
    "queries": [
        "iphone", "macbook", "notebook gamer", "rtx 5070", "tv oled",
        "tv 65 4k", "geladeira", "lava e seca", "ar condicionado",
        "playstation 5", "xbox series x", "drone dji"
    ],
    "thresholds": {
        "max_ratio": 0.55,
        "min_savings": 1000,
        "min_baseline": 2000,
        "weak_max_ratio": 0.35,
        "weak_min_savings": 2000,
        "weak_min_baseline": 3000
    },
}


def _unique_strings(values: list) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _merge_watchlist(base: list, extra: list) -> list[dict]:
    """Mescla itens pelo nome; o arquivo extra pode atualizar um item já existente."""
    merged: dict[str, dict] = {}
    order: list[str] = []
    for row in [*base, *extra]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key not in merged:
            order.append(key)
            merged[key] = {}
        merged[key].update(row)
    return [merged[key] for key in order]


def _load_extra(path: Path) -> dict:
    extra_path = path.with_name("watchlist_extra.json")
    if not extra_path.exists():
        return {}
    try:
        data = json.loads(extra_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_config(path: Path) -> dict:
    config = dict(DEFAULTS)
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        config.update(user)
        thresholds = dict(DEFAULTS["thresholds"])
        thresholds.update(user.get("thresholds", {}))
        config["thresholds"] = thresholds

    extra = _load_extra(path)
    if extra:
        extra_watch = [x for x in extra.get("watchlist", []) if isinstance(x, dict)]
        config["watchlist"] = _merge_watchlist(
            [x for x in config.get("watchlist", []) if isinstance(x, dict)],
            extra_watch,
        )

        extra_queries = [str(x.get("query") or "").strip() for x in extra_watch]
        extra_queries.extend(str(x) for x in extra.get("queries", []) if x)
        extra_queries = _unique_strings(extra_queries)
        config["queries"] = _unique_strings([*config.get("queries", []), *extra_queries])

        casas = config.get("casas_bahia")
        if isinstance(casas, dict):
            casas["queries"] = _unique_strings([*casas.get("queries", []), *extra_queries])

        # Varejistas com mecanismo de pesquisa recebem os novos termos.
        for retailer in config.get("retailers", []):
            if not isinstance(retailer, dict) or not retailer.get("search_url_template"):
                continue
            retailer["queries"] = _unique_strings([*retailer.get("queries", []), *extra_queries])

    return config
