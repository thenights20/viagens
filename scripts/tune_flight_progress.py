from pathlib import Path
p = Path('flight-month-search/search.py')
s = p.read_text(encoding='utf-8')
s = s.replace('CHECKPOINT_SECONDS = 18', 'CHECKPOINT_SECONDS = 8')
s = s.replace('CHECKPOINT_COMPLETIONS = 24', 'CHECKPOINT_COMPLETIONS = 12')
if 'CHECKPOINT_SECONDS = 8' not in s or 'CHECKPOINT_COMPLETIONS = 12' not in s:
    raise SystemExit('Constantes de checkpoint não encontradas')
p.write_text(s, encoding='utf-8')
