# AI Use Declaration (draft — finalise before submission)

As required by the assignment, this project declares all AI assistance.

## Tool

Claude Code (Anthropic) — agentic coding assistant, used under the
student's direction throughout the project.

## What AI did

| Area | AI contribution | Student contribution |
|---|---|---|
| Data exploration | Suggested joins between the three MTR id spaces; flagged the empty coordinate column | Verified mappings with scripts; made canonical-id decision |
| Code | Drafted module skeletons (datasets/graph/routing), docstrings, tests | Reviewed, corrected, and extended all code; owns every line for demo defence |
| Documentation | Drafted README/checklist structure | Requirements interpretation, scope, product decisions |

## What AI did not do

- Product idea, scope, user requirements (owner's own, from Task 1 pitch).
- Any submission decision or recorded material.

## Verification workflow

Every AI-drafted module was run against the real data pipeline
(`scripts/build_network.py`), covered by `tests/test_routing.py`
(including Dijkstra vs A* optimality cross-checks), and read line by
line by the student before being kept.
