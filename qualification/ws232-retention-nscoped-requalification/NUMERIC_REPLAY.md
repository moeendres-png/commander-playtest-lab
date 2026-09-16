# U5-D Numeric-Bearing Semantic Replay: CLOSED (PASS)

## Claim

A scenario containing a repaired WS229 numeric decision is recorded in
one fresh process and replayed in two independent fresh processes, with
the numeric domain descriptor and chosen value bound semantically.

## Evidence (DIRECTLY_VERIFIED)

Tape `tapes/ws232-tape-arcnum-2p.json` (2P Arc Lightning symmetric decks,
seed 424242, tape schema `semantic-replay-tape/1.0.0`):

- 502 steps; decision classes include `target_amount` (2 frames: the
  structured divide + companion with bounds and chosen values recorded
  as semantic numeric coordinates, not raw text).
- Rules-Core RNG regenerated (`require_explicit_seed`, 196 -> 784).
- Replay B (fresh process): PASS, 502/502 steps verified.
- Replay C (fresh process): PASS, 502/502 steps verified.
- Semantic option matching (exactly-one), event/state/checkpoint digests,
  terminal-state verification, principal-scoped digests, no injection.

The numeric descriptor (`[1,3]` -> 2, `[1,1]` -> 1) and chosen values are
bound in the tape's numeric coordinates and re-verified on replay; the
replay consumer recomputes digests and fails closed on divergence
(TAMPER matrix carries over by schema stability, predicates bind the
consumer blob).

## Machine companion

`NUMERIC_REPLAY.json` (this file's table is the summary) and
`REPLAY_RNG_5_MATRIX.json` records.
