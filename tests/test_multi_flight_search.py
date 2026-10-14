"""Regression tests for combined airfare route and date selection.

Tests the pure helpers without importing network-dependent flight providers.
"""
import ast
import re
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract(path, name, extra=None):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    module = ast.Module(body=[fn], type_ignores=[])
    ns = {"re": re, "date": date, "timedelta": timedelta}
    ns.update(extra or {})
    exec(compile(ast.fix_missing_locations(module), path, "exec"), ns)
    return ns[name]


def build_combinations(start, end, today):
    result = []
    d = max(start, today + timedelta(days=1))
    while d < end:
        r = d + timedelta(days=1)
        while r <= end:
            result.append((d, r))
            r += timedelta(days=1)
        d += timedelta(days=1)
    return result


class CombinedFlightSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.iata_list = staticmethod(extract("flight-month-search/multi.py", "iata_list"))
        cls.date_pairs = staticmethod(extract("flight-month-search/multi.py", "date_pairs", {
            "date_list": extract("flight-month-search/multi.py", "date_list"),
            "month_bounds": lambda month: (date.fromisoformat(month + "-01"), date.fromisoformat(month + "-30")),
            "build_combinations": build_combinations,
        }))
        cls.dedupe = staticmethod(extract("flight-month-search/search.py", "dedupe"))

    def test_airports_are_normalized_and_deduplicated(self):
        self.assertEqual(self.iata_list("gru,cgh, GRU, vcp"), ["GRU", "CGH", "VCP"])
        with self.assertRaises(ValueError):
            self.iata_list("GRU,INVALID")

    def test_dates_only_include_valid_outbound_and_return_pairs(self):
        pairs, departures, returns = self.date_pairs(
            "dates", "2026-11", "2026-11-10,2026-11-13", "2026-11-12,2026-11-18", date(2026, 11, 1)
        )
        self.assertEqual(len(pairs), 3)
        self.assertNotIn((date(2026, 11, 13), date(2026, 11, 12)), pairs)
        self.assertEqual(len(departures), 2)
        self.assertEqual(len(returns), 2)

    def test_past_departures_are_excluded(self):
        pairs, _, _ = self.date_pairs(
            "dates", "2026-11", "2026-11-01,2026-11-10", "2026-11-15", date(2026, 11, 2)
        )
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0], date(2026, 11, 10))

    def test_legacy_range_is_preserved(self):
        pairs, _, _ = self.date_pairs(
            "range", "2026-11", "2026-11-10", "2026-11-12", date(2026, 11, 1)
        )
        self.assertEqual(len(pairs), 3)

    def test_same_days_different_routes_are_not_merged(self):
        base = dict(departure_date="2026-11-10", return_date="2026-11-18")
        rows = [
            dict(base, origin="GRU", destination="MIA", price=900),
            dict(base, origin="CGH", destination="MIA", price=750),
            dict(base, origin="GRU", destination="MIA", price=800),
        ]
        found = self.dedupe(rows)
        self.assertEqual(len(found), 2)
        self.assertEqual(next(x for x in found if x["origin"] == "GRU")["price"], 800)

    def test_interface_exposes_multi_fields_and_legacy_periods(self):
        ui = (ROOT / "docs/flight-explorer.js").read_text(encoding="utf-8")
        for key in ["addMonthOrigin", "addMonthDestination", "datesDeparture", "datesReturn",
                    "monthPeriodMonth", "monthPeriodRange", "monthPeriodDates"]:
            self.assertIn(key, ui)
        bridge = (ROOT / "apps-script/Code.gs").read_text(encoding="utf-8")
        self.assertIn("validAirportList_", bridge)
        self.assertIn("validDateList_", bridge)


if __name__ == "__main__":
    unittest.main()
