# Architecture Freeze ADR — Owner draft (not a Freeze)

Status: **OWNER DRAFT. Nothing here is claimed.** `ARCHITECTURE_FREEZE = NOT_CLAIMED`
and `provider_decision = NO_PROVIDER_READY` stay in force until the Owner decides
(AGENTS.md §8, Owner-only reservation). This draft follows
`docs/architecture_freeze_readiness_20260927/ARCHITECTURE_FREEZE_ADR_TEMPLATE.md`. It fills
every slot that sealed evidence settles and marks every slot that is an Owner decision
or still unbound as **OWNER-DECISION** or **NOT BOUND**.

Refs #662 (step 4), #255.

## 0. Why this draft exists

The sealed epoch `85dbcb1ac475-9824c55d5ef2` was produced by PB-03 run 38050485330 on
`main@85dbcb1ac475f9b9dba56f4aa5634bb2997ac5c9` (tree `9824c55d5ef2…`). It is the
first epoch whose XMage freeze record is eligible:

- `scripts/assemble_freeze_record.py` gives `freeze_eligible=True` with 0 reasons;
- `freeze_readiness.check_freeze_eligibility` gives `(True, [])`.

The SLOT-06 ruling (`docs/slot06_capability_ruling_20261009/SLOT06_RULING.md`) defines
how this is judged:
- **capability set:** exactly one, the production lane `full-game` (AF01 on that lane);
- **capabilities:** every one of the 11 required capabilities is credited only from
  executed in-epoch native receipts of its proof classes (`freeze_record.CAPABILITY_PROOF`);
- **gates:** every lane-surface gate has its production-lane component.

An eligible record is a decision input for the Owner, not a Freeze.

## 1. RULES_CORE

**OWNER-DECISION.** The evidence supports exactly one candidate: **XMage**. Forge is a
reference column only (Owner decision 2, `docs/engine_strategy_20261009`).

## 2. PRODUCTION_PROVIDER

**OWNER-DECISION** (must equal RULES_CORE). `PRODUCTION_PROVIDER = NOT SELECTED`.
`config/rules_engines.json` keeps `production_provider: null` and
`provider_selected: false`.

## 3. ENGINE_REPOSITORY

`https://github.com/moeendres-png/mage.git` (MIT; compatibility fork, unreleased).

## 4. ENGINE_COMMIT

`b479fe74fd1eaf899ff16c6a9203e74a91c0f339` (reported by the engine in AF01; pinned in
`config/rules_engines.json`).

## 5. ENGINE_TREE

`1ff64c794b1f992a8596c0b1b9952055520ccd10`, the engine tree pinned for `b479fe74` and
recorded in the provider readiness packet's engine pins. Re-verify it against a fresh
checkout at Freeze.

## 6. ENGINE_BUILD_ARTIFACT

`org.mage:mage:1.4.61` (`mage-1.4.61.jar`, 7,107,605 bytes), as reported by
`get_provider_version` on the production lane (AF01).

## 7. ENGINE_BUILD_SHA256

`3bede866e142de66631e04bfc611424e835ed2c95e2b736cd5f638615c2dc660` (AF01
`engine_identity.get_provider_version_payload.engine_artifact_sha256`).

## 8. PROTOCOL_VERSION

`2.0.0` (`commander-lab.pre-freeze-qualification/2.0.0`).

## 9. PROTOCOL_SCHEMA_IDENTITY

`git-blob:ea8651f75a1461ecc41dc1f24586c00bff97fee5`
(`schemas/engine_adapter_protocol.schema.json`). Re-verify at Freeze.

## 10. BRIDGE_ARCHITECTURE

- **Transport:** stdin/stdout JSONL, the `XmageFullGameJsonlBridge` production lane.
  Decisions are projected unchanged from the native callback through
  `XmageFullGameActionProjection`.
- **Decision identity:** `decision_id` plus `decision_offset`. A request may name
  `game_id`, `actor_id` or `decision_class`; any mismatch fails closed with
  `UNKNOWN_GAME`, `WRONG_ACTOR` or `UNSUPPORTED_DECISION_CLASS` (#667).
- **Fail-closed codes:**
  - `STALE_DECISION`, `PILOT_RESPONSE_INVALID`, `ILLEGAL_ACTION`;
  - `UNSUPPORTED_DECISION_CLASS` / `UNDECLARED_DECISION_CLASS`, `UNPROJECTABLE_DECISION`;
  - `FULL_GAME_SHUT_DOWN`, `FULL_GAME_ALREADY_TERMINAL`.
- **SLOT-03 shim reference:** **OWNER-DECISION** to confirm.

## 11. PROCESS_TOPOLOGY

AF11 PASS in this epoch: one provider process per game, and the pilot is external to
the provider process. **OWNER-DECISION** remains on the D17 in-JVM residual risk, which
is **not accepted**.

## 12. PLAYER_COUNTS_SUPPORTED

2P, 3P, 4P and 5P are required, with AF02 PASS (`PLAYER_CARDINALITY_XMAGE.json`,
`required_counts [2,3,4,5]`). 6P is bounded-secondary.

## 13. PLAYER_COUNTS_FAIL_CLOSED

Every other count fails closed with a typed error before a game starts
(`XmageFullGamePlayerCountTest`).

## 14. HIDDEN_INFORMATION_MODEL

AF05 PASS. The model is principal-scoped projection: `XmageFullGameHiddenInformationTest`
plus `XmageFullGameLegalActionsPrincipalTest`. A foreign principal is refused, and no
other hand or library card is named in the actor's frame. The event log names no card
that is only in hidden zones (`XmageFullGameEventLogTest`).

## 15–18. OBSERVATION / LEGAL_ACTION / DECISION / TARGET-MODE-CHOICE CONTRACTS

These are defined by the SLOT-06 ruling (a) definitions L1–L4 and S1–S3. The proofs are:
- `XmageFullGameDecisionClassMatrixTest`: 25 tests, 17 decision classes, an engine-API
  oracle, typed S2 rejections with unchanged privileged state;
- `XmageFullGameDecisionClassInventoryTest`;
- `XmageFullGameUnprojectableDecisionTest`;
- `XmageFullGameCancelRewindTest`.

Schema file and version pins: **NOT BOUND**, to be bound at Freeze.

## 19. RULES_RNG_CONTRACT

`seed_supported` comes from `XmageFullGameRulesSeedBindingTest`: an explicit per-game
Rules seed bound before start, with XMage owning Rules randomness. AF03 PASS.

## 20. SEMANTIC_REPLAY_CONTRACT

- **Export:** `export_replay`, schema `xmage-full-game-replay/1.1.0`.
- **Verifier:** a fresh JVM, `Main full-game-replay`. Every tamper class is reported
  as DIVERGED.
- **Proofs:** `XmageFullGameReplayExportTest` and `XmageFullGameReplayTwinTest`. AF09 PASS.
- **Bit-exact replay** remains unclaimed (`bit_exact_replay_validated=false`).

## 21. FAILURE_SEMANTICS

Typed failures as in §10. A rejected submission leaves the game unchanged: the
privileged state digest and the transcript are unchanged (matrix S2). A cancelled
proposal is rewound to the pre-proposal state, including partial payment (S3). A
provider failure ends the game as a recorded terminal failure.

## 22. PROCESS_ISOLATION

One game per process (AF11). The isolation mechanism beyond the OS process boundary:
**OWNER-DECISION**.

## 23. ACTUAL_CARD_QUALIFICATION_BOUNDARY

AF07 PASS, with the actual-card records `ACTUAL_CARD_XMAGE.json` and
`ACTUAL_CARD_CAMPAIGN_XMAGE.json` in this epoch.

## 24. MULTIPLAYER_COMMANDER_BOUNDARY

FULL107: 107/107 PASS (`FULL107_XMAGE_RESULTS.json`; 0 BLOCKED, FAIL or UNKNOWN). AF08
PASS. `commander_supported` comes from `XmageFullGameTaxExecutionTest` and
`XmageFullGamePartnerExecutionTest`.

## 25. INTEROP_LICENSE_TOPOLOGY

XMage is MIT. The consequences for the private production repository are
**OWNER-DECISION**.

## 26. SOURCE_LOCK

- **Lab:** `85dbcb1ac475f9b9dba56f4aa5634bb2997ac5c9`, tree
  `9824c55d5ef2fe391f9a302c2035290ebb31a0ca`.
- **Provider:** `moeendres-png/mage@b479fe74fd1eaf899ff16c6a9203e74a91c0f339`.
- **Artifact:** `mage-1.4.61.jar`, sha256 `3bede866…c660`.
- **Epoch seal:** `CURRENT_BOUNDARY_SHA256SUMS` of `85dbcb1ac475-9824c55d5ef2`.

The adapter source tree and the contract blobs are **NOT BOUND** here; bind them at
Freeze.

## 27. SUPPORTED_PATHS

- 2P to 5P (6P bounded).
- The 17 declared decision classes on the full-game lane (matrix).
- Commander deck import.
- Explicit-seed games.
- Replay export with fresh-JVM verification.
- `shutdown_game` and engine shutdown.

Each item names its proof in `FREEZE_RECORD_XMAGE.json` → `proof_ledger`.

## 28. UNSUPPORTED_PATHS (fail closed)

- **Player counts:** any count outside 2–6 (§13).
- **Undeclared decision classes:** `UNDECLARED_DECISION_CLASS`.
- **Optionless decisions:** a decision with no options and no numeric domain gives
  `UNPROJECTABLE_DECISION`.
- **Land-or-spell:** an undeclared engine caller of the land-or-spell callback (at the
  pin, Vault 112: Sadistic Simulation) gives `UNSUPPORTED_DECISION_CLASS`.
- **Controlled turns (CR 723):** decision frames during a controlled turn have no
  engine-API oracle (L1 is not proven for them).

## 29. KNOWN_BOUNDED_LIMITATIONS

The #675 and #681 follow-ups:
- S1 routing is checked against the accepted record, not the native return;
- the causal pass window has no upper position bound;
- the hold and empty-block causal paths have not been exercised on credited rows.

## 30. QUALIFICATION_EVIDENCE

Every file of the sealed epoch `qualification/current-boundary-epochs/85dbcb1ac475-9824c55d5ef2`:
- AF01, a 20-invariant run on lane `full-game`;
- player cardinality;
- FULL107;
- hidden information;
- RNG and replay;
- the actual-card records;
- `NATIVE_SUITE_RECEIPTS.json` and `receipts/`;
- the comparison and divergence packets.

## 31. AF00_AF11_RESULTS

All twelve gates, AF00 through AF11, are PASS in `FREEZE_RECORD_XMAGE.json`
(`record.gate_results`). Each lane-surface gate is bound to its production-lane
component (`LANE_SURFACE_COMPONENTS`).

## 32. FREEZE_ELIGIBILITY

`freeze_eligible: true` for the XMage record:
- `missing_required_capabilities: []`;
- 11/11 required capabilities are credited from in-epoch receipts;
- `architecture_winner: false`.

**The Freeze itself is the Owner's decision and is not claimed by this draft.**

---

## Owner checklist (open)

- [ ] RULES_CORE / PRODUCTION_PROVIDER selection (§1–2)
- [ ] ENGINE_TREE re-verified (§5); adapter/contract blobs bound (§26)
- [ ] SLOT-03 shim reference confirmed (§10)
- [ ] D17 in-JVM residual risk decision (§11). It is currently NOT accepted.
- [ ] Process isolation mechanism (§22) and license topology (§25)
- [ ] Contract schema pins (§15–18)
- [ ] `ARCHITECTURE_FREEZE = CLAIMED`, recorded by the Owner with date
