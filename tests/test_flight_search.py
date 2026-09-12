import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flight_response import parse_payload, parse_html, ProviderResponseError
spec = importlib.util.spec_from_file_location("month_search", Path(__file__).resolve().parents[1]/"flight-month-search/search.py")
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)

def offer(price=680):
    segment = [None]*22
    segment[3], segment[6], segment[11] = "DOU", "GRU", 100
    flight = [None, ["LATAM"], [segment]]
    return [flight, [[None, price]]]

class SearchRegression(unittest.TestCase):
    def test_empty_groups(self):
        for payload in (None, [None]*4, [None,None,[None],[None]], [None,None,[[]],None]):
            self.assertEqual(parse_payload(payload), [])
    def test_incomplete_and_valid_offers(self):
        for entry in (None, [None,None], offer(None), [[None,[],None], [[None,500]]]):
            self.assertEqual(parse_payload([None,None,None,[[entry]]]), [])
        self.assertEqual(parse_payload([None,None,[[offer()]],None])[0].price,680)
        self.assertEqual(parse_payload([None,None,None,[[offer(720)]]])[0].price,720)
    def test_structural_errors_remain_errors(self):
        for payload in ({}, [], [None,None,None,{"changed":True}]):
            with self.assertRaises(ProviderResponseError): parse_payload(payload)
        with self.assertRaises(ProviderResponseError): parse_html("<html>Unavailable</html>")
    def test_months_and_range(self):
        for month,total in (("2026-10",465),("2026-11",435),("2026-12",465),("2027-01",465)):
            start,end=search.month_bounds(month)
            self.assertEqual(len(search.build_combinations(start,end,date(2026,9,12))),total)
        self.assertEqual(len(search.build_combinations(date(2026,10,13),date(2026,10,15),date(2026,9,12))),3)
        index=next(i for i in range(465) if search._pair_from_index(i)==(13,15))
        self.assertEqual(search.decode_origin_and_period(search.RANGE_CODES[index],"2026-10")[1:3],(date(2026,10,13),date(2026,10,15)))
    def test_history_preserved_and_comparison(self):
        history={"pairs":{}}
        for month in ("2026-10","2026-11","2026-12"):
            row={"departure_date":month+"-13","return_date":month+"-15","price":680}
            search.merge_rows_into_history(history,[row],"DOU","GRU",2,"first")
        before=copy.deepcopy(history)
        row={"departure_date":"2026-11-13","return_date":"2026-11-15","price":720}
        enriched=search.enrich_with_history([row],history,"DOU","GRU",2)[0]
        self.assertEqual((enriched["previous_price"],enriched["change_amount"],enriched["change_pct"]),(680,40,5.9))
        search.merge_rows_into_history(history,[row],"DOU","GRU",2,"second")
        self.assertEqual(len(history["pairs"]),3)
        self.assertEqual(history["pairs"]["DOU|GRU|2026-10-13|2026-10-15|2"],before["pairs"]["DOU|GRU|2026-10-13|2026-10-15|2"])
    def test_corrupt_history_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"history.json";path.write_text("broken")
            with patch.object(search,"HISTORY_PATH",path):
                with self.assertRaises(json.JSONDecodeError): search.load_history()
    def test_all_missing_including_nonregional_use_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fast(origin,dest,combos,stops,workers,progress):
                row={"departure_date":"2027-01-01","return_date":"2027-01-02","price":500}
                return [row], combos[1:], []
            calls=[]
            def fallback(origin,dest,combos,stops,workers,progress):
                calls.extend(combos);progress(len(combos),[],[],{})
                return [],[]
            with patch.dict(os.environ,{"SEARCH_ORIGIN":"GRU","SEARCH_DESTINATION":"MIA","SEARCH_MONTH":"2027-01","GITHUB_TOKEN":""}), patch.object(search,"OUTPUT_PATH",Path(tmp)/"out.json"), patch.object(search,"HISTORY_PATH",Path(tmp)/"history.json"), patch.object(search,"run_fast_streaming",fast), patch.object(search,"run_swoop_batch",fallback), patch.object(search,"build_combinations",return_value=[(date(2027,1,1),date(2027,1,2)),(date(2027,1,1),date(2027,1,3))]):
                search.main()
            self.assertEqual(len(calls),1)
            self.assertEqual(json.loads((Path(tmp)/"out.json").read_text())["stats"]["fallback_done"],1)

if __name__=="__main__":
    unittest.main()
