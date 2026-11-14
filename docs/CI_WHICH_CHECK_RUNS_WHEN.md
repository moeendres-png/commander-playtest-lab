# Which check runs when (state after CI package B, 2026-11-14)

Required checks (branch ruleset): `quality`, `security`, `infrastructure`. Nothing else blocks a merge.
Wall-clock figures are from real runs of PR #1359 (the pull-request head), not estimates.

| Check (job) | Starts on | What it proves | Time |
|---|---|---|---|
| `quality` (gate over `changes`, `lint`, `tests 1/4..4/4`, `packaging`) | every pull request, push to `main`, dispatch | the ruff, format, mypy, compile, secret-scan and wheel checks, and every test outside `tests/qualification`; the gate (`scripts/ci_gate.py`) is green only if each needed job succeeded | about 2.5 min (slowest `tests` slot) |
| `tests` slots | as `quality`; a documents-only PR runs one slot with the docs tests (`tests/pytest_docs_tests.json`) | the unit, integration, contract and golden suites, four runners with four shards each | 100 to 145 s |
| `packaging` | push to `main`; a PR that changes a packaging input (`pyproject.toml`, `requirements/`, an added/deleted `src/` module, a package `__init__.py`, a console-script module, the smoke tooling) | an isolated wheel install imports and runs every console entrypoint | about 4.5 min when it runs |
| `security` | every pull request, push to `main` | dependency audit, SBOM, license report | 1.5 to 2.5 min |
| `infrastructure` (`production-qualification.yml`) | every pull request, push to `main`, dispatch | `tests/qualification` (four in-job shards) and the fixture manifest | 105 to 120 s |
| `exact-main-admission` | push to `main` only | the production admission record for the exact main SHA | about 1 min |
| `ci-definition-integrity-shadow` | every pull request to `main` (`pull_request_target`, runs `main`'s checker) | informational: the required-check definitions. Green for added or extended tests; red only for a changed required-check definition, a removed test or assertion, a new skip, `conftest.py`, other test data, or a gate script | under 1 min |
| `repository-tree-integrity` | every pull request to `main` (`pull_request_target`) | the tree contains no forbidden paths | under 1 min |
| XMage Full Game Conformance | PR and push to `main` that touch the engine bridge, the engine rules code it runs, its scripts or pin (`paths:`), dispatch | the bridge Java suite, SpotBugs, a real four-player game, replay and the 2/3/5/6/7-player smokes | 10 to 13 min |
| XMage Real 4P Technical Smoke | same kind of paths (bridge, full-game code, its scripts and decks), dispatch | one real four-player game through the live bridge | about 2 min |
| External XMage Integration | bridge and rules-engine paths, dispatch | B3 to B4F regression scripts and the Phase-6 differential against the pinned engine | about 5 min |
| Meta Qualification | meta-verification code, engine and replay paths | live mutation-kill of replay and hidden-information checks | about 3 min |
| H4 Docker Materialization | PR for `docker/**`, the compose file, `engine-bridge/**`, the pin authority and the H4 scripts; dispatch | the Docker image build, provenance gate with negative controls, and a real container handshake | 15 to 25 min |
| PB-03 Runtime Qualification | PR for `engine-bridge/**`, `src/commander_lab/qualification/**`, the qualification fixtures, the pins and its scripts; dispatch (sealing dispatches it). Not for general lab code (`src/commander_lab/engine`, `agents`, `models`, ...). | the current-boundary runtime qualification | 25 to 32 min |
| Core Workflow Acceptance | PR and push to `main` for `src/commander_lab/**` and its data inputs | the J-P6 workflow smoke on real data | about 2 min |
| Windows Runtime Hygiene | PR for the modules and tests it executes; push to `main`; dispatch | Windows junction, atomic-storage, run-manifest and runtime-hygiene contracts | about 1.5 min |
| Release Artifacts | push to `main`, `release/**`; PR that changes `pyproject.toml` or its own file | the release build and its contents | about 2 min |
| Exact Main Recovery | push to `main` | the recovery payload of the exact main SHA | about 1 min |
| Decision Support Regression, Batching Qualification, Collection Coverage, Studio EDHREC Proof Capture | dispatch only | historical or long manual lanes | on demand |
| Determinism Multi-Seed | dispatch, or the PR label `determinism-multiseed` | twin real-pod runs compared | about 12 min |

Rules of thumb
- A run that does not appear in the check list of a PR did not start because no path of its filter changed. That is intended, not a skipped check.
- `quality` is the only gate over several jobs. A red `lint`, `tests` or `packaging` makes `quality` red; a skipped `packaging` is accepted only when `changes` reports that no packaging input changed.
- Shard weights: `python -m tests.pytest_shards weights --from-artifacts > tests/pytest_shard_weights.json` rebuilds the table from the JUnit artifacts of the latest main run (`--qualification` for `tests/qualification`). A new test file without a weight is allowed; the guard fails only for a table entry of a missing file or when more than 5 % of the files are unweighted.
