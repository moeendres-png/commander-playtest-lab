# MUSE HEAVY SUPPORT HANDOFF — WS-48 FORGE v1.0.5

**Lane:** parallel Muse support (NOT final qualification authority)
**Support branch:** `muse/ws48-forge-v1.0.5-heavy-support`
**Base:** `origin/ws48/forge-v1.0.5-successor-qualification` @ `8dd961409917680a1a4e14999e30e266545097a8`
**Updated:** 2026-09-08 (UTC) — Phase A complete, Phase B in progress

## 1. SOURCE LOCK (freshly verified locally)

| Identity | Value | Verified |
|---|---|---|
| WS-48 HEAD | `8dd961409917680a1a4e14999e30e266545097a8` | `git rev-parse origin/ws48/...` PASS |
| WS-47 freeze commit | `192e2b77c0625ad26905bd0ee8dcc3f44a5796c8` | `git rev-parse` PASS |
| WS-47 freeze tree | `f596c54d2cb229b9827c6c94a278175e8312c65c` | PASS |
| WS-47 namespace tree | `12af73695c801a42a0193ee895d5fc0843d16b0c` | PASS |
| WS-47 schema | `commander-lab.semantic-fixture-materialization/1.0.5` | PASS |
| Materialization SHA-256 | `0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3` | `sha256sum` PASS |
| Canonical bundle digest | `631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01` | doc field PASS |
| Provider denominator | 107 unique fixture_ids | PASS |
| Forge repo/branch | `moeendres-png/forge` / `foundry/ws45-v104-observation-remediation` | clone in progress |
| Forge commit/tree | `66caae16015bd403bc0a52fa6689afb5508f74d0` / `40fc8f29ce4de31a964972461db2b48b4221e07f` | pending clone verify |
| Historical runtime credit | 0 | per WS48 checkpoints |

## 2. CURRENT WS-48 GATE MATRIX

| Obligation | Status | Evidence |
|---|---|---|
| source lock (G48-01/02) | PASS | §1 + WS48_CHECKPOINT_01 |
| denominator/digest reconciliation (G48-04/05) | PASS | WS48_CHECKPOINT_01_PREFLIGHT_PASS.json (CI run 34242094044) |
| strict no-request-echo (G48-06) | PASS | WS48_CHECKPOINT_03 (CI run 34260903310) |
| Construction 107 (G48-07) | PASS | WS48_CHECKPOINT_03: 107/107 RUNTIME_VERIFIED |
| independent native-readback normalization (G48-08) | PASS | WS48_CHECKPOINT_04: 107/107 (CI run 34263710979) |
| Behavior 107 (G48-09) | NOT_RUN | inventory+shape probe only (see §3) |
| AF04/AF05/AF06/AF08/AF09 | UNKNOWN | no fresh behavior-dependent evidence yet |
| CARD_02 | NOT_RUN | construction row PASS only; behavior not executed |
| hidden-information adversarial | PARTIAL | noecho knowledge probes PASS; full HI evidence UNKNOWN |
| RNG/replay | NOT_RUN | contract has 5 replay_rng rows + RNG probes in noecho gate |
| unsupported/fallback-zero | PARTIAL | 6 fail_closed_probe rows in denominator; runtime NOT_RUN |
| terminal evidence closure | NOT_RUN | — |

Earliest failing production-relevant gate: **G48-09 behavior** (NOT_RUN).

## 3. BEHAVIOR CONTRACT SHAPE (locally reproduced)

`artifacts/ws48-behavior-shape/INVENTORY.json` built locally from immutable
materialization: denominator=107, decision_count=92, modes={NATIVE_STATE_LOAD:100,
NATURAL_GAME_START:7}. Decision families: priority 23, mulligan 21, target 11,
choose_mode 9, choice 5, replacement_effect 5, declare_attacker 4, mana_payment 3, ...
Selector kinds include semantic_action 44, boolean 10, semantic_mode_key 7,
fail_closed_probe 6, semantic_player 4, ... Native procedure ops include
NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE ×76, NATIVE_CAST_SPELL ×15,
NATIVE_RESOLVE_TOP_OF_STACK ×16, EXTERNAL_SUBMIT_SELECTED_SEMANTIC_RESPONSE ×24,
NATIVE_CONTINUE_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES ×19, plus combat / trigger /
commander-zone / replay-checkpoint / negative-probe ops.

## 4. KEY ARCHITECTURAL FINDING

The generated provider (`scripts/ws23_generate_forge_vertical_provider.py` →
`ws25` → `finalist` → `ws40` overlays) already implements an interactive
Rules-Core-owned decision surface: `Broker.choosePriority` enumerates native legal
actions via `Card.getAllPossibleAbilities(actor, true)` and emits DECISION_FRAME
kind `priority`; `chooseSpellAbilityToPlay`/`playChosenSpellAbility` use native
`PlaySpellAbility`; mode/target/mana/combat-damage choices are externally selected
**only from core-authorized options** (opaque option ids). Fail-closed on
zero/multiple-match is a harness-side obligation.

Gap for behavior: DECISION_FRAME options carry opaque labels
(`PASS`/`FORGE_LEGAL_ACTION`/`NATIVE_OPTION`); the harness cannot map a
`semantic_action` (e.g. cast obj:micro-growth) to the offered option without a
provider-emitted semantic descriptor per option. Fix must be provider-side
observation enrichment (labels only, enumeration stays in Rules Core), never
pilot-side legality reconstruction. Event stream (`expected_events`) likewise needs
a provider-emitted native event feed; currently only snapshots exist.

## 5. NEXT

Phase B: verify Forge clone → build forge-game → compile provider → reproduce one
construction case locally, then construction subset, then design behavior runner.
