# WS225 Candidate Admission Bar (procedure; machine companion: CANDIDATE_ADMISSION_BAR.json + ADMISSION_STAGE_CONTRACT.json)

Pre-qualification admission for Rules-engine candidates. Decides whether a new
engine deserves expensive full qualification. This is **not Provider Selection**
and grants no incumbency privilege to XMage or Forge.

## The funnel (cheap terminal blockers first)

| Stage | Name | Pass requires | Evidence grade |
|-------|------|---------------|----------------|
| S0 | Source/license/build identity | exact commit/tree/license(SPDX)+build-or-adapter identity | SOURCE_DERIVED / DIRECTLY_VERIFIED |
| S1 | Architecture / Rules authority / legal-action / hidden-info feasibility | sole-authority design + surface inventory + fail-closed design + principal-scoped observations | CODE_DERIVED min |
| S2 | Cardinality + Commander/multiplayer viability | 2P–5P constructible + Commander/multiplayer viable | CODE_DERIVED min |
| S3 | Frozen-card + micro-rules denominator screen | **29/29 SUPPORTED with dedicated tests inventoried** + 17/17 micro implemented, zero blocked areas | DIRECTLY_VERIFIED census |
| S4 | RNG/replay feasibility | attribution design + **bounded clean-process replay runtime proof** (≥1 tape + independent replay) | runtime proof required |
| S5 | Full common-fixture admission | 135/135 RUNTIME_VERIFIED campaign at pin | RUNTIME_VERIFIED |

First FAIL in S0→S5 order is terminal for the current pin
(`DO_NOT_PROMOTE_CURRENT_PIN`). Later stages still evaluate diagnostically to
map the full gap set. UNKNOWN (evidence never collected, e.g. census absent)
is equally terminal, with `blocker_kind: MISSING_EVIDENCE` prescribing
inventory work instead of upstream implementation.

## Why S3 is strict (29/29)

The frozen 29 is ~2% of the known universe and already triggers-heavy and
layers-thin (F-CARD-01). Spending weeks of qualification on an engine that
cannot demonstrate the full 29 with inventoried behavior tests is the exact
waste this bar exists to prevent. Census-grade evidence (a `card()`/frontier
probe plus test mapping, WS219 shape) costs hours; satisfying it costs
upstream months — the asymmetry is the point. Construction, import, parsing,
or readback earn **zero** behavior credit at S3.

## Provider neutrality (hard rule)

No stage may require XMage Java APIs, Forge controller class names, specific
UUID formats, one engine's RNG method, or one engine's callback taxonomy.
Semantic capabilities only; each provider supplies a mapping layer
(checklist H01–H12). Historical effort already spent is not evidence: XMage
reaches S5-pending (S0–S4 PASS, S5 FAIL — the campaign is not run), and Forge
is terminal at S1 (proven whole-boundary violation) — the same bar bites
incumbents (see INCUMBENCY_BIAS_TEST.json).

## Outputs per assessment

Candidate, source lock, per-stage statuses, terminal stage, blocker,
evidence pointers, next required evidence, and a coarse burden band
(HOURS/DAYS/WEEKS/MONTHS-upstream/UNKNOWN — point estimates forbidden).
Machine shape: `ADMISSION_ASSESSMENTS.json`; WS219 dry run:
`WS219_ADMISSION_DRY_RUN.json` (both current pins
`DO_NOT_PROMOTE_CURRENT_PIN` for the sealed WS219 reasons).
