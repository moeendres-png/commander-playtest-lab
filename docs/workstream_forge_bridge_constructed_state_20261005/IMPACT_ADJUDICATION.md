# Forge bridge source rebind (forge#22 + forge#25 + forge#28): impact adjudication

- **Change:** the Forge **bridge/materialization** source moves from `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (tree `00006689`, forge#16) to `4ed8992de4bd7bd120c3920c0362533c7c65d822` (tree `31f70b51`).
  - That commit is the forge#28 head: one commit on the #11 qualification branch head `6f09dab0`, which carries forge#22 (`42963734`, 2026-10-04) and forge#25 (`6f09dab0`, 2026-10-05).
  - Merging forge#28 into the branch keeps tree `31f70b51`. The pin binds the forge#28 commit itself, never a later branch head.
  - An earlier revision of this PR pinned `6f09dab0` (schema `/2`). Commander-Lab #530 now requires schema `/3`, so `6f09dab0` would fail closed there; it was never merged as a pin.
- **Unchanged:** the Rules-Core authority `bb0a740d2bef725194798383c2452213ecdd0b37` (R-1, #11 incl. #12). The two roles stay separate fields: `secondary_engine.commit` and `secondary_engine.bridge_source.commit`.
- **Lock:** `qualification/forge-bridge-constructed-state-20261005/SUCCESSOR_SOURCE_LOCK.json`. The forge#16 lock `qualification/forge-bridge-r5-integrated-20261001/` stays historical under its own identity.
- **Lane:** Claude lane, #441 (Forge residual mechanisms and decision (c)).
- **Not:** Production Provider selection, Architecture Freeze, a denominator change, a Rules-Core change, or a merge to `forge/master`.

## Delta `20e3e1f7..4ed8992d` (bridge only)

`bb0a740d..4ed8992d` touches only `forge-protocol2-bridge/`: 0 Rules-Core files and 0 card-data files.

| Change | Behaviour |
|---|---|
| forge#22 free mulligan tuck | The bridge answers the free multiplayer mulligan's zero-card London tuck itself (there is no card to choose), instead of stalling on an empty selection (#441 PILOT_MULLIGAN). |
| forge#25 `get_constructed_state` | A new **orchestration channel**, not a principal observation.<br>• Every launch without `COMMANDER_LAB_ORCHESTRATION_KEY` refuses it with `orchestration_channel_not_enabled`.<br>• With a key it reports public seat facts and each seat's library and hand as one HMAC-SHA-256 digest under the launch key.<br>• It also reports each library's engine shuffle count (`GameEventShuffle`).<br>• Capabilities declare `constructed_state_supported` and its scope.<br>• This is the Lab's generic-lane construction proof (#441 (c), Commander-Lab #530). |
| forge#28 native commander attributes | `get_constructed_state` moves to schema `commander-lab.generic-constructed-state/3`. Each commander carries the engine's own `controller`, `counters` (above zero), `face_down`, `tapped` and `attachments` (a count). These are public commander facts. The schema string is an HMAC token, so a `/2` digest never verifies as `/3`. This answers Codex P1 on Commander-Lab #530: the proof observes these attributes instead of inferring them from the request. |

## Hidden-information channel table

`forge_hidden_information.py` is re-asserted against `4ed8992d` by rerunning the census with the Forge source at that commit:
- the closed message set gains `BridgeProtocol.GET_CONSTRUCTED_STATE`;
- the table records `orchestration_constructed_state` as SUPPORTED, with its key-refusal guard as a required fragment;
- the keyed success path is its own entry, `orchestration_constructed_state_payload`. It requires the HMAC `zoneDigest` construction (`OrchestrationKey.digest`) and pins the closed set of keys the payload writes (`CONSTRUCTED_STATE_KEYS`). A new key that could carry a hidden card name, or a lost digest, is drift.
- forge#28 adds five keys to that closed set: `attachments`, `controller`, `counters`, `face_down` and `tapped`. All are public commander facts. The decision-frame sentinel facets are attached only to the `decision_frames` entry, not to this payload (Codex P2 on #537).

No other asserted fragment, bootstrap field, frame key or stderr diagnostic drifted. The AF05 Forge classifications are unchanged (20 PROVIDER_ADAPTER_GAP); only the matrix's bridge binding moves.

## Exact-head evidence (`4ed8992d`)

| Evidence | Result |
|---|---|
| Test build, push run 37286563067 and forge#28 PR run 37286594611 | Java 17 and Java 21 success |
| iOS/MobiVM link audit, push run 37286563013 and PR run 37286594621 | success |
| Local full `forge.bridge` suite on `4ed8992d` (`xvfb-run -a mvn -o -B test -pl forge-protocol2-bridge -am -Dcheckstyle.skip`) | 363 run, 0 failures, 0 errors, 0 skipped |
| Earlier base `6f09dab0`: Test build push run 37250587908, iOS push run 37250587931; forge#25 PR head `f4b8cdfa` runs 37240374839 and 37240376596 | Java 17/21 and iOS success |

## Evidence families

| Family | Disposition |
|---|---|
| Forge rows of earlier epochs bound to `20e3e1f7` or `e8b8aec6` | **HISTORICAL_ONLY**: not relabelled. |
| PILOT_MULLIGAN and the multiplayer free-mulligan rows on Forge | **REQUIRES_REQUALIFICATION**: the tuck is now answered by the bridge. |
| Generic-lane construction rows (PLAYER_COUNT_2P–5P, PILOT_MULLIGAN) on Forge | **REQUIRES_REQUALIFICATION** through #530's keyed orchestration launch, which compares schema `/3` native commander attributes. Without a key they stay UNKNOWN. |
| Every other current-boundary Forge row | **REQUIRES_REQUALIFICATION** through the successor PB-03 epoch, like every row at a new source identity. |
| WSR20/WSR22 Forge evidence (`ef958ee9` lineage) | **HISTORICAL_ONLY**, unchanged. |

**INVALIDATED:** none.

**UNKNOWN:** the current Forge standing at the new bridge source, until the successor epoch exists.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED` · `PRODUCTION_REPOSITORY = NOT_CREATED`
