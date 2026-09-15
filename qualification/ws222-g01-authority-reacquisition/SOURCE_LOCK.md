# WS222 SOURCE_LOCK

- Repository: `moeendres-png/commander-playtest-lab`
- Branch: `ws222/g01-authority-reacquisition-20260915`
- Audit base (terminal published WS220): `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b`
  (tree `6bc707b37f8fb39950f4ade2db11e7ccef03dab6`)
- HEAD at WS222 start: `1a6ffcdaa264bb64dbc32c9b32019092fc4a896b` (clean worktree, verified via `git status` / `git rev-parse HEAD` / `git rev-parse HEAD^{tree}`).
- WS220 inputs consumed (read-only, never mutated):
  `research/project-audit/ws220/FINDINGS.json` (F-QUAL-02),
  `research/project-audit/ws220/SUCCESSOR_PROPOSALS.json` (S3),
  `research/project-audit/ws220/QUALIFICATION_AUDIT.md`,
  `research/project-audit/ws220/SOURCE_TRUTH_MAP.md` + `.json`,
  `research/project-audit/ws220/FINAL_HANDOFF.md`.
- Active-workstream boundary: WS218 (Semantic Replay) and WS221
  (evidence vocab/integrity/source truth) surfaces are not mutated by WS222.
  If WS221 changes evidence enums while WS222 runs, WS222 does not chase the
  unpublished branch; drift is reported as POST_LOCK_DRIFT for Coordinator
  integration.
- Reference roots: none declared (`FOUNDRY_REFERENCE_ROOTS = []`).

`ARCHITECTURE_FREEZE = NOT_CLAIMED`. `PRODUCTION_PROVIDER = NOT_SELECTED`.

Machine companion: `SOURCE_LOCK.json`.
