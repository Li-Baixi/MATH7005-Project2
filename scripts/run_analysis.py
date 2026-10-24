"""Run the full analysis suite: network.json -> analysis.json.

Usage (from the project root):

    python -I scripts/run_analysis.py data/processed/network.json

Writes ``analysis.json`` next to the network bundle and prints a short
human summary (cluster sizes, weakest lines, benchmark headline).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from accesshk.analysis import full_analysis
from accesshk.bundle import load_network

NETWORK = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    "data", "processed", "network.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(NETWORK)),
                   "analysis.json")


def main() -> None:
    registry, graph, _meta, _labels = load_network(NETWORK)
    payload = full_analysis(registry, graph)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    km = payload["kmeans"]
    print(f"k-means: chosen k={km['chosen_k']} "
          f"(silhouette {km['chosen_silhouette']}, "
          f"selection: {km['selection']})")
    for c in payload["clusters"]:
        print(f"  cluster {c['cluster']} [{c['label_en']}]: "
              f"{c['size']} stations")
    lines = sorted(payload["line_coverage"],
                   key=lambda r: r["step_free_pct"])
    print("weakest lines by step-free share:")
    for row in lines[:3]:
        print(f"  {row['line']}: {row['step_free']}/{row['stations']} "
              f"({row['step_free_pct']}%)")
    b = payload["benchmark"]
    print(f"benchmark: {b['n_pairs']} pairs, costs all equal: "
          f"{b['all_costs_equal']}, nodes saved by A*: "
          f"{b['nodes_saved_pct']}%")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
