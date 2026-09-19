# Port Ledger — donor fa4cd8d1 → base aebcfda3

Donor: `ws232/xmage-retention-nscoped-requalification-20260915` @
`fa4cd8d1` (cumulative WS213→WS215→WS218→WS229→WS232, read-only).
Merge-base with main: `7725570b`. Main-side touched NONE of the ported
production paths since MB (verified per file); shared-test overlaps were
checked file-by-file (none).

## Commit 291dc89a — production (31 files, donor blobs wholesale)

Java (`engine-bridge/src/main`, same xmage-1.4.61 pin):
Phase6DifferentialAdapter, XmageFullGameActionProjection (NEW),
XmageFullGameDecisionController, XmageFullGameJsonlBridge,
XmageFullGamePlayer, XmageFullGameSession, XmageFullGameStateRedactor,
XmageProvider.

Python: agents/pilots.py, candidates/models.py,
engine/rules/full_game.py, engine/rules/full_game_batch.py,
robustness.py, semantic_replay/{__init__,canonicalization,capability,
consumer,divergence,fingerprint,recorder,source_lock,tape,tape_helpers}
(NEW package).

Config/docs/scripts: config/rules_engines.json (pin prose cfc36f44→
db134b97; lineage DIRECTLY_VERIFIED: db134b97 is a 5-commit descendant of
cfc36f44 on origin/mage, WS206/WS211/WS212), docs/
OPERATIONAL_SIMULATION_POLICY.md, docs/architecture/
{deckbuilding-simulation-separation,xmage-full-game-external-pilots}.md,
scripts/{bootstrap_engine_linux.sh,bootstrap_engine_windows.ps1,
generate_full_game_contract_artifacts.py,run_external_full_game_conformance.py}.

Uncommitted follow-up: `.github/workflows/external-engine-integration.yml`
(2 lines: workflow pin defaults → db134b97; install logic untouched).

## Commit 009bf560 — tests (35 files, donor blobs wholesale)

Java (19): JsonlBridge, Ws204DecisionKindCensus, Ws92D1D2D3Projection,
Ws92D4ChoiceProjection, Ws92DecisionKindCensus, XmageDecisionRejectionWs229,
XmageFullGameActionProjection, XmageFullGameBridgeContract,
XmageFullGameCombatDamage, XmageFullGameConcedeAction,
XmageFullGameGenericActionSubmission, XmageFullGameGenericBridge,
XmageFullGameHiddenInformation, XmageFullGameNameCanary,
XmageFullGamePlayerBoundary, XmageFullGamePlayerCount,
XmageFullGameRulesSeedBinding, XmageNumericDomainWs229,
XmageVariablePlayerLifecycle.

Python (16): unit/{operational_4p_policy, semantic_replay_tape,
ws223_cardinality_regression, ws223_environment_identity, ws224_name_canary,
ws229_numeric_domain, ws_a1d_docker_pin_authority, ws_a1r_pin_authority,
ws_arclose_d1_authority_drift, xmage_compatibility_provider,
xmage_full_game, xmage_full_game_decision_matrix, xmage_variable_player},
tests/test_candidate_lossless_handoff.py,
tests/qualification/test_ws232_retention_predicates.py.

Fixture: qualification/ws215-.../decks/ws215_lions.json (100-card
technical deck, test input).

## Fixture ports (test inputs, donor bytes, provenance cited)

- qualification/ws218-.../tapes/ws218-tape-{2,3,4,5}p.json (canary inputs)
- qualification/ws232-.../{WORKLOAD_DERIVATION,RETENTION_PREDICATES,
  RETENTION_PREDICATE_RESULTS,RETENTION_PREDICATE_SCHEMA}.json
- qualification/ws232-.../bin/check_predicates.py (static evaluator)
- qualification/manifests/AUTHORITY_LOCK_v2.json (byte-exact, content SHA
  319e6921… verified; semantics owned by G01/WS226/WS229 per predicate
  metadata — carried as fixture, no authority authored here)

## Deliberately NOT ported (with rationale)

- Donor evidence/research dirs (micro-rules/actual-card campaigns,
  observations, matrices): provenance stays on donor branches; behavior
  requalified fresh on new base instead of relabeled.
- tests/qualification/{test_ws17r_exact_main_runtime,
  test_ws221_evidence_vocab, test_ws222_authority, test_ws225_standing}:
  governance tier (Coordinator), not simulator function.
- .github/workflows (beyond the 2 pin-default lines): main owns CI wiring;
  donor install/lock regime (requirements/lock.txt) not adopted.
- scripts/{generate_lock_appendix,verify_dependency_lock,
  write_environment_receipt}: lock-governance tooling, no ported test needs.
- requirements/lock.* + WS17_SHA256SUMS + .gitignore deltas: main's regimes
  retained.
- tests/test_candidate_lossless_handoff.py IS ported but uncollectible here
  (hypothesis missing — pre-existing environmental, main's version needs it
  too).
