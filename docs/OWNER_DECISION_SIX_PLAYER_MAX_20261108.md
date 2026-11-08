# Owner decision: permanent maximum of six players per simulation (2026-11-08)

**Decision source:** direct Owner instruction on 2026-11-08 during the Playgroup Live architecture review. This is the newest explicit choice for the supported Commander game size. It supersedes prior research suggestions to explore 7–8 player tables.

## Binding product scope

- **Maximum 6 seats in every newly designed Commander simulation and play surface.** Never offer, plan, implement, benchmark, admit, or advertise an operational 7+ player session. There is no future 8-player stretch goal.
- **Default remains 4 seats:** one Owner deck (currently Chulane) and three opponents. Other supported modes may use 2, 3, 5 or 6 seats after relevant lane-specific runtime qualification.
- Keep all server-side validators, job planners, candidate schemas, pilots, comparison protocols and browser UI fail-closed at **2–6 players**. A solo goldfish may have one human seat as a *separate practice mode*, not a multiplayer simulation. A six-player session must not be claimed qualified merely because the upper-bound validation allows it.
- The motivation is consciously bounded **JVM/CPU time, memory growth, game duration and table readability**, not a claim that Magic rules prohibit 7+ players.
- Never extend this maximum implicitly because XMage upstream could support more seats, a historical capability test has 7+, a UI layout might fit, or another application adds support. Only a new direct Owner instruction can supersede this decision.
- Do not retrofit or delete immutable 7+ historical source/evidence, import-only metadata of real-world games, or unrelated collection records to make an old artifact appear as a supported new simulation.
- Rules remain authoritative **only in the pinned XMage engine**; this decision does not authorize rules shortcuts.

## Verified boundaries and gaps as of the source lock

Lab main `e3d88eb957813b59d077e9b94bfbc32ce7fa2412`:

| Surface | Observed bound | Action |
|---|---|---|
| `XmageFullGameRunner` and `FullGameSmokeResult` | 2–6 | **Preserve**, do not expand |
| Full-game pilot policy (`full_game_pilot/state.py`) | 2–6 | **Preserve** |
| `DeckComparisonSpec.opponents` | 1–5, yielding 2–6 seats | **Preserve** |
| `FullGameBatchCase` | Rejects player count outside 2–6 | **Preserve** |
| `FutureXmageScenario` | 2–6 | **Preserve** |
| One `TapeGameManifest` / `TapeSeatPrincipal` replay contract | Currently 2–5 | **Known capability gap for 6P**; do not quietly widen without review and tests |
| Structural/tooling metadata `pod_size` up to 10 | Different non-live scopes and legacy references | Audit operational callers before changing; never use this as authorization for a 7+ simulator |

The source `docs/OPERATIONAL_SIMULATION_POLICY.md` describes 4P as the official default and historically labels six as optional/unqualified. This decision fixes the *maximum*, **not** a claim of successful six-player behavioral qualification.

## New work acceptance criteria

1. Automated negative checks reject `player_count=7` and `8` at every new admission or planner endpoint; six is not rejected on *grounds of this product cap*.
2. Full-game, replay, observation isolation, network update fanout and renderer should be evaluated for 2/4/6 seats only. For 6P, evidence must be a separate successful exact-source run; lower-player PASS results do not promote automatically.
3. Chulane-pod runners may remain 4P while the backend exposes bounded, qualified 5/6P. Do not manufacture six-player readiness or win-rate results.
4. Do not make a global rewrite to historical recorded-games metadata: the limitation applies to **new simulator sessions**, not real-life game records imported for analytics.

## Review status

Owner-declared policy: **DIRECTLY_VERIFIED (instruction)**. Current code bounds: **CODE_DERIVED** from repository source. Exhaustive current-head 6P game behavior: **UNKNOWN / not run in this workstream**. No XMage pin change.

Related audit: `docs/research/PLAYGROUP_LIVE_PHASE1_ARCHITECTURE_AUDIT_20261108.md`.
