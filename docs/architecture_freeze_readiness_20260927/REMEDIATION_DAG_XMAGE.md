# Remediation DAG — XMage (CONDITIONAL, NOT selected)

"If the Coordinator later selects XMage (`b19596980f2734496ea1896504253e1bdd2756dd`),
the minimum remaining path to Freeze is: …" — derived only from current
evidence. This packet is symmetric in structure with REMEDIATION_DAG_FORGE.md
and contains no recommendation.

## Entry state (from XMAGE_FREEZE_READINESS.json)

PASS: AF00, AF02, AF03, AF10. Non-PASS: AF01 UNKNOWN, AF04 FAIL, AF05 UNKNOWN,
AF06 UNKNOWN, AF07 UNKNOWN, AF08 UNKNOWN, AF09 UNKNOWN, AF11 FAIL. Missing
required capabilities: `legal_actions_supported`, `action_submission_supported`,
`replay_supported` (compat lane also `seed_supported`; several flags lane-dependent).

## DAG (dependencies first; parallel only where marked independent)

- [ ] X1. Designate ONE production lane (recommendation-neutral: the lane that
  will serve production games) and freeze its capability report. Depends on:
  SLOT-06 ruling. Unblocks: X2, X3.
- [ ] X2. Bridge repair: consistent truthful capability flags on the
  production lane (`seed_supported=true` with engine-owned binding; correct
  `legal_actions/action_submission` flags for the `external_control=true`
  surface). Depends on: X1. Unblocks: X3. Evidence preserved: AF02, AF03.
- [ ] X3. Rerun 20 AF01 v2 invariants on the production lane → AF01 PASS
  (closes PB-04; resolves SLOT-07 by construction). Depends on: X2.
- [ ] X4. Adapter repair: (a) `external_control=true` required at
  `create_commander_game` + fail-closed test when omitted (PB-01); (b)
  decision-identity normalizer (`decision_id`+`action_id`) with provenance
  tests (PB-02, SLOT-03 ruling). Depends on: SLOT-03 ruling. Independent of
  X1–X3 (parallel allowed). Unblocks: X5, X9.
- [ ] X5. Rerun AF04 decision-boundary probes on the production lane → AF04
  PASS. Depends on: X3, X4.
- [ ] X6. Starting-state injection seam for the XMage bridge, OR the SLOT-02
  mechanism-equivalence ruling with per-row mapping. Depends on: SLOT-02
  ruling. Unblocks: X7. (Largest schedule item if the seam path is chosen.)
- [ ] X7. Execute the 33 AF06 BLOCKED rows + 18 AF08 rows (overlap: 18 of the
  33 are the AF08 set; union is 33 rows) → AF06/AF08 PASS. Depends on: X6.
- [ ] X8. Hidden-information scenario campaign: 19 AF05 rows incl. honeycard
  sentinel (SLOT-04 scope) → AF05 PASS. Depends on: SLOT-04 ruling.
  Independent of X6–X7 (parallel allowed).
- [ ] X9. 29-card actual-card corpus campaign (SLOT-08 timing) → AF07 PASS.
  Independent of X6–X8 (parallel allowed).
- [ ] X10. Per-fixture clean-process replay twins: REPLAY_CLEAN_PROCESS,
  REPLAY_DECISION_TAPE, REPLAY_EVENT_TAPE, REPLAY_STATE_HASHES, RNG_RULES_TAPE
  (SLOT-09 timing) → AF09 PASS. Depends on: production lane fixed (X1);
  parallel with X7–X9 allowed.
- [ ] X11. Single-provider topology record (MIT license posture, process
  boundary, request conventions) + AF11 re-verification → AF11 PASS
  (SLOT-03 ruling applied). Depends on: X4, X5.
- [ ] X12. Full requalification seal: 12 PASS + 11 required capabilities
  present + schema-validated `freeze_eligible=true` + AF10 re-established
  (denominator-complete rerun accounting). Depends on: X3, X5, X7–X11.

## Requalification impact set (reruns)

AF01 (X3), AF04 (X5), AF06 33 rows + AF08 18 rows (X7), AF05 19 rows (X8),
AF07 corpus (X9), AF09 twins (X10), AF11 (X11), AF10 accounting on the rerun.

## Historical evidence that survives (no rerun)

AF00 (pin unchanged), AF02 lifecycles, AF03 authority probes, START-2 v1.0.6,
native suites as provenance, divergence packet as historical observation —
per SELECTED_PROVIDER_IMPACT_TEMPLATE §2, unless the remediation touches
their paths.

## What MUST NOT rerun

Already-PASS FULL107 rows outside the X7 set; the WSR22 comparison packet;
Rules-authority capture.

## Falsifiers (from the impact template §5)

Any row FAIL; any new crash/timeout/protocol-failure; new divergence on
unchanged obligations; shim provenance failure; honeycard failure;
harness-side RNG; invalid `freeze_eligible=true` validating.
