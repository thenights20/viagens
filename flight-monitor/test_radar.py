from __future__ import annotations

import unittest
from datetime import date, timedelta

from radar import booking_bucket, score_candidate, should_repeat_alert, summarise


class RadarTests(unittest.TestCase):
    def test_booking_windows(self) -> None:
        self.assertEqual(booking_bucket(4), "0-7")
        self.assertEqual(booking_bucket(14), "8-21")
        self.assertEqual(booking_bucket(40), "22-60")
        self.assertEqual(booking_bucket(120), "61+")

    def test_median_mad_resist_outlier(self) -> None:
        stats = summarise([3000, 3050, 3100, 3150, 9000], distinct_days=5)
        self.assertIsNotNone(stats)
        assert stats is not None
        self.assertEqual(stats.median, 3100)
        self.assertLess(stats.mad, 200)
        self.assertGreater(stats.maximum, stats.median * 2)

    def test_strong_anomaly_scores_high(self) -> None:
        stats = summarise([3000, 3050, 3100, 3150, 3200, 3250, 3300, 3350], distinct_days=8)
        assert stats is not None
        candidate = {
            "price": 1800,
            "stops_count": 0,
            "duration_minutes": 600,
            "provider_discount_pct": 40,
        }
        history = [{"duration_minutes": 620} for _ in range(8)]
        result = score_candidate(candidate, history, stats, confirmation="second_source")
        self.assertGreaterEqual(result["deal_score"], 90)
        self.assertIn("TARIFA ANORMAL", result["status"])
        self.assertLessEqual(result["percentile"], 5)
        self.assertLess(result["z_score"], -2)

    def test_low_history_caps_confidence(self) -> None:
        stats = summarise([3000, 3100, 3200], distinct_days=1)
        assert stats is not None
        candidate = {"price": 1800, "stops_count": 0, "duration_minutes": 600}
        result = score_candidate(candidate, [], stats, confirmation="second_source")
        self.assertLessEqual(result["deal_score"], 74)

    def test_repeat_suppression(self) -> None:
        today = date.today()
        previous = {"price": 2000, "score": 80, "date": (today - timedelta(days=2)).isoformat()}
        self.assertFalse(should_repeat_alert(previous, current_price=1980, current_score=81, today=today))
        self.assertTrue(should_repeat_alert(previous, current_price=1880, current_score=81, today=today))
        self.assertTrue(should_repeat_alert(previous, current_price=1980, current_score=90, today=today))


if __name__ == "__main__":
    unittest.main()
