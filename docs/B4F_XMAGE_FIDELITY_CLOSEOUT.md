# B4-F XMage Fidelity Closeout

Date: 2026-08-22

## Decision

`FIDELITY_REVIEW=COMPLETE`

`FIDELITY_RECLASSIFICATION=NONE`

The completed B4-F XMage evidence validates a bounded external-rules slice. It does **not** broaden the Structural resolver's mechanics fidelity and therefore does not justify moving any card or mechanic into `MECHANISTICALLY_SUPPORTED` or `APPROXIMATED_DECISION_SAFE`.

The historical `docs/J_P3_CLOSEOUT.md` is preserved as provenance for the earlier provider-readiness decision and is not rewritten by this closeout.

## Evidence source

B4-F implementation/evidence head reviewed before this closeout-only commit:

- repository: `moeendres-png/commander-playtest-lab`
- PR: `#105`
- B4-F evidence head: `1fd8c7d9741ab0aa4583aca1f836f6b5fc2fafe0`
- External XMage Integration run: `32555305458` (`SUCCESS`)
- evidence artifact id: `9471313110`
- evidence artifact digest: `sha256:e13d80ea4f984f4d21710dd8c37bad07573ed0d59a5fd629a91540620e5fe930`
- XMage version: `1.4.61`
- XMage commit: `77d7646da6958fdf8125ee7c8f4aabd130d21d4c`
- bridge artifact SHA256: `fd7ec129c3f74730789684943aaebcbd32df1148dd1ab76ccba17cdfa3dd99e6`
- protocol: `2.0.0`
- scenario contract: `provider_state_injection_v1`
- frozen fixture set: `data/evals/differential/rules_cases.json`
- frozen fixture SHA256: `39c7b85bb041253792656267108ed3764713902a91fc3c8ec7d96a2740481e67`
- capability descriptor SHA256: `ac325f0b816482701644350a59fe290529336804229c0c2d8aee73418e9efc69`
- capability hash: `164332b6484c427dc8d8ae52098d72897043ca44bb52d1417e82701dbb4519f4`

## Post-closeout evidence-boundary hardening

A follow-up review tightened the wording and machine-readable boundary of the B4-F evidence without changing the original Fidelity decision. The original hashes above remain historical provenance for the initial B4-F closeout; subsequent B4-F capability artifacts are expected to bind the exact runtime evidence files that support their claims.

The bounded Commander Damage evidence is now interpreted narrowly:

- XMage provider-derived: `player_loses` after XMage Commander state-based actions evaluate already separated `CommanderInfoWatcher` state;
- adapter-derived normalization: `loss_reason` and `maximum_single_commander_damage`;
- **not proven by this fixture**: combat-path attribution of damage to separate commanders before the watcher state is populated.

Accordingly, `commander_damage_per_commander_separation=PROVEN` is retired as an overbroad capability label. The replacement bounded claim is `commander_damage_state_based_loss_from_separated_injected_watcher_state=PROVEN`, while `commander_damage_combat_attribution_per_commander=NOT_PROVEN`. This clarification does not broaden Structural fidelity and does not alter `FIDELITY_RECLASSIFICATION=NONE`.

The follow-up capability binding also includes SHA-256 identities for the Phase-6 replay evidence, illegal-action evidence and B4-C action evidence, so the capability hash binds both runtime/provider identity and the exact supporting evidence chain.

## B4-F gates reviewed

The following gates passed through the real pinned XMage path:

1. real four-player Phase-6 differential for all three frozen fixtures;
2. repeated fresh-process reconstruction: three fresh XMage JVM processes for each frozen fixture;
3. explicit non-enumerated/illegal action rejection against a current provider decision, with provider state and decision identity unchanged after rejection and a subsequent valid action succeeding;
4. machine-readable bounded capability descriptor;
5. capability binding to XMage commit, bridge artifact SHA, protocol, scenario contract, frozen fixture set and exact supporting B4-C/B4-F evidence-file hashes;
6. separate provider-pin validation reproducing the capability hash and matching the live provider identity.

Frozen Phase-6 rules cases:

- `commander_tax_third_cast`: PASS;
- `commander_damage_not_combined`: PASS;
- `commander_damage_exactly_twenty_one`: PASS.

Repeated fresh-process reconstruction hashes:

- `commander_tax_third_cast`: `a5e08218618548c3428316432f54633563663dd3433f51c4a6a8e48977feb1e8`;
- `commander_damage_not_combined`: `4f083cc2125a3346bf5884c03b5a350feb0f400307c4c303e1006d549205757a`;
- `commander_damage_exactly_twenty_one`: `335751c03b49682bb17d42e01e1ac5b121f8995372168a482539479b209274ba`.

## Fidelity model reviewed

Current source of truth reviewed on the B4-F evidence head:

`src/commander_lab/whole_deck/mechanics_fidelity.py`

Structural semantic model:

`structural-mechanics-fidelity-2026-08-21-v1`

Structural confirmatory remains limited to:

- `MECHANISTICALLY_SUPPORTED`;
- `APPROXIMATED_DECISION_SAFE`.

The following remain non-Structural-confirmatory routing tiers:

- `APPROXIMATED_SCREENING_ONLY` -> search/screening only;
- `TACTICAL_REQUIRED` -> Tactical or fail closed;
- `EXTERNAL_RULES_REQUIRED` -> External Rules or fail closed;
- `UNSUPPORTED` -> fail closed.

Current external-rules mechanic gates remain:

- `SACRIFICE_COST`;
- `SACRIFICE_OUTLET`;
- `DEATH_TRIGGER`;
- `COMMANDER_DAMAGE_SUPPORT`;
- `TABLE_DAMAGE`;
- `STACK_INTERACTION`.

The B4-F Commander Damage fixtures are external-rules evidence for a bounded XMage provider slice. They are not evidence that the legacy Structural resolver now mechanistically implements `COMMANDER_DAMAGE_SUPPORT` or `TABLE_DAMAGE`. Those mechanic gates therefore remain unchanged.

Current explicit `TACTICAL_REQUIRED` cards remain unchanged:

- `Silence`;
- `Dovin's Veto`;
- `Negate`;
- `Wash Away`;
- `Esior, Wardwing Familiar`.

Current explicit `EXTERNAL_RULES_REQUIRED` cards remain unchanged:

- `Light of Hope`;
- `Psychotic Fury`;
- `Boros Charm`;
- `Flare of Duplication`;
- `Wear // Tear`;
- `Louisoix's Sacrifice`;
- `Chain Reaction`;
- `Farewell`;
- `Vandalblast`;
- `Curiosity`;
- `Combat Research`;
- `Lightning Greaves`;
- `Swiftfoot Boots`;
- `Duelist's Heritage`;
- `Springleaf Drum`;
- `Relic of Legends`;
- `Kediss, Emberclaw Familiar`;
- `Harmonic Prodigy`;
- `Veyran, Voice of Duality`;
- `Guttersnipe`;
- `Kykar, Wind's Fury`;
- `Storm-Kiln Artist`;
- `Archmage Emeritus`;
- `Jeska, Thrice Reborn`;
- `Aerial Extortionist`;
- `Narset, Enlightened Master`;
- `Clever Impersonator`.

## What the external evidence proves

Bounded/proven for the pinned XMage provider path:

- real four-player Commander runtime for the validated path;
- frozen provider-state reconstruction for the three Phase-6 fixtures;
- Commander Tax on a third command-zone cast in the frozen case;
- state-based loss evaluation from already separated injected CommanderInfoWatcher damage state in the frozen cases;
- 21 injected Commander Damage in one CommanderInfoWatcher causing the frozen-case loss;
- current-priority machine-readable actions for the validated bounded path;
- bounded targetless/nonmodal state-bound submission for the validated path;
- stale/non-enumerated action rejection for the validated path;
- fresh-process reconstruction stability for the frozen fixtures.

## What the external evidence does not prove

The following remain outside the demonstrated capability surface:

- global legal-action enumeration completeness;
- global action-submission completeness;
- arbitrary starting-state injection;
- seed-controlled full-game replay;
- full-game deterministic replay;
- complete target submission;
- complete mode/choice submission;
- complete combat decision submission;
- combat-path attribution of damage to separate commanders before CommanderInfoWatcher state is populated;
- complete attachment legality;
- complete stack/priority sequencing for arbitrary cards;
- card-specific rules correctness for the current Tactical/External Rules card sets.

Therefore:

- `PRODUCTION_READY=NO`;
- `PROVIDER_SELECTED_FOR_PRODUCTION=NO`;
- `FULL_GAME_REPLAY_PROVEN=NO`;
- `GLOBAL_ACTION_SURFACE_PROVEN=NO`;
- `STRUCTURAL_EVIDENCE_BOUNDARY_PRESERVED=YES`.

## Reclassification matrix

| Evidence item | External provider result | Structural fidelity effect |
|---|---|---|
| Commander Tax third cast fixture | proven for frozen XMage case | none |
| Commander damage state-based loss from already separated injected watcher state | proven for frozen XMage case | none |
| Combat-path per-Commander damage attribution | not proven by these fixtures | none |
| 21 Commander Damage loss from injected watcher state | proven for frozen XMage case | none |
| stale/non-enumerated action rejection | proven for bounded current-decision path | none |
| fresh-process reconstruction | proven for frozen fixtures | none |
| seed-controlled full-game replay | not proven | none |
| global target/mode/choice/combat surface | not proven | none |
| card-specific External Rules mechanics | not proven by these fixtures | none |

## Scope / non-changes

This closeout performs no optimizer campaign, holdout consumption or deck decision. It changes no canonical deck list, inventory quantity, allocation, purchase decision, opponent observation or opponent evidence class.

No historical holdout is reopened or reused.

The correct Fidelity outcome is a completed review with **no Structural reclassification**. Future card- or mechanic-specific promotion requires direct evidence for the exact mechanic in the relevant evidence layer; provider availability alone is insufficient.
