from __future__ import annotations

import json
from pathlib import Path

from deal_sources import feed_payload

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "external-deals.json"


def main() -> None:
    payload = feed_payload()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        "Fontes externas:",
        payload.get("signal_count", 0),
        "sinais;",
        f"{payload.get('responding_source_count', 0)}/{payload.get('source_count', 0)} fontes respondendo",
    )
    for name, info in payload.get("sources", {}).items():
        print(name, info.get("ok"), info.get("items"), info.get("message"))


if __name__ == "__main__":
    main()
