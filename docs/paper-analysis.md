# Applied Research Paper: PatchTST

## Paper (requirement: original, ≥2022, >2022 citations, not a survey)

> Nie, Y., Nguyen, N. H., Sinthong, P., & Kalagnanam, J. (2023).
> **"A Time Series is Worth 64 Words: Long-term Forecasting with
> Transformers."** *International Conference on Learning
> Representations (ICLR 2023).* arXiv:2211.14730 (first posted
> November 2022).

Verified 2026-10-24 via the Semantic Scholar API:
**citationCount = 5,114** (requirement: > 2022), publication year 2022,
venue ICLR, publication type journal article — an original methods
paper, not a survey.

## What the paper proposes

Two design ideas on top of a vanilla Transformer encoder for
long-horizon multivariate time-series forecasting:

1. **Channel independence (CI).** Each univariate series (one "channel")
   is modelled independently, sharing the same network weights. CI
   consistently outperforms explicit cross-channel attention on
   standard benchmarks.
2. **Patching.** The input series is sliced into subseries-level
   patches (length 16 by default — the "64 words" of the title), which
   simultaneously lengthen the effective look-back horizon and reduce
   attention's quadratic cost.

## Why this paper is the right one for AccessHK

Our router's weakest estimate is a constant:
`BOARDING_WAIT_MIN = 2.5` minutes per ride
([routing.py](../accesshk/routing.py)). The principled upgrade is a
per-route forecast of expected wait / crowding from historical
automatic-vehicle-location (AVL) data — and PatchTST's two ideas map
directly onto that problem:

| PatchTST idea | MTR feeder-bus reality | Fit |
|---|---|---|
| Channel independence | ~26 feeder routes, each with few months of history | One shared backbone over per-route channels works when per-channel data is thin — exactly our situation |
| Patching | Headway "bunching" (two buses arriving together) is a pattern over 10–15 min windows | Patch tokens align with the timescale of the phenomenon |
| Long-horizon ability | A journey planned now needs waits 0–60 min ahead | Medium-horizon forecasting is the paper's core strength |

## What we concretely applied in this project

1. **Ingestion layer built.** [realtime.py](../accesshk/realtime.py)
   already POSTs the live `rt.data.gov.hk` schedule API and mirrors
   every successful response, timestamped, into a snapshot cache — the
   exact corpus a PatchTST-style model would train on. Collecting it
   for a term gives (route × stop × minute) channels for free.
2. **Channel-independent data design.** Bus ETA payloads are keyed per
   route and summarised per stop id, so each (route, stop) pair is a
   natural channel — the schema follows the CI decomposition instead
   of fighting it.
3. **Scoped design, not a bolt-on.** The report's future-work section
   specifies the upgrade path (replace the wait constant with
   PatchTST-derived per-route expected headway), including the honest
   limitation: data.gov.hk publishes no historical AVL archive, so the
   corpus must be self-collected via our cache.

## Why we did not implement the forecaster itself

Individual 10-week course project: the routing, accessibility logic,
clustering and live feeds already span the assessed data-mining
toolkit. Training a Transformer on a corpus that does not yet exist
(caching started this week) would be theatre, not engineering — we
prefer an honest constant today and a specified, evidence-based
upgrade path.

## Reproducing the citation check

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/arXiv:2211.14730?fields=title,year,citationCount,venue,publicationTypes"
```
