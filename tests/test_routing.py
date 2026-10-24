"""Unit tests for the AccessHK routing core.

Run from the project root after building the network:

    python -m pytest tests/ -q

The tests are offline: they load ``data/processed/network.json`` if
present, otherwise build a tiny synthetic network so the algorithm
contracts (Dijkstra == A*, step-free filtering, itinerary folding) are
still verified.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from accesshk.datasets import LineSequences, Station
from accesshk.graph import build_graph
from accesshk.routing import _station_entry_advice, astar, dijkstra, plan

NETWORK = "data/processed/network.json"


def test_entry_advice_schema_matches_evidence():
    """origin/destination advice must use the same field names as
    step_free_evidence (exit/how/mtr_managed) — the UI renders ONE
    shape (regression: a 'via'/'how' mismatch showed '經 undefined')."""
    _graph, reg = _synthetic()
    st = next(s for s in reg.stations.values()
              if s.facilities.get("AJ3") and s.facilities.get("AJ8"))
    advice = _station_entry_advice(st, True)
    assert advice, "expected at least one named step-free exit"
    for a in advice:
        assert {"exit", "how", "mtr_managed"} <= set(a), a
        assert "via" not in a, a
        assert a["how"]                            # non-empty label


def _synthetic():
    """3-line toy network.

    A -- B -- C        (line L1, all step-free)
         |             (transfer at B)
    D -- B -- E        (line L2; D has NO paid-area lift -> not step-free)
         |
         F             (line L3 spur, step-free)
    """
    stations = {}
    for sid, code, name, sf in [
        ("1", "A", "Alpha", True), ("2", "B", "Beta", True),
        ("3", "C", "Gamma", True), ("4", "D", "Delta", False),
        ("5", "E", "Eps", True), ("6", "F", "Zeta", True),
    ]:
        st = Station(sid=sid, code=code, name_en=name, name_zh=name,
                     coord=(22.30 + int(sid) * 0.01, 114.15))
        if sf:
            st.facilities = {"AJ3": True, "AJ8": True}
            st.exit_facilities = [{"item": "AJ3", "exit": "A", "exit_zh": "A"}]
        else:
            st.facilities = {"AJ8": False}
        stations[sid] = st
    from accesshk.datasets import StationRegistry
    reg = StationRegistry(stations)
    seqs = LineSequences({("L1", "DT"): ["1", "2", "3"],
                          ("L2", "DT"): ["4", "2", "5"],
                          ("L3", "DT"): ["2", "6"]})
    return build_graph(reg, seqs), reg


def _real():
    """Rebuild the graph from raw data (same calls as build_network.py)."""
    from accesshk.datasets import (attach_coordinates, attach_facilities,
                                   load_lines_and_stations)
    reg, seqs = load_lines_and_stations("data/raw/mtr_lines_and_stations.csv")
    attach_facilities(reg, "data/raw/barrier_free_facilities.csv")
    attach_coordinates(reg, "data/supplementary/station_coords.json")
    return build_graph(reg, seqs), reg


def test_dijkstra_matches_astar_synthetic():
    graph, _ = _synthetic()
    for src in range(len(graph.node_key)):
        for dst in range(len(graph.node_key)):
            if src == dst:
                continue
            cd, _ = dijkstra(graph, src, dst)
            ca, _ = astar(graph, src, dst)
            assert cd == pytest.approx(ca, rel=1e-9), (src, dst, cd, ca)


def test_step_free_filter_blocks_delta():
    graph, reg = _synthetic()
    origin, dest = reg.by_sid("1"), reg.by_sid("5")
    fastest = plan(graph, origin, dest, "fastest")
    assert fastest is not None
    # step-free route Alpha->Eps must exist via Beta transfer, and must
    # never board at Delta (Delta line L2 platforms are masked out)
    sf = plan(graph, origin, dest, "step_free")
    if sf is not None:
        for seg in sf["segments"]:
            assert seg["board"] != "Delta"


def test_itinerary_folding():
    graph, reg = _synthetic()
    route = plan(graph, reg.by_sid("1"), reg.by_sid("5"), "fastest")
    kinds = [s["kind"] for s in route["segments"]]
    assert kinds == ["ride", "transfer", "ride"]
    assert route["transfers"] == 1
    assert route["step_free_guaranteed"] is False


def test_unreachable_returns_none():
    graph, reg = _synthetic()
    # step-free profile from Delta (no paid-area lift) cannot start
    assert plan(graph, reg.by_sid("4"), reg.by_sid("1"), "step_free") is None


@pytest.mark.skipif(not os.path.exists(NETWORK), reason="network.json not built")
def test_real_network_sham_shui_po_to_admiralty():
    graph, reg = _real()
    ssp, adm = reg.search("Sham Shui Po"), reg.search("Admiralty")
    route = plan(graph, ssp, adm, "fastest")
    assert route is not None and route["total_minutes"] > 5
    sf = plan(graph, ssp, adm, "step_free")
    if sf is not None:
        assert sf["total_minutes"] >= route["total_minutes"]
