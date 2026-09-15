# WS17 Aggregate Adjudication (narrative; machine companion: WS17_AGGREGATE_ADJUDICATION.json)

**Decision: option B — deprecate as historical; the generated WS225 views are
the living standing.**

WS220 F-EVID-01 proved the WS17 rollup (0 PASS / all NOT_RUN at old locks,
`G01 FAIL`, `G02–G10 NOT_RUN`) contradicts the authoritative WS213/WS215/WS218
seals with no reconciling index. Two constraints force option B:

1. Hand-editing stale rows until they look right is forbidden (it would
   manufacture PASS rows without trace pointers).
2. Deleting WS17 historical evidence is forbidden (reports remain provenance).

So the sealed bytes are untouched, and an additive pointer —
`qualification/aggregate/WS225_ROLLUP_STATUS.json` — makes the living
directory unambiguous: every WS17 aggregate/evidence file listed there is
**HISTORICAL**; every `qualification/reporting/ws225/*_STANDING.json` view
plus `FREEZE_READINESS_VIEW.json` is **living** (generated, recomputable via
`standing_generator.py`).

Option A (regenerate the WS17 files in place) was rejected: rewriting sealed
bytes would destroy evidence and break the same-commit integrity history, and
the WS17 schema cannot express trace pointers, current/stale status, or
cross-branch seals.

Rerun after integration: rerun the generator (cheap), refresh SHA manifests
same-commit, reseal `VALIDATION.json`.
