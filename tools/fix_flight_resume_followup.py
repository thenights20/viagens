from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'flight-month-search/multisource.py'
s=P.read_text(encoding='utf-8')
old='''    if error:
        errors.append(error)
    if row:
        row["assigned_source"] = assigned
        return row, errors, assigned

    row, error = _google_probe(origin, destination, dep, ret, max_stops)
'''
new='''    if error:
        errors.append(error)
    if row:
        row["assigned_source"] = assigned
        return row, errors, assigned
    if assigned == "google":
        return None, errors, assigned

    row, error = _google_probe(origin, destination, dep, ret, max_stops)
'''
if old not in s:
    raise SystemExit('Google duplicate-query patch point not found')
s=s.replace(old,new,1)
P.write_text(s,encoding='utf-8')
print('Removed duplicate Google retry for Google-assigned shards')
