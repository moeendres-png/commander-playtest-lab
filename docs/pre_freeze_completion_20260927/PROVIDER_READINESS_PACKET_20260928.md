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
| XMage candidate (successor live pin) | `moeendres-png/mage@f79e4168902e65063034b21be6f4585397fd43b3`, bridge `xmage-engine-bridge 0.1.0-SNAPSHOT`, xmage `1.4.61` |
| XMage prior boundary identity (historical, not repinned) | `moeendres-png/mage@b19596980f2734496ea1896504253e1bdd2756dd` — the sealed WSR22 identity; `source_lock.py` is deliberately not repinned |
| Forge Rules Core (`COMMANDER_LAB_FORGE_FORK`) | `moeendres-png/forge@ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree `fc3387bf37aab19d780b2939a235309ed32b0492` |
| Forge bridge / evidence head | `moeendres-png/forge@e15f37d6b2b5c0ad682948f86f037e07b6aaded5`, tree `a1d4d4a8fe421e57b919e8e0bd9fda7d9deb0d3b`, PR #5, Draft, deliberately not merged to Forge master |
| Forge Lab bridge-source pin of record | `4753bb7c72ea60d653121e0bab989077b4009f9c` |
| Upstream Forge baseline (`UPSTREAM_FORGE_BASELINE`) | `Card-Forge/forge@a37a865a53280dd8ad6fad3384d69611e8c5a42f` — ancestry only, **not** verified pristine, upstream behaviour **not** observed |

The Forge Rules Core, the Forge bridge/evidence head, the Lab bridge-source pin
and the upstream baseline are four distinct commits. None is collapsed into a
single "Forge SHA", and no result observed on one is reported as evidence for
another.

**Successor current-boundary epoch (2026-09-29).** The XMage column in this
packet was requalified under the PB-03 fresh-main reconciliation workstream, in a
successor run of the same authoritative pipeline: the runner binds the canonical
live pin from `config/rules_engines.json` (`f79e4168`), and the frozen WSR22
`source_lock` identity stays historical. The Forge column was re-executed in the
documented bridge/evidence checkout at `e15f37d6` (Rules Core trees proven
identical to `ef958ee9`), because the default Forge workspace had moved to a
divergent WSR20 branch whose bridge lacks the Commander-legality repair; a run
against that checkout produced a spurious AF03 FAIL and was discarded. Every
receipt and artifact recorded below now names the commit that actually executed.

**Measured, not assumed.** PR #5 head `e15f37d6` is 26 commits above the
Rules-Core head and changes `forge-protocol2-bridge` only; zero files change
outside that module. The six Rules-Core modules (`forge-game`, `forge-core`,
`forge-ai`, `forge-gui`, `forge-gui-desktop`, `adventure-editor`) are
byte-identical at both commits, which `engine_tree_equivalence` re-proves from git
on every run and refuses credit if any differ.

---

## 2. Runtime provenance

Produced by `scripts/run_current_boundary_qualification.py` from a clean committed
tree, against live engines. Four verified native-suite receipts:

| Receipt | Candidate | Group | Tests | Passed | Executed at | Engine identity |
|---|---|---|---|---|---|---|
| `native-forge-direct.json` | forge | direct | 150 | 150 | `e15f37d6b2b5` | `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL` |
| `native-forge-mechanism.json` | forge | mechanism | 67 | 67 | `e15f37d6b2b5` | `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL` |
| `native-xmage-direct.json` | xmage | direct | 34 | 34 | Lab `75816f5f` | `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT` |
| `native-xmage-mechanism.json` | xmage | mechanism | 179 | 179 | Lab `75816f5f` | `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT` |

The XMage rows name the Lab commit that actually executed, which is **not** the
candidate: `engine-bridge` is a module of this repository, so the executing head is
the Lab's. The engine identity is the provider's reported commit, verified at AF00.
These two figures were previously hand-written and had drifted from the receipts
they summarise. `test_receipt_counts_are_stated` now requires the packet's stated
value to be a prefix of `receipt["executed_commit"]`, and it caught the drift twice
while this workstream was in flight — which is the behaviour it is for. The value
moves whenever the pipeline is re-run, because each run records the commit it
executed from.

Each receipt binds the executing runner commit and tree, `dirty: false`, 61
per-input sha256 digests, a runner digest, the exact command, build identity,
wall-clock window, return code, counts and environment. A receipt that cannot be
re-derived, or that reports a failure, a non-zero exit or a digest mismatch, earns
no credit. The runner digest is content-bound: it covers the commit, tree, dirty
state and every executed-input digest, and deliberately excludes the capture
timestamp so the runner and the assembler — different processes — compare the
same identity for the same tree. A real post-#344 run exposed that the timestamp
had been inside the digest, which silently zeroed every freshly executed
receipt; the repair is in `receipts.py` and is regression-locked.

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
PB-03 now has a production-reachable mid-game lane on the XMage side: the live
per-dimension manifest admits 12 of the 30 frozen-state rows
(`TECHNICALLY_CONFORMANT`), 16 stay blocked on dimensions the engine does not
declare, and the bound native runtime ledger proves all 30 exact audited
testcases ran green (`FRESH_EXACT`). Reachability is not FULL107 credit and no row
is promoted from it, so the 44 `BLOCKED` rows stay blocked pending the exact
semantic-obligation bindings; that is the honest current state, not a naming
artifact.

---

## 4. Semantic comparison

| Disposition | Count |
|---|---|
| `NON_COMPARABLE` (evidence gap) | 107 |
| `SAME_SEMANTICS` | 0 |
| `RULES_VISIBLE_DIVERGENCE` | 0 |

Zero `SAME_SEMANTICS` is the correct outcome, not an omission. Only five rows
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
at least one candidate, which is why no provider ranking is possible. AF03 is
`PASS` for both candidates on this boundary (Forge on the repaired bridge head
`e15f37d6`, XMage on the live pin). AF11 moved from `FAIL` to `UNKNOWN` on the
successor run: every observable interop/licence fact holds (separate external
processes, no embedded engine, a shared recorded boundary), so the residual is
the Coordinator-owned AF11 policy question rather than a measured violation.

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

**XMage — historical defect, requalified on the successor run.** The sealed
WSR22 artifact demonstrated an engine defect: `get_game_state` on the generic
B4-D lane returned **byte-identical** state to every observer — one distinct
state view across four different requesters, containing, for all four seats, the
real `player_id`, the hand card object ids and the library contents — with
attribution `ENGINE_CANDIDATE_DEFECT`. The successor current-boundary run on the
live pin and the current bridge requalified that column: four distinct state
views, `PRINCIPAL_SCOPED`, attribution `NONE`, all four requesters established
by an authoritative binding, no engine leak indicator and no zone content on an
unmarked seat. The committed artifact is `HIDDEN_INFO_XMAGE.json`; the regression
guard now requires the scoped facts, so a return to the shared-view defect fails
rather than passing as "not a defect". AF05 stays `UNKNOWN` for the per-scenario
hidden rows, not because the projection is unproven.

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

Neither candidate's generic-lane projection is masked, and both now measure
`PRINCIPAL_SCOPED` on this boundary. The hidden-information gate still earns no
credit on either candidate, because AF05's per-scenario hidden rows remain
unreachable on the generic surface rather than because the projection is
unproven. The full-game lane uses a different protocol and is scoped through
`XmageFullGameStateRedactor`, which emits seat-derived opaque tokens for every
non-viewer principal.

### 6.3 Rules RNG — the two candidates are in different states, not the same

An earlier revision of this packet said "no seed is sent" for both candidates.
On the sealed WSR22 boundary XMage was fully uncontrolled; the successor run
requalified both columns, and the two candidates are in different states, at
different evidence depths.

**XMage — seed acknowledged at the creation transaction.** The sealed WSR22
position was that XMage was fully uncontrolled: `seed_supported: false`, no seed
sent by the driver, binding `UNCONTROLLED_ENGINE_RNG` with `rng_credit: false`.
The successor run on the live pin reports `seed_supported: true`, the driver
sends the seed, and the creation transaction acknowledges the engine-accepted
seed — `ACKNOWLEDGED_ENGINE_SEED`, source `create_commander_game_response`,
`controlled: true`, `rng_credit: true`, acknowledged seed == requested seed ==
`424242`. Unlike Forge, XMage does not expose the engine's own root seed or Rules
call count in the observed state, so the acknowledgement rests on the creation
transaction rather than on a state readback. AF09 stays `UNKNOWN` on the
clean-process replay twin rows, not on the seed binding.

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
not because the seed binding is unproven. Both candidates now acknowledge the
seed at the creation transaction; Forge additionally exposes the engine's own
accepted root seed and Rules call count in the observed state. The two positions
are reported separately rather than collapsed.

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

### 6.5 Both denominators are shaped by Lab work

PB-03's original XMage shape was a Lab harness shortcut; the successor run
replaced it with a production-reachable mid-game lane and record-aware dimension
admission (12 admitted / 18 blocked, runtime ledger 30/30 fresh), while keeping
FULL107 row credit unaffected. PB-09 shows the Forge column is shaped by Lab
engine modification. Neither column is a clean candidate measurement. This is
recorded rather than resolved, because which artifact is the Forge candidate is a
Coordinator provider decision.

---

## 7. Blocker register

| Blocker | Side | Status after this workstream | Basis |
|---|---|---|---|
| PB-03 starting-state classification | both | **RESOLVED** (mechanism); XMage also has a production-reachable starting-state lane; FULL107 rows stay uncredited | mechanism-based classifier, split measured exact against the effective materialization, no fixture-id prefix, 107-row denominator preserved. Successor evidence: the live per-dimension manifest admits 12/30 frozen-state rows, 18 are blocked (16 on undeclared dimensions, 2 on the declared controller/owner divergence), and the bound native runtime ledger executes all 30 exact audited testcases (`FRESH_EXACT`); qualification credit remains NONE. Block attribution reads each candidate's own declared capability: Forge declares the seam, so its 44 rows are a Lab execution-path gap, not a Forge capability gap |
| PB-05 build provenance | forge | **RESOLVED** | Forge PR #5 (continuing the PR #4 repair) removes the fail-open paths; `verify_pb05_provenance` consumes build commit/tree/dirty/source/verified independently of the provider's self-assessment; Forge AF00 `PASS` |
| PB-06 per-scenario hidden channels | both | **SPLIT: Forge RESOLVED on this boundary; XMage historical** | Forge now marks the observing principal (`observer_player_id` + exactly one `players[].is_actor`); `HIDDEN_INFO_FORGE.json` is `PRINCIPAL_SCOPED`, attribution `NONE`, four established requesters, and the distinctness comparison is content-only. The committed XMage artifact remains the pre-#283 demonstrated leak; PR #283 carries the XMage remediation and its own exact-head runtime verification, and this workstream does not re-run it. Per-scenario channels remain unexecuted (§6.2) |
| PB-07 effective 29-card corpus | both | **BLOCKED** | 12 declared of 29 required, `CARD_02` `UNKNOWN`. Completion is derived from behaviourally executed cards, so naming 29 cards cannot advertise a complete corpus (§6.4) |
| PB-08 clean-process replay twin | both | **SPLIT: Forge seed acknowledgement RESOLVED; twin rows BLOCKED** | XMage is fully uncontrolled, so a same-seed twin proves nothing. Forge now acknowledges the accepted seed from engine state in the creation transaction (`ACKNOWLEDGED_ENGINE_SEED`, `rng_credit: true`); the clean-process twin half per fixture remains unproven and is what keeps AF09 `UNKNOWN` |
| PB-09 Forge candidate identity | coordinator | **OPEN — RESERVED** | which artifact is the candidate: pinned upstream `a37a865a` or the Lab fork `ef958ee9`. Not a coding question |
| Aftermath `Find // Finality` | forge | **NON_BLOCKING_CAPABILITY_GAP** | not decision- or release-blocking on current evidence; recorded, no engine mutation opened |

---

## 8. Comparison dimensions, facts only

| Dimension | XMage | Forge |
|---|---|---|
| Protocol handshake (AF01) | FAIL | PASS |
| External discretionary decisions bound to engine-offered options | PASS (4 PASS rows) | PASS (4 PASS rows) |
| Player cardinality 2P/3P/4P/5P (AF02) | PASS | PASS |
| Bounded 6P | attempted, not separately credited | attempted, not separately credited |
| Commander deck legality at import (AF03) | PASS | **PASS** (repaired on PR #5 head `e15f37d6`) |
| Principal-scoped hidden information | **PASS — established on the successor run** (`PRINCIPAL_SCOPED`, four distinct requesters, content-only distinctness; the sealed WSR22 artifact was a demonstrated defect and is recorded as history) | **PASS — established** (`PRINCIPAL_SCOPED`, four requesters, content-only distinctness) |
| Rules RNG control (AF09) | **ACKNOWLEDGED_ENGINE_SEED** — creation-transaction acknowledgement; no engine root-seed readback; twin rows keep AF09 `UNKNOWN` | **ACKNOWLEDGED_ENGINE_SEED** — create response acknowledges the engine-accepted root seed; twin rows keep AF09 `UNKNOWN` |
| Semantic replay | UNKNOWN | UNKNOWN |
| Actual-card runtime behaviour | UNKNOWN | UNKNOWN |
| Mid-game starting-state materialization | production-reachable lane exists (admission 12/30, runtime ledger 30/30 fresh); FULL107 still BLOCKED, 44 rows | BLOCKED, 44 rows (Lab execution-path gap on its declared seam) |
| Failure semantics | fail-closed on unknown messages and illegal actions | fail-closed, confirmed against a live game at event offset 17 |
| Process isolation | per-decision-process lane | clean-process twin exists Forge-side, unconsumed |
| Build provenance | handshake-reported, verified at AF00 | build-derived, verified at AF00 |
| Maintenance / integration burden | in-repo bridge, small surface | out-of-repo fork, GPL-3.0 derivative, 47 Rules-touching Lab commits |

Legal actions, priority, mana and cost payment, targets/modes/choices, stack,
triggers, replacement/prevention, continuous effects and layers, SBAs, zones,
copy/control, combat, command zone, commander tax, commander damage, Partner and
per-count multiplayer lifecycle are **not established for either candidate**: they
sit inside the `UNKNOWN` and `BLOCKED` rows (58 UNKNOWN / 44 BLOCKED on each
side).

---

## 9. What would change the verdict

1. A Coordinator ruling on PB-09, which determines whether the Forge column means
   anything as a candidate measurement and whether AF11's licence posture is
   recomputed for a GPL-3.0 derivative.
2. Done on this boundary for both candidates: the observing principal is marked
   and each generic-lane projection is `PRINCIPAL_SCOPED`. AF05 remains `UNKNOWN`
   only because the per-scenario hidden rows are unreachable on the generic
   surface.
3. Done on this boundary for both candidates at the creation transaction
   (`ACKNOWLEDGED_ENGINE_SEED`; Forge additionally exposes the engine's own root
   seed and call count). AF09 stays `UNKNOWN` on the clean-process replay twin
   rows.
4. Execution of the 29-card corpus under the actual-behaviour standard. This
   unblocks PB-07 and AF07.
5. For XMage the starting-state seam now exists as a production-reachable
   mid-game lane (admission 12/30, bound runtime ledger 30/30 fresh); the
   remaining work is converting reachability into exact semantic-obligation
   credit, which the PB-03 record model does not grant and must not fake.
   Forge needs the Lab to exercise the seam the candidate declares. Either way
   this unblocks the 44 `BLOCKED` rows and AF08 only with real obligation
   credit.

**Attribution is per candidate, and the PB-03 work split it accordingly.**
`AF01_FORGE.json` reports `starting_state_injection_supported: true` and
`scenario_injection_supported: true`, while `AF01_XMAGE.json` still reports
`starting_state_injection_supported: false` on the generic lane. That coarse bit
is deliberately not flipped: the XMage starting-state capability is published per
dimension through `full_game_lane.state_restoration_dimensions` and consumed by
the mid-game lane, so the global claim stays false while the itemized claim is
measured. Forge's 44 `BLOCKED` rows remain a **Lab execution-path gap** — the
candidate declares the capability and this run did not exercise the seam.

Consequence for remediation: Closing Forge's rows is Lab work, and this packet no
longer rules it out.

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
hidden rows, the clean-process replay twin rows, the AF11 policy question, and
AF04–AF09 for at least one candidate on both sides. The requester binding on
both candidates, the seed acknowledgement on both candidates, and the PB-03
starting-state seam on XMage are no longer among them; the PB-03 rows remain
uncredited until exact semantic-obligation bindings exist.

`PROVIDER_SELECTION_READY = NO`.

`ARCHITECTURE_FREEZE_READY_FOR_COORDINATOR = NO`.

`PRODUCTION_PROVIDER = NOT SELECTED`. `ARCHITECTURE_FREEZE = NOT CLAIMED`.
