# Operational Simulation Policy

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
- **6 players is an optional stretch**, currently not supported unless later
  qualification changes it.
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
