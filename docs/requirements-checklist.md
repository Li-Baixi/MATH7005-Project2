# Assignment Requirements → Implementation Map (living document)

Tracking every hard requirement from `MATH7005_project_2026.pdf`,
the teacher's Q&A answers, and the project owner's own constraints.
Updated as the build progresses; feeds the final report.

## From the assignment PDF

| # | Requirement | Where / plan | Status |
|---|---|---|---|
| 1 | Data product for the theme (users, needs, impact) | AccessHK: step-free journey planner; users = wheelchair users, elderly, strollers, carers | ✅ defined |
| 2 | data.gov.hk as **main** data source | MTR Routes/Fares/Barrier-Free Facilities (network + per-exit facilities + fares) | ✅ primary |
| 2b | Supplementary data allowed | OpenStreetMap station coords (official exit-coordinate column is empty — verified 0/3564) | ✅ declared |
| 2c | "Good-to-have" datasets proposal (report §data) | TODO: real-time lift outages, tactile floor plans, geo-coded population by district | ⬜ report |
| 3 | Working prototype, usable features | routing core done; API + age-friendly PWA demo shell next | 🔨 in progress |
| 4 | Multiple data-mining/ML methods, not 1–2 | (a) rule-based classification (step-free verdicts) (b) graph shortest-path: hand-written Dijkstra + A* (c) facility-vector clustering (NumPy k-means, planned) (d) accessibility coverage analytics (planned) | 🔨 2/4 done |
| 5 | NOT primarily techniques from other ORBS subjects (ARIMA etc.) | none used; graph mining + classification are the subject's own toolkit | ✅ |
| 6 | All code in Python | 100% Python backend; PWA shell is a thin demo layer only | ✅ |
| 7 | Core functions meaningfully implement algorithms (no one-line sklearn) | Dijkstra/A* written from scratch (`accesshk/routing.py`); k-means will be hand-written NumPy | ✅/planned |
| 8 | Original research paper ≥2022, >2022 citations, not a survey (top marks) | candidates shortlist pending; must verify citation count | ⬜ |
| 9 | Future steps section (report) | native app, real-time lift outage feeds, demand estimation | ⬜ report |
| 10 | AI use declaration (report) | `docs/ai-use.md` started; update continuously | 🔨 |

## From the teacher Q&A

| # | Requirement | Status |
|---|---|---|
| Q1 | Python assessed via submitted code; raw Python/NumPy implementations | ✅ design principle from day one |
| Q2 | Full anonymity in video (already satisfied for the pitch) | ✅ n/a for code, remember for demo |
| Q3 | Individual scope | ✅ scope sized for one person |

## From the project owner (user requirements)

| # | Requirement | Status |
|---|---|---|
| 1 | PWA **demo only**; production would be a normal app | architecture keeps Python core UI-agnostic ✅ |
| 2 | Mobile-app form factor, age-friendly: big text, high contrast, few taps | UI spec for demo shell | 🔨 next |
| 3 | Python-driven (course alignment) | ✅ |
| 4 | GitHub repo Li-Baixi/MATH7005-Project2 | git initialised; push pending credentials | 🔨 |

## Demo plan (10 min, no slides)

1. Problem in 60s: two route cards, fastest vs step-free, real data.
2. Live route: origin → destination, entrance/lift/exit advice.
3. Fallback feature: no step-free route → nearest accessible station.
4. Analytics view: station accessibility profile/clustering.
5. Code walkthrough: `routing.py` (Dijkstra/A*), `datasets.py` (ID reconciliation).
6. Q&A defence: every constant documented; limitations honest.
