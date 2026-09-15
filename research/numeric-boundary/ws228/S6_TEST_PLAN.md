# S6 Test Plan (executable successor plan)

S6 base: fb156d2b4cf8c5c21d0c84e844a53160032c0992
(tree 52359f47eea7ddc1e4ec8187e89b67fa67d63616).
Entry gate first: re-run RETENTION_PREDICATES.json machine checks; on
NO_IMPACT across all predicates, proceed (see WS226_DELTA_REVALIDATION.json
for the WS223→WS226 precedent).

## Files likely to change (exact)

1. src/commander_lab/engine/rules/full_game.py
   - ExternalPilotDecisionPolicy.decide numeric-only branch (~383-384)
   - target_amount companion call (~405-406)
   - _decide_numeric body (~736-774) → descriptor build + choose_number(s)
     + membership validation (no fallback arms)
2. src/commander_lab/agents/pilots.py
   - BasePilot.choose_number / choose_numbers (default: raise)
   - concrete deterministic + stochastic strategy implementations
3. src/commander_lab/semantic_replay/tape.py (if vector field added:
   numeric_choices) + recorder.py (descriptor digest binding) +
   consumer.py (legs/totals equality) — recorder/consumer strengthening
   only; no semantic change; follow WS218 tape-versioning procedure
4. engine-bridge/src/main/.../XmageFullGamePlayer.java multi_amount path
   (936-977) ONLY if joint-frame transport needs bridge work (U4 spike
   decides; scalar paths need NO bridge change — projection already
   accepts the full interval)
5. F-RULES-03 dispositions in the same files (5 branches per WS220 S6
   surface): single-offer logging, mulligan-cap forced-move log, priority
   mana-withhold disposition, pool-shortcut disposition, London-bottom
   structured-context routing

## Existing tests to extend (do not weaken)

- tests/unit/test_xmage_full_game_decision_matrix.py: add span>16
  descriptor/offered-set cases per numeric class (P-B1 shape); keep all
  existing small-domain rows green
- engine-bridge XmageFullGameActionProjectionTest: add joint-vector
  rejection rows (N-16) + schema-confusion row (N-22)
- engine-bridge XmageFullGamePlayerBoundaryTest: add live numeric
  companion variants (N-07/N-08 live)

## New test classes/files

- tests/unit/test_numeric_domain_descriptor.py (Lab path: descriptor
  exactness, boundary 16/17 retired-behavior regression, malformed/
  out-of-domain fail-closed incl N-23 anti-fallback proof, P-N1 O(1)
  budget at span 10^9)
- tests/unit/test_multi_amount_joint.py (joint predicate: legs, totals,
  length, malformed elements)
- JVM live suites per POSITIVE_MATRIX (P-A1/P-A2/P-M1/P-T1) + per-class
  live negatives per NEGATIVE_MATRIX (N-01..N-23 instantiations)

## Runs

- Java/JVM: targeted bridge suites above (offline mvn -o, same lane WS228
  used: XmageFullGamePlayerBoundaryTest 4/4, ProjectionTest 17/17)
- Python: full unit file runs for touched areas + descriptor suites
- Fresh-process runs: each JVM suite in a fresh process (no shared-engine
  state); Python numeric suites also fresh-process (subprocess invocation)
  to catch import-time coupling
- Positive observations: P-A1/P-A2/P-M1/P-T1 live incl span>16, with tape
  steps asserting (min,max[,legs,totals],choice) + invariant green
- Negative submissions: N-01..N-23 forged-submission cases, exact error
  families asserted as CONTAINS
- Process isolation: JVM full-game scenarios run scenario-per-process
  (engine static state); unit suites may share a process per file

## Required evidence files (S6 seals)

- offered-descriptor captures per positive case
- projection/consumer acceptance logs
- tape excerpts with invariant checks
- (min,max) distribution log for U1 (every numeric step records bounds)
- WS218 dual-replay positives re-run for numeric-bearing scenarios

## Expected runtime cost

- Python unit: seconds. JVM unit suites: minutes (offline). Live
  full-game numeric scenarios: bounded — one scenario per positive case
  (4) + cheapest-reach harness per negative family; NO 135-fixture
  campaign (S6 is not a requalification workstream; S8 owns N-scoped
  reruns per the action graph).

## Explicit non-goals (S6 must not)

- Card-name hacks in implementation; weakening any existing assertion;
  materializing legal sets; touching replay semantics beyond the typed
  vector field; claiming behavior credit beyond observed rows.
