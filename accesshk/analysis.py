"""Data-mining layer: station accessibility analytics.

Everything here is hand-written NumPy (teacher Q1: core algorithms are
implemented from scratch, no scikit-learn one-liners):

* :func:`kmeans`           — Lloyd's algorithm with k-means++ seeding,
                             best-of-``n_init`` restarts
* :func:`silhouette_score` — per-point silhouette, O(n^2) pairwise
                             distances, no scipy
* :func:`elbow_knee`       — scree-plot knee via point-to-line distance
* :func:`benchmark_search` — expanded-node counts, Dijkstra vs A*, the
                             empirical check that the admissible
                             heuristic pays off on this graph

The features are the four category-coverage fractions (AJ/MJ/VJ/HJ)
plus a step-free indicator, so every cluster is directly explainable in
the report and the UI ("full access", "partial", ...).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from . import routing
from .datasets import Station, StationRegistry
from .facilities import category_coverage, is_step_free
from .graph import TransitGraph

FEATURE_NAMES = ["aj_coverage", "mj_coverage", "vj_coverage",
                 "hj_coverage", "step_free"]

# weights for the headline accessibility score (report + gap analysis)
SCORE_WEIGHTS = {"AJ": 0.4, "MJ": 0.2, "VJ": 0.2, "HJ": 0.2}


# ---------------------------------------------------------------------------
# features
# ---------------------------------------------------------------------------

def feature_matrix(registry: StationRegistry
                   ) -> Tuple[np.ndarray, List[str]]:
    """(n_stations, 5) feature matrix plus the station ids in row order."""
    sids, rows = [], []
    for sid in sorted(registry.stations, key=int):
        st = registry.stations[sid]
        cov = category_coverage(st)
        sids.append(sid)
        rows.append([cov.get("AJ", 0.0), cov.get("MJ", 0.0),
                     cov.get("VJ", 0.0), cov.get("HJ", 0.0),
                     1.0 if is_step_free(st) else 0.0])
    return np.array(rows, dtype=float), sids


def accessibility_score(st: Station) -> float:
    """0..1 headline score: weighted category coverage, halved with the
    binary step-free verdict (a station that is not usable end-to-end
    cannot score above 0.5 however rich its facility list)."""
    cov = category_coverage(st)
    weighted = sum(w * cov.get(cat, 0.0)
                   for cat, w in SCORE_WEIGHTS.items())
    return round(0.5 * weighted
                 + 0.5 * (1.0 if is_step_free(st) else 0.0), 3)


# ---------------------------------------------------------------------------
# hand-written k-means
# ---------------------------------------------------------------------------

def _kmeans_pp_init(X: np.ndarray, k: int, rng: np.random.Generator
                    ) -> np.ndarray:
    """k-means++ seeding: each next centre is drawn with probability
    proportional to its squared distance from the nearest existing one."""
    n = X.shape[0]
    centers = [X[rng.integers(n)]]
    for _ in range(1, k):
        stack = np.array(centers)
        d2 = ((X[:, None, :] - stack[None, :, :]) ** 2).sum(-1).min(1)
        total = float(d2.sum())
        if total <= 1e-12:                    # all points coincide
            centers.append(X[rng.integers(n)])
            continue
        centers.append(X[rng.choice(n, p=d2 / total)])
    return np.array(centers, dtype=float)


def _sq_dists(X: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """(n, k) squared Euclidean distances via broadcasting."""
    return ((X[:, None, :] - centers[None, :, :]) ** 2).sum(-1)


def kmeans(X: np.ndarray, k: int, n_init: int = 10, max_iter: int = 100,
           tol: float = 1e-6, seed: int = 0) -> dict:
    """Lloyd's algorithm with k-means++ seeding, best-of-``n_init``.

    Returns ``{labels, centers, sse, iterations, k, n_init}``.
    """
    rng = np.random.default_rng(seed)
    best: Optional[dict] = None
    for _ in range(n_init):
        centers = _kmeans_pp_init(X, k, rng)
        labels = np.full(X.shape[0], -1)
        it = 0
        for it in range(1, max_iter + 1):
            new_labels = _sq_dists(X, centers).argmin(1)
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels
            new_centers = np.empty_like(centers)
            for j in range(k):
                pts = X[labels == j]
                # empty cluster -> re-seed at a random point
                new_centers[j] = (pts.mean(0) if len(pts)
                                  else X[rng.integers(X.shape[0])])
            shift = float(np.linalg.norm(new_centers - centers))
            centers = new_centers
            if shift <= tol:
                break
        sse = float(((X - centers[labels]) ** 2).sum())
        if best is None or sse < best["sse"]:
            best = {"labels": labels.copy(), "centers": centers.copy(),
                    "sse": sse, "iterations": it, "k": k, "n_init": n_init}
    return best  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# cluster validation / model selection
# ---------------------------------------------------------------------------

def silhouette_samples(X: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Per-point silhouette coefficient, hand-written (no sklearn)."""
    n = X.shape[0]
    d = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))
    uniq = np.unique(labels)
    out = np.zeros(n)
    if len(uniq) < 2:
        return out
    for i in range(n):
        same = labels == labels[i]
        n_same = int(same.sum())
        if n_same <= 1:
            out[i] = 0.0
            continue
        a = float(d[i, same].sum() / (n_same - 1))
        b = min(float(d[i, labels == c].mean())
                for c in uniq if c != labels[i])
        denom = max(a, b)
        out[i] = (b - a) / denom if denom > 0 else 0.0
    return out


def silhouette_score(X: np.ndarray, labels: np.ndarray) -> float:
    s = silhouette_samples(X, labels)
    return float(s.mean()) if len(s) else 0.0


def elbow_knee(ks: List[int], sses: List[float]) -> int:
    """Knee of the scree plot: the SSE point farthest from the straight
    line joining the first and last points (classic, dependency-free)."""
    p1 = np.array([ks[0], sses[0]], dtype=float)
    p2 = np.array([ks[-1], sses[-1]], dtype=float)
    chord = p2 - p1
    chord_len = float(np.linalg.norm(chord))
    if chord_len <= 1e-12:
        return ks[0]
    dists = [abs(float(np.cross(chord,
                                np.array([k, s], dtype=float) - p1)))
             / chord_len for k, s in zip(ks, sses)]
    return ks[int(np.argmax(dists))]


# ---------------------------------------------------------------------------
# descriptive analytics
# ---------------------------------------------------------------------------

def line_coverage(registry: StationRegistry) -> List[dict]:
    """Per-line step-free share and mean entrance/exit coverage."""
    acc: Dict[str, dict] = {}
    for st in registry.stations.values():
        cov = category_coverage(st)
        for line in st.lines:
            s = acc.setdefault(line, {"n": 0, "sf": 0, "aj": []})
            s["n"] += 1
            s["sf"] += 1 if is_step_free(st) else 0
            s["aj"].append(cov.get("AJ", 0.0))
    return [{"line": line,
             "stations": s["n"],
             "step_free": s["sf"],
             "step_free_pct": round(100.0 * s["sf"] / s["n"], 1),
             "mean_aj_coverage": round(float(np.mean(s["aj"])), 3)}
            for line, s in sorted(acc.items())]


def gap_analysis(registry: StationRegistry, bottom_n: int = 10) -> dict:
    """Where is the network weakest?  Lowest-score stations plus the
    stations with *zero* coverage in some impairment category."""
    ranked = sorted(registry.stations.values(),
                    key=accessibility_score)
    zero: Dict[str, List[str]] = {"AJ": [], "MJ": [], "VJ": [], "HJ": []}
    for st in ranked:
        cov = category_coverage(st)
        for cat in zero:
            if cov.get(cat, 0.0) == 0.0:
                zero[cat].append(st.name_en)
    return {
        "bottom": [
            {"name_en": st.name_en, "name_zh": st.name_zh,
             "lines": sorted(st.lines),
             "score": accessibility_score(st),
             "step_free": is_step_free(st)}
            for st in ranked[:bottom_n]],
        "zero_coverage_counts": {c: len(v) for c, v in zero.items()},
        "zero_coverage_examples": {c: v[:5] for c, v in zero.items()},
    }


# ---------------------------------------------------------------------------
# shortest-path benchmark
# ---------------------------------------------------------------------------

def benchmark_search(graph: TransitGraph, n_pairs: int = 30,
                     seed: int = 7) -> dict:
    """Dijkstra vs A* on identical random station pairs: expanded nodes
    and an equality check on the returned cost (the admissibility
    guarantee, verified empirically on the real network)."""
    rng = np.random.default_rng(seed)
    sids = sorted(graph.station_nodes, key=int)
    pairs = set()
    while len(pairs) < n_pairs:
        ia, ib = (int(x) for x in
                  rng.choice(len(sids), size=2, replace=False))
        pairs.add((sids[ia], sids[ib]))
    rows, d_exp, a_exp, equal = [], [], [], True
    for a, b in sorted(pairs, key=lambda p: int(p[0])):
        s1, s2 = {}, {}
        src, dst = graph.nodes_of_station(a)[0], graph.nodes_of_station(b)[0]
        c1, _ = routing.dijkstra(graph, src, dst, stats=s1)
        c2, _ = routing.astar(graph, src, dst, stats=s2)
        match = bool(abs(c1 - c2) < 1e-9)
        equal = equal and match
        d_exp.append(s1.get("expanded", 0))
        a_exp.append(s2.get("expanded", 0))
        rows.append({
            "from": graph.registry.stations[a].name_en,
            "to": graph.registry.stations[b].name_en,
            "minutes": round(c1, 1),
            "cost_match": match,
            "dijkstra_expanded": s1.get("expanded", 0),
            "astar_expanded": s2.get("expanded", 0)})
    d_mean, a_mean = float(np.mean(d_exp)), float(np.mean(a_exp))
    return {
        "pairs": rows,
        "n_pairs": len(rows),
        "all_costs_equal": equal,
        "dijkstra_expanded_mean": round(d_mean, 1),
        "astar_expanded_mean": round(a_mean, 1),
        "nodes_saved_pct": round(100.0 * (1 - a_mean / d_mean), 1)
        if d_mean else 0.0,
    }


# ---------------------------------------------------------------------------
# one-call entry point
# ---------------------------------------------------------------------------

def _cluster_label(centroid: np.ndarray) -> Tuple[str, str]:
    """Plain-language label for a cluster from its centroid profile.

    Thresholds are calibrated on the 2026-10 data release: AJ coverage
    rarely exceeds 0.4 because most stations implement only a subset of
    the AJ item types, so 0.28 splits the step-free majority into
    "richer" vs "basic" entrance facilities.
    """
    aj, sf = float(centroid[0]), float(centroid[4])
    if sf < 0.5:
        return "not step-free end-to-end", "非全程免樓梯"
    if aj >= 0.28:
        return "step-free, richer facilities", "免樓梯 · 設施較全"
    return "step-free, basic facilities", "免樓梯 · 設施基本"


def full_analysis(registry: StationRegistry, graph: TransitGraph,
                  seed: int = 42, k_min: int = 2, k_max: int = 8
                  ) -> dict:
    """The whole analysis suite in one payload (API + report artefact)."""
    X, sids = feature_matrix(registry)
    stations = registry.stations

    ks = list(range(k_min, k_max + 1))
    sse_by_k, sil_by_k = {}, {}
    runs = {}
    for k in ks:
        run = kmeans(X, k, seed=seed)
        runs[k] = run
        sse_by_k[k] = round(run["sse"], 3)
        sil_by_k[k] = round(silhouette_score(X, run["labels"]), 3)
    chosen_k = elbow_knee(ks, [sse_by_k[k] for k in ks])

    clusters = []
    for j in range(chosen_k):
        members = [sids[i] for i in range(len(sids))
                   if runs[chosen_k]["labels"][i] == j]
        centroid = runs[chosen_k]["centers"][j]
        label_en, label_zh = _cluster_label(centroid)
        clusters.append({
            "cluster": j,
            "label_en": label_en, "label_zh": label_zh,
            "size": len(members),
            "centroid": {name: round(float(v), 3)
                         for name, v in zip(FEATURE_NAMES, centroid)},
            "stations": [
                {"name_en": stations[sid].name_en,
                 "name_zh": stations[sid].name_zh,
                 "step_free": is_step_free(stations[sid])}
                for sid in members],
        })
    clusters.sort(key=lambda c: -c["size"])

    return {
        "meta": {"n_stations": len(sids),
                 "features": FEATURE_NAMES,
                 "seed": seed},
        "kmeans": {"k_range": ks,
                   "sse_by_k": sse_by_k,
                   "silhouette_by_k": sil_by_k,
                   "chosen_k": chosen_k,
                   "chosen_silhouette": sil_by_k[chosen_k],
                   "silhouette_peak_k": max(sil_by_k, key=sil_by_k.get),
                   "selection": "elbow/knee (max distance to scree chord)"},
        "clusters": clusters,
        "line_coverage": line_coverage(registry),
        "gaps": gap_analysis(registry),
        "benchmark": benchmark_search(graph, seed=seed),
    }
