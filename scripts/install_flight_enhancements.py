from pathlib import Path

p = Path('docs/terabyte-live.js')
s = p.read_text(encoding='utf-8')
old = "    s.src = './flight-explorer.js?v=20260912-6';\n    s.defer = true;\n    s.dataset.flightExplorer = '1';\n    document.head.appendChild(s);"
new = "    s.src = './flight-explorer.js?v=20260912-8';\n    s.defer = true;\n    s.dataset.flightExplorer = '1';\n    s.onload = () => {\n      if (document.querySelector('script[data-flight-enhancements]')) return;\n      const e = document.createElement('script');\n      e.src = './flight-explorer-enhancements.js?v=20260912-1';\n      e.defer = true;\n      e.dataset.flightEnhancements = '1';\n      document.head.appendChild(e);\n    };\n    document.head.appendChild(s);"
if old not in s:
    old = "    s.src = './flight-explorer.js?v=20260912-7';\n    s.defer = true;\n    s.dataset.flightExplorer = '1';\n    document.head.appendChild(s);"
if old not in s:
    raise SystemExit('Loader do flight-explorer não encontrado')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
