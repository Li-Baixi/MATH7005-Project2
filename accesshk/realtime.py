"""Real-time MTR feeder-bus arrivals (rt.data.gov.hk live API).

API notes (the non-obvious part, cost us an hour of 404s):

* the endpoint is **POST**, not GET — ``GET ...?routeName=K12`` answers
  ``404 Resource not found`` from the gateway even with correct params
* body: ``{"language": "en"|"zh", "routeName": "K12"}``
* ``busStopId`` values join exactly against ``STATION_ID`` in the
  static ``mtr_bus_stops.csv`` (U-prefixed = outbound, D = inbound)

Demo-day resilience: :func:`get_eta` tries the live API first and
mirrors every successful response into a snapshot file; when the venue
Wi-Fi is down it serves that snapshot, clearly labelled
``source: "cached"`` — the UI shows the label so nobody mistakes
stale data for live data.
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.request
from typing import Dict, List

BUS_ETA_URL = "https://rt.data.gov.hk/v1/transport/mtr/bus/getSchedule"
CACHE_FILENAME = "bus_eta_cache.json"


def load_bus_stops(path: str) -> Dict[str, dict]:
    """busStopId -> {name_en, name_zh, lat, lon, route, direction, seq}."""
    stops: Dict[str, dict] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            stops[r["STATION_ID"]] = {
                "name_en": r["STATION_NAME_ENG"],
                "name_zh": r["STATION_NAME_CHI"],
                "lat": float(r["STATION_LATITUDE"]),
                "lon": float(r["STATION_LONGITUDE"]),
                "route": r["ROUTE_ID"],
                "direction": r["DIRECTION"],
                "seq": int(r["STATION_SEQNO"]),
            }
    return stops


def bus_routes(stops: Dict[str, dict]) -> List[str]:
    """Sorted route ids present in the static stop table."""
    return sorted({s["route"] for s in stops.values()})


def fetch_bus_eta(route: str, language: str = "en",
                  timeout: float = 8.0) -> dict:
    """POST the live API and return the raw payload (raises on any
    network/HTTP/JSON problem)."""
    body = json.dumps({"language": language, "routeName": route}).encode()
    req = urllib.request.Request(
        BUS_ETA_URL, data=body, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def summarize_eta(raw: dict, stops: Dict[str, dict],
                  max_arrivals: int = 3) -> List[dict]:
    """Raw API payload -> UI-friendly list (stop names joined from the
    static table, arrival texts, suspended flags)."""
    out: List[dict] = []
    for stop in raw.get("busStop", []):
        sid = stop.get("busStopId", "")
        info = stops.get(sid, {})
        arrivals = []
        for bus in (stop.get("bus") or [])[:max_arrivals]:
            arrivals.append({
                "text": bus.get("arrivalTimeText") or "",
                "in_minutes": round(int(bus.get("arrivalTimeInSecond", 0))
                                    / 60),
                "is_scheduled": bool(int(bus.get("isScheduled", "0"))),
                "is_delayed": bool(int(bus.get("isDelayed", "0"))),
            })
        out.append({
            "stop_id": sid,
            "name_en": info.get("name_en") or sid,
            "name_zh": info.get("name_zh") or sid,
            "suspended": bool(int(stop.get("isSuspended", "0") or 0)),
            "arrivals": arrivals,
        })
    return out


def get_eta(route: str, stops: Dict[str, dict], cache_path: str,
            language: str = "en", timeout: float = 8.0) -> dict:
    """Live fetch with write-through cache, falling back to the cached
    snapshot (labelled ``source: "cached"``) when the API is
    unreachable.  Raises only when neither live nor cached data exists.
    """
    try:
        raw = fetch_bus_eta(route, language, timeout)
        payload = {
            "route": route,
            "source": "live",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "refresh_seconds": int(raw.get("appRefreshTimeInSecond", 60)),
            "stops": summarize_eta(raw, stops),
        }
        os.makedirs(os.path.dirname(os.path.abspath(cache_path)),
                    exist_ok=True)
        tmp = cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        os.replace(tmp, cache_path)
        return payload
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            OSError, ValueError):
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
            cached["source"] = "cached"
            return cached
        raise
