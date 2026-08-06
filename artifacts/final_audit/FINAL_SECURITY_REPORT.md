# Final Security and Integrity Report

## Executed

- Safe ZIP inspection of the Drive repository: 1,343 entries, no absolute paths, no `..` traversal, no symbolic links, CRC test passed.
- Repository SHA-256 matched the current Drive handoff: `a814523177e7ee848716b3e4cec639a34d3657821aee2a8a8a306a90e6904e36`.
- `git fsck --full` and `git diff --check` passed before changes.
- Custom tracked-file secret scan found no API key. `.env` is not tracked; `.env.example` contains only an empty placeholder.
- No `shell=True`, unsafe YAML load, pickle deserialization, `eval` or `exec` use was found in `src` or `scripts` by the executed pattern scan.
- Atomic write and run-manifest integrity tests passed in the final regression suite.
- Bridge subprocesses now close streams and join pump threads deterministically.
- `pip check` executed.

## Findings

`pip check` reported a global container conflict: `moviepy 2.2.1` requires `pillow<12.0`, while Pillow 12.2.0 is installed. MoviePy is not a declared Commander Playtest Lab dependency; the finding is environment-level and does not change project test results.

## Blocked tools

The following were not installed and were not claimed as executed: `pip-audit`, CycloneDX SBOM generator, Ruff, mypy, Hypothesis and mutmut. Maven, Gradle and Docker were also absent. These are routed to Codex/networked CI.

## Result

Local security and artifact-integrity checks: `passed_with_limitations`. No secret exposure or critical integrity defect was found. Dependency vulnerability scanning and SBOM generation remain `blocked_not_installed`.
