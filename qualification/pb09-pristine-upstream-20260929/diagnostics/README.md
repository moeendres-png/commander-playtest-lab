# PB-09 live-observation diagnostics

Raw, unedited state payloads captured from the **pristine** candidate during the
PB-09 runtime-reachability probe, before the qualification runner existed.

- `live_state_observed_by_p1.json` — `get_game_state` with `observer_player_id=p1`
- `live_state_observed_by_p2.json` — `get_game_state` with `observer_player_id=p2`

These are the raw observations behind the hidden-information finding: each seat
receives its own seven real cards and `<hidden>` placeholders for every opponent,
and the two views differ. They are retained as provenance; the authoritative
hidden-information evidence and its validator verdict are in
`../HIDDEN_INFO_PIN.json`.

Not behaviour evidence for any card: these are projections of a game-start state.
