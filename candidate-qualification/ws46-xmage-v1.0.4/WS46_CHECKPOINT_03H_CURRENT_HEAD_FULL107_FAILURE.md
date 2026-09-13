# WS46 CHECKPOINT 03H — CURRENT-CODE FULL107 CONSTRUCTION v2 TERMINAL FAILURE

## Source Lock

- Commander Lab repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws46/xmage-v1.0.4-successor-qualification`
- Current-code runtime head tested: `d5f534f7014e78b272983b0548e3c5ce266fde35`
- WS44 freeze commit: `12940248497a8795991cbbd2eedef72945528cfe`
- WS44 root tree: `cd83c973b269711106d08ab5be2d7672f05bcb7c`
- WS44 namespace tree: `6579e119605b90248426a3121a47c487b2bb13cd`
- WS44 materialization SHA-256: `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`
- WS44 immutable materialization blob: `4e3344bac577aca677260a837dd78e2c096f72f1`
- XMage candidate commit: `0c1f455ea8c8fa48ab9d638ad5068ec242800428`
- XMage candidate tree: `fdb8bf56a8bd8199a4ef372e468d93d6550b0649`
- Historical v1.0.3 successor runtime credit: exactly `0`

## Terminal Current-Code Runtime Evidence

Workflow:
`WS46 XMage v1.0.4 Full107 Construction v2`

- run: `34221583745`
- job: `102045705813`
- conclusion: **FAIL**
- terminal probe result: `WS46_FULL107_V104_V2_FAIL:19`
- PASS: `88/107`
- FAIL: `19/107`
- TOTAL: `107`

All prerequisite gates before the 107-record probe passed, including source-lock verification, denominator verification, overlay application, Python compilation, XMage build, bridge compilation and runtime classpath checks.

Artifact:
- ID: `10062360868`
- name: `ws46-full107-v2-d5f534f7014e78b272983b0548e3c5ce266fde35`
- GitHub artifact SHA-256: `1f3766c984363ebb2f1738d25f0753ad8ce1be70e1ebcf715433fc9bd7048f70`

## Exact Remaining Failure Taxonomy

### Natural-start/configuration — 7

- `WS05-MP-CMD-FREECAST-1`
- `WS05-MP-TRIG-3`
- `WS05-MP-TRIG-4`
- `WS05-MP-DRAW-1`
- `WS05-MP-DRAW-2`
- `WS05-MP-ELIM-OWNED-3`
- `WS05-MP-60A-7`

Failure family:
`CONFIGURATION_INVALID:<fixture>:NATURAL_GAME_START_DISALLOWS_PRELOAD|...`

The Java-side WS46 natural-start patch is therefore not sufficient by itself. The Python probe still rejects these records before invoking the bridge whenever their frozen requested state contains non-empty setup surfaces. This must be adjudicated against the exact immutable WS44 record semantics before changing the guard.

### Hidden-information `face_down` shape — 2

- `HIDDEN_05`
- `HIDDEN_10`

Failure family:
`FAIL_CLOSED:WS46_NATIVE_READBACK_FACE_DOWN_UNSUPPORTED:<fixture>:dict`

### Knowledge library-range — 2

- `HIDDEN_14`
- `HIDDEN_15`

Failure family:
`FAIL_CLOSED:WS46_KNOWLEDGE_LIBRARY_RANGE_UNSUPPORTED:<fixture>:players.alpha`

### Extra-turn `resolution_sequence` — 2

- `WS05-MP-TURN-3`
- `WS05-MP-TURN-5`

Failure family:
`FAIL_CLOSED:WS46_NATIVE_READBACK_EXTRA_TURN_UNSUPPORTED:<fixture>:resolution_sequence`

### Elimination `condition` — 6

- `WS05-MP-ELIM-1`
- `WS05-MP-ELIM-2`
- `WS05-MP-ELIM-OWNED-1`
- `WS05-MP-ELIM-OWNED-2`
- `WS05-MP-ELIM-OWNED-4`
- `WS05-MP-ELIM-OWNED-5`

Failure family:
`FAIL_CLOSED:WS46_NATIVE_READBACK_ELIMINATION_UNSUPPORTED:<fixture>:condition`

Total: `7 + 2 + 2 + 2 + 6 = 19`.

## Interpretation

This run is the current-code runtime authority for the construction gate at this checkpoint. It independently reproduced the same five failure classes preserved by the earlier pre-fix run.

No failure is currently proven terminal. No PASS may be inferred for any of the 19 records. No request-echo, heuristic legality, silent fallback, or historical runtime credit is permitted as remediation.

## Gate State

- Reconciliation: **PASS**
- Exact XMage source lock/build: **PASS**
- Full107 construction: **FAIL / 88 of 107**
- Independent normalized native-state digest 107/107: **NOT GRANTED**
- Behavior 107/107: **NOT RUN / NOT GRANTED**
- AF04/AF05/AF06/AF08/AF09: **NOT GRANTED**
- CARD_02 behavior: **NOT GRANTED**
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED`: **FALSE**

## Exact Next Action

Read the exact immutable WS44 requested-state and semantic metadata for all 19 failing fixtures, bind each unsupported shape to a concrete XMage-native state source and lifecycle boundary, then implement only source-proven remediations. Re-run the complete 107-record construction probe from record 1 after each coherent remediation batch. Keep PR #160 Draft and unmerged.
