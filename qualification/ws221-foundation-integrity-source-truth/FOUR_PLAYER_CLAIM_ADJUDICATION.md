# WS221 Four-Player Claim Adjudication (S11)

Living, fixed (production-reachable / operator-facing):

- docs/OPERATIONAL_SIMULATION_POLICY.md → reconciled: 4P primary decision mode,
  2–5P technical conformance, bounded-lane limits, 4P conformance workflow until
  S5, 6P stretch/unsupported.
- src/commander_lab/robustness.py ×2 guards → enforcement kept, messages
  lane-scoped ("outside this lane's scope"; 2–5P full-game lane pointer). The
  "out of project scope" wording was the false project-scope exclusion.
- tests/unit/test_operational_4p_policy.py → updated to the lane-scoped contract.
- docs/architecture/xmage-full-game-external-pilots.md → "exactly four-player"
  scoped to current conformance evidence (S5 pending); 2–5P lane capability noted.
- docs/architecture/deckbuilding-simulation-separation.md → scenario contract
  annotated variable-player (2–5, FutureXmageScenario ge=2 le=5); 4P shape kept
  as the primary-decision instance.

Deliberately untouched (provenance / bounded fixtures / foreign ownership):

- qualification/** seals and candidate reason prose (xmage.json single-pod-size
  integration note, PLAYER_COUNT_IMPACT, CAPABILITY_TRUTH, IMPACT_MAP,
  FINAL_HANDOFF, ENTRYPOINT_REACHABILITY): historical seal state, not living
  claims; test consumers check coverage/codes, not prose.
- scripts/run_external_full_game_conformance.py + xmage-full-game-conformance.yml:
  S5-owned, read-only (follow-up: S5 parametrizes 2–5P).
- src/commander_lab/whole_deck/optimizer_v2_decision_runtime.py (single-pod-size
  decision runtime message): frozen decision contract with a 2048-4P
  sealed holdout; true of that runtime, changeable only by separate validation.
- tests/unit/test_xmage_full_game.py (4-player scenario instance): valid 4P instance fixture
  of a 2–5P-capable contract, not a scope claim.
- Tactical/Structural 4P fixtures (tactical.py guard, pod_scheduling,
  project_context): intentionally bounded diagnostics.
