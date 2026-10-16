# J-P0 — Integrität, Run Identity und fail-closed Projektwahrheit

## Status

Roadmap-J-P0 erweitert die vorhandene CommanderToolService-Provenienz zu einer universellen,
fail-closed RunIdentity. Es wurden keine Deck-, Inventar-, Gegner-, Pilot-, Kartenprofil- oder
Optimierungsgewichte verändert.

Baseline vor P0:

- GitHub main: `85af667c2bda54c3d1370dc0f83046dca9d34c1c`
- Tree: `c98a707010a3fb58aa8beadbbcd39bdbbf3e009b`
- Package: `1.13.4`
- PRE-J: complete; Roadmap J start allowed.

P0 changes the package version to `1.14.0` because the decision-evidence schema and CLI runtime
output are product behavior, while `public_release_required` remains false for this phase.

## Measured identity gaps

The pre-P0 ToolService already bound deck, inventory, pilot, policy, meta, opponent and scenario
hashes. P0 closed the remaining decision-evidence gaps:

- Git tree and package version were not part of one typed universal identity;
- identity component states did not distinguish `NOT_APPLICABLE`, `UNKNOWN` and
  `MISSING_REQUIRED`;
- canonical serialization did not have dedicated Unicode/float/path normalization rules;
- canonical prepared-source ID/hash mismatch was not part of the per-run stale gate;
- commander configuration, opponent ensemble, seed-set and rules-fixture identities were not
  first-class fields;
- direct structural CLI output did not emit a reusable RunIdentity sidecar;
- the G holdout had already been evaluated and therefore could not serve as a fresh blind J
  holdout;
- the newer Aug-08 deck workbook was not represented as the current Drive alias even though the
  prepared import remains correctly bound to its Aug-07 provenance bytes.

## Universal RunIdentity

`RunIdentity` schema `1.0.0` now records, when applicable:

- software commit, tree and package version;
- deck hashes and commander configuration hash;
- inventory source ID and content hash;
- opponent profile IDs/hashes and opponent ensemble hash;
- pilot name/version/parameter hash and policy hash;
- scenario-set ID/hash;
- pod size, seat and turn-order policy;
- seed/seed-set hash and simulation configuration hash;
- structural model version;
- engine mode/provider/provider pin/capability identity;
- tactical fixture version;
- canonical source-manifest hash;
- explicit per-component identity status;
- canonical/stale/historical-replay status and stale reasons.

`created_at` is excluded from the semantic RunIdentity hash.

## Canonical serialization

The P0 canonical run serializer:

- sorts mappings deterministically;
- normalizes Unicode to NFC;
- represents finite floats by deterministic hexadecimal value;
- rejects NaN and infinities;
- normalizes project paths to `project://...` form;
- preserves list order where order is semantically relevant;
- sorts unordered sets deterministically;
- excludes timestamps from the semantic identity payload.

This serializer is separate from the existing deck-hash serializer so P0 does not silently change
historical deck identities.

## Fail-closed stale input behavior

Canonical decision-level runs now reject:

- prepared canonical source ID mismatches;
- prepared canonical source hash mismatches;
- deck-manifest/current-source deck-hash mismatches;
- missing referenced opponent ensembles;
- pilot profiles bound to a different current deck hash;
- a tracked worktree that differs from the recorded Git tree.

Historical replay is allowed only when the request explicitly carries `historical_replay=true`;
the identity then records `canonical_input_status=historical_replay` and retains stale reasons.

## Drive source alias reconciliation

The prepared deck import remains provenance-bound to Drive file
`1mO0pnm1thoRrjAg7TGuGSXmrTTYDivJHxrUCdEtY5GQ` and its recorded source SHA. The source registry now
also records the later Drive final `1nDVdTnCXoGEuCnf5uL4Gu6YXbvTthNVNLMMi1Y_1PD8` as the active
canonical alias with unchanged canonical deck hashes. P0 does not rewrite prepared source bytes or
deck content.

## Entry-point coverage

- ToolService / Python decision API: typed universal RunIdentity and public
  `build_run_identity(...)` helper.
- FastAPI tool server: uses ToolService and therefore emits the same metadata.
- MCP/toolserver: uses ToolService and therefore emits the same metadata.
- OpenAI/agent workflow: uses the same tool registry/service boundary; no separate provenance path.
- Structural goldfish/matchup/paired/ablation/commander-denial/sensitivity/search tools: ToolService
  metadata binds the same identity fields.
- Reporting tools: input tool responses are included in the report request identity; report tool
  metadata carries RunIdentity.
- Direct CLI `run-structural-batch`: emits `run_identity` with the aggregate and writes
  `run_identity.json` beside runtime output.
- Tactical Oracle: explicitly identified as `engine_mode=tactical_oracle`.
- External-engine request: explicitly identified as `engine_mode=external`; provider version and
  capability remain `UNKNOWN` before a real provider handshake and are not promoted to external
  validation by P0.

Low-level structural engine functions remain internal primitives; a result becomes project decision
evidence only through a decision-level wrapper carrying RunIdentity.

## Eval registry / holdout

`data/evals/j_eval_registry.json` freezes four J evidence classes:

1. `DEVELOPMENT_GOLDENS` — existing 24-case G development corpus;
2. `UNTOUCHED_HOLDOUT` — new `J_HOLDOUT_v1`, 12 sealed exact cases spanning both pilots and
   3/4/5-player pods;
3. `SENSITIVITY_AND_ADVERSARIAL` — existing composite robustness/opponent/mulligan baseline;
4. `RULES_CRITICAL_FIXTURES` — existing Tactical/Structural/Differential rules corpus.

The prior 12-case G holdout remains frozen legacy regression evidence and is explicitly *not* the
fresh J holdout.

`J_HOLDOUT_v1` was schema-validated in P0 but never evaluated. It has:

- `mutable=false`;
- `used_for_tuning=false`;
- `first_evaluation_timestamp=null`.

If a later phase tunes against this holdout, its independent status is invalidated and a new
holdout version is required.

## Local validation

Authoritative P0 local validation was performed in deterministic batches because the single full
pytest invocation exceeded the execution-window limit. Every collected test file was subsequently
run.

- pytest collection: 336 tests;
- PASS: 335;
- SKIP: 1 expected real XMage/Forge differential test without configured external provider;
- FAIL: 0;
- P0 targeted RunIdentity/compatibility tests: PASS;
- `python -m compileall -q src tests`: PASS;
- `git diff --check`: PASS;
- `git fsck --full`: PASS (historical dangling commits only);
- canonical data audit: MATCH;
- CLI structural RunIdentity smoke: PASS, sidecar hash equals displayed hash;
- API/MCP/toolserver integration tests: PASS;
- clean-tree after doctor/audit/runtime smokes: PASS;
- wheel build (`pip wheel --no-build-isolation`): PASS for `1.14.0`;
- installed wheel import with available runtime dependencies: PASS;
- local Ruff: `LOCAL_UNAVAILABLE` (package mirror cannot supply Ruff);
- local Mypy: `LOCAL_UNAVAILABLE` (package mirror cannot supply Mypy);
- local Python: 3.13.5; GitHub CI remains the Python-3.12 final authority.

Legacy `audit-phase86 --skip-tests` remains `phase_9_blocked` locally only because Ruff/Mypy are
unavailable in this runtime and real external-engine validation is intentionally pending. Its
execution leaves the tracked tree clean. Those statuses are not converted to PASS.

## Scope boundaries preserved

- Structural estimates remain model estimates, not empirical winrates.
- Tactical Oracle remains distinct from XMage/Forge.
- No real external-engine validation is claimed by P0.
- `real_playtest_calibration=inactive_project_scope`.
- No automatic canonical deck/inventory/purchase/allocation mutation.
- Kaervek remains frozen opponent-only.

## Release decision

- `package_version_bump_required = true` → `1.14.0` because RunIdentity/CLI behavior is product code.
- `recovery_snapshot_refresh_required = true` after merge because canonical main/package changes.
- `public_release_required = false`; Roadmap J still prefers the public/final canonical release in
  J-FINAL.
