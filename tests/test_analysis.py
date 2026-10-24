"""Tests for the hand-written analysis layer (k-means, silhouette,
elbow) — synthetic ground truth plus a real-network smoke test."""
import os
import unittest

import numpy as np

from accesshk.analysis import (elbow_knee, feature_matrix, full_analysis,
                               kmeans, silhouette_score)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORK = os.path.join(BASE, "data", "processed", "network.json")


def _blobs(seed: int = 0) -> np.ndarray:
    """Two well-separated 2-D gaussian blobs + one loose third group."""
    rng = np.random.default_rng(seed)
    a = rng.normal([0.0, 0.0], 0.05, size=(30, 2))
    b = rng.normal([5.0, 5.0], 0.05, size=(30, 2))
    c = rng.normal([0.0, 5.0], 0.3, size=(15, 2))
    return np.vstack([a, b, c])


class TestKmeans(unittest.TestCase):
    def test_recovers_separated_blobs(self):
        X = _blobs()
        run = kmeans(X, k=3, seed=1)
        labels = run["labels"]
        # points of the same blob must share one label
        for lo, hi in ((0, 30), (30, 60), (60, 75)):
            self.assertEqual(len(set(labels[lo:hi])), 1,
                             f"blob [{lo}:{hi}] split across clusters")
        # three distinct labels overall
        self.assertEqual(len(set(labels)), 3)

    def test_sse_decreases_with_k_and_labels_sum_ok(self):
        X = _blobs(seed=3)
        sses = [kmeans(X, k=k, seed=0)["sse"] for k in (2, 4, 6)]
        self.assertTrue(all(x > y for x, y in zip(sses, sses[1:])))
        run = kmeans(X, k=4, seed=0)
        self.assertEqual(len(run["labels"]), X.shape[0])
        self.assertTrue(run["iterations"] >= 1)

    def test_empty_cluster_reseeding_does_not_crash(self):
        # duplicate points: k-means++ may pick identical centres
        X = np.zeros((6, 2))
        run = kmeans(X, k=3, n_init=2, seed=0)
        self.assertEqual(run["labels"].shape, (6,))


class TestModelSelection(unittest.TestCase):
    def test_silhouette_bounds_and_perfect_separation(self):
        X = _blobs(seed=5)
        good = kmeans(X, k=3, seed=1)["labels"]
        s_good = silhouette_score(X, good)
        self.assertGreater(s_good, 0.9)          # blobs nearly perfectly
        # random labels must score badly
        rng = np.random.default_rng(0)
        s_bad = silhouette_score(X, rng.integers(0, 3, X.shape[0]))
        self.assertLess(s_bad, 0.2)
        self.assertTrue(-1.0 <= s_good <= 1.0)

    def test_silhouette_single_cluster_is_zero(self):
        X = _blobs()
        self.assertEqual(silhouette_score(X, np.zeros(75, dtype=int)), 0.0)

    def test_elbow_knee_finds_three_blobs(self):
        X = _blobs(seed=7)
        ks = list(range(2, 8))
        sses = [kmeans(X, k=k, seed=2)["sse"] for k in ks]
        self.assertEqual(elbow_knee(ks, sses), 3)


class TestRealNetwork(unittest.TestCase):
    @unittest.skipIf(not os.path.exists(NETWORK),
                     "network.json not built")
    def test_full_analysis_runs_and_is_consistent(self):
        from accesshk.bundle import load_network
        registry, graph, _m, _l = load_network(NETWORK)
        X, sids = feature_matrix(registry)
        self.assertEqual(X.shape[0], len(registry.stations))
        self.assertEqual(X.shape[1], 5)
        self.assertTrue(((X >= 0) & (X <= 1)).all())

        payload = full_analysis(registry, graph, seed=11)
        km = payload["kmeans"]
        self.assertIn(km["chosen_k"], km["k_range"])
        sizes = [c["size"] for c in payload["clusters"]]
        self.assertEqual(sum(sizes), len(registry.stations))
        self.assertTrue(payload["benchmark"]["all_costs_equal"])
        self.assertGreater(len(payload["line_coverage"]), 0)


if __name__ == "__main__":
    unittest.main()
