from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs" / "index.html"


def main() -> None:
    html = PATH.read_text(encoding="utf-8")
    if 'id="productUpdated"' not in html:
        html = html.replace('<main id="productsApp">', '<main id="productsApp">\n  <span id="productUpdated" hidden></span>', 1)
    required = [
        'id="productBugPanel"', 'id="productBugRows"', 'id="productSensorPanel"',
        'id="productSensorRows"', 'id="productCouponPanel"', 'id="productCouponRows"',
        'id="productBugUpdated"', 'id="productTabs"', 'id="productUpdated"',
    ]
    missing = [item for item in required if item not in html]
    if missing:
        raise RuntimeError("IDs ausentes no painel: " + ", ".join(missing))
    PATH.write_text(html, encoding="utf-8")
    print("Painel de produtos finalizado.")


if __name__ == "__main__":
    main()
