# WS-49 CHECKPOINT 07 — PREGAME ACTOR BINDING REMEDIATION

Status: **PERSISTED / NO PASS CREDIT GRANTED**

## Exact failure evidence

- provider head: `8de1964d7ae4197e8e2b5b8a5ad09da1707394ac`
- workflow run: `34282287373`
- job: `102249656867`
- outcome: failure; `100/107` native setup-ready and `7/107` fail-closed

The actor-safe option-rebind regression was no longer present.  The seven
remaining NATURAL_GAME_START rows proceeded into native pregame but exposed
three provider readback/adapter defects:

1. actor-safe observation replaces external player references with opaque
   handles, while the runner incorrectly keyed native readback by `player_id`
   rather than the independently emitted native seat;
2. the runner treated XMage's internal callback order for private mulligan
   prompts as a semantic player-decision order; and
3. `WS05-CMD-MULL-2` reached an additional native `target` prompt, now
   intentionally captured with an actor-safe structured diagnostic rather
   than silently skipped.

## Bounded remediation

The runner now reconstructs canonical P1..Pn only from the native stable seat
field and validates a complete unique seat set.  Mulligan instructions are
bound to canonical player plus round, and every native callback consumes only
that actor's next immutable response; callback ordering is retained as
evidence but cannot change the selected response.  Any duplicate, out-of-
range, unplanned, or unfinished player-round fails closed.

No default response, option position, random selection, AI, GUI, or silent
skip was introduced.  The unexplained `target` prompt remains fail-closed and
will be classified from the next exact-head artifact.

Focused local checks:

- Python compile PASS;
- deterministic player-round grouping and seat mapping assertions PASS.

## Next automatic action

Push the focused runner remediation, obtain fresh exact-head Full107 evidence,
and inspect the remaining `WS05-CMD-MULL-2` prompt if it persists.
