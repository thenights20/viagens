"""Run a real three-pair January range with isolated output and history."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
spec=importlib.util.spec_from_file_location("month_search",root/"flight-month-search/search.py")
search=importlib.util.module_from_spec(spec);spec.loader.exec_module(search)
with tempfile.TemporaryDirectory() as tmp:
    search.OUTPUT_PATH=Path(tmp)/"result.json"
    search.HISTORY_PATH=Path(tmp)/"history.json"
    original=json.loads((root/"docs/data/flight-price-history.json").read_text())
    shutil.copyfile(root/"docs/data/flight-price-history.json",search.HISTORY_PATH)
    index=next(i for i in range(465) if search._pair_from_index(i)==(13,15))
    os.environ.update(SEARCH_ORIGIN=search.RANGE_CODES[index],SEARCH_DESTINATION="GRU",
                      SEARCH_MONTH="2027-01",SEARCH_MAX_STOPS="2",SEARCH_REQUEST_ID="audit_january_range",GITHUB_TOKEN="")
    search.main()
    result=json.loads(search.OUTPUT_PATH.read_text())
    history=json.loads(search.HISTORY_PATH.read_text())
    assert result["stats"]["combinations"]==3
    assert result["stats"]["primary_completed"]==3
    assert result["status"]=="completed"
    assert result["stats"]["priced_combinations"]>0
    for key,value in original["pairs"].items():
        if not key.startswith("DOU|GRU|2027-01-"):
            assert history["pairs"][key]==value
    print("REAL_RANGE_VERIFIED",json.dumps({"request":result["request"],"stats":result["stats"],"errors":result["errors"]}),flush=True)
