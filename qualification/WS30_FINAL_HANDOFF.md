# WS-30 FINAL HANDOFF — Canonical Provider-Neutral Semantic Fixture Materialization Freeze

## Source Lock

- Repository: `moeendres-png/commander-playtest-lab`
- Canonical main: `c83e52ae79ff2242578757c0f517badbb1a2621c`
- Canonical main tree: `551c0d55a171508618d2b7d29e0f49b19893f886`
- Exact stacked neutral WS-29 base/head: `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- WS-29 tree: `e510af2fd8a05f7db874781e3182a6bf3c062fc4`
- Frozen Common manifest SHA256: `e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4`
- Protocol: `commander-lab.rules-service/1.1.0`
- Semantic materialization schema: `commander-lab.semantic-fixture-materialization/1.0.0`
- WS-29/current CR PDF raw-byte lock: `9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c`, effective 2026-08-07.
- Latest canonical machine-artifact commit: `4b8e9f7b88369acc82ef26400a8f9b7027181761`
- Latest canonical machine-artifact tree: `1664369c5ec7e2fec61059d3cfb26c830edb748c`
- Final user-authored semantic verification head: `f9b2c92c6781de9e81b13458262dd03ff12ec089`
- Final user-authored semantic verification tree: `d1d4ba79a7bc15182431b75b168103ec3c3af123`

The final handoff commit that contains this document is documentation-only and follows the verified semantic head above; it does not change the materialization corpus, generator, validator, tests, or WS-30 workflow.

The Coordinator-declared draft-schema SHA256 `a095c906f89c62805595cbac25488d07e201ca7b7e626098ae93cb883dc2ec6e` remains provenance only. Its content was not available in supplied artifacts, connected Drive, or the exact neutral base, so unknown draft content was not silently made normative.

## WS-28 Lock

- Draft PR: `#143`
- Exact final handoff head: `525bbe141ac2d6266c2278acc436c3a8576a0f8b`
- Canonical neutral orchestration head: `a93748470f2fac79ca94fe7ec770e65051ff32da`
- Binding finding preserved: 18 nominal shared independent PASS fixtures; 18/18 `SETUP_NONISOMORPHIC`; `DIFFERENTIAL_AGREEMENT_PASS = 0`; no established engine semantic disagreement; no established direct Rules defect.
- Exact known-PASS union preserved as 18 shared + 16 historical Forge-only + 16 historical XMage-only = 50.
- Provider labels remain provenance only and grant no runtime or qualification credit.

## WS-29 Lock

- Draft PR: `#142`
- Exact authority head/base: `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- CR raw-byte lock: PASS
- Gatherer direct access: PASS
- `FULL_CURRENT_ORACLE_LOCK = 29/29`
- `DISCRIMINATOR_AUTHORITY_PASS = 29/29`
- unresolved card-authority blockers: 0
- `CARD_01`–`CARD_29` bind by exact fixture ID to `qualification/ws29/PROVIDER_NEUTRAL_EXPECTED_SEMANTICS.json`.

## Work Completed

WS-30 materializes exactly the frozen 135 Common qualification obligations as one provider-neutral semantic scenario corpus. It does not execute or select any provider and does not change WS-10R, AF mapping, denominator, fixture IDs, scoring, admission semantics, candidate code, holdout state, or Architecture Freeze.

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
- Required record content includes identity/provenance, players/seats, Commander state, semantic objects, temporal state, KnowledgeLedger-compatible viewer state, Rules randomness, external decision scripts, expected semantic events, terminal postconditions, normalization, and native setup validation.
- Validation rejects unresolved TODO/TBD/FIXME/default/placeholder fields.

## Semantic Identity Model

- Players: stable `P1..Pn` plus explicit seat order.
- Objects: fixture-local `semantic_id` plus stable `card_lineage_id`.
- Zone changes may create a new object incarnation while preserving card lineage where Magic semantics require continuity of the underlying card.
- Commanders: stable `commander_id` independent of current zone/controller; command-zone cast counts and commander-damage matrices key on Commander identity.
- Raw UUID/JVM/memory/action/internal stack identity is never semantic identity.

## Initial-State Model

Every scenario is declarative. A provider must:

1. construct the requested semantic state inside its Rules process;
2. run provider-native structural validation;
3. expose the normalized constructed state;
4. compare requested vs constructed semantic state;
5. fail closed on mismatch.

Forbidden external behavior includes proprietary-side legality calculation, layers, state-based actions, replacement outcomes, fabricated legal-option sets, and silent setup correction.

`PLAYER_COUNT_2P/3P/4P/5P` are explicitly Commander lifecycle fixtures: 40 starting life, Commander in command zone, Rograkh plus 99 basic Mountains, seeded provider-native shuffle, seven-card opening hand. This interpretation is independently adjudicated from the Commander-centric frozen project contract rather than either historical candidate setup.

## Knowledge-State Model

All 20 hidden-information records explicitly define viewer state, known/hidden objects or ranges, permitted public metadata, prohibited identity/metadata, temporary permissions, invalidation conditions, and prompt/context/option/source/ability/pile/state/event/transcript/log channels under test.

`HIDDEN_HONEYCARD_SENTINEL` uses deterministic sentinel `WS30_HONEY_P2_PRIVATE_7F3A`; leakage into prohibited channels is failure.

## Decision Selector Model

External discretionary decisions use semantic selectors over provider-owned legal options. Selectors may identify semantic players/objects/object sets, actions, modes/abilities, booleans, integers/X, amount assignments, ordered lists, partitions, attacker/blocker assignments and mana sources.

Invariant:

- only provider-offered legal options may be selected;
- zero matches -> `FAIL_CLOSED`;
- multiple matches -> `FAIL_CLOSED`;
- no option-index semantics;
- no first/random/default yes-no/internal AI/GUI default/silent skip/parent fallback;
- decision scripts never invent or enumerate legal actions independently of provider offers.

The seven negative fixtures construct concrete production-reachable discretionary decisions and deliberately withhold the external handler. PASS requires typed unsupported-decision failure, never fallback continuation.

## Rules RNG / Replay Model

Rules RNG and pilot decisions remain separate. The five replay fixtures use Rules seed `424242`, provider-native Rules RNG operations, DecisionTape semantics, normalized EventTape and semantic checkpoints. Required equality is semantic event/state equality, never equality of provider-local PRNG internals or raw object identities.

Replay fixtures bind exact initial materialization digest, seed, DecisionTape semantics, event normalization, checkpoint boundaries, and final-state equality.

## Normalization Model

Ignored provider-local properties:

- raw UUIDs
- JVM object IDs
- memory identity
- internal stack object identity
- engine action IDs
- process IDs
- wall clock values

Retained semantics include player/object/card-lineage/Commander identity, owner/controller/zone/ordered zone position where relevant, counters/attachments, Commander cast count/damage, viewer knowledge/permissions, temporal state, semantic event actor/object/value, semantic stack order and Rules RNG operation.

## Shared 18 Materialization

`qualification/materialization/DIFFERENTIAL_STARTER_18.json` contains exactly the mandated 18 in frozen order.

`qualification/materialization/CRITICAL_18_MANUAL_REVIEW.md` contains the mandatory human review explaining for every one of the 18 why the chosen materialization preserves the frozen obligation and does not adopt Forge/XMage historical setup as authority.

All 18 remain materialization-only. No runtime or differential PASS is awarded.

## Known-PASS Union 50

`qualification/materialization/KNOWN_PASS_UNION_50.json` contains exactly the 18 shared + 16 historical Forge-only + 16 historical XMage-only IDs. Every record is the same canonical record as the full 135 corpus by materialization digest. Candidate partition is provenance only.

## Actual-Card 29 Integration

All `CARD_01`–`CARD_29` are exact 4P. Each binds to the corresponding WS-29 authority record, preserves its discriminator, exact card identity and CR-reference set, and adds only provider-neutral deterministic construction detail required to make the experiment executable.

The validator rejects card-ID, card-identity, CR-reference, 4P, authority-classification, or discriminator-lock mismatch.

## Full 135 Materialization

- records: **135/135**
- unique frozen IDs: **135/135**
- family counts: **4 + 17 + 7 + 20 + 5 + 17 + 29 + 36 = 135**
- contract-ambiguity blockers: **0**
- canonical semantic bundle digest: `d4f0f78fd8307e708ccbf316f709a70c61e4e73710d16507a531620e1b7018d1`
- materialization JSON raw-byte SHA256: `c99b9947833ace9a59370c06a1a9a9cc1d01601e8b746a82c9acce84864d03c9`
- schema raw-byte SHA256: `423c1003a96aef3e817abdcf2cdf45f055960c209b399e66964030f62fbb2b8c`

The change from the earlier provisional bundle identity was caused by the branch normalization/materialization cycle before final verification. The final user-authored PR verification reproduced the values above exactly; these are the authoritative WS-30 closeout identities.

`AMBIGUITY != MATERIALIZED`, `CANDIDATE_SETUP != CANONICAL_SETUP`, and `INDEPENDENT_PASS != DIFFERENTIAL_VERIFIED` remain binding.

## Contract Ambiguities

`qualification/materialization/MATERIALIZATION_BLOCKERS.json` records `blocker_count = 0`.

No frozen obligation required choosing a new Magic semantic outcome. Providers remain authoritative for legality and Rules outcomes; inability to faithfully construct a requested state must fail closed during provider execution.

## Validation / CI

Repository components:

- `scripts/build_ws30_materialization.py`
- `scripts/validate_ws30_materialization.py`
- `tests/qualification/test_ws30_semantic_materialization.py`
- `.github/workflows/ws30-semantic-materialization.yml`

Final authoritative WS-30 verification evidence:

- user-authored semantic verification head: `f9b2c92c6781de9e81b13458262dd03ff12ec089`
- PR merge-ref tested: `61fb8262d62c7bbdf7dbabbce4253b2d0a549095`
- WS30 Semantic Materialization run: `33375457919` (run #16)
- job: `99435818795`
- conclusion: **SUCCESS**
- Ruff quality for WS-30 Python: **PASS** (`All checks passed`, 3 files already formatted)
- generator: **135 records**, exact frozen family counts
- canonical bundle digest reproduced: `d4f0f78fd8307e708ccbf316f709a70c61e4e73710d16507a531620e1b7018d1`
- raw materialization SHA256 reproduced: `c99b9947833ace9a59370c06a1a9a9cc1d01601e8b746a82c9acce84864d03c9`
- strict validator: **960 checks / 0 errors**
- WS-30 qualification tests: **3 passed**
- `SHA256SUMS`: all eight required entries **OK**

The repositorywide `CI / quality` workflow is not a WS-30 admission gate and is already red on the exact WS-29 stacked base `362d9351f749b6f49d67cd1ef4eed298b8922b68`: Ruff lint, Ruff format, and the broad test suite fail there as inherited baseline state, while security passes. WS-30's dedicated quality/validator/test workflow is independently green and its Python files pass Ruff.

## PASS / FAIL / UNKNOWN

| Gate | Result |
|---|---|
| Source/stack lock | PASS |
| WS-28 input lock | PASS |
| WS-29 authority lock | PASS |
| semantic schema separate from WS-10R | PASS |
| exactly 135 canonical records | PASS |
| exact frozen ID set / unchanged denominator | PASS |
| exact family counts 4/17/7/20/5/17/29/36 | PASS |
| stable semantic identity / no provider IDs | PASS |
| native setup-validation contract | PASS |
| fail-closed decision-selector contract | PASS |
| explicit hidden-information viewer state | PASS |
| replay/RNG/normalization contract | PASS |
| Shared 18 materialization | PASS |
| Shared 18 manual review | PASS |
| Known-PASS union 50 | PASS |
| CARD_01–CARD_29 WS-29 integration / exact 4P | PASS |
| blockers/ambiguity register | PASS — 0 blockers |
| final WS-30 PR materialization CI | PASS |
| candidate runtime execution | NOT_RUN / OUT_OF_SCOPE |
| differential agreement | NOT_RUN / OUT_OF_SCOPE |
| Rules Core selection | NOT_RUN / OUT_OF_SCOPE |

**WS-30 FINAL VERDICT: PASS.**

## Outputs

Required machine outputs:

- `qualification/materialization/SEMANTIC_FIXTURE_SCHEMA_v1.json`
- `qualification/materialization/SEMANTIC_FIXTURE_MATERIALIZATION_v1.json`
- `qualification/materialization/SEMANTIC_FIXTURE_MATERIALIZATION_v1.sha256`
- `qualification/materialization/MATERIALIZATION_BLOCKERS.json`
- `qualification/materialization/MATERIALIZATION_AUTHORITY_MAP.json`
- `qualification/materialization/DIFFERENTIAL_STARTER_18.json`
- `qualification/materialization/KNOWN_PASS_UNION_50.json`
- `qualification/materialization/SHA256SUMS`

Additional required/supporting outputs:

- `qualification/materialization/CRITICAL_18_MANUAL_REVIEW.md`
- `scripts/build_ws30_materialization.py`
- `scripts/validate_ws30_materialization.py`
- `tests/qualification/test_ws30_semantic_materialization.py`
- `.github/workflows/ws30-semantic-materialization.yml`
- `qualification/WS30_FINAL_HANDOFF.md`

## Draft PR

- Draft PR: **#144**
- URL: `https://github.com/moeendres-png/commander-playtest-lab/pull/144`
- Base: `ws29/canonical-authority-closure`
- Exact base SHA: `362d9351f749b6f49d67cd1ef4eed298b8922b68`
- Verified semantic head: `f9b2c92c6781de9e81b13458262dd03ff12ec089`
- State: OPEN, DRAFT, UNMERGED
- Merge authorization: NOT GRANTED; no merge performed.

## Dependencies Unblocked

WS-30 unblocks identical same-fixture provider execution of:

1. the exact Differential Starter 18;
2. the exact Known-PASS Union 50;
3. the full frozen 135 Common denominator.

Future differential evidence can now compare providers from one canonical initial semantic state, one knowledge state, one Rules-RNG/DecisionTape contract, one semantic selector model, one event normalization model, and one terminal assertion set rather than merely sharing fixture IDs.

No provider receives credit from WS-30 itself.

## Exact Next Action

Start the next provider-execution/differential workstream with `qualification/materialization/DIFFERENTIAL_STARTER_18.json` as the exact canonical experiment source.

For each provider independently:

1. construct the requested canonical semantic state inside the provider Rules process;
2. run native structural validation;
3. fail closed on construction mismatch;
4. expose only provider-offered legal options;
5. apply only the canonical fail-closed semantic decision selectors;
6. emit normalized semantic events/checkpoints/terminal state;
7. compare same-fixture normalized evidence only after both executions are valid.

Do not select a Rules Core in WS-30.
