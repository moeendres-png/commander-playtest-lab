# AF09 clean-process semantic replay twins (2026-10-01)

Workstream: `AF09-CLEAN-PROCESS-REPLAY-TWINS-20261001` (GitHub #454, parent #255,
concurrency ruling #255 comment 5936731960).

`PRODUCTION_PROVIDER = NOT_SELECTED` · `ARCHITECTURE_FREEZE = NOT_CLAIMED`

This packet documents the AF09 clean-process semantic replay contract and the
per-candidate results produced under it. It does not rank candidates and does
not select a provider.

## The contract

A candidate/fixture twin runs two (or more) genuinely fresh OS processes and
binds, per process:

1. **fixture identity** — fixture id, candidate, player count, requested seed,
   lane, deck identities and hashes;
2. **candidate/build identity** — the provider's own version payload (engine,
   version, declared commit, observed artifact kind/sha256), the launch-plan
   build identity and the exact command digest;
3. **Lab source identity** — the producing checkout's commit and tree, with its
   dirty state recorded rather than hidden;
4. **requested seed and provider acknowledgement** — the provider's own echoed
   seed, classified; acknowledgement is a precondition, never replay proof;
5. **externally supplied decision tape** — one semantic entry per answered
   decision, identified by the engine's own published option identity;
6. **semantic event tape** — the ordered per-decision event digests over
   engine-published transition coordinates;
7. **defined checkpoint state hashes** — the engine-published state digest chain
   (initial, pre and post every answered decision) plus RNG/event coordinates;
8. **terminal facts/outcome** — the engine's game-over state and terminal
   outcome rows, or an explicit bounded horizon (which is not a PASS);
9. **process identities** — pid, pid start ticks and boot id observed from the
   OS, checked pairwise distinct.

`:func:`commander_lab.qualification.current_boundary.replay_twins.compare_twin_runs`
compares two runs semantically and returns typed divergences. A twin verifies
only when every required section is present and non-empty, all compared facts
are identical, the requested seed was acknowledged, the terminal is complete,
and the process identities are observed and distinct.

### Candidate lanes

| Candidate | Lane | Decision identity | Checkpoints | RNG tape | Terminal |
|---|---|---|---|---|---|
| XMage | full-game semantic replay tape (WS218) | recorder fingerprint (`semantic_replay.fingerprint`) | tape `semantic_state_digest` / `post_checkpoint_digest` | per-step `rules_random_calls` | tape terminal checkpoint + fresh-process consumer |
| Forge | Protocol-2 JSONL (`protocol2-jsonl`) | engine `legal_action.semantic_fingerprint` (WS227) | engine `public_state_digest` chain | engine `rng_binding.rules_calls` chain | engine `game_over` + `terminal_outcomes` |

The XMage adapter records two fresh tapes, compares them with the qualified
`comparator.compare_tapes`, and consumes the first tape in a third fresh process
with the qualified consumer. The Forge adapter records a decision tape in one
fresh process and replays it in a second fresh process: before every external
submission it re-checks kind/actor/revision, the engine's public-state digest
and the legal-set digest against the tape, then resolves the recorded semantic
fingerprint to exactly one offered option (zero or multiple matches fail
closed).

Forge's own identity discipline (WS227) deliberately treats fully
indistinguishable duplicate siblings as one colliding fingerprint. The recording
policy therefore chooses the smallest fingerprint that occurs exactly once in
the offered set and fails closed when the entire offered set collides; the
fixture profile uses the in-repo singleton Commander deck lists so that
cleanup-discard decisions always contain distinguishable cards.

Events, RNG use and state transitions originating in the engine are never
invented, re-ranked or normalized by the harness. No second Rules state model
exists.

## Normalization contract

No comparison silently strips anything. The compared surface contains only
semantic, engine-published facts. The only removable values are those on the
declared process-local allow-list:

- `process` and `process_local_identifiers` sections (excluded from comparison;
  the process identity is still checked for observation and distinctness);
- a fixed set of allow-listed keys (session/game/handle identifiers, wall-clock,
  absolute paths) that may be removed **only** through an explicit
  `NormalizationRule` naming one of the declared justifications
  (`process_local_identifier`, `wall_clock`, `absolute_path`).

A rule whose path is not on the allow-list — for example
`decisions.*.chosen_fingerprint`, `semantic_events.*.digest`,
`checkpoint_state_hashes.*.public_state_digest`, `terminal.outcomes`, or
`rules_rng.rng_call_coordinates` — raises `NormalizationContractError` at
construction. Each applied removal is reported with the removed value's digest.

## Mandatory adversarial controls

`run_adversarial_controls` runs on every produced twin (and in the unit suite
on synthetic twins) and requires detection of:

| Control | Expected divergence |
|---|---|
| changed decision | `DECISION_DIVERGENCE` |
| changed seed / RNG binding | `RNG_DIVERGENCE` |
| changed RNG coordinate | `RNG_DIVERGENCE` |
| missing event | `EVENT_MISSING` |
| reordered event | `EVENT_REORDERED` |
| changed checkpoint hash | `STATE_DIVERGENCE` |
| changed terminal | `TERMINAL_DIVERGENCE` |
| same seed, different decisions | `DECISION_DIVERGENCE` |
| same process identity | `PROCESS_IDENTITY_NOT_DISTINCT` |
| normalization of a Rules-significant field | `NormalizationContractError` |

A bounded-horizon terminal, a missing/empty required section, an unacknowledged
seed, or an unobserved process identity can never verify.

## Running the campaign

```
python scripts/run_replay_twin_campaign.py \
    --candidate both \
    --forge-workspace <clean exact-source Forge checkout> \
    [--xmage-mage-jar <exact candidate artifact>]
```

Evidence documents are written to `docs/af09_replay_twins_20261001/evidence/`.
A candidate whose lane cannot expose a required channel is written as UNKNOWN
with the exact missing capability; the campaign never patches bridge production
code and never invents a harness-side state model.

## Results

See `evidence/AF09_REPLAY_TWIN_XMAGE.json` and
`evidence/AF09_REPLAY_TWIN_FORGE.json`. Candidate coverage and every UNKNOWN
blocker are restated in `RESULTS.md`.
