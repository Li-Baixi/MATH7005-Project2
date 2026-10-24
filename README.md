# AccessHK — Barrier-Free Journey Planner for Hong Kong

MATH7005 2026/27 project. AccessHK plans MTR journeys that are
**guaranteed step-free, end to end** — naming the entrance, the lift and
the exit — instead of just the fastest route.

## Why

- 1.6M+ Hong Kong residents are 65 or older; 500K+ live with a
  disability. Mainstream planners optimise for time and cannot tell a
  stairs-only exit from a lift.
- Official data shows the gap is real: only ~62 of 98 MTR stations have
  a lift between street and concourse (unpaid area), even though 94 have
  paid-area lifts.

## Data

| Source | Role | Licence |
|---|---|---|
| data.gov.hk — [MTR Routes, Fares and Barrier-Free Facilities](https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities) | **primary**: network, sequences, per-exit barrier-free facilities, fares | Open Data (MTR Corporation) |
| OpenStreetMap (Overpass) | supplementary: station coordinates (official exit-coordinate column is empty in the current release) | ODbL |

## Architecture

```
Python core (100% of the product logic)      thin demo shell
┌────────────────────────────────────┐      ┌──────────────────┐
│ accesshk/                          │      │ app/ (FastAPI)   │
│  datasets.py  reconcile 3 ID spaces│◄─────┤  /api/route ...  │
│  facilities.py step-free verdicts  │      │  static PWA page │
│  graph.py     line-platform graph  │      └──────────────────┘
│  routing.py   hand-written         │      (demo-only PWA; a native
│               Dijkstra + A*        │       app would reuse the same
└────────────────────────────────────┘       Python core unchanged)
```

## Quickstart

```bash
pip install -r requirements.txt

# 1. download the MTR CSVs (see scripts/README or re-run curl commands)
# 2. optional: refresh station coordinates from OpenStreetMap
python -I scripts/fetch_coords.py data/raw data/supplementary

# 3. build the processed network bundle
python -I scripts/build_network.py data/raw data/supplementary data/processed

# 4. tests
python -m pytest tests/ -q
```

## Methods (hand-written, no scikit-learn one-liners)

1. **Data reconciliation** — three station-ID spaces unified with a
   documented canonical mapping (dual Airport-Express ids, Racecourse).
2. **Step-free verdicts** — rule-based classification from per-exit
   facility codes (street→concourse × concourse→platform).
3. **Routing graph** — line-platform nodes; edge minutes estimated with
   NumPy haversine distance / per-line speed + dwell (constants
   documented, no official travel times are published).
4. **Dijkstra & A\*** — binary-heap implementations written from
   scratch; A* heuristic (straight-line / max line speed) is provably
   admissible, verified equal-cost against Dijkstra in tests.
5. **Accessibility analytics** — category-coverage profiling and
   clustering of stations by facility vectors (see `accesshk/analysis`).

## Repo layout

```
accesshk/     Python package (product core)
scripts/      data pipeline + utility scripts
app/          FastAPI service and demo frontend (PWA shell, demo-only)
tests/        pytest suite
data/raw/     downloaded CSVs (git-ignored; re-download per README)
data/supplementary/  cached OSM coordinates
data/processed/      built network bundle (git-ignored)
docs/         requirement checklists, AI-use declaration
```
