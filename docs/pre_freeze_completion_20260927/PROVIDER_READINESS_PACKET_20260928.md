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
| Forge bridge / evidence head | `moeendres-png/forge@d5bd22d1bf3c5cf7f98f768fdbb59f0ba841c3fa`, tree `575cbbd6de274036944ea7bd8d5c6ccb7fd55fc9`, PR #4, Draft, deliberately not merged to Forge master |
| Forge Lab bridge-source pin of record | `4753bb7c72ea60d653121e0bab989077b4009f9c` |
| Upstream Forge baseline (`UPSTREAM_FORGE_BASELINE`) | `Card-Forge/forge@a37a865a53280dd8ad6fad3384d69611e8c5a42f` — ancestry only, **not** verified pristine, upstream behaviour **not** observed |

The Forge Rules Core, the Forge bridge/evidence head, the Lab bridge-source pin
and the upstream baseline are four distinct commits. None is collapsed into a
single "Forge SHA", and no result observed on one is reported as evidence for
another.

**Measured, not assumed.** PR #4 head `d5bd22d1` is 22 commits above the
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
| `native-forge-direct.json` | forge | direct | 150 | 150 | `d5bd22d1bf3c` | `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL` |
| `native-forge-mechanism.json` | forge | mechanism | 67 | 67 | `d5bd22d1bf3c` | `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL` |
| `native-xmage-direct.json` | xmage | direct | 34 | 34 | Lab `1c8de8e3` | `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT` |
| `native-xmage-mechanism.json` | xmage | mechanism | 135 | 135 | Lab `1c8de8e3` | `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT` |

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
| XMage | 4 | 0 | 59 | 44 | 0 | 0 | 0 | **107** |
| Forge | 4 | 0 | 59 | 44 | 0 | 0 | 0 | **107** |

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
| AF03 RULES_AUTHORITY | **PASS** | **FAIL** |
| AF04 LEGAL_ACTION_AND_DECISION_BOUNDARY | **FAIL** | UNKNOWN |
| AF05 HIDDEN_INFORMATION | UNKNOWN | UNKNOWN |
| AF06 GENERAL_RULES_CORRECTNESS | UNKNOWN | UNKNOWN |
| AF07 ACTUAL_CARD_BEHAVIOR | UNKNOWN | UNKNOWN |
| AF08 MULTIPLAYER_COMMANDER | UNKNOWN | UNKNOWN |
| AF09 RNG_REPLAY | UNKNOWN | UNKNOWN |
| AF10 RUNTIME_EVIDENCE_RELIABILITY | **PASS** | **PASS** |
| AF11 INTEROP_LICENSE_TOPOLOGY | **FAIL** | **FAIL** |

Every verdict is derived from an observation. No gate carries a historical
auto-PASS. AF03, AF04, AF05, AF06, AF07, AF08, AF09 and AF11 are not established
for either candidate, which is why no provider ranking is possible.

---

## 6. Decision-critical findings

### 6.1 Forge accepts an illegal Commander deck — `AF03` FAIL, not masked

The real negative deck-import probe shows the executed Forge bridge **accepted**:

- a deck whose commander is `Hill Giant`, a real card that is not a legal Commander;
- a deck whose colour identity violates its commander (`Black Lotus` x99 under
  `Isamaru, Hound of Konda`, which is `{W}{W}`).

CR 2.3 and the Commander format require both refusals. The same probe confirms
Forge *does* refuse an unknown card name, a short mainboard and an empty mainboard,
so this is a specific gap in Commander-legality enforcement rather than a broken
import path. Recorded, not repaired in the Lab: masking it in the harness and
awarding the gate would be a second source of legality.

### 6.2 Hidden information differs by candidate, and only one is a demonstrated leak

The two candidates are **not** in the same state, and an earlier revision of this
packet said they were. It accused Forge of a content leak that Forge does not
commit. The corrected reading:

**XMage — demonstrated engine defect.** `get_game_state` on the generic B4-D lane
returns **byte-identical** state to every observer: one distinct state view across
four different requesters, containing, for all four seats, the real `player_id`,
the hand card object ids and the library contents. Because the requester differs
while the payload does not, each caller necessarily sees every other seat's cards.
Attribution `ENGINE_CANDIDATE_DEFECT`.

**Forge — unestablished, not defective.** The Forge bridge redacts correctly: it
returns **four distinct** state views, the requesting seat's real card names and
`"<hidden>"` for every opponent card. That is proper redaction. What Forge does
*not* do is mark the observing principal, so the Lab cannot confirm from the
response alone which seat was the requester's. Attribution is
`SCOPING_NOT_ESTABLISHED_ACTOR_MARKING_ABSENT`, and AF05 stays `UNKNOWN` for Forge
rather than reporting a confirmed engine failure.

The distinction matters in both directions. A redaction placeholder is the
*absence* of content, and counting a placeholder array as exposed hand content
manufactures an accusation. Conversely, an undemonstrated leak must never be
asserted: without actor marking, content on a seat that is not known to be the
requester's may be the requester's own.

The Lab does not mask the XMage finding and the hidden-information gate earns no
credit on either candidate. The full-game lane uses a different protocol and is
properly scoped through `XmageFullGameStateRedactor`, which this workstream
repaired to emit seat-derived opaque tokens for every non-viewer principal.

### 6.3 Rules RNG is uncontrolled on both candidates

Both artifacts record `UNCONTROLLED_ENGINE_RNG`, `controlled: false`,
`rng_credit: false`, `acknowledged_seed: null`. The generic B4-D lane reports
`seed_supported: false`, so no seed is sent and none is acknowledged. The earlier
literal `engine_owned: true` no longer appears in any production source or artifact.
AF09 cannot be established for either candidate as a result.

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

The Forge-side ceiling recorded on Forge PR #4 is 28 runtime-qualified with one
documented engine gap, `Find // Finality` (the Aftermath back-half legal ability
discovery). That 28/29 is Forge-local and is **not** consumed as Lab credit here.

### 6.5 Both denominators are shaped by Lab work

PB-03 showed the XMage column is shaped by a Lab harness shortcut; PB-09 shows the
Forge column is shaped by Lab engine modification. Neither column is a clean
candidate measurement. This is recorded rather than resolved, because which
artifact is the Forge candidate is a Coordinator provider decision.

---

## 7. Blocker register

| Blocker | Side | Status after this workstream | Basis |
|---|---|---|---|
| PB-03 starting-state classification | both | **RESOLVED** (mechanism); block attribution now per candidate | mechanism-based classifier, split measured exact against the effective materialization, no fixture-id prefix, 107-row denominator preserved. Block attribution reads each candidate's own declared capability: Forge declares the seam, so its 44 rows are a Lab execution-path gap, not a Forge capability gap |
| PB-05 build provenance | forge | **RESOLVED** | Forge PR #4 repairs the fail-open paths; `verify_pb05_provenance` consumes build commit/tree/dirty/source/verified independently of the provider's self-assessment; Forge AF00 `PASS` |
| PB-06 per-scenario hidden channels | both | **BLOCKED** | no principal-scoped observation is credible. XMage's generic lane returns one shared state view to every observer (a demonstrated leak); Forge redacts but does not mark the observing principal, so scoping cannot be established either way. No per-scenario channel was executed (§6.2) |
| PB-07 effective 29-card corpus | both | **BLOCKED** | 12 declared of 29 required, `CARD_02` `UNKNOWN`. Completion is derived from behaviourally executed cards, so naming 29 cards cannot advertise a complete corpus (§6.4) |
| PB-08 clean-process replay twin | both | **BLOCKED** | Rules RNG is uncontrolled on both candidates, so a same-seed twin proves nothing |
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
| Commander deck legality at import (AF03) | PASS | **FAIL** |
| Principal-scoped hidden information | **FAIL — demonstrated engine defect** | **UNKNOWN — redacted correctly, scoping unestablished** |
| Rules RNG control (AF09) | **UNCONTROLLED** | **UNCONTROLLED** |
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
sit inside the 59 `UNKNOWN` and 44 `BLOCKED` rows.

---

## 9. What would change the verdict

1. A Coordinator ruling on PB-09, which determines whether the Forge column means
   anything as a candidate measurement and whether AF11's licence posture is
   recomputed for a GPL-3.0 derivative.
2. A principal-scoped observation surface for the generic lane, or a decision to
   qualify the full-game lane only. XMage additionally needs its projection fixed;
   Forge needs the observing principal marked so its correct redaction can be
   verified rather than merely trusted. This unblocks PB-06 and AF05.
3. A seed-capable generic lane, or an engine-level RNG binding. This unblocks
   PB-08 and AF09.
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

`DECISION_CRITICAL_UNKNOWN_REMAINS = YES` — PB-09, PB-06, PB-07, PB-08, plus
AF04–AF09 for at least one candidate on both sides.

`PROVIDER_SELECTION_READY = NO`.

`ARCHITECTURE_FREEZE_READY_FOR_COORDINATOR = NO`.

`PRODUCTION_PROVIDER = NOT SELECTED`. `ARCHITECTURE_FREEZE = NOT CLAIMED`.
