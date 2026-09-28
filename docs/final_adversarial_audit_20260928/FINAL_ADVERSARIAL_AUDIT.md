# FINAL ADVERSARIAL AUDIT — DeepSeek Independent Lab

Date: 2026-09-28
Auditor identity: DeepSeek V4.1 Flash MAX (independent DeepSeek lab)
Posture: adversarial falsification + independent bounded engineering

## Source Lock

| Item | Value |
| --- | --- |
| Commander-Lab main at audit | `3910040b3ca4eb276f8895fa4c9801af3550f123`, tree `a28d98b29c84342056e5658f8f4423f927999108` |
| Lab PR #286 | MERGED at `3910040b`; head `5ed07d23`; CI terminal green |
| Lab PR #282 / #283 / #280 | merged into main before this audit |
| Forge Rules Core | `moeendres-png/forge@ef958ee91ac6c9ce0152189f2654bf6e05abf273`, tree `fc3387bf37aab19d780b2939a235309ed32b0492` |
| Forge bridge/evidence | `e15f37d6b2b5c0ad682948f86f037e07b6aaded5` (PR #5, DRAFT, deliberately unmerged) |
| XMage candidate | `moeendres-png/mage@b19596980f2734496ea1896504253e1bdd2756dd` |
| DeepSeek independent Forge branch | `deepseek/finality-aftermath-20260928` @ `52cfd9a24ba` (based on the Rules Core `ef958ee9`) |
| DeepSeek audit branch | `docs/final-adversarial-audit-20260928` (docs-only) |
| Space Bunny | `sbmax/full-completion` PR #285 OPEN, head `b4ea7751`; 2096 files changed, not reviewed in depth (mid-flight, mass convergence) |
| Sol salvage | `sol/final-integration-salvage-20260928` @ `a1e233ca`, read-only |

## PASS Claims Challenged

### 1. Forge AF03 (illegal Commander deck refused by Rules Core)

- Claim: `AF03_FORGE.json` PASS; `deck_not_legal` from `DeckFormat.Commander.getDeckConformanceProblem`, distinct from `deck_import_failed`.
- Falsification attempt: could the refusal come from the bridge's own shape guards (commander count / 100-card check) rather than Commander legality? Probes are 1 commander + 99 cards = 100, so shape guards pass. Non-commander probe message is `has an illegal commander` (DeckFormat line), colour probe message is `do not match the commanders color identity:` with `Shivan Reef` (non-basic, non-legendary, so singleton/size/copy rules cannot be the cause). Unknown card and size failures are `deck_import_failed`, not `deck_not_legal`. No bridge string duplicates the legality messages; the bridge delegates.
- Result: **SURVIVES** (DIRECTLY_VERIFIED).

### 2. Forge principal scoping (`HIDDEN_INFO_FORGE.json`)

- Claim: `PRINCIPAL_SCOPED`, attribution `NONE`, 4 established requesters, `distinct_state_views = 4`.
- Falsification attempt (independent recomputation): stripped every binding field (`observer_player_id`, `observer_engine_player_id`, `observer_seat`, `is_actor`, offset) from the four observation states and canonicalized; the content still differs 4 ways, and the difference is exactly the requester's own hand (`p1` sees 7 Plains on seat 0, `p4` sees 7 Plains on seat 3; every other hand is `<hidden>`). Library counts are identical public `92` everywhere, no order exposed. Exactly one `is_actor` per view at the requesting seat.
- Marker-only fabrication attempt: pinned by `test_binding_metadata_alone_cannot_fabricate_distinct_views` (one identical content view with every binding field varied must yield `distinct = 1`), and `_BINDING_STATE_KEYS` excludes the envelope fields from the content view.
- Result: **SURVIVES** (DIRECTLY_VERIFIED).

### 3. Forge creation-seed acknowledgement

- Claim: `RNG_REPLAY_FORGE.json` `ACKNOWLEDGED_ENGINE_SEED`, source `create_commander_game_response`, `rng_credit: true`.
- Falsification attempt: is the acknowledgement a request echo? The bridge installs the seed and reports `MyRandom.getRootSeed()/isExplicitSeed()`; the readback is verified against the session seed and throws on divergence; the create transaction fails closed with `SEED_UNSUPPORTED` and registers no session. Negative controls exist (reject, mismatch) and unseeded launches clear a stale binding. The Lab classifies only from the acknowledged value.
- Result: **SURVIVES for the creation acknowledgement** (DIRECTLY_VERIFIED). The clean-process twin half is NOT proven; AF09 stays UNKNOWN.

### 4. START-2 (`WS05-CMD-START-2`)

- Claim: PASS on CR 103.8a semantics.
- Falsification attempt: requested values must not be presented as observed. Persisted guard inputs: `observed_decision_kinds = [STARTING_PLAYER, MULLIGAN, MULLIGAN, PRIORITY]`, `observed_draw_semantic_events = []`, `observed_starting_actor = p1`, `draw_step_decision_frames = []`, `draw_step_decision_exposed = false`, `priority_reached = true`, `observed_actor_zone_counts = [{seat 0, hand 7, library 92, STATE_ACTOR_MARKER}]`. The counts come from the marked principal's `zones.hand` / `zones.library_size`; the tape shows the real decision sequence. No requested-state value is stored as evidence.
- Caveat: the row has no before/after count baseline, so "counts unchanged" is corroborated but not differentially measured; the PASS reason does not claim it.
- Result: **SURVIVES** (DIRECTLY_VERIFIED), with the baseline gap recorded as P3.

### 5. Native-suite credit

- Claim: forge direct 150/150, mechanism 67/67 at `e15f37d6`.
- Falsification attempt: cross-candidate contamination? Receipts are per-candidate (`candidate=forge`, `executed_commit=e15f37d6`, `candidate_commit=ef958ee9`, proof `RULES_CORE_MAIN_SOURCE_TREES_IDENTICAL`); the XMage receipts remain separately present with `ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT`; `native_suite_credit` filters by candidate and requires the engine-identity proof. No other candidate's suite is copied into the Forge document. Git-less exports earn no source-bound credit by construction (`ENGINE_NOT_A_SEPARATE_GIT_CHECKOUT`).
- Finding: `NATIVE_SUITE_RECEIPTS.json` currently indexes only the two Forge receipts (`receipt_count: 2`) because the native stage is candidate-scoped. The per-candidate receipt files remain and the assembler reads the directory, so credit is unaffected; a reader of the index alone could misread it. P3.
- Result: **SURVIVES** (DIRECTLY_VERIFIED).

### 6. PB-07 Forge "28/29"

- Claim: Forge-side `PB07_EVIDENCE.json` `RUNTIME_QUALIFIED: 28`, one engine gap.
- Falsification attempt: the artifact's own `global_verdict` is `PARTIAL (Forge-side preparation only; PB-07 global closure NOT claimed)`. It is a Forge-side self-assessment, not on canonical Lab main, and the Lab's current-boundary `ACTUAL_CARD_FORGE.json` is import/construction evidence over 12 imported names, not the 29-card behavioral denominator.
- Result: **DOES NOT SURVIVE as current-boundary credit**. It is a valid candidate-side input; PB-07 remains BLOCKED for Lab credit. P2.

## AF11 Technical Topology

| Dimension | Forge | XMage |
| --- | --- | --- |
| Engine repository | `moeendres-png/forge` (fork) | `moeendres-png/mage` (fork) |
| Engine commit | `ef958ee9` (tree `fc3387bf`) | `b1959698` |
| Engine license | GPL-3.0 (`LICENSE` file present at the fork root) | MIT (upstream Mage); exact license file in the candidate checkout not re-verified here |
| Bridge location | same repository, module `forge-protocol2-bridge` | Lab repository, module `engine-bridge` (`org.commanderlab.xmage`) |
| Bridge license | inherits Forge GPL-3.0 (same repo) | Lab code (no top-level Lab LICENSE file found) |
| Link relationship to engine | compiled in the same Maven reactor against `forge-core`/`forge-game`/`forge-gui` jars | compiled against published `org.mage:mage:1.4.61` (+ `mage-deck-constructed`, `mage-game-commanderfreeforall`); no `<repositories>` entry in the poms, so resolution is from the local Maven repository/settings |
| Runtime topology | separate JVM process: `java -cp forge-protocol2-bridge/target/classes:<deps> forge.bridge.BridgeMain` | separate JVM process: `java -cp engine-bridge/target/classes:<deps> org.commanderlab.xmage.Main` |
| Transport | JSONL over stdin/stdout (Protocol 2.0.0) | JSONL over stdin/stdout (Protocol 2.0.0) |
| Engine source copied into Lab | no | no (engine consumed as binary artifacts) |
| Engine binary distribution | modified Forge build produced in the candidate worktree | Mage jars consumed from the local repository |
| Same process/artifact as Lab | no | no |
| Dynamic link between Lab and engine | none (IPC only) | none (IPC only) |

Machine-readable form: `FINAL_ADVERSARIAL_AUDIT.json` → `af11_technical_topology`.

## AF11 Remaining Legal Questions

No legal conclusion is asserted. Classifications: DIRECTLY_VERIFIED (files/pins/poms above), TECHNICAL_FACT (topology), LEGAL_INTERPRETATION_REQUIRED (below).

1. If the Production architecture ships modified Forge GPL-3.0 binaries (or a jar built from the fork) alongside a separately communicating Commander-Lab process, what source-offer and notice obligations attach to the shipped package, and does the Lab's JSONL-only IPC keep the Lab outside the GPL combined-work boundary?
2. The Lab repository has no top-level LICENSE file. What license/notice must the Lab distribution carry for its own code and for the bundled/consumed engine artifacts?
3. XMage MIT attribution: what notice set must accompany a distribution that embeds the Mage jars transitively (deck-constructed, commander-free-for-all)?
4. Does distributing a modified Forge build as a container image with source fetched at build time change the source-offer mechanics compared to shipping binaries?

## PB-07 Receipt Map (29 rows)

Source: Forge-side `wsr24-evidence-closure/PB07_EVIDENCE.json` (read-only, not canonical main) plus the Lab
`ACTUAL_CARD_DOMAIN_v1.json#regression_corpus_29` denominator. Dispositions are the auditor's, based on
the recorded evidence class and candidate identity; no row is promoted.

| # | Card | Claimed obligation | Recorded evidence | Evidence class | Reuse disposition |
| --- | --- | --- | --- | --- | --- |
| 1 | Ishai, Ojutai Dragonspeaker | trigger counter on opponent cast | probe: +1/+1 counter | runtime | REQUIRES_TARGETED_RERUN (bridge head pin) |
| 2 | Rograkh, Son of Rohgahh | cast + commander tax | BridgeEngineTest + fixtures | runtime | REQUIRES_TARGETED_RERUN |
| 3 | Esior, Wardwing Familiar | hardcast + flying + evasion | probe | runtime | REQUIRES_TARGETED_RERUN |
| 4 | Kediss, Emberclaw Familiar | damage propagation | WsR10KedissBridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |
| 5 | Veyran, Voice of Duality | magecraft doubling | WS236F4BridgeTest + WS234 | runtime | REQUIRES_TARGETED_RERUN |
| 6 | Harmonic Prodigy | trigger doubling | WS236F4BridgeTest | runtime | REQUIRES_TARGETED_RERUN |
| 7 | Narset, Parter of Veils | static + loyalty | probe | runtime | REQUIRES_TARGETED_RERUN |
| 8 | Jeska, Thrice Reborn | loyalty cost shape | WsR11JeskaBridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |
| 9 | Magma Opus | split/cleave-style cast | WsR10MagmaBridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |
| 10 | Wash Away | cleave variant | probe | runtime | REQUIRES_TARGETED_RERUN |
| 11 | Wear // Tear | fuse | WsR11FuseBridgeFamilyTest | runtime | REUSABLE (no engine change) |
| 12 | Dig Through Time | delve + look/select | probe | runtime | REQUIRES_TARGETED_RERUN |
| 13 | Flare of Duplication | retarget | WsR9RetargetBridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |
| 14 | Vandalblast | overload variants | probe | runtime | REQUIRES_TARGETED_RERUN |
| 15 | Finale of Revelation | X spell | WsR9FinaleX10BridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |
| 16 | Psychosis Crawler | draw drain | probe | runtime | REQUIRES_TARGETED_RERUN |
| 17 | Kaervek the Merciless | targeted burn | probe | runtime | REQUIRES_TARGETED_RERUN |
| 18 | Shriekmaw | ETB + evoke | probe | runtime | REQUIRES_TARGETED_RERUN |
| 19 | Butcher of Malakir | sacrifice trigger | probe | runtime | REQUIRES_TARGETED_RERUN |
| 20 | Syphon Mind | multiplayer discard | probe | runtime | REQUIRES_TARGETED_RERUN |
| 21 | Gratuitous Violence | combat doubling | probe | runtime | REQUIRES_TARGETED_RERUN |
| 22 | Bolt Bend | retarget | WsR9RetargetBridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |
| 23 | Makeshift Mannequin | reanimate + counter | probe | runtime | REQUIRES_TARGETED_RERUN |
| 24 | Warstorm Surge | entry damage | probe | runtime | REQUIRES_TARGETED_RERUN |
| 25 | Basilisk Collar | equip + keywords | probe | runtime | REQUIRES_TARGETED_RERUN |
| 26 | Burn Down the House | modal devils | probe | runtime | REQUIRES_TARGETED_RERUN |
| 27 | Path of Ancestry | mana + scry | WsR13PathBridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |
| 28 | Find // Finality | aftermath half | front-half runtime; aftermath enumeration gap | runtime (front only) | REQUIRES_TARGETED_RERUN, now remediable (see Aftermath) |
| 29 | Boseiju Reaches Skyward // Branch of Boseiju | saga + channel | WsR11BoseijuBridgeFamilyTest | runtime | REQUIRES_TARGETED_RERUN |

All 29 dispositions require a targeted rerun against a single pinned bridge/evidence head before they can be
Lab credit; the evidence lives on a Forge branch, not on canonical Lab main, and no source-lock binding to the
Lab current boundary exists for it.

## Aftermath Root Cause (Find // Finality)

- Exact root cause: `Card.getAllPossibleAbilities` iterated only `getSpellAbilities()` (the current state).
  Once a split card holds the front half's state (`LeftSplit`, which is the state after the front half is
  cast), the `RightSplit` state's Aftermath SA is never added. In the graveyard the front half is correctly
  filtered by its own zone gate, so the enumeration returned `[]` even though the right half is legal there.
- Independent reproduction: fixture with `currentState=LeftSplit`, `currentAbilities=1`,
  `alternate=RightSplit`, `alternateAbilities=1` → `getAllPossibleAbilities(p1, true)` returned `[]`.
- Smallest systemic seam: add the alternate state's spells in `getAllPossibleAbilities` and let the existing
  playability filter decide; zone legality stays in the ability's own restriction.
- Implemented and pushed: `deepseek/finality-aftermath-20260928` @ `52cfd9a24ba`
  (`forge-game/.../Card.java` + `DeepseekAftermathDiscoveryTest`).
- Evidence: fail-before 3/6 (empty graveyard enumeration), fix-after 6/6 with
  `after=true spell=true zone=Graveyard`; desktop suite 456 tests 0 failures; bridge suite 213 tests 0 failures.
- Blast radius: every `getAllPossibleAbilities` consumer (AI, GUI, bridge); mitigations are the existing
  playability filter plus the full desktop and bridge suites. No card-name or zone special case.
- Release/provider-decision criticality: this was PB-07's last Forge card gap; the fix makes the 29th card
  enumerable. It does not by itself close PB-07 (the Lab must rerun the actual-card evidence at a pinned head).

## Readiness Blind-Spot Matrix

| Domain | Required observable | Current evidence source | Strongest classification | Known gap | False-positive shape | Remaining work |
| --- | --- | --- | --- | --- | --- | --- |
| Legal Actions | engine-offered options, actor-scoped | bridge acting-frame enumeration; AF04 UNKNOWN | CODE_DERIVED | only acting-frame surface; AF04 unestablished | fixture-scripted options mistaken for engine options | enumerate all decision classes at pinned heads |
| Decision Identity | revision/id + rejection semantics | START-2 tape, bridge tests | DIRECTLY_VERIFIED | AF04 row-level unestablished | accepted stale revision | decision-family matrix |
| Priority | real priority passes | PLAYER_COUNT rows, bridge tests | DIRECTLY_VERIFIED | full priority cycles not measured | pass inferred from silence | priority micro-rules |
| Stack | stack state, responses | family tests | CODE_DERIVED | no stack-denominator row | resolved stack read as empty | micro-rules |
| Costs | cost payment, reductions | Cleave/delve/overload probes | DIRECTLY_VERIFIED (spot) | not systematic | option offered but unpayable | cost micro-rules |
| Mana | pool + payment framing | engine-bridge tests, mana-payment probes | DIRECTLY_VERIFIED (spot) | partial | auto-pay assumed | mana micro-rules |
| Targets | legal target sets | retarget/target probes | DIRECTLY_VERIFIED (spot) | not systematic | target list from fixture | target-family matrix |
| Modes | modal choices | Burn Down the House, Vandalblast | DIRECTLY_VERIFIED (spot) | partial | default mode assumed | modes matrix |
| Choices | optional yes/no | probes | DIRECTLY_VERIFIED (spot) | partial | optional skipped | choice-family matrix |
| Triggers | trigger events | family tests (Kediss, Kaervek, etc.) | DIRECTLY_VERIFIED (spot) | partial | event count mistaken for behavior | trigger-family matrix |
| Replacement | replacement effects | WS234 Aftermath exile replacement | DIRECTLY_VERIFIED (spot) | narrow | replacement untested per family | micro-rules |
| Prevention | prevention shields | none current | UNKNOWN | full | damage zero attributed to prevention | micro-rules |
| Continuous Effects | static buffs/debuffs | Gratuitous Violence probe | DIRECTLY_VERIFIED (spot) | narrow | layer ordering unobserved | micro-rules |
| Layers | dependency ordering | none current | UNKNOWN | full | outcome correct by coincidence | micro-rules |
| SBAs | state-based actions | bridge tests (battlefield cleanup) | CODE_DERIVED | partial | SBA attributed to action | micro-rules |
| Zones | zone transitions | START-2, exile replacement | DIRECTLY_VERIFIED (spot) | partial | zone read before move | micro-rules |
| Copy | copy effects | AF rows UNKNOWN | UNKNOWN | full | copied object treated as original | micro-rules |
| Control | control changes | HIDDEN_12 test (Mindslaver shape) | DIRECTLY_VERIFIED (spot) | narrow | controller from owner | micro-rules |
| Combat | combat steps/damage | Gratuitous Violence, combat tests | DIRECTLY_VERIFIED (spot) | partial | damage attributed to wrong source | micro-rules |
| Command Zone | commander placement/move | commander tests | DIRECTLY_VERIFIED (spot) | partial | command zone as exile | micro-rules |
| Commander Tax | cast-count tax | Rograkh, commander cast tests | DIRECTLY_VERIFIED (spot) | partial | tax applied once | tax matrix |
| Commander Damage | tracked per commander | commander damage tests | DIRECTLY_VERIFIED (spot) | partial | aggregate damage | damage matrix |
| Partner | partner pairing | pods import; lifecycle unqualified | UNKNOWN | pairing/bloodline rules | two commanders accepted without partner check | partner matrix |
| Mulligan | keep/bottom | START-2 tape, mulligan tests | DIRECTLY_VERIFIED (spot) | bottoming not fully covered | keep-all assumed | mulligan matrix |
| Start Rules | first-player draw skip | START-2 PASS | DIRECTLY_VERIFIED | no count baseline | fixture obligation as evidence | baseline counts |
| 2P / 3P / 4P / 5P | real lifecycles | PLAYER_COUNT_2P..5P PASS | DIRECTLY_VERIFIED | depth limited | one decision per row | deepen lifecycle rows |
| 6P bounded | 6-player lifecycle | cardinality tests | CODE_DERIVED | not credited | 4P does not establish 6P | 6P row |
| Hidden Information | principal-scoped observation | HIDDEN_INFO_FORGE PASS; XMage #283 | DIRECTLY_VERIFIED (generic) | full scenario denominator | marker-only distinctness; placeholder counted as content | PB-06 scenario run |
| Rules RNG | engine-accepted seed | RNG_REPLAY_FORGE ACKNOWLEDGED_ENGINE_SEED | DIRECTLY_VERIFIED (creation) | clean-process twin | request echo as acknowledgement | twin runs |
| Semantic Replay | deterministic replay from tape | REPLAY rows UNKNOWN | UNKNOWN | clean-process twins | structural replay | PB-08 |
| Actual-Card Behavior | behavior, not import | Lab artifact = import; Forge-side 28/29 | UNKNOWN (Lab credit) | denominator mismatch | import counted as behavior | pinned rerun (29) |
| Process Isolation | separate processes, IPC | bridge/engine launched as separate JVMs | DIRECTLY_VERIFIED | no packaging test | same-JVM assumption | packaging topology test |
| Failure Semantics | fail closed on bad input | bridge rejection tests | DIRECTLY_VERIFIED | partial | silent skip | failure matrix |
| Evidence Integrity | receipts bound to execution | runner/native receipts; manifests resealed | DIRECTLY_VERIFIED | index scoping note | stale receipt reuse | index note |
| AF11 topology/license | exact topology + notices | this audit | TECHNICAL_FACT | legal questions | asserted compatibility | Coordinator legal questions |

## Findings

### P0

None.

### P1

1. **Aftermath alternate-half enumeration gap (fixed in the DeepSeek branch).**
   `Card.getAllPossibleAbilities` returned `[]` for a split card holding the front-half state in the
   graveyard. The PB-07 "FULL SUPPORTED" verdict for `Find // Finality` was reached without the enumeration
   surface, so the 28/29 claim rested on a gap that only the bridge probe exposed. Fix and evidence in
   `deepseek/finality-aftermath-20260928`.

### P2

2. **PB-07 Forge 28/29 is not canonical and not Lab credit.** The evidence is a Forge-side self-assessment
   on `PB07_EVIDENCE.json`, not on Lab main; the Lab's current-boundary actual-card artifact is
   import/construction evidence over 12 imported names. The 29-card denominator needs a pinned targeted rerun.
3. **XMage PB-06 generic-to-full gap.** The merged #283 code enforces explicit observer resolution within the
   addressed game and fails closed on unknown ids, and it redacts through one actor-view authority. The
   per-scenario denominator (temporary look, permission expiry, shuffle invalidation, controlled-player,
   mulligan bottoming, private choice payloads, error payloads) is not proven by this audit.

### P3

4. `NATIVE_SUITE_RECEIPTS.json` indexes only the candidate-scoped receipts (Forge, 2); the XMage receipt
   files coexist in the directory and the assembler reads them, but the index alone can be misread.
5. START-2 takes no before/after count baseline, so "counts unchanged" is corroborated but not
   differentially measured.
6. Commander-Lab has no top-level LICENSE file; AF11 questions 2-3 depend on that.

## Candidate-Specific Facts

- Forge: Rules-Core `ef958ee9`; bridge/evidence `e15f37d6`; AF03 PASS; generic principal scoping established;
  creation-seed acknowledgement engine-readback; START-2 PASS; native 150/150 + 67/67; PB-07 candidate-side
  28/29 with the 29th now made enumerable by the DeepSeek fix; AF04-AF09/AF11 open; GPL-3.0.
- XMage: `b1959698`; principal-scoping remediation merged (#283); explicit observer + envelope binding;
  generic `UNKNOWN` current-boundary rows remain; PB-06 full scenario coverage open; MIT upstream license.
- No ranking, no scoring, no provider preference is expressed.

## What Space Bunny Must Still Prove

- PB-03 starting-state transport and the formerly BLOCKED FULL107 rows for both candidates.
- PB-06 full scenario coverage for both candidates.
- PB-08 clean-process twins and semantic replay.
- PB-07 Lab-credit rerun at a pinned candidate head (the DeepSeek Aftermath fix is a candidate input).
- AF04-AF09 and AF11 closure for both candidates.
- Final semantic comparison and readiness packet.

## What Coordinator Must Adjudicate

1. Whether the Forge branch `deepseek/finality-aftermath-20260928` fix is integrated into the candidate line
   (it is independent of PR #5 and based on the Rules Core).
2. Whether the PB-07 denominator rerun consumes the Forge-side 28/29 evidence or requires fresh execution.
3. The four AF11 legal questions above.
4. Whether the XMage per-scenario PB-06 coverage is routed as its own workstream.

## Final Flags

- `DEEPSEEK_FINAL_AUDIT = COMPLETE`
- `PRODUCTION_CODE_MUTATED = YES` (isolated DeepSeek Forge branch only; no canonical/foreign surface touched)
- `PROVIDER_SELECTED = NO`
- `ARCHITECTURE_FREEZE = NOT CLAIMED`
- `DECISION_CRITICAL_FINDINGS = 3` (1 P1, 2 P2)
- `EXACT_NEXT_ACTION = Coordinator consumes audit alongside Space Bunny final handoff`

---

## Drift Refresh (post-audit checkpoint)

| Field | Value |
| --- | --- |
| LAST_REFRESHED_MAIN_SHA | `3910040b3ca4eb276f8895fa4c9801af3550f123` |
| LAST_REFRESHED_MAIN_TREE | `a28d98b29c84342056e5658f8f4423f927999108` |
| Main drift vs prior lock | NONE (same commit/tree) |
| Relevant merges since lock | none |
| Worktrees | audit `ecf673f4` clean; donor `52cfd9a24ba` clean |

Open dependencies (read-only, classification D):

- **#284** (Sol salvage / PB-03 integration writer, head `27644c2b`) — `WAIT_FOR_MERGE`. Overlaps the runner, `receipts.py`, `bridge_launcher.py` and the receipts test. Not raced, not cherry-picked.
- **#289** (Space Bunny final pre-Freeze, head `479c2ebb`) — `WAIT_FOR_MERGE`. On merge it changes the audit basis for XMage/START-2/packet surfaces; re-adjudicate then.
- **#288** (Astra junction rejection) — `NON_OVERLAPPING`.
- **#287** (this audit) — `OWN_DRAFT`, do not auto-merge.

Donor status: `deepseek/finality-aftermath-20260928` @ `52cfd9a24ba` = **DONOR_CANDIDATE**, not
integrated elsewhere. The Forge candidate relationship is unchanged: Rules Core `ef958ee9`,
bridge/evidence PR #5 head `e15f37d6` (still DRAFT).

Evidence impact: none on canonical main. The audit conclusions survive; PB-07 `LAB_CREDIT` remains
**0/29**; the Aftermath fix remains a candidate-side donor pending a pinned Lab rerun.

Exact next action: **WAIT_FOR_INTEGRATION** — re-adjudicate when #284/#289 merge, then run the
29-card denominator at the pinned candidate head with the Aftermath fix integrated.

---

## Successor Verification (2026-09-29 refresh)

Fresh state: canonical Lab main unchanged (`3910040b` / tree `a28d98b2`); Forge PR #5 unchanged
(`e15f37d6`, DRAFT). New open items: #290 (quarantine paths, NON_OVERLAPPING), #291 (Muse PB-03
dimension discriminator, NON_OVERLAPPING), #284 advanced to `46e971c0`, #289 advanced to `122e0eb7`.

**Donor status changed: `REUSE / INTEGRATED_ELSEWHERE`.** The Forge successor branch
`sol/final-candidate-successor-20260929` transplanted the DeepSeek Aftermath fix verbatim
(`49bcaed6517` engine, `6ea3d95357c` regression) and added a bridge-level Finality resolution
requirement (`6f70e32e810`). Do not duplicate the fix.

**New finding DS-07 (P1): the successor's added test is red at its own head.**
Independent verification in a detached read-only worktree at `6f70e32e810`:

- `mvn -o -pl forge-protocol2-bridge -am test -Dtest=WsR24Pb07MechanicProbesTest …`
  → **16 tests, 1 failure**: `testFindAndAftermath` → `unexpected COPY_CHOICE for p1`
  (`answerCommon:130` via `drainToResolution:227` at `testFindAndAftermath:676`), deterministic.
- Root cause: Finality's optional `PutCounter` (`Choices$ Creature.YouCtrl`, `ChoiceOptional$ True`)
  parks the engine's `chooseSingleEntityForEffect` decision; the bridge kinds it `COPY_CHOICE` and
  offers entity options plus a decline option. The test helper does not handle that kind, so the
  test can never reach its assertions.
- Validated minimal repair: 13 lines in `answerCommon` selecting the first entity option
  (`confirmValue == null`) on `COPY_CHOICE`. After the repair the class is **16/16 green** and the
  mapped assertions (Serra Angel survives 2 counters then -4/-4, Grizzly Bears dies, Finality is
  exiled) are reached. Unified diff captured at
  `/tmp/opencode/deepseek-successor-finality-harness-fix.patch`; not pushed to any foreign branch.

Product behavior is correct; the harness as committed is not. PB-07 Lab credit remains **0/29** and
still requires a pinned Lab runtime rerun after the successor line carries this repair.
