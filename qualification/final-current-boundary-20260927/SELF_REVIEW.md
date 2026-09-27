# WSR22 Adversarial Self-Review — FINAL-CURRENT-BOUNDARY-FREEZE-QUALIFICATION-20260927

Each item states the attack, the search performed, and the verdict.

## 1. Vacuous tests

**Attack:** AF01 fail-closed negatives proved nothing if they only ever ran
outside a live game.
**Search:** inspected each AF01 negative invariant and its evidence payload.
Every illegal-action / stale-decision / unsupported-class probe returned a
provider-side typed error. These run against a live bridge but **outside** a
constructed game.
**Verdict:** PARTIALLY MITIGATED, and disclosed. The negatives are real provider
responses, not vacuous no-ops, but they are pre-game probes. The in-game
negative that matters was separately discovered and recorded: XMage rejects a
Forge-shaped `revision` submission with `STALE_EXTERNAL_DECISION`, which is a
genuine in-game fail-closed path. No AF01 invariant is marked PASS on the basis
of an empty response alone; `_fails_closed` requires an explicit non-success
typed verdict.

## 2. Construction-only behaviour claims

**Attack:** deck import + `create_commander_game` could be mistaken for
runtime behaviour.
**Search:** every PASS row requires an external decision to have been reached
and answered with an engine-offered option, or an engine-validated native
execution. Import alone never yields PASS.
**Verdict:** NO VIOLATION. Recorded explicitly in the actual-card packet that
the engine itself validated the deck (it rejected an illegal colour identity).

## 3. Inherited historical PASS

**Attack:** the native harness classes load the **v1.0.5** materialization, so
promoting their green results to the v1.0.6 boundary could be silent transfer.
**Search:** mechanically compared all 107 records between the frozen v1.0.5
materialization and the effective v1.0.6 bundle across 14 obligation-relevant
fields.
**Verdict:** MECHANICALLY RESOLVED. 106/106 rows byte-identical; only
`WS05-CMD-START-2` differs. `SUCCESSOR_INHERITANCE_PROOF.json` records the
comparison. `WS05-CMD-START-2` never draws native credit; it was executed fresh
under v1.0.6 semantics via the Protocol-2 driver. No WSR20/WSR21 verdict was
carried into any current-boundary count.

## 4. Player-count inference

**Attack:** a 2P result might be silently used to imply 3P/4P/5P.
**Search:** each of 2P/3P/4P/5P ran its own independent lifecycle with its own
deck imports, Commander game creation, start, and external priority decision.
**Verdict:** NO VIOLATION. Six separate lifecycles per candidate. `PLAYER_COUNT_*`
rows are derived from the frozen seat roster, not from a shared run.

## 5. START-2 predecessor semantics reused

**Attack:** the disabled historical `XmageFullGameStart2ExecutionTest` asserts
the unsatisfiable `beginning/draw` checkpoint and could have been revived.
**Search:** the new START-2 run is entirely Protocol-2, reads the effective
v1.0.6 record, and asserts the **absence** of any draw-step checkpoint, draw
event, or in-step priority.
**Verdict:** NO VIOLATION. The historical disabled test was not re-enabled and
contributes nothing. Effective digest asserted as
`bc01a714…` in the reconciliation test.

## 6. Stale Rules authority

**Attack:** the repository recorded `FRESHNESS_CONFLICT_FAIL_CLOSED` and a
2026-08-07 citation; a worker could have accepted either without re-checking.
**Search:** direct capture of the official page HTML, direct capture of the TXT
it links, byte hash, effective date, and a rule-level diff against the
repository's own historically-hashed 2026-08-19 artifact (which re-captured to
exactly the recorded sha256, validating the capture pipeline).
**Verdict:** RESOLVED, not assumed. The official page now links
`MagicCompRules 20260925.txt`; the previously recorded 2026-08-07 URL returns
404. The successor contract's cited date is superseded but its semantics are
confirmed byte-identical for every qualification-relevant rule.

## 7. Hidden fallback

**Attack:** the driver might pick an arbitrary option when the intended one is
absent, manufacturing a PASS.
**Search:** inspected every decision branch in `game_driver`. Priority passes
only an engine-offered `pass_priority`; a structural choice must match the
fixture-scripted seat or raise `DecisionUnsatisfied`; a decision class with no
matching policy stops the run and records
`NO_MATCHING_OFFERED_OPTION` rather than substituting.
**Verdict:** NO VIOLATION. Three separate driver defects were found and repaired
before any PASS was claimed (envelope, decision identity, lane selection) —
each would otherwise have produced a false result.

## 8. Fabricated legal options / adapter legality reconstruction

**Attack:** the runner might infer legality to reach an obligation.
**Search:** the runner only reads `get_legal_actions` /
`get_capabilities` payloads and transports selections. XMage's own fail-closed
`LEGAL_ACTIONS_UNAVAILABLE` when `external_control` is omitted is preserved and
not worked around by any other route.
**Verdict:** NO VIOLATION.

## 9. Rules RNG outside the engine

**Attack:** harness-side seeding or outcome injection.
**Search:** no outcome is written into engine state anywhere in the runner. The
requested seed is recorded; XMage's compat lane truthfully reports
`seed_supported=false` and AF01 records that invariant as **UNKNOWN** for that
lane rather than claiming a binding.
**Verdict:** NO VIOLATION, and the asymmetry is disclosed rather than smoothed.

## 10. Replay without a runtime twin

**Attack:** claiming replay PASS from a single-process export.
**Search:** the replay packet states explicitly that the clean-process twin half
is not proven per fixture; the affected rows stay UNKNOWN/BLOCKED.
**Verdict:** NO VIOLATION.

## 11. Protocol/capability claims inferred rather than observed

**Attack:** reading `legal_actions_supported=false` from the manifest and
concluding XMage has no decision surface.
**Search:** the manifest and the live payload were compared. The live compat
lane with `external_control=true` **does** expose a complete external PRIORITY
decision, contradicting the manifest's global false flag.
**Verdict:** MATERIAL FINDING, not smoothed. Recorded as PB-01: the manifest's
global capability flags understate the live capability, and capability
reporting is lane-dependent (compat `seed_supported=false`, full-game `true`).
AF01 is reported per lane rather than merged.

## 12. Engine-local IDs mistaken for Rules differences

**Attack:** `game_id`, `decision_id`, UUID actor ids and `revision` counters
differ between candidates and could be reported as divergence.
**Search:** the comparison packet explicitly lists those fields as excluded
from comparison; all 107 rows were reviewed for such conflation.
**Verdict:** NO VIOLATION. The decision-identity divergence is classified as an
**interface shape** difference (PB-02), not a Magic Rules difference.

## 13. Failures collapsed to UNKNOWN or PASS

**Attack:** four `PLAYER_COUNT_*` rows first reported FAIL from a classifier
bug; the tempting fix is to downgrade to UNKNOWN.
**Search:** root-caused to a missing scalar `player_count` in the effective
records, fixed the classifier, and re-ran. The underlying lifecycles had
already succeeded.
**Verdict:** NO COLLAPSE. The failure was repaired at its actual layer, not
downgraded. No expected value was weakened anywhere in this workstream.

## 14. Unclassified denominator items

**Attack:** rows silently omitted.
**Search:** the runner asserts exactly 107 documents per candidate and the
reconciliation test asserts 107 unique fixture ids and a complete outcome
vocabulary. Zero CRASH / TIMEOUT / PROTOCOL_FAILURE.
**Verdict:** NO UNCLASSIFIED ROWS.

## 15. Provider ranking

**Attack:** the large PASS asymmetry (Forge 79 vs XMage 30) invites the
conclusion that Forge is the better provider.
**Search:** the asymmetry is analysed at its true cause. Forge's advantage comes
from WSR20 having already built 150 native denominator tests, while the Lab
XMage harness covers 30 rows. It is an **evidence-build asymmetry**, not a
measured Rules-capability difference. Both candidates passed every row that
either one executed. Classified in `PROVIDER_BLOCKERS` as PB-03 with
`UNKNOWN_IMPACT` and a concrete remediation, not as a capability claim.
**Verdict:** NO RANKING. No score, no winner, no preferred provider. The
mechanical test scans the analytical packets for ranking language.

## 16. Provider-blocking classification honesty

**Attack:** calling a gap non-blocking because it is inconvenient.
**Search:** each of the 8 register entries carries a technical reason. Four are
`BOUNDED_NON_BLOCKING` only because a conforming adapter was demonstrated in
this workstream. The 33 XMage blocked rows, the 5 historical Forge hidden
seams, the 29-card corpus, and the per-fixture replay twins are all
`UNKNOWN_IMPACT`, explicitly **not** dismissed.
**Verdict:** HONEST. No `PROVIDER_BLOCKING` claim is made from this workstream;
that judgement is the Coordinator's.

## 17. Scope discipline

**Attack:** the temptation to fix the engine seams that were discovered.
**Search:** no engine file was modified. The Forge reference worktree remained
byte-clean at `18bba95a…` after three build/test runs. Every discovered gap is
recorded with a smallest-remediation scope instead of being fixed.
**Verdict:** NO VIOLATION.
