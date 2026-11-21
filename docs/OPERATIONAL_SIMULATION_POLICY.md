# Operational Simulation Policy

> **State 2026-11-18 (seat counts).** The player bounds below are out of date. In current source
> `XmageFullGameRunner` (`src/commander_lab/engine/rules/full_game.py`) and the bridge
> (`XmageFullGameSession.java`) both have `MIN_PLAYERS = 2` and `MAX_PLAYERS = 6`. The 2–5P lane
> qualification named below (WS215) does not cover six seats; six-seat behaviour is `UNKNOWN`
> (`docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`). Studio rule: two to four seats are active;
> five and six stay locked until their own qualification and the Owner's release
> (`docs/OWNER_DECISIONS_STUDIO_20261118.md`, section 4 and section 6). The Studio start path
> enforces it (`studio/launch.py`, `MAX_RELEASED_SEATS = 4`, PR #1515), and so do the series routes
> and `compare-decks` (PR #1536; `compare-decks` has the switch `--allow-unreleased-seats`, off by default).

Current policy effective 2026-09-15 (WS221; supersedes the 2026-08-20 revision,
which restricted operations to a single pod size):

- **Primary deck-decision mode is 4-player Commander** (one own deck, three
  opponents). Official deck-comparison campaigns, optimization, and readiness
  gates run 4P unless a separately authorized decision contract states otherwise.
- **Technical conformance covers 2–5 players.** The production full-game lane
  (`XmageFullGameRunner`, `MIN_PLAYERS=2`, `MAX_PLAYERS=5`) is qualified for
  2–5P per WS215; a 4P result does not establish another count's correctness.
  2P/3P/5P work is in project scope wherever the executing lane supports it.
- **Bounded lanes retain their implemented limits.** Project-level
  tournament/robustness configuration and Structural self-play remain
  4-player-pod bounded; their guards fail closed on other counts. That is a
  lane limit, not a project-scope exclusion: use the 2–5P full-game lane for
  other counts.
- **Conformance-workflow evidence is 4P until S5.** The external full-game
  conformance script/workflow still runs seeded 4P games; 2–5P CI expansion is
  deferred to successor S5. This does not narrow lane capability.
- **New Owner decision (2026-11-08): a permanent maximum of 6 players** in every new
  operational simulator session, 4P still the default. There is **no 7+/8P stretch
  goal**; isolated technical feasibility research on eight seats at most stays possible on explicit Owner assignment and admits no operational session. This hard product maximum is independent of qualification: a lane that is
  qualified only for 2–5P does not gain 6P evidence by policy declaration. See
  `docs/OWNER_DECISION_SIX_PLAYER_MAX_20261108.md`. Historical artifacts are unchanged.
- Generic low-level StructuralSimulator capability may remain for isolated
  technical engine-correctness tests; it is not an operational decision path.
- Historical 3P/5P references or artifacts are provenance only, not current
  evidence requirements — except WS215 2–5P qualification seals, which are
  living authority for lane capability.
- Useful robustness axes remain within 4P: opponent composition, pilot/mulligan
  policy, seat position, commander denial, ablation, worst case, rebuild,
  protection, interaction, and finish structure.
- Structural results remain `structural_model_estimates`, not empirical win rates.
- This policy does not mutate canonical deck lists, inventory, purchases,
  opponent truth, or physical allocations.
