# Unowned Mage Edits — Rejected Residue Preservation (WSR25, 2026-09-27)

Coordinator ruling: `REJECTED_STALE_EXPERIMENTAL_RESIDUE`. Must NOT be promoted.
Must NOT influence canonical Mage candidate `b1959698`.

- Worktree: `/home/moeen/code/xmage-ws49-baseline`, detached base `0c1f455ea8c8fa48ab9d638ad5068ec242800428` (WS42 commander-damage API).
- Seven tracked modifications (unstaged, preserved here binary-safe in `UNOWNED_MAGE_EDITS_REJECTED.patch`):
  five card shuffles + `PlayerImpl.java` (2 sites) re-routed to global `RandomUtil.getRandom()`,
  plus `RandomUtil.java` `RecordingRandom` tape instrumentation (WS-39 style).
- Reason (accepted from audit): not present in `b1959698`, never committed to candidate lineage,
  no gate consumes them, no runtime binds them; conflicts with canonical per-game
  Rules-RNG architecture (WS54: `game.getRulesRandom()`, `RandomUtil` demoted to NON-RULES).
- Ownership check 2026-09-27: detached HEAD, no branch, no stash, no locks, no workstream
  state claim, only own-shell cwd in `lsof`. Genuinely ownerless → eligible for cleanup §12.
- Preservation is FORENSIC PROVENANCE ONLY and grants NO qualification credit.
- File hashes (dirty state): `UNOWNED_MAGE_EDITS_SHA256.txt`. Base: `UNOWNED_MAGE_EDITS_BASE.txt`.
- Diffstat: `UNOWNED_MAGE_EDITS_DIFFSTAT.txt`. Status-before: `UNOWNED_MAGE_EDITS_STATUS_BEFORE.txt`.
