# L3 — RG-03 Authoritative Temporal Progression Driver

## Terminal Handoff

**Disposition:** COMPLETE / PASS

**Branch:** `sol/rg03-temporal-driver-20260924`

**Exact predecessor L2:** `9dd94806377fa7fce17f7243048f747fe3ae1606`

**Runtime-qualified L3 head:** `1efab77b4bda64e957391400b38eb2035acfa9ff`

**Mage pin:** `b19596980f2734496ea1896504253e1bdd2756dd`

**Draft PR:** #244, stacked on `sol/rg02-commander-damage-wrapper-20260924`

**WORKTREE:** NOT_AVAILABLE_IN_CONNECTOR_EXECUTION

**ARCHITECTURE_FREEZE:** NOT CLAIMED

**PRODUCTION_PROVIDER:** NOT SELECTED

## Objective / Work Completed

Implemented a reusable, fail-closed temporal progression layer that reaches supported checkpoints through the running XMage engine rather than writing clock fields.

- `XmageNativeStateRestoration` now parses and validates only the explicitly qualified turn-1 temporal checkpoint set needed by residual fixtures.
- Added `XmageTemporalProgressionDriver`.
- The driver observes authoritative native turn/phase/step/active/priority state.
- Every discretionary transition is supplied by an explicit external `DecisionSource` and submitted through the existing authoritative decision-scoped legal-action boundary.
- No first-option, random, default yes/no, internal AI, GUI default, silent skip or direct clock mutation exists.
- Missing scripts, stale/revision-divergent decisions, unsupported targets, overshoot, terminal-before-target and bounded-execution exhaustion fail closed.
- Added reusable predicate-based `driveUntil` support for exact live native checkpoints/decision states.
- Qualified advanced temporal behavior including skip-combat, extra turn creation/ordering and simultaneous beginning-trigger ordering.

## Reuse Classification

`WRAP / EXTRACT_AND_GENERALIZE`.

The existing full-game session and action projection already owned real engine progression. L3 generalized the repeated ad-hoc test loops into one fail-closed temporal driver; no second Rules Core was introduced.

## Changed Files vs L2

Exact compare `9dd94806377fa7fce17f7243048f747fe3ae1606..1efab77b4bda64e957391400b38eb2035acfa9ff`:

- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageNativeStateRestoration.java`
- `engine-bridge/src/main/java/org/commanderlab/xmage/XmageTemporalProgressionDriver.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageNativeStateRestorationTest.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageTemporalProgressionDriverTest.java`
- `engine-bridge/src/test/java/org/commanderlab/xmage/XmageTemporalAdvancedProgressionTest.java`

The lineage is 10 commits ahead / 0 behind L2 with merge-base exactly the L2 predecessor.

## Initial Failure / Remediation

The first L3 bridge run exposed two test-scope defects, not a Rules failure:

1. a retained negative v1 regression still asserted that every combat checkpoint must be rejected;
2. the parser-only temporal test used `PILOT_TRIGGER_ORDER`, whose unrelated cumulative-upkeep counter dimension is intentionally unsupported by restoration.

Remediation:
- changed the negative check to an actually unqualified turn-2 checkpoint;
- limited parser-only fixtures to records that isolate temporal parsing;
- added dedicated live trigger-order qualification with real `Phyrexian Arena` + `Mystic Remora` simultaneous upkeep triggers.

No engine clock/state shortcut was added.

## Exact Runtime Evidence

All five branch workflows on exact head `1efab77b4bda64e957391400b38eb2035acfa9ff` completed SUCCESS:

- CI `36206461508`
- External XMage Integration `36206461503`
- XMage Full Game Conformance `36206461510`
- XMage Real 4P Technical Smoke `36206461504`
- H4 Docker Materialization `36206461536`

External bridge job `108303945980`:
- `XmageTemporalProgressionDriverTest`: 7 tests, 0 failures/errors
- `XmageTemporalAdvancedProgressionTest`: 6 tests, 0 failures/errors
- `XmageNativeStateRestorationTest`: 20 tests, 0 failures/errors
- complete bridge suite: 246 tests, 0 failures, 0 errors, 1 intentional skip
- Maven BUILD SUCCESS

## Qualified Semantic Cases

PASS:
- turn-1 upkeep reachability
- turn-1 draw reachability
- precombat main
- declare attackers
- declare blockers
- combat damage
- postcombat main
- postcombat progression at 2P/3P/4P/5P
- explicit real attack/no-block progression
- skip-combat behavior through a real rules effect
- real extra-turn creation and ordering
- simultaneous beginning-trigger ordering via native `trigger_order` decision
- fail-closed unscripted decisions
- fail-closed unqualified/later temporal targets

The historical START-2 frozen assertion combining a draw-step priority checkpoint with `first_turn_draw:false` remains a separate fixture/engine contract issue. L3 does not falsely convert that unrelated frozen assertion into PASS.

## Evidence Classification

- branch ancestry/source lock: DIRECTLY_VERIFIED
- exact CI/runtime tests: DIRECTLY_VERIFIED
- temporal driver semantics: TECHNICALLY_CONFORMANT
- no direct clock-field mutation: CODE_DERIVED + runtime progression tests
- extra-turn / trigger-order live behavior: DIRECTLY_VERIFIED
- START-2 full frozen fixture: UNKNOWN / separately blocked, not promoted

## PASS / FAIL / UNKNOWN

**PASS:** `RG03_AUTHORITATIVE_TEMPORAL_DRIVER = PASS`

**FAIL:** none in bounded L3 scope.

**UNKNOWN:** only frozen semantics outside the qualified temporal-driver scope, including the previously documented START-2 first-turn-draw contradiction.

## Remaining Blockers

None for L4 start.

## Dependencies Unblocked

L4 may start from the exact terminal head produced by this handoff commit.

## Exact Next Action

Create/resume `sol/rg01-causal-stack-reconstruction-20260924` from the exact L3 terminal head. Reconstruct stack checkpoints only through genuine engine actions (cast/activate, targets, modes, X/numeric choices, costs/mana, trigger placement/order), never by inserting a finished stack object or fabricating historical events.

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
