# Canonical Drive sync handoff – 1.13.3

This branch records the canonical pre-XMage data-sync release while preserving the distinction between the GitHub history and the authoritative Google Drive Git history.

## Canonical release

- Package version: `1.13.3`
- Canonical local/Drive commit: `f6c53d2d244363b58cbfc46c411ae801309d77d9`
- Canonical parent: `bcf154a9de8627659fac67b76a423fbb6ca3685f`
- GitHub main at handoff: `76888d23f03a776274b43b82164076ca9acf7903`
- GitHub does not contain `bcf154a9...`; therefore this branch MUST NOT be treated as the canonical Git lineage.

## Exact-history recovery artifact

The authoritative Git bundle is `commander-playtest-lab-1.13.3.bundle`.

SHA-256: `770c4b588a1272d1974647591b898b8e878a4efd2663b88d1321ef507a335389`

The bundle was verified as complete and cloned successfully to HEAD `f6c53d2d244363b58cbfc46c411ae801309d77d9`, parent `bcf154a9de8627659fac67b76a423fbb6ca3685f`, package version `1.13.3`.

## Validation

- 288 tests collected
- 287 passed
- 1 skipped: external XMage/Forge differential test only
- 0 failed
- `git diff --check`: passed
- `python -m compileall -q src tests`: passed
- Drive data audit: `MATCH`
- data sync dry-run: `MATCH`, no mutation
- external XMage/Forge observations: 0
- external rules-engine validation remains pending

## Current deck hashes

- Korvold: `72c0cb6a804cfb97b5cb048ca5e2b261782037044f6360b98a6b7df51c79bf1f`
- RogShai: `3827c35995e280753c4e714e391b9baf0a34e2c019e9df519ea1db0260ff9932`

This marker exists specifically to prevent the older GitHub-only history or the previously misbased `feature/data-sync-before-xmage` branch from being mistaken for the canonical 1.13.3 release.