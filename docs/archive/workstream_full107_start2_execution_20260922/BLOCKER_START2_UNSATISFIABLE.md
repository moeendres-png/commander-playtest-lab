# Blocker — WS05-CMD-START-2 unsatisfiable as specified (2026-09-22)

Status: FAIL-CLOSED. No mapping change. Production delta in this
workstream: repository-readiness guard in card materialization only
(`ensureRepositoryReady` shared; proven by test progression past
materialization). Temporal-envelope/inverse-map extensions reverted
unproven. Execution test kept `@Disabled` with the exact enabling
conditions.

## Frozen demands (all mandatory)

- `first_turn_draw:false`, `starting_player:P1`; terminal: P1 skips the
  draw-step draw on turn 1 (2P rule, CR 103.7a shape).
- Temporal: turn 1, beginning/draw, active P1, priority P1.
- Construction digest equality (same gate as all DIRECTs).

## Observed engine behavior (pinned xmage 1.4.61, proven by live test)

- Pre-start assembly, keeps, passes, and arrival all work; upkeep park
  shows P1 hand 7 (no early draw); draw-step park shows P1 hand 8:
  exactly one draw occurred AT the draw step.
- Root cause (engine sources, pinned commit): `DrawStep.beginStep`
  draws unconditionally; the 2P skip exists only as
  `GameCommanderImpl.startingPlayerSkipsDraw`, which
  `CommanderFreeForAll.init` hardcodes to `false`. No draw-suppression
  mechanism exists; the only skip path is a step-removing TurnMod.

## Exhaustion proof (both remediations fail)

- Skip disabled (current): draw occurs → `first_turn_draw:false` and the
  terminal are violated.
- Skip enabled (TurnMod): `Phase` skips `playStep` entirely, so no
  priority ever parks at the draw step → the requested temporal point
  (turn 1/beginning/draw/priority P1) is unobservable → digest equality
  and event observation are impossible.
- Harness-side draw suppression (undoing the draw) would be outcome
  manipulation: forbidden, not attempted.

## Authority questions (in order)

1. Rules: for 2P Commander, is the correct semantic step-removal (CR
   103.7a letter) or draw-suppression with a live step? If step-removal,
   the fixture's temporal expectation is unsatisfiable as specified.
2. If draw-suppression: engine-repo change (new behavior) via a separate
   engine workstream + pin change + full requalification — or a frozen
   successor contract revising the fixture.
3. Evidence policy: no mapping credit for START-2 under any reading until
   (1) is adjudicated and (2) implemented; the digest gate additionally
   requires the observable temporal to match.

## Enabling conditions for the disabled test

`XmageFullGameStart2ExecutionTest` may be enabled iff: (a) the engine
 demonstrably satisfies `first_turn_draw:false` with an observable
 turn-1 draw-step priority for P1, and (b) its construction digest
 reproduces the frozen hex. Until then it stays disabled and START-2
 stays NOT_RUN_BLOCKED.
