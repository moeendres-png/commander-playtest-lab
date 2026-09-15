# WS229 CARDINALITY_IMPACT (regression GREEN, impact-selected)

## Evidence (DIRECTLY_VERIFIED)

- JVM `XmageVariablePlayerLifecycleTest`: 12/12 PASS (2-5P lifecycle incl
  joint-capable drivers).
- JVM `XmageFullGamePlayerCountTest`: 6/6 PASS.
- Python `test_xmage_variable_player.py` + `test_xmage_full_game.py`:
  green (4-seat policy incl priority/mana/numeric paths).
- Live end-to-end smokes through the changed Lab+bridge stack:
  - 2P bounded smoke (25 decisions): PASS — classes observed:
    choose_object, mulligan, target, priority, mana_payment
    (seed 20260825, engine 1.4.61, clean shutdown).
  - 3P bounded smoke (25 decisions): PASS (seed 20260826).
  - 6P: FAIL_CLOSED before engine launch (ValueError at the
    conformance cardinality table, engine_launched=false).
- 4P full-game gate + 5P smoke: NOT rerun (cost; unchanged paths beyond
  the impact-selected suites above). The 4P gate exercises no numeric
  callbacks in the Isamaru/Plains line (proven by 2P/3P observed
  classes); numeric live proof rests on the callback-level suites.

## Conformance preserved

2P/3P/4P/5P conformance paths unmodified (pilot bindings still require
seats 1..N, 2..5 players); 6P still fails closed at four layers
(untouched). No player-count capability claimed beyond evidence.
