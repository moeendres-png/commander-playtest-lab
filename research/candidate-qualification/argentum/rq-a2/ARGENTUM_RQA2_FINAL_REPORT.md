# RQ-A2 — Argentum Comparable Architecture Qualification: Final Report

Terminal disposition: **`ARGENTUM_REMEDIATION_REQUIRED_BEFORE_RUNTIME`**

(Do not perform the repair in RQ-A2. This is not provider selection, not a freeze.)

## 1. Source Lock

- CPL: branch `research/argentum-comparable-qualification-rq-a2-20260910`, start
  `a62a8c7` / tree `89bb39f`; terminal HEAD/TREE in `ARGENTUM_RQA2_SOURCE_LOCK.md`.
- Argentum: `wingedsheep/argentum-engine` HEAD `3f46367d87c88bcf156a843a9e69fd29e1693872`,
  TREE `2adf51caa8f9c6a9908ea961fa988ebb5eb1959f`, tracked tree clean at every milestone.
  Candidate source semantically READ-ONLY throughout (gitignored build products only).

## 2. Work Completed (campaign order)

1. **U19 replay round-trip** (first): 3 engine-level games (G1 pass-only+cleanup discards,
   80 actions; G2 Study discards with 7 SubmitDecisions, 183; G3 coin-flip game-over with
   9 flips, 261) replay EXACT per-frame via fresh fold AND via the candidate's actual
   `ReplayReconstructor` from codec-round-tripped `CompactReplay` with checkpoints
   (fidelity EXACT, streams complete). 7 tamper controls (altered input/actor/seed/order,
   omission, seat-id collision) ALL detected fail-closed; N1b shows semantic-divergence
   propagation (valid altered choice → divergence at frame 11 → downstream rejection at 52).
2. **U22 identity**: 4 same-game fresh-JVM pairs (S1/S2/S3/S4, 527 frames) canonical-EXACT;
   routing/entity/RNG stable; pinned+unpinned persisted replays EXACT; raw differs ONLY at
   runtime-minted tokens (storm `AbilityId.generate`, activation `EntityId.generate`
   resolutionKeys) — localized, normalized, behavior-neutral.
3. **U16 hidden-info adversary**: 4P Commander pod, per-principal `Visibility` authority vs
   Gym obs (0/0), server DTO (1 finding), spectator (clean), decisions (clean), errors
   (clean); revealAll control fires (384); in-process full-state caveat demonstrated.
4. **U10 5-player**: FFA rotation/priority, Commander pod, elimination ladder with winner +
   leaver-skipping rotation, 6P smoke — all green; no engine cap (product caps
   rules-correct or dev-surface).
5. **U5 linkage**: mechanical inventory (13,402 declared / 11,144 canonical / 2,227 generated
   / 4,532 behavior-linked / 7,621 UNKNOWN; 10 named multiplayer + 1 named commander).
6. **U1 rules-dense**: 13/13 scripted runtime probes green (priority/stack, costs, counter,
   persist, layers arithmetic, copy, control+EOT revert, SBA, APNAP, lethal, multi-defender,
   search-as-select, commander cast/choice/tax/damage).
7. **U2/U3 packets**: behavior recorded (theft reverts; Watcher silent off 5-object mass
   removal; 2HG fan-out fires once, 30→29); questions open for Sol High.
8. **Seams**: U12 config-only (3-seat runtime); U15 trigger ordering AUTOMATIC (RQ-A1 row 17
   corrected); freshness F1–F5 fail-closed; commander shortcut unreachable (NO); RNG closure
   holds (split claims).
9. **Adjudication**: canonical `foundry-adjudicator` XHIGH reviewed all nonlocal conclusions;
   all required downgrades applied (see §13).

## 3. New Findings

- **D1 (ARGENTUM_ENGINE_DEFECT, high)**: every draw leaks — `ClientEventTransformer`
  `ZoneChangeEvent→HAND/LIBRARY` emits `PermanentLeft(cardName, "Opponent's X went to hand")`
  to all viewers alongside the properly masked `CardDrawn`. Production-reachable via
  per-viewer broadcast (`GameSession.kt:1011`). Minimal repair: mask by `Visibility` in that
  branch. Requalification: U16 event/draw probes + event-projection tests.
- **DTO/gym divergence (pending authority)**: server DTO shows controllers their face-down
  exiled cards' true names; Gym masks all viewers. `AUTHORITY_GATE-4` (CR 708.5).
- **N-B**: `EntityId.generate()` DOES have a live use (activation `resolutionKey`;
  identity-only, replay-safe) — corrects RQ-A1.
- **N-C**: RQ-A1 decision-matrix row 17 corrected (trigger ordering AUTOMATIC).
- **N-D**: declare steps skipped with no attackers (BEGIN_COMBAT→END_COMBAT) — gated (G6).
- **N-A**: seat-id namespace collision fails closed (control, not defect).
- **N-F**: test-definition shadowing (Lightning Bolt) — linkage caveat.

## 4. U19 Replay Round-Trip

- `ENGINE_DETERMINISM`: DIRECTLY_VERIFIED (same-process exact re-folds; complements:
  `ReproducibilityTest` 5/5).
- `CONTROLLED_RULES_RNG`: DIRECTLY_VERIFIED on tested paths (recorded seed == config;
  seed+1 rejected at frame 0; G3 flips identical); exhaustive no-bypass CODE_DERIVED.
- `REEXECUTION`: DIRECTLY_VERIFIED (fresh fold + `ReplayReconstructor`, fidelity EXACT;
  complement: `CompactReplayReconstructionTest` 2/2).
- `SEMANTIC_REPLAY`: TECHNICALLY_CONFORMANT (bounded: 3 games/decks/seeds + 7 controls +
  codec + checkpoints + cross-process pairs; UNKNOWN elsewhere — cross-version and
  adversarial-deck coverage open). Never a general guarantee.

## 5. U22 Ability-ID Identity Impact

Semantic identity holds cross-process (527 frames); transport identity isolated and
normalizable in a non-Rules journal layer on tested (yield-free) paths. Recorded
`ActivateAbility(ability_33)` replays EXACT pinned+unpinned (legal-option identity stable
for the real corpus). Holes: yields/batches over synthetic identities UNKNOWN; fixture
UUIDs fail closed (bounded); unpinned fidelity UNVERIFIED by construction. Full analysis:
`ARGENTUM_ABILITY_ID_REPLAY_IMPACT.md`.

## 6. U16 Hidden Information

Managed path clean; spectator clean; errors/decisions clean; controls fire; caveat
demonstrated (integration must pin `GameGymEnv.observe()`/managed observations — an
in-process pilot reading `StepResult.state` bypasses protection structurally; if the safe
topology needs a process/API boundary, this is the place). D1 blocks hidden-info
qualification until remediated; D2 awaits authority.

## 7. U10 Five-Player Feasibility

Feasibility green at engine level (2–6 seats runtime-evidenced now); product caps are
rules-correct or dev-surface. Conformance in the qualification sense remains open (U11).

## 8. U5 Real-Card Behavior Linkage (exact definitions in §2 of the linkage report)

13,402 declared / 11,144 canonical / 2,227 generated / 4,532 behavior-linked (~34%, strong +
heuristic) / 7,621 UNKNOWN (~57%) / 10 named multiplayer + 1 named commander. Counts are
inventory, never coverage. Sampling does not prove global coverage.

## 9. Targeted Rules-Maturity Evidence

13/13 DIRECTLY_VERIFIED behavior probes with exact setups/decision sequences/results in
`ARGENTUM_RULES_DENSE_PROBES.json`. Zero mechanisms `EXTERNALLY_RULE_VALIDATED` (that
promotion is Coordinator-controlled). Notable: P11 commander chain (cast → 903.9a YES →
divert → taxed recast with 3 tapped → damage tracked 2); P13 search-as-`SelectCardsDecision`
(min 0 = fail-to-find legal); P9 APNAP order with 23/23 resolution and no ordering question.

## 10. MTG Rules Authority Gates

Six open gates in `ARGENTUM_RULES_AUTHORITY_GATES.md`: 800.4a/d (U2), 800.4c (U2b, no
fixture), 805.4d fan-out (U3, fires-once recorded), 708.5 controller exile vision (G4),
603.3b auto-ordering (G5), declare-step skip (G6). Unresolved official-Rules questions are
listed there verbatim; Muse resolves none.

## 11. Decision Seam / Freshness

F1 valid succeeds; F2 stale-id, F3 fabricated-id, F4 wrong-actor, F5 old-id-on-new-decision
all FAIL-CLOSED with exact messages ("expected r1, got r0"). U12 starting-player is
configuration-only input. U15 trigger ordering is AUTOMATIC (may/modal/target choices stay
authoritative PendingDecisions).

## 12. Commander Shortcut Audit

`FORCED_COMMANDER_SHORTCUT_PRODUCTION_REACHABLE = NO` (flag test-only; production chain
presets→false; gym/AI zero references). Integration constraint: keep it off production paths.

## 13. RNG Use-Site Closure

Tested-path reproduction DIRECTLY_VERIFIED; exhaustive closure CODE_DERIVED (16 consumer
files via `nextRandom`; pre-game/auth/AI/test randomness correctly separated; zero bypass
in rules paths). Seed authority recorded; starting-player randomness = seeded shuffle.

## 14. Changes

- CPL: 9 commits on the research branch, all under `rq-a2/` (harness Kotlin drivers,
  python inventory, 13 evidence JSONs, 8 reports, state). No other surface touched.
- Candidate: zero tracked changes (verified clean at every milestone).

## 15. Tests / Evidence (exact)

- Harness runs: rqA2Replay (3 games EXACT/EXACT), rqA2ReplayNeg (N0 EXACT, N1a–N5 detected),
  u22 matrix (6 records + 8 replays, 527 canonical-EXACT), rqA2HiddenInfo (5 true findings),
  rqA2FivePlayer (F1–F4 green), card_linkage.py (counts), rqA2RulesDense (13/13),
  rqA2Authority (U2/U3 fixtures), rqA2Freshness (F1–F5 fail-closed, U12 3/3, U15 auto).
- Existing candidate suites (read-only): multiplayer/Commander-adjacent (RQ-A1 254/254),
  ObservationVisibilityTest 6/6, GameMaskingTest 3/3, CombatDamageMaskingEnricherTest 1/1,
  CompactReplayReconstructionTest 2/2, ReproducibilityTest 5/5.
- Evidence classes: per-contract seven; runtime facts DIRECTLY_VERIFIED; static facts
  CODE_DERIVED; bounded contracts TECHNICALLY_CONFORMANT; zero EXTERNALLY_RULE_VALIDATED
  self-promotions; gaps UNKNOWN.

## 16. PASS / FAIL / UNKNOWN (major gates)

- Source lock: PASS. Replay round-trip (bounded): PASS. Negative controls: PASS.
- Cross-process identity (bounded): PASS. 5P feasibility: PASS. Linkage inventory: PASS.
- Rules-dense probes: PASS (behavior, not validation). Freshness/seams: PASS.
- Shortcut audit: PASS (NO). RNG closure: PASS (split claims).
- Hidden-info no-leak: FAIL (D1 defect; managed path itself PASS).
- Full-rules qualification: UNKNOWN (out of scope). 5P conformance: UNKNOWN. Coverage: UNKNOWN.
- Cross-version replay: UNKNOWN. 6 Rules gates: UNKNOWN (open).

## 17. Candidate Disposition

**`ARGENTUM_REMEDIATION_REQUIRED_BEFORE_RUNTIME`**

A bounded, remediable masking defect (D1 draw leak) materially blocks fair runtime
comparison on hidden-information paths; the DTO/gym divergence (D2) needs authority
resolution. Architecture (determinism, replay, identity, RNG, seams) is the strongest
evidenced part of the campaign and is NOT the blocker. Do not perform the repair in RQ-A2;
requalify U16 event/draw probes + event-projection tests afterward. (Adjudicated XHIGH;
alternatives rejected: WARRANTED forbidden by D1+coverage+gates; RETAIN understates the
gate; DEMOTE disproportionate; BLOCKED_UNKNOWN inapplicable — evidence decides.)

## 18. Architecture Ranking Impact

**No ranking effect.** Standing within the comparable cohort is strengthened on
determinism/replay/identity, but runtime candidacy is blocked pending remediation.
Forge remains provisional leader; XMage remains strongest established challenger pending
WS52. `genuine challenger` / `runner-up` claims rejected as unsupported.

## 19. Remaining Blockers

1. D1 remediation + requalification (engine repair workstream, not RQ-A2).
2. Six authority gates (Sol High).
3. Coverage depth (57% UNKNOWN names; 10+1 named multi/commander links).
4. Cross-version replay + adversarial-deck closure (discriminator phase).

## 20. Outputs

`ARGENTUM_RQA2_SOURCE_LOCK.md`, `ARGENTUM_REPLAY_ROUNDTRIP.json`,
`ARGENTUM_REPLAY_NEGATIVE_CONTROLS.json`, `ARGENTUM_ABILITY_ID_REPLAY_IMPACT.md`,
`ARGENTUM_HIDDEN_INFO_ADVERSARY.json`, `ARGENTUM_FIVE_PLAYER_PROBE.json`,
`ARGENTUM_CARD_BEHAVIOR_LINKAGE.json/.md`, `ARGENTUM_RULES_DENSE_PROBES.json`,
`ARGENTUM_RULES_AUTHORITY_GATES.md`, `ARGENTUM_RNG_USE_SITE_CLOSURE.md`,
`ARGENTUM_DECISION_FRESHNESS.json`, `ARGENTUM_COMMANDER_SHORTCUT_AUDIT.md`,
`ARGENTUM_UNKNOWN_LEDGER_UPDATED.md`, `ARGENTUM_RQA2_FINAL_REPORT.md` (this file),
`ARGENTUM_AUTHORITY_PROBES.json`, `WORKSTREAM_STATE.yaml`, harness + scripts + `u22/` digests.

## 21. Dependencies Unblocked

- An Argentum **bounded actual-card/runtime comparison is NOT yet justified** (blocked on D1
  remediation + D2 gate). Do not start it.
- Unblocked now: D1 repair workstream (exact file/lines/probe), Sol High adjudication of six
  gates (packets complete), U20 cross-version design, WS51-style restore comparison inputs
  (snapshot/replay primitives characterized).

## 22. Exact Next Action

Coordinator: charter the D1 remediation repair + U16 requalification, adjudicate the six
authority gates, then decide on the bounded runtime/behavior discriminator. No RQ-A2
follow-up work remains.

`CSN_FULL107_CREDIT_CHANGE = 0`

`FULL107 = NOT_RUN`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
