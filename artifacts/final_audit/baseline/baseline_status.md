# Unchanged baseline — 1.10.1

- Drive repository SHA-256: `a814523177e7ee848716b3e4cec639a34d3657821aee2a8a8a306a90e6904e36` (`passed`)
- Safe ZIP extraction: `passed` (1343 entries, no path traversal, no symlinks, ZIP CRC passed)
- Git commit: `6459581cc3e886d412d8e3c1bf3c1f7dfe0f3009`
- Package version: `1.10.1`
- Collected tests: 256
- Unit tests actually executed: 199 passed
- Integration excluding Phase-10 acceptance: 21 passed
- Phase-10 acceptance smoke: `failed` as an audit gate because it did not finish within 120 seconds in a fresh Drive restore; no pass is claimed.
- Remaining categories were interrupted by the same process-lifecycle behavior during baseline isolation and are re-run after regression fixes.
- Drive-reported prior handoff: 255 passed, 1 skipped. This remains historical evidence, not a substitute for the current audit run.
- External engine: not configured; validation pending.
