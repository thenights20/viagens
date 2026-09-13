from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MULTI = ROOT / 'flight-month-search/multisource.py'
RESULT = ROOT / 'docs/data/flight-month-search.json'
HISTORY = ROOT / 'docs/data/flight-price-history.json'

ALLOWED = {'google', 'fast-flights', 'Google Flights', 'google flights'}


def patch_multisource() -> None:
    s = MULTI.read_text(encoding='utf-8')
    s, n = re.subn(
        r'SOURCE_CATALOG = \{.*?\}\n\nAUTO_CANDIDATES = \[.*?\]\n',
        '''SOURCE_CATALOG = {
    "google": {"label": "Google Flights", "auto_candidate": True},
    "ita": {"label": "ITA Matrix", "auto_candidate": False},
}

AUTO_CANDIDATES = []
''',
        s,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit('SOURCE_CATALOG patch point not found')

    s, n = re.subn(
        r'URL_BUILDERS = \{.*?\}\n\n\ndef search_links',
        '''URL_BUILDERS = {
    "google": google_url,
    "ita": ita_url,
}


def search_links''',
        s,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit('URL_BUILDERS patch point not found')

    start = s.find('def preflight_sources(')
    end = s.find('\ndef query_one(', start)
    if start < 0 or end < 0:
        raise SystemExit('preflight_sources patch point not found')
    replacement = '''def preflight_sources(
    origin: str,
    destination: str,
    dep: date,
    ret: date,
    max_stops: int,
) -> tuple[list[str], dict[str, dict]]:
    """Only Google Flights may create automatic fare rows.

    ITA Matrix remains available as a route/date verification link. Generic
    agency HTML is intentionally excluded because unrelated promotional values
    can be mistaken for airfare.
    """
    health = {
        "google": {
            "enabled": True,
            "label": SOURCE_CATALOG["google"]["label"],
            "reason": "structured fare collector",
        },
        "ita": {
            "enabled": False,
            "label": SOURCE_CATALOG["ita"]["label"],
            "reason": "verification/search link only; no stable public fare API",
        },
    }
    return ["google"], health

'''
    s = s[:start] + replacement + s[end + 1:]
    s = s.replace('payload["source_strategy"] = "preflight_sharded"', 'payload["source_strategy"] = "google_flights_with_ita_verification"')
    s = s.replace('Busca multifonte ', 'Busca Google+ITA ')
    MULTI.write_text(s, encoding='utf-8')


def good_row(row: dict) -> bool:
    vals = {
        str(row.get('source_kind') or '').strip(),
        str(row.get('provider') or '').strip(),
        str(row.get('airline') or '').strip(),
    }
    return bool(vals & ALLOWED)


def clean_result() -> None:
    if not RESULT.exists():
        return
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    for key in ('results', 'all_results', 'daily_min'):
        if isinstance(data.get(key), list):
            data[key] = [r for r in data[key] if isinstance(r, dict) and good_row(r)]
    rows = data.get('all_results') or data.get('results') or []
    stats = data.setdefault('stats', {})
    prices = [float(r['price']) for r in rows if r.get('price') is not None]
    total = int(stats.get('combinations') or 0)
    stats['priced_combinations'] = len(rows)
    stats['result_count'] = min(100, len(data.get('results') or []))
    stats['lowest_price'] = min(prices) if prices else None
    stats['coverage_pct'] = round(len(rows) / total * 100, 1) if total else 0
    data['sources'] = {
        'google': {'label': 'Google Flights', 'auto_candidate': True},
        'ita': {'label': 'ITA Matrix', 'auto_candidate': False},
    }
    data['active_sources'] = ['google']
    data['source_strategy'] = 'google_flights_with_ita_verification'
    RESULT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def clean_history() -> None:
    if not HISTORY.exists():
        return
    hist = json.loads(HISTORY.read_text(encoding='utf-8'))
    pairs = hist.get('pairs') if isinstance(hist, dict) else None
    if not isinstance(pairs, dict):
        return
    clean = {}
    for key, pair in pairs.items():
        obs = pair.get('observations') or []
        sources = {str(o.get('source') or '').strip() for o in obs if isinstance(o, dict)}
        if not sources or sources <= ALLOWED:
            clean[key] = pair
    hist['pairs'] = clean
    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> None:
    patch_multisource()
    clean_result()
    clean_history()
    print('Restricted flight prices to Google Flights; ITA Matrix retained for verification links.')


if __name__ == '__main__':
    main()
