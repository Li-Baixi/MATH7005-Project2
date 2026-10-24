# AI Use Declaration

As required by the assignment, this project declares all AI assistance.

## Tool

Claude Code (Anthropic) — agentic coding assistant, used under the
student's direction throughout the project.

## What AI did

| Area | AI contribution | Student contribution |
|---|---|---|
| Data exploration | Suggested joins between the three MTR id spaces; flagged the empty coordinate column | Verified mappings with scripts; made canonical-id decision |
| API research | Probed parameter/method variants for the rt.data.gov.hk bus API until the POST form was found | Chose the honest-documentation strategy (fix documented in `realtime.py` docstring) |
| Code | Drafted module skeletons (datasets/graph/routing/analysis/fares/realtime), docstrings, tests | Reviewed, corrected, and extended all code; owns every line for demo defence |
| Documentation | Drafted README/report/checklist structure and prose | Requirements interpretation, scope, product decisions; verified every factual claim against the data |

## What AI did not do

- Product idea, scope, user requirements (owner's own, from Task 1 pitch).
- Any submission decision or recorded material.
- Any unaudited algorithm: every assessed method (Dijkstra, A*, k-means++,
  silhouette, elbow, haversine) was specified to be hand-written from
  primitives and is covered by tests that check it against ground truth.

## Verification workflow

Every AI-drafted module was run against the real data pipeline
(`scripts/build_network.py`, `scripts/run_analysis.py`), covered by the
pytest suite (18 tests: routing optimality cross-checks, clustering
ground truth, fare lookups, offline-fallback behaviour), and read line
by line by the student before being kept.
