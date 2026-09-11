# WS56 — XMage Successor Requalification Final Report

Terminal verdict: `XMAGE_SUCCESSOR_REQUALIFICATION_PASS`

- Exact successor pin consumed; M1-M5 bounded PASS through CPL; no
  production-critical Rules-RNG bypass; mode identity gap closed; state/frame
  freshness gap closed; hidden-info regression PASS; negative controls PASS;
  UNKNOWN 0 in claimed successor architecture scope.

## Source lock (DIRECTLY_VERIFIED)

- CPL: `moeendres-png/commander-playtest-lab` @
  `7023cbdf533df82d59a50a83d16baf816edb7307` /
  `e4122b510e7bb3018f72ef74ce4e8ffdc8ac9076` on
  `ws56/xmage-successor-requalification-20260911`.
- Old engine: `0c1f455ea8c8fa48ab9d638ad5068ec242800428` /
  `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`.
- Successor: `7135d5e85ddb4c8aa4b49b4192ca51947c822704` /
  `ea193e0d04493d53d962ed13ebd3b5d2f68838c7` (detached clean read-only
  `/tmp/ws56-mage-successor-src`; ancestor of old is old; 114-file WS54 delta).
- WS54 terminal `XMAGE_RNG_REEXECUTION_REMEDIATION_PASS` consumed as
  CODE_DERIVED input; requalified through CPL in WS56 M5.
- XMage read-only; no master upgrade; no other pin.
- See `WS56_SOURCE_LOCK.md`, `WS56_PIN_INTEGRATION.json`.

## Pin integration

- `XmageProvider.ENGINE_COMMIT` updated `77d7646d` → `7135d5e8`
  (full-game lane declaration now matches runtime; hygiene defect fixed).
- `JsonlBridgeTest` expectation updated to successor (pin change, not weakening).
- Runtime artifacts (`~/.m2` 1.4.61 jars) byte-identical to successor-worktree
  targets built from `7135d5e` (mage `de83c2e5…`, sets `5f225321…`,
  deck-constructed `d8c9c432…`, commander-FFA `647f2216…`).
- Historical B4 lane (`Phase6DifferentialAdapter`, `config/rules_engines.json`)
  still declares the old audit pin and is NOT requalified in WS56 (out of
  claimed scope; see impact ledger).

## Adapter changes (CPL-owned, no XMage edits)

1. **Rules seed authority (M5):** `XmageFullGameSession` + `Ws52Harness` now
   `setRulesSeed(seed)` + `setRequireExplicitSeed(true)` immediately after game
   construction (fail-closed when missing). `RandomUtil.setSeed` retained as
   NON-RULES only. `resultPayload` now exposes `rules_seed`,
   `rules_seed_explicit`, `rules_random_calls` (diagnostics, never authority).
2. **Mode identity (Phase C):** `XmageFullGamePlayer.chooseMode` emits opaque
   `stableId("mode", nativeModeUUID)` handles; metadata carries only
   `mode_ref` opaque + paw-print (no native UUIDs). Availability still via
   `modes.getAvailableModes(source, game)` (engine alone). Per-frame `byId`
   + controller `externalToNative` binds exactly one current native; stale/
   wrong/unknown/ambiguous fail closed. Sequential modes engine-driven.
3. **Freshness (Phase D):** `XmageFullGameDecisionController` computes
   `option_digest` (sorted current external ids + kind) and `frame_digest`
   (game + revision + actor + subject + kind + option_digest + actor_view_hash)
   plus `frame_revision`, `actor_view_hash`, `freshness` object, and
   `field_provenance` (every field `ENGINE_NATIVE` or `ADAPTER_OWNED`).
   Submit must echo all three; mismatch → `STALE_DECISION`; missing →
   `PILOT_RESPONSE_INVALID`. Digests are SHA-256 hex (no hidden leakage).
   Test helpers (`Ws52`, `Ws52Harness`) echo freshness (contract adaptation,
   not weakening).

## M1 — Authoritative Decision Extraction: PASS (bounded)

- Priority set EQUALS engine `getPlayable` (+ pass x1); target set EQUALS
  `possibleTargets` (opaque `obj-` handles, non-first binds live player).
- Mode reassessed: visible/null-source Boros Charm modes (3) cross with opaque
  identity, 1:1 native binding, no UUID/metadata leak; hidden-library modal
  source still fail-closed via gateway (`HIDDEN_INFORMATION_LEAK` or blocker).
- Freshness present on every frame; no hidden tokens in frame.
- Evidence: `WS56_M1_DECISION_EXTRACTION.json`, `Ws56DecisionExtractionTest`
  4/4 + `Ws52M1` 4/4 on successor.

## M2 — Selection → Native → Execution: PASS (bounded)

- Twin Rograkh cast (non-first, index ≥1) vs pass twin: cast stack holds
  exactly Rograkh, pass twin empty, both advance, transcript records.
- Target first-vs-last opaque bind different natives.
- No label rematch (binding via frame-local exact ids + freshness).
- Evidence: `WS56_M2_SELECTION_EXECUTION.json`.

## M3 — Fail Closed: PASS (bounded)

- Unknown → `ILLEGAL_ACTION`; stale id/replay/tampered digest/previous frame
  → `STALE_DECISION`; malformed → `invalid_full_game_decision`/`invalid_json`/
  `protocol_version_mismatch`; wrong principal → wrong-actor; wrong kind bound
  in id+digest (cross-kind replay → stale); ambiguous collapse → blocker;
  missing freshness → `PILOT_RESPONSE_INVALID`; duplicate/bounds/numeric/
  zero-binding/second-game all fail closed. No fallback.
- Evidence: `WS56_M3_STALE_INVALID.json`, `WS56_NEGATIVE_CONTROLS.json`.

## M4 — Hidden Information: PASS (bounded)

- Sentinel disjoint decks: own hand 7 named, opponent hand key ABSENT,
  opponent library names absent both viewers, public zones visible, pending
  frame carries no opponent identity.
- Planted leak at `validate` trips `HIDDEN_INFORMATION_LEAK`; owner passes.
- Freshness/mode metadata, serialized frames, transcript/diagnostics inspected;
  digests opaque, diagnostics generic `ENGINE_ERROR` tokens.
- NOT claimed (UNKNOWN, out of scope): face-down/morph, face-down exile,
  lookAt/reveal, multi-card reveal, `GameView` redaction.
- Evidence: `WS56_M4_HIDDEN_INFO.json`.

## M5 — Controlled Rules RNG + Reexecution: PASS (bounded, through CPL)

- Explicit identical Rules seed (5201, `isRulesSeedExplicit` true);
  identical setup (rogshai 98+2, same hash); identical decisions (Seat1 +
  2 keeps + 10 priority passes); identical outcomes (hands sorted multisets
  byte-identical, incl. Boros Charm in hand0); identical events (flow
  `choose_object,mulligan,mulligan,priority*10`); identical terminal state
  (turn 1, decisions 14, calls 194, digest 497 chars byte-identical).
- Fresh JVM/process: two separate `mvn` invocations → byte-identical digests.
- Interleaved isolation: foreign seed B in same JVM does not perturb A.
- Non-Rules perturbation: 50k `RandomUtil` storm does not perturb Rules.
- Snapshot/restore: arbitrary mid-decision replay remains NOT_REQUIRED and is
  not claimed (WS54 disposition; WS52 snapshot test updated to GameRandom
  forward-only without live parked restore).
- Evidence: `WS56_M5_RNG_REEXECUTION.json`, `Ws56M5RngReexecutionTest` 5/5 +
  fresh-process gate.

## Phase C — Mode Identity: GAP CLOSED

- Competing (3), non-first (last), stale, wrong-principal, ambiguous
  (unknown + collapsing unit), progression (new id/digest, old stale) all PASS.
- Evidence: `WS56_MODE_IDENTITY.json`, `Ws56ModeIdentityTest` 6/6.

## Phase D — State / Frame Freshness: GAP CLOSED

- Binds game, principal, kind, current option identities, frame/state
  (`actor_view_hash` + revision). Older frame fails closed. Every field
  classified `ENGINE_NATIVE`/`ADAPTER_OWNED` (see `WS56_STATE_REVISION.json`);
  no adapter digest described as XMage-native; no revision leak.
- Evidence: `WS56_STATE_REVISION.json`, `Ws56StateFreshnessTest` 7/7.

## Historical impact

- `WS56_HISTORICAL_IMPACT_LEDGER.json`: WS49 TARGETED, M1-M4 TARGETED
  (all requalified PASS in WS56), M5 INVALIDATED (superseded), earlier history
  TARGETED. NO_IMPACT 0, UNKNOWN 0. No PASS preserved by assumption.

## Rules authority boundary (all forbidden absent)

- No reconstructed legality, target/cost/mana solvers, provider priority
  legality, manual resolution, internal AI, first/random/default fallbacks,
  requested-filtering as legality, or manual injection. Verified by oracle
  equality (M1), exact binding (M2), and negative matrix (M3/mode/freshness).
  Unsupported paths fail closed.

## Tests / evidence

- `mvn -f engine-bridge/pom.xml test` → **111/111 PASS** (86 pre-existing +
  25 new WS56: mode 6, freshness 7, M5 5, decision 4, hidden 3).
- `mvn -f engine-bridge/pom.xml -Dtest='Ws52*' test` → 24/24 PASS on successor.
- Fresh-process M5: 2× separate JVMs → byte-identical 497-char digests.
- Evidence classes used: `DIRECTLY_VERIFIED` (runtime), `CODE_DERIVED`
  (source/rationale), `TECHNICALLY_CONFORMANT` (bounded PASS), `UNKNOWN`
  (explicit out-of-scope only). No `RUNTIME_VERIFIED` invented; no
  `EXTERNALLY_RULE_VALIDATED` from XMage behavior.
- Artifacts: `candidate-qualification/ws56-xmage-successor-requalification/`
  (`WS56_*.md/json` + `WORKSTREAM_STATE.yaml`) + `engine-bridge/target/ws56-evidence/`.

## Remaining blockers

- None in claimed successor scope. Out-of-scope UNKNOWNs remain (face-down,
  reveal windows, `GameView` redaction, arbitrary restore, WS54 residuals)
  and must stay UNKNOWN until future qualification. RQ-C3 First Wave NOT run
  in WS56 by boundary.

## Outputs

- `WS56_SOURCE_LOCK.md`, `WS56_PIN_INTEGRATION.json`,
  `WS56_HISTORICAL_IMPACT_LEDGER.json`, `WS56_M1_DECISION_EXTRACTION.json`,
  `WS56_M2_SELECTION_EXECUTION.json`, `WS56_M3_STALE_INVALID.json`,
  `WS56_M4_HIDDEN_INFO.json`, `WS56_M5_RNG_REEXECUTION.json`,
  `WS56_MODE_IDENTITY.json`, `WS56_STATE_REVISION.json`,
  `WS56_NEGATIVE_CONTROLS.json`, `WS56_SUCCESSOR_READINESS.json`,
  `WS56_FINAL_REPORT.md`, `WORKSTREAM_STATE.yaml`.

## Dependencies unblocked

- Successor XMage architecture may enter later candidate-neutral RQ-C3
  execution stage (WS56 determines readiness; does not execute First Wave).

## Exact next action

- Coordinator adjudication of `XMAGE_SUCCESSOR_REQUALIFICATION_PASS` from the
  sealed WS56 evidence; on PASS, authorize RQ-C3 candidate-neutral First Wave
  as a separate workstream (WS56 executes no further engine work).

---

`XMAGE_SUCCESSOR_PIN_ACCEPTED = YES`

`XMAGE_RQC3_FIRST_WAVE_ENTRY_PREREQUISITES_READY = YES`

`BEHAVIOR_CREDIT = 0/107`

`FULL107 = NOT_RUN`

`ARCHITECTURE_FREEZE = NOT CLAIMED`

`PRODUCTION_PROVIDER = NOT SELECTED`
