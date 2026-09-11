# WS-49 CHECKPOINT 11 — G49-08 REMEDIATION AND NORMALIZER (CI PENDING)

Status: **REMEDIATED / LOCALLY VALIDATED / CI RUN PENDING**

No credit claimed. Construction 107/107 PASS (checkpoint 10) stands on
unmodified construction code paths; the bridge remediation below changes
native installed state and therefore requires a fresh exact-head
construction + normalization cycle before any promotion.

## Root causes (both first found by the new G49-08 normalizer, fail-closed)

RC-A — PROVIDER_ADAPTER_DEFECT, sickness restoration gap (CODE_DERIVED):
`CardUtil.putCardOntoBattlefieldWithEffects` (used by `GameImpl.cheat`,
the setup path) unconditionally calls `removeSummoningSickness`, erasing the
per-object controlled-since-turn-began state the immutable scenario models.
Native `getAvailableAttackers` (full Rules legality via `canAttack`) then
correctly-but-on-wrong-state reports sick creatures eligible. Observed:
WS05-MP-COMBAT-4 requested `eligible_attackers=[mp-attacker-0, mp-attacker-1]`
(P1-bears sick, csts absent) while native reported P1-bears eligible.
The Rules Core query is CORRECT; the installed state was wrong. Never
misclassified as an XMage Rules defect.

RC-B — PROVIDER_ADAPTER_DEFECT, blocker declaration-authority scoping
(CODE_DERIVED): `PermanentImpl.canBlock` answers capability, not CR 509.1a
declaration authority, so the readback aggregation across all non-attacking
players listed creatures defending nothing. Observed: WS05-MP-BLOCK-4 native
`eligible_blockers` included P4-bears (P4 defends no attacker). Real play is
unaffected (declaration UI scopes defenders first); only the direct-readback
consumer was exposed.

Contract reading (both evidenced): requested `eligible_attackers` is exact
(active-player scoped natively); requested `eligible_blockers` models the
temporal priority player's declaration options (v1.0.4→v1.0.5 audit precedent:
P2-bears added, P3/P4 excluded). P1-bears' exclusion alongside P1's listed
options proves sickness (only remaining attacker restriction).

## Bounded systemic remediation (bridge-confined, no mage change)

`apply_ws49_native_remediation.py` (+2 patch functions, anchor-safe,
idempotent, full chain re-verified from pristine):

1. Sick-preserving battlefield placement: battlefield cards bypass cheat's
   battlefield path into a step-for-step mirror of
   `putCardOntoBattlefieldWithEffects` minus the single unconditional
   sickness lift (public APIs only). ETB default installs sick; sickness is
   lifted only where the scenario models it (the pre-existing post-hoc WS39
   lift stays as an idempotent net). Sound because the session uses the jump
   model (`init` → cheat → temporal jump → resume): no turn ever begins, so
   `beginningOfTurn` never re-marks installed sickness.
2. Defender-scoped blocker eligibility: a blocker counts only against
   attackers its own controller defends (native group/defender data;
   player/planeswalker/battle handled). No requested data enters.

Not used: request-derived legality filtering (forbidden), synthetic control
history (forbidden), reflection, engine mutation.

## G49-08 normalizer (new, independent observer)

`normalize_construction_v105.py`: offline `--contract/--probe/--output`
gate reusing only WS42 *normalizer* modules (never construction code).
State-load rows: field-by-field derivation with requested-digest equality
(base 9 keys + combat/extra-turn/elimination/zone-move + knowledge grants +
face-down exile + counters zero-convention + csts fidelity pin).
Natural rows: 12-check battery federating preflight deck readback, decision
transcript, observation query, and replay checkpoints (no requested-digest
claim; explicit marker). Fail-closed throughout; 8/8 negative mutation
probes fail with precise codes.

## Local validation (exact locks, DIRECTLY_VERIFIED)

- Bridge `mvn verify`: 62/62 PASS (remediated build).
- Fresh full local construction (remediated bridge): 107/107 admitted, 0
  unsupported. Native state confirms the fix (P1-bears sick, mp-attackers
  lifted; BLOCK-4 blockers defender-scoped, P4-bears gone).
- Fresh offline normalization over that readback: 107/107
  PASS_INDEPENDENT_NORMALIZATION (100 digest-equal + 7 opening-verified).
- 8/8 negative probes fail-closed (tampered hands/echo/denominator/
  sentinel/eligibility/sickness/tapes/history-flag).
- `ruff check` clean on both Python files; normalizer `ruff format` clean
  (apply script keeps its pre-existing file style; HEAD was already
  format-dirty there).
- CI workflow extended with the G49-08 normalization step + lock/digest
  assertions (same artifact dir, sealed).

## Next action

Push this package; register the fresh exact-head construction+G49-08 run
PENDING with run/job/artifact IDs; adjudicate 107/107 independently;
persist terminal PASS/FAIL before G49-09.

COVERAGE_PROMOTION=FALSE. TASK_COMPLETE=NO. WS49=INCOMPLETE.
