# WS218 IDENTITY_INVENTORY

Provenance: source inspection of `XmageFullGameDecisionController`,
`XmageFullGamePlayer`, `XmageFullGameStateRedactor`, `XmageAuditEventLog`,
`XmageFullGameSession`, `XmageFullGameActionProjection`,
`ExternalPilotDecisionPolicy`, `Ws215LifecycleProbe`.

## Process-local (NEVER hashed; mapped or redacted)

- `game_id` engine UUID (`controller.request gameId=game.getId()`; `actorView game_id`).
  Mapped to `"game"` / seat keys. Proven nonsemantic: twins mint distinct ids
  with identical semantic transcripts (`WS215_MATRIX` transcript_hash MATCH
  while `distinct_actors`/`last_submission` UUIDs differ).
- `actor_id` / `player_id` native UUIDs. Mapped to `seat:N` via the live
  seat map. Proven nonsemantic as identity (seat rotation is the semantic
  content; UUID equality across processes never holds).
- `option_id` for object/ability/combat paths: either raw target UUID
  (`objectOptions id.toString`), `abilityOptionId stableId(sourceId,originalId)`,
  `optionId stableId(...)` over UUIDs, or attacker UUID. Never hashed raw;
  resolved via observation-joined projection. Stable only for
  mulligan keep/mulligan (`stableId("mulligan",...)`), boolean
  (`stableId(class,true/false)`), choice-key (`stableId("choice-key",key)`),
  mana-pool (`stableId("mana-pool",type)`), pile slots, numeric-only.
- Ability `source_object_id` / `ability_original_id` / `card_id` /
  `defender_id` / `attacker_id` / `blocker_id` / `mode_id` UUIDs. Same rule:
  join to observation or drop; label/source_name carry the semantics.
- `decision_id=stableId(gameId,offset,actor,class)`. Process-local because
  inputs are. Tape revision is `decision_offset` (monotonic stable).
- Prompt/label `object_id='...'` attributes, bare UUIDs, GameLog `[xxx]`
  short-ids, choice ` [xxx]` suffixes. Redacted by `redact_text`
  (lineage: `_semantic_text` / `redactObjectIds` / `choiceText`); tests prove
  redaction preserves Rules text while normalizing twins.
- `action_id=decision_id:option_id` (projection). Opaque, decision-bound,
  never a replay key; consumer submits CURRENT native ids.
- Array positions of unordered sets (battlefield, hand, command, legal
  options). Sorted by semantic fingerprint before digest; ordered zones
  (stack, graveyard order, transcript order) stay ordered.

## Semantic (hashed)

- Decision class strings (17 production classes + `concede` lifecycle).
- Actor principal seat (1..N, = engine seat+1).
- Revision `decision_offset` (strictly increasing).
- Redacted labels/prompts, boolean `value`, choice `choice_key`/`choice`
  text, pile name multisets, `mana_type`, ability `ability_type`+`source_name`
  + redacted ability text, replacement `source_name`+label, mode text,
  numeric value+bounds, target/attacker/blocker public projections
  (name, controller/owner seat, tapped, power/toughness, damage, counters,
  face-up ability text, zone occurrence).
- Observation: turn/phase/step, life/poison/counts, public permanents,
  graveyard order (names), command (names), stack order (names),
  commander damage/tax rows, actor hand names (sorted) + mana + land-plays,
  granted_library names (sorted, window-only).
- RNG: root seed + explicit/require + per-step calls before/after.
- Events: offset range + canonical digest over the above (no debug strings).
- Terminal: seat-mapped outcomes (seat/won/lost/left/life) + turn + calls.

## Ambiguity rule

If two distinct native options share a fingerprint under this model, the
recorded choice is AMBIGUOUS and the replay FAILS CLOSED
(`CHOSEN_OPTION_AMBIGUOUS`). The model never picks first/positional/GUI.

Machine companion: `IDENTITY_INVENTORY.json`.
