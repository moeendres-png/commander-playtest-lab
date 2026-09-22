# Checkpoint — next sequential frontier: CARD_02 + START-2 (2026-09-22)

Source lock at checkpoint: `origin/main`
`937b78a6faf8a2701737255563c35156ace2a093`. Mapping: 6 DIRECT (MULL-2/4,
TAX-2/4, PARTNER-ZONE/TAX) / 13 SUPPORTING / 57 UNKNOWN / 31 NOT_RUN_BLOCKED.
Frozen WS47 `5a2e4f46`, engine xmage `1.4.61` / pin `db134b97` unchanged.
Prior workstreams (WS1/WS2/executor/promotion/partner) closed and merged;
this note starts no workstream and owns no implementation surface.

## 1. CARD_02 (first)

Frozen shape: 4P; command-zone Rograkh ×4 (casts 0); no battlefield
objects; turn 1 precombat main P1 active/priority; seed 424242. Scripted
single decision: cast-commander P1 (matches-only-offered, fail-closed both
directions). Procedure: NATIVE_CAST_COMMANDER + NATIVE_RESOLVE_TOP_OF_STACK.
Required: commander_cast, spell_resolved, creature_entered. Terminal:
Rograkh on P1 battlefield, count cmd:P1-A = 1, no tax charged.

Execution sketch (no new capability): WS2 construction + arrival (proven
4P path) + exact-one cast offer for Rograkh with EMPTY pool (fresh count
→ tax {0}; no payment decisions expected — fail closed if any appear) +
submit through the protected path + passes to resolution + terminal
readback (battlefield presence, count 1). Then register/guard/mapping
promotion (DIRECT 6→7) as a separate adjudication.

## 2. WS05-CMD-START-2 (second)

Frozen shape: 2P; command Rograkh ×2 + battlefield Bears ×2; temporal
turn 1 beginning/draw (NOT main); script empty; seed 424242. Procedure:
CONSTRUCT_AND_VALIDATE + CREATE_COMMANDER_GAME_FROM_DECKS_AND_VERIFY_START_
STATE. Required: starting_player:P1, first_turn_draw:false. Terminal: P1
skips the draw-step draw on the first turn (2P rule).

Execution sketch: WS2 construction + arrival DRIVE WITH DRAW-STEP
OBSERVATION (arrival already passes through upkeep/draw priorities —
observed in executor probes): capture the turn-1 draw-step priority round,
assert P1 hand count unchanged through it (7, no draw) and starting player
P1, then continue to main for the construction MATCH. No new capability;
step-aware assertions via the existing readback phase/step fields. Then
register/guard/mapping promotion (DIRECT 7→8) as a separate adjudication.

## Explicitly not started here

No branch, code, or mapping change in this checkpoint. The next workstream
establishes its own exclusive branch/worktree/contract and owns CARD_02
first, START-2 second, each with execution-then-promotion separation.
