"""Small real provider checks; never dispatches workflows or changes history."""
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from search_core import query_cheapest
spec=importlib.util.spec_from_file_location("month_search",Path(__file__).resolve().parents[1]/"flight-month-search/search.py")
search=importlib.util.module_from_spec(spec);spec.loader.exec_module(search)
samples=[(m+"-13",m+"-15") for m in ("2026-10","2026-11","2026-12","2027-01")]
samples += [("2027-01-01","2027-01-10"),("2027-01-01","2027-01-12"),("2027-01-02","2027-01-09")]
jan_prices=0
for dep,ret in samples:
    result=query_cheapest("DOU","GRU",date.fromisoformat(dep),date.fromisoformat(ret),{"max_stops":2})
    print("PRIMARY",dep,ret,result.price_value if result else None,flush=True)
    if result:
        price=result.price_value
    else:
        def progress(done,rows,errors,pair):
            if done: print("FALLBACK_PROGRESS",done,len(rows),pair,flush=True)
        rows,errors=search.run_swoop_batch("DOU","GRU",[(date.fromisoformat(dep),date.fromisoformat(ret))],2,1,progress)
        if errors: raise RuntimeError(errors)
        price=rows[0]["price"] if rows else None
    print("REAL_RESULT",json.dumps({"departure":dep,"return":ret,"price":price,"status":"priced" if price else "no_result"}),flush=True)
    if dep.startswith("2027") and price: jan_prices+=1
print("JANUARY_PRICED_SAMPLES",jan_prices,flush=True)
