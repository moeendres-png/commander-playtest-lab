# Forge bridge source rebind (forge#22 + forge#25 + forge#28): impact adjudication

- **Change:** the Forge **bridge/materialization** source moves from `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (tree `00006689`, forge#16) to `ee37e4a52d99401ba57fba7ca516ac01f1981161` (tree `b26c5936`).
  - That commit is the forge#28 head: three commits on the #11 qualification branch head `6f09dab0`, which carries forge#22 (`42963734`, 2026-10-04) and forge#25 (`6f09dab0`, 2026-10-05).
  - Merging forge#28 into the branch keeps tree `b26c5936`. The pin binds the forge#28 commit itself, never a later branch head.
  - An earlier revision of this PR pinned `6f09dab0` (schema `/2`). Commander-Lab #530 now requires schema `/4`, so `6f09dab0` would fail closed there; it was never merged as a pin.
- **Unchanged:** the Rules-Core authority `bb0a740d2bef725194798383c2452213ecdd0b37` (R-1, #11 incl. #12). The two roles stay separate fields: `secondary_engine.commit` and `secondary_engine.bridge_source.commit`.
- **Lock:** `qualification/forge-bridge-constructed-state-20261005/SUCCESSOR_SOURCE_LOCK.json`. The forge#16 lock `qualification/forge-bridge-r5-integrated-20261001/` stays historical under its own identity.
- **Lane:** Claude lane, #441 (Forge residual mechanisms and decision (c)).
- **Not:** Production Provider selection, Architecture Freeze, a denominator change, a Rules-Core change, or a merge to `forge/master`.

## Delta `20e3e1f7..ee37e4a5` (bridge only)

`bb0a740d..ee37e4a5` touches only `forge-protocol2-bridge/`: 0 Rules-Core files and 0 card-data files.

| Change | Behaviour |
|---|---|
| forge#22 free mulligan tuck | The bridge answers the free multiplayer mulligan's zero-card London tuck itself (there is no card to choose), instead of stalling on an empty selection (#441 PILOT_MULLIGAN). |
| forge#25 `get_constructed_state` | A new **orchestration channel**, not a principal observation.<br>• Every launch without `COMMANDER_LAB_ORCHESTRATION_KEY` refuses it with `orchestration_channel_not_enabled`.<br>• With a key it reports public seat facts and each seat's library and hand as one HMAC-SHA-256 digest under the launch key.<br>• It also reports each library's engine shuffle count (`GameEventShuffle`).<br>• Capabilities declare `constructed_state_supported` and its scope.<br>• This is the Lab's generic-lane construction proof (#441 (c), Commander-Lab #530). |
| forge#28 native commander attributes | `get_constructed_state` moves to schema `commander-lab.generic-constructed-state/3`. Each commander carries the engine's own `controller`, `counters` (above zero, keyed by the engine's counter name lower-cased: `+1/+1`, `charge`), `face_down`, `tapped` and `attachments` (a count). These are public commander facts. The schema string is an HMAC token, so a `/2` digest never verifies as `/3`. This answers Codex P1 on Commander-Lab #530: the proof observes these attributes instead of inferring them from the request. Schema `/4` adds the engine's own rules state (`combat_groups`, `combat_attackers`, `extra_turns`, `pending_triggers`, `continuous_effects`, with each player's Commander rule effect, CR 903.8, reported apart as `format_rule_effects`) and each seat's `knowledge.visible_hidden_cards` and `commander_damage_taken`, so no must-be-empty projection is inferred either. |

## Hidden-information channel table

`forge_hidden_information.py` is re-asserted against `ee37e4a5` by rerunning the census with the Forge source at that commit:
- the closed message set gains `BridgeProtocol.GET_CONSTRUCTED_STATE`;
- the table records `orchestration_constructed_state` as SUPPORTED, with its key-refusal guard as a required fragment;
- the keyed success path is its own entry, `orchestration_constructed_state_payload`. It requires the HMAC `zoneDigest` construction (`OrchestrationKey.digest`) and pins the closed set of keys the payload writes (`CONSTRUCTED_STATE_KEYS`). A new key that could carry a hidden card name, or a lost digest, is drift.
- forge#28 adds to that closed set the five public commander keys `attachments`, `controller`, `counters`, `face_down` and `tapped`, and the ten schema `/4` count keys (`rules_state` and its five counts plus `format_rule_effects`, `knowledge`, `visible_hidden_cards`, `commander_damage_taken`). None can carry a card name. The decision-frame sentinel facets are attached only to the `decision_frames` entry, not to this payload (Codex P2 on #537).

No other asserted fragment, bootstrap field, frame key or stderr diagnostic drifted. The AF05 Forge classifications are unchanged (20 PROVIDER_ADAPTER_GAP); only the matrix's bridge binding moves.

## Exact-head evidence (`ee37e4a5`)

| Evidence | Result |
|---|---|
| Test build, push run 37302534392 and forge#28 PR run 37302539535 | Java 17 and Java 21 success |
| iOS/MobiVM link audit, push run 37302534416 and PR run 37302539584 | success |
| Earlier forge#28 head `e746a14b` (schema `/3`, superseded by the schema `/4` readbacks, never pinned): Test build runs 37291710827 and 37291716231, iOS runs 37291710820 and 37291716229 | Java 17/21 and iOS success |
| Local full `forge.bridge` suite on `ee37e4a5` (`xvfb-run -a mvn -o -B test -pl forge-protocol2-bridge -am -Dcheckstyle.skip`) | 365 run, 0 failures, 0 errors, 0 skipped |
| First forge#28 head `4ed8992d` (counters keyed by the enum constant, superseded after the Codex P2 on forge#28, never pinned): Test build runs 37286563067 and 37286594611, iOS runs 37286563013 and 37286594621 | Java 17/21 and iOS success |
| Earlier base `6f09dab0`: Test build push run 37250587908, iOS push run 37250587931; forge#25 PR head `f4b8cdfa` runs 37240374839 and 37240376596 | Java 17/21 and iOS success |

## Evidence families

| Family | Disposition |
|---|---|
| Forge rows of earlier epochs bound to `20e3e1f7` or `e8b8aec6` | **HISTORICAL_ONLY**: not relabelled. |
| PILOT_MULLIGAN and the multiplayer free-mulligan rows on Forge | **REQUIRES_REQUALIFICATION**: the tuck is now answered by the bridge. |
| Generic-lane construction rows (PLAYER_COUNT_2P–5P, PILOT_MULLIGAN) on Forge | **UNKNOWN, PENDING_DEPENDENCY** on Commander-Lab #530, the consumer, which is not in this tree. Until #530 is on main, `full107.construction_credit_gap` keeps every construction-required row UNKNOWN. Afterwards they **REQUIRE_REQUALIFICATION** through #530's keyed orchestration launch, which compares schema `/4` native commander attributes and rules-state readbacks; without a key they stay UNKNOWN. |
| Every other current-boundary Forge row | **REQUIRES_REQUALIFICATION** through the successor PB-03 epoch, like every row at a new source identity. |
| WSR20/WSR22 Forge evidence (`ef958ee9` lineage) | **HISTORICAL_ONLY**, unchanged. |

**INVALIDATED:** none.

**UNKNOWN:** the current Forge standing at the new bridge source, until the successor epoch exists.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED` · `PRODUCTION_REPOSITORY = NOT_CREATED`
