"""Build the static PWA bundle for GitHub Pages.

The Python core precomputes every origin->destination comparison
(9,312 pairs, ~6 s) plus the analysis payload, so the hosted demo is a
pure static site: no backend to run, installable from the phone
browser, and every route query is one lazy JSON fetch.

Usage (from the project root):

    python -I scripts/build_site.py data/processed/network.json data/raw site

Layout produced under the output dir:

    index.html ... app shell (copied from app/static)
    stations.json        picker data (sid-keyed)
    analysis.json        full analytics payload
    bus_data.json        feeder-bus routes, stop names, fares
    routes/{sid}.json    per-origin: {pairs: {dst: comparison result}}
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from accesshk.analysis import full_analysis
from accesshk.bundle import load_network
from accesshk.fares import load_fare_tables
from accesshk.l10n import to_simplified
from accesshk.realtime import bus_routes, load_bus_stops
from accesshk.routing import compare_routes

NETWORK, RAW, OUT = (sys.argv[1], sys.argv[2], sys.argv[3])
STATIC = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "app", "static")


def main() -> None:
    registry, graph, _meta, _labels = load_network(NETWORK)
    fares = load_fare_tables(RAW, registry)
    stops = load_bus_stops(os.path.join(RAW, "mtr_bus_stops.csv"))

    os.makedirs(os.path.join(OUT, "routes"), exist_ok=True)
    for f in os.listdir(STATIC):
        shutil.copy(os.path.join(STATIC, f), os.path.join(OUT, f))

    stations = [
        {"sid": sid, "name_en": st.name_en, "name_zh": st.name_zh,
         "name_zh_cn": to_simplified(st.name_zh),
         "code": st.code, "lines": sorted(st.lines),
         "lat": st.coord[0], "lon": st.coord[1],
         "step_free": graph.step_free_nodes[graph.station_nodes[sid][0]]}
        for sid, st in sorted(registry.stations.items(), key=lambda kv: int(kv[0]))
    ]
    _dump(os.path.join(OUT, "stations.json"), stations)

    n_pairs = 0
    sids = sorted(registry.stations, key=int)
    for sid in sids:
        origin = registry.stations[sid]
        pairs = {}
        for other in sids:
            if other == sid:
                continue
            result = compare_routes(graph, origin,
                                    registry.stations[other],
                                    fare_tables=fares)
            if result["fastest"] is not None:
                pairs[other] = result
                n_pairs += 1
        _dump(os.path.join(OUT, "routes", f"{sid}.json"),
              {"origin": sid, "pairs": pairs})

    _dump(os.path.join(OUT, "analysis.json"),
          full_analysis(registry, graph))
    _dump(os.path.join(OUT, "bus_data.json"), {
        "routes": bus_routes(stops),
        "stops": {sid: {**s, "name_zh_cn": to_simplified(s["name_zh"])}
                  for sid, s in stops.items()},
        "fares": fares["bus"],
    })

    total = sum(os.path.getsize(os.path.join(r, f))
                for r, _d, fs in os.walk(OUT) for f in fs)
    biggest = max((os.path.getsize(os.path.join(r, f)), os.path.join(r, f))
                  for r, _d, fs in os.walk(OUT) for f in fs)
    print(f"precomputed {n_pairs} origin-destination pairs")
    print(f"site size: {total / 1e6:.1f} MB total, "
          f"largest file {biggest[0] / 1e3:.0f} KB ({biggest[1]})")
    print("wrote", OUT)


def _dump(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
