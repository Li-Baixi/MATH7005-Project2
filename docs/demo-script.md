# AccessHK Demo Script (10 minutes, no slides)

**Primary demo (zero setup):** the hosted PWA at
https://li-baixi.github.io/MATH7005-Project2/ — open on the phone,
*Add to Home Screen*, and everything below runs from the home-screen
icon. The laptop server is only the fallback if the venue has no
internet at all.

**Fallback setup (15 min checklist, only if offline demo is needed):**

1. Laptop: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
   (verify `curl localhost:8000/api/meta`, and run
   `python -I scripts/build_network.py ...` +
   `python -I scripts/run_analysis.py ...` if `data/processed` is empty).
2. Phone (Android demo device), USB connected, USB debugging on:
   `adb reverse tcp:8000 tcp:8000` → phone browser opens
   `http://localhost:8000`. This makes the phone a *secure context*, so
   Chrome offers **安裝應用程式 / Install app** — do it live or
   pre-install; the icon opens AccessHK full-screen like a native app.
3. Warm the bus-ETA cache once over any network
   (`curl "localhost:8000/api/bus-eta?route=K12"`) so even total
   Wi-Fi failure still shows a *labelled* cached card.
4. Fallback if adb is unavailable: phone and laptop on the same
   hotspot, browse `http://<laptop-ip>:8000` (app still works; only the
   install prompt is unavailable).

**Anonymity (teacher Q2):** no name/voice/face reveal — the laptop
user session shows the project only; close personal apps before
sharing screen.

---

## Timeline

### 0:00–1:00 — Problem, in one sentence
Hold up the phone: *"For most of us the fastest route wins. For a
wheelchair user, one flight of stairs deletes the route. AccessHK
plans journeys that are guaranteed step-free — using the government's
own per-exit data."* Show the app icon on the home screen (the PWA
install moment — "added from the browser, no app store").

### 1:00–3:30 — The headline query (live, on the phone)
- The app opens prefilled 起點 中環 Central → 終點 炮台山 Fortress Hill
  (the pitch deck's story) — one tap on 規劃.
- Read the cards: fastest is a **14-min direct train**, but the
  step-free card says **impossible** — Fortress Hill is not step-free
  in the official data. The app then answers the real question:
  **nearest step-free station 天后 Tin Hau · 0.6 km**, and at Central
  board via the **Exit A lift**.
- Point at the fare line: 成人 $5.9 · **長者 $2 · 傷殘 $2** (concession
  fares are distance-tiered in the official table; this pair is $2).

### 3:30–4:30 — The second query (when both routes work)
- Switch to 深水埗 Sham Shui Po → 金鐘 Admiralty: fastest = step-free
  (17.8 min, direct), plus the **per-exit entrance advice** — B1 lift /
  A1 stair lift at Sham Shui Po, E lift / A&D stair lift at Admiralty —
  data the incumbents don't show. 成人 $13.2 · 長者 $2.6.
- One sentence on honesty: the official data marks 4 stations not
  step-free — we show what the data says and flag it, never silently patch.

### 4:30–6:00 — Live feeder-bus ETA
- Tap the 巴士 card, route K12: next arrivals per stop, **live from
  rt.data.gov.hk** — on the hosted PWA the phone browser calls the
  government API directly (CORS is open; zero backend).
- Kill Wi-Fi (airplane mode), reopen the app: it still opens and
  answers previously-viewed queries — offline-cached by the service
  worker; the bus card honestly reports no data. *"Stale data must
  introduce itself as stale."*

### 6:00–7:30 — The analytics view
- Scroll to 數據洞察: 97 stations clustered by hand-written k-means
  into tiers; the weakest-stations list is the advocacy slide.
- Headline finding: the k=2 silhouette peak (0.83) = the step-free
  divide; one k=5 cluster *is exactly* the 4 flagged stations.

### 7:30–9:00 — Code defence (laptop, 90 seconds of scrolling)
- `routing.py`: Dijkstra & A* from scratch, heaps visible, the
  admissible heuristic explained in one sentence; the test asserting
  both return equal costs on all pairs.
- `analysis.py`: k-means++ / elbow / silhouette, all hand-written.
- `datasets.py`: the dual-id reconciliation (`DUAL_ID_MAP`) — 30
  seconds on why three id spaces made "simple joins" a research
  problem.

### 9:00–10:00 — Close
- The stack in one line: data.gov.hk primary + one declared
  supplementary source; all Python; four data-mining methods; an
  ICLR-2023 paper applied to the roadmap (PatchTST).
- *"The nearest station without stairs — computed, not guessed."*

---

## Q&A defence (likely questions → 10-second answers)

- **Why not Google Maps data?** Assignment requires data.gov.hk
  primary; incumbents also don't expose per-exit lift data in HK.
- **Are travel times official?** No official dataset exists — modelled
  haversine ÷ line speed + dwell, constants documented in `graph.py`.
- **Why is Airport marked not step-free?** The official monthly file
  says so (no paid-area lift row); we keep fidelity and flag it —
  it's finding #1 in the report.
- **Is the PWA the product?** No — demo shell; production is a native
  app over the same Python API (scoping decision, stated in README).
- **Where is AI in this?** Declared in `docs/ai-use.md`: assistive
  scaffolding/debugging under human direction; every assessed
  algorithm is hand-written and tested.
