# AccessHK — Barrier-Free MTR Journey Planner

**MATH7005 Data Product Development · Task 2 (90%) · 2026/27**
Repository: https://github.com/Li-Baixi/MATH7005-Project2

---

## 1. Problem

Hong Kong's MTR is one of the world's most accessible metros on paper
— yet journey planners available today optimise for minutes, not for
*stairs*. For the roughly 62 out of every 98 people in Hong Kong who
are elderly or live with a disability (C&SD 2021 basis, as cited in
the project pitch), "fastest route" is the wrong objective: a route
that saves three minutes but includes one broken escalator or a
footbridge is not a route they can take.

**Users:** wheelchair users, elderly passengers, people with strollers
or luggage, and carers assisting them.

**Need:** a journey planner whose primary objective is *guaranteed
step-free travel* — street → concourse → platform → train → exit —
backed by official per-exit facility data, not crowd-sourced tags.

**Impact:** AccessHK answers three questions the incumbent tools
cannot: (1) is this journey possible without stairs, end to end?
(2) *which entrance/exit and which lift* should I use at each end?
(3) if it is impossible, which nearby station should I travel to
instead, and what does the trip cost me at concession fares?

## 2. Data

### 2.1 Primary source (data.gov.hk)

Dataset *"MTR Routes, Fares and Barrier-Free Facilities"* (monthly
release, 9 CSVs + 1 real-time API, mirrored from opendata.mtr.com.hk):

| File | Role in the product |
|---|---|
| `mtr_lines_and_stations.csv` | network topology: 97 stations, 10 lines, per-line sequences |
| `barrier_free_facilities.csv` | per-station *and per-exit* facility flags (AJ/MJ/VJ/HJ codes) |
| `mtr_lines_fares.csv` | 9,216 origin-destination fares incl. distance-tiered elderly/PWD Octopus concessions (from $2) |
| `airport_express_fares.csv` | AEL fares (separate id space, joined by name) |
| `mtr_bus_stops.csv` / `mtr_bus_fares.csv` / `mtr_bus_routes.csv` | feeder-bus stop table (ids, coordinates, bilingual names) + fares |
| `rt.data.gov.hk` bus schedule API | **live** arrival forecasts (see §3.4) |

### 2.2 Supplementary source (declared)

The official `Exit_Coordinate_X_Y` column is **empty for all 3,564
facility rows** — a verified data-quality gap. Station coordinates
(needed for distance heuristics and nearest-station fallback) were
therefore fetched from the Wikipedia API (en + zh wikis,
`coprimary=all`, rate-limit-safe resumable script
[fetch_coords.py](../scripts/fetch_coords.py)): **97/97 stations
matched**, cached and committed as
[data/supplementary/station_coords.json](../data/supplementary/station_coords.json).

### 2.3 Data engineering findings (the honest part)

* **Three id spaces collide.** The facilities file uses a second id
  for three Airport Express stations (44/45/46 vs 39/40/42); the AEL
  fares file uses a third (44/45/47/56). We reconcile them
  ([datasets.py](../accesshk/datasets.py): `DUAL_ID_MAP`) and join the
  AEL fares **by name**, not id.
* **The official data marks 4 stations as not step-free end-to-end**
  (Fortress Hill — no street access; Tsing Yi, Airport, Po Lam — no
  paid-area lift), contradicting on-site signage. We keep the data
  faithful (93/97 step-free) and surface it as a finding — §5 shows
  unsupervised clustering *independently rediscovers* these four.
* **The real-time bus API is POST-only.** GET with the documented
  parameters returns `404` from the gateway; the fix (documented in
  [realtime.py](../accesshk/realtime.py)) is a POST with a JSON body
  `{"language", "routeName"}`.

## 3. Methods (all hand-written Python/NumPy — no sklearn shortcuts)

### 3.1 Rule-based classification: the step-free verdict

A station is step-free end-to-end iff (1) it has at least one
street→concourse step-free item (ramp `AJ2`, lift `AJ3`, same-level
`AJ1`, …) and (2) a concourse→platform item (paid-area lift `AJ8`,
stair lift `AJ5`, …). Codes and verdict logic:
[facilities.py](../accesshk/facilities.py). The per-exit `AJTextEn`
field lets us name *which exit* — the product's key differentiator.

### 3.2 Graph mining: hand-written Dijkstra and A*

The network is a **line-platform node graph**: a node is (station,
line); consecutive stations on a line are joined by ride edges
weighted by haversine distance ÷ per-line speed + dwell; same-station
platform pairs are joined by transfer edges (5 min; 8 min
step-free-profile, modelling lift detours). Both shortest-path
algorithms are implemented from scratch with binary heaps
([routing.py](../accesshk/routing.py)). A* uses an **admissible**
heuristic — straight-line distance ÷ network-max-speed (110 km/h) —
so it provably returns the same optimum as Dijkstra.

The headline query `compare_routes` runs both profiles and, when a
step-free route is impossible, computes the *nearest step-free
station* (NumPy haversine) as fallback advice.

### 3.3 Clustering: hand-written k-means over station feature vectors

Each station is a 5-dim vector: AJ/MJ/VJ/HJ category-coverage
fractions + step-free indicator. Implemented from scratch
([analysis.py](../accesshk/analysis.py)): **k-means++** seeding,
Lloyd iterations with best-of-10 restarts, **elbow selection** via
max distance to the scree chord, and a hand-written **silhouette**
score for validation. Per-line coverage and a weighted accessibility
score power the "weakest stations" gap analysis.

### 3.4 Real-time data product: live feeder-bus ETA with graceful degradation

`realtime.py` POSTs the rt.data.gov.hk schedule API, joins `busStopId`
to the static stop table (exact-match; U-prefix = outbound, D =
inbound), and summarises next arrivals per stop. Every successful
response is mirrored, timestamped, into a snapshot cache; when the
venue Wi-Fi dies the API serves that snapshot **labelled
`source: "cached"`** — the UI shows the label, so stale data can never
masquerade as live data.

### 3.5 Fare integration

MTR fares depend on entry/exit stations (not the path), so one table
lookup annotates both route variants: adult, **elderly $2**, **PWD
$2** Octopus fares; Airport Express rows (no concession columns in the
source) are joined by name and flagged. Feeder-bus fares annotate the
live ETA card the same way ([fares.py](../accesshk/fares.py)).

## 4. Product

A single Python core (`accesshk/` package) exposes everything through
FastAPI (`app/main.py`):

```
GET /api/stations        GET /api/route?from=&to=
GET /api/station/{name}  GET /api/analysis
GET /api/bus-routes      GET /api/bus-eta?route=K12
```

The demo front-end is an **installable PWA** (manifest + service
worker + PNG icons): add-to-home-screen from the phone browser, opens
full-screen standalone; the shell is cached for offline open while
API calls stay live. It is deliberately a thin shell — per the
project's own scoping, production would be a native app over this same
Python API. **Age-friendly by design**: 20px base type, high-contrast
Morandi palette, two selects and one primary button, a one-tap
"use my location" origin picker (browser geolocation → nearest MTR
station), Chinese station names inside itineraries, and a trilingual
interface (繁/簡/EN — Simplified names come from a hand-written
Traditional→Simplified converter, `accesshk/l10n.py`); every card
states its data source. 21 automated tests (`python -m pytest`) cover
routing equivalence, clustering ground truth, fare lookups, the
offline fallback and the converter.

**Public deployment** (https://li-baixi.github.io/MATH7005-Project2/):
the same Python core precomputes all 9,312 origin→destination
comparisons into static JSON shards (~6 s build,
`scripts/build_site.py`), which GitHub Pages serves — the hosted demo
needs no backend at all, and the phone browser calls the live bus API
directly (CORS is open). The deployment is a build artefact of the
Python core, exactly like a static site generator.

## 5. Findings

* **93/97 stations** are step-free end-to-end per official data; the 4
  exceptions cluster into exactly one k-means cluster — the
  unsupervised analysis *independently rediscovers* the data-quality
  exception list (§2.3) from facility vectors alone.
* **The strongest natural structure is binary**: silhouette peaks at
  k = 2 (s = 0.83) — step-free vs not. The scree-knee k = 5 refines
  the step-free majority into "richer" (56 stations) vs "basic" (37)
  entrance-facility tiers.
* **AEL is the least accessible line** (3/5 step-free, 60%) — a direct
  consequence of two of the four flagged stations lying on it.
* **A* explores 21.6% fewer nodes** than Dijkstra on 30 random
  station pairs, with **identical optimal cost on every pair** — the
  admissibility guarantee verified empirically on the real network.

## 6. Applied research paper

Nie et al. (2022/2023), *"A Time Series is Worth 64 Words"* (ICLR
2023, PatchTST) — verified 5,114 citations (Semantic Scholar,
2026-10-24), original methods paper. Its channel-independence +
patching design maps directly onto forecasting per-route bus headways
to replace our constant 2.5-min wait estimate; our cache layer is
already the ingestion pipeline such a model would train on. Full
analysis: [paper-analysis.md](paper-analysis.md).

## 7. Limitations

1. **Edge weights are modelled, not measured** — no official MTR
   travel-time dataset exists; ride times are haversine ÷ line speed
   + dwell, calibrated constants documented in
   [graph.py](../accesshk/graph.py).
2. **4 stations contradict signage** (§2.3); we chose fidelity to the
   graded data source and surface the discrepancy rather than
   hand-patch it.
3. **Elderly/PWD concessions assumed available** — eligibility rules
   (JoyYou card age thresholds etc.) are not encoded in any dataset.
4. **Live bus ETA depends on rt.data.gov.hk uptime**; offline demo
   degrades to a labelled cache rather than silently wrong data.
5. **No in-station navigation** (which corridor, which lift bank) —
   the data has per-exit resolution, not per-corridor.

## 8. AI use

Declared in full in [ai-use.md](ai-use.md). In brief: AI (Claude Code)
assisted with scaffolding, debugging and drafting under continuous
human direction; every algorithmic core (Dijkstra, A*, k-means++,
silhouette, elbow, haversine) was specified to be hand-written and is
tested; all data statements in this report were verified against the
downloaded files.

## 9. Future steps

1. **Wait-time forecasting** with a PatchTST-style channel-independent
   model trained on our accumulating cache corpus (§6).
2. **Real-time lift outage feed** — good-to-have dataset proposed to
   data.gov.hk; would turn "step-free on paper" into "step-free now".
3. **In-station wayfinding** via tactile-path data + station floor
   plans (good-to-have proposal).
4. **Native app** (the PWA is a demo shell) with saved accessibility
   profiles (e.g. "avoid lifts", "toilet needed").
5. **Demand estimation** from district-level census to prioritise the
   gap-analysis output for advocacy.

## Appendix: reproduction

```bash
pip install -r requirements.txt
python scripts/fetch_coords.py     # supplementary coords (cached: 97/97)
python -I scripts/build_network.py data/raw data/supplementary data/processed
python -I scripts/run_analysis.py data/processed/network.json
python -m pytest tests/ -q
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
