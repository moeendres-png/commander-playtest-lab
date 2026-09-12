# WS74 Final Report — XMage Full107 Construction + Independent Normalization (Staging Only)

Terminal verdict: `WS74_XMAGE_FULL107_STAGING=PARTIAL` (demonstrated native causes below).
No Full107 behavior executed. No behavior credit. No engine edits.

## Source Lock

- CPL: `moeendres-png/commander-playtest-lab`, branch
  `ws74/xmage-full107-construction-normalization-20260912`, audit base WS73
  `96db95dbc3a63d2a10d86e04c65443da617d4437`.
- Contract: WS47 `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8` — 135 materialized
  records, 107 provider denominator, 28 excluded, schema
  `commander-lab.semantic-fixture-materialization/1.0.5`.
- Engine: `moeendres-png/mage` at accepted successor
  `7135d5e85ddb4c8aa4b49b4192ca51947c822704` / tree
  `ea193e0d04493d53d962ed13ebd3b5d2f68838c7` (read-only checkout
  `/tmp/ws56-mage-successor-src`, no tracked modifications; old pin `0c1f455e`
  absent from the staging classpath).
- Bridge lineage: WS56 `1dc43619` (111/111 at successor) + WS60 `731891ec`
  (RQ-C3 14/15, separate historical evidence). Staging reuses the qualified
  lane read-only (`XmageGameManager`, `XmageBridgePlayer`,
  `XmageActionExecutor.passPriority` for startup only, `XmageDeckImporter`).
- Validated tools HEAD (this staging scope only): `083fa615`.
- Full lock: `SOURCE_LOCK.md`. Evidence classes: only `DIRECTLY_VERIFIED`,
  `CODE_DERIVED`, `TECHNICALLY_CONFORMANT`. Never `RUNTIME_VERIFIED`.

## Work Completed

1. **Denominator binding (mechanical re-read).** 135/107/28 with per-record
   digest recomputation, membership/union proofs, RQ-C3 namespace
   disjointness, SHA provenance. `FULL107_DENOMINATOR_BINDING.json` PASS.
2. **Fresh exact-pin build.** Offline `mvn` rebuild of `Mage`, `Mage.Sets`,
   `Mage.Deck.Constructed`, `Mage.Game.CommanderFreeForAll` at `7135d5e`
   (BUILD SUCCESS). All four runtime jars byte-identical to the installed
   `1.4.61` artifacts; only `1.4.61` exists locally; successor descends from
   the old pin. `XMAGE_BUILD_RECEIPT.json` (re-verifiable digests).
3. **107/107 construction attempts (fresh exact-pin JVM).** New staging
   harness `Ws74StagingHarness` (same-package reuse, zero bridge/engine
   edits): per fixture — Commander decks (commander identities + Wastes
   filler), explicit Rules seed, native start through scripted keeps,
   provider-machinery startup passes to the contractual load boundary
   (precombat main, turn 1, active P1, priority P1, paused), direct native
   state placement (zones, tapped, counters, face-down, ordered libraries,
   stack spells with declared targets/modes, commander-damage restore via
   the in-pin API, grant-backed look/reveal traces), native structural
   validation, native readback emission. Result: **105/107 CONSTRUCTED**.
4. **Independent 107/107 normalization.** `ws74_normalize.py` shares no code
   with the constructor, never echoes fixture input as observed state, and
   derives everything observable from native readback (fixed D1/D3/D7/D8
   rules, filler excluded by native UUID only). Result: **42/107
   NORMALIZATION_PASS** (digest-equal), 63 FAIL with exact field codes,
   2 UNKNOWN (no constructed readback).
5. **Negative controls 8/8 PASS.** Wrong seat, identity, zone,
   controller/owner, hidden exposure, stale handle, denominator tamper, and
   echo substitution (record-shaped + inconsistent forgery) all detected
   fail-closed. `NORMALIZATION_NEGATIVE_CONTROLS.json`.
6. **Hidden preflight.** Independent scan of all native per-viewer views:
   105 clean, 0 exposures, 2 UNKNOWN (unconstructed fixtures).
   Representation-only; no hidden-behavior PASS granted.
7. **Determinism.** Full pipeline rerun from committed tools: 212 artifacts
   compared, 0 mismatches (normalized projections byte-identical);
   isolated single-fixture JVM spots equal sequential runs.
   `STAGING_DETERMINISM.json` PASS.

## Terminal fail taxonomy (demonstrated native causes, terminal adjudications)

Construction (2 FAIL):
- `WS05-MP-TURN-3`, `WS05-MP-TURN-5`: `MOVE_REJECTED:graveyard`
  (`obj:mp-nexus`, Nexus of Fate) — the engine's own replacement effect
  refuses graveyard placement through legal moves. No fabrication path
  taken; staged as terminal construction FAIL.

Normalization (63 FAIL, first-diff causes):
- ~20× `controlled_since_turn_began`: the contract asserts setup objects were
  controlled since turn began; natively every placement occurs after turn 1
  began (false). Model-history vs engine-truth gap; largest single cause.
- 12× `temporal.phase` (+2 active, +1 priority): combat/beginning/pregame
  phases and P2 active/priority are post-behavior or model-boundary states,
  unreachable without executing behavior.
- 8× `zone_move_event`: pending commander choices (behavior-gated decisions).
- 4× `combat_state` (+2 attached_to): attack/block declarations and Aura
  attachments (behavior-gated).
- 6× elimination/SBA-adjacent (`elimination_trigger`, life-0): SBA evaluation
  is out of staging scope (no loss applied, no SBA run).
- 3× `prior_command_zone_cast_count`: requested cast history (TAX fixtures);
  no casts executed in staging.
- 4× knowledge (`known_object_identities` HIDDEN_03/18, `known_library_ranges`
  HIDDEN_10/11): public-exile listing without grant, transcript-scoped
  knowledge, and scry/shuffle knowledge have no native trace at the boundary.
- 1× `tapped` (PILOT_CHOOSE_USE Path of Ancestry): ETB choice declined by the
  bridge (no choice submitted in staging); engine left it tapped.
- 1× `zone` (PILOT_PILE): pending-choice piles have no native zone (cards sit
  in hand with revealed-container membership).

## Changes

Owned directory only
(`candidate-qualification/ws74-xmage-full107-construction-normalization/`):
tools (`Ws74StagingHarness.java`, `ws74_construct/denominator/normalize/
negatives/preflight/determinism/validate.py`), `SOURCE_LOCK.md`, evidence
matrices/receipts, `FINAL_REPORT.md`, `WORKSTREAM_STATE.yaml`. No other CPL
files. No XMage, bridge, or provider semantic edits. No weakened assertions
or denominators. Ignored runtime outputs only (engine `target/`, H2 card
cache, scratch runs — all documented, none committed).

## Tests / Evidence

- `ws74_validate.py` terminal gates (exit PARTIAL=3): denominator PASS, build
  PASS, construction 105/107 (107 attempted), normalization 42/107,
  negatives PASS, determinism PASS, preflight PARTIAL (105/0/2).
- Evidence classes: `DIRECTLY_VERIFIED` (pins, counts, digests),
  `CODE_DERIVED` (matrices, derivations), `TECHNICALLY_CONFORMANT`
  (lane reuse). The validator's label sweep notes the policy sentence
  "Never `RUNTIME_VERIFIED`" in this report; that is a restatement of the
  prohibition, not an evidence claim (no artifact asserts that class).
  UNKNOWN never PASS.
- `validated_head=083fa615` (clean committed tools HEAD of final validation;
  evidence/state descendants do not promote it; staging scope only).

## PASS / FAIL / UNKNOWN

- `FULL107_DENOMINATOR_BINDING=PASS`
- `XMAGE_EXACT_PIN_BUILD=PASS`
- `FULL107_CONSTRUCTION=105/107` (107/107 attempted; 2 engine-refused)
- `FULL107_NORMALIZATION=42/107` (63 FAIL evidenced, 2 UNKNOWN)
- `NORMALIZATION_NEGATIVES=PASS` (8/8)
- `HIDDEN_REPRESENTATION_PREFLIGHT=PARTIAL` (105 clean, 0 exposures, 2 UNKNOWN)
- `STAGING_DETERMINISM=PASS`
- `WS74_XMAGE_FULL107_STAGING=PARTIAL`

## Remaining Blockers

None for this staging workstream (terminal). The PARTIAL causes are
future-work inputs, not WS74 blockers: (a) contract history fields
(`controlled_since_turn_began`, cast/damage histories) unproducible without
gameplay; (b) post-behavior snapshots (combat phases, declarations, pending
choices, SBA outcomes) require the Full107 behavior workstream (NOT_RUN);
(c) Nexus-of-Fate-class replacement paradoxes need a Rules-authority
disposition; (d) model-boundary temporals (pregame/mulligan) need a
contract-boundary revision or pre-game staging API. No new giant checkout was
allocated; no infrastructure blocker remains open.

## Outputs

`candidate-qualification/ws74-xmage-full107-construction-normalization/`:
`SOURCE_LOCK.md`, `FULL107_DENOMINATOR_BINDING.json`,
`XMAGE_BUILD_RECEIPT.json`, `FULL107_CONSTRUCTION_MATRIX.json`,
`FULL107_NORMALIZATION_MATRIX.json`, `NORMALIZATION_NEGATIVE_CONTROLS.json`,
`HIDDEN_REPRESENTATION_PREFLIGHT.json`, `STAGING_DETERMINISM.json`,
`Ws74StagingHarness.java` (`ws74_construct.py` driver),
`ws74_normalize.py`, `ws74_denominator/negatives/preflight/determinism/
validate.py`, `FINAL_REPORT.md`, `WORKSTREAM_STATE.yaml`.

## Dependencies Unblocked

- Future Full107 behavior commissioning inherits an exact-pin engine binding,
  a 105-fixture constructed-state baseline with native readbacks, and a
  proven independent normalizer with 8/8 negative controls.
- The fail taxonomy scopes exact follow-ups (behavior workstream, contract
  history-field revision, Nexus-class Rules disposition) without re-derivation.

## Exact Next Action

Coordinator review of this terminal PARTIAL staging result; then authorized
`safe_push` actual only if accepted (dry-run first with
`--expected-audit-base-ref ws73/full107-contract-reconciliation-20260912`).
No behavior, freeze, or provider selection follows from WS74.

---

WS74_XMAGE_FULL107_STAGING=PARTIAL
FULL107_DENOMINATOR_BINDING=PASS
XMAGE_EXACT_PIN_BUILD=PASS
FULL107_CONSTRUCTION=105/107
FULL107_NORMALIZATION=42/107
NORMALIZATION_NEGATIVES=PASS
HIDDEN_REPRESENTATION_PREFLIGHT=PARTIAL
STAGING_DETERMINISM=PASS
VALIDATED_HEAD=083fa615294e6f6f127ee26ae506936b20651501
XMAGE_FULL107_BEHAVIOR_CREDIT=0/107
FULL107_BEHAVIOR=NOT_RUN
ARCHITECTURE_FREEZE=NOT_CLAIMED
PRODUCTION_PROVIDER=NOT_SELECTED
