import tempfile
import unittest
import sys
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

from search_core import Deal, SearchPlan, Store, _deal, _price, build_plan, query_cheapest


def sample_deal(price: float, dep: str = "2027-01-10") -> Deal:
    return Deal(
        origin="CGR", destination="REC", departure_date=dep, return_date="2027-01-17",
        airline="Teste", price_text=f"R$ {price:.2f}", price_value=price,
        duration="3h 00min", duration_minutes=180, stops="Direto", stops_count=0,
        departure="", arrival="", query_url="https://example.test",
    )


class PlanTests(unittest.TestCase):
    def params(self, depth: str = "Profundo"):
        start = date.today() + timedelta(days=1)
        return {
            "origins": "CGR", "destinations": "REC", "origin_regions": [], "destination_regions": [],
            "date_mode": "Próximos 12 meses", "dep_start": start,
            "dep_end": start + timedelta(days=364), "min_nights": 3, "max_nights": 5,
            "depth": depth,
        }

    def test_deep_checks_every_day_and_stay(self):
        plan = build_plan(self.params())
        self.assertEqual(365 * 3, plan.total)

    def test_quick_mode_is_a_smaller_sample(self):
        self.assertLess(build_plan(self.params("Rápido")).total, build_plan(self.params()).total)

    def test_plan_interleaves_routes_for_broad_coverage(self):
        pair = (date(2027, 1, 1), date(2027, 1, 8))
        plan = SearchPlan(routes=[("A", "B"), ("A", "C")], pairs=[pair])
        self.assertEqual(("A", "B"), plan.item(0)[:2])
        self.assertEqual(("A", "C"), plan.item(1)[:2])


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "test.db")
        self.job_id = self.store.create_job({"dep_start": date.today()}, 10)

    def tearDown(self):
        self.store.conn.close()
        self.temp.cleanup()

    def test_only_lowest_price_survives_per_route(self):
        self.assertTrue(self.store.save_best(self.job_id, sample_deal(1000)))
        self.assertFalse(self.store.save_best(self.job_id, sample_deal(1200)))
        self.assertTrue(self.store.save_best(self.job_id, sample_deal(850)))
        results = self.store.best(self.job_id)
        self.assertEqual(1, len(results))
        self.assertEqual(850, results[0].price_value)

    def test_job_can_be_resumed_with_saved_cursor(self):
        self.store.update_job(self.job_id, 7, "paused", 2)
        job = self.store.latest_resumable()
        self.assertEqual(7, job["cursor"])
        self.assertEqual(2, job["errors"])


class ConversionTests(unittest.TestCase):
    def test_parses_brazilian_and_international_price_formats(self):
        self.assertEqual(1234, _price("R$ 1.234"))
        self.assertEqual(1234, _price("$1,234"))
        self.assertEqual(1234.56, _price("R$ 1.234,56"))
        self.assertEqual(1234.56, _price("$1,234.56"))

    def test_converts_and_preserves_cheapest_fields(self):
        flight = SimpleNamespace(
            price="1.234,56", airlines=["G3"],
            flights=[SimpleNamespace(duration=90, departure="08:00", arrival="09:30")],
        )
        converted = _deal(flight, "CGR", "GRU", date(2027, 1, 1), date(2027, 1, 8))
        self.assertEqual(1234.56, converted.price_value)
        self.assertEqual("G3", converted.airline)
        self.assertEqual("Direto", converted.stops)

    def test_query_selects_only_the_cheapest_returned_flight(self):
        fake = ModuleType("fast_flights")

        class FlightQuery:
            def __init__(self, date=None, from_airport=None, to_airport=None, max_stops=None):
                self.date = date

        class Passengers:
            def __init__(self, adults=1):
                self.adults = adults

        def create_query(flights=None, seat=None, trip=None, passengers=None, language=None, currency=None, max_price=None):
            return flights

        def get_flights(_query):
            return [SimpleNamespace(price=1250, airlines=["A"]), SimpleNamespace(price=799, airlines=["B"])]

        fake.FlightQuery = FlightQuery
        fake.Passengers = Passengers
        fake.create_query = create_query
        fake.get_flights = get_flights
        previous = sys.modules.get("fast_flights")
        sys.modules["fast_flights"] = fake
        try:
            result = query_cheapest(
                "CGR", "REC", date(2027, 1, 1), date(2027, 1, 8),
                {"adults": 1, "currency": "BRL", "seat": "economy", "max_stops": 2},
            )
        finally:
            if previous is None:
                sys.modules.pop("fast_flights", None)
            else:
                sys.modules["fast_flights"] = previous
        self.assertEqual(799, result.price_value)
        self.assertEqual("B", result.airline)


if __name__ == "__main__":
    unittest.main()
