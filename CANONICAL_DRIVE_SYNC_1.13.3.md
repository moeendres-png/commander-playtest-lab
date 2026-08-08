# Canonical Drive sync handoff – 1.13.3

This branch is a **non-canonical GitHub marker only**. It records the verified pre-XMage data-sync release while preserving the distinction between the GitHub object database and the authoritative Google Drive Git history.

## Canonical release

- Package version: `1.13.3`
- Canonical local/Drive commit: `ebb3a3b520a2ad22537a4c90059cef92a4ee4b79`
- Canonical parent: `bcf154a9de8627659fac67b76a423fbb6ca3685f`
- GitHub main at verification: `76888d23f03a776274b43b82164076ca9acf7903`
- GitHub does not contain `bcf154a9...` or `ebb3a3b...`; therefore this branch MUST NOT be treated as the canonical Git lineage.

## Exact-history recovery artifact

The authoritative full-history artifact is `commander-playtest-lab-1.13.3.bundle` in Google Drive folder `23_Pre_XMage_Data_Sync_1.13.3_FINAL` (folder ID `1QDcD2O2CrQtbqLAX6RLPDnvxiiI2ZWWQ`).

SHA-256: `9ad11464d86ffe9a32da15f5d8be3cb928a7a437d805aae1b71fefeaaff451c8`

The bundle was downloaded from Drive, cloned successfully, and verified at HEAD `ebb3a3b520a2ad22537a4c90059cef92a4ee4b79`, direct parent `bcf154a9de8627659fac67b76a423fbb6ca3685f`, package version `1.13.3`; `git fsck --full` passed.

## Validation

- 288 tests collected
- 287 passed
- 1 skipped: real XMage/Forge differential test only
- 0 failed
- `git diff --check`: passed
- `python -m compileall -q src tests`: passed
- Drive data audit: `MATCH`
- data sync dry-run: `MATCH`, no mutation
- Drive artifact roundtrip: byte-identical against the final SHA-256 register
- external XMage/Forge observations: 0
- external rules-engine validation remains pending

## Current deck hashes

- Korvold: `72c0cb6a804cfb97b5cb048ca5e2b261782037044f6360b98a6b7df51c79bf1f`
- RogShai: `3827c35995e280753c4e714e391b9baf0a34e2c019e9df519ea1db0260ff9932`

## Required GitHub completion

Exact synchronization requires pushing the canonical Git objects from the verified bundle/clone with normal Git transport. Do **not** reconstruct replacement commits from the older GitHub `main`, because that would create different commit identities and break the canonical ancestry.

`00_LATEST` must remain gated until the exact canonical history is present on GitHub.