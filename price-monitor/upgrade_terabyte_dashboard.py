from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "docs" / "index.html"


def main() -> None:
    html = PATH.read_text(encoding="utf-8")
    marker = '<script src="./terabyte-live.js"></script>'
    if marker in html:
        print("Terabyte Live já conectado ao painel.")
        return
    if "</body>" not in html:
        raise RuntimeError("marcador </body> não encontrado")
    html = html.replace("</body>", marker + "\n</body>", 1)
    PATH.write_text(html, encoding="utf-8")
    print("Terabyte Live conectado ao painel.")


if __name__ == "__main__":
    main()
