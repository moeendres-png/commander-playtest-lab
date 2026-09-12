# FULL107 Execution Plan — Exact 107 Provider-Fixture Contract (Future Qualification, Not Executed)

Workstream: `WS73-FULL107-CONTRACT-RECONCILIATION` (sole evidence writer; this plan designs, does not execute).
Contract: WS47 `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8` — 135 materialized records, 107 provider denominator
(`qualification/ws44/WS44_PROVIDER_DENOMINATOR_107.json`), schema
`commander-lab.semantic-fixture-materialization/1.0.5`, protocol
`commander-lab.rules-service/1.1.0`, `canonical_bundle_digest`
`631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01`.
This is the exact 107 provider-fixture contract, NOT a hypothetical remaining-92 RQ-C3 scenario set.
`FULL107 = NOT_RUN`. `BEHAVIOR_CREDIT_CHANGE = 0`. No behavior credit from WS73.

## 0. Scope and non-goals

- Qualify the 107 provider fixtures for each candidate independently (Forge at
  `a9a95db6662c2d28814390a9c0c2f986e39aa8b4`, XMage at `7135d5e85ddb4c8aa4b49b4192ca51947c822704`).
- No RQ-C3 scenario is a Full107 fixture; no RQ-C3 PASS pre-counts Full107 credit
  (RQ-C1 relation). No invented 92. No cross-contract credit.
- No engine edits, no provider semantic edits beyond separately-authorized remediation
  workstreams. WS67/WS68 outcomes are conditional inputs (Forge plan gated below).

## 1. Required current contract materialization

1. Re-resolve the exact WS47 materialization at `192e2b77` (`SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json`,
   sha256 `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3`, 135 records) and the exact
   denominator (`WS44_PROVIDER_DENOMINATOR_107.json`, 107 IDs + 28 excluded `CARD_01,CARD_03..CARD_29`).
2. Validate with `ws73_validate.py`: 135 records, 107 denominator IDs, every denominator ID in
   materialization, denominator+excluded==135, family censuses.
3. Freeze the 107 ordered fixture list byte-identically (see `FULL107_CONTRACT_IDENTITY.json`);
   any re-materialization requires new authority, never silent substitution.
4. Families to cover per fixture (denominator census): `player_count 4`, `pilot_boundary 17`,
   `pilot_boundary_negative 7`, `hidden_information 20`, `replay_rng 5`, `micro_rules 17`,
   `multiplayer_commander 36`, `actual_card 1 (CARD_02)`. Execution modes: 100 `NATIVE_STATE_LOAD`,
   7 `NATURAL_GAME_START` (MULL/START/TURN natural rows with bottom/hand/library evidence).

## 2. Provider/engine binding (per candidate, exact-pin provenance)

### Forge
- Engine: `moeendres-png/forge@a9a95db` / tree `2c18327f79e330f2ed167067166ffd42d61b0849`
  (WS59 remediation on `66caae1`). Verify `git rev-parse HEAD^{tree}`, `git log --oneline -1`,
  fresh offline `mvn -o` build of `forge-core,forge-game`.
- Provider: fresh build from the qualifying worktree against the successor `PlayerController`
  surface (110-callback generation pattern per WS62/WS65), with `WS62v2`-lineage transports
  (conditional concession via native `canConcede`, stack-SA binding via `canTargetSpellAbility`+host-ID)
  plus whatever WS68 qualifies (payCombatCost authoritative transport + two-phase concession offer).
  Record all overlay digests + `provider.classpath` + handshake proving successor-only runtime
  (old pin `66caae1` fail-closed absent from classpath).
- **Gate: do not start Full107 behavior until WS67 (engine: Ghalta/Covenant/Clone) and WS68
  (provider: payCombatCost/concession) both reach qualified terminal PASS.** If either is
  PARTIAL/FAIL/ACTIVE, Full107 Forge behavior stays `NOT_RUN`; construction/readback may proceed
  only as explicitly-gated staging with zero behavior credit.

### XMage
- Engine: `moeendres-png/mage@7135d5e` / tree `ea193e0d04493d53d962ed13ebd3b5d2f68838c7`
  (WS56 successor, M1-M5 + mode/freshness closed, 111/111 green). Verify HEAD/tree, fresh build.
- Provider/harness: WS56-lineage bridge (`XmageFullGamePlayer/DecisionController/Session/Provider`)
  with WS49-remediation bindings (native `possibleTargets`/`getPlayable`/`GameView` authority,
  actor/source-scoped mana, principal-scoped hidden battery, SBA-derived elim, `RandomUtil` funnel
  audit) plus WS60 driver/projection fixes (key-mode `Choice`, content-ordered attacker/blocker frames,
  `dieResults` tape, redaction). Record digests + handshake.
- XMage has no WS67/WS68 dependency; gate is fresh Full107 construction + G49-08-class independent
  normalization at `7135d5e` before any behavior.

## 3. Per-fixture evidence (each of the 107, each candidate)

For every fixture ID, in a fresh process, produce:
- `fixture.json` (exact contract record + intent: native entry mode, scripted decisions if any,
  seeded-ledger boundaries with `BEHAVIOR_CREDIT=0` where applicable, e.g., G03-class patterns).
- `run_receipt.json` (source locks: WS47 commit/tree/materialization sha, denominator sha,
  engine commit/tree, provider commit/tree/digests, runner digest, seed(s), process PID/host,
  artifact hashes; no timestamps as evidence).
- `journal.json.gz` (complete native Decision-frame/event tape; every external selection bound
  1:1 to an engine-offered legal option; zero/multiple matches fail closed; forbidden fallbacks
  absent: first/random/default/GUI/AI/pseudo-option/injection/filtering).
- `adjudication.json` (PASS/FAIL/UNKNOWN per Full107 evidence contract; PASS requires all terminal
  postconditions + expected events + hidden/RNG/replay sub-verdicts; UNKNOWN is not PASS).
- `replay.json.gz` + `replay_verdict` (semantic replay in a second fresh process with same explicit
  Rules seeds; 0 divergences required for PASS; B01-class structural UNKNOWN gets no replay credit).
- Negative controls per family (tampered hands/echo/denominator/sentinel/eligibility/sickness/tapes
  fail closed with precise codes, per WS49 G49-08 8/8 pattern).

Stages mirror WS48/WS49 discipline: (a) fresh construction 107/107, (b) independent readback/
normalization 107/107 by a separately-implemented normalizer (no construction imports),
(c) fresh behavior 107/107, (d) hidden-adversarial, RNG/replay, unsupported-path audits.
Construction/normalization grant zero behavior credit.

## 4. Process isolation

- One fixture per fresh OS process (no shared static game state; `MINTED`-style determinism per
  deck+seed where applicable, but never cross-fixture seed reuse as proof).
- Engine and provider classpaths pinned per run; old pins absent (fail-closed classpath gate).
- Artifacts content-addressed (sha256 manifest); rerun byte-identical on normalized logs
  (timestamps excluded from digests).

## 5. Principal-scoped hidden info

- Every hidden fixture (`HIDDEN_01..19`, `HIDDEN_HONEYCARD_SENTINEL`, plus pilot hidden-zone
  decisions, e.g., pitch costs) verified per-viewer against native `GameView`/ledger snapshots:
  each viewer sees only own hand names; libraries counts-only outside entitled grant windows;
  face-down exile/battlefield redacted (`Hidden card`); reveal-to-ALL during resolution where
  Rules require it (701.20a-class), hidden-again after with retained usable knowledge (not leak).
- Sentinel scanned absent across all readbacks. Multi-view partitioning proofs on hidden rows;
  four-surface federation on natural rows (preflight decks, decision transcript, observation query,
  replay checkpoints) per WS49 pattern.

## 6. Controlled Rules RNG

- All randomness originates in Rules Core; seeds recorded per run with purpose/domain/fingerprint/
  result/event/replay journal contract (purpose `RQ_C1_RNG_EXPECTATIONS`-class shapes, never
  prescribed outcomes). `RNG_RULES_TAPE` + `REPLAY_*` fixtures validate tape-validity, clean-process
  replay, and state-hash chains. `RandomUtil`/shuffle/coin/d20/discard funnels audited;
  uncovered channels (e.g., `putCards Top/Bottom Collections.shuffle`-class) explicitly listed,
  never silently passed.

## 7. Semantic replay

- Every behavior PASS requires a twin replica in a fresh process with identical explicit seeds,
  byte-identical normalized logs, matching event multisets/views, zero assertion divergences.
- Replay grants no separate credit. Divergences fail closed (flaky/environmental claims require
  multi-head reproduction evidence, per WS49 Full Game Conformance discipline).

## 8. Fail-closed behavior

- Unsupported decision kinds (e.g., pre-WS68 `payCombatCost`), undeclared pass authority,
  zero/multiple-match selections, stale handles, provenance mismatches, and out-of-option
  selections all terminate fail-closed with precise codes (e.g.,
  `UNSUPPORTED_DECISION_KIND`, `WS49_BEHAVIOR_PRIORITY_PASS_NOT_DECLARED`).
- Requested-option filtering as reconstructed legality is forbidden. Manual target/outcome
  injection is forbidden. First/random/default fallbacks are forbidden (7-item negative list
  censused statically + in journals).

## 9. Exact credit semantics

- One credit per Full107 fixture PASS at the candidate's exact qualifying source lock, denominator 107.
- Construction/readback/normalization grant 0 behavior credit. Replay grants 0. Entry-prerequisite
  tests grant 0. Seeded pre-boundary state grants 0.
- RQ-C3 First-Wave PASS grants 0 Full107 credit. `BEHAVIOR_CREDIT_CHANGE = 0` until a Full107
  behavior PASS is sealed under this plan.
- Verdicts: `PASS` (credited), `FAIL` (defect demonstrated), `UNKNOWN` (insufficient evidence;
  not creditable). Missing evidence stays `UNKNOWN` or `NOT_RUN`, never PASS.

## 10. Current-pin provenance (to be rebound at execution)

- Forge: `a9a95db` + WS67/WS68 terminal commits/trees/digests (to be filled; plan conditioned).
- XMage: `7135d5e` + WS56 `1dc43619` + execution-worktree HEAD/tree (to be filled).
- WS47 contract + denominator shas as in §1. All pins verified pre-edit via `git rev-parse` +
  `git show` + file-hash gates; evidence/state descendants do not promote the audit head.

## 11. Forge conditional (WS67/WS68)

- If WS68 qualifies payCombatCost + concession: unblock the 16 DEPENDENT fixtures for behavior
  attempts (E01-class pay/decline, G04-class concession, MP combat/elim paths) with fresh evidence.
- If WS67 dispositions Ghalta/Covenant/Clone (fix or scoped UNKNOWN→FAIL with packets): unblock
  or terminally scope the 27 BLOCKED fixtures accordingly; do not attempt BLOCKED fixtures as
  PASS-expected before disposition.
- If either remains ACTIVE/PARTIAL/FAIL: Forge Full107 behavior remains `NOT_RUN` (construction
  staging only, explicitly zero-credit).

## 12. Outputs and validation

- Per-fixture packets + `FULL107_BEHAVIOR_CREDIT.json` (`n/107`), `FULL107_SCENARIO_MATRIX.json`,
  hidden/RNG/replay audits, failure taxonomy, final report, `WORKSTREAM_STATE.yaml` with
  `validated_head` set to the clean committed audit HEAD (evidence/state descendants do not promote).
- Validate with a deterministic validator (135/107/denominator-membership/Full107-credit-only-from-Full107-contract gates) on clean HEAD before any push; `safe_push` dry-run then actual only if all gates pass.

*Designed, not executed. No behavior credit from WS73.*
