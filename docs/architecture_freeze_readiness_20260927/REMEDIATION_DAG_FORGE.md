# Remediation DAG — Forge (CONDITIONAL, NOT selected)

"If the Coordinator later selects Forge (`ef958ee91ac6c9ce0152189f2654bf6e05abf273`),
the minimum remaining path to Freeze is: …" — derived only from current
evidence. This packet is symmetric in structure with REMEDIATION_DAG_XMAGE.md
and contains no recommendation.

## Entry state (from FORGE_FREEZE_READINESS.json)

PASS: AF00 (with PB-05 provenance note), AF01, AF02, AF03, AF10. Non-PASS:
AF04 UNKNOWN, AF05 UNKNOWN, AF06 UNKNOWN, AF07 UNKNOWN, AF08 UNKNOWN, AF09
UNKNOWN, AF11 FAIL. Missing required capabilities: `legal_actions_supported`,
`action_submission_supported`, `event_log_supported`, `replay_supported`
(all false on the protocol2-jsonl lane while live decisions demonstrably work).

## DAG (dependencies first; parallel only where marked independent)

- [ ] F1. Resolve PB-05 per SLOT-05 ruling: accept env-supplied binding, or
  bridge repair (build-derived commit/tree emission), or container provenance
  file. Depends on: SLOT-05 ruling. Unblocks: F8 (AF00 record final).
- [ ] F2. Bridge correction: truthful capability flags on the production
  lane (`legal_actions/action_submission/event_log/replay` corrected with no
  behavior change) per SLOT-06 ruling. Depends on: SLOT-06 ruling. Unblocks: F3.
- [ ] F3. Rerun 20 AF01 v2 invariants on the production lane → AF01 PASS
  reconfirmed on corrected flags. Depends on: F2.
- [ ] F4. Adapter repair: decision-identity normalizer (`revision`+`actor_id`)
  with provenance tests (PB-02, SLOT-03 ruling). Depends on: SLOT-03 ruling.
  Independent of F1–F3 (parallel allowed). Unblocks: F5, F9.
- [ ] F5. Rerun AF04 decision-boundary probes across all reachable decision
  classes (STARTING_PLAYER, MULLIGAN, PRIORITY, + targets/modes/choices where
  offered) with fail-closed tests for unsupported classes → AF04 PASS.
  Depends on: F3, F4.
- [ ] F6. Probe Forge's reported `starting_state_injection_supported=true` /
  `scenario_injection_supported=true`: build the Lab-side execution path and
  attempt the 7 AF06 BLOCKED rows + 2 AF08 rows directly. Depends on: nothing
  (parallel allowed). Unblocks: F7.
- [ ] F7. If F6 succeeds: execute MICRO_COPY, MICRO_COSTS, MICRO_MODES,
  MICRO_REPLACEMENT, MICRO_ZONE_CHANGES, WS05-MP-BLOCK-4, WS05-MP-COMBAT-4 →
  AF06/AF08 PASS. If F6 fails: bounded injection workstream, else the SLOT-02
  mechanism-equivalence ruling with per-row mapping. Depends on: F6 + SLOT-02
  ruling (fallback only).
- [ ] F8. Hidden-information scenario campaign with fresh classification of
  HIDDEN_05/06/08/11/12: 8 AF05 rows (SLOT-04 scope) → AF05 PASS. Depends on:
  SLOT-04 ruling. Independent of F6–F7 (parallel allowed).
- [ ] F9. 29-card actual-card corpus campaign (SLOT-08 timing) → AF07 PASS.
  Independent of F6–F8 (parallel allowed).
- [ ] F10. Per-fixture clean-process replay twin: REPLAY_CLEAN_PROCESS
  (SLOT-09 timing; decision/event/state-hash tapes already have same-seed
  twins) → AF09 PASS. Depends on: production lane fixed; parallel with
  F7–F9 allowed.
- [ ] F11. Single-provider topology record (GPL-3.0 license posture with
  interop consequences, process boundary, request conventions) + AF11
  re-verification → AF11 PASS (SLOT-03 ruling applied). Depends on: F4, F5.
- [ ] F12. Full requalification seal: 12 PASS + 11 required capabilities
  present + schema-validated `freeze_eligible=true` + AF10 re-established.
  Depends on: F1, F3, F5, F7–F11.

## Requalification impact set (reruns)

AF01 reconfirmation (F3), AF04 all-classes (F5), AF06 7 rows + AF08 2 rows
(F7), AF05 8 rows (F8), AF07 corpus (F9), AF09 twin (F10), AF11 (F11), AF10
accounting on the rerun.

## Historical evidence that survives (no rerun)

AF00 (subject to F1 form), AF02 lifecycles, AF03 authority probes, START-2
v1.0.6, 79 PASS FULL107 rows outside the F7 set, native suites as provenance,
divergence packet as historical observation — per
SELECTED_PROVIDER_IMPACT_TEMPLATE §2, unless the remediation touches their paths.

## What MUST NOT rerun

Already-PASS FULL107 rows outside the F7 set; the WSR22 comparison packet;
Rules-authority capture.

## Falsifiers (from the impact template §5)

Any row FAIL; any new crash/timeout/protocol-failure; new divergence on
unchanged obligations; shim provenance failure; honeycard failure;
harness-side RNG; invalid `freeze_eligible=true` validating.
