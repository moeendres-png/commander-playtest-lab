# Workstream STATE — real-deck 4P e2e gate (2026-09-23)

- Branch: `opencode/real-deck-e2e-gate-20260923`
- Worktree: `/home/moeen/code/ws-real-deck-e2e-gate-20260923`
- Base: `69d6beb8bc43a2cb578820e23270db3308502c65`
- Progress:
  - [x] Ownership established (branch/worktree/base verified, contract + lock)
  - [x] Reuse-first inspection (runner/batch/replay/pilots/decks mapped)
  - [x] Phase A baseline (bridge built; 36 variable-player + new gate tests green)
  - [x] Phase B real-deck single game (seed 20260923 TERMINAL, winner seat 2, 12 decision classes)
  - [ ] Phase C replay (same-seed transcript match)
  - [ ] Phase D 10-game batch
  - [ ] Artifacts + validation + PR/merge decision
- Root causes fixed (all runtime-proven, no card/label heuristics):
  - Pilot selected cost+tap activations with empty pool, spending the shared
    tap mid-payment (fetch {1},{T},sacrifice; signet {1},{T}) -> activation
    failed. Fix: bridge projects engine-native cost facts (Mana amounts,
    tap/untap/sacrifice-source flags, source tapped, Mana.enough pool
    coverage); pilot uses booleans for discretionary ranking only; engine
    re-validates everything; unknown facts -> no gating.
  - Bridge treated pilot Cancel at mana payment as fatal. Fix: cancel aborts
    to native pass; genuine failures (no cancel) stay fatal.
  - Library bottom-ordering (Dig Through Time) misrouted into London-hand
    bottom valuation. Fix: London path only when options are hand cards;
    otherwise generic offered-option ranking.
- Authority adjudication (coordinator delta): pilot gate is discretionary
  ranking among engine-authorized options using authoritative structured
  cost metadata, NOT a legality verdict (see _priority_action_affordable
  docstring). Executability stays XMage-native (offers + execution/abort).
