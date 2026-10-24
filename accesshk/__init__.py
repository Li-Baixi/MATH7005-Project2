"""AccessHK — barrier-free journey planner for Hong Kong (MATH7005 project).

Python package layout:

* :mod:`accesshk.datasets`    — load & reconcile data.gov.hk MTR CSVs
* :mod:`accesshk.facilities`  — step-free verdicts from barrier-free data
* :mod:`accesshk.geo`         — NumPy haversine, coordinate helpers
* :mod:`accesshk.graph`       — line-platform routing graph construction
* :mod:`accesshk.routing`     — hand-written Dijkstra & A*, itinerary builder
"""

__version__ = "0.1.0"

from .datasets import StationRegistry, LineSequences, Station  # noqa: F401
from .graph import TransitGraph, build_graph                    # noqa: F401
from .routing import compare_routes, dijkstra, astar, plan      # noqa: F401
