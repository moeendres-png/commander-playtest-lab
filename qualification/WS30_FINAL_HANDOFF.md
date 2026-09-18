# WS-30 FINAL HANDOFF — Canonical Provider-Neutral Semantic Fixture Materialization Freeze

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Canonical main: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- Canonical main tree: `551c0d55a171508618d2b7d29e0f49b19893f886`
- Exact stacked neutral WS-29 base/head: `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- WS-29 tree: `e510af2fd8a05f7db874781e3182a6bf3c062fc4`
- Frozen Common manifest SHA256: `e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`
- Protocol: `commander-lab.rules-service/1.1.0`
- WS-29/current CR PDF raw-byte lock: `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`, effective 2026-08-07.
- Canonical WS-30 machine-artifact commit: `41d2ba115df759da65530fe1d585f2f5272aaa75`
- Canonical WS-30 machine-artifact tree: `27f009d17d2f67e6e4879cbd7c4a79190fa053b1`

The Coordinator-declared draft-schema SHA256 `a095c906f89c62805595cbac25488d07e201ca7b7e626098ae93cb883dc2ec6e` is provenance only. Its content was not available in supplied artifacts, connected Drive, or the exact neutral base, so it was not silently made normative.

## WS-28 Lock

- Draft PR: `#143`
- Exact final handoff head: `525bbe141ac2d6266c2278acc436c3a8576a0f8b`
- Canonical neutral orchestration head: `a93748470f2fac79ca94fe7ec770e65051ff32da`
- Binding result preserved: 18 nominal shared independent PASS; 18/18 `SETUP_NONISOMORPHIC`; `DIFFERENTIAL_AGREEMENT_PASS = 0`; no established direct engine semantic disagreement and no established direct Rules defect.
- Exact known-PASS union preserved as 18 shared + 16 historical Forge-only + 16 historical XMage-only = 50. Provider labels are provenance only and grant no credit.

## WS-29 Lock

- Draft PR: `#142`
- Exact authority base: `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- CR raw-byte lock: PASS
- Gatherer direct access: PASS
- `FULL_CURRENT_ORACLE_LOCK = 29/29`
- `DISCRIMINATOR_AUTHORITY_PASS = 29/29`
- unresolved card-authority blockers: 0
- `CARD_01`–`CARD_29` bind by exact fixture ID to `qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json`.

## Work Completed

WS-30 materializes exactly the frozen 135 Common qualification obligations as one provider-neutral semantic scenario corpus. It does not execute or select any provider and does not change WS-10R, AF mapping, denominator, fixture IDs, scoring, admission semantics, candidate code, or holdout state.

Exactly 135 unique Common IDs are present in the frozen family distribution:

- 4 player-count/lifecycle
- 17 pilot decisions
- 7 forbidden-fallback negatives
- 20 hidden-information
- 5 RNG/replay
- 17 micro-rules
- 29 actual-card
- 36 multiplayer/Commander

Every record binds to the frozen manifest by `INHERIT_BY_REFERENCE_NO_REDEFINITION`.

## Materialization Schema

- Identity: `commander-lab.semantic-fixture-materialization/1.0.0`
- File: `qualification/materialization/SEMANTIC_FIXTURE_SCHEMA_v1.json`
- Layer: above, not a redefinition of, `commander-lab.rules-service/1.1.0`
- Status values: `OBLIGATION_PRESERVED` or `MATERIALIZATION_BLOCKED_CONTRACT_AMBIGUITY`
- Validation rejects unresolved TODO/TBD/default placeholder fields.

## Semantic Identity Model

- Players: stable `P1..Pn` plus explicit seat order.
- Objects: fixture-local `semantic_id` plus stable `card_lineage_id`.
- Zone changes may create a new object incarnation while preserving card lineage where required by Magic rules.
- Commanders: stable `commander_id` independent of current zone/controller; command-zone cast counts and commander-damage matrices key on Commander identity.
- Raw UUID/JVM/memory/action/internal stack identity is never semantic identity.

## Initial-State Model

Every scenario is declarative. A provider must construct the requested semantic state inside its Rules process, run native structural validation, expose normalized constructed state, compare requested vs constructed state, and fail closed on mismatch.

Forbidden external behavior includes proprietary-side legality calculation, layers, state-based actions, replacement outcomes, fabricated legal-option sets, and silent setup correction.

`PLAYER_COUNT_2P/3P/4P/5P` are explicitly Commander lifecycle fixtures: 40 starting life, Commander in command zone, Rograkh plus 99 basic Mountains, seeded provider-native shuffle, seven-card opening hand. This is independently adjudicated from the Commander-centric frozen contract rather than either historical candidate setup.

## Knowledge-State Model

All 20 hidden-information records explicitly define viewer state, known/hidden objects or ranges, permitted public metadata, prohibited identity/metadata, temporary permissions, invalidation conditions, and prompt/context/option/source/ability/pile/state/event/transcript/log channels under test.

`HIDDEN_HONEYCARD_SENTINEL` uses deterministic sentinel `WS30_HONEY_P2_PRIVATE_7F3A`; prohibited-channel leakage is failure.

## Decision Selector Model

External discretionary decisions use semantic selectors over provider-owned legal options. Selectors may identify semantic players/objects/object sets, actions, modes/abilities, booleans, integers/X, amount assignments, ordered lists, partitions, attacker/blocker assignments and mana sources.

Invariant:

- only provider-offered legal options may be selected;
- zero matches -> `FAIL_CLOSED`;
- multiple matches -> `FAIL_CLOSED`;
- no option-index semantics;
- no first/random/default yes-no/internal AI/GUI default/silent skip/parent fallback.

The seven negative fixtures construct concrete production-reachable decisions and deliberately withhold the external handler. PASS requires typed unsupported-decision failure, never fallback continuation.

## Rules RNG / Replay Model

Rules RNG and pilot decisions remain separate. The five replay fixtures use Rules seed `424242`, provider-native Rules RNG operations, DecisionTape semantics, normalized EventTape and semantic checkpoints. Required equality is semantic event/state equality, never equality of provider-local PRNG internals or raw object identity.

## Normalization Model

Ignored provider-local properties: raw UUIDs, JVM object IDs, memory identity, internal stack object identity, engine action IDs, process IDs and wall clock.

Retained semantics: player/object/card-lineage/Commander identity, owner/controller/zone/ordered zone position where relevant, counters/attachments, Commander cast count/damage, viewer knowledge/permissions, temporal state, semantic event actor/object/value, semantic stack order and Rules RNG operation.

## Shared 18 Materialization

`qualification/materialization/DIFFERENTIAL_STARTER_18.json` contains exactly the mandated 18 in the frozen order. `qualification/materialization/CRITICAL_18_MANUAL_REVIEW.md` contains the mandatory human review explaining why each materialization preserves the frozen obligation and is independent of the historical Forge/XMage setups.

All 18 are materialization-only. No runtime or differential PASS is awarded.

## Known-PASS Union 50

`qualification/materialization/KNOWN_PASS_UNION_50.json` contains exactly the 18 shared + 16 historical Forge-only + 16 historical XMage-only IDs. Every record is the same canonical record as in the full corpus by materialization digest. Candidate partition is provenance only.

## Actual-Card 29 Integration

All `CARD_01`–`CARD_29` are exact 4P. Each binds to the corresponding WS-29 authority record, preserves its discriminator, exact card identity and CR-reference set, and adds only deterministic provider-neutral construction detail sufficient for execution. The validator rejects card-ID, card-identity, CR-reference, 4P, authority-classification or discriminator-lock mismatch.

## Full 135 Materialization

- records: **135/135**
- unique frozen IDs: **135/135**
- family counts: **4 + 17 + 7 + 20 + 5 + 17 + 29 + 36 = 135**
- contract-ambiguity blockers: **0**
- canonical semantic bundle digest: `97edd3da8e7afc28407f4d7dac94077abc8bbacf40a32aa7ecba25c62309cdf5`
- materialization JSON raw-byte SHA256: `204ccc4b1a0e4576e0a767e1c5c12cfd6b65ac5f08fdac810bd4be59df0c7ff8`

`INDEPENDENT_PASS != DIFFERENTIAL_VERIFIED` remains binding.

## Contract Ambiguities

`qualification/materialization/MATERIALIZATION_BLOCKERS.json` records `blocker_count = 0`. No frozen obligation required choosing a new Magic semantic outcome. Providers remain authoritative for legality and outcome; inability to faithfully construct a requested state must fail closed during execution.

## Validation / CI

Repository components:

- `scripts/build_ws30_materialization.py`
- `scripts/validate_ws30_materialization.py`
- `tests/qualification/test_ws30_semantic_materialization.py`
- `.github/workflows/ws30-semantic-materialization.yml`

Evidence:

1. Push materialization run `33373158188`, job `99428605419`: **PASS**. It rebuilt the corpus, validated exact repository sources, ran WS-30 tests, verified checksums, and created the canonical machine-artifact commit.
2. PR materialization run `33373372491`, job `99429270274`, executed on the real PR merge ref: **PASS**.
3. PR strict validator: **960 checks / 0 errors**.
4. PR tests: **3 passed**.
5. PR `SHA256SUMS`: all eight entries **OK**.
6. CI rebuild reproduced exactly 135 records, the required family counts, canonical bundle digest `97edd3da8e7afc28407f4d7dac94077abc8bbacf40a32aa7ecba25c62309cdf5`, and materialization SHA256 `204ccc4b1a0e4576e0a767e1c5c12cfd6b65ac5f08fdac810bd4be59df0c7ff8`.

## PASS / FAIL / UNKNOWN

| Gate | Result |
|---|---|
| Source/stack lock | PASS |
| WS-28 input lock | PASS |
| WS-29 authority lock | PASS |
| schema separate from WS-10R | PASS |
| 135/135 canonical records | PASS |
| exact frozen ID set | PASS |
| Shared 18 manual review | PASS |
| Known-PASS union 50 | PASS |
| Card 29 WS-29 integration | PASS |
| Knowledge/decision/replay/normalization/setup contracts | PASS |
| repository/PR materialization CI | PASS |
| candidate runtime execution | NOT_RUN / OUT_OF_SCOPE |
| differential agreement | NOT_RUN / OUT_OF_SCOPE |
| Rules Core selection | NOT_RUN / OUT_OF_SCOPE |

**WS-30 FINAL VERDICT: PASS.**

## Outputs

Machine outputs:

- `qualification/materialization/SEMANTIC_FIXTURE_SCHEMA_v1.json`
- `qualification/materialization/SEMANTIC_FIXTURE_MATERIALIZATION_v1.json`
- `qualification/materialization/SEMANTIC_FIXTURE_MATERIALIZATION_v1.sha256`
- `qualification/materialization/MATERIALIZATION_BLOCKERS.json`
- `qualification/materialization/MATERIALIZATION_AUTHORITY_MAP.json`
- `qualification/materialization/DIFFERENTIAL_STARTER_18.json`
- `qualification/materialization/KNOWN_PASS_UNION_50.json`
- `qualification/materialization/SHA256SUMS`

Additional outputs:

- `qualification/materialization/CRITICAL_18_MANUAL_REVIEW.md`
- `scripts/build_ws30_materialization.py`
- `scripts/validate_ws30_materialization.py`
- `tests/qualification/test_ws30_semantic_materialization.py`
- `.github/workflows/ws30-semantic-materialization.yml`
- `qualification/WS30_FINAL_HANDOFF.md`

## Draft PR

- Draft PR: **#144**
- URL: `https://github.com/moeendres-png/commander-playtest-lab/pull/144`
- Base: `ws29/canonical-authority-closure` at exact WS-29 head `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- Machine-artifact head: `41d2ba115df759da65530fe1d585f2f5272aaa75`
- State: OPEN, DRAFT, UNMERGED

## Dependencies Unblocked

WS-30 unblocks identical same-fixture execution of the exact Shared 18, expansion to the exact Known-PASS Union 50, and later full-135 provider execution from one canonical semantic corpus. It makes future differential execution meaningful without adopting either finalist's historical setup.

## Exact Next Action

Start a new provider-execution workstream using `DIFFERENTIAL_STARTER_18.json`. Each finalist must independently construct and native-validate the exact canonical state, execute only canonical semantic selectors, emit normalized semantic evidence, and only then classify differential agreement/disagreement.

Do not select a Rules Core in WS-30.
