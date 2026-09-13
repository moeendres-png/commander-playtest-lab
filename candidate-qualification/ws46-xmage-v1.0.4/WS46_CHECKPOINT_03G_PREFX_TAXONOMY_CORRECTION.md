# WS46 CHECKPOINT 03G — PRE-FIX FULL107 TAXONOMY CORRECTION

## Scope

This checkpoint corrects two evidence-transcription errors in `WS46_CHECKPOINT_03F_PREFX_FULL107_FAILURE_TAXONOMY.md` only. It does **not** change any runtime result, semantic conclusion, construction credit, or provider qualification status.

## Source Lock

- Commander Lab repository: `moeendres-png/commander-playtest-lab`
- WS46 branch before this checkpoint: `ws46/xmage-v1.0.4-successor-qualification`
- Pre-fix runtime commit: `d0f314945613abd9facca989ee640a88553d6589`
- Pre-fix workflow run: `34218604151`
- Pre-fix job: `102036168036`
- Pre-fix artifact ID: `10053664039`
- Pre-fix artifact name: `ws46-full107-v2-d0f314945613abd9facca989ee640a88553d6589`
- Authoritative GitHub artifact SHA-256: `ffeef603f75468715679cecbe4b20ba92aa4bf3db532aadfd10755144e4148e7`

## Correct Runtime Result

The terminal pre-fix full107 runtime result remains:

- PASS: `88/107`
- FAIL: `19/107`
- construction credit: **NOT GRANTED**

The exact corrected 19-failure taxonomy is:

### Natural-start/configuration — 7

1. `WS05-MP-CMD-FREECAST-1`
2. `WS05-MP-TRIG-3`
3. `WS05-MP-TRIG-4`
4. `WS05-MP-DRAW-1`
5. `WS05-MP-DRAW-2`
6. `WS05-MP-ELIM-OWNED-3`
7. `WS05-MP-60A-7`

Failure family:
`CONFIGURATION_INVALID:<fixture>:NATURAL_GAME_START_DISALLOWS_PRELOAD|...`

### Hidden-information `face_down` shape — 2

1. `HIDDEN_05`
2. `HIDDEN_10`

Failure family:
`FAIL_CLOSED:WS46_NATIVE_READBACK_FACE_DOWN_UNSUPPORTED:<fixture>:dict`

### Knowledge library-range — 2

1. `HIDDEN_14`
2. `HIDDEN_15`

Failure family:
`FAIL_CLOSED:WS46_KNOWLEDGE_LIBRARY_RANGE_UNSUPPORTED:<fixture>:players.alpha`

### Extra-turn `resolution_sequence` — 2

1. `WS05-MP-TURN-3`
2. `WS05-MP-TURN-5`

Failure family:
`FAIL_CLOSED:WS46_NATIVE_READBACK_EXTRA_TURN_UNSUPPORTED:<fixture>:resolution_sequence`

### Elimination `condition` — 6

1. `WS05-MP-ELIM-1`
2. `WS05-MP-ELIM-2`
3. `WS05-MP-ELIM-OWNED-1`
4. `WS05-MP-ELIM-OWNED-2`
5. `WS05-MP-ELIM-OWNED-4`
6. `WS05-MP-ELIM-OWNED-5`

Failure family:
`FAIL_CLOSED:WS46_NATIVE_READBACK_ELIMINATION_UNSUPPORTED:<fixture>:condition`

Total: `7 + 2 + 2 + 2 + 6 = 19`.

## Correction Against 03F

`WS46_CHECKPOINT_03F_PREFX_FULL107_FAILURE_TAXONOMY.md` incorrectly transcribed the `face_down` / elimination split as `4 / 4`; the artifact proves `2 / 6`.

03F also carried a stale/incorrect artifact digest. The authoritative GitHub artifact metadata proves:

`ffeef603f75468715679cecbe4b20ba92aa4bf3db532aadfd10755144e4148e7`

This checkpoint supersedes 03F **only** for those taxonomy counts and the artifact digest.

## Gates

- Reconciliation: **PASS**
- Exact XMage source lock/build: **PASS**
- Full107 construction: **NOT GRANTED**
- Independent normalized-state digest 107/107: **NOT GRANTED**
- Behavior 107/107: **NOT RUN / NOT GRANTED**
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED`: **FALSE**

No historical v1.0.3 runtime credit is imported.

## Exact Next Action

Use the terminal current-head full107-v2 result as the only current construction runtime authority, then remediate only the failures that still reproduce against immutable WS44 v1.0.4. Do not infer PASS from this corrected pre-fix taxonomy.
