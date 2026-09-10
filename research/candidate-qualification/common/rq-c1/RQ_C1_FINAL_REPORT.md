# RQ-C1 Final Report — Candidate-Neutral Actual-Card Architecture-Reverser Corpus

Workstream: `RQ-C1-CANDIDATE-NEUTRAL-ACTUAL-CARD-ARCHITECTURE-REVERSER-CORPUS`
Branch: `research/candidate-neutral-architecture-reverser-corpus-rq-c1-20260910`
Writer: `foundry-implementer` (`opencode-go/muse-spark-1.3-contributor`, HIGH;
XHIGH `foundry-adjudicator` for draft-plan redundancy/coverage/constructibility).

No candidate was executed. No provider code was modified. `BEHAVIOR_CREDIT_CHANGE = 0`.

## 1. Corpus summary (no behavior coverage implied)

- 40 actual-card scenario families (files `scenarios/RQ-C1-*.json`), all 4-player primary, adaptable per-scenario notes.
- First-wave: 15 scenarios (list §2).
- Statuses: 35 READY_FOR_COORDINATOR_RULES_ADJUDICATION, 3 READY_FOR_CANDIDATE_EXECUTION (A02, C02, F04: Oracle-direct), 2 AUTHORITY_GATE_REQUIRED (G04, K02: blocked until Sol High answers).
- Rejected: 1 (Boros Charm choose-one; ID RQ-C1-D02 reassigned to added Twincast spell-copy).
- Deferred: random-order RNG (no executable actual-card case); 5 second-wave candidates (Artificial Evolution, Vial Smasher, Frenetic Efreet, Command Tower, Time Warp) + 1 unidentified Q6 intake row.
- Rules adjudication needed: 35 confirmation packets + 2 gates (37 packets in `RQ_C1_RULES_AUTHORITY_QUEUE.md`); 3 no-question Oracle-direct scenarios.
- Unverified Oracle texts (must confirm before ANY candidate execution): Murder (B04, G02), Cultivate (C04), Ornithopter (D06).

## 2. First wave (15) with falsified reversers

A04 replacement ordering (REPLACEMENT/DECISION_SEAM); A03 optional replacement
(REPLACEMENT/COSTS_MANA/DECISION_SEAM); B01 4P APNAP (TRIGGERS/MULTIPLAYER/
DECISION_SEAM); F01 hidden search+shuffle (HIDDEN_INFO/DECISION_SEAM/RULES_RNG/
REPLAY); D06 choose-one-or-more (DECISION_SEAM/RULES_CORRECTNESS); C01 pitch vs
hard-cast (COSTS_MANA/DECISION_SEAM); C03 X+increase+division (COSTS_MANA/
DECISION_SEAM/RULES_CORRECTNESS); E01 multi-defender tax (COMBAT/MULTIPLAYER/
COSTS_MANA/DECISION_SEAM); E02 double-block+trample (COMBAT/RULES_CORRECTNESS/
DECISION_SEAM); H01 copy-vs-Humility (LAYERS/RULES_CORRECTNESS); G02 movement+tax
(COMMANDER/ZONE_IDENTITY/COSTS_MANA); G03 damage loss at 21, gated on
PRE_DECISION ledger seeding (COMMANDER/MULTIPLAYER/RULES_CORRECTNESS); G04
elimination cleanup, AUTHORITY_GATE (MULTIPLAYER/RULES_CORRECTNESS/
ZONE_IDENTITY/NATIVE_IDENTITY); J02 d20+recursion (RULES_RNG/REPLAY/TRIGGERS/
ZONE_IDENTITY); I01 blink identity (ZONE_IDENTITY/NATIVE_IDENTITY/
RULES_CORRECTNESS).

## 3. Axis coverage (required axes A-K)

A replacement/prevention: A01-A04 (incl. pure-prevention baseline A02).
B triggers: B01-B04 (APNAP, delayed, intervening-if, dies+fan-out).
C costs/mana: C01-C04 (alternate, additional, X+increase, commander-conditioned).
D targets/modes/division: D01-D06 (choose-two, spell-copy, stack survival,
copy-trigger, chooser-division, choose-one-or-more).
E combat: E01-E03 (multi-defender tax, ordering+trample, deathtouch).
F hidden info: F01-F04 (search+shuffle, scoped reveal+choice, morph, scry).
G multiplayer/commander: G01-G05 (vote, movement+tax, damage loss, elimination, each-opponent).
H layers: H01-H02 (copy-vs-Humility timestamp-independence; Growth/Frog timestamp-dependence).
I zone identity: I01-I03 (blink, reanimation, token lifecycle).
J randomness: J01-J03 + F01-shuffle (coin, d20+recursion, random discard); random-order DEFERRED.
K SBA: K01-K02 (mass trigger accounting; legend-rule gating).

Reverser-axis depth: DECISION_SEAM 32, RULES_CORRECTNESS 33, ZONE_IDENTITY 11,
COSTS_MANA 11, TRIGGERS 11, MULTIPLAYER 8, NATIVE_IDENTITY 7, COMBAT 5,
HIDDEN_INFO 5, REPLACEMENT 4, RULES_RNG 4, REPLAY 4, COMMANDER 3, LAYERS 2.
Decision criticality: 3 BLOCKING, 29 HIGH, 8 MEDIUM. Information gain: 13
VERY_HIGH, 20 HIGH, 7 MEDIUM. Complexity: 14 LOW, 23 MEDIUM, 3 HIGH.

Known non-coverage (not hidden): starting-player/mulligan (pre-game, no
card vehicle), piles, surveil (scry covers library-top; surveil deferred),
secret choice (no candidate-neutral authoritative case found),London-style
redraw, monarch/initiative/day-night (variant tracks, Q6 curator-review).

## 4. Decision-surface coverage

29 kinds across 40 scenarios (matrix `RQ_C1_DECISION_SURFACE_MATRIX.csv`):
cast 32, pass 40, mana payment 30, targets 24, attackers 6, defender-per-attacker 6,
copy choices 4, mana source 4, blockers 3, X 3, sacrifice 3, alternate cost 2,
may 2, modes 2, combat damage assignment 2, hidden-zone selection 2,
+ 13 singletons (activate, additional cost, concession, Commander movement,
discard, divide/distribute, ordering, replacement ordering, reveal, scry,
search, trigger ordering, voting).

## 5. Hidden-information scenarios

F01 (searcher-only + post-shuffle unknown-to-all), F02 (reveal-to-P0-only +
privacy restoration, P2/P3 adversarial), F03 (face-down 2/2-public/identity-hidden),
F04 (scry-private), J03 (victim-only + retained-private), C01 (pitch-card
private-until-exile), D02/B04/K01/G01/G03 (public-ledger assertions).
Expectations: `RQ_C1_HIDDEN_INFO_EXPECTATIONS.json`.

## 6. Rules-RNG scenarios

F01 shuffle, J01 coin, J02 d20+recursion, J03 random-select-discard.
Journal contract (purpose/domain/fingerprint/result/event/replay):
`RQ_C1_RNG_EXPECTATIONS.json`. All RNG originates in Rules Core with seed
authority at execution; corpus prescribes shapes, never outcomes.

## 7. Multiplayer / Commander scenarios

B01 (4P APNAP), B04/K01 (fan-out/accounting), E01 (multi-defender), G01-G05
(vote, movement+tax, damage loss, elimination, each-opponent). Primary 4P;
2/3/5 adaptations noted per scenario. Per-count conformance remains per-count
at execution (a 4P result proves nothing for other counts).

## 8. Native setup boundaries (WS51 RESTORE_PATH_REJECTED)

35 NATURAL_GAME_START, 4 PRE_STEP_NATIVE_PROGRESSION (E01/E02/E03/J02:
progress natively to declare-attackers, attackers undeclared), 1
PRE_DECISION_CONSTRUCTION (G03: damage ledger seeded pre-first-decision).
Zero scenarios inject stacks, triggers, attackers, or mid-step state.
Map: `RQ_C1_NATIVE_SETUP_BOUNDARIES.json`.

## 9. Q6 consumption

Taxonomy consumed (verb registry, trigger/mode rules, randomness taxonomy with
shuffle split, replacement/copy hypotheses, unsupported exclusions). 55-card
sample: 20 primary + 3 supporting SELECTED as discovery pointers (zero behavior
credit); 20 REJECTED_REDUNDANT; 6 REJECTED_AUTHORITY_UNCLEAR (4 Q6-unsupported
constructs + Teferi's + Aethersnatch); 0 candidate-biased; 0 low-information
(folded into redundant); 6 DEFERRED. 27 corpus cards added independent of Q6.
Full log: `RQ_C1_Q6_CONSUMPTION.json`. Check: 20+3+20+6+6 = 55.

## 10. Rules Authority Queue

37 packets (35 confirm + 2 gates G04/K02) + 3 no-question Oracle-direct entries
+ 3 unverified-text flags (Murder, Cultivate, Ornithopter). No Muse Rules
adjudication made. File: `RQ_C1_RULES_AUTHORITY_QUEUE.md`.

## 11. Negative controls

7 identity + 4 hidden-info (incl. planted-leak calibration) + 3 replay + 1
qualification-calibration control, all SYNTHETIC_NEGATIVE_CONTROL, never
behavior coverage. Referenced per-scenario; enforced pre-credit at execution.
File: `RQ_C1_NEGATIVE_CONTROLS.json`.

## 12. Candidate execution contract

Future Forge/XMage (and Argentum iff RQ-A2 justifies) runs instantiate
`RQ_C1_CANDIDATE_EXECUTION_CONTRACT.md` unchanged-semantics: engine pin, seam,
fixture boundary, verbatim legal options, per-principal observations, bound
selections, native ack, neutral Rules events, hidden-info checks, RNG journal,
post-state fingerprint, evidence class, fail-closed unsupported taxonomy
(ENGINE_/PROVIDER_UNSUPPORTED, HARNESS_/FIXTURE_LIMITATION, UNKNOWN).

## 13. Redundancy adjudication

XHIGH adjudication: 7 challenged pairs all KEEP (distinct Rules
question/surface/boundary); 1 cut (Boros Charm), 1 add (Twincast spell-copy),
2 redesigns (G03 seeding, K02 gating), 2 authoring corrections (Murder,
Ornithopter). Coarse-matrix collisions (D01/D06, B04/K01) explicitly covered
KEEP. File: `RQ_C1_REDUNDANCY_ADJUDICATION.md`.

## 14. Machine validation

`validate_rqc1.py` PASS: 40 scenarios, 40 unique IDs, files match, cards/
authority/boundary/reuse enums valid, no candidate-native IDs in semantic
fields, no READY-with-gate, hidden/RNG/first-wave rules hold, manifest/CSV/
matrices sorted and deterministic (double-build hash-equal), collisions
adjudicated. See `RQ_C1_EVIDENCE_SEAL.json`.

## 15. Remaining blockers

1. Sol High adjudication of the 37-packet Rules queue (2 gates block G04/K02 only).
2. Oracle confirmation of Murder/Cultivate/Ornithopter texts.
3. WS52/WS53 seam adjudication (external dependency; corpus is seam-agnostic by design).
4. No further RQ-C1 work: corpus engineering COMPLETE pending adjudication.

## 16. Terminal verdict input

Corpus engineering complete; first wave fully specified; unresolved Rules
questions explicitly segregated (2 gated scenarios + 35 confirmations + queue).
Proposed verdict: NEUTRAL_CORPUS_READY_PENDING_RULES_ADJUDICATION.
