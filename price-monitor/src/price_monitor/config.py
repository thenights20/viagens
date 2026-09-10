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


def load_config(path: Path) -> dict:
    config = dict(DEFAULTS)
    if path.exists():
        user = json.loads(path.read_text(encoding="utf-8"))
        config.update(user)
        thresholds = dict(DEFAULTS["thresholds"])
        thresholds.update(user.get("thresholds", {}))
        config["thresholds"] = thresholds
    return config
