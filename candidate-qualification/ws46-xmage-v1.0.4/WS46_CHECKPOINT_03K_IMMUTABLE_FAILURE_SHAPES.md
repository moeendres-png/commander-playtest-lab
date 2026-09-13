# WS-46 CHECKPOINT 03K — IMMUTABLE WS44 SHAPES FOR CURRENT FULL107 FAILURES

## Gate

`WS46_CURRENT_FAILURE_SHAPE_AUDIT = PASS`

This is source/contract evidence only. It grants no construction, behavior, AF or provider PASS credit.

## Exact Audit Evidence

- workflow: `WS46 XMage v1.0.4 Current Failure Shape Audit`
- run: `34230112246`
- job: `102073817884`
- tested WS46 head: `e4557fb73046a3a81c2219d1cadf844f3da65083`
- conclusion: `success`
- artifact id: `10057443340`
- artifact name: `ws46-current-failure-shapes-e4557fb73046a3a81c2219d1cadf844f3da65083`
- artifact digest: `sha256:5928a5f1e0012f393bf66958ae77afad59020b9b6ef33913e765088dd980c8dc`
- `WS46_CURRENT_FAILURE_SHAPES.json` SHA-256: `5b3690daecdb5a330a7631a2c5ee2cf03d842f0dbb3f6c7936bc19e2fc6d1787`

The audit independently verified:

- WS44 freeze commit `12940248497a8795991cbbd2eedef72945528cfe`;
- root tree `cd83c973b269711106d08ab5be2d7672f05bcb7c`;
- namespace tree `6579e119605b90248426a3121a47c487b2bb13cd`;
- materialization SHA-256 `9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35`;
- contract `commander-lab.semantic-fixture-materialization/1.0.4`;
- exact 19 current failing fixture IDs from Checkpoint 03J.

## Source-Proven Current Shapes

### A. Seven `NATURAL_GAME_START` records

The seven records use actual Commander deck templates; there is no literal card named `natural_library_card_name` in WS44.

For each player:

- commander: `Rograkh, Son of Rohgahh`;
- commander zone: `command`;
- prior command-zone cast count: `0`;
- library template: `{ "card_identity": "Mountain", "count": 99 }`;
- opening hand size: `7`;
- entry mode: `NATURAL_GAME_START`;
- initial temporal state: pregame / game_start / turn 0;
- Rules RNG channels are the per-player native library-shuffle channels.

Therefore the current runtime error `INVALID_SCENARIO: text natural_library_card_name` is a WS46 translation defect. The remediation must translate the actual immutable `library_template.card_identity`/`count` and commander objects into the natural-start scenario; no fabricated placeholder name is allowed.

### B. `HIDDEN_05` / `HIDDEN_06` — face-down exile is intentional

The requested semantic object `obj:hidden-hand` is, in these two records:

- identity: `Demonic Tutor`;
- owner/controller: `P2`;
- zone: `exile`;
- `face_down: true`.

The same records also contain a distinct battlefield face-down object `obj:facedown` (`Grizzly Bears`).

The knowledge obligation grants P1 temporary permission to look at `obj:hidden-hand` while it remains the same face-down exile object; HIDDEN_06 additionally requires invalidation when it becomes a new object/changes zone.

Therefore the existing WS46/XMage scenario guard `face_down only applies to battlefield` is too narrow for this immutable obligation. Remediation must use XMage-native face-down exile / revealed-knowledge semantics; it must not coerce the object to battlefield or make the identity public.

### C. `HIDDEN_10` / `HIDDEN_11` — library range shape

The immutable known-library-range entries are structured objects, not an invalid scalar interval:

HIDDEN_10:
`{ "viewer": "P1", "player": "P1", "start": 0, "count": 2, "ordered": true }`

HIDDEN_11:
`{ "viewer": "P1", "player": "P2", "start": 0, "count": 2, "ordered": true, "before_event": "shuffle" }`

`start: 0` is source-authoritative. The current `WS46_KNOWLEDGE_LIBRARY_RANGE_INVALID:<player>:0:2` rejection is therefore a provider/bridge interpretation defect, not a contract error.

Remediation must bind this zero-based top-of-library range to native library order plus the XMage knowledge ledger (`LookedAt`/`Revealed`/invalidation state as applicable), and HIDDEN_11 must preserve the pre-shuffle invalidation obligation.

### D. `WS05-MP-TURN-3` / `WS05-MP-TURN-5` — extra-turn creation shape

`extra_turn_creation` is a list of structured entries. Each entry contains:

- `player`;
- `source` semantic object id;
- integer field `sequence`;
- descriptive `semantic_resolution`.

Both fixtures contain two creations:

1. P2 from `obj:mp-time-warp`, `sequence: 1`;
2. P3 from `obj:mp-nexus`, `sequence: 2`.

There is no immutable integer field named `resolution_sequence`. The current `WS46_JSON_INTEGER_REQUIRED:resolution_sequence` failure is a WS46 schema-binding defect.

Remediation must consume `sequence` and source/player identities and validate resulting order from native `GameState.turnMods`; `semantic_resolution` is descriptive source provenance and must not become a second rules engine.

### E. Six elimination fixtures — trigger shape

For all six current failures, `elimination_trigger` is exactly:

`{ "player": <Pi>, "reason": "life_total_0" }`

The corresponding requested player state has that player at native life total `0`, while `lost` and `eliminated` remain `false` at the construction boundary.

There is no immutable `condition` string field. The current `WS46_JSON_STRING_REQUIRED:condition` failure is a WS46 schema-binding defect.

Remediation must accept the source-authoritative `reason == "life_total_0"` and derive the pre-SBA trigger condition from native `Player.getLife() == 0`; it must not pre-apply the loss or fabricate a loss event during construction.

## Fail-Closed Constraints

The next patch MUST NOT:

- echo immutable request values as observed native state;
- rename or rewrite WS44 fields;
- weaken requested-state digest equality;
- treat descriptive `semantic_resolution` as rules execution;
- publish hidden face-down exile identity to unauthorized viewers;
- preserve HIDDEN_11 library order knowledge after the specified shuffle invalidation;
- pre-run elimination SBA/loss during construction;
- import historical runtime credit.

## Credit State

- current fresh construction runtime: `88/107`;
- construction PASS: `NOT GRANTED`;
- independent normalization: `NOT GRANTED`;
- fresh behavior: `0/107`;
- `XMAGE_SUCCESSOR_PROVIDER_QUALIFIED = FALSE`;
- historical successor runtime credit imported: `0`.

## Exact Next Action

Patch only the five source-proven translation/native-state defects above against the current WS46 bridge/overlay implementation. Compile and execute a fresh exact Full107 Construction v2 run. Persist every remediation and resulting CI evidence. Construction credit remains blocked until 107/107 native setup and a separate independent native-readback normalization both pass.
