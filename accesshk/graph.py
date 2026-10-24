"""Routing graph construction.

Model
-----
We use a **line-platform node** graph: a node is ``(station, line)`` —
"the Kwun Tong Line platform of Yau Ma Tei".  Riding between adjacent
stations on one line traverses a *ride edge*; changing lines at a
station traverses a *transfer edge*.  This makes transfers explicit,
costed, and visible in the itinerary, which a plain station graph
cannot do.

Edge weights
------------
The MTR open data publishes **no travel times**, so ride-edge minutes
are *estimated* and the estimation is fully documented:

    minutes = haversine_km(u, v) / line_speed_kmh * 60 + dwell_min

Line speeds are calibratable constants chosen from published MTR
service characteristics (Airport Express ~110 km/h cruise, cross-harbour
express ~80, urban lines ~40); dwell adds the station stop.  Transfer
edges carry a fixed penalty (longer in step-free mode, where lifts and
concourse detours take time).  When coordinates are missing for an edge
we fall back to a per-line fixed segment time instead of dropping it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .datasets import LineSequences, StationRegistry, Station
from .facilities import is_step_free
from .geo import haversine_km

# Calibration constants (documented in the report; deliberately explicit).
LINE_SPEED_KMH = {
    "AEL": 110.0,   # Airport Express
    "EAL": 80.0,    # East Rail (express, fewer stops)
    "TML": 75.0,    # Tuen Ma
    "DRL": 45.0,    # Disneyland Resort
    "TWL": 40.0, "ISL": 38.0, "KTL": 38.0, "TCL": 45.0,
    "TKL": 40.0, "SIL": 38.0,
}
DEFAULT_SPEED_KMH = 40.0
DWELL_MIN = 1.0            # station stop included in each ride edge
TRANSFER_MIN_NORMAL = 5.0  # same-station line change
TRANSFER_MIN_STEPFREE = 8.0  # lifts/detours take longer
FALLBACK_SEGMENT_MIN = {    # used only when an endpoint has no coords
    "AEL": 6.0, "EAL": 3.2, "TML": 2.4, "DRL": 3.0,
}
FALLBACK_DEFAULT_MIN = 2.2

# Highest line speed in the network -> admissible A* heuristic denominator.
MAX_SPEED_KMH = max(LINE_SPEED_KMH.values())


@dataclass
class TransitGraph:
    """Adjacency structure over line-platform nodes.

    ``edges[i]`` is a list of ``(j, minutes, kind, line)`` tuples where
    kind is ``"ride"`` or ``"transfer"``.  Everything the routers need is
    plain Python lists: the hand-written Dijkstra/A* in
    :mod:`accesshk.routing` therefore has zero framework magic in it.
    """
    node_key: List[Tuple[str, str]]                  # index -> (sid, line)
    node_index: Dict[Tuple[str, str], int]           # (sid, line) -> index
    edges: List[List[Tuple[int, float, str, str]]]
    station_nodes: Dict[str, List[int]]              # sid -> node indices
    registry: StationRegistry
    step_free_nodes: Optional[List[bool]] = None     # per-node accessibility

    def nodes_of_station(self, sid: str) -> List[int]:
        return self.station_nodes.get(sid, [])

    def station_of(self, node: int) -> Station:
        sid = self.node_key[node][0]
        return self.registry.by_sid(sid)

    def line_of(self, node: int) -> str:
        return self.node_key[node][1]


def _ride_minutes(u: Station, v: Station, line: str) -> float:
    """Estimated in-train minutes for one hop on *line* (see module doc)."""
    if u.coord is None or v.coord is None:
        return FALLBACK_SEGMENT_MIN.get(line, FALLBACK_DEFAULT_MIN)
    speed = LINE_SPEED_KMH.get(line, DEFAULT_SPEED_KMH)
    km = float(haversine_km(np.array([u.coord]), np.array([v.coord]))[0])
    return round(km / speed * 60.0 + DWELL_MIN, 2)


def build_graph(registry: StationRegistry,
                seqs: LineSequences) -> TransitGraph:
    """Build the line-platform graph from cleaned line sequences."""
    node_key: List[Tuple[str, str]] = []
    node_index: Dict[Tuple[str, str], int] = {}
    station_nodes: Dict[str, List[int]] = {}

    def ensure(sid: str, line: str) -> int:
        key = (sid, line)
        if key not in node_index:
            node_index[key] = len(node_key)
            node_key.append(key)
            station_nodes.setdefault(sid, []).append(node_index[key])
        return node_index[key]

    best: Dict[Tuple[int, int], Tuple[float, str, str]] = {}

    for (line, _direction), sids in seqs.sequences.items():
        for a, b in zip(sids, sids[1:]):
            st_a, st_b = registry.by_sid(a), registry.by_sid(b)
            if st_a is None or st_b is None:
                continue
            i, j = ensure(a, line), ensure(b, line)
            minutes = _ride_minutes(st_a, st_b, line)
            # spur lines may repeat a hop; keep the fastest variant
            for (x, y) in ((i, j), (j, i)):
                if (x, y) not in best or minutes < best[(x, y)][0]:
                    best[(x, y)] = (minutes, "ride", line)

    # transfer edges between all platforms sharing a station
    for sid, nodes in station_nodes.items():
        for x in nodes:
            for y in nodes:
                if x != y:
                    key = (x, y)
                    if key not in best or best[key][1] == "ride":
                        best[key] = (0.0, "transfer", "")
                    # ride edges already exist in both directions; only
                    # fill transfer where no ride edge is present

    edges: List[List[Tuple[int, float, str, str]]] = [[] for _ in node_key]
    for (x, y), (minutes, kind, line) in best.items():
        if kind == "transfer":
            minutes = TRANSFER_MIN_NORMAL     # profile adjusts at query time
        edges[x].append((y, minutes, kind, line))

    step_free_nodes = [is_step_free(registry.by_sid(sid))
                       for (sid, _line) in node_key]

    return TransitGraph(node_key=node_key, node_index=node_index, edges=edges,
                        station_nodes=station_nodes, registry=registry,
                        step_free_nodes=step_free_nodes)
