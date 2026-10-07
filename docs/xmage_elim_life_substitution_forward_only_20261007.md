# Forward-only note: the XMage elimination life substitution is a declared variance

**Date:** 2026-10-07 · **Authority:** Coordinator ruling on #585 (comment 6036312389, condition 2)
· `PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

## What changed

The XMage mid-game causal elimination openly substitutes the victim's recorded life at the
pre-causal position, because the recorded value is the state-based-action-pending instant of
CR 704.3 and no priority point shows it. The engine plans the substitution itself
(`XmageMidgameCausalBridge.java:221-232, 531-547, 913-920`) and publishes the pair in the
`create_midgame_game` response's `elimination_plan.life_substitutions`.
`docs/xmage_elim_composed_20261003/README.md` describes the same route.

The receipt nonetheless labelled an otherwise-`EXACT` construction of such a row `EXACT`
with the assertion class `BEHAVIOUR_OBSERVED`, which hid the declared deviation. From this
commit, when the engine's own verdict for the row is `EXACT`, the Lab labels it exactly as
the Forge scenario lane does for the same disposition
(`forge_scenario_lane.py:1474-1493, 1728-1735, 3921-3929`):

- `construction_verdict`: `ALLOWED_VARIANCE`, never `EXACT`, with its own top-level
  `variance_source` naming the declared causal elimination and CR 704.3;
- `assertion_class`: `BEHAVIOUR_OBSERVED_LAB_DECLARED_CAUSAL_SUBSTITUTION`.

The overlay applies only to an engine verdict of `EXACT`. An engine `ALLOWED_VARIANCE` —
the declaration-step priority allowance on `WS05-MP-ELIM-PRIO-3` / `WS05-MP-ELIM-TURN-3` —
is the engine's own disposition and keeps its own `variance_source`
(`ENGINE_DECLARATION_STEP_PRIORITY_ALLOWANCE_VARIANCE_SOURCE`) and its own assertion class
(`BEHAVIOUR_OBSERVED`). A substitution the same plan declares is recorded beside it in
`declared_substitution_source`, never in place of it, so neither source overwrites the
other.

Scope: only `players.<victim>.life` on rows whose plan carries an elimination entry. A real
construction `MISMATCH` still takes precedence, and a row without an elimination plan or
without a declared substitution keeps the engine's own verdict verbatim.
`midgame_rows.construction_with_declared_substitution` implements the overlay and
`execute_row` applies it before the construction gate.

## Why this note exists (forward-only)

Historical receipts are **not** relabelled. The sealed epoch
`qualification/current-boundary-epochs/ab357d1772c3-8698ff38979c/` pins the old label for
`WS05-MP-ELIM-STACK-3`, `WS05-MP-ELIM-OWNED-3`, `WS05-MP-ELIM-5` and `WS05-MP-ELIM-CONTROL-3`
(`construction_verdict: EXACT`, `assertion_class: BEHAVIOUR_OBSERVED`), and
`WS05-MP-ELIM-PRIO-3` / `WS05-MP-ELIM-TURN-3` pin `ALLOWED_VARIANCE` from the engine's
declaration-step priority allowance — the class the engine keeps today. Those artifacts stay
byte-identical: they are the provenance of the runs that produced them, and the change is
forward-only.

A row earns the new label only from a fresh execution whose receipt is bound to the exact
engine commit and executing Lab runner. No existing credit changes, no receipt is rewritten,
and this note claims no qualification PASS. The epoch itself (`ab357d1772c3`) predates this
change and remains a correct record of what ran then.
