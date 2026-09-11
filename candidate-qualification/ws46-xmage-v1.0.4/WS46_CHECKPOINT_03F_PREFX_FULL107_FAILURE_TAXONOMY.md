# WS46 CHECKPOINT 03F — PRE-FIX FULL107 FAILURE TAXONOMY

## Source Lock

- Pre-fix Commander Lab commit: `842431d0af4290d86257ea7de5d8010050e49058`
- Pre-fix Commander Lab tree: `d65631c38b7357a9ab3d0ef5831ec77f5e6dd849`
- WS44 freeze commit: `12940248497a8795991cbbd2eedef72945528cfe`
- WS44 namespace tree: `6579e119605b90248426a3121a47c487b2bb13cd`
- WS44 materialization blob: `4e3344bac577aca677260a837dd78e2c096f72f1`
- WS44 materialization SHA-256: `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- XMage commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- XMage tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`
- Historical v1.0.3 runtime credit imported: `0`

## Exact Pre-Fix Runtime Evidence

Workflow run: `34218604151`

Job: `102036168036` (`full107-construction`)

Exact Full107 result:

- denominator: `107`
- `NATIVE_SETUP_PASS_AWAITING_INDEPENDENT_NORMALIZATION`: `88`
- `NATIVE_SETUP_FAIL`: `19`
- entry modes: `100 NATIVE_STATE_LOAD + 7 NATURAL_GAME_START`
- unsupported dimension counts: `{}`

Build/source-lock/bridge/classpath steps all passed before the runtime probe failed.

Artifact:

- artifact ID: `10053664039`
- artifact name: `ws46-v104-construction-v2-842431d0af4290d86257ea7de5d8010050e49058`
- artifact SHA-256: `ffeef60333771bbb1589abc544aea9efbdf3c50ad594088530aac2ef5535bfc4`

This is negative diagnostic evidence only. It grants no v1.0.4 construction PASS.

## Exact 19-Failure Taxonomy

### A. Natural-game-start translation/configuration — 7

Fixtures:

1. `PLAYER_COUNT_2P`
2. `PLAYER_COUNT_3P`
3. `PLAYER_COUNT_4P`
4. `PLAYER_COUNT_5P`
5. `PILOT_MULLIGAN`
6. `WS05-CMD-MULL-2`
7. `WS05-CMD-MULL-4`

Observed error class:

`RuntimeError:natural game start requires natural_library_card_name`

This failure occurs before the new first-external-decision readback can supply construction evidence. It therefore requires translator/configuration remediation in addition to the decision-boundary readback work already source-proven in checkpoint 03E.

### B. Knowledge-state native library range — 2

Fixtures:

- `PILOT_BORROWED_INFORMATION`
- `PILOT_HIDDEN_INFO_OWNER_HAND`

Observed error:

`requested knowledge_state library range is missing from native readback`

This is a lower-level native readback / contract-shape mismatch. No request echo or synthetic contract-derived range may be used as proof.

### C. Extra-turn construction shape — 2

Fixtures:

- `WS05-MP-EXTRA-1`
- `WS05-MP-EXTRA-2`

Observed error:

`unsupported extra_turn_creation field(s): ['resolution_sequence']`

The exact immutable meaning of `resolution_sequence` must be read from WS44 and bound to native `GameState.turnMods` / `TurnMod` evidence before admission.

### D. Elimination construction shape — 4

Fixtures:

- `WS05-MP-ELIM-1`
- `WS05-MP-ELIM-2`
- `WS05-MP-ELIM-3`
- `WS05-MP-ELIM-4`

Observed error:

`unsupported elimination_trigger field(s): ['condition']`

The exact immutable condition shape must be bound to native player/game state. No condition may be inferred from fixture identity alone.

### E. Face-down hidden-information semantic-object shape — 4

Fixtures:

- `WS05-MP-HID-6`
- `WS05-MP-HID-7`
- `WS05-MP-HID-8`
- `WS05-MP-HID-9`

Observed error class:

unsupported native semantic-object key `face_down`

One failure occurs through the hidden-validation family and three through hidden-exile-validation-family paths. The exact frozen `face_down` obligation must be verified against WS44 and must use native visibility/face-down state rather than the request object.

## Current Remediation Head Context

After this pre-fix run, WS46 created atomic commit:

`5d6c65f4b4d841814ffbb87621f4e05c58bb9844`

with a WS46-only Natural-Start first-decision readback and matching capture validator. That patch does **not** by itself justify assuming the seven translator/configuration failures are closed, and it does not address the other twelve failures listed above.

The exact-head Construction-v2 run for that patch was still executing the fresh 107-record runtime probe when this checkpoint was prepared. Its result must be evaluated independently.

## Gate Status

- Reconciliation: PASS
- Exact XMage source/build lock: PASS through the applicable pre-fix build steps; fresh exact-head build also previously reached PASS before runtime probe
- Full107 lower-level native construction: `FAIL` for the pre-fix run (`88/107 pass, 19/107 fail`)
- Current-head Full107 result: `UNKNOWN / IN_PROGRESS` at checkpoint preparation
- Independent normalized construction gate: NOT CLOSED
- Construction 107/107: NOT GRANTED
- AF04: NOT GRANTED
- AF05: NOT GRANTED
- AF06: NOT GRANTED
- AF08: NOT GRANTED
- AF09: NOT GRANTED
- CARD_02 behavior: NOT GRANTED
- AF07: NOT GRANTED
- Architecture Freeze: NOT GRANTED

## Required Remediation Discipline

For every failure class above:

1. read the exact immutable v1.0.4 record shape from WS44;
2. identify the exact native XMage state/readback source;
3. patch only qualification plumbing or native engine capability genuinely required by the obligation;
4. do not consume `successor_requested_state` or the declared requested-state digest as observed proof;
5. fail closed on unknown fields or absent native evidence;
6. execute a fresh exact-head 107-record probe;
7. grant construction credit only after separate independent normalization reproduces the immutable requested-state digest from native evidence.

## Exact Next Action

Read the terminal result of current-head Construction-v2 run `34220355466`, then bind the remaining failure classes to exact WS44 record shapes and native XMage sources. Remediate all still-reproducing classes atomically where practical, execute a fresh exact-head Full107 probe, and only after lower-level 107/107 proceed to independent v1.0.4 normalization.