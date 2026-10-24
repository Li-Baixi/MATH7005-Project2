# Assignment Requirements → Implementation Map (living document)

Tracking every hard requirement from `MATH7005_project_2026.pdf`,
the teacher's Q&A answers, and the project owner's own constraints.
Updated as the build progresses; feeds the final report.

## From the assignment PDF

| # | Requirement | Where / plan | Status |
|---|---|---|---|
| 1 | Data product for the theme (users, needs, impact) | AccessHK: step-free journey planner; users = wheelchair users, elderly, strollers, carers | ✅ defined |
| 2 | data.gov.hk as **main** data source | MTR Routes/Fares/Barrier-Free Facilities (network + per-exit facilities + fares) + rt.data.gov.hk live bus API | ✅ primary |
| 2b | Supplementary data allowed | Wikipedia station coords (official exit-coordinate column is empty — verified 0/3564) | ✅ declared |
| 2c | "Good-to-have" datasets proposal (report §data) | real-time lift outages, tactile floor plans, geo-coded population (report §9) | ✅ report |
| 3 | Working prototype, usable features | routing core + FastAPI + installable PWA demo shell + live bus ETA + fares (`app/`), 18 tests green | ✅ v1.3 running |
| 4 | Multiple data-mining/ML methods, not 1–2 | (a) rule-based classification ✅ (b) hand-written Dijkstra + A* ✅ (c) hand-written k-means + silhouette + elbow ✅ (d) coverage/gap analytics + A*-vs-Dijkstra benchmark ✅ (e) real-time stream integration ✅ | ✅ 4+ done |
| 5 | NOT primarily techniques from other ORBS subjects (ARIMA etc.) | none used; graph mining + classification + clustering are the subject's own toolkit | ✅ |
| 6 | All code in Python | 100% Python backend; PWA shell is a thin demo layer only | ✅ |
| 7 | Core functions meaningfully implement algorithms (no one-line sklearn) | Dijkstra/A* from scratch (`routing.py`); k-means++/silhouette/elbow from scratch (`analysis.py`); haversine from scratch (`geo.py`) | ✅ |
| 8 | Original research paper ≥2022, >2022 citations, not a survey (top marks) | PatchTST (Nie et al., ICLR 2023, arXiv:2211.14730): **5,114 citations** verified via Semantic Scholar 2026-10-24; applied analysis in `docs/paper-analysis.md` + report §6 | ✅ |
| 9 | Future steps section (report) | report §9 (PatchTST wait forecasting, lift-outage feed, in-station wayfinding, native app, demand estimation) | ✅ report |
| 10 | AI use declaration (report) | `docs/ai-use.md` finalised | ✅ |

## From the teacher Q&A

| # | Requirement | Status |
|---|---|---|
| Q1 | Python assessed via submitted code; raw Python/NumPy implementations | ✅ design principle from day one |
| Q2 | Full anonymity in video (already satisfied for the pitch) | ✅ remembered in demo-script setup |
| Q3 | Individual scope | ✅ scope sized for one person |

## From the project owner (user requirements)

| # | Requirement | Status |
|---|---|---|
| 1 | PWA **demo only**; production would be a normal app | architecture keeps Python core UI-agnostic ✅ |
| 2 | Mobile-app form factor, installable add-to-home-screen PWA, age-friendly: big text, high contrast, few taps | manifest+SW+PNG icons; standalone display; adb-reverse tip in demo script ✅ |
| 3 | Python-driven (course alignment) | ✅ |
| 4 | GitHub repo Li-Baixi/MATH7005-Project2 | pushed (main branch, tagged commits) ✅ |

## Demo plan (10 min, no slides) — full script in `docs/demo-script.md`

1. Problem in 60s: two route cards, fastest vs step-free, real data.
2. Live route: origin → destination, entrance/lift/exit advice + $2 concession fares.
3. Fallback feature: no step-free route → nearest accessible station.
4. Live feeder-bus ETA + labelled offline fallback.
5. Analytics view: k-means tiers, weakest stations, A* benchmark.
6. Code walkthrough: `routing.py` (Dijkstra/A*), `analysis.py` (k-means++), `datasets.py` (ID reconciliation).
7. Q&A defence: every constant documented; limitations honest.

## Key verified numbers (for report/demo consistency)

- 97 stations, 10 lines; 93/97 step-free end-to-end per official data
  (4 flagged: Fortress Hill, Tsing Yi, Airport, Po Lam).
- k-means: knee k=5, silhouette peak k=2 (0.834); one k=5 cluster =
  exactly the 4 flagged stations.
- A* saves 21.6% expanded nodes vs Dijkstra on 30 random pairs; costs
  equal on all pairs.
- AEL weakest line: 3/5 step-free (60%).
- Fares: elderly/PWD $2 Octopus concession (rail + feeder bus).
