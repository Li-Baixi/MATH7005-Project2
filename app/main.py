"""AccessHK API service (FastAPI).

Serves the demo frontend and a small JSON API over the Python core:

    GET /api/stations              station list for pickers
    GET /api/route?from=&to=       fastest vs step-free comparison
    GET /api/station/{name}        accessibility profile of one station

Run from the project root:

    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

For the phone demo the laptop runs this server and the phone (same
Wi-Fi) opens http://<laptop-ip>:8000 — no internet needed at show time.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from accesshk.datasets import Station, StationRegistry
from accesshk.graph import TransitGraph
from accesshk.routing import compare_routes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORK = os.path.join(BASE, "data", "processed", "network.json")

app = FastAPI(title="AccessHK", version="0.1.0")


def _load_network(path: str):
    """Rebuild the runtime objects from the processed bundle produced by
    ``scripts/build_network.py`` (keeps startup instant and the API a
    pure consumer of the pipeline artefact)."""
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


REGISTRY, GRAPH, META, ITEM_LABELS = _load_network(NETWORK)


@app.get("/api/stations")
def list_stations():
    """Station pickers: name pair, serving lines, step-free flag."""
    return [
        {"name_en": st.name_en, "name_zh": st.name_zh, "code": st.code,
         "lines": sorted(st.lines), "step_free": GRAPH.step_free_nodes[
             GRAPH.station_nodes[st.sid][0]]}
        for st in sorted(REGISTRY.stations.values(),
                         key=lambda s: s.name_en)
    ]


@app.get("/api/route")
def route(from_station: str = Query(alias="from"),
          to_station: str = Query(alias="to")):
    """Compare fastest vs guaranteed step-free journeys."""
    origin = REGISTRY.search(from_station)
    destination = REGISTRY.search(to_station)
    if origin is None or destination is None:
        raise HTTPException(404, "unknown station name")
    if origin is destination:
        raise HTTPException(400, "origin and destination are the same")
    return compare_routes(GRAPH, origin, destination)


@app.get("/api/station/{name}")
def station_profile(name: str):
    """One station's full accessibility profile (evidence + coverage)."""
    from accesshk.facilities import category_coverage, step_free_evidence
    st = REGISTRY.search(name)
    if st is None:
        raise HTTPException(404, "unknown station name")
    return {
        "name_en": st.name_en, "name_zh": st.name_zh, "lines": sorted(st.lines),
        "step_free": GRAPH.step_free_nodes[GRAPH.station_nodes[st.sid][0]],
        "evidence": step_free_evidence(st),
        "coverage": category_coverage(st),
        "facilities": {k: v for k, v in st.facilities.items() if v},
        "labels": ITEM_LABELS,
    }


@app.get("/api/meta")
def meta():
    return META


# demo frontend (PWA shell — demo only, production would ship a native app
# against this same Python API)
app.mount("/", StaticFiles(directory=os.path.join(BASE, "app", "static"),
                           html=True), name="static")
