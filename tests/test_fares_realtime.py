"""Tests for fare tables and the real-time bus module (no network)."""
import json
import os
import tempfile
import unittest

from accesshk.fares import load_bus_fares, load_rail_fares, rail_fare
from accesshk.realtime import get_eta, load_bus_stops, summarize_eta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "data", "raw")

RAW_ETA = {
    "appRefreshTimeInSecond": "60",
    "busStop": [
        {"busStopId": "K12-D030", "isSuspended": "0",
         "bus": [{"arrivalTimeInSecond": "153", "arrivalTimeText": "2 minutes",
                  "isDelayed": "0", "isScheduled": "0"}]},
        {"busStopId": "K12-D040", "isSuspended": "1", "bus": None},
    ],
}


class TestRealtime(unittest.TestCase):
    def test_summarize_joins_stop_names(self):
        stops = load_bus_stops(os.path.join(RAW, "mtr_bus_stops.csv"))
        out = summarize_eta(RAW_ETA, stops)
        self.assertEqual(out[0]["name_en"], "Uptown Plaza")
        self.assertEqual(out[0]["name_zh"], "新達廣場")
        self.assertEqual(out[0]["arrivals"][0]["in_minutes"], 3)
        self.assertEqual(out[0]["arrivals"][0]["text"], "2 minutes")
        self.assertTrue(out[1]["suspended"])       # parsing "1"
        self.assertFalse(out[1]["arrivals"])

    def test_get_eta_falls_back_to_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "bus_eta_cache.json")
            with open(cache, "w", encoding="utf-8") as f:
                json.dump({"route": "K12", "source": "live",
                           "fetched_at": "2026-10-24T10:00:00+08:00",
                           "stops": []}, f)
            # unreachable URL -> cached payload, relabelled
            out = get_eta("K12", {}, cache, timeout=0.001)
            self.assertEqual(out["source"], "cached")

    def test_get_eta_raises_without_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                get_eta("K12", {}, os.path.join(tmp, "none.json"),
                        timeout=0.001)


class TestFares(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = {
            "rail": load_rail_fares(os.path.join(RAW, "mtr_lines_fares.csv")),
            "bus": load_bus_fares(os.path.join(RAW, "mtr_bus_fares.csv")),
        }

    def test_known_pair_concessions(self):
        # Central (1) <-> Admiralty (2): $2 elderly/PWD concession
        fa = rail_fare(self.tables, "1", "2")
        self.assertAlmostEqual(fa["octopus_adult"], 4.9)
        self.assertAlmostEqual(fa["octopus_elderly"], 2.0)
        self.assertAlmostEqual(fa["octopus_pwd"], 2.0)
        self.assertAlmostEqual(rail_fare(self.tables, "2", "1")["octopus_adult"],
                               4.9)                       # symmetric

    def test_unknown_pair_is_none(self):
        self.assertIsNone(rail_fare(self.tables, "1", "9999"))

    def test_bus_fares_concessions_and_dashes(self):
        k12 = self.tables["bus"]["K12"]
        self.assertAlmostEqual(k12["octopus_elderly"], 2.0)
        self.assertAlmostEqual(k12["octopus_pwd"], 2.0)
        # '-' columns parse to None, never crash
        self.assertIn(k12["single_adult"] is None
                      or k12["single_adult"] >= 0, [True])


if __name__ == "__main__":
    unittest.main()
