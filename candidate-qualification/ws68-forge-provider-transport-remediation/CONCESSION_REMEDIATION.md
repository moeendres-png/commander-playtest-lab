# WS68 — Native Concession Transport Remediation (G04 decision path)

- Workstream: `ws68/forge-provider-transport-remediation-20260912`
- Code commit: `903b3f4a6ff9f5228a3d8210429d5a0689383ec9`
- Provider build: `/tmp/ws68-ev` digest `c4fb2245…` (state/transport digests unchanged)
- Engine pin: `a9a95db6662c2d28814390a9c0c2f986e39aa8b4` (read-only; no Forge edits)
- Remediated packet: `WS65-RP-CONCESSION-EMITTER-01` (was: zero concession frames in
  61,914; `ws62RequestConcession` existed with zero call sites)
- Behavior credit granted in WS68: `0/107` (remediation/requalification only)

## 1. Authority split

Rules Core owns concession legality (`PlayerController.canConcede`: in-game and
game-not-over, no priority/phase/principal gate) and the outcome including
multiplayer leave-game cleanup (`concede()` → `GameAction.concede` →
`player.concede` + `checkGameOverCondition` → `Game.onPlayerLost`, native 800.4).
The provider transports only the external Decision: conditional offer (labels
project native authority + pid), harness selection among offered options,
submission through the `concede()` seam exclusively.

## 2. Implementation: offer anywhere-legal, execute where-safe (two-phase)

**Offer** — `autoPassCancel` hook. The engine calls `autoPassCancel` for every
player on every turn boundary outside priority (CLEANUP sweep over all players
plus the post-game reset), so the offer is reachable in natural play without
any priority coincidence. Authorization is `canConcede()` alone; there is no
priority-holder, turn, or step check in the new code (`PhaseType` count
invariant across the patch). Not-legal sweeps (eliminated players, post-game)
record an automatic and return silently. Labels reuse the WS62 grammar
(`WS62:CONCEDE:authority=PlayerController.canConcede:true:player=<pid>` +
`WS62:CONCEDE:opt=DECLINE`, kind `concession`); zero/multi/stale matches fail
closed. The pre-existing `autoPassCancel` automatic record is preserved.

**Execution** — deferred to the next priority consultation of the conceding
player (`chooseSpellAbilityToPlay` top). This is by engine necessity,
DIRECTLY_VERIFIED: the CLEANUP sweep iterates the LIVE player list
(`PhaseHandler:411` over `game.getPlayers()` which returns live
`ingamePlayers`; `Game.onPlayerLost` removes from it), so a re-entrant
`concede()` inside the sweep fails the engine's own iterator
(`ConcurrentModificationException` — see §5). The priority loop is
counter-driven and carries an explicit active-player-lost handoff
(`PhaseHandler:1058-1064`, "so it sees you conceding on own turn"), i.e. the
engine tolerates concession at priority. On execution the seam is re-checked
(`NOT_LEGAL_AT_EXECUTION` guard), `concede()` is called, a binding
`ws68Concession:EXECUTED` native event is emitted, and no further frame is
offered (a lost player takes no actions). The ACCEPT→EXECUTE lag is at most a
few frames (next priority of that player) and is journaled end-to-end.

**Why not offer at priority too?** Priority-coincident offers would make every
opportunity priority-coincident (effective priority gating) and would double
priority frames. Emission stays non-priority; only the execution venue is
priority-safe. Authorization, emission, and selection are all
priority-independent (ACCEPT evidenced at CLEANUP with nobody holding
priority); engine-level non-gating is independently proven (Ws59 4/4, concede
during opponent turn/priority).

## 3. Requirement compliance

- No priority gating: no priority-state check; offers fire in CLEANUP (priority
  is not passed there); ACCEPT at turn 50 CLEANUP.
- No direct orchestration: exactly 2 `concede();` seam calls in the provider
  (WS62 site + WS68 drain); zero `player.concede()` / `Player.concede` /
  `getAction().concede` (build-time grep gates).
- No GUI default: the provider never auto-selects; every offer goes through
  `broker.choose` to the harness.
- No fabricated availability: offers emit only when native `canConcede()` is
  true, with the consulted value embedded in the authority label.
- Explicit decline path: `DECLINE` offered on every frame; 199/200 declined in
  qualification (plus `ws68Concession:DECLINED` automatics).
- Authoritative/replayable identity: `WS62:CONCEDE:authority=…:player=P1` +
  ACCEPT at deterministic frame 1879 across three independent runs.
- Engine-owned cleanup: provider performs zero cleanup; 800.4 evidenced (§4).
- Production-reachable: 200 offers through the normal protocol in a real
  session (not a test-called helper); the seam executes in-session.

## 4. Evidence (final build `c4fb2245`, accepted pin)

- `RQ-C3-G04/journal.json.gz` (1907 frames, hidden PASS): 200 `concession`
  frames (all cleanups, all players); 199 pilot-DECLINED; ACCEPT frame 1879
  (P1, turn 50 CLEANUP, authority `…canConcede:true:player=P1`); milestones
  `ACCEPTED_DEFERRED` → `EXECUTING_AT_PRIORITY` → `ws68Concession:EXECUTED
  player=P1`; zero post-loss P1 frames; first 3-player snapshot at frame 1885
  (turn 51 UPKEEP); game continues to frame 1907.
- 800.4a leave-game correction: P1-owned objects cease across the leave
  (Control Magic MINTED-22 and P1's lands/graveyard cards vanish from all
  zones); stolen Bear-107 (owned by P2) remains on the battlefield;
  Control-Magic-establishing prefix (cast t49, paid, targeted — all script
  entries consumed) proves the stolen-control precondition.
- Pilot standing instruction (harness, documented in `ws68_runner.py`): never
  concede except when scripted; unscripted offers select the single offered
  DECLINE (fail closed otherwise). This is pilot behavior (like passing
  unscripted priority), not a provider default — the provider offers both
  options every time and never auto-selects.
- Determinism: ACCEPT at frame 1879 in all three G04 runs (CME demo + two
  final-build runs), establishing replayable Decision identity.

## 5. Engine limitation discovered (new defect packet, out of WS68 scope)

`WS68_SWEEP_REENTRANCY/journal_cme_demo.json.gz`: the first-generation overlay
called `concede()` synchronously inside the sweep offer. Frame 1879 ACCEPTED,
then the session died immediately with
`UNEXPECTED:java.util.ConcurrentModificationException` and zero subsequent
frames. Classification: `ENGINE_DEFECT` (engine iteration not re-entrant at
this hook point; provider and harness behaved correctly — the seam was reached
through the conformant path). Causal chain (all at the accepted pin):
`PhaseHandler:411` iterates live `game.getPlayers()` → `Game.getPlayers`
returns live `ingamePlayers` → `Game.onPlayerLost:999` removes from it →
fail-fast iterator throws on the next sweep step. The GUI never hits this
because its concede arrives asynchronously between engine steps. Remediation
(engine-side, forbidden in WS68): snapshot the sweep list or serve concession
through an engine request queue. The two-phase transport is the conformant
workaround: it never asks the engine to do what the engine cannot do.

## 6. Re-entry readiness

The credited G04 path (Control-Magic state + concession Decision + leave-game
cleanup with game continuing) is fully evidenced through the qualified
transport. `G04_CONCESSION_REENTRY_PREREQUISITE=READY` for a future crediting
wave. Outcome flags (`conceded()` vs `hasLost()`) are not journaled by the
transport (same visibility class as tap flags in WS65 A03) and are
`EXTERNALLY_RULE_VALIDATED` via the seam identity (the Ws59 suite proves the
seam sets them; the provider calls the same seam).

## 7. Remaining limits

- Pending-Decisions execute at the player's next priority; a game ending first
  would leave `ACCEPTED_DEFERRED` without execution (journaled explicitly).
- A pending player consulted elsewhere before their next priority fails closed
  (no script covers doomed-player decisions); G04 exhibits no such consultation.
- Post-terminal intent exhaustion (`BLOCKED_AT:discardToMaximumHandSize`, class
  `HARNESS`) ends the Leon after the behavior is complete.
