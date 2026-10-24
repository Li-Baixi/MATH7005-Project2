"""AccessHK API service (FastAPI).

Serves the demo frontend and a small JSON API over the Python core:

    GET /api/stations              station list for pickers
    GET /api/route?from=&to=       fastest vs step-free comparison
    GET /api/station/{name}        accessibility profile of one station
    GET /api/analysis              clustering + benchmark analytics
    GET /api/bus-routes            feeder-bus route ids
    GET /api/bus-eta?route=        live feeder-bus arrivals (cached
                                   fallback when offline, labelled)

Run from the project root:

    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

For the phone demo the laptop runs this server and the phone (same
Wi-Fi) opens http://<laptop-ip>:8000 — no internet needed at show time.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from accesshk.analysis import full_analysis
from accesshk.bundle import load_network
from accesshk.fares import load_fare_tables
from accesshk.realtime import (CACHE_FILENAME, bus_routes, get_eta,
                               load_bus_stops)
from accesshk.routing import compare_routes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORK = os.path.join(BASE, "data", "processed", "network.json")
RAW = os.path.join(BASE, "data", "raw")

app = FastAPI(title="AccessHK", version="0.3.0")

REGISTRY, GRAPH, META, ITEM_LABELS = load_network(NETWORK)

try:
    FARES = load_fare_tables(RAW, REGISTRY)
    BUS_STOPS = load_bus_stops(os.path.join(RAW, "mtr_bus_stops.csv"))
except FileNotFoundError:                      # partial checkout: degrade
    FARES, BUS_STOPS = None, {}


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
    return compare_routes(GRAPH, origin, destination, fare_tables=FARES)


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


_analysis_cache: dict | None = None


@app.get("/api/analysis")
def analysis():
    """Full analytics payload (k-means clustering, line coverage, gaps,
    Dijkstra-vs-A* benchmark).  Computed once on first request — 97
    stations make this instant — and cached for the session."""
    global _analysis_cache
    if _analysis_cache is None:
        _analysis_cache = full_analysis(REGISTRY, GRAPH)
    return _analysis_cache


@app.get("/api/bus-routes")
def feeder_routes():
    """Feeder-bus route ids for the ETA picker."""
    return {"routes": bus_routes(BUS_STOPS)}


@app.get("/api/bus-eta")
def bus_eta(route: str = Query("K12"), lang: str = Query("en")):
    """Live feeder-bus arrivals for one route (POST to rt.data.gov.hk),
    with a labelled cached fallback when the API is unreachable."""
    if route not in bus_routes(BUS_STOPS):
        raise HTTPException(404, "unknown bus route")
    cache = os.path.join(os.path.dirname(NETWORK), CACHE_FILENAME)
    try:
        payload = get_eta(route, BUS_STOPS, cache, language=lang)
    except Exception:
        raise HTTPException(
            503, "bus ETA unavailable (offline and no cached snapshot)")
    if FARES:
        payload["fares"] = FARES["bus"].get(route)
    return payload


# demo frontend (PWA shell — demo only, production would ship a native app
# against this same Python API)
app.mount("/", StaticFiles(directory=os.path.join(BASE, "app", "static"),
                           html=True), name="static")
