# WS223 Design Options (chosen options marked CHOSEN)

## D1 — Cardinality smoke boundary

- (a) Full game-over + replay for every N (2,3,4,5). Rejected: ~4× JVM cost,
  repeats WS215's matrix on every commit against the contract's cost bound.
- (b) CHOSEN: bounded lifecycle smoke for 2/3/5 (native start, seed/count
  binding, mulligan+priority progression, unsupported-callback watch, clean
  `shutdown_engine` termination at a calibrated decision target) + unchanged
  full 4P game-over/replay pair. Rationale: every smoke-scope item in the
  contract except terminal/outcome-shape is covered live per-N; terminal +
  one-outcome-per-seat per-N is covered by existing unit guards
  (`test_build_result_requires_one_outcome_per_seat`, parametrized 2–5) plus
  the live 4P terminal. Smallest system that catches all listed regressions.
- (c) Pure unit/matrix-YAML gate. Rejected by the contract (forbidden shortcut).

## D2 — Bounded-smoke implementation site

- (a) Script drives private `_RawFullGameClient` directly. Rejected: second
  lifecycle path, duplicates validation/handshake.
- (b) CHOSEN: additive `XmageFullGameRunner.run_smoke()` reusing
  `_validate_inputs`, `_validate_handshake`, policy construction, and the
  client's clean `close()`; returns `FullGameSmokeResult`. `run()` bytecode
  semantics unchanged. New method is production-reachable code but
  smoke-scoped by contract (fail-closed validations identical to `run()`).

## D3 — 6P fail-closed layering

- CHOSEN: layer 1 = `FutureXmageScenario` model (`ge=2, le=5`) rejects 6P at
  construction (script `--expect-fail-closed` proves it with zero JVM);
  layer 2 = `_validate_inputs` rejects any 6P scenario smuggled via
  `model_copy` (unit test); layer 3 = policy rejects 6 runtimes (existing).
  No 6P support claimed anywhere.

## D4 — Python lock mechanism

- (a) `pip freeze` snapshot. Rejected: no hashes, no regeneration command,
  platform/leakage-prone.
- (b) Poetry/PDM/uv migration. Rejected: replaces project conventions
  (setuptools + pip + setup-python) with a new ecosystem for lock's sake.
- (c) CHOSEN: `pip-tools` (pinned `7.6.1`) `pip-compile --generate-hashes`
  over `requirements/lock.in` (union of all pyproject extras + audit tools +
  explicitly-declared `jsonschema`), emitting `requirements/lock.txt`;
  install path `pip install --require-hashes -r requirements/lock.txt` +
  `pip install --no-deps -e .`. Provenance + tool versions in lock header.
  Single lock with environment markers (one file, all platforms); CI cache
  explicitly keyed on it.

## D5 — Lock-vs-3.12 skew (local interpreter is 3.14)

- CHOSEN: compile for the running resolver, then machine-verify every pin's
  `Requires-Python` allows 3.12 (script check against PyPI metadata +
  `pip install --dry-run --require-hashes --python-version`… — concretely:
  metadata assertion script + CI's real 3.12 locked install as the final
  proof). Clean-resolution venvs prove determinism (A==B); the 3.12
  compatibility proof is the metadata gate plus first CI run. Both recorded
  honestly with distinct statuses.

## D6 — JDK identity

- (a) Align everything to 17 (incl. containers). Rejected: no evidence the
  full-XMage-source container build tolerates 17; arbitrary downgrade.
- (b) Align everything to 21. Rejected: contradicts bytecode authority
  (`release=17`) and current passing CI state; arbitrary upgrade.
- (c) CHOSEN: documented matrix — bytecode floor 17 (pom authority); CI JVM
  lanes Temurin 17 (major pin, patch recorded per-run in receipt); containers
  Temurin 21 digest-pinned (zero-change, immutability only). Receipt records
  actual `java -version` per run so skew is visible, never silent. Future
  advisory: evaluate container 21→17 with a real image-build test.

## D7 — Container identity

- CHOSEN: `FROM eclipse-temurin:21-jdk@sha256:1f79c734…` (manifest-list
  digest observed 2026-09-15) + `LABEL org.commander-lab.base-image*` human
  annotations. Zero byte-change from today; float eliminated. Re-verification
  without a daemon via Hub registry API documented in CONTAINER_IDENTITY.

## D8 — PYTHONHASHSEED policy

- CHOSEN: `PYTHONHASHSEED: "0"` top-level `env` in every workflow that
  executes Python tests/qualification/conformance (12 lanes added; 4 already
  had it). `opencode.yml` exempt (no Python execution; documented). Static
  test enforces. Explicit non-claim: hashseed does not control JVM Rules RNG
  (engine-owned; recorded in policy file).

## D9 — Cache identity

- CHOSEN: explicit `cache-dependency-path: requirements/lock.txt` (+
  `pyproject.toml`) on every `setup-python cache: pip` step; keep
  `setup-java cache: maven` (pom-bound). No cache destruction; old
  environments cannot masquerade (key changes with lock bytes). Static test
  enforces. Docker-layer caching untouched (no registry cache configured).

## D10 — Environment receipt

- CHOSEN: `scripts/write_environment_receipt.py` → JSON receipt (python
  impl/version, lock digest, resolved-set digest, java identity, image ref
  passthrough, hashseed, tool versions, engine pins) + `*_identity.sha256`
  over the canonical (clock-free) subset. Called by CI lanes post-install;
  schema asserted by unit test. Secrets never collected; wall-clock kept
  informational only, excluded from identity digest.
