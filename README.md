# AccessHK — Barrier-Free Journey Planner for Hong Kong

MATH7005 2026/27 project. AccessHK plans MTR journeys that are
**guaranteed step-free, end to end** — naming the entrance, the lift and
the exit — instead of just the fastest route.

**📱 线上版 / Hosted demo:** https://li-baixi.github.io/MATH7005-Project2/
open on a phone browser → menu → *Add to Home Screen* → it installs as
a standalone app (installable PWA, works offline for visited queries;
live feeder-bus ETA is fetched directly from rt.data.gov.hk).

## How the hosted version works

GitHub Pages serves static files only — so the Python core **precomputes
every origin→destination comparison** (9,312 pairs, one ~6 s build) into
per-origin JSON shards the front-end lazy-loads. The deployment is a
build artefact of the Python core, like a static site generator; the
FastAPI service in `app/` remains the product's reference architecture.

```bash
python -I scripts/build_site.py data/processed/network.json data/raw site
python -I scripts/deploy_site.py site      # pushes gh-pages + points Pages at it
```

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
| data.gov.hk — [MTR Routes, Fares and Barrier-Free Facilities](https://data.gov.hk/en-data/dataset/mtr-data-routes-fares-barrier-free-facilities) | **primary**: network, sequences, per-exit barrier-free facilities, fares (rail + AEL + feeder bus) | Open Data (MTR Corporation) |
| rt.data.gov.hk — MTR bus schedule API | **primary (live)**: real-time feeder-bus arrivals (POST `getSchedule`) | Open Data (MTR Corporation) |
| Wikipedia API | supplementary: station coordinates (official exit-coordinate column is empty in the current release) | CC BY-SA |

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

# 4. run the analysis suite (clustering, coverage, benchmark)
python -I scripts/run_analysis.py data/processed/network.json

# 5. tests
python -m pytest tests/ -q

# 6. serve the API + demo PWA
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Phone demo tip: `adb reverse tcp:8000 tcp:8000` over USB lets the
phone browse `http://localhost:8000` — a secure context, so Chrome
offers **Install app** and the PWA opens full-screen from the home
screen (see `docs/demo-script.md`).

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
5. **Hand-written k-means** — k-means++ seeding, best-of-n restarts,
   elbow/knee selection and a from-scratch silhouette score over
   station facility vectors (`accesshk/analysis.py`); per-line
   coverage and weighted accessibility scores power the gap analysis.
6. **Real-time integration** — POST-only rt.data.gov.hk bus ETA with
   stop-name joins and a *labelled* offline cache fallback
   (`accesshk/realtime.py`).
7. **Fare analytics** — origin-destination table lookups incl. the $2
   elderly/PWD Octopus concessions; Airport Express joined by name
   across its private id space (`accesshk/fares.py`).

## Repo layout

```
accesshk/     Python package (product core)
scripts/      data pipeline + utility scripts
app/          FastAPI service and demo frontend (PWA shell, demo-only)
tests/        pytest suite (18 tests)
data/raw/     downloaded CSVs (git-ignored; re-download per README)
data/supplementary/  cached Wikipedia coordinates (committed)
data/processed/      built network/analysis bundles (git-ignored)
docs/         report, demo script, paper analysis, AI-use declaration
```

## Documents

- [docs/report.md](docs/report.md) — final report
- [docs/demo-script.md](docs/demo-script.md) — 10-minute demo plan (no slides)
- [docs/paper-analysis.md](docs/paper-analysis.md) — applied paper (PatchTST, ICLR 2023)
- [docs/ai-use.md](docs/ai-use.md) — AI use declaration
- [docs/requirements-checklist.md](docs/requirements-checklist.md) — requirement → implementation map
