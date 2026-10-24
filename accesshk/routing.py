"""Hand-written shortest-path routing over the line-platform graph.

Two classic algorithms are implemented from scratch (no networkx, no
scipy, no scikit-learn):

* :func:`dijkstra`  — binary-heap Dijkstra over adjacency lists
* :func:`astar`     — A* with a haversine / max-line-speed heuristic,
                      which is *admissible*: it can never overestimate
                      the remaining in-train time, so A* returns exactly
                      the same optimal cost as Dijkstra, only faster.

Routing profiles
----------------
``fastest``    minimise estimated total minutes (any station allowed)
``step_free``  only stations that are step-free street-to-platform;
               transfers cost more (lifts and concourse detours)

The itinerary builder folds the node path back into human steps:
ride segments ("board at X, alight at Y, n stops, line L"), transfers,
and entrance/exit advice drawn from the per-exit facility data.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .datasets import StationRegistry, Station
from .facilities import (ITEM_LABELS, NON_MTR_MANAGED, is_step_free,
                         nearest_step_free, step_free_evidence,
                         step_free_exits)
from .geo import haversine_km
from .graph import MAX_SPEED_KMH, TRANSFER_MIN_STEPFREE, TransitGraph

PROFILE_TRANSFER_MIN = {"fastest": None, "step_free": TRANSFER_MIN_STEPFREE}
BOARDING_WAIT_MIN = 2.5     # expected wait per ride, shown separately


def dijkstra(graph: TransitGraph, source: int, target: int,
             allowed: Optional[List[bool]] = None,
             transfer_minutes: Optional[float] = None,
             stats: Optional[dict] = None
             ) -> Tuple[float, List[int]]:
    """Classic Dijkstra with a binary heap.

    ``allowed`` masks out nodes (used for the step-free profile) and
    ``transfer_minutes`` optionally overrides the cost of transfer edges
    (they take longer when you must hunt for lifts).  ``stats`` (optional
    dict) is filled with ``expanded`` = number of nodes settled — used by
    the analysis module to benchmark against A*.  Returns
    ``(cost, node_path)``; cost is ``inf`` when unreachable.
    """
    n = len(graph.node_key)
    dist = [float("inf")] * n
    prev: List[Optional[int]] = [None] * n
    dist[source] = 0.0
    heap = [(0.0, source)]
    visited = [False] * n

    while heap:
        d, u = heapq.heappop(heap)
        if visited[u]:
            continue
        visited[u] = True
        if stats is not None:
            stats["expanded"] = stats.get("expanded", 0) + 1
        if u == target:
            break
        for v, w, kind, _line in graph.edges[u]:
            if allowed is not None and not allowed[v]:
                continue
            if kind == "transfer" and transfer_minutes is not None:
                w = transfer_minutes
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[target] == float("inf"):
        return float("inf"), []
    path, node = [], target
    while node is not None:
        path.append(node)
        node = prev[node]
    return dist[target], path[::-1]


def astar(graph: TransitGraph, source: int, target: int,
          allowed: Optional[List[bool]] = None,
          transfer_minutes: Optional[float] = None,
          stats: Optional[dict] = None
          ) -> Tuple[float, List[int]]:
    """A* with an admissible heuristic: straight-line distance to the
    target station divided by the fastest line speed in the network.

    Because no train can beat that, the heuristic never overestimates,
    so the result matches Dijkstra exactly while exploring fewer nodes
    (``expanded`` counters in tests verify both properties)."""
    target_station = graph.station_of(target)
    t_coord = target_station.coord if target_station else None

    def h(node: int) -> float:
        if t_coord is None:
            return 0.0
        s = graph.station_of(node)
        if s is None or s.coord is None:
            return 0.0
        km = float(haversine_km(np.array([s.coord]), np.array([t_coord]))[0])
        return km / MAX_SPEED_KMH * 60.0

    n = len(graph.node_key)
    g = [float("inf")] * n
    prev: List[Optional[int]] = [None] * n
    g[source] = 0.0
    heap = [(h(source), 0.0, source)]
    closed = [False] * n

    while heap:
        _f, d, u = heapq.heappop(heap)
        if closed[u]:
            continue
        closed[u] = True
        if stats is not None:
            stats["expanded"] = stats.get("expanded", 0) + 1
        if u == target:
            break
        for v, w, kind, _line in graph.edges[u]:
            if allowed is not None and not allowed[v]:
                continue
            if kind == "transfer" and transfer_minutes is not None:
                w = transfer_minutes
            nd = d + w
            if nd < g[v]:
                g[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd + h(v), nd, v))

    if g[target] == float("inf"):
        return float("inf"), []
    path, node = [], target
    while node is not None:
        path.append(node)
        node = prev[node]
    return g[target], path[::-1]


# ---------------------------------------------------------------------------
# itinerary building
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    kind: str                 # "ride" | "transfer"
    line: str = ""
    board: str = ""           # station name
    alight: str = ""
    stops: int = 0
    minutes: float = 0.0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _refold(graph: TransitGraph, path: List[int]) -> Tuple[List[Segment], float]:
    """Collapse a node path back into human steps.

    Consecutive ride edges on the same line fold into one segment
    ("board at X, alight at Y, n stops"); every line change appears as an
    explicit transfer step.  Returns ``(segments, in_vehicle_minutes)``.
    """
    steps: List[Tuple[int, int, float, str, str]] = []      # u, v, w, kind, line
    for u, v in zip(path, path[1:]):
        _to, w, kind, line = next(e for e in graph.edges[u] if e[0] == v)
        steps.append((u, v, w, kind, line))

    segments: List[Segment] = []
    total = 0.0
    idx = 0
    while idx < len(steps):
        u, v, w, kind, line = steps[idx]
        if kind == "ride":
            board = graph.station_of(u).name_en
            alight, stops, minutes = graph.station_of(v).name_en, 1, w
            while idx + 1 < len(steps) and steps[idx + 1][3] == "ride" \
                    and steps[idx + 1][4] == line:
                idx += 1
                alight = graph.station_of(steps[idx][1]).name_en
                stops += 1
                minutes += steps[idx][2]
            segments.append(Segment("ride", line=line, board=board,
                                    alight=alight, stops=stops,
                                    minutes=round(minutes, 1)))
            total += minutes
        else:
            segments.append(Segment("transfer", board=graph.station_of(u).name_en,
                                    minutes=w))
            total += w
        idx += 1
    return segments, round(total, 1)


def _station_entry_advice(station: Station, entering: bool) -> List[dict]:
    """Entrance/exit advice from per-exit facility data (step-free only)."""
    advice = []
    for e in step_free_exits(station):
        advice.append({
            "exit": e["exit"],
            "via": ITEM_LABELS.get(e["item"], e["item"]),
            "mtr_managed": e["item"] not in NON_MTR_MANAGED,
        })
    return advice


def plan(graph: TransitGraph, origin: Station, destination: Station,
         profile: str = "fastest", algorithm: str = "dijkstra"
         ) -> Optional[dict]:
    """Route from *origin* to *destination* under a profile.

    Returns ``None`` when either endpoint is unreachable (e.g. a
    step-free route cannot start from a station without paid-area lifts).
    """
    algo = dijkstra if algorithm == "dijkstra" else astar

    allowed = None
    transfer_minutes = PROFILE_TRANSFER_MIN[profile]
    if profile == "step_free":
        allowed = list(graph.step_free_nodes)

    # pick any platform of the origin/destination that is allowed
    def pick(station: Station) -> Optional[int]:
        for node in graph.nodes_of_station(station.sid):
            if allowed is None or allowed[node]:
                return node
        return None

    best_result = None
    for src in graph.nodes_of_station(origin.sid):
        if allowed is not None and not allowed[src]:
            continue
        for dst in graph.nodes_of_station(destination.sid):
            if allowed is not None and not allowed[dst]:
                continue
            cost, path = algo(graph, src, dst, allowed, transfer_minutes)
            if path and (best_result is None or cost < best_result[0]):
                best_result = (cost, path)
    if best_result is None:
        return None

    cost, path = best_result
    segments, ride_minutes = _refold(graph, path)
    rides = [s for s in segments if s.kind == "ride"]
    transfers = [s for s in segments if s.kind == "transfer"]

    return {
        "origin": origin.name_en,
        "destination": destination.name_en,
        "profile": profile,
        "algorithm": algorithm,
        "in_vehicle_minutes": ride_minutes,
        "estimated_wait_minutes": round(BOARDING_WAIT_MIN * len(rides), 1),
        "total_minutes": round(ride_minutes + BOARDING_WAIT_MIN * len(rides), 1),
        "transfers": len(transfers),
        "segments": [s.to_dict() for s in segments],
        "origin_access": _station_entry_advice(origin, True),
        "destination_access": _station_entry_advice(destination, False),
        "step_free_guaranteed": profile == "step_free",
    }


def compare_routes(graph: TransitGraph, origin: Station,
                   destination: Station) -> dict:
    """The product's headline query: fastest route vs guaranteed
    step-free route, with a fallback suggestion when the latter is
    impossible from the requested endpoints.

    Fallback advice is only given for endpoints that are themselves not
    step-free (a compliant endpoint is never the problem), and unnamed
    step-free entrances are described honestly instead of silently
    producing an empty advice list.
    """
    fastest = plan(graph, origin, destination, "fastest")
    step_free = plan(graph, origin, destination, "step_free")

    fallback = None
    if step_free is None:
        all_stations = [st for st in graph.registry.stations.values()]
        fallback = {}
        for label, endpoint in (("origin", origin), ("destination", destination)):
            if is_step_free(endpoint):
                continue                    # this endpoint is not the blocker
            hit = nearest_step_free(endpoint, all_stations)
            if hit:
                advice = step_free_evidence(hit[0])["street_access"]
                if not advice:
                    advice = [{"exit": "entrance (unnamed in official data)",
                               "how": "step-free access",
                               "managed_by_mtr": True}]
                fallback[label] = {
                    "station": hit[0].name_en,
                    "distance_km": round(hit[1], 1),
                    "access": advice,
                }

    return {"fastest": fastest, "step_free": step_free, "fallback": fallback}
