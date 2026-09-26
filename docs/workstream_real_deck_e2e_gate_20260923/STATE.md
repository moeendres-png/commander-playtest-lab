# Workstream STATE — real-deck 4P e2e gate (2026-09-23)

- Branch: `opencode/real-deck-e2e-gate-20260923`
- Worktree: `/home/moeen/code/ws-real-deck-e2e-gate-20260923`
- Base: `69d6beb8bc43a2cb578820e23270db3308502c65`
- Progress:
  - [x] Ownership established (branch/worktree/base verified, contract + lock)
  - [x] Reuse-first inspection (runner/batch/replay/pilots/decks mapped)
  - [x] Phase A baseline (bridge built; 36 variable-player + new gate tests green)
  - [x] Phase B real-deck single game (seed 20260923 TERMINAL, winner seat 2, 12 decision classes)
  - [x] Phase B re-validation on final code (v7: TERMINAL, 18137 decisions, winner seat 2)
  - [x] Phase B re-validation (v9: TERMINAL, 16252 decisions, winner seat 2)
  - [x] Replay twins both terminal (7243/5946 decisions) but semantic
    mismatch: cross-process engine UUIDs leaked into pilot tiebreaks.
    Fix: twin-stable content-derived view ids everywhere (priority,
    targets, semantic/mode, boolean, pile; attack/block/mana already
    stable) + card-name bottom tiebreak. Unit order-independence green.
  - [x] Phase C replay semantic match, final code (twins 10826/10826,
    winner seat 2, identical transcripts; raw mismatch by construction)
  - [x] Phase D batch v12 on final code: 10/10 TERMINAL, seeds
    20260923-20260932, winners seats {1,2,3,4}, 4581-13883 decisions,
    default heap, all fresh processes. Zero failures.
  - [x] Single seed 20260923 on final code: TERMINAL, 10826, winner 2
    (transcript identical to replay twins: guards inert on loop-free games)
- Bridge full suite: 200 tests, 1 error in
  XmageNativeStateRestorationTest.partnerCommandersMatch
  (UNKNOWN_CARD_NAME: Grizzly Bears, card-DB contention under suite load);
  passes 15/15 in isolation; untouched by this workstream's paths.
  Re-running full suite for a clean claim.
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
  - Modal cast failed on targetless mode (engine skips target callbacks via
    canChoose, no bridge signal). Fix: bridge projects mode_targets_available
    from Target.canChoose per mode; pilot prefers viable modes; no-viable-mode
    casts map to pass (601.2 rewind); genuine failures stay fatal.
    Correction: Target.isRequired(Ability) is false for unactivated spells,
    so the probe mirrors the engine flow with minNumberOfTargets+canChoose.
  - Hybrid {U/R} payment livelock (54k identical mana_payments): pilot spent
    unusable pool mana (prompt-text heuristic blind to hybrids), engine
    re-prompted unchanged. Fix: bridge projects native ManaCost.testPay per
    pool option; policy filters non-advancing spends; identical-offer repeat
    guard (3x) takes the offered cancel. No color parsing in the pilot.
- Known risk: same-seed twins run in fresh processes with per-process engine
  UUIDs; pilot tiebreaks on engine UUIDs can diverge twins (replay match).
  Cross-process determinism hardening is next if replay mismatches.
- Authority adjudication (coordinator delta): pilot gate is discretionary
  ranking among engine-authorized options using authoritative structured
  cost metadata, NOT a legality verdict (see _priority_action_affordable
  docstring). Executability stays XMage-native (offers + execution/abort).
