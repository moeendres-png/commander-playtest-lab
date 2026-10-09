# ADR: Rules-engine strategy — one production Rules Core with a bounded reference

Status: **Coordinator assessment and recommendation. The decision it asks for is Owner-only.**
`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED` ·
`PRODUCTION_REPOSITORY = NOT_CREATED`. This record selects no provider and claims no Freeze
(AGENTS.md §8). It changes no pin, no denominator, no contract and no qualification gate.

Question: which Rules-engine strategy reaches a full-rules, reproducible, four-player Commander
simulator with the least total engineering effort — one engine, two production engines, or one
engine with a bounded reference?

## 1. Source lock (2026-10-09)

| Item | Value |
| --- | --- |
| Lab `main` | `b2e4acbc6` (tree `43f29c0e`), after #643 (contract 1.0.30) and #644 |
| XMage pin | `b479fe74fd1eaf899ff16c6a9203e74a91c0f339` on `moeendres-png/mage` (MIT) |
| Forge pin | Rules Core `bb0a740d` / bridge `31cbae12` on `moeendres-png/forge` (GPL-3.0); R-1 candidate identity |
| Lab licence | `LicenseRef-Proprietary` (`pyproject.toml`) |
| Last sealed epoch | `ff688b58359f-42c21a3659cd` (contract 1.0.24) |
| Latest PB-03 (PR head, **unsealed**) | run 37914716200 on `9a248fad` (= #643 head, contract 1.0.30) |
| Governing decisions | R-1…R-4 (`docs/coordinator_adjudication_20260930/ADJUDICATION.md`, Owner-accepted 2026-09-30); R-5 is a Coordinator finding, not a ruling (ADJUDICATION.md:16); the all-PASS eligibility rule of `architecture_freeze_contract_v2`; AGENTS.md §1 (single Rules authority after Freeze), §8 (Owner-only reservations) |

R-1 fixes the Forge candidate identity (the Lab fork, not pristine upstream). R-2 approves the
decision-identity shim. R-3 requires AF01 on one lane. R-4 requires direct execution, so adjacent
evidence earns no credit. The all-PASS rule of `architecture_freeze_contract_v2` (restated in
finding R-5) makes a candidate eligible only when all its gates PASS. AF11 is sequenced after
selection (ADJUDICATION.md:113). A difference in counts is never the selection criterion. This
ADR respects all of this. It compares strategies and total cost, which the rule leaves to the
Owner's selection.

## 2. Evidence

Each claim names its source. Measured facts are marked M, estimates E, unknowns U.

### 2.1 Qualification state

| Gate | XMage sealed ff688b58 | XMage PR-head 37914716200 (unsealed) | Forge (both) |
| --- | --- | --- | --- |
| FULL107 | 106 PASS / 1 UNKNOWN | **107 PASS** | 20 PASS / 33 BLOCKED / 54 UNKNOWN |
| AF00–AF04, AF08, AF10 | PASS | PASS | AF00–AF04, AF10 PASS; AF08 UNKNOWN |
| AF05 hidden information | PASS | PASS | UNKNOWN (20 rows) |
| AF06 rules correctness | UNKNOWN (1 row) | **PASS** | UNKNOWN |
| AF07 actual cards | PASS | **UNKNOWN** (see 2.3) | UNKNOWN |
| AF09 RNG / replay | PASS | PASS | UNKNOWN (5 rows) |
| AF11 interop / licence topology | UNKNOWN | UNKNOWN | UNKNOWN |

(M: the packets read by `pb03_packet.py`.) The PR-head result is not credit until a sealed epoch on
`main` reproduces it (§4: `LOCAL_OBSERVED`/PR-head evidence ≠ sealed credit).

### 2.2 What the gaps are, by class

- **No Rules divergence has been established for either engine.** All 107 comparison rows are
  `NON_COMPARABLE` (0 `SAME_SEMANTICS`, 0 adjudicated differences) (M, sealed
  `CURRENT_BOUNDARY_COMPARISON.json`). The evidence measures integration depth, not Rules quality.
  Forge's lower count is **not** evidence that its Rules Core is worse.
- **Forge's 87 non-PASS rows** (M, sealed packet, grouped by leading reason):
  - 55 are fixtures corrected by later contracts and not re-executed;
  - 23 are `LAB_EXECUTION_GAP`;
  - 5 are `PROVIDER_ADAPTER_GAP`;
  - 4 others.

  Counted across all named missing mechanisms, **36 rows need Forge-side adapter work**, e.g. no
  event-log export or no card owner in the readback. These rows are owned by #592 wave 2.
- **Forge FULL107 has not moved across the last epochs.** It stood at 20/33/54 in epoch
  `b1c8f54a`, in `ff688b58` and in both 1.0.30 PR-head runs (M). Over the same seam XMage went
  from 14 PASS (the #411 run, R-5 table) to 106 (sealed `ff688b58`). The unsealed PR-head run
  37914716200 shows 107 (M).
- **XMage's recent failures were Lab defects, not engine defects.** The XMage regressions of
  the 1.0.28–1.0.30 cycle traced to:
  - records that did not declare a player's choice (arrival history, mana sources, attack sets);
  - one Lab lane observation-scope defect: the AF05 transport leak, where a principal-neutral
    arrival readback landed on the principal tape (#643).

  No engine defect was involved (M, #643/#645 trace diffs).
- **Rules-Core repairs made by the Lab** (M):
  - XMage fork: 2 Lab merges up to the pin (#33 leaver trigger order, #41 priority after
    state-based elimination);
  - Forge fork: 4 Lab merges on the bridge line, plus the 47 Rules-Core commits R-1 counted
    between upstream and `ef958ee9`.

  Neither number measures engine quality. Both show that each fork needs targeted Rules work.

### 2.3 Newly found during this assessment: AF07 regression on `main`

In both PR-head PB-03 runs after strict arrival (#625), the actual-card campaign blocks **22 of 29**
CARD records (M, `ACTUAL_CARD_CAMPAIGN_XMAGE.json` in runs 37888112605 and 37914716200). No PB-03
has run on `main` since; the same state there is inferred. The refusal:
"the record scripts no mulligan keep for P1". Errata 1.0.28–1.0.30 enumerated the midgame,
knowledge, replay and probe registries, but missed the campaign registry. So this is a Lab
record gap of the same class as before, not an XMage defect. A second missed registry also
showed up: the replay twin's mana payments (PB-03 run 37920050254 on #645). Both go into contract
1.0.31 (#645), together with a static coverage test over **every** lane registry. That test is
the structural fix (efficiency measure M5).

### 2.4 Product capability (beyond qualification)

- **XMage runs complete real multiplayer games today** (M, `xmage-full-game-conformance` run
  37920050208 on the PR #645 head `0a88ccea`, pinned engine):
  - 3P seed 1234: TERMINAL after 2,118 decisions, ≈ 19 s;
  - 4P seed 1618: TERMINAL after 2,576 decisions, ≈ 25 s;
  - 5P and 6P: hit the 3,000-decision cap at turns 44/37 (U: terminal not shown);
  - semantic same-seed replay, hidden-information redaction and fail-closed external decisions
    are covered by the same suite, and `xmage-real-4p-smoke` runs 4 turns of a real 4P game on
    every relevant PR.

  These are technical conformance games, not deck-strength evidence
  (`XMAGE_FULL_GAME_CLOSEOUT.md`).
- **The Lab's full-game lane is XMage-only** (`src/commander_lab/engine/rules/full_game.py`:
  `FULL_GAME_LANE = "xmage_full_game_external_pilots"`). The batch wrapper `full_game_batch.py`
  builds on that lane.
- **Forge has only the Protocol-2 scenario bridge** (`forge-protocol2-bridge`, 81 Java files
  module-wide). It has no external full-game driver in the Lab (M).
- **Card implementation breadth is at parity** (M, file counts at the pins; implementation files,
  not behaviour proof):
  - XMage: 32,123 card classes;
  - Forge: 33,669 card scripts.

### 2.5 Cost of running two engines

- **PB-03 wall-clock** (M, run 37914716200, total ≈ 3,000 s):
  - Forge-specific steps ≈ 435 s (≈ 15 %): build 132 s, checkout 33 s, FULL107 50 s, scenario
    lane 220 s;
  - XMage phases ≈ 1,800 s.

  Removing Forge would save ≈ 7 min per run. That is real but small.
- **The dominant cost is engineering, not CI** (E):
  - Forge parity needs the 87 rows of wave 2, 36 of them with adapter work;
  - then the Forge full-game lane, batch, replay and pilot integration, which do not exist;
  - then requalifying every later contract erratum on both engines.

  `docs/efficiency/PROJECT_EFFICIENCY_STATUS.md` records 3 PB-03 cycles lost to statically
  detectable record gaps in one erratum round (M). Doubling the engines doubles that exposure (E).

### 2.6 Licence (reported dimension, not a legal conclusion)

- **XMage is MIT** (recorded licence metadata).
- **Forge is GPL-3.0.** The Lab is proprietary. Running Forge as a separate process (the current
  qualification topology) differs from linking it in-JVM: the Owner has not accepted the D17
  in-JVM residual risk.
- **Porting Forge source into the MIT XMage fork or into the Lab is not permitted** without an
  explicit Owner licence decision. Lab policy treats rewritten Forge code as Forge-derived. The
  legal question is not answered here.

## 3. Options

| | A: XMage only | B: Forge only | C: two production engines | D: XMage production + bounded Forge reference | E: other engine (phase.rs screened, external data) |
| --- | --- | --- | --- | --- | --- |
| Rules correctness evidence | highest measured coverage; divergence unmeasured (107/107 NON_COMPARABLE) | 20/107 measured; divergence unmeasured | same as A+B | same as A; Forge cross-checks hard cases | none (U) |
| Card breadth | 32k classes | 34k scripts | — | as A | "34,300+" self-reported; "thousands … still unimplemented" |
| Multiplayer / Commander | real 3P/4P to TERMINAL | scenario lane only | — | as A | U |
| Legal actions to external pilots | full-game lane exists | Protocol-2 scenario only | — | as A | not described |
| Hidden info / RNG / replay | AF05, AF09 PASS | UNKNOWN | — | as A | U |
| Licence fit (proprietary Lab) | MIT | GPL-3.0 topology constraints | GPL constraints remain | MIT for production; Forge only as an external reference process | MIT/Apache |
| Remaining work to Freeze-ready | 1.0.31 + seal, then AF11 after selection | wave 2 (87 rows) + full-game lane + AF05/07/08/09 | A + B + parity upkeep | as A, plus an optional reference harness | full bridge and qualification from zero |
| Long-term cost | one fork | one fork, larger adapter gap | two forks, two qualification surfaces, every erratum twice | one fork; reference used on demand | rebuild |
| Fit with AGENTS.md §1 (single Rules authority after Freeze) | yes | yes | **no** | yes | yes |

- **C is rejected.**
  - It contradicts the mission's own end state: a single Rules authority after Freeze.
  - It doubles every requalification.
  - Its one real benefit, an independent second opinion on hard Rules cases, is available under
    D at a fraction of the cost.
  - Two engines that agree are not a proof of correctness. Official Comprehensive Rules, Oracle
    and rulings, actual-card rows, negative controls and replay twins give the same assurance
    without production parity.
- **B is rejected on the evidence.**
  - No Forge Rules advantage has been measured. Divergence is unmeasured, and card breadth is at
    parity.
  - Forge would need the full-game lane, batch, replay and pilot integration that XMage already
    has, plus 36 rows of adapter work and a GPL topology decision.
  - The time to the first usable product is strictly longer. This stays true even if Forge's
    internal Rules quality is assumed equal.
- **E (phase.rs) is screened out for now.**
  - It is weeks old by its own account, has thousands of cards unimplemented, documents no
    external decision interface, and has no Lab evidence. Source: its README at
    `github.com/lgray/phase`, read 2026-10-09; external data, not verified by the Lab.
  - Revisit trigger: a published external-agent protocol plus independent rules-test coverage.
- **A vs D.** D is A plus a deliberately small use of Forge:
  - Forge stays buildable at its R-1 pin and serves as a behaviour reference for named
    hard-Rules cases;
  - each such case is always adjudicated against the Comprehensive Rules, Oracle and rulings,
    never against Forge;
  - there is no production parity, no wave-2 obligation and no code port.

  The extra cost over A is near zero (E): the Forge checkout and scenario lane already exist.

### Counter-arguments examined

- **"Forge might have better Rules internals."** Plausible, but unmeasured. Nothing in the
  evidence shows an XMage Rules defect that Forge gets right. The XMage Rules defects found
  so far (mage#33, mage#41) were repaired inside the fork. If a systemic XMage Rules defect class appears that
  XMage's architecture cannot fix, D keeps Forge measurable. The revisit criterion is below.
- **"Dropping Forge loses the comparison."** Under D the comparison rows and the sealed Forge
  evidence stay. Nothing is deleted or relabelled. Only the *obligation* to reach Forge parity
  ends, and only once the Owner selects.
- **"Sunk cost in XMage."** The decisive facts are forward-looking: what remains to Freeze
  (A/D: one erratum and a seal; B: a product lane plus 87 rows), and that the only working
  full-game lane is XMage's.

## 4. Recommendation

**Option D: XMage as the single production Rules Core, with Forge kept as a bounded
differential reference.** This requires the Owner to select XMage as Production Provider. That
is Owner-only (AGENTS.md §8). Under the all-PASS rule XMage is eligible once every gate except
AF11 passes on a sealed epoch. AF11 is sequenced after selection (ADJUDICATION.md:113;
COORDINATOR_ADJUDICATION.md AF11 finding).

### Owner decisions requested (#255)

1. **Timing of the selection.**
   - Either select XMage once a sealed epoch on `main` shows every XMage gate except AF11 PASS.
     AF11 is adjudicated after selection against the single-provider topology, so it cannot
     pass before. This is the earlier adjudication's option B. Per the unsealed PR-head run it is
     one erratum away; the sealed AF06 is still UNKNOWN.
   - Or select now, with the same Freeze conditions.
2. **Forge role after selection: bounded reference (D).**
   - #592 wave 2 ends without a completion claim.
   - The Forge PB-03 phases become reference-only. They no longer gate PRs and run on demand.
3. **Licence policy.** No Forge source is ported into XMage or the Lab. A missing XMage mechanic
   is implemented independently from the Comprehensive Rules and Oracle, with provenance noted
   in the PR. Forge may be consulted for observed behaviour and for general technical ideas,
   never for code.

Revisit criterion (pre-agreed so it is not re-litigated): reopen B/C only if a sealed epoch shows
a systemic XMage Rules defect class that cannot be repaired inside XMage's architecture. Systemic
means the same CR mechanism failing across at least 3 independent actual-card rows.

## 5. What the Coordinator does now (authorized, no Owner action needed)

1. **Sequencing.** XMage critical path first:
   - contract 1.0.31 (AF07 campaign arrival histories, replay-twin mana, all-registry coverage
     test) and #634 step B in #645;
   - PB-03 on `main`, seal, re-issue the #255 adjudication.
2. **Forge.**
   - No new Forge wave-2 dispatches until the Owner answers decision 2. This is a reversible
     sequencing decision.
   - **This supersedes COORDINATOR_ADJUDICATION.md:101-102** ("Forge wave 2 continues, limited to
     items that change a gate, so option C stays available"). Option C is delayed until the
     Owner answers. If the Owner keeps C open, the gate-changing wave-2 items resume
     immediately.
   - #592 stays open. Its status is recorded as `DEFERRED_PENDING_OWNER_ENGINE_DECISION`, not
     COMPLETE.
   - Forge stays in PB-03 unchanged. Until selection, R-5 requires both candidates to run
     through the same producer.
   - No Forge evidence is deleted or relabelled.
3. **Codex and OpenCode work** is unaffected:
   - #646 (PB-03 trigger audit) is Codex's;
   - the #645 OpenCode run is Claude's lane.
4. **CI.** No check is removed now. The ≈ 435 s Forge share of PB-03 is reclassified only after
   the Owner's decision 2, as a separate PR with impact adjudication.

## 6. Roadmap to reproducible four-player Commander studies (XMage path)

| Step | Content | Gate / owner |
| --- | --- | --- |
| 1 | 1.0.31 + #634 step B (#645) | PB-03 on PR head; Claude |
| 2 | PB-03 on `main`, seal epoch, re-issue #255 | sealed epoch; Claude |
| 3 | Production Provider selection | **Owner** |
| 4 | AF11 against the single-provider topology (separate-process XMage); then Freeze | Coordinator adjudication, then **Owner** (Freeze) |
| 5 | Production repository | **Owner** |
| 6 | Real 100-card decks: import (AF03), external pilots on the full-game lane, 5P/6P to TERMINAL within the decision cap | engineering, after Freeze |
| 7 | Process-isolated batch (`full_game_batch.py`), semantic replay per game, seed ledger | engineering |
| 8 | First deck-vs-field study: N games per pairing, confidence intervals, replay-sampled audits | engineering + analysis |

Throughput estimate for step 8: the 4P technical fixture takes ≈ 25 s per game in CI (M), so
about 140 games per hour per process (E). Real 100-card decks and stronger pilots will change
this (U).

## 7. Unknowns that remain

- AF11 for any candidate; it is only decidable after selection.
- Whether 5P/6P games terminate within the decision cap.
- Real-deck throughput.
- Forge's internal Rules quality relative to XMage. It has not been measured and is not needed
  for D.
- The legal conclusion on GPL topologies. It is not given here.

## 8. CI and evidence impact

| Check / evidence | Now (before selection) | After Owner decision 2 (D) |
| --- | --- | --- |
| PB-03 XMage phases (FULL107, mid-game, knowledge, replay, campaign) | kept; the qualification surface | kept |
| PB-03 Forge phases (build, FULL107 forge, scenario lane; ≈ 435 s) | kept unchanged; same-producer measurement until selection | reference-only, run on demand, no PR gate; separate PR with impact adjudication |
| `xmage-full-game-conformance`, `xmage-real-4p-smoke` | kept | kept; extended toward real decks and 5P/6P terminal |
| Sealed epochs (all, incl. Forge rows) | immutable | immutable; no relabelling |
| Forge census matrices (`docs/forge_af0*`) | regenerated on record changes | frozen as reference snapshot |
| `ci-definition-integrity-shadow` | red by design (CI-02) | unchanged |

No check is removed or weakened by this record.

## 9. Workstream reconciliation

| Workstream | Owner | Disposition |
| --- | --- | --- |
| #634 / #645 (step B + contract 1.0.31) | Claude | XMage critical path; continues |
| #441 evidence closure | Claude | continues, XMage-first |
| #626 arrival rows | Claude | close after a sealed epoch requalifies its rows |
| #646 PB-03 trigger audit | Codex | unaffected; no overlap |
| #592 Forge wave 2 | (no active dispatch) | `DEFERRED_PENDING_OWNER_ENGINE_DECISION`; stays open |
| #255 provider adjudication | Coordinator → Owner | re-issued after the next sealed epoch, with this ADR as the strategy basis |
