# Phase 12.19 – Quality, Security and Performance

## Status

`quality_security_performance_completed_with_limitations`

The final consolidated suite contains **282 tests: 281 passed, 1 expected external-engine skip, 0 failed**. Tests were completed in isolated groups/files because the monolithic process can remain alive after test output due to a known child-process/pipe cleanup issue; this lifecycle defect is recorded rather than misreported as a clean monolithic pass.

## Required quality tools

A fresh installation attempt was made for Ruff 0.15.22, mypy 2.3.0, Hypothesis 6.160.0, mutmut 3.6.0, pip-audit 2.10.1, CycloneDX BOM 7.3.0 and pip-licenses 5.5.5. The runtime package index could not provide the packages. Therefore none of those commands is claimed as executed.

Locally executable checks passed: `compileall`, `git diff --check`, `git fsck --full`, deterministic property tests, mutation guards, boundary fuzzing, tracked-file secret scanning, atomic-write and integrity tests.

`pip check` reports one global environment conflict: moviepy 2.2.1 requires Pillow <12 while the runtime has Pillow 12.2.0. It is separated from project dependency health.

## Security

- 751 tracked text files scanned for common credential forms; **0 findings**.
- AST scan found **0** `shell=True`, `eval`, `exec`, or archive `extractall` calls in active source/scripts.
- The dynamic legacy-table DROP statement is constrained to the constant `LEGACY_MANUAL_PLAYTEST_TABLES` allow-list.
- Atomic persistence uses temporary files, `fsync`, and atomic rename.
- Fallback SBOM/license inventories remain clearly labeled as fallbacks; official CycloneDX/pip-licenses execution is blocked.

## Performance

Current final-code measurements include 100-game structural goldfish, 20 four-player games, mulligan sampling, paired comparison, counterfactual branchpoint scan, decision diagnostics and MCP 2026 `server/discover`/`tools/list`. All local measurements passed. XMage and Forge remain blocked; Parquet remains unused because it is not an active persistence requirement.

No canonical deck, inventory, or allocation files were modified.
