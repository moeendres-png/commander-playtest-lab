# Successor Specification — Dedicated XMage WS90 First-Wave Qualification (Planning Only)

Status: execution-ready specification. Planning only; do not execute inside
WS204. Consumes WS204 read-only plus sealed corrected WS90 authority.

## Inputs (read-only)

- WS204 head plus `qualification/ws204-xmage-b4d-action-submission/`
  (decision-scoped generic transport, 17-class unit proof, 5-class
  actual-card transport proof, census artifacts, core-boundary file).
- Sealed corrected WS90 authority:
  `qualification/ws90-rqc3-corrected-first-wave-reissue/` (15-slot corrected
  denominator, H01 A/B/C as one slot, H01 binding, execution packs).
- Pinned engine cfc36f445f917f101fa2ed588770e043f53bc44c; RogShai and WS90
  scenario decks as named by WS90 packs.

## Objective

Qualify First-Wave behavior (not reachability) for the 15-slot corrected
denominator using actual cards on the dedicated full-game lane with WS204
transport. Separate reachability from behavior correctness in every slot.

## Method

- For each of the 15 slots, drive the exact WS90 execution-pack scenario
  through `legalActionsPayload`/`submitAction` only (no native custom verbs
  in the qualification path, no requested-result filtering).
- Pilot policy: the sealed WS204 `ExternalPilotDecisionPolicy` semantics
  (or its explicitly versioned successor); record
  `decision_policy_version` per run. Reachability selections from the WS204
  census driver must not be reused as behavior evidence.
- Determinism: explicit seed per scenario; one isolated JVM per game;
  record `seed_scope=single_isolated_jvm_process`.
- Same-seed twin evidence where relevant: rerun each completed game with the
  identical external decision stream in a fresh JVM; compare semantic
  projections (`semantic_transcript` normalization: drop private state and
  engine object ids, normalize process-local prompt ids), not raw
  per-process UUIDs. Record `semantic_replay_match` and keep
  `bit_exact_replay_validated=false` unless byte-level evidence supports it.
- Do not use the old 20-kind census as behavior proof (reachability only).

## Scoring

- Run the exact 15-slot corrected denominator; treat H01 A/B/C as one slot.
- Zero credit for BLOCKED/UNKNOWN. `concede` and `combat damage assignment`
  slots (if any) remain BLOCKED by the WS204 core-boundary file until an
  engine-side remediation lands and is itself qualified.
- Preserve D1–D5 gates as regressions; D5 twin equality stays UNKNOWN until
  the twin gate above proves it per scenario.
- `GLOBAL_BEHAVIOR_CREDIT_CHANGE` accumulates only behavior PASS slots;
  reachability alone credits nothing. `FULL107` stays `NOT_RUN` unless the
  contract explicitly authorizes it.

## Outputs

- Per-slot records: scenario, seed, deck handles, decision stream
  (decision_id/offset/class/actor, offered counts/types, submitted option,
  native advancement, pre/post semantic state or event evidence), negative
  controls (stale/wrong/unknown/replay per slot where applicable),
  semantic transcript hashes, twin-gate hashes, verdict
  (PASS/BLOCKED/UNKNOWN/FAIL) with evidence classification.
- Aggregate: 15-slot matrix, behavior credit delta, blockers with exact
  callback/call-chain reproducer for any new core boundary, and the exact
  next action for any unblocking workstream.

## Gates

- No Production Provider selection. No Architecture Freeze claim.
- No WS204/WS203/WS92 mutation. No engine repin. No test or denominator
  weakening. No raw git push (canonical safe_push dry-run first).
