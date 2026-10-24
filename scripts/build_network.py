"""Run the full data pipeline: raw CSVs -> processed network bundle.

Usage (from the project root):

    python -I scripts/build_network.py data/raw data/supplementary data/processed

Produces ``data/processed/network.json`` containing the serialised graph,
station registry and facility evidence — the single artefact the API and
the analysis notebooks consume.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from accesshk.datasets import (attach_coordinates, attach_facilities,
                               load_category_table, load_lines_and_stations)
from accesshk.facilities import (category_coverage, is_step_free,
                                 step_free_evidence)
from accesshk.graph import build_graph

RAW, SUP, PROC = sys.argv[1], sys.argv[2], sys.argv[3]


def main() -> None:
    registry, seqs = load_lines_and_stations(
        os.path.join(RAW, "mtr_lines_and_stations.csv"))

    warnings = attach_facilities(
        registry, os.path.join(RAW, "barrier_free_facilities.csv"))
    joined = attach_coordinates(
        registry, os.path.join(SUP, "station_coords.json"))
    categories = load_category_table(
        os.path.join(RAW, "barrier_free_facility_category.csv"))

    graph = build_graph(registry, seqs)

    step_free_count = sum(
        1 for st in registry.stations.values() if is_step_free(st))

    payload = {
        "meta": {
            "source": "data.gov.hk - MTR Routes, Fares and Barrier-Free "
                      "Facilities (monthly release)",
            "supplementary": "OpenStreetMap station coordinates",
            "stations": len(registry.stations),
            "lines": sorted({line for st in registry.stations.values()
                             for line in st.lines}),
            "graph_nodes": len(graph.node_key),
            "coords_joined": joined,
            "step_free_stations": step_free_count,
            "warnings": warnings,
        },
        "item_labels": {code: {"en": row["Facility_En"], "zh": row["Facility_Zh"],
                               "category": row["Category_En"]}
                        for code, row in categories.items()},
        "stations": {sid: {
            **st.to_dict(),
            "step_free": is_step_free(st),
            "coverage": category_coverage(st),
            "evidence": step_free_evidence(st),
        } for sid, st in sorted(registry.stations.items(), key=lambda kv: int(kv[0]))},
        "graph": {
            "node_key": [[sid, line] for sid, line in graph.node_key],
            "edges": graph.edges,
            "step_free_nodes": graph.step_free_nodes,
        },
    }

    os.makedirs(PROC, exist_ok=True)
    out = os.path.join(PROC, "network.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    m = payload["meta"]
    print(f"stations: {m['stations']}  lines: {len(m['lines'])}  "
          f"graph nodes: {m['graph_nodes']}  coords joined: {m['coords_joined']}")
    print(f"step-free stations (street->platform): "
          f"{m['step_free_stations']}/{m['stations']}")
    for w in warnings:
        print("WARN:", w)
    print("wrote", out)


if __name__ == "__main__":
    main()
