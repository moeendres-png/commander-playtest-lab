# Provider Readiness Packet — pre-Freeze

Branch `wsr26/final-provider-readiness-20260928`. Supersedes the pre-remediation
WSR22 comparison for decision purposes.

`PRODUCTION_PROVIDER = NOT SELECTED`. `ARCHITECTURE_FREEZE = NOT CLAIMED`.

This packet contains facts and verdicts only. It names no winner. Rules
Correctness remains the highest-priority dimension, and the honest result of the
repaired pipeline is that neither candidate is currently close to demonstrable
Rules Correctness, for reasons that are recorded per candidate below.

---

## 1. Source lock

| Item | Identity |
|---|---|
| Commander-Lab main after #278 | `f96bc7ec6b7ea07c73f74282c16dcaf73daaad40`, tree `c60a0ce2ffff404efcff9ada2b7979ec0cdc9346` |
| Qualification boundary | `commander-lab.pre-freeze-qualification/2.0.0` |
| Transport protocol | `2.0.0` |
| Rules authority | `MagicCompRules 20260925.txt`, effective `2026-09-25`, SHA-256 `8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca` |
| Rules clause in scope | 103.8a |
| XMage candidate | `moeendres-png/mage@b19596980f2734496ea1896504253e1bdd2756dd`, bridge `xmage-engine-bridge 0.1.0-SNAPSHOT`, xmage `1.4.61` |
| Forge Rules Core (`COMMANDER_LAB_FORGE_FORK`) | `moeendres-png/forge@ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree `fc3387bf37aab19d780b2939a235309ed32b0492` |
| Forge bridge / evidence head | `moeendres-png/forge@e15f37d6b2b5c0ad682948f86f037e07b6aaded5`, tree `a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b`, PR #5, Draft, deliberately not merged to Forge master |
| Forge Lab bridge-source pin of record | `4753bb7c72ea60d653121e0bab989077b4009f9c` |
| Upstream Forge baseline (`UPSTREAM_FORGE_BASELINE`) | `Card-Forge/forge@a37a865a53280dd8ad6fad3384d69611e8c5a42f` — ancestry only, **not** verified pristine, upstream behaviour **not** observed |

The Forge Rules Core, the Forge bridge/evidence head, the Lab bridge-source pin
and the upstream baseline are four distinct commits. None is collapsed into a
single "Forge SHA", and no result observed on one is reported as evidence for
another.

**Measured, not assumed.** PR #5 head `e15f37d6` is 26 commits above the
Rules-Core head and changes `forge-protocol2-bridge` only; zero files change
outside that module. The six Rules-Core modules (`forge-game`, `forge-core`,
`forge-ai`, `forge-gui`, `forge-gui-desktop`, `adventure-editor`) are
byte-identical at both commits, which `engine_tree_equivalence` re-proves from git
on every run and refuses credit if any differ.

---

## 1b. Candidate heads newer than the consumed evidence — BOTH candidates are stale

**All four committed candidate artifacts are now `STALE_FOR_PUBLISHED_HEAD`:
both XMage artifacts and both Forge artifacts.** Neither candidate column
describes the bridge that currently exists. This is recorded rather than
resolved, because regenerating either column needs
`scripts/run_current_boundary_qualification.py`, which is under PR #284's active
writer lock.

### XMage — PR #293, merged, Rule-randomness defect repaired

PR #293 (merged to `main` as `adee8b16`) found and removed a silent skip of
Rules randomness on the XMage **generic lane** — the lane the current-boundary
pipeline uses. `XmageBridgePlayer.shuffleLibrary` was overridden as a no-op, so:

* CR 103.3 opening shuffles never happened, and neither did mulligan shuffles nor
  any "search … then shuffle";
* every library stayed in decklist order, so a principal who knew the decklist
  knew every library order **and every opening hand**;
* the engine's `SHUFFLE_LIBRARY` replacement check and `LIBRARY_SHUFFLED` event
  were suppressed, so shuffle replacements and triggers could never fire.

The same change binds the generic-lane Rules RNG seed and flips
`seed_supported` to `true`. The committed XMage artifacts consumed adapter commit
`f432605e`, which is on a parallel lineage and does not contain this change, so
they describe the old bridge.

**Directly verified at the repaired revision** (`BRIDGE_VALIDATION_XMAGE.json`,
bridge clean, `bridge_matches_recorded_revision: true`): the engine-bridge suite
is **344 tests, 0 failures, 0 errors**, and the focus suites pass —
`genericBridgePlayerNeverOverridesTheEngineShuffle`,
`differentSeedChangesTheOpeningShuffle`,
`bridgeAcknowledgesTheSeedFromEngineReadback`,
`principalScopedStateNeverCarriesTheSeedValue`, and
`sameSeedReproducesEveryOpeningLibraryAndHandForTwoToFivePlayers` (2P–5P).

That is a **bridge-level capability result, not a column requalification.** The
FULL107 rows are produced by the runner, so AF05/AF09 stay `UNKNOWN`.

### XMage — impact on findings this workstream derived

`XMAGE_SHUFFLE_IMPACT_ADJUDICATION.json` classifies the XMage-derived findings.
The rule is deliberately narrow: a finding is impacted only when its obligation
depends on library order, opening-hand contents or shuffle events.

| Finding | Disposition | Why |
|---|---|---|
| `xmage_hidden_01` opponent hand identities absent, count visible | **IMPACTED — requalification required** | opening hands were the first seven cards of the decklist, so hand contents were derivable from the ordering |
| `xmage_hidden_02` library identities/order absent, count visible | **IMPACTED — requalification required** | the defect made library order derivable from the decklist, which is the disclosure this obligation forbids |
| `xmage_pb08_seed_precondition` | **IMPACTED — requalification required** | the same change flipped the lane from `seed_supported: false` to a validated Rules seed |
| `af11_technical_facts` | unaffected | process topology and licence metadata do not depend on library order or RNG |

The projection did mask the arrays in both hidden rows; the **lane** still failed
the obligation, because a principal holding the decklist read both off the
ordering. No verdict moves and no disposition is rewritten — the findings are
marked as no longer citable for the current bridge.

### Forge — PR #6, still open



Two Forge pull requests are published against the head the committed evidence
consumed. Neither is merged, and **no committed Forge artifact is valid for
either**. This is recorded rather than acted on, because requalifying them
would mean mutating a candidate this workstream does not own.

| Candidate head | State | Touches | Effect on committed Forge evidence |
|---|---|---|---|
| `6f70e32e` (PR #6) | **OPEN draft**, 42 files, +13142/-19 | production Rules Core `forge-game/.../card/Card.java` (+24/-0, `getAllPossibleAbilities` aftermath surfacing) **and** `forge-protocol2-bridge/` | **STALE.** Committed Forge artifacts consumed Rules Core `ef958ee9` + bridge `e15f37d6`. |
| `e15f37d6` (PR #5) | OPEN draft, consumed by current evidence | `forge-protocol2-bridge/` only | Current; this is the head the evidence ran against. |

Consequences that follow directly, and are **not** decisions this workstream
made:

* **Nothing transfers from PR #5 evidence to PR #6.** PR #6 rewrites the Rules
  Core, and the Rules Core is the sole authority for legal actions. Relabelling
  a run with the newer head would be a silent false credit: the JSON stays
  well-formed, the row outcomes do not move, and the denominators still add up.
* **Split/fuse aftermath semantics need fresh adjudication.** `Card.java` changes
  exactly the ability-discovery path that governs the aftermath half of split
  cards, so `Find // Finality`, `Wear // Tear` and `Boseiju Reaches Skyward //
  Branch of Boseiju` are directly affected. PR #6's own packet records
  `Find // Finality` as `RUNTIME_QUALIFIED_FRONT_PLUS_ENGINE_GAP` and declares
  `global_verdict: PARTIAL (Forge-side preparation only; PB-07 global closure
  NOT claimed)`. That declaration is the donor's, not a Lab adjudication.
* **Generated evidence must be regenerated at the actually consumed head.** The
  `PROVIDER_EVIDENCE_BINDING.json` artifact records this mechanically: both
  Forge artifacts are `STALE_FOR_PUBLISHED_HEAD`, both XMage artifacts remain
  `BOUND_TO_CONSUMED_HEAD`. AF07 names the head it is bound to rather than
  presenting itself as candidate-neutral.
* Forge PR #6 is not mutated here. It is owned elsewhere and remains open.

`PROVIDER_EVIDENCE_BINDING.json` performs the same check on every run, so a
future relabelling attempt fails rather than passing quietly.

## 2. Runtime provenance

Produced by `scripts/run_current_boundary_qualification.py` from a clean committed
tree, against live engines. Four verified native-suite receipts:

| Receipt | Candidate | Group | Tests | Passed | Executed at | Engine identity |
|---|---|---|---|---|---|---|
| `native-forge-direct.json` | forge | direct | 150 | 150 | `e15f37d6b2b5` | `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL` |
| `native-forge-mechanism.json` | forge | mechanism | 67 | 67 | `e15f37d6b2b5` | `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL` |
| `native-xmage-direct.json` | xmage | direct | 34 | 34 | Lab `f432605e` | `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT` |
| `native-xmage-mechanism.json` | xmage | mechanism | 135 | 135 | Lab `f432605e` | `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT` |

The XMage rows name the Lab commit that actually executed, which is **not** the
candidate: `engine-bridge` is a module of this repository, so the executing head is
the Lab's. The engine identity is the provider's reported commit, verified at AF00.
These two figures were previously hand-written and had drifted from the receipts
they summarise. `test_receipt_counts_are_stated` now requires the packet's stated
value to be a prefix of `receipt["executed_commit"]`, and it caught the drift twice
while this workstream was in flight — which is the behaviour it is for. The value
moves whenever the pipeline is re-run, because each run records the commit it
executed from.

Each receipt binds the executing runner commit and tree, `dirty: false`, 28
per-input sha256 digests, a runner digest, the exact command, build identity,
wall-clock window, return code, counts and environment. A receipt that cannot be
re-derived, or that reports a failure, a non-zero exit or a digest mismatch, earns
no credit.

XMage's engine identity comes from the provider handshake because `engine-bridge`
is a module of this repository and has no engine checkout of its own. `AF00`
verifies the provider-reported commit against the expected candidate and is `PASS`
on both sides.

---

## 3. FULL107

107 accounted rows per candidate. No missing rows, no duplicates, no denominator
reduction, no carry-forward across changed evidence semantics.

| Candidate | PASS | FAIL | UNKNOWN | BLOCKED | CRASH | TIMEOUT | PROTOCOL_FAILURE | total |
|---|---|---|---|---|---|---|---|---|
| XMage | 5 | 0 | 58 | 44 | 0 | 0 | 0 | **107** |
| Forge | 5 | 0 | 58 | 44 | 0 | 0 | 0 | **107** |

The historical figures were XMage `30 PASS` and Forge `79 PASS`. They were upper
bounds over a PASS set that was substantially unobserved. The repaired pipeline
was not permitted to weaken a detector or fixture to preserve them, and did not.

The 44 `BLOCKED` rows on each side are the obligations that require a frozen
mid-game starting state, classified by mechanism rather than by fixture-id prefix.
PB-03 is closed as a harness defect; the blocker is a genuine capability gap in
the generic Protocol-2 surface, not a naming artifact.

---

## 4. Semantic comparison

| Disposition | Count |
|---|---|
| `NON_COMPARABLE` (evidence gap) | 107 |
| `SAME_SEMANTICS` | 0 |
| `RULES_VISIBLE_DIVERGENCE` | 0 |

Zero `SAME_SEMANTICS` is the correct outcome, not an omission. Only four rows
`PASS` on each side and none carries comparable normalized Rules-visible
semantics, so equality is claimed nowhere. `PASS/PASS` is never treated as
semantic equality: rows are reduced to a normalized signature over the evidence
they actually recorded, with candidate-specific identity removed and everything
the Rules can observe preserved.

---

## 5. AF00–AF11

| Gate | XMage | Forge |
|---|---|---|
| AF00 SOURCE_AND_BUILD_LOCK | **PASS** | **PASS** |
| AF01 PROTOCOL_HANDSHAKE | **FAIL** | **PASS** |
| AF02 PLAYER_CARDINALITY | **PASS** | **PASS** |
| AF03 RULES_AUTHORITY | **PASS** | **PASS** |
| AF04 LEGAL_ACTION_AND_DECISION_BOUNDARY | **FAIL** | UNKNOWN |
| AF05 HIDDEN_INFORMATION | UNKNOWN | UNKNOWN |
| AF06 GENERAL_RULES_CORRECTNESS | UNKNOWN | UNKNOWN |
| AF07 ACTUAL_CARD_BEHAVIOR | UNKNOWN | UNKNOWN |
| AF08 MULTIPLAYER_COMMANDER | UNKNOWN | UNKNOWN |
| AF09 RNG_REPLAY | UNKNOWN | UNKNOWN |
| AF10 RUNTIME_EVIDENCE_RELIABILITY | **PASS** | **PASS** |
| AF11 INTEROP_LICENSE_TOPOLOGY | UNKNOWN | UNKNOWN |

Every verdict is derived from an observation. No gate carries a historical
auto-PASS. AF04, AF05, AF06, AF07, AF08, AF09 and AF11 are not established for
at least one candidate, which is why no provider ranking is possible. AF03 is now
established for Forge on the repaired head and remains `PASS` for XMage.

AF11 was previously a hard-coded `FAIL` whose prose did not address its own
contract ("actual integration topology satisfies WS-09; Forge remains a genuine
separate process/service"). A gate that observes nothing cannot be evidence in
either direction, so it is now **computed** from the facts the Lab can actually
measure: each candidate is driven through its own distinct external adapter
(Forge `forge-protocol2-bridge`, XMage `engine-bridge/.../xmage`) by one and the
same driver column; no adapter identity resolves to the Lab's in-tree engine
package, so no engine code is embedded in the Lab process; both ran under the
recorded `commander-lab.pre-freeze-qualification/2.0.0` boundary; and the recorded
licence topology is XMage MIT / Forge GPL-3.0. Every one of those technical facts
holds on current evidence.

The residual question is **not** a Lab measurement: whether the candidate-scoped
decision-identity shim and the GPL-3.0 process topology satisfy AF11/WS-09 under
existing policy, and any licence/redistribution consequence, is recorded in both
`XMAGE_FREEZE_READINESS.json` and `FORGE_FREEZE_READINESS.json` as reserved for
Coordinator adjudication. AF11 is therefore `UNKNOWN`, not `PASS` — the Lab does
not invent a pass it cannot measure, and it does not assert a topological failure
it did not observe. This is not a loosening: freeze eligibility requires `PASS`,
and `UNKNOWN` is already in `NON_PASS_VERDICTS`, so neither candidate is closer
to eligible than before. The verdict becomes `FAIL` automatically if a technical
fact is ever actually violated, and the AF11 contract is recorded in
`architecture_freeze_gate_catalog_v2.json`.

---

## 6. Decision-critical findings

### 6.1 Forge no longer accepts an illegal Commander deck — `AF03` repaired and requalified

The committed WSR22-era probe proved the defect: the executed Forge bridge
**accepted** a deck whose commander was `Hill Giant`, a real card that is not a
legal Commander, and a deck whose colour identity violated its commander. CR 2.3
and the Commander format require both refusals. The same probe confirmed Forge
refused an unknown card name, a short mainboard and an empty mainboard, so it was
a specific gap in Commander-legality enforcement rather than a broken import path.
It was recorded, not masked in the Lab: masking it in the harness would have been
a second source of legality.

Forge PR #5 head `e15f37d6` repairs it at the provider boundary: `import_deck`
delegates to the Rules Core's own `DeckFormat.Commander.getDeckConformanceProblem`
and refuses with the distinct `deck_not_legal` code, so "the engine read this deck
and refused it" stays distinguishable from "the deck could not be read". The fresh
probe on the repaired head shows:

- the legal control deck (`Isamaru, Hound of Konda` + 99 `Plains`) is accepted;
- `Hill Giant` as commander is refused by the engine's commander predicate
  (`deck_not_legal`: "has an illegal commander");
- the colour-identity probe (`Shivan Reef` x99 under a mono-white commander, a
  non-basic, non-legendary card so the mutation isolates colour identity rather
  than an incidental size or copy limit) is refused by the engine's colour-identity
  rule (`deck_not_legal`: "do not match the commanders color identity");
- unknown card, short mainboard and empty mainboard are refused as
  `deck_import_failed`.

AF03 is `PASS` for Forge on the repaired head, earned by the Rules Core's own
conformance check rather than by a Lab-side filter.

### 6.2 Hidden information differs by candidate, and only one is a demonstrated leak

The two candidates are **not** in the same state, and an earlier revision of this
packet said they were. It accused Forge of a content leak that Forge does not
commit. The corrected reading:

**XMage — demonstrated engine defect (committed pre-remediation artifact).**
`get_game_state` on the generic B4-D lane returns **byte-identical** state to
every observer: one distinct state view across four different requesters,
containing, for all four seats, the real `player_id`, the hand card object ids
and the library contents. Because the requester differs while the payload does
not, each caller necessarily sees every other seat's cards. Attribution
`ENGINE_CANDIDATE_DEFECT`. This paragraph describes the committed
current-boundary artifact, which was produced before PR #283; PR #283
(`5db60757`, merged as `c9277b90`) carries the XMage remediation and its own
exact-head runtime verification, and the Lab current-boundary XMage column is
deliberately not regenerated in this Forge workstream.

**Forge — established, not defective.** The Forge bridge redacts correctly: it
returns **four distinct** state views, the requesting seat's real card names and
`"<hidden>"` for every opponent card. Forge PR #5 head `e15f37d6` also marks the
observation with the validated requester: the state names `observer_player_id`
and exactly one player row carries `is_actor`. `HIDDEN_INFO_FORGE.json` records
`PRINCIPAL_SCOPED`, attribution `NONE`, four established requesters and no
findings, and the distinctness comparison is over observed content only, so
changing the requester marker alone can never fabricate four distinct views. AF05
stays `UNKNOWN` for a different reason: the per-scenario hidden rows remain
unreachable on the generic surface, not because the projection is unproven.

The distinction matters in both directions. A redaction placeholder is the
*absence* of content, and counting a placeholder array as exposed hand content
manufactures an accusation. Conversely, an undemonstrated leak must never be
asserted: without actor marking, content on a seat that is not known to be the
requester's may be the requester's own.

The Lab does not mask the XMage finding and the hidden-information gate earns no
credit on either candidate. The full-game lane uses a different protocol and is
properly scoped through `XmageFullGameStateRedactor`, which this workstream
repaired to emit seat-derived opaque tokens for every non-viewer principal.

### 6.3 Rules RNG — the two candidates are in different states, not the same

An earlier revision of this packet said "no seed is sent" for both candidates. That
is false for Forge. They are separate gaps of different widths.

**XMage — fully uncontrolled.** `AF01_XMAGE.json` reports `seed_supported: false`.
The driver reads that capability and therefore does not send a seed, the create
response acknowledges none, and the binding is `UNCONTROLLED_ENGINE_RNG` with
`rng_credit: false`. Nothing about the run's randomness is under Lab or engine
control. Closing this needs a seed-capable generic lane or an engine-level
binding.

**Forge — seed acknowledged from engine state at creation.** `AF01_FORGE.json`
reports `seed_supported: true`, `_probes_forge.json` records
`provider_seed_supported: true` and `seed_sent_to_provider: true`. Forge PR #5
head `e15f37d6` installs the seed as part of `create_commander_game` and
acknowledges it from the engine's own accepted state
(`MyRandom.getRootSeed()/isExplicitSeed()`), never from the request value. The
observed game state carries the engine binding:

```
rng_binding: {explicit_seed: true, require_explicit_seed: true,
              root_seed: 424242, rules_root_seed: 424242, rules_calls: 393}
```

`RNG_REPLAY_FORGE.json` records `classification: ACKNOWLEDGED_ENGINE_SEED`,
`acknowledged_seed: 424242`, `controlled: true`, `rng_credit: true`, source
`create_commander_game_response`. A rejected or divergent readback fails closed
with `seed_unsupported` and registers no session, and an unseeded launch clears a
stale explicit binding, so an uncontrolled run cannot silently inherit a seed.

AF09 stays `UNKNOWN` because the clean-process replay twin rows remain blocking,
not because the seed binding is unproven. What Forge now has is engine-accepted
seed control at the creation transaction; prescribing a seed-capable lane for both
candidates would have been wrong on Forge's evidence.

The earlier literal `engine_owned: true` no longer appears in any production source
or artifact on either side.

### 6.4 Actual-card corpus is not executed — PB-07 open

Both artifacts declare 12 card names against 29 required, `complete: false`.
`CARD_02` is `UNKNOWN` on both sides, so no card has behaviourally executed and the
executed set is empty. Four decks are imported at runtime, which proves import and
engine-side rejection of unknown names, not card behaviour. Import, parsing,
construction and lookup are not counted as runtime card behaviour.

Completion is derived from the behaviourally executed set, never from the declared
list. An earlier version computed `complete` from the number of names in the
artifact, so simply appending 29 names would have advertised a complete runtime
corpus with no probe behind it, and it also counted `len(deck_identity)`, which is
a per-seat deck count and says nothing about cards.

The Forge-side ceiling recorded on Forge PR #5 is 28 runtime-qualified with one
documented engine gap, `Find // Finality` (the Aftermath back-half legal ability
discovery). That 28/29 is Forge-local and is **not** consumed as Lab credit here.

### 6.5 The 29-card corpus is largely outside the 107-row denominator

Structural finding (`CODE_DERIVED`). `COMMON_FIXTURE_MANIFEST_v1` defines 29
`CARD_nn` fixtures and all 29 carry a `card_identity`, but only **`CARD_02`** is
present in the 107-row denominator. `CARD_01` and `CARD_03`..`CARD_29` are
manifest fixtures that are not rows.

This is why `ACTUAL_CARD_*.json` reports `card_fixtures: 29` with
`card_fixtures_passed: 0` and `behaviorally_executed_count: 0`: AF07 is scored
against fixtures that the current denominator cannot execute. The corpus gap is
therefore partly a **denominator/accounting** question and not only a missing
engine harness.

Not resolved here, deliberately. The `CARD_` mapping, execution dispatch and
corpus accounting all live in `scripts/run_current_boundary_qualification.py`,
and the native `CARD` harnesses in `engine-bridge/.../XmageFullGameCard02ExecutionTest.java`
and `XmageNativeStateRestorationTest.java` — all under PR #284's active writer
lock. Separately, *whether* the denominator should be widened to carry all 29
fixtures, or AF07 satisfied by a separate corpus artifact, is an evidence-policy
decision reserved to the Coordinator, not a Lab change.

### 6.6 Per-obligation dispositions replaced two blanket UNKNOWN families

Two families were recorded with a single reason that was too coarse to act on.
Each obligation is now classified individually against the live observations,
persisted as `PB06_HIDDEN_OBLIGATIONS_<CAND>.json` and
`PB08_REPLAY_OBLIGATIONS_<CAND>.json`, and surfaced in AF05 and AF09.

| Family | XMage | Forge | What the disposition records |
|---|---|---|---|
| PB-06 hidden info | 2 satisfied, 18 unestablished | 1 satisfied, 19 unestablished | `HIDDEN_01` (opponent hand identities absent, count visible) and `HIDDEN_02` (library identities/order absent, count visible) are stated purely over the principal-scoped state view the generic lane does expose, and the live observations satisfy them. |
| PB-08 replay/RNG | 0 preconditions, 5 unestablished | 1 precondition, 4 unestablished | Forge acknowledges the requested seed `424242`; XMage does not. Both candidates **refuse** the semantic replay export. |

The Forge/XMage split on `HIDDEN_02` is a real difference, not a gap in the
evidence: Forge's projection returns no library **count**, so identity absence
is unproven rather than assumed. A missing count is treated as unproven, never
as safe.

Boundaries these dispositions do not cross:

* No obligation is credited from a different obligation's evidence. `HIDDEN_04`
  (face-down permanent) is not satisfied by observing masked opponent hands.
* Uncredible principal scoping credits nothing, so one principal's correct
  scoping cannot launder an unscoped projection.
* A fail-closed export refusal is an absent capability, never a satisfied
  obligation.
* An acknowledged seed is a **precondition** for RNG control, not a demonstrated
  `RulesRngTape`, so the obligation stays unestablished.
* **No disposition flips a FULL107 row.** Row outcomes belong to
  `run_current_boundary_qualification.py` under PR #284's active writer lock, so
  these classify only; the owner can consume them without a second
  implementation. AF05 and AF09 both stay `UNKNOWN`.

One false claim was removed while doing this: AF09 previously read "replay
export **executed** in a live game" when the artifact records that the engine
**refused** it. The line now states the attempt was refused.

### 6.7 Neither committed lane demonstrates the shuffle a legal game start requires

`LANE_INTEGRITY_<CAND>.json` applies the check that the XMage defect exposed as
missing. CR 103.3 requires each player to shuffle their library to start a game,
so a lane that demonstrates no shuffling has not executed a legal game start.
This is a statement about the game, not about harness coverage, and the two must
not be conflated — which is exactly how the defect survived: the evidence
faithfully recorded `HIDDEN_11 = "no shuffle/order-knowledge invalidation
scenario reachable"` and that line was read as an ordinary coverage gap.

**Both committed lanes fail this check, which is the point of recording it for both:**

| Lane | Seed control | Shuffle-invalidation scenario | Disposition |
|---|---|---|---|
| XMage | none (`seed_supported: false`, no seed) | `HIDDEN_11` unreachable | `LANE_SHUFFLE_NOT_DEMONSTRATED` |
| Forge | acknowledged seed `424242` | `HIDDEN_11` unreachable | `LANE_SHUFFLE_NOT_DEMONSTRATED` |

Forge was **not** exempt from this scrutiny just because its defect was not
published. It has an acknowledged Rules seed and still no reachable
shuffle-invalidation scenario, so its order-knowledge obligations are blocked on
the same basis. A defect being public for one candidate is not a reason to
assume the other is clean.

On both lanes this blocks `HIDDEN_02`, `HIDDEN_09`, `HIDDEN_10` and `HIDDEN_11`
from being credited. The obligations are blocked by their own nature — they are
about order knowledge that shuffling is what invalidates — not by whether a
harness happened to mention them. Note that this is an **independent** line of
reasoning from the impact adjudication above, and the two converge.

It does not diagnose either engine. "No shuffle was observed" is a fact about
the run; the cause is for the owner of that lane. And it does not claim the
repaired XMage lane now satisfies any of these — only a fresh run at the
repaired revision can establish that.

### 6.8 The seven forbidden shortcuts are unreachable at the validation seam

`FORBIDDEN_SHORTCUT_CAMPAIGN.json` answers the seven `NEGATIVE_*` obligations
behaviourally rather than by keyword search. A static scan cannot tell
`candidates[0]` as a forbidden first-option pick from the same subscript reached
only after an exact-uniqueness check, and it produces nothing at all for a
forbidden behaviour that is simply absent. So each obligation is tested by
feeding the production validator a proposal that **would** succeed if that
shortcut were reachable, and recording that it fails closed instead.

**Result: 7 of 7 fail closed, 0 reachable**, at
`commander_lab.engine.action_validation.validate_action_proposal`.

| Obligation | Adversarial input | Outcome |
|---|---|---|
| `NEGATIVE_FIRST_OPTION` | three offered actions identical except `action_id`, nothing in the proposal can single one out | fails closed: *"must identify exactly one engine-offered legal action"* |
| `NEGATIVE_SILENT_SKIP` | a proposal naming no offered action | fails closed |
| `NEGATIVE_DEFAULT_YES_NO` | a required choice omitted | fails closed: *"missing required choices"* |
| `NEGATIVE_RANDOM_OPTION` | a choice outside the offered schema | fails closed |
| `NEGATIVE_INTERNAL_AI` | an actor that does not hold priority | fails closed |
| `NEGATIVE_GUI_DEFAULT` | a target the engine did not offer | fails closed |
| `NEGATIVE_PARENT_CLASS_FALLBACK` | a mode the engine did not offer | fails closed |

A positive control accompanies the campaign: a proposal matching exactly one
offered action is **accepted**, and the returned value is the engine's own
`LegalAction` object. The campaign therefore does not pass by rejecting
everything — the seam still works, and the validator never substitutes an object
of its own.

**What this does not establish, stated plainly.** This is the behaviour of *one*
seam: the validation a proposal must pass to reach the engine. It is not an audit
of every production-reachable surface, and it does not claim the seven
obligations are globally discharged. It says nothing about engine behaviour, and
it does not promote any FULL107 row: row outcomes belong to
`run_current_boundary_qualification.py` under PR #284's active writer lock. A
global audit is a separate, larger exercise and is not claimed here.

One correction worth recording: the campaign's first draft reported
`NEGATIVE_FIRST_OPTION` as **reachable**. That was a defect in the adversarial
input, not in the validator — the three offered actions differed in
`source_object_id`, so the proposal legitimately disambiguated one of them. The
case now offers actions identical in every field a proposal can name, which is
the input a first-option shortcut would actually resolve. The campaign caught
its own weak test, which is the behaviour it exists to produce.

### 6.9 Both denominators are shaped by Lab work

PB-03 showed the XMage column is shaped by a Lab harness shortcut; PB-09 shows the
Forge column is shaped by Lab engine modification. Neither column is a clean
candidate measurement. This is recorded rather than resolved, because which
artifact is the Forge candidate is a Coordinator provider decision.

---

## 7. Blocker register

| Blocker | Side | Status after this workstream | Basis |
|---|---|---|---|
| PB-03 starting-state classification | both | **RESOLVED** (mechanism); block attribution now per candidate | mechanism-based classifier, split measured exact against the effective materialization, no fixture-id prefix, 107-row denominator preserved. Block attribution reads each candidate's own declared capability: Forge declares the seam, so its 44 rows are a Lab execution-path gap, not a Forge capability gap |
| XMage evidence staleness | xmage | **STALE — REQUALIFICATION REQUIRED** | PR #293 (merged `adee8b16`) removed the `shuffleLibrary` no-op that silently skipped CR 103.3 opening/mulligan shuffles and left every library in decklist order, then bound the generic-lane Rules RNG seed. Committed XMage artifacts consumed adapter `f432605e`, which does not contain the change. Bridge capability is directly verified at the repaired revision (344 tests, 0 failures); the FULL107 column is not, and needs `run_current_boundary_qualification.py` under PR #284's lock. HIDDEN_01, HIDDEN_02 and the PB-08 seed precondition are marked IMPACTED (§1b) |
| PB-05 build provenance | forge | **RESOLVED** | Forge PR #5 (continuing the PR #4 repair) removes the fail-open paths; `verify_pb05_provenance` consumes build commit/tree/dirty/source/verified independently of the provider's self-assessment; Forge AF00 `PASS` |
| PB-06 per-scenario hidden channels | both | **SPLIT: Forge RESOLVED on this boundary; XMage historical** | Forge now marks the observing principal (`observer_player_id` + exactly one `players[].is_actor`); `HIDDEN_INFO_FORGE.json` is `PRINCIPAL_SCOPED`, attribution `NONE`, four established requesters, and the distinctness comparison is content-only. The committed XMage artifact remains the pre-#283 demonstrated leak; PR #283 carries the XMage remediation and its own exact-head runtime verification, and this workstream does not re-run it. Per-scenario channels remain unexecuted (§6.2) |
| PB-07 effective 29-card corpus | both | **BLOCKED** | 12 declared of 29 required, `CARD_02` `UNKNOWN`. Completion is derived from behaviourally executed cards, so naming 29 cards cannot advertise a complete corpus (§6.4). Additionally **28 of the 29 mandatory `CARD_nn` fixtures are not rows in the 107 denominator at all** (§6.5), so AF07 is partly a denominator-accounting question; the execution dispatch is under PR #284's active writer lock |
| PB-08 clean-process replay twin | both | **SPLIT: both seed paths now exist at bridge level; twin rows BLOCKED; XMage column STALE** | XMage is fully uncontrolled, so a same-seed twin proves nothing. Forge now acknowledges the accepted seed from engine state in the creation transaction (`ACKNOWLEDGED_ENGINE_SEED`, `rng_credit: true`); the clean-process twin half per fixture remains unproven and is what keeps AF09 `UNKNOWN`. Per-obligation: Forge observes 1 precondition and 4 unestablished, XMage 0 and 5; **both candidates refuse the semantic replay export**, so the four `REPLAY_*` obligations need that seam on either side (§6.6). XMage's recorded 0 preconditions is a statement about the pre-#293 bridge and is **IMPACTED**: the repaired lane binds a validated Rules seed (`BRIDGE_VALIDATION_XMAGE.json`), so the XMage column must be regenerated before its PB-08 disposition is cited (§1b) |
| PB-09 Forge candidate identity | coordinator | **RESOLVED — IDENTITY SPLIT** | resolved as an identity split: the production candidate is the Lab fork `ef958ee9` (tree `fc3387bf`), and upstream `a37a865a` is retained for attribution and control only. The four Forge commits are kept distinct and no result is transferred between them (§1) |
| Aftermath `Find // Finality` | forge | **NON_BLOCKING_CAPABILITY_GAP** | not decision- or release-blocking on current evidence; recorded, no engine mutation opened |
| Forge PR #6 supersedes consumed evidence | forge | **STALE — REQUALIFICATION REQUIRED** | PR #6 (`6f70e32e`, OPEN draft) rewrites the production Rules Core `forge-game/.../card/Card.java` and the bridge. Committed Forge artifacts consumed Rules Core `ef958ee9` + bridge `e15f37d6`, so **nothing transfers**; split/fuse aftermath semantics are directly affected. Enforced by `PROVIDER_EVIDENCE_BINDING.json` (§1b) |
| PB-03 Tier-1/Tier-2 behaviour credit | xmage | **WAIT_FOR_OWNER / #284** | `main` merged PR #291, which landed the Muse PB-03 dimension-admission discriminator (reused, not reimplemented). The Tier-1/Tier-2 behaviour credit stays blocked by a P1 in the shared mana helper that `main` documents and does **not** claim as passed. No co-edit with #284 |

---

## 8. Comparison dimensions, facts only

| Dimension | XMage | Forge |
|---|---|---|
| Protocol handshake (AF01) | FAIL | PASS |
| External discretionary decisions bound to engine-offered options | PASS (4 PASS rows) | PASS (4 PASS rows) |
| Player cardinality 2P/3P/4P/5P (AF02) | PASS | PASS |
| Bounded 6P | attempted, not separately credited | attempted, not separately credited |
| Commander deck legality at import (AF03) | PASS | **PASS** (repaired on PR #5 head `e15f37d6`) |
| Principal-scoped hidden information | **FAIL — demonstrated engine defect in the committed pre-#283 artifact** | **PASS — established** (`PRINCIPAL_SCOPED`, four requesters, content-only distinctness) |
| Rules RNG control (AF09) | **UNCONTROLLED** — no seed sent, `seed_supported: false` | **ACKNOWLEDGED_ENGINE_SEED** — create response acknowledges the engine-accepted root seed; twin rows keep AF09 `UNKNOWN` |
| Semantic replay | UNKNOWN | UNKNOWN |
| Actual-card runtime behaviour | UNKNOWN | UNKNOWN |
| Mid-game starting-state materialization | BLOCKED, 44 rows | BLOCKED, 44 rows |
| Failure semantics | fail-closed on unknown messages and illegal actions | fail-closed, confirmed against a live game at event offset 17 |
| Process isolation | per-decision-process lane | clean-process twin exists Forge-side, unconsumed |
| Build provenance | handshake-reported, verified at AF00 | build-derived, verified at AF00 |
| Maintenance / integration burden | in-repo bridge, small surface | out-of-repo fork, GPL-3.0 derivative, 47 Rules-touching Lab commits |

Legal actions, priority, mana and cost payment, targets/modes/choices, stack,
triggers, replacement/prevention, continuous effects and layers, SBAs, zones,
copy/control, combat, command zone, commander tax, commander damage, Partner and
per-count multiplayer lifecycle are **not established for either candidate**: they
sit inside the 58 `UNKNOWN` and 44 `BLOCKED` rows.

---

## 9. What would change the verdict

1. A Coordinator ruling on the AF11 policy residual: whether the candidate-scoped
   decision-identity shim plus the GPL-3.0 process topology satisfies AF11/WS-09
   under existing policy, and any licence/redistribution consequence. The
   technical half of AF11 is measured and holding; only this policy half is
   open. (PB-09 identity split is resolved: the production Forge column is the
   `ef958ee9` fork, and upstream `a37a865a` is attribution/control only.)
2. For Forge this is done on the current boundary: the observing principal is
   marked and the projection is `PRINCIPAL_SCOPED`. AF05 remains `UNKNOWN` only
   because the per-scenario hidden rows are unreachable on the generic surface.
   The XMage generic-lane projection was remediated by PR #283 on its own exact
   head; requalifying the XMage current-boundary column is separate work this
   packet does not claim.
3. For XMage, a seed-capable generic lane or an engine-level RNG binding. For
   Forge the creation-transaction acknowledgement now exists from engine state
   (`ACKNOWLEDGED_ENGINE_SEED`); AF09 stays `UNKNOWN` on the clean-process twin
   rows. PB-08's Forge half is closed on this boundary.
4. Execution of the 29-card corpus under the actual-behaviour standard. This
   unblocks PB-07 and AF07.
5. A starting-state materialization seam. This unblocks the 44 `BLOCKED` rows and
   AF08.

**Attribution is per candidate, and one item is a Lab defect, not a candidate
gap.** `AF01_FORGE.json` reports `starting_state_injection_supported: true` and
`scenario_injection_supported: true`, while `AF01_XMAGE.json` reports
`starting_state_injection_supported: false` on the generic lane. Forge's 44
`BLOCKED` rows were therefore attributed by a reason that cited XMage's `false`,
which is wrong for Forge: the obligation is unestablished and uncredited either
way, but for Forge the block is a **Lab execution-path gap** — the candidate
declares the capability and this run did not exercise the seam — whereas for
XMage it is a genuine capability gap.

Consequence for remediation: item 5 is two different pieces of work. XMage needs
a starting-state seam; Forge needs the Lab to exercise the seam it already
declares. Closing Forge's rows is Lab work, and this packet no longer rules it out.

Item 1 is also a Lab execution-path question rather than a candidate defect,
because the fault is a shared classifier reason applied to a candidate that
discloses the capability. The classifier's *mechanism* requirement is
candidate-neutral and correct; only its capability attribution was wrong, and it
is now taken from each candidate's own reported capabilities.

---

## 10. Terminal state

`PROVIDER_COMPARISON_COMPLETE = NO` — the comparison is honestly produced, but
`SAME_SEMANTICS` is 0 of 107 and six required dimensions are unestablished for
both candidates, so no capability ranking is admissible.

`DECISION_CRITICAL_UNKNOWN_REMAINS = YES` — PB-09, PB-07, the per-scenario
hidden rows, the Forge clean-process twin rows, and AF04–AF09 for at least one
candidate on both sides. The Forge requester binding and the Forge
creation-seed acknowledgement are no longer among them.

`PROVIDER_SELECTION_READY = NO`.

`ARCHITECTURE_FREEZE_READY_FOR_COORDINATOR = NO`.

`PRODUCTION_PROVIDER = NOT SELECTED`. `ARCHITECTURE_FREEZE = NOT CLAIMED`.
