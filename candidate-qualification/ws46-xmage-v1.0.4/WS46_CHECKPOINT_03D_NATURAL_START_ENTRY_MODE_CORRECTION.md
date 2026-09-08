# WS46 CHECKPOINT 03D — FRESH FULL107 CONSTRUCTION V2 ENTRY-MODE CORRECTION

## Source Lock

- Commander Lab branch: `ws46/xmage-v1.0.4-successor-qualification`
- Pre-checkpoint head: `9c3aad35d62c87ef8adfdf611c386c236cedbdaf`
- WS44 freeze commit: `12940248497a8795991cbbd2eedef72945528cfe`
- WS44 root tree: `cd83c973b269711106d08ab5be2d7672f05bcb7c`
- WS44 materialization SHA-256: `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- XMage candidate commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- XMage candidate tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`
- Historical successor runtime credit imported: `0`

## Fresh Construction V2 Runtime Evidence

Exact push run:

- run: `34216665085`
- job: `102029922091`
- workflow: `WS46 XMage v1.0.4 Fresh Full107 Construction v2`
- artifact ID: `10052501985`
- artifact name: `ws46-v104-construction-v2-9c3aad35d62c87ef8adfdf611c386c236cedbdaf`

Fresh gates completed before the probe failure:

- exact WS46 checkout: PASS
- exact immutable WS44 commit/tree/materialization hash: PASS
- exact XMage commit/tree: PASS
- independent v1.0.4 denominator reconstruction: PASS `107/107`
- all requested-state digests independently recomputed equal: PASS
- WS46 qualification overlays: PASS
- exact XMage build: PASS
- qualification bridge build: PASS
- runtime classpath materialization: PASS

The first failure is inside the actual fresh v1.0.4 full107 construction probe:

`WS46_CONSTRUCTION_UNEXPECTED_NATURAL_GAME_START:<fixture>`

This is a probe admission assumption defect, not an XMage Rules-Core failure.

## Correct Immutable v1.0.4 Entry-Mode Distribution

The independently generated `WS46_DENOMINATOR_MANIFEST_107.json` from the exact WS44-locked run proves:

- `NATIVE_STATE_LOAD`: `100`
- `NATURAL_GAME_START`: `7`
- total: `107`

Exact `NATURAL_GAME_START` fixture IDs:

1. `PLAYER_COUNT_2P`
2. `PLAYER_COUNT_3P`
3. `PLAYER_COUNT_4P`
4. `PLAYER_COUNT_5P`
5. `PILOT_MULLIGAN`
6. `WS05-CMD-MULL-2`
7. `WS05-CMD-MULL-4`

This supersedes the earlier WS46 audit statement that v1.0.4 contained zero natural-start records.

## Remediation Authority

The probe must not reject these seven records merely because their immutable execution entry mode is `NATURAL_GAME_START`.

The correction is deliberately narrow:

- remove only the `UNEXPECTED_NATURAL_GAME_START` admission rejection;
- execute all seven natural-start records freshly in WS46;
- import no historical PASS/runtime credit;
- do not skip/defer any of the seven records;
- retain exact 107-record denominator enforcement;
- retain requested-state digest verification;
- retain native non-request-echo readback validation;
- retain `unsupported_dimension_counts == {}` as a hard gate;
- retain fail-closed behavior for actual runtime/setup mismatches.

## Gate State

- Reconciliation: PASS
- Fresh exact XMage source/build/native restore: PASS
- Native construction surface audit: PASS
- Full107 denominator: PASS `107/107`
- Full107 native construction: FAIL / remediable probe assumption
- Construction normalization: NOT_RUN
- Full behavior 107/107: NOT_RUN
- AF04/05/06/08/09: NOT GRANTED
- CARD_02 behavior: NOT_RUN
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`

## Exact Next Action

Patch only the stale natural-start rejection in `run_full107_construction_probe_v104.py`, then execute a fresh exact-head full107 construction run and remediate the first genuine compiler/runtime/native-readback mismatch without weakening any frozen semantic obligation.
