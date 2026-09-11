from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs" / "index.html"


def main() -> None:
    html = PATH.read_text(encoding="utf-8")
    old = '<option value="70" selected>70+ Muito barata</option><option value="80">80+ Excepcional</option>'
    new = '<option value="70">70+ Muito barata</option><option value="80" selected>80+ Excepcional</option>'
    if old in html:
        html = html.replace(old, new, 1)
        PATH.write_text(html, encoding="utf-8")
        print("Filtro padrão do Deal Hunter ajustado para Score 80+.")
    else:
        print("Filtro padrão já está em Score 80+ ou marcador não se aplica.")


if __name__ == "__main__":
    main()
