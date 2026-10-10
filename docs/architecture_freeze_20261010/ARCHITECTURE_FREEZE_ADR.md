# Architecture Freeze ADR — final, awaiting the Owner's signature

Status: **FINAL, UNSIGNED.** Every slot of
`docs/architecture_freeze_readiness_20260927/ARCHITECTURE_FREEZE_ADR_TEMPLATE.md` is
filled from sealed evidence or from the Owner decisions recorded in
`OWNER_DECISIONS_20261010.md`. `ARCHITECTURE_FREEZE = NOT_CLAIMED` and
`provider_decision = NO_PROVIDER_READY` stay in force until the Owner signs (§ Signature).
Nothing in this file claims the Freeze before that signature.

Refs #662, #255. Supersedes the owner draft in `docs/architecture_freeze_owner_draft_20261010/`.

## 0. Evidence basis

The sealed epoch `f881d56fb33f-aef9f7f660b4` was produced by PB-03 run 38066157470 on
`main@f881d56fb33fab3fc58c08de51b732614a1457c1` (tree
`aef9f7f660b47739df92ba8c19028e1067b6614f`). That head carries everything the Freeze
rests on:
- the full-game capability proofs (#675, #678);
- the strict causal probe helpers (#681);
- the protocol schema identity binding (#693);
- the engine-verify required set (#694).

Its XMage freeze record (`FREEZE_RECORD_XMAGE.json` next to this file) is eligible:
- `scripts/assemble_freeze_record.py` gives `freeze_eligible=True` with 0 reasons;
- `freeze_readiness.check_freeze_eligibility` gives `(True, [])`;
- XMage AF00–AF11 are all PASS;
- FULL107 is 107/107 PASS.

Judged under the SLOT-06 ruling (`docs/slot06_capability_ruling_20261009/SLOT06_RULING.md`):
- **capability set:** exactly one, the production lane `full-game`;
- **capabilities:** the 11 required capabilities are credited from executed in-epoch
  evidence: 9 from native receipts, `engine_shutdown_supported` from AF01 plus the
  `XmageFullGameShutdownGameTest` receipt, and `headless_supported` from AF01;
- **gates:** every lane-surface gate has its production-lane component.

## 1. RULES_CORE

**XMage** (Owner decision D1). It is the single authority for legality, costs, stack,
priority, targets, modes, choices, combat, triggers, replacement effects, layers,
state-based actions, zones, Commander and multiplayer rules, and Rules randomness.
Forge stays a reference column only.

## 2. PRODUCTION_PROVIDER

**XMage** (D1; equal to RULES_CORE). It takes effect with the Owner's signature. Until
then `config/rules_engines.json` keeps `production_provider: null` and
`provider_selected: false`.

The application still launches the B4-D compatibility bridge
(`production_bridge: b4d_event_log_lifecycle_bridge`). The compatibility-lane AF01 of
this epoch derives its missing list as `action_submission_supported`,
`legal_actions_supported` and `replay_supported`, so `engine-verify` stays `degraded`.
Moving the application runtime to the proven full-game lane is decision D5, after
signature.

## 3. ENGINE_REPOSITORY

`https://github.com/moeendres-png/mage.git` (MIT; compatibility fork, unreleased).

## 4. ENGINE_COMMIT

`b479fe74fd1eaf899ff16c6a9203e74a91c0f339` (reported by the engine in AF01; pinned in
`config/rules_engines.json`).

## 5. ENGINE_TREE

`1ff64c794b1f992a8596c0b1b9952055520ccd10`. Verified on 2026-10-10 against a fresh fetch
of `moeendres-png/mage@b479fe74`.

## 6. ENGINE_BUILD_ARTIFACT

`org.mage:mage:1.4.61` (`mage-1.4.61.jar`, 7,107,605 bytes), as reported by
`get_provider_version` on the production lane (AF01).

## 7. ENGINE_BUILD_SHA256

`ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d`. Sources: AF01 `engine_identity.get_provider_version_payload.engine_artifact_sha256`
and `source_lock.build.artifact_sha256` of this epoch's record.

The jar build of `b479fe74` is **not byte-reproducible**. Two PB-03 builds of the same
commit gave jars of identical size but different SHA-256: `3bede866…` in epoch
`85dbcb1ac475-9824c55d5ef2`, and this one. The pin therefore binds exactly the bytes this
epoch built and qualified. The production base must keep that artifact. Any rebuild is
a new artifact and must be re-qualified (PB-03) before use.

## 8. PROTOCOL_VERSION

`2.0.0`: the record's `transport_protocol_version` and the protocol schema's
`protocol_version`, under the qualification boundary
`commander-lab.pre-freeze-qualification/2.0.0`.

## 9. PROTOCOL_SCHEMA_IDENTITY

`git-blob:9818d20ee1309e4fde522ffbfe5340eea5145d73`
(`schemas/engine_adapter_protocol.schema.json`). The freeze contract's const is bound
to the real file blob, and the assembler refuses eligibility on any mismatch (drift
guard). The pre-freeze source lock's `ea8651f7` stays as provenance. It differs only by
the additive `get_constructed_state` message type.

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
- **SLOT-03 shim:** the decision-identity envelope is `decision_id` plus
  `decision_offset`, with the request binding above. The bridge never reconstructs
  legality: options are the native callback's, projected unchanged.

## 11. PROCESS_TOPOLOGY

AF11 PASS: one provider process per game, and the pilot is external to the provider
process.

D17, the in-JVM residual risk, is accepted for the Freeze as a bounded, compensated
limitation (Owner decision D2). It binds every run to two conditions:
1. Pilots always run out of process.
2. No third-party or pilot code runs inside the engine JVM. Only the Lab's own reviewed
   adapter code does, under the AF05 proofs.

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

Schema pins:
- Every message of these contracts is defined by the protocol schema
  `schemas/engine_adapter_protocol.schema.json`, `git-blob:9818d20e…` (§9), on protocol
  `2.0.0`.
- The freeze contract is `qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json`
  at `main@f881d56f`.

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

- One game per OS process (AF11).
- Under D2, pilots stay out of process and no foreign code runs in the engine JVM.
- Stronger isolation (for example a sandboxed engine process with a minimal adapter
  surface) is a post-Freeze gate. It must hold before any untrusted pilot is admitted.

## 23. ACTUAL_CARD_QUALIFICATION_BOUNDARY

AF07 PASS, with the actual-card records `ACTUAL_CARD_XMAGE.json` and
`ACTUAL_CARD_CAMPAIGN_XMAGE.json` in this epoch.

## 24. MULTIPLAYER_COMMANDER_BOUNDARY

FULL107: 107/107 PASS (`FULL107_XMAGE_RESULTS.json`; 0 BLOCKED, FAIL or UNKNOWN). AF08
PASS. `commander_supported` comes from `XmageFullGameTaxExecutionTest` and
`XmageFullGamePartnerExecutionTest`.

## 25. INTEROP_LICENSE_TOPOLOGY

XMage is MIT (Owner decision D3):
- Production code lives in a private production repository and consumes the pinned
  fork artifact.
- The fork stays minimal, and its diff to upstream is documented so that repins stay
  feasible.
- MIT places no copyleft obligation on the private repository; the notices are kept.

## 26. SOURCE_LOCK

- **Lab (adapter source):** `f881d56fb33fab3fc58c08de51b732614a1457c1`, tree
  `aef9f7f660b47739df92ba8c19028e1067b6614f`.
- **Provider:** `moeendres-png/mage@b479fe74fd1eaf899ff16c6a9203e74a91c0f339`, tree
  `1ff64c794b1f992a8596c0b1b9952055520ccd10`.
- **Artifact:** `mage-1.4.61.jar` (7,107,605 bytes), sha256
  `ebcb7006e4e90237e82a5e27eca5dd260dfc4e9f1cf7aa851de9356740c02f2d` (the bytes this epoch built and qualified; see §7, the build is not
  reproducible).
- **Protocol schema:** `git-blob:9818d20ee1309e4fde522ffbfe5340eea5145d73`.
- **Epoch seal:** `CURRENT_BOUNDARY_SHA256SUMS` of `f881d56fb33f-aef9f7f660b4`.

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

These are tracked as follow-ups (#675, #681) and do not block the Freeze:
- S1 routing is checked against the accepted record, not the native return. This is a
  known weakness of the credited S1 proof, not a fail-closed path;
- the causal pass window has no upper position bound (outside the decision, bounded
  by the row's own stop);
- the hold and empty-block causal paths have not been exercised on credited rows
  (they fail closed on any undeclared combat frame).

## 30. QUALIFICATION_EVIDENCE

Every file of the sealed epoch `qualification/current-boundary-epochs/f881d56fb33f-aef9f7f660b4`:
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
- 11/11 required capabilities are credited from in-epoch evidence: 9 from native
  receipts, engine shutdown from AF01 plus its receipt, headless from AF01;
- `architecture_winner: false`.

The Freeze is claimed only by the Owner's signature below.

---

## Coordinator-fill checklist

- [x] RULES_CORE / PRODUCTION_PROVIDER bound to XMage (D1, effective at signature)
- [x] ENGINE pin bound and verified: repository, commit, tree, artifact, SHA-256
- [x] BRIDGE_ARCHITECTURE references the SLOT-03 shim as implemented
- [x] PROCESS_TOPOLOGY satisfies AF11; D17 accepted as bounded under D2
- [x] PLAYER_COUNTS_SUPPORTED has AF02 evidence; the rest fail closed
- [x] HIDDEN_INFORMATION_MODEL: AF05 production-lane proofs
- [x] Contracts pinned to the protocol schema blob and protocol version
- [x] FAILURE_SEMANTICS and PROCESS_ISOLATION concrete
- [x] Card and multiplayer boundaries: AF07, AF08, FULL107 107/107
- [x] INTEROP_LICENSE_TOPOLOGY: MIT, private production repository (D3)
- [x] SOURCE_LOCK complete
- [x] SUPPORTED and UNSUPPORTED paths explicit, with fail-closed behavior
- [x] QUALIFICATION_EVIDENCE attached by exact identity
- [x] AF00–AF11: twelve PASS records in `FREEZE_RECORD_XMAGE.json`

## Signature

- [ ] `ARCHITECTURE_FREEZE = CLAIMED`, signed by the Owner, date: ____________

After the signature the Coordinator:
1. records the Freeze (`provider_decision` and the selected provider in
   `config/rules_engines.json`);
2. starts D5, the application runtime switch to the full-game lane. Its gate is
   `engine-verify` healthy, the derived runtime missing list empty, and H4 green.
