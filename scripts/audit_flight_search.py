"""Read-only provider diagnostic. No dispatch, publisher, or history writes."""
import inspect
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import traceback
from datetime import date
import fast_flights
from search_core import query_cheapest

print("GET_FLIGHTS_SOURCE", inspect.getsource(fast_flights.get_flights), flush=True)
for month in ("2026-10", "2026-11", "2026-12", "2027-01"):
    dep, ret = date.fromisoformat(month+"-01"), date.fromisoformat(month+"-10")
    print("SAMPLE", dep, ret, flush=True)
    try:
        result = query_cheapest("DOU", "GRU", dep, ret, {"max_stops": 2})
        print("RESULT", result, flush=True)
    except Exception as exc:
        traceback.print_exc()
        tb = exc.__traceback__
        while tb:
            frame = tb.tb_frame
            if "fast_flights" in frame.f_code.co_filename:
                print("FAILING_FUNCTION", inspect.getsource(frame.f_code), flush=True)
                # Shapes only; never dump remote documents or environment.
                for key, value in frame.f_locals.items():
                    if key in ("data", "flights", "flight", "item", "result", "results"):
                        print("SHAPE", key, type(value).__name__, len(value) if isinstance(value,(list,dict)) else "", flush=True)
            tb = tb.tb_next
