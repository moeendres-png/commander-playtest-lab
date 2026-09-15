# WS220 Audit Strategy

## Prioritization

`risk_to_correctness × probability × blast_radius × uncertainty_reduction ÷
investigation_cost`, applied with engineering judgment, never mechanically.
Correctness risks outrank efficiency always; efficiency matters only where it
compounds into correctness risk (e.g. re-running valid evidence trains
operators to ignore red, or token/time cost blocks needed qualification).

## Phase plan

1. **Orientation** (done): surveys + verification probes → orientation,
   backlog, strategy, source lock → checkpoint commit.
2. **Batch 1 — integrity of what we claim** (evidence model, source truth,
   qualification architecture, FULL107/denominators). Mostly static probes
   over machine-readable artifacts + doc/code cross-checks. Cheap, high value.
3. **Batch 2 — integrity of what we run** (Rules-authority boundary,
   hidden info, RNG/replay requirement, test strategy, CI reproducibility).
   Targeted code probes + smallest authoritative test runs only.
4. **Batch 3 — integrity of how we work** (Foundry/OpenCode, workstream
   sizing, parallelism, efficiency, hygiene, roadmap order). History-as-data:
   workstream graph analysis, state-file/token metrics, duplication measures.
5. **Exploratory phase** (explicitly non-checklist): metric analysis (what do
   current numbers optimize?), unstated assumptions, failure modes no gate
   tests, opportunities recent work unlocked that the roadmap missed.
6. **Falsification pass**: for each P0/P1 candidate — search for mitigation,
   superseding evidence, design rationale, existing coverage, lock confusion,
   artifact confusion. Record rejections in `REJECTED_HYPOTHESES.md`.
7. **Synthesis**: findings with severity/confidence, successor contracts,
   autonomy opportunities, dependency-aware action graph, validation seal,
   final handoff. Publish via `safe_push.py` (dry-run first).

## Rules of engagement

- Read-only outside `research/project-audit/ws220/**`. No production or
  qualification-authority mutation; no pin changes; no WS218/WS219 surfaces.
- Probes live under `research/project-audit/ws220/probes/`; keep them small,
  deterministic, stdlib-first; retain outputs only for reproducibility value.
- Impact-first test runs: state the uncertainty to remove before running;
  prefer the smallest test that answers it; never run FULL107 or Maven XMage
  builds without a written decision-value justification.
- Every material finding gets: id, title, classification, severity,
  confidence, evidence class, source/evidence, why-it-matters, affected
  objective, current vs desired behavior, minimal repair surface,
  dependencies, requalification burden, execution tier. Severity is not
  inflated: P0 = correctness/evidence integrity compromised now; P1 = blocks
  Freeze path; P2 = substantial reliability/productivity gain; P3 = optional.
- Reprioritization is recorded in the backlog (`status` + `resolution`).
  Dead ends are closed, not nursed.
- Missing evidence stays UNKNOWN. `UNKNOWN != PASS` applies to the audit too.
