# Engine adapter protocol 1.0.0

The bridge is a persistent newline-delimited JSON process. The authoritative
schema is `schemas/engine_adapter_protocol.schema.json`.

## Request envelope

Every request contains:

- `protocol_version`
- `request_id`
- `timestamp`
- `engine`
- `engine_version`
- optional `game_id`
- `message_type`
- `payload`

Required message types:

```text
engine_hello
engine_capabilities
load_deck
create_game
set_seed
start_game
get_game_state
get_legal_actions
submit_action
advance_priority
advance_phase
get_event_log
export_replay
shutdown_game
```

## Response envelope

Every response contains:

- matching `request_id`
- `success`
- `status`
- `payload`
- `warnings`
- `errors`
- `engine_event_offset`

Unknown messages, protocol mismatches and illegal actions must return a failed
response and must not mutate the game state.

## Handshake

`engine_hello` returns provider and exact engine version.
`engine_capabilities` returns actual observed capabilities, including:

```text
commander_supported
partner_supported
multiplayer_supported
max_players
headless_supported
seed_supported
deck_import_supported
legal_actions_supported
action_submission_supported
event_log_supported
replay_supported
stack_visible
priority_visible
commander_damage_visible
commander_tax_visible
```

The Python client never infers a capability from the provider name. Missing core
capabilities cause `degraded` or abort. `healthy` additionally requires
`runtime_kind=external_rules_engine`.

## Compatibility

Phase-8 `method` and `params` aliases remain accepted for migration tests. Such a
legacy probe is not sufficient for an external healthy status.
