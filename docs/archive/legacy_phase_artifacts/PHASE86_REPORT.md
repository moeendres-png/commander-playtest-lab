# Phase 8.6 system audit report

## Verdict

The locally executable portion of Phase 8.6 was completed and hardened. The entire requested phase is **not fully accepted** because mandatory external/static tools could not execute in the sandbox.

```text
status=phase_9_blocked
external_engine_validation_pending=true
```

## Baseline

- Protected baseline commit: `a189065d7ed90bc057a32fdeadd681365d64463c`
- Working branch: `phase/8.6-system-audit`
- Baseline tests: 130 passed, 1 external test skipped.
- Hardened tests: 145 passed, 1 external test skipped.

## Bugs found and fixed

| Severity | Count | Status |
|---|---:|---|
| Critical | 1 | fixed and regression-tested |
| High | 3 | fixed and regression-tested |
| Medium | 2 | fixed and regression-tested |
| Low/Cosmetic | 0 | none recorded |

Key fixes:

1. Legacy/mock bridge responses can no longer become `rules_engine_validated`.
2. Phase 8.5 contract evidence now records messages actually exercised.
3. Handshake health alone no longer marks external integration ready.
4. Key JSON, registry, process-state and event-log writes are atomic.
5. Runs can be hash-verified and quarantined.
6. SQLite backup/restore works with WAL and is integrity-checked.
7. Experiment hypotheses, variants, scenarios, seeds and acceptance criteria are sealed together.
8. Stronger game-state invariants, architecture boundaries, deterministic fuzz guards and mutation guards were added.
9. The Phase 8.5 tactical contract was changed from 14 costly subprocess launches to one persistent bridge process.

## Tests and checks

- `pytest`: 145 passed, 1 skipped.
- `pytest --collect-only`: passed.
- Python compile check: passed.
- Local Phase-8.6 acceptance workflow: passed.
- SQLite integrity: passed.
- Tactical validation: passed as `tactical_oracle` only.
- External rules engine: not run.
- Ruff: blocked because executable/package unavailable.
- Ruff format: blocked.
- mypy: blocked.
- Native Hypothesis state-machine tests: blocked.
- Automated mutation tool and coverage-guided fuzzing: blocked.
- Dependency vulnerability audit and generated CycloneDX SBOM: blocked by package/network access.

Targeted deterministic fuzz and mutation-regression tests were executed, but they are not represented as native Hypothesis or mutmut runs.

## Implemented hardening/features

- atomic persistence and run manifests;
- run verification and quarantine;
- SQLite check/migrate/backup/restore;
- sealed experiment registry;
- scenario editor;
- replay debugger;
- structured redacted logging and metrics;
- `commander-lab doctor`;
- database and run-integrity CLI commands;
- model/protocol schema export;
- CI workflow for lint/type/tests;
- external XMage integration workflow that cannot silently fall back.

## Remaining blocking work

1. Run Ruff, formatting, mypy, Hypothesis, mutation, dependency audit and SBOM in network-enabled CI.
2. Implement and build the real provider-specific XMage Java bridge.
3. Execute external build, handshake, legal-action loop, four-player Commander game, replay and critical scenarios.
4. Import the real external evidence and rerun the full acceptance gate.

## Data safety

No final Korvold or RogShai deck list, canonical inventory, or Google Drive project file was changed.
