# Forge bridge source rebind (forge#22 + forge#25): impact adjudication

- **Change:** the Forge **bridge/materialization** source moves from `20e3e1f7ff8e6195b95ed0dc14e0d4c87f1bcf4c` (tree `00006689`, forge#16) to `6f09dab0b9dfacaed1aeb84b1c7f3666d499e3f3` (tree `532202f3`).
  - That commit is the #11 qualification branch head after forge#22 (`42963734`, 2026-10-04) and forge#25 (`6f09dab0`, 2026-10-05).
  - The forge#25 PR head `f4b8cdfa` has the same tree.
- **Unchanged:** the Rules-Core authority `bb0a740d2bef725194798383c2452213ecdd0b37` (R-1, #11 incl. #12). The two roles stay separate fields: `secondary_engine.commit` and `secondary_engine.bridge_source.commit`.
- **Lock:** `qualification/forge-bridge-constructed-state-20261005/SUCCESSOR_SOURCE_LOCK.json`. The forge#16 lock `qualification/forge-bridge-r5-integrated-20261001/` stays historical under its own identity.
- **Lane:** Claude lane, #441 (Forge residual mechanisms and decision (c)).
- **Not:** Production Provider selection, Architecture Freeze, a denominator change, a Rules-Core change, or a merge to `forge/master`.

## Delta `20e3e1f7..6f09dab0` (bridge only)

`bb0a740d..6f09dab0` touches only `forge-protocol2-bridge/`: 0 Rules-Core files and 0 card-data files.

| Change | Behaviour |
|---|---|
| forge#22 free mulligan tuck | The bridge answers the free multiplayer mulligan's zero-card London tuck itself (there is no card to choose), instead of stalling on an empty selection (#441 PILOT_MULLIGAN). |
| forge#25 `get_constructed_state` | A new **orchestration channel**, not a principal observation.<br>• Every launch without `COMMANDER_LAB_ORCHESTRATION_KEY` refuses it with `orchestration_channel_not_enabled`.<br>• With a key it reports public seat facts and each seat's library and hand as one HMAC-SHA-256 digest under the launch key.<br>• It also reports each library's engine shuffle count (`GameEventShuffle`).<br>• Capabilities declare `constructed_state_supported` and its scope.<br>• This is the Lab's generic-lane construction proof (#441 (c), Commander-Lab #530). |

## Hidden-information channel table

`forge_hidden_information.py` is re-asserted against `6f09dab0` by rerunning the census with the Forge source at that commit:
- the closed message set gains `BridgeProtocol.GET_CONSTRUCTED_STATE`;
- the table records `orchestration_constructed_state` as SUPPORTED, with its key-refusal guard as a required fragment.

No other asserted fragment, bootstrap field, frame key or stderr diagnostic drifted. The AF05 Forge classifications are unchanged (20 PROVIDER_ADAPTER_GAP); only the matrix's bridge binding moves.

## Exact-head evidence (`6f09dab0`)

| Evidence | Result |
|---|---|
| Test build, push run 37250587908 | Java 17 and Java 21 success |
| iOS/MobiVM link audit, push run 37250587931 | success |
| forge#25 PR head `f4b8cdfa` (same tree), Test build runs 37240374839 and 37240376596 | Java 17 and Java 21 success; iOS success |
| Local full `forge.bridge` suite on `f4b8cdfa` (`xvfb-run -a mvn -o -B test -pl forge-protocol2-bridge -am -Dcheckstyle.skip`) | 363 run, 0 failures, 0 errors, 0 skipped |

## Evidence families

| Family | Disposition |
|---|---|
| Forge rows of earlier epochs bound to `20e3e1f7` or `e8b8aec6` | **HISTORICAL_ONLY**: not relabelled. |
| PILOT_MULLIGAN and the multiplayer free-mulligan rows on Forge | **REQUIRES_REQUALIFICATION**: the tuck is now answered by the bridge. |
| Generic-lane construction rows (PLAYER_COUNT_2P–5P, PILOT_MULLIGAN) on Forge | **REQUIRES_REQUALIFICATION** through #530's keyed orchestration launch. Without a key they stay UNKNOWN. |
| Every other current-boundary Forge row | **REQUIRES_REQUALIFICATION** through the successor PB-03 epoch, like every row at a new source identity. |
| WSR20/WSR22 Forge evidence (`ef958ee9` lineage) | **HISTORICAL_ONLY**, unchanged. |

**INVALIDATED:** none.

**UNKNOWN:** the current Forge standing at the new bridge source, until the successor epoch exists.

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED` · `PRODUCTION_REPOSITORY = NOT_CREATED`
