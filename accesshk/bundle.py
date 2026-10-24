"""Load the processed network bundle back into runtime objects.

``scripts/build_network.py`` writes ``data/processed/network.json``; this
module is the single reader of that schema, shared by the API service
(``app/main.py``), the analysis scripts and anything else that needs a
ready-made registry + graph without re-running the CSV pipeline.
"""
from __future__ import annotations

import json
from typing import Tuple

from .datasets import Station, StationRegistry
from .graph import TransitGraph


def load_network(path: str
                 ) -> Tuple[StationRegistry, TransitGraph, dict, dict]:
    """Rebuild (registry, graph, meta, item_labels) from *path*."""
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    stations = {}
    for sid, d in payload["stations"].items():
        stations[sid] = Station(
            sid=sid, code=d["code"], name_en=d["name_en"],
            name_zh=d["name_zh"], lines=d["lines"],
            coord=(d["lat"], d["lon"]) if "lat" in d else None,
            facilities=d["facilities"],
            exit_facilities=d["exit_facilities"])

    registry = StationRegistry(stations)
    node_key = [(sid, line) for sid, line in payload["graph"]["node_key"]]
    station_nodes = {}
    for i, (sid, _line) in enumerate(node_key):
        station_nodes.setdefault(sid, []).append(i)

    graph = TransitGraph(
        node_key=node_key,
        node_index={k: i for i, k in enumerate(node_key)},
        edges=payload["graph"]["edges"],
        station_nodes=station_nodes,
        registry=registry,
        step_free_nodes=payload["graph"]["step_free_nodes"])

    return registry, graph, payload.get("meta", {}), payload.get("item_labels", {})
