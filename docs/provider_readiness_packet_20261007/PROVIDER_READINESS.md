# Provider-readiness packet - section F (issue #255)

Evidence summary only. It selects no provider, ranks no candidate and makes no recommendation. Provider adjudication is Coordinator-owned in issue #255; provider selection and Architecture Freeze are Owner-reserved.

`PRODUCTION_PROVIDER = NOT_SELECTED` | `ARCHITECTURE_FREEZE = NOT_CLAIMED` | `PRODUCTION_REPOSITORY = NOT_CREATED`

## Source lock

- Packet branch: `evidence/provider-readiness-packet-20261007` from `1d605a5883c1a8dd1de87d5a9261c74768c65f16` (tree `34bc6cef608dec6ca2c0ae470932c709ea28b1eb`).
- Sealed epoch: `b1c8f54a999a-2d13b953a82c`; manifest `qualification/current-boundary-epochs/b1c8f54a999a-2d13b953a82c/CURRENT_BOUNDARY_SHA256SUMS` sha256 `dddc3cb1a6fd5eb0d89fde8706b34fbdb9884ca8d189d1b8320075627c8ce385`; 194/194 digests verified (EXACT_ALL_FILES_EXCEPT_MANIFEST).
- Effective contract: `commander-lab.full107/1.0.22-successor` (`qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_22.json` sha256 `f52cd34e221dca8f86eff51b8490e994cd1286cfacda33ce0b8011d86a00f27e`); pointer sha256 `da111ba14910d889240dc7c464d9a57b92e6fd0214becf8a960c384b92f10604`.
- Engine pins (`config/rules_engines.json` sha256 `1eea3b67946fd93e951af96d9f868268bc6c2616640f590bfd71ce127ad323dd`): XMage `b479fe74` / tree `1ff64c79`; Forge Rules-Core `bb0a740d` / tree `4989b5bb`; Forge bridge `31cbae12` / tree `b5c19c19`.

## Drift records

| Subject | Pin | Sealed evidence | Verdict |
| --- | --- | --- | --- |
| xmage engine commit | `b479fe74fd1eaf899ff16c6a9203e74a91c0f339` | `b479fe74fd1eaf899ff16c6a9203e74a91c0f339` | IDENTICAL |
| forge Rules-Core commit | `bb0a740d2bef725194798383c2452213ecdd0b37` | `bb0a740d2bef725194798383c2452213ecdd0b37` | IDENTICAL |
| forge bridge/materialization commit | `31cbae12640e6066499aa7f17c9bf2dba6a30da6` | `31cbae12640e6066499aa7f17c9bf2dba6a30da6` | IDENTICAL |
| effective fixture contract | `commander-lab.full107/1.0.22-successor` | `commander-lab.full107/1.0.22-successor` | IDENTICAL |

## Dimensions

| # | Dimension | XMage | XMage non-PASS fixtures | Forge | Forge non-PASS fixtures |
| --- | --- | --- | --- | --- | --- |
| 1 | Rules authority separation | PASS | - | PASS | - |
| 2 | Legal actions / submission | UNKNOWN | - | UNKNOWN | PILOT_ANNOUNCE_X, PILOT_CHOICE, PILOT_CHOOSE_ABILITY, PILOT_CHOOSE_MODE, PILOT_CHOOSE_OBJECT, PILOT_CHOOSE_USE, PILOT_DECLARE_ATTACKER, PILOT_DECLARE_BLOCKER, PILOT_MANA_PAYMENT, PILOT_MULTI_AMOUNT, PILOT_PILE, PILOT_PRIORITY, PILOT_REPLACEMENT_EFFECT, PILOT_TARGET, PILOT_TARGET_AMOUNT, PILOT_TRIGGER_ORDER |
| 3 | Costs / mana | UNKNOWN | - | UNKNOWN | MICRO_COSTS, MICRO_MANA_PAYMENT, PILOT_MANA_PAYMENT |
| 4 | Stack / priority | UNKNOWN | - | UNKNOWN | MICRO_PRIORITY, MICRO_STACK, WS05-MP-PRIO-3, WS05-MP-PRIO-5 |
| 5 | Targets / modes / choices | UNKNOWN | - | UNKNOWN | MICRO_MODES, MICRO_TARGETS, PILOT_ANNOUNCE_X, PILOT_CHOICE, PILOT_CHOOSE_ABILITY, PILOT_CHOOSE_MODE, PILOT_CHOOSE_OBJECT, PILOT_CHOOSE_USE, PILOT_MULTI_AMOUNT, PILOT_PILE, PILOT_TARGET, PILOT_TARGET_AMOUNT |
| 6 | Triggers | UNKNOWN | - | UNKNOWN | MICRO_TRIGGERS, PILOT_TRIGGER_ORDER, WS05-MP-TRIG-3, WS05-MP-TRIG-5 |
| 7 | Replacement / prevention | UNKNOWN | - | UNKNOWN | MICRO_PREVENTION, MICRO_REPLACEMENT, PILOT_REPLACEMENT_EFFECT |
| 8 | Continuous effects / layers | UNKNOWN | - | UNKNOWN | MICRO_CONTINUOUS_EFFECTS, MICRO_LAYERS |
| 9 | State-based actions | UNKNOWN | - | UNKNOWN | MICRO_STATE_BASED_ACTIONS |
| 10 | Zones | UNKNOWN | - | UNKNOWN | MICRO_ZONE_CHANGES, WS05-CMD-ZONE-LIB-NO, WS05-CMD-ZONE-LIB-YES |
| 11 | Copy / control | UNKNOWN | - | UNKNOWN | MICRO_CONTROL, MICRO_COPY, WS05-CMD-DMG-CONTROL |
| 12 | Combat | UNKNOWN | - | UNKNOWN | MICRO_COMBAT, PILOT_DECLARE_ATTACKER, PILOT_DECLARE_BLOCKER, WS05-MP-BLOCK-4, WS05-MP-COMBAT-4, WS05-MP-COMBAT-5 |
| 13 | Commander rules | UNKNOWN | WS05-CMD-MULL-2 | UNKNOWN | WS05-CMD-DMG-CONTROL, WS05-CMD-DMG-SAME-21, WS05-CMD-ELIM-4, WS05-CMD-MULL-2, WS05-CMD-PARTNER-TAX, WS05-CMD-START-3, WS05-CMD-TAX-2, WS05-CMD-TAX-4, WS05-CMD-ZONE-LIB-NO, WS05-CMD-ZONE-LIB-YES |
| 14 | Multiplayer 2-5P | UNKNOWN | - | UNKNOWN | WS05-MP-BLOCK-4, WS05-MP-COMBAT-4, WS05-MP-COMBAT-5, WS05-MP-ELIM-CONTROL-3, WS05-MP-ELIM-TURN-3, WS05-MP-PRIO-3, WS05-MP-PRIO-5, WS05-MP-TRIG-3, WS05-MP-TRIG-5, WS05-MP-TURN-3, WS05-MP-TURN-5 |
| 15 | Bounded 6P | UNSUPPORTED | - | NOT_RUN | - |
| 16 | Hidden information | PASS | - | UNKNOWN | HIDDEN_01, HIDDEN_02, HIDDEN_03, HIDDEN_04, HIDDEN_05, HIDDEN_06, HIDDEN_07, HIDDEN_08, HIDDEN_09, HIDDEN_10, HIDDEN_11, HIDDEN_12, HIDDEN_13, HIDDEN_14, HIDDEN_15, HIDDEN_16, HIDDEN_17, HIDDEN_18, HIDDEN_19, HIDDEN_HONEYCARD_SENTINEL |
| 17 | Rules RNG | PASS | - | UNKNOWN | MICRO_RULES_RANDOMNESS, RNG_RULES_TAPE |
| 18 | Semantic replay | PASS | - | UNKNOWN | REPLAY_CLEAN_PROCESS, REPLAY_DECISION_TAPE, REPLAY_EVENT_TAPE, REPLAY_STATE_HASHES |
| 19 | Process isolation | UNKNOWN | - | UNKNOWN | - |
| 20 | Fail-closed unsupported paths | UNKNOWN | NEGATIVE_PARENT_CLASS_FALLBACK | UNKNOWN | NEGATIVE_DEFAULT_YES_NO, NEGATIVE_FIRST_OPTION, NEGATIVE_GUI_DEFAULT, NEGATIVE_INTERNAL_AI, NEGATIVE_PARENT_CLASS_FALLBACK, NEGATIVE_RANDOM_OPTION, NEGATIVE_SILENT_SKIP |
| 21 | Actual-card runtime coverage | PASS | - | UNKNOWN | CARD_02 |

Backing AF verdicts per dimension:

| # | Dimension | XMage AFs | Forge AFs |
| --- | --- | --- | --- |
| 1 | Rules authority separation | AF00=PASS, AF03=PASS | AF00=PASS, AF03=PASS |
| 2 | Legal actions / submission | AF04=UNKNOWN | AF04=UNKNOWN |
| 3 | Costs / mana | AF06=UNKNOWN | AF06=UNKNOWN |
| 4 | Stack / priority | AF06=UNKNOWN | AF06=UNKNOWN |
| 5 | Targets / modes / choices | AF06=UNKNOWN | AF06=UNKNOWN |
| 6 | Triggers | AF06=UNKNOWN | AF06=UNKNOWN |
| 7 | Replacement / prevention | AF06=UNKNOWN | AF06=UNKNOWN |
| 8 | Continuous effects / layers | AF06=UNKNOWN | AF06=UNKNOWN |
| 9 | State-based actions | AF06=UNKNOWN | AF06=UNKNOWN |
| 10 | Zones | AF06=UNKNOWN | AF06=UNKNOWN |
| 11 | Copy / control | AF06=UNKNOWN | AF06=UNKNOWN |
| 12 | Combat | AF06=UNKNOWN | AF06=UNKNOWN |
| 13 | Commander rules | AF08=UNKNOWN | AF08=UNKNOWN |
| 14 | Multiplayer 2-5P | AF02=PASS, AF08=UNKNOWN | AF02=PASS, AF08=UNKNOWN |
| 15 | Bounded 6P | AF02=PASS | AF02=PASS |
| 16 | Hidden information | AF05=PASS | AF05=UNKNOWN |
| 17 | Rules RNG | AF09=PASS | AF09=UNKNOWN |
| 18 | Semantic replay | AF09=PASS | AF09=UNKNOWN |
| 19 | Process isolation | AF11=UNKNOWN | AF11=UNKNOWN |
| 20 | Fail-closed unsupported paths | AF01=PASS, AF04=UNKNOWN | AF01=PASS, AF04=UNKNOWN |
| 21 | Actual-card runtime coverage | AF07=PASS | AF07=UNKNOWN |

## Known residuals (issue-recorded state beside current sealed state)

| Residual | Candidate | Issue-recorded state | Sealed state |
| --- | --- | --- | --- |
| HIDDEN_05 | forge | UNKNOWN - face-down exile permission persistence | UNKNOWN |
| HIDDEN_06 | forge | UNKNOWN - face-down exile invalidation on zone change | UNKNOWN |
| HIDDEN_08 | forge | NOT_RUN_BLOCKED - look-audience seam | UNKNOWN |
| HIDDEN_11 | forge | UNKNOWN - shuffle/order-knowledge invalidation | UNKNOWN |
| HIDDEN_12 | forge | NOT_RUN_BLOCKED - controlled-player decision seam | UNKNOWN |
| WS05-CMD-MULL-2 | forge | NOT_RUN_BLOCKED - London bottom-choice seam | UNKNOWN |
| WS05-CMD-MULL-2 | xmage | AF08 residual - no external London-bottom decision | UNKNOWN |
| NEGATIVE_PARENT_CLASS_FALLBACK | xmage | NOT_NAMED_BY_ISSUE - observed UNKNOWN in the current sealed epoch | UNKNOWN |

## Optional metrics (never a Rules-correctness gate)

| Metric | Value |
| --- | --- |
| native_suite_receipts | 4 |
| pb03_executed_pass | 30 |

Every status above is derived from the sealed artifacts cited in `PROVIDER_READINESS.json`; `UNKNOWN != PASS`. Regenerate with `python3 scripts/build_provider_readiness_packet.py`; verify with `--check`.
